"""Build the frozen v7 single-core offline resource/DDR accounting report."""

from __future__ import print_function

import argparse
import hashlib
import json
from pathlib import Path

import cnn_shared_v7_contract as contract


def _sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def build_report(root, cache_budget_path, gelu_analysis_path):
    cache = json.loads(cache_budget_path.read_text(encoding="utf-8-sig"))
    gelu = json.loads(gelu_analysis_path.read_text(encoding="utf-8-sig"))
    profiles = {}
    aggregate = {
        "normal_blocks": 0,
        "pw_weight_read_bytes": 0,
        "gelu_table_load_128b_beats": 0,
        "gelu_table_load_bytes": 0,
        "modeled_major_parameter_read_bytes": 0,
        "gelu_lookups": 0,
        "activation_traffic_bytes": 0,
        "sequential_full_block_activation_baseline_bytes": 0,
    }
    for profile in (2, 0, 1):
        model = contract.resource_model(profile)
        blocks = contract.profile_spec(profile)["blocks"]
        model["blocks_per_frame"] = blocks
        profiles[str(profile)] = model
        aggregate["normal_blocks"] += blocks
        aggregate["pw_weight_read_bytes"] += \
            blocks * model["pw_weight_read_bytes_per_block"]
        aggregate["gelu_table_load_128b_beats"] += \
            blocks * model["gelu_table_load_128b_beats_per_block"]
        aggregate["gelu_table_load_bytes"] += \
            blocks * model["gelu_table_load_bytes_per_block"]
        aggregate["modeled_major_parameter_read_bytes"] += \
            blocks * model["modeled_major_parameter_read_bytes_per_block"]
        aggregate["gelu_lookups"] += blocks * model["gelu_lookups_per_block"]
        aggregate["activation_traffic_bytes"] += \
            blocks * model["activation_traffic_bytes"]
        aggregate["sequential_full_block_activation_baseline_bytes"] += \
            blocks * model["full_frame_activation_traffic_row_equivalents"] * \
            model["channels"] * model["width"] * 2
    aggregate["pw_weight_read_mib"] = \
        float(aggregate["pw_weight_read_bytes"]) / float(1 << 20)
    aggregate["gelu_table_load_mib"] = \
        float(aggregate["gelu_table_load_bytes"]) / float(1 << 20)
    aggregate["modeled_major_parameter_read_mib"] = \
        float(aggregate["modeled_major_parameter_read_bytes"]) / float(1 << 20)
    aggregate["activation_traffic_increase_bytes"] = \
        (aggregate["activation_traffic_bytes"] -
         aggregate["sequential_full_block_activation_baseline_bytes"])
    hit_rates = [float(item["hit_rate"]) for item in cache["cases"]]
    return {
        "status": "CNN_SHARED_V7_OFFLINE_RESOURCE_MODEL",
        "scope": [
            "resource-balanced T16 stripe4 single-core static accounting",
            "actual C++ valid-channel PW request count",
            "fixed exact 8192x128-bit sequential GELU preload for every job",
        ],
        "pl_execution": False,
        "profiles": profiles,
        "aggregate_36_normal_blocks": aggregate,
        "superseded_selected_gelu_cache_replay": {
            "path": cache_budget_path.relative_to(root).as_posix(),
            "sha256": _sha256_file(cache_budget_path),
            "case_count": len(cache["cases"]),
            "hit_rate_min": min(hit_rates),
            "hit_rate_max": max(hit_rates),
            "scope": cache["scope"],
            "not_full_pipeline_statistic": True,
            "not_used_by_current_kernel": True,
            "replacement": "exact full-table sequential preload of 8192 128-bit words per job",
        },
        "gelu_table_structure": {
            "path": gelu_analysis_path.relative_to(root).as_posix(),
            "sha256": _sha256_file(gelu_analysis_path),
            "block_count": gelu["block_count"],
            "unique_table_count": gelu["unique_table_count"],
            "exact_table_dedup_saved_bytes":
                gelu["storage"]["exact_table_dedup_saved_bytes"],
        },
        "required_board_metrics": {
            "params_ar_beats": "per job and trace phase when hardware exposes it",
            "gelu_table_preload": "expect 8192 128-bit beats per successful job before DW/PW traffic; verify from RTL/ILA or phase counter",
            "memory_axi": "read/write beats and stall/cycle counters",
            "qualification": "measured counters must remain separate from this static model",
        },
        "limitations": [
            "no AXI arbitration, burst overhead, stalls, or multi-core contention modeled",
            "historical small-cache replay is retained only as superseded provenance",
            "packed PW padding is present in params but is skipped by current C++ channel loops",
            "modeled major parameter traffic excludes smaller metadata, DW weights, coefficients, and AXI overhead",
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--cache-budget", type=Path, required=True)
    parser.add_argument("--gelu-analysis", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    cache = (root / args.cache_budget).resolve()
    gelu = (root / args.gelu_analysis).resolve()
    result = build_report(root, cache, gelu)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print(json.dumps({
        "output": str(args.output),
        "pw_weight_read_bytes":
            result["aggregate_36_normal_blocks"]["pw_weight_read_bytes"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
