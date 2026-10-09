"""Audit every retained v6 frame against the same-board integer reference.

The normal-fallback route preserves v5 arithmetic. Requiring byte identity
also detects stale or mis-associated buffers under the new DAG scheduler.
Timing and hardware deployment evidence are audited separately.
"""
import argparse
import hashlib
import json
from pathlib import Path

from audit_cnn_ddr_v5_features import run as audit_reference_quality
from audit_network2_features import require


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def checked_file(root, relative, expected_sha, expected_bytes):
    root = root.resolve()
    path = (root / relative).resolve()
    require(path.is_relative_to(root), "feature path escapes evidence directory")
    raw = path.read_bytes()
    require(len(raw) == expected_bytes == 2048 and sha(raw) == expected_sha,
            "feature length or SHA mismatch")
    return raw


def audit_frames(report, root, golden, golden_root):
    require(report["status"] == "BOARD_V6_BENCHMARK_COMPLETED" and
            report["pl_execution"] is True, "not a completed v6 board benchmark")
    require(report["kernel_boot_id"] == golden["execution"]["boot_id"],
            "golden and benchmark boot differ")
    binding = report["parameter_binding"]
    require(binding["production_mode"] == "normal_fallback" and
            binding["physical_profiles"] == [2, 0, 1], "unsupported arithmetic route")
    require(binding["v5_bundle_manifest_sha256"] ==
            golden["source_hashes"]["canonical_bundle_manifest"], "parameter identity differs")
    require(report["split_manifest_sha256"] ==
            golden["source_hashes"]["runtime_split_manifest"], "PS split identity differs")
    references = {}
    for record in golden["results"]:
        ref = record["feature"]
        raw = checked_file(golden_root, ref["path"], ref["sha256"], ref["bytes"])
        require(record["input_sha256"] not in references, "duplicate reference input")
        references[record["input_sha256"]] = (record["sample_id"], raw)
    require(len(references) == 3, "three reference inputs required")
    files = {r["frame_id"]: r for r in report["feature_outputs"]}
    frames = report["measurement"]["frames"]
    require(len(files) == len(report["feature_outputs"]) == len(frames) == 30,
            "30 unique retained frames required")
    checked, seen, counts = [], set(), dict.fromkeys(references, 0)
    for frame in frames:
        fid = frame["frame_id"]
        require(fid not in seen, "duplicate frame ID")
        seen.add(fid)
        source = frame["input_sha256"]
        require(source in references, "unknown frame input")
        sample, reference = references[source]
        record = files[fid]
        actual = checked_file(root, record["relative_path"], record["sha256"], record["bytes"])
        require(actual == reference, "frame %s differs from its input-bound golden" % fid)
        counts[source] += 1
        checked.append({"frame_id": fid, "sample_id": sample, "input_sha256": source,
                        "feature_sha256": sha(actual), "byte_exact": True})
    require(set(counts.values()) == {10}, "expected ten measured frames per input")
    return checked


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--golden", required=True, type=Path)
    parser.add_argument("--expected-golden-sha256", required=True)
    parser.add_argument("--ps-oracle", required=True, type=Path)
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    quality = audit_reference_quality(args.golden, args.expected_golden_sha256,
                                      args.ps_oracle, args.baseline)
    blob = args.report.read_bytes()
    checked = audit_frames(json.loads(blob), args.report.parent,
                           json.loads(args.golden.read_bytes()), args.golden.parent)
    result = {"status": "V6_ALL_MEASURED_FEATURES_BYTE_EXACT_AND_ENGINEERING_RANKING_PASS",
              "report_sha256": sha(blob), "golden_manifest_sha256": args.expected_golden_sha256,
              "baseline_sha256": quality["baseline_sha256"], "checked_frames": checked,
              "golden_quality": quality["golden_quality"],
              "scope": "30 actual retained outputs, each bound by input SHA to a same-board golden. "
                       "Byte identity preserves the independently checked full pure-PS ranking. "
                       "Three historical engineering images, not independent recognition accuracy. "
                       "Timing and deployment must pass their separate audits."}
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(json.dumps({"status": result["status"], "frames": len(checked),
                      "output_sha256": sha(args.output.read_bytes())}, indent=2))


if __name__ == "__main__":
    main()
