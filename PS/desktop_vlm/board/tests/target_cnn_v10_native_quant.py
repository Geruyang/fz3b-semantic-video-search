#!/usr/bin/env python3
"""Target-side exactness and timing check for the optional C quantizer."""
from __future__ import print_function

import argparse
import hashlib
import json
import pathlib
import statistics
import time

import numpy as np

from activation_buffers import ActivationBufferWorkspace
from cnn_v10_native_quant import V10NativeQuantWorkspace
from cnn_v10_native_quant_ctypes import CtypesV10Quantizer


PROFILES = {
    0: (128, 32, "network1-bridge-output.f32"),
    1: (256, 16, "network3-bridge-output.f32"),
    2: (64, 64, "stem-prefix-output.f32"),
}


def _sha256(value):
    return hashlib.sha256(bytes(value)).hexdigest()


def _timed(function, iterations):
    values = []
    for unused in range(iterations):
        started = time.perf_counter()
        function()
        values.append((time.perf_counter() - started) * 1000.0)
    return {
        "count": len(values), "min_ms": min(values),
        "mean_ms": statistics.mean(values), "max_ms": max(values),
        "p50_ms": statistics.median(values),
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-manifest", required=True)
    parser.add_argument("--native-lib", required=True)
    parser.add_argument("--fixture-root", action="append", required=True)
    parser.add_argument("--iterations", type=int, default=20)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    if len(args.fixture_root) != 2 or args.iterations < 3:
        parser.error("two fixture roots and at least three iterations are required")
    output = pathlib.Path(args.output)
    if output.exists():
        raise RuntimeError("refusing to overwrite %s" % output)
    manifest_raw = pathlib.Path(args.release_manifest).read_bytes()
    manifest = json.loads(manifest_raw.decode("utf-8"))
    records = []
    for profile in (2, 0, 1):
        channels, width, filename = PROFILES[profile]
        scale = float(manifest["profiles"][str(profile)]["input_scale"])
        legacy = ActivationBufferWorkspace(profile, channels, width)
        native = V10NativeQuantWorkspace(
            profile, channels, width, native_lib=args.native_lib)
        scalar = V10NativeQuantWorkspace(
            profile, channels, width,
            native_lib=CtypesV10Quantizer(
                args.native_lib, symbol="cnn_v10_quantize_chw_to_hcw_scalar"))
        for lane, root in zip(("A", "B"), args.fixture_root):
            raw = (pathlib.Path(root) / filename).read_bytes()
            source = np.frombuffer(raw, dtype="<f4").copy().reshape(
                (1, channels, width, width))
            expected = legacy.quantize_chw_to_hcw(
                source, scale, "profile %d %s legacy" % (profile, lane)).copy()
            actual = native.quantize_chw_to_hcw(
                source, scale, "profile %d %s native" % (profile, lane)).copy()
            scalar_actual = scalar.quantize_chw_to_hcw(
                source, scale, "profile %d %s scalar" % (profile, lane)).copy()
            if not np.array_equal(actual, expected) or not np.array_equal(
                    scalar_actual, expected):
                mismatch = np.flatnonzero(actual.reshape(-1) != expected.reshape(-1))
                raise RuntimeError("profile %d %s scalar/NEON mismatch%s" %
                                   (profile, lane,
                                    " at %d" % int(mismatch[0]) if mismatch.size else ""))
            legacy_timing = _timed(
                lambda: legacy.quantize_chw_to_hcw(source, scale, "legacy"),
                args.iterations)
            native_timing = _timed(
                lambda: native.quantize_chw_to_hcw(source, scale, "native"),
                args.iterations)
            scalar_timing = _timed(
                lambda: scalar.quantize_chw_to_hcw(source, scale, "scalar"),
                args.iterations)
            records.append({
                "profile": profile, "lane": lane,
                "shape": list(source.shape), "scale": scale,
                "source_sha256": _sha256(raw),
                "quantized_sha256": _sha256(actual.tobytes(order="C")),
                "byte_exact_to_legacy": True,
                "legacy": legacy_timing, "native": native_timing,
                "scalar_c": scalar_timing,
                "native_over_legacy_mean": (
                    native_timing["mean_ms"] / legacy_timing["mean_ms"]),
            })
    # An odd-width synthetic vector forces the AArch64 scalar tail and covers
    # exact ties, adjacent FP32 values, saturation, and both signs. It is not
    # included in the timing comparison above.
    scale = 0.5
    quotients = np.asarray([
        -40000.0, -32768.5, -32768.0, -32767.5, -2.5, -2.0, -1.5,
        -1.0, -0.5, -0.0, 0.0, 0.5, 1.0, 1.5, 2.0, 2.5,
        32766.5, 32767.0, 32767.5, 40000.0], dtype=np.float32)
    values = np.tile(quotients * np.float32(scale), 9)[:175]
    values[20] = np.nextafter(np.float32(0.25), np.float32(0.0))
    values[21] = np.nextafter(np.float32(0.25), np.float32(1.0))
    source = values.reshape(1, 7, 5, 5)
    legacy = ActivationBufferWorkspace(99, 7, 5)
    neon = V10NativeQuantWorkspace(99, 7, 5, native_lib=args.native_lib)
    scalar = V10NativeQuantWorkspace(
        99, 7, 5, native_lib=CtypesV10Quantizer(
            args.native_lib, symbol="cnn_v10_quantize_chw_to_hcw_scalar"))
    expected = legacy.quantize_chw_to_hcw(source, scale, "synthetic").copy()
    neon_value = neon.quantize_chw_to_hcw(source, scale, "synthetic").copy()
    scalar_value = scalar.quantize_chw_to_hcw(source, scale, "synthetic").copy()
    if not np.array_equal(neon_value, expected) or not np.array_equal(
            scalar_value, expected):
        raise RuntimeError("synthetic scalar/NEON exactness mismatch")
    invalid = source.copy()
    invalid.reshape(-1)[73] = np.nan
    rejected = 0
    for workspace in (neon, scalar):
        try:
            workspace.quantize_chw_to_hcw(invalid, scale, "nonfinite")
        except ValueError:
            rejected += 1
    if rejected != 2:
        raise RuntimeError("native quantizer did not reject non-finite input")
    receipt = {
        "schema": "cnn-v10.1-native-quant-target-v1",
        "status": "PASS_ALL_PROFILES_TWO_FIXTURES_BYTE_EXACT",
        "release_manifest_sha256": _sha256(manifest_raw),
        "native_lib_sha256": _sha256(pathlib.Path(args.native_lib).read_bytes()),
        "rounding": "FP64 division, ties-to-even, signed INT16 saturation",
        "layout": "NCHW FP32 to HCW INT16",
        "iterations_per_record": args.iterations,
        "synthetic_edge_gate": {
            "shape": [1, 7, 5, 5], "odd_width_scalar_tail": True,
            "ties_nextafter_saturation_both_signs": True,
            "nonfinite_rejected_by_both_exports": True,
            "scalar_neon_numpy_byte_exact": True,
            "output_sha256": _sha256(expected.tobytes(order="C")),
        },
        "records": records,
    }
    raw = (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode("utf-8")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(raw)
    print(json.dumps({"status": receipt["status"],
                      "receipt_sha256": _sha256(raw)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
