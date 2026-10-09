"""Independently compare retained v5 features with same-board integer goldens.

Without --report this audits reference quality only, never claims PL execution.
"""
import argparse
import json
from pathlib import Path

import numpy as np

from audit_network2_features import digest, load_oracle, metrics, rank, read_array, require


def extended_metrics(actual, reference):
    result = metrics(actual, reference)
    result["relative_l2"] = float(np.linalg.norm(actual - reference) / np.linalg.norm(reference))
    return result


def run(golden_path, expected_sha, oracle_root, baseline_path, report_path=None,
        thread_path=None, expected_thread_sha=None):
    golden_blob = golden_path.read_bytes()
    require(digest(golden_blob) == expected_sha, "golden manifest identity")
    golden = json.loads(golden_blob)
    require(golden["execution"]["pl_execution"] is False and
            golden["execution"]["board_capture"] is True and
            golden["execution"]["board_ps_ort_version"] == "1.16.3", "golden provenance")
    references, text = load_oracle(oracle_root)
    baseline_blob = baseline_path.read_bytes()
    baseline = json.loads(baseline_blob)
    require(baseline["execution"] == "board" and baseline["pl_execution"] is False,
            "baseline must be actual pure PS")
    baseline_inputs = {}
    for row in baseline["records"]:
        sample = row["sample_id"]
        if type(sample) is int and 0 <= sample <= 2:
            sample = "image-%02d" % sample
        require(sample in references, "unknown baseline sample")
        require(row["correct"] is True, "baseline validation failed")
        raw = references[sample]["pure_ps"].astype("<f4").tobytes()
        require(digest(raw) == row["feature_sha256"], "pure PS reference differs from baseline output")
        require(row["input_sha256"] not in baseline_inputs or
                baseline_inputs[row["input_sha256"]] == sample, "ambiguous baseline input")
        baseline_inputs[row["input_sha256"]] = sample
    by_input = {}
    golden_quality = []
    for row in golden["results"]:
        sample = row["sample_id"]
        require(baseline_inputs.get(row["input_sha256"]) == sample, "golden/baseline input identity")
        feature = read_array(golden_path.parent, row["feature"], (512,))
        actual_rank = rank(feature, text)
        pure_rank = rank(references[sample]["pure_ps"], text)
        require(actual_rank == pure_rank, "golden changes full pure PS ranking")
        require(row["input_sha256"] not in by_input, "duplicate golden input")
        by_input[row["input_sha256"]] = (sample, feature, actual_rank)
        golden_quality.append({"sample_id": sample, "vs_pure_ps": extended_metrics(feature, references[sample]["pure_ps"]),
                               "rank_indices": actual_rank, "pure_ps_rank_matches": True})
    require(len(by_input) == 3, "three engineering reference images required")
    result = {"status": "SAME_BOARD_PS_WIDE_INTEGER_GOLDEN_QUALITY_PASS", "pl_execution_audited": False,
              "golden_manifest_sha256": expected_sha, "baseline_sha256": digest(baseline_blob),
              "golden_quality": golden_quality,
              "scope": "Three historical engineering regressions, not independent real-object accuracy.",
              "reference_thread_scope": "PS thread equivalence must be bound by the deployment evidence."}
    if report_path is None:
        return result
    require(thread_path is not None and expected_thread_sha is not None,
            "board feature audit requires pinned PS thread consistency evidence")
    thread_blob = thread_path.read_bytes()
    require(digest(thread_blob) == expected_thread_sha, "thread consistency manifest identity")
    thread_check = json.loads(thread_blob)
    require(thread_check["source_golden_manifest_sha256"] == expected_sha and
            thread_check["status"] == "BOARD_C_ORT_PLANNED_THREAD_BUDGETS_BYTE_EXACT_TO_THREAD2_GOLDEN",
            "thread evidence does not bind this golden")
    require(len(thread_check["cases"]) == 24 and all(c["byte_exact"] is True for c in thread_check["cases"]),
            "incomplete thread consistency coverage")
    report_blob = report_path.read_bytes()
    report = json.loads(report_blob)
    require(report["status"] == "BOARD_V5_BENCHMARK_COMPLETED" and report["pl_execution"] is True,
            "not an actual completed v5 board benchmark")
    require(report["kernel_boot_id"] == golden["execution"]["boot_id"], "golden/benchmark boot changed")
    require(report["parameter_binding"]["parameter_bundle_manifest_sha256"] ==
            golden["source_hashes"]["canonical_bundle_manifest"], "parameter binding differs")
    require(report["split_manifest_sha256"] == golden["source_hashes"]["runtime_split_manifest"],
            "PS split identity differs")
    budget = {k.replace("_", "-"): v for k, v in report["ort_thread_budget"].items()}
    require(budget in thread_check["plans"].values(), "unverified PS thread allocation")
    files = {row["frame_id"]: row for row in report["feature_outputs"]}
    frames = report["measurement"]["frames"]
    require(len(files) == len(report["feature_outputs"]) == len(frames) == 30, "30 unique feature outputs required")
    checked, seen = [], set()
    for row in frames:
        fid = row["frame_id"]
        require(fid not in seen, "duplicate measured frame")
        seen.add(fid)
        sample, reference, reference_rank = by_input[row["input_sha256"]]
        rec = files[fid]
        actual = read_array(report_path.parent,
                            dict(path=rec["relative_path"], dtype="<f4", shape=[512],
                                 bytes=rec["bytes"], sha256=rec["sha256"]), (512,))
        quantized = extended_metrics(actual, reference)
        require(quantized["max_abs"] <= 1e-6 and quantized["cosine"] >= .99999,
                "PL feature differs from same-board wide integer reference")
        actual_rank = rank(actual, text)
        require(actual_rank == reference_rank == rank(references[sample]["pure_ps"], text),
                "PL feature full ranking differs")
        checked.append({"frame_id": fid, "sample_id": sample, "vs_quantized_reference": quantized,
                        "vs_pure_ps": extended_metrics(actual, references[sample]["pure_ps"]),
                        "rank_indices": actual_rank, "pure_ps_rank_matches": True})
    result.update(status="V5_BOARD_FEATURES_AND_ENGINEERING_RANKING_PASS", pl_execution_audited=True,
                  report_sha256=digest(report_blob), checked_frames=checked,
                  thread_consistency_sha256=expected_thread_sha,
                  reference_thread_scope="Byte-exact consistency verified for this PS thread allocation.",
                  timing_audit="Required separately; this tool does not accept performance timing.")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--golden", required=True, type=Path)
    parser.add_argument("--expected-golden-sha256", required=True)
    parser.add_argument("--ps-oracle", required=True, type=Path)
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--thread-consistency", type=Path)
    parser.add_argument("--expected-thread-consistency-sha256")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = run(args.golden, args.expected_golden_sha256, args.ps_oracle, args.baseline, args.report,
                 args.thread_consistency, args.expected_thread_consistency_sha256)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
