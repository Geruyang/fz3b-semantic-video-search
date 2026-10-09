"""Independent v6 DAG timing and globally interleaved PL-counter audit.

Reads retained evidence only. Does not contact the board. Numerical equivalence,
quantization quality and PL inter-block overlap require their separate evidence.
"""
import argparse
import hashlib
import json
import math
import struct
import uuid
from pathlib import Path

from audit_cnn_ddr_v5_benchmark import (
    COUNTERS, STATUS_FIELDS, near, number, require, sha, stats, status_check, uint,
)


ORDERS = ((2, 0, 1), (2, 3, 4, 0, 1), (2, 0, 5, 6, 1), (2, 3, 4, 0, 5, 6, 1))
BOUNDARIES = (
    "admission_wait_ms", "admitted_to_ready_ms", "ready_to_emit_wait_ms",
    "admitted_to_complete_ms", "arrival_to_complete_ms",
)


def union_ms(intervals):
    if not intervals:
        return 0.0
    ordered = sorted(intervals)
    left, right = ordered[0]
    total = 0.0
    for start, end in ordered[1:]:
        if start > right:
            total += right - left
            left, right = start, end
        else:
            right = max(right, end)
    return total + right - left


def peak_active(intervals):
    changes = []
    for start, end in intervals:
        if end > start:
            changes.extend(((start, 1), (end, -1)))
    active = peak = 0
    for unused_time, delta in sorted(changes):
        active += delta
        peak = max(active, peak)
    return peak


def checked_status(value, generation, complete=False, profile_switch_reset=False):
    hardware_generation = (uint(value["reset_generation"], "hardware reset generation")
                           if profile_switch_reset else generation)
    status_check(value, hardware_generation, complete=complete)


def check_completion(completion, after, generation, profile_switch_reset=False):
    for key in STATUS_FIELDS:
        if profile_switch_reset and key == "reset_generation":
            require(completion["hardware_reset_generation"] == after[key],
                    "raw hardware generation differs from completion status")
            require(completion[key] == completion["generation_token"] == generation,
                    "logical frame generation changed")
        else:
            require(completion[key] == after[key], "flattened completion differs")


def audit_job_order(jobs, before_batch, final, generation, hz, profile_switch_reset=False):
    """Counters, not result/frame order, define the actual global job sequence."""
    previous = before_batch
    hardware = {}
    ordered = sorted(jobs, key=lambda row: row[0])
    for expected, (distance, before, after, fid) in enumerate(ordered, 1):
        checked_status(before, generation, profile_switch_reset=profile_switch_reset)
        checked_status(after, generation, complete=True, profile_switch_reset=profile_switch_reset)
        if profile_switch_reset:
            require(before["reset_generation"] == previous["reset_generation"] and
                    before["profile"] == previous["profile"], "inter-job reset/profile discontinuity")
            increment = int(before["profile"] != after["profile"])
            require(after["reset_generation"] == (before["reset_generation"] + increment) & 0xffffffff,
                    "profile switch did not produce exactly one guarded core reset")
        require(distance == expected, "missing/duplicate/intervening job in actual hardware order")
        require(distance == (after["completed_frames"] - before_batch["completed_frames"]) & 0xffffffff,
                "job distance is not bound to counter")
        require(all(before[key] == previous[key] for key in COUNTERS), "global counter discontinuity")
        require((after["completed_frames"] - before["completed_frames"]) & 0xffffffff == 1, "job did not advance once")
        for key in COUNTERS[1:]:
            require((after[key] - before[key]) & 0xffffffff > 0, "AXI counter did not advance")
        previous = after
        hardware.setdefault(str(after["profile"]), []).append(after["job_cycles"] * 1000 / hz)
    require(all(final[key] == previous[key] for key in STATUS_FIELDS), "last actual job/status mismatch")
    return hardware


def audit(report, root, profile_switch_reset=False):
    require(report["status"] == "BOARD_V6_BENCHMARK_COMPLETED" and
            report["execution"] == "board_linux_ioctl_fzv6" and report["pl_execution"] is True,
            "not a completed actual v6 board run")
    require(str(uuid.UUID(report["kernel_boot_id"])) == report["kernel_boot_id"], "boot identity")
    for key in ("runtime_config_sha256", "split_manifest_sha256"):
        sha(report[key])
    clock = report["pl_clock"]
    sha(clock["design_sha256"])
    sha(clock["deployment_receipt_sha256"])
    hz = uint(clock["hz"], "PL clock", 64)
    require(hz > 0, "zero clock")
    warm = report["warmup_policy"]
    require(warm["frames"] == 3 and warm["completed"] is True and
            warm["included_in_statistics"] is False, "warmup is not separate")
    require(all(report["cleanup_receipt"][key] is True for key in
                ("quiesce_confirmed", "all_handles_freed", "transport_closed")), "cleanup incomplete")
    measure = report["measurement"]
    frames = measure["frames"]
    require(len(frames) == measure["frames_completed"] == report["measurement_policy"]["frames"] == 30,
            "requires exactly 30 measured frames")
    origin = number(measure["batch_wall_start_monotonic_s"], "origin")
    end = number(measure["batch_wall_end_monotonic_s"], "end")
    wall = number(measure["batch_wall_ms"], "wall")
    require(wall > 0, "empty batch")
    near(wall, (end - origin) * 1000, "wall")
    near(measure["throughput_fps"], 30000 / wall, "FPS")
    require(measure["outer_call_wall_ms"] + 1e-6 >= wall, "wall exceeds enclosing run")
    cpu = measure["cpu_before"]
    require(cpu == measure["cpu_after"] and cpu["frequency_status"] == "measured_from_sysfs"
            and cpu["online_cpu_list"] == "0-3", "CPU environment changed/unavailable")
    frequencies = cpu["current_frequency_samples"]
    require([row["cpu"] for row in frequencies] == [0, 1, 2, 3], "missing CPU frequency samples")
    require(all(uint(row["scaling_cur_freq_khz"], "CPU frequency") > 0 for row in frequencies), "zero CPU clock")
    generation = uint(report["driver_generation"], "generation")
    before_batch = report["driver_status_before_measurement"]
    checked_status(before_batch, generation, complete=True, profile_switch_reset=profile_switch_reset)
    feature_records = {row["frame_id"]: row for row in report["feature_outputs"]}
    require(len(feature_records) == len(report["feature_outputs"]) == 30, "feature coverage")
    jobs, pl_events, ps_events, frame_intervals = [], [], [], []
    boundaries = {key: [] for key in BOUNDARIES}
    busy, wait = {}, {}
    seen = set()
    expected_order = None
    last_emit = 0.0
    input_sequence = hashlib.sha256()
    for index, frame in enumerate(frames):
        fid = uint(frame["frame_id"], "frame id")
        require(fid not in seen and fid in feature_records, "duplicate/unretained feature")
        seen.add(fid)
        require(frame["sequence_index"] == index and frame["generation"] == generation, "stale/reordered frame")
        input_sequence.update((sha(frame["input_sha256"]) + "\n").encode("ascii"))
        arrival, admitted, ready, output_start, output_done = [number(frame[key], key) for key in
            ("arrival_ms", "admitted_ms", "compute_ready_ms", "output_start_ms", "output_done_ms")]
        require(0 <= arrival <= admitted <= ready <= output_start <= output_done <= wall + 1e-6,
                "frame event order/outside batch")
        require(output_start >= last_emit, "actual output callback order is not serial")
        last_emit = output_done
        frame_intervals.append((admitted, output_done))
        near(frame["complete_ms"], output_done, "complete is not actual output done")
        deltas = (admitted - arrival, ready - admitted, output_start - ready,
                  output_done - admitted, output_done - arrival)
        for key, delta in zip(BOUNDARIES, deltas):
            near(frame[key], delta, key)
            boundaries[key].append(delta)
        for key, delta in (("arrival", arrival), ("admitted", admitted), ("complete", output_done)):
            near(frame["event_monotonic_s"][key], origin + delta / 1000, "absolute " + key)
        stage_intervals = []
        events = frame["stage_events_ms"]
        for required_stage in ("capture", "decode", "preprocess", "stem_prefix", "suffix", "rank", "output"):
            require(required_stage in events, "missing PS stage event " + required_stage)
        for name, event in events.items():
            queued, started, ended = [number(event[key], name + "." + key)
                                      for key in ("queued_ms", "start_ms", "end_ms")]
            require(admitted <= queued <= started <= ended <= output_done + 1e-6, "invalid stage event " + name)
            busy.setdefault(name, []).append(ended - started)
            wait.setdefault(name, []).append(started - queued)
            if name != "output":
                require(ended <= ready + 1e-6, "compute stage finishes after ready")
                stage_intervals.append((started, ended))
                target = pl_events if name.startswith(("pl_", "plchain_")) else ps_events
                target.append((started, ended, fid, name))
        stage_intervals.sort()
        require(all(a[1] <= b[0] + 1e-6 for a, b in zip(stage_intervals, stage_intervals[1:])),
                "same frame has overlapping dependent DAG stages")
        near(events["output"]["start_ms"], output_start, "output event start")
        near(events["output"]["end_ms"], output_done, "output event end")
        completions = frame["driver_completions"]
        order = tuple(completion["status_after"]["profile"] for completion in completions)
        require(order in ORDERS and (expected_order is None or order == expected_order), "profile path changed/missing job")
        expected_order = order
        require(frame["driver_completion_count"] == len(completions), "completion count")
        for completion in completions:
            before, after = completion["status_before"], completion["status_after"]
            checked_status(before, generation, profile_switch_reset=profile_switch_reset)
            checked_status(after, generation, complete=True, profile_switch_reset=profile_switch_reset)
            check_completion(completion, after, generation, profile_switch_reset)
            distance = (after["completed_frames"] - before_batch["completed_frames"]) & 0xffffffff
            jobs.append((distance, before, after, fid))
        rec = feature_records[fid]
        path = (root / rec["relative_path"]).resolve()
        require(path.is_relative_to(root.resolve()), "feature path escapes evidence root")
        raw = path.read_bytes()
        require(len(raw) == rec["bytes"] == 2048 and hashlib.sha256(raw).hexdigest() == sha(rec["sha256"]),
                "feature identity")
        require(all(math.isfinite(value) for value in struct.unpack("<512f", raw)), "nonfinite feature")
    near(last_emit, wall, "batch ends after last actual output")
    pipeline_stats = measure["pipeline_stats"]
    flight_peak = peak_active(frame_intervals)
    require(flight_peak <= uint(pipeline_stats["max_in_flight"], "max in flight"), "in-flight bound exceeded")
    ps_peak = peak_active([(row[0], row[1]) for row in ps_events])
    workers = uint(pipeline_stats["ps_workers"], "PS workers")
    require(1 <= workers <= 4 and ps_peak <= workers, "PS worker budget exceeded")
    pl_events.sort()
    require(len(pl_events) == len(jobs), "PL stage event/job coverage")
    require(all(a[1] <= b[0] + 1e-6 for a, b in zip(pl_events, pl_events[1:])), "multiple simultaneous PL owners")
    hardware = audit_job_order(jobs, before_batch, report["driver_status_after_measurement"],
                               generation, hz, profile_switch_reset=profile_switch_reset)
    for key, values in boundaries.items():
        summary = stats(values)
        near(measure[key]["median"], summary["p50"], key + " median")
        near(measure[key]["p95"], summary["p95"], key + " p95")
    intersections = []
    for ps, pe, pf, unused in pl_events:
        for ss, se, sf, unused2 in ps_events:
            if pf != sf and min(pe, se) > max(ps, ss):
                intersections.append((max(ps, ss), min(pe, se)))
    return {
        "status": "V6_TIMING_GLOBAL_COUNTERS_FEATURE_FILES_PASS",
        "execution": "offline_audit_of_board_evidence", "measured_frames": 30,
        "measured_pl_jobs": len(jobs), "profile_order_per_frame": list(expected_order),
        "hardware_reset_policy": "one_per_profile_change" if profile_switch_reset else "fixed_generation",
        "measured_profile_changes": sum(row[1]["profile"] != row[2]["profile"] for row in jobs),
        "batch_wall_ms": wall, "throughput_fps": 30000 / wall,
        "latency_boundaries": {key: stats(values) for key, values in boundaries.items()},
        "stage_active_ms": {key: stats(values) for key, values in busy.items()},
        "stage_queue_wait_ms": {key: stats(values) for key, values in wait.items()},
        "hardware_job_ms_by_profile": {key: stats(values) for key, values in hardware.items()},
        "cross_frame_ps_callback_pl_interval_union_ms": union_ms(intersections),
        "observed_frame_in_flight_peak": flight_peak, "observed_ps_callback_peak": ps_peak,
        "kernel_boot_id": report["kernel_boot_id"], "pl_clock_hz": hz,
        "input_sequence_sha256": input_sequence.hexdigest(),
        "scope": "PS callback intervals include locks/driver waits; their overlap alone does not prove DMA or PL inter-block overlap. Numerical quality requires a separate audit."
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--profile-switch-reset", action="store_true",
                        help="Require exactly one guarded core reset per profile change, none for same-profile jobs")
    args = parser.parse_args()
    raw = args.report.read_bytes()
    result = audit(json.loads(raw), args.report.parent, profile_switch_reset=args.profile_switch_reset)
    result["source"] = {"path": str(args.report.resolve()), "sha256": hashlib.sha256(raw).hexdigest()}
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
