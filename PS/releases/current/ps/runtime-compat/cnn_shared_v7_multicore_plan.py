"""Offline memory and descriptor plan for a future multi-core v7 runtime.

This module never touches a board.  It deliberately gives every normal block
its own full-tensor destination inside one frame/profile memory object.  That
avoids recycling a ping-pong tensor while another core can still be reading a
halo from it.  Scratch is private per core.  The runtime scheduler remains
responsible for proving the predecessor halo4 rows are committed.
"""

import argparse
import json
from pathlib import Path

import cnn_shared_v7_contract as contract
import cnn_shared_v7_scheduler as scheduler


WORD_BYTES = 16
ALLOCATION_GRANULE_WORDS = (64 * 1024) // WORD_BYTES
MAX_PLANNED_CORES = 4


def _align_up(value, alignment=ALLOCATION_GRANULE_WORDS):
    value = int(value)
    alignment = int(alignment)
    if value < 0 or alignment <= 0:
        raise ValueError("alignment operands must be positive")
    return ((value + alignment - 1) // alignment) * alignment


def _region(name, offset_words, used_words):
    return {
        "name": str(name),
        "offset_words": int(offset_words),
        "used_words": int(used_words),
        "extent_words": _align_up(used_words),
    }


def build_plan(profile, core_count, frame_id="frame-0"):
    """Return one profile chain layout for a single logical frame.

    ``core_count`` is a software planning parameter.  The routed design must
    report the actual count before this plan becomes board eligible.
    """
    spec = contract.profile_spec(profile)
    core_count = int(core_count)
    if core_count < 1 or core_count > MAX_PLANNED_CORES:
        raise ValueError("core_count must be in 1..%d" % MAX_PLANNED_CORES)
    tensor_words = spec["channels"] * spec["width"] * spec["width"] // 8
    offset = 0
    tensors = []
    for index in range(spec["blocks"] + 1):
        name = "input" if index == 0 else "block-%02d-output" % (index - 1)
        item = _region(name, offset, tensor_words)
        item["producer_block"] = None if index == 0 else index - 1
        tensors.append(item)
        offset += item["extent_words"]

    scratch = []
    scratch_used_words = 10 * 512
    for core_id in range(core_count):
        item = _region("core-%d-scratch" % core_id, offset,
                       scratch_used_words)
        item["core_id"] = core_id
        scratch.append(item)
        offset += item["extent_words"]

    params_words = spec["blocks"] * spec["stride_words"]
    jobs = []
    for block_index in range(spec["blocks"]):
        jobs.append({
            "block_index": block_index,
            "param_base_words": block_index * spec["stride_words"],
            "src_words": tensors[block_index]["offset_words"],
            "dst_words": tensors[block_index + 1]["offset_words"],
        })
    return {
        "frame_id": str(frame_id),
        "profile": int(profile),
        "core_count": core_count,
        "block_count": spec["blocks"],
        "width": spec["width"],
        "tensor_words": tensor_words,
        "params_words": params_words,
        "params_bytes": params_words * WORD_BYTES,
        "memory_words": offset,
        "memory_bytes": offset * WORD_BYTES,
        "memory_object": "%s:profile%d:memory" % (frame_id, int(profile)),
        "parameter_object": "profile%d:readonly-params" % int(profile),
        "tensor_regions": tensors,
        "scratch_regions": scratch,
        "jobs": jobs,
        "lifetime_rule": (
            "block output regions are never recycled within the frame; "
            "each core owns one private scratch region while active"
        ),
    }


def stripe_descriptor(plan, block_index, core_id, start_row, row_count):
    block_index = int(block_index)
    core_id = int(core_id)
    if block_index < 0 or block_index >= plan["block_count"]:
        raise ValueError("block_index is outside the profile chain")
    if core_id < 0 or core_id >= plan["core_count"]:
        raise ValueError("core_id is outside the routed core count")
    job = plan["jobs"][block_index]
    scratch = plan["scratch_regions"][core_id]
    return {
        "profile": plan["profile"],
        "param_base_words": job["param_base_words"],
        "params_words": plan["params_words"],
        "memory_words": plan["memory_words"],
        "src_words": job["src_words"],
        "dst_words": job["dst_words"],
        "scratch_words": scratch["offset_words"],
        "start_row": int(start_row),
        "row_count": int(row_count),
    }


def scheduler_job(plan, block_index, core_id, start_row, row_count):
    descriptor = stripe_descriptor(plan, block_index, core_id,
                                   start_row, row_count)
    return scheduler.StripeJob(
        plan["frame_id"], int(block_index), plan["profile"],
        int(start_row), int(row_count), int(core_id),
        "%s:core%d" % (plan["memory_object"], int(core_id)),
        plan["memory_object"], descriptor["src_words"],
        descriptor["dst_words"])


def build_release_model(core_count):
    profiles = [build_plan(profile, core_count,
                           frame_id="profile%d-frame" % profile)
                for profile in (0, 1, 2)]
    return {
        "schema": "cnn-shared-v7-multicore-memory-plan-v1",
        "core_count": int(core_count),
        "profiles": profiles,
        "normal_blocks": sum(item["block_count"] for item in profiles),
        "tensor_regions": sum(len(item["tensor_regions"])
                              for item in profiles),
        "scratch_regions": sum(len(item["scratch_regions"])
                               for item in profiles),
        "params_bytes": sum(item["params_bytes"] for item in profiles),
        "memory_bytes": sum(item["memory_bytes"] for item in profiles),
        "total_bytes": sum(item["params_bytes"] + item["memory_bytes"]
                           for item in profiles),
        "driver_requirements": {
            "one_global_arena_allocator": True,
            "readonly_parameter_reference_counting": True,
            "memory_span_read_write_leases": True,
            "per_core_job_lock": True,
            "global_lock_held_while_waiting_for_core": False,
            "runtime_core_count_from_release_identity": True,
            "single_core_driver_is_not_multicore_eligible": True,
        },
    }


def build_capacity_models():
    return {
        "schema": "cnn-shared-v7-multicore-capacity-models-v1",
        "release_core_count": None,
        "release_gate": (
            "bind core_count only after routed resource and address reports "
            "identify every physical core and guard aperture"
        ),
        "models": [build_release_model(count)
                   for count in range(1, MAX_PLANNED_CORES + 1)],
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    output = Path(args.output)
    if output.exists():
        raise FileExistsError("refusing to overwrite %s" % output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(build_capacity_models(), indent=2,
                                 sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
