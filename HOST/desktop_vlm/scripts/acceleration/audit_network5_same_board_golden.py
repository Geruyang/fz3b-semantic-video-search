"""Audit the frozen same-board ORT 1.16.3 plus HOST-wide W16 golden artifact."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[3]
GOLDEN = ROOT / "artifacts/board-debug-20261005/acceleration/host/network-w16-same-board-golden-001"
HOST_ONLY = ROOT / "artifacts/board-debug-20261005/acceleration/host/network-w16-full-chain-preflight-001"
OUT = ROOT / "artifacts/board-debug-20261005/acceleration/host/network-w16-same-board-golden-audit-002.json"


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    if OUT.exists():
        raise FileExistsError(str(OUT))
    manifest_path = GOLDEN / "manifest.json"
    receipt_path = GOLDEN / "run-receipt.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    failures = []
    verified_bytes = 0
    for relative, record in manifest["files"].items():
        path = GOLDEN / relative
        if not path.is_file() or path.stat().st_size != record["bytes"] or sha(path) != record["sha256"]:
            failures.append("file:" + relative)
        else:
            verified_bytes += path.stat().st_size
    if receipt.get("result") != "SAME_BOARD_C_ORT_HOST_W16_THREE_IMAGE_GOLDEN_COMPLETE_LOCK_RELEASED":
        failures.append("run-receipt-result")
    if receipt.get("manifest", {}).get("sha256") != sha(manifest_path):
        failures.append("run-receipt-manifest-sha")
    if any(command.get("exit_code") != 0 for command in receipt.get("commands", [])):
        failures.append("command-exit-code")
    checks = manifest.get("checks", {})
    if (checks.get("pl_execution") is not False or
            not all(value is True for key, value in checks.items() if key != "pl_execution")):
        failures.append("manifest-checks")
    expected_stages = ["stem-prefix", "network1-bridge", "network3-bridge", "suffix"]
    comparisons = []
    for result in manifest["results"]:
        sample_id = result["sample_id"]
        actual_stages = [stage["stage"] for stage in result["board_ps_stages"]]
        if actual_stages != expected_stages:
            failures.append(sample_id + ":stage-order")
        if any(stage.get("pl_execution") is not False or stage.get("boot_id") != manifest["execution"]["boot_id"]
               or stage.get("ort_ready_header", {}).get("ort_version") != "1.16.3"
               for stage in result["board_ps_stages"]):
            failures.append(sample_id + ":stage-provenance")
        profile_diffs = {}
        for profile in (2, 0, 1):
            same_path = GOLDEN / result["profile%d_input_i16_hcw" % profile]["path"]
            host_path = HOST_ONLY / sample_id / ("profile%d" % profile) / "input-hcw.i16le"
            same = np.fromfile(same_path, dtype="<i2")
            host = np.fromfile(host_path, dtype="<i2")
            if same.shape != host.shape:
                failures.append(sample_id + ":profile%d-shape" % profile)
                continue
            delta = same.astype(np.int32) - host.astype(np.int32)
            profile_diffs[str(profile)] = {
                "elements": int(same.size),
                "different_elements": int(np.count_nonzero(delta)),
                "max_abs_code_difference": int(np.max(np.abs(delta))),
                "same_board_sha256": sha(same_path),
                "host_only_sha256": sha(host_path),
                "exact": bool(np.array_equal(same, host)),
            }
        same_feature = np.fromfile(GOLDEN / result["feature"]["path"], dtype="<f4").astype(np.float64)
        host_feature_path = HOST_ONLY / sample_id / "w16-full-chain-feature.f32"
        host_feature = np.fromfile(host_feature_path, dtype="<f4").astype(np.float64)
        delta = same_feature - host_feature
        feature_comparison = {
            "cosine": float(np.dot(same_feature, host_feature) /
                            max(float(np.linalg.norm(same_feature) * np.linalg.norm(host_feature)), 1e-300)),
            "max_abs": float(np.max(np.abs(delta))),
            "relative_l2": float(np.linalg.norm(delta) / max(float(np.linalg.norm(host_feature)), 1e-300)),
            "same_board_sha256": sha(GOLDEN / result["feature"]["path"]),
            "host_only_sha256": sha(host_feature_path),
            "exact": bool(np.array_equal(same_feature, host_feature)),
        }
        comparisons.append({"sample_id": sample_id, "profile_input_code_differences_vs_host_only": profile_diffs,
                            "feature_vs_host_only_full_chain": feature_comparison,
                            "ranking_matches_frozen_host_pure_ps": result["ranking_matches_frozen_host_pure_ps"]})
    audit = {
        "schema_version": 1,
        "status": "PASS" if not failures else "FAIL",
        "source": {"manifest": str(manifest_path.relative_to(ROOT)).replace("\\", "/"),
                   "manifest_sha256": sha(manifest_path), "run_receipt_sha256": sha(receipt_path)},
        "execution_provenance": manifest["execution"],
        "files_verified": len(manifest["files"]),
        "bytes_verified": verified_bytes,
        "comparisons": comparisons,
        "failures": failures,
    }
    OUT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": audit["status"], "audit": str(OUT), "audit_sha256": sha(OUT),
                      "files_verified": audit["files_verified"], "comparisons": comparisons}, indent=2))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
