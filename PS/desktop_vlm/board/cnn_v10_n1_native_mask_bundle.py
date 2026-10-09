"""Build host-prepared PS native mask16/mask32 W8A16 fallback bundles.

The packed data keeps the frozen native C ABI. Target proof artifacts are
explicitly pending; this script does not manufacture a target PASS receipt.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
BOARD = ROOT / "desktop_vlm" / "board"
ACCEL = ROOT / "desktop_vlm" / "scripts" / "acceleration"
sys.path.insert(0, str(BOARD))
sys.path.insert(0, str(ACCEL))

from cnn_v10_mixed_int import error_metrics, load_n1_contract, run_n1_w8a16, sha256_file
from cnn_v10_n1_native_pack import pack as pack_native

DEFAULT_MODEL = Path("artifacts/board-debug-20261006/acceleration/host/network10-v10.1-release-bundle-003/models/network1-bridge.onnx")
DEFAULT_FIXTURE = Path("artifacts/board-debug-20261005/acceleration/host/network-w16-same-board-golden-001")
DEFAULT_FALLBACK = Path("artifacts/board-debug-20261007/acceleration/host/cnn-v10-mixed-n1-native-fallback-002")
DEFAULT_MASKS = Path("artifacts/board-debug-20261007/acceleration/host/cnn-v10-mixed-n1-masksearch-001/manifest.json")
DEFAULT_LIBRARY = Path("artifacts/board-debug-20261007/acceleration/host/cnn-v10-n1-native-bundle-005/libcnn_v10_n1_native.so")
DEFAULT_SOURCE = Path("artifacts/board-debug-20261007/acceleration/host/cnn-v10-n1-native-bundle-005/cnn_v10_n1_native.c")


def _read_f32(path: Path, shape):
    raw = path.read_bytes()
    if len(raw) != int(np.prod(shape)) * 4:
        raise ValueError(f"fixture size mismatch: {path}")
    return np.frombuffer(raw, dtype="<f4").reshape(shape).copy()


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _selection_descriptor(mask_dir: Path, manifest: dict, params_sha: str,
                          library_sha: str, model_sha: str) -> dict:
    return {
        "schema": "cnn-v10.1-n1-w8a16-selection-v1",
        "status": "HOST_PREPARED_TARGET_GATE_PENDING",
        "source_model_sha256": model_sha,
        "precision": {"backend": "existing PS native W8A16Acc32 C ABI",
                      "pw_fp32_channels": manifest["pw_fp32_channels"],
                      "sensitive_channel_count": len(manifest["pw_fp32_channels"]),
                      "mask_identity": "PS FP32 weight fallback channels; no W16 claim"},
        "logical_boundary_contract": {"input_profile": 2,
            "input_scale": manifest["input"]["logical_pl_scale_value_f64"],
            "output_profile": 0, "output_scale": manifest["output"]["logical_pl_scale_value_f64"]},
        "native_manifest": {"path": "native-manifest.json", "bytes": (mask_dir / "native-manifest.json").stat().st_size,
                            "sha256": _digest((mask_dir / "native-manifest.json").read_bytes())},
        "native_library": {"path": "libcnn_v10_n1_native.so", "bytes": (mask_dir / "libcnn_v10_n1_native.so").stat().st_size,
                           "sha256": library_sha},
        "packed_parameters": {"path": "n1-params.bin", "bytes": (mask_dir / "n1-params.bin").stat().st_size,
                              "sha256": params_sha},
        "target_receipt": {"path": "target-receipt.json", "bytes": (mask_dir / "target-receipt.json").stat().st_size,
                           "sha256": sha256_file(mask_dir / "target-receipt.json")},
        "target_result": {"path": "target-result.json", "bytes": (mask_dir / "target-result.json").stat().st_size,
                          "sha256": sha256_file(mask_dir / "target-result.json")},
        "runtime_eligibility": "NOT_ELIGIBLE_UNTIL_REAL_TARGET_RECEIPT_AND_RESULT_ARE_ATTACHED",
    }


def build_candidate(model_path: Path, fixture_root: Path, fallback_root: Path,
                    mask_record: dict, output_dir: Path, library_path: Path,
                    source_path: Path) -> dict:
    if output_dir.exists():
        raise FileExistsError(output_dir)
    channels = list(mask_record["sensitive_channels"])
    count = int(mask_record["sensitive_count"])
    if len(channels) != count or len(set(channels)) != count or any(c < 0 or c >= 128 for c in channels):
        raise ValueError("invalid mask candidate channels")
    convs = load_n1_contract(model_path)[:2]
    calibration_path = DEFAULT_FALLBACK / "n1-w8a16-oracle.json"
    cal_report = json.loads(calibration_path.read_text(encoding="utf-8"))
    scales = cal_report["calibration"]
    case_rows, outputs, refs, proofs = [], [], [], []
    for i in range(3):
        board = fixture_root / f"image-{i:02d}" / "board"
        input_path = board / "network1-bridge-input.f32"
        ref_path = board / "network1-bridge-output.f32"
        fallback_path = fallback_root / f"image-{i:02d}-mixed-fp32-fallback.f32"
        x = _read_f32(input_path, (1, 64, 64, 64))
        ref = _read_f32(ref_path, (1, 128, 32, 32))
        fallback = _read_f32(fallback_path, (1, 128, 32, 32))
        out, proof, _ = run_n1_w8a16(convs, x, scales, pw_fp32_channels=channels)
        metrics = error_metrics(ref, out)
        gate = metrics["cosine"] >= 0.999 and metrics["relative_l2"] <= 0.05
        outputs.append(out); refs.append(ref); proofs.append(proof)
        case_rows.append({"case_index": i, "input_sha256": sha256_file(input_path),
            "full_fp32_output_sha256": sha256_file(ref_path),
            "prior_mixed_fallback_sha256": sha256_file(fallback_path),
            "metrics": metrics, "vs_prior_mask7_fallback": error_metrics(fallback, out), "pass": gate})
    aggregate = error_metrics(np.concatenate([v.ravel() for v in refs]),
                              np.concatenate([v.ravel() for v in outputs]))
    if not all(r["pass"] for r in case_rows) or aggregate["cosine"] < 0.999 or aggregate["relative_l2"] > 0.05:
        raise ValueError(f"PS mask{count} fails required full-FP32 gate")
    proof_rows = []
    for row in proofs[0]:
        proof_rows.append({"bound": row["bound"],
            "observed_accumulator_min": row["observed_accumulator_min"],
            "observed_accumulator_max": row["observed_accumulator_max"]})
    report = {"schema_version": 2,
        "contract": {"model_sha256": sha256_file(model_path)},
        "calibration": scales,
        "layer_error_attribution": {"mixed_candidate_search": {
            "status": "PASS", "dw_fp32_channels": [], "pw_fp32_channels": channels,
            "metrics": aggregate,
            "per_case_gate": [{"case_index": r["case_index"], "metrics": r["metrics"], "pass": r["pass"]} for r in case_rows]}},
        "mixed_execution_contract": {"status": "PASS",
            "fallback_semantics": "native_a16_dequant_input_fp32_weights_accum",
            "pw1": {"fallback_channels": channels},
            "backend": "PS native W8A16Acc32 with selected PW FP32 output channels"},
        "overflow_proofs": proof_rows}
    output_dir.mkdir(parents=True)
    oracle_path = output_dir / "host-oracle.json"
    oracle_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    pack_dir = output_dir / "packed"
    manifest = pack_native(model_path, oracle_path, pack_dir, 9.687628574169352e-05)
    shutil.copyfile(library_path, pack_dir / "libcnn_v10_n1_native.so")
    shutil.copyfile(source_path, pack_dir / "cnn_v10_n1_native.c")
    manifest["native_abi"].update({"library_path": "libcnn_v10_n1_native.so",
        "library_sha256": sha256_file(pack_dir / "libcnn_v10_n1_native.so"),
        "source_path": "cnn_v10_n1_native.c", "source_sha256": sha256_file(pack_dir / "cnn_v10_n1_native.c")})
    manifest["candidate_selection"] = {"identity": f"ps-native-mask{count}",
        "pw_fp32_channels": channels, "precision": "W8A16Acc32 plus selected PW FP32 fallback",
        "target_validation": "PENDING; host package only, not target-proven"}
    native_manifest_path = pack_dir / "native-manifest.json"
    native_manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    # Keep the current loader's selection keys but make the pending state
    # fail closed. These placeholders are never represented as target proof.
    for name, content in (("target-receipt.json", {"status": "NOT_RUN_HOST_ONLY"}),
                          ("target-result.json", {"status": "NOT_RUN_HOST_ONLY"})):
        (pack_dir / name).write_text(json.dumps(content, indent=2) + "\n", encoding="utf-8")
    params_sha = sha256_file(pack_dir / "n1-params.bin")
    library_sha = sha256_file(pack_dir / "libcnn_v10_n1_native.so")
    selection = _selection_descriptor(pack_dir, manifest, params_sha, library_sha,
                                      sha256_file(model_path))
    selection_path = pack_dir / "selection.json"
    selection_path.write_text(json.dumps(selection, indent=2) + "\n", encoding="utf-8")
    out_rows = []
    for i, output in enumerate(outputs):
        path = output_dir / f"image-{i:02d}-ps-mask{count}-output.f32"
        output.astype("<f4").tofile(path)
        out_rows.append({"path": path.name, "sha256": sha256_file(path), "bytes": path.stat().st_size,
                         "vs_full_fp32": case_rows[i]["metrics"], "pass": case_rows[i]["pass"]})
    result = {"schema_version": 1, "status": "HOST_PASS_TARGET_PENDING",
        "mask_count": count, "pw_fp32_channels": channels,
        "model_sha256": sha256_file(model_path), "aggregate_metrics": aggregate,
        "cases": out_rows, "packed_parameter_sha256": params_sha,
        "native_library_sha256": library_sha,
        "selection_status": selection["status"], "runtime_loadable_after_target_receipt": True}
    (output_dir / "host-result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    p.add_argument("--fixture-root", type=Path, default=DEFAULT_FIXTURE)
    p.add_argument("--fallback-root", type=Path, default=DEFAULT_FALLBACK)
    p.add_argument("--mask-manifest", type=Path, default=DEFAULT_MASKS)
    p.add_argument("--library", type=Path, default=DEFAULT_LIBRARY)
    p.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    args.output.mkdir(parents=True)
    masks = json.loads(args.mask_manifest.read_text(encoding="utf-8"))
    candidates = {int(x["sensitive_count"]): x for x in masks["mask_search"]}
    results = []
    for count in (16, 32):
        target = args.output / f"mask{count:02d}"
        results.append(build_candidate(args.model, args.fixture_root, args.fallback_root,
            candidates[count], target, args.library, args.source))
    receipt = {"schema_version": 1, "status": "HOST_PASS_TARGET_PENDING",
        "mask_manifest_sha256": sha256_file(args.mask_manifest),
        "model_sha256": sha256_file(args.model),
        "candidates": results,
        "files": {str(f.relative_to(args.output)).replace("\\", "/"):
            {"bytes": f.stat().st_size, "sha256": sha256_file(f)}
            for f in sorted(args.output.rglob("*")) if f.is_file()}}
    (args.output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": receipt["status"],
        "mask16_params_sha256": results[0]["packed_parameter_sha256"],
        "mask32_params_sha256": results[1]["packed_parameter_sha256"],
        "mask16_metrics": results[0]["aggregate_metrics"],
        "mask32_metrics": results[1]["aggregate_metrics"]}, indent=2))


if __name__ == "__main__":
    main()
