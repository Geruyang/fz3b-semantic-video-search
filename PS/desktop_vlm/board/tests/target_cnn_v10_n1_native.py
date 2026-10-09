#!/usr/bin/env python3
"""Target correctness and timing gate for the optional N1 native bridge."""
from __future__ import print_function

import argparse
import hashlib
import json
import pathlib
import statistics
import time

import numpy as np

from activation_buffers import ActivationBufferWorkspace
from cnn_ddr_v5_runtime import load_v5_split_contracts
from cnn_pipeline_v10_mixed_runtime import Int16HCWActivation
from cnn_v10_n1_native_ctypes import CtypesN1NativeClient
from cnn_v10_ps_shm_clients import ShmOrtPartitionClient


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _stats(values):
    return {"count": len(values), "min_ms": min(values),
            "mean_ms": statistics.mean(values), "p50_ms": statistics.median(values),
            "max_ms": max(values)}


def _timed(function, warmup, measured):
    for unused in range(warmup):
        function()
    samples = []
    last = None
    for unused in range(measured):
        started = time.perf_counter()
        last = function()
        samples.append((time.perf_counter() - started) * 1000.0)
    return last, _stats(samples)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--expected-manifest-sha256", required=True)
    parser.add_argument("--native-lib", required=True)
    parser.add_argument("--model-root", required=True)
    parser.add_argument("--model-manifest", required=True)
    parser.add_argument("--expected-model-manifest-sha256", required=True)
    parser.add_argument("--runner", required=True)
    parser.add_argument("--fixture-root", action="append", required=True)
    parser.add_argument("--oracle-output", action="append", required=True)
    parser.add_argument("--threads", type=int, default=3)
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--measured", type=int, default=3)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    if (len(args.fixture_root) != len(args.oracle_output) or
            len(args.fixture_root) < 2 or args.warmup < 1 or args.measured < 3):
        parser.error("matching two or more fixtures and at least 1 warmup/3 measured are required")
    output_path = pathlib.Path(args.output)
    if output_path.exists():
        raise RuntimeError("refusing to overwrite %s" % output_path)

    native = CtypesN1NativeClient(
        args.manifest, args.native_lib, args.expected_manifest_sha256)
    split = load_v5_split_contracts(
        args.model_root, args.expected_model_manifest_sha256)
    record = split["models"]["network1-bridge"]
    ort = ShmOrtPartitionClient(
        [args.runner, record["path"], str(args.threads)],
        record["contract"], threads=args.threads)
    profile2_scale = float(native.manifest["input"]["logical_pl_scale_value_f64"])
    profile0_scale = float(native.manifest["output"]["logical_pl_scale_value_f64"])
    qin = ActivationBufferWorkspace(2, 64, 64)
    qout = ActivationBufferWorkspace(0, 128, 32)
    rows = []
    try:
        for index, (fixture_root, expected_path) in enumerate(
                zip(args.fixture_root, args.oracle_output)):
            source_raw = (pathlib.Path(fixture_root) /
                          "network1-bridge-input.f32").read_bytes()
            source = np.frombuffer(source_raw, dtype="<f4").copy().reshape(
                1, 64, 64, 64)
            expected_raw = pathlib.Path(expected_path).read_bytes()
            expected_fp32 = np.frombuffer(expected_raw, dtype="<f4").copy().reshape(
                1, 128, 32, 32)
            source_hcw = qin.quantize_chw_to_hcw(
                source, profile2_scale, "N1 target input").copy()
            expected_hcw = qout.quantize_chw_to_hcw(
                expected_fp32, profile0_scale, "N1 target expected").copy()
            activation = Int16HCWActivation(
                source_hcw, 2, profile2_scale, (1, 64, 64, 64))
            neon_last, neon_wall = _timed(
                lambda: native.infer_int16_hcw(activation),
                args.warmup, args.measured)
            scalar_last, scalar_wall = _timed(
                lambda: native.infer_int16_hcw_scalar(activation),
                args.warmup, args.measured)
            profiled_value, profiled_total_ms, profiled_dw_ms, profiled_pw_ms = (
                native.infer_int16_hcw_profile(activation))
            ort_last, ort_wall = _timed(
                lambda: ort.infer([source]), args.warmup, args.measured)
            neon_value, neon_run = neon_last
            scalar_value, scalar_run = scalar_last
            neon_scalar = neon_value.payload.reshape(-1) != scalar_value.payload.reshape(-1)
            neon_oracle = neon_value.payload.reshape(-1) != expected_hcw.reshape(-1)
            scalar_oracle = scalar_value.payload.reshape(-1) != expected_hcw.reshape(-1)
            code_delta = np.abs(neon_value.payload.astype(np.int32) -
                                expected_hcw.astype(np.int32))
            # Integer PW NEON must exactly equal the shared scalar C path.
            # The independent oracle crosses platform libm/FP32 GELU and is
            # assessed separately: sparse one-code differences are expected at
            # ties and do not weaken the final feature gate.
            if neon_scalar.any():
                raise RuntimeError("N1 target NEON/scalar mismatch count=%d" %
                                   int(neon_scalar.sum()))
            if not np.array_equal(neon_value.payload, profiled_value.payload):
                raise RuntimeError("N1 profiled export differs from NEON export")
            actual_fp32 = qout.dequantize_hcw_to_chw(
                neon_value.payload, profile0_scale, "N1 target actual")
            a = actual_fp32.reshape(-1).astype(np.float64)
            b = expected_fp32.reshape(-1).astype(np.float64)
            relative_l2 = float(np.linalg.norm(a - b) / np.linalg.norm(b))
            cosine = float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
            max_abs = float(np.max(np.abs(a - b)))
            if cosine < 0.999 or relative_l2 > 0.05 or max_abs > 0.08:
                raise RuntimeError(
                    "N1 target FP32/GELU gate failed mismatches=%d max_code=%d "
                    "cosine=%.9f rel_l2=%.9f max_abs=%.9f" %
                    (int(neon_oracle.sum()), int(code_delta.max()),
                     cosine, relative_l2, max_abs))
            ort_output = ort_last[0][record["contract"]["outputs"][0]["name"]]
            rows.append({
                "case_index": index,
                "source_sha256": _sha(source_raw),
                "oracle_fp32_sha256": _sha(expected_raw),
                "output_i16_sha256": _sha(neon_value.payload.tobytes(order="C")),
                "neon_scalar_i16_byte_exact": True,
                "python_oracle_i16_mismatch_count": int(neon_oracle.sum()),
                "python_oracle_i16_mismatch_fraction": float(neon_oracle.mean()),
                "python_oracle_i16_max_code_delta": int(code_delta.max()),
                "fp32_gelu_reference_cosine": cosine,
                "fp32_gelu_reference_relative_l2": relative_l2,
                "fp32_gelu_reference_max_abs": max_abs,
                "neon_run_ms_last": neon_run,
                "scalar_run_ms_last": scalar_run,
                "profiled_total_ms": profiled_total_ms,
                "profiled_dw_ms": profiled_dw_ms,
                "profiled_pw_ms": profiled_pw_ms,
                "neon_wall": neon_wall, "scalar_wall": scalar_wall,
                "ort_wall": ort_wall,
                "ort_run_ms_last": float(ort_last[1]),
                "ort_output_sha256": _sha(ort_output.astype("<f4", copy=False).tobytes()),
            })
    finally:
        ort.close()
    receipt = {
        "schema": "cnn-v10.1-n1-native-target-v1",
        "status": "PASS_TARGET_NEON_SCALAR_EXACT_FP32_GELU_GATE",
        "manifest_sha256": args.expected_manifest_sha256,
        "library_sha256": _sha(pathlib.Path(args.native_lib).read_bytes()),
        "source_model_sha256": native.manifest["source_model"]["sha256"],
        "threads": args.threads, "warmup": args.warmup,
        "measured": args.measured,
        "timing_scope": "N1-only; native begins/ends at frozen INT16 HCW boundaries; ORT is FP32 model run; setup excluded",
        "integer_exact_scope": "AArch64 NEON PW and scalar PW produce byte-identical final I16 boundaries; host tests separately compare scalar integer path to Python full-shape oracle",
        "fp32_sensitive_scope": (
            "%d PW output channels retain FP32 weights/accumulation; platform "
            "libm/FP32 GELU differences are reported as code deltas and "
            "engineering cosine/relative-L2, separately from integer exactness" %
            len(native.manifest.get("pw_fp32_channels", []))),
        "pw_fp32_channels": list(native.manifest.get("pw_fp32_channels", [])),
        "rows": rows,
    }
    raw = (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode("utf-8")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(raw)
    print(json.dumps({"status": receipt["status"],
                      "receipt_sha256": _sha(raw)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
