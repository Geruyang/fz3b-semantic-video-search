#!/usr/bin/env python3
"""Finalize the strictly non-hardware P3-domain suffix prediction evidence."""
from __future__ import print_function

import datetime
import hashlib
import json
from pathlib import Path

import numpy as np


REPO = Path(r"E:\AIProject\FPGAVibecoding")
OUT = REPO / ("artifacts/board-debug-20261007/acceleration/host/"
              "cnn-v10-p3-domain-host-prediction-001")
P3 = REPO / ("artifacts/board-debug-20261007/acceleration/host/"
             "cnn-v10-n1-p3-full-w16-002")
NORMAL = REPO / ("artifacts/board-debug-20261007/acceleration/host/"
                 "network10-v10.2-native-broker-dw7-joint-normal-001")
RELEASE = REPO / ("artifacts/board-debug-20261006/acceleration/host/"
                  "network10-v10.1-release-bundle-003")
EXPECTED_REFERENCES = (
    "4121608b7bb27060d5babe05dd6ae723d191b4405a0852d55adde876f4ef16b3",
    "7654afe2d025731f18d23268c2109aba3445b2708a8e9ef1a2e49ed84c369adb",
)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def rec(path):
    path = Path(path)
    return {"path": path.relative_to(REPO).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def compare(candidate, reference):
    actual = np.fromfile(candidate, dtype="<f4").astype(np.float64)
    wanted = np.fromfile(reference, dtype="<f4").astype(np.float64)
    if actual.shape != (512,) or wanted.shape != (512,):
        raise ValueError("feature vectors must contain exactly 512 FP32 values")
    delta = actual - wanted
    denominator = float(np.linalg.norm(wanted))
    cosine_denominator = float(np.linalg.norm(actual) * np.linalg.norm(wanted))
    return {
        "feature_sha256": sha(candidate),
        "reference_sha256": sha(reference),
        "cosine": float(np.dot(actual, wanted) / cosine_denominator),
        "relative_l2": float(np.linalg.norm(delta) / denominator),
        "max_abs": float(np.max(np.abs(delta))),
    }


def main():
    final_path = OUT / "receipt.json"
    if final_path.exists():
        raise RuntimeError("refusing to overwrite final prediction receipt")
    for index, expected in enumerate(EXPECTED_REFERENCES):
        path = OUT / "outputs" / ("image-%02d-reference-feature.f32" % index)
        if sha(path) != expected:
            raise ValueError("reference feature identity mismatch")
    variants = {}
    for label in ("suffix-fp32", "suffix11", "suffix6"):
        cases = []
        for index in range(2):
            candidate = OUT / "outputs" / ("image-%02d-%s-output.f32" % (index, label))
            reference = OUT / "outputs" / ("image-%02d-reference-feature.f32" % index)
            value = compare(candidate, reference)
            value["case_id"] = "image-%02d" % index
            cases.append(value)
        variants[label] = {
            "cases": cases,
            "min_cosine": min(case["cosine"] for case in cases),
            "max_relative_l2": max(case["relative_l2"] for case in cases),
            "engineering_gate": all(case["cosine"] >= 0.999 and
                                    case["relative_l2"] <= 0.05
                                    for case in cases),
        }
    output_files = {}
    for path in sorted((OUT / "outputs").glob("*")):
        if path.is_file():
            output_files[path.name] = rec(path)
    normal_receipt = json.loads((NORMAL / "receipt.json").read_text(encoding="utf-8"))
    receipt = {
        "schema": "cnn-v10.2-p3-domain-host-prediction-v1",
        "status": "PASS_HOST_PREDICTION_COMPLETE_REAL_P3_CAPTURE_STILL_REQUIRED",
        "generated_utc": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
        "hardware_execution": False,
        "performance_valid": False,
        "board_state": "factory PL and fpgadrv retained; target used only for ORT N3/suffix",
        "scope": ("P3 full-W16 raw oracle -> host-native ABI10.1 P0 -> target ORT1.16.3 N3 -> "
                  "host-native ABI10.1 P1 -> target ORT1.16.3 suffix FP32/11/6"),
        "limitations": [
            "This is a host prediction and cannot satisfy the real P3 capture or board quality gate.",
            "P0/P1 used the historical 50f8/388f product object already proven by the bound native receipt.",
            "No timings from this mixed host/target path are valid for FPS or hardware performance.",
        ],
        "quality_thresholds": {"min_cosine": 0.999, "max_relative_l2": 0.05,
                               "engineering_images_only": True},
        "quality": variants,
        "identities": {
            "p3_manifest": rec(P3 / "manifest.json"),
            "p3_receipt": rec(P3 / "receipt.json"),
            "p3_parameter_file": rec(P3 / "candidate-p3-full-w16-params.bin"),
            "normal_native_receipt": rec(NORMAL / "receipt.json"),
            "product_object": rec(OUT / "build" / "cnn_pipeline_v10.o"),
            "dump_executable": rec(OUT / "build" / "cnn_pipeline_v10_dump.exe"),
            "dump_testbench": rec(OUT / "source-snapshot" / "cnn_pipeline_v10_dump_tb.cpp"),
            "compile_response": rec(OUT / "build" / "compile.rsp"),
            "link_response": rec(OUT / "build" / "link.rsp"),
            "profile0_params": rec(RELEASE / "params" / "profile0.bin"),
            "profile1_params": rec(RELEASE / "params" / "profile1.bin"),
            "target_worker": rec(REPO / "desktop_vlm/board/run_cnn_v10_partition_once.py"),
            "target_wrapper": rec(REPO / "desktop_vlm/scripts/acceleration/run_cnn_v10_p3_domain_target_stage.py"),
            "target_n3_receipt": rec(OUT / "target-n3-receipt.json"),
            "target_suffix_base_receipt": rec(OUT / "target-suffix-base-receipt.json"),
            "target_suffix_receipt": rec(OUT / "target-suffix-receipt.json"),
        },
        "bound_product_sources": normal_receipt["source_sha256"],
        "transform_contract": {
            "p0_output_scale": 8.010273432023655e-06,
            "p1_input_scale": 7.726196825520674e-05,
            "p1_output_scale": 2.462270113096634e-05,
            "quantize": "FP64 divide, NumPy rint ties-even, clip signed INT16, NCHW to HCW",
            "dequantize": "INT16 HCW to NCHW, multiply by frozen FP32 scale",
        },
        "files": output_files,
        "compile_attempt1": {
            "status": "FAILED_MISSING_INCLUDE_PATH_FIXED_WITH_ABSOLUTE_FROZEN_SNAPSHOT_PATH",
            "log": rec(OUT / "build" / "compile-attempt1.log"),
        },
        "prediction_gate_pass": variants["suffix-fp32"]["engineering_gate"],
        "suffix11_prescreen_pass": variants["suffix11"]["engineering_gate"],
        "suffix6_prescreen_pass": variants["suffix6"]["engineering_gate"],
        "real_p3_capture_required": True,
    }
    raw = (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode("utf-8")
    final_path.write_bytes(raw)
    print(json.dumps({"status": receipt["status"],
                      "suffix11_pass": receipt["suffix11_prescreen_pass"],
                      "suffix6_pass": receipt["suffix6_prescreen_pass"],
                      "receipt_sha256": hashlib.sha256(raw).hexdigest()}, sort_keys=True))


if __name__ == "__main__":
    main()
