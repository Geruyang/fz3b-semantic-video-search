"""Audit v4 INT32 accumulator bounds for C=128 and C=256 profiles."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import onnx

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_network2_int_oracle as n2

INT32_MAX = np.iinfo(np.int32).max
N2_ORACLE = Path("artifacts/board-debug-20261005/acceleration/host/network2-int-oracle-board-ps-001/manifest.json")
N2_TRACE = Path("artifacts/board-debug-20261005/acceleration/network/network2-block-traces-ps-001/board-ps-collection-manifest.json")
MODEL = Path("artifacts/board-debug-20261004/host/s1-onnx-001/mobileclip_s1_image.onnx")
N4_ORACLE = Path("artifacts/board-debug-20261005/acceleration/host/network4-host-quant-contract-001/manifest.json")


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_meta(root, meta):
    path = root / meta["path"]
    raw = path.read_bytes()
    if len(raw) != meta["bytes"] or hashlib.sha256(raw).hexdigest() != meta["sha256"]:
        raise ValueError("tensor SHA/size mismatch: " + str(path))
    value = np.frombuffer(raw, dtype=np.dtype(meta["dtype"]))
    if value.size != int(np.prod(meta["shape"])):
        raise ValueError("tensor shape mismatch: " + str(path))
    return value.reshape(meta["shape"]).copy()


def peak_entry(values, sample_id, block, op, kind):
    channel_values = np.max(np.abs(np.asarray(values, dtype=np.int64)), axis=(1, 2))
    index = int(np.argmax(channel_values))
    return {"sample_id": sample_id, "block": block, "op": op, "kind": kind,
            "channel": index, "abs_peak": int(channel_values[index])}


def parameter_files_n2(oracle_path, oracle, block_index):
    root = oracle_path.resolve().parent
    block = oracle["blocks"][block_index]
    files = block["files"]
    return {
        "weights": {"pw1": read_meta(root, files["pw1_weights"]),
                    "pw2": read_meta(root, files["pw2_weights"])},
        "bias": {"pw1": read_meta(root, {**files["bias_i32"], "shape": [768]})[256:640],
                 "pw2": read_meta(root, {**files["bias_i32"], "shape": [768]})[640:768]},
        "source_sha256": block["parameter_manifest_sha256"],
    }


def audit_n2(oracle_path, trace_path):
    oracle = json.loads(oracle_path.read_text(encoding="utf-8"))
    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    info = n2.validate_trace_manifest(trace)
    if info["provenance"] != "BOARD_PS":
        raise ValueError("network2 accumulator audit requires real BOARD_PS calibration trace")
    trace_samples = n2.load_trace_arrays(trace_path, trace)
    scales = n2.symmetric_calibration_scales(trace_samples)
    model = onnx.load(str(MODEL))
    records = []
    max_activation = [{"pw1": 0, "pw2": 0} for _ in range(12)]
    actual_peaks = {}
    actual_raw = {}
    layer_by_block = [n2.extract_block_parameters(model, block) for block in trace["blocks"]]
    for sample in trace_samples:
        qinput = n2.quantize_symmetric(sample["blocks"][0]["input"], scales[0]["input"], 16)[0]
        for index, block in enumerate(trace["blocks"]):
            layers = layer_by_block[index]
            arrays, specs = n2.make_block_parameter_arrays(layers, scales[index])
            params = dict(specs)
            for key in ("scale_multiplier_i32", "scale_shift_i32", "residual_multiplier_i32", "residual_shift_i32"):
                params[key] = arrays[key]
            qadd, stages = n2.execute_block(qinput, params, scales[index], layers, arrays["gelu_lut"])
            input_pw = {"pw1": stages["dw7"], "pw2": stages["gelu"]}
            for op in ("pw1", "pw2"):
                mag = int(np.max(np.abs(input_pw[op].astype(np.int64))))
                max_activation[index][op] = max(max_activation[index][op], mag)
                accumulator = stages["accumulators"][op]
                for kind, tensor in (("raw", accumulator["raw"]),
                                     ("bias_included", accumulator["bias_included"])):
                    entry = peak_entry(tensor, sample["sample_id"], index, op, kind)
                    key = (index, op, kind)
                    if key not in actual_peaks or entry["abs_peak"] > actual_peaks[key]["abs_peak"]:
                        actual_peaks[key] = entry
                actual_raw[index, op] = stages["accumulators"][op]
            qinput = qadd
    for index in range(12):
        p = parameter_files_n2(oracle_path, oracle, index)
        for op in ("pw1", "pw2"):
            weights = p["weights"][op].astype(np.int64)
            bias = p["bias"][op].astype(np.int64).reshape(-1)
            l1 = np.sum(np.abs(weights), axis=1)
            full = 32767 * l1 + np.abs(bias)
            observed_range = max_activation[index][op]
            calibrated = observed_range * l1 + np.abs(bias)
            raw_peak = actual_peaks[index, op, "raw"]
            biased_peak = actual_peaks[index, op, "bias_included"]
            records.append({"block": index, "op": op, "input_reduction": int(weights.shape[1]),
                            "output_channels": int(weights.shape[0]),
                            "input_abs_bound_full_int16": 32767,
                            "input_abs_bound_fixture_range": observed_range,
                            "per_output_channel": [{"channel": channel,
                                                    "weight_l1": int(l1[channel]),
                                                    "abs_bias": int(abs(bias[channel])),
                                                    "full_range_bound": int(full[channel]),
                                                    "fixture_range_bound": int(calibrated[channel]),
                                                    "full_range_fits_int32": bool(full[channel] <= INT32_MAX),
                                                    "fixture_bound_fits_int32": bool(calibrated[channel] <= INT32_MAX)}
                                                   for channel in range(weights.shape[0])],
                            "full_range_max": {"channel": int(np.argmax(full)), "bound": int(full.max()),
                                               "fits_int32": bool(np.all(full <= INT32_MAX))},
                            "fixture_range_max": {"channel": int(np.argmax(calibrated)),
                                                  "bound": int(calibrated.max()),
                                                  "fits_int32": bool(np.all(calibrated <= INT32_MAX))},
                            "actual_fixture_raw_peak": raw_peak,
                            "actual_fixture_bias_included_peak": biased_peak,
                            "source_parameter_sha256": p["source_sha256"]})
    return {"profile": "network2-C128", "status": oracle["status"],
            "oracle_manifest_sha256": sha256(oracle_path), "trace_manifest_sha256": sha256(trace_path),
            "records": records}


def audit_n4(oracle_path):
    oracle = json.loads(oracle_path.read_text(encoding="utf-8"))
    root = oracle_path.resolve().parent
    max_activation = [{"pw1": 0, "pw2": 0} for _ in range(20)]
    actual_peaks = {}
    for sample in oracle["results"]:
        for block in sample["blocks"]:
            index = block["index"]
            outputs = block["outputs"]
            for op, input_key, raw_key, biased_key in (
                    ("pw1", "dw7_output_i16", "pw1_raw_i64", "pw1_bias_included_i32"),
                    ("pw2", "gelu_output_i16", "pw2_raw_i64", "pw2_bias_included_i32")):
                activation = read_meta(root, outputs[input_key])
                max_activation[index][op] = max(max_activation[index][op],
                    int(np.max(np.abs(activation.astype(np.int64)))))
                for kind, key in (("raw", raw_key), ("bias_included", biased_key)):
                    values = read_meta(root, outputs[key])
                    entry = peak_entry(values, sample["sample_id"], index, op, kind)
                    slot = (index, op, kind)
                    if slot not in actual_peaks or entry["abs_peak"] > actual_peaks[slot]["abs_peak"]:
                        actual_peaks[slot] = entry
    records = []
    for index, block in enumerate(oracle["blocks"]):
        params = block["parameters"]
        def get(name):
            return read_meta(root, params[name])
        for op in ("pw1", "pw2"):
            weights = get(f"{op}_weights_i8").astype(np.int64)
            bias = get(f"{op}_bias_i32").astype(np.int64).reshape(-1)
            l1 = np.sum(np.abs(weights), axis=1)
            full = 32767 * l1 + np.abs(bias)
            calibrated = max_activation[index][op] * l1 + np.abs(bias)
            records.append({"block": index, "op": op, "input_reduction": int(weights.shape[1]),
                            "output_channels": int(weights.shape[0]),
                            "input_abs_bound_full_int16": 32767,
                            "input_abs_bound_fixture_range": max_activation[index][op],
                            "per_output_channel": [{"channel": channel,
                                                    "weight_l1": int(l1[channel]),
                                                    "abs_bias": int(abs(bias[channel])),
                                                    "full_range_bound": int(full[channel]),
                                                    "fixture_range_bound": int(calibrated[channel]),
                                                    "full_range_fits_int32": bool(full[channel] <= INT32_MAX),
                                                    "fixture_bound_fits_int32": bool(calibrated[channel] <= INT32_MAX)}
                                                   for channel in range(weights.shape[0])],
                            "full_range_max": {"channel": int(np.argmax(full)), "bound": int(full.max()),
                                               "fits_int32": bool(np.all(full <= INT32_MAX))},
                            "fixture_range_max": {"channel": int(np.argmax(calibrated)),
                                                  "bound": int(calibrated.max()),
                                                  "fits_int32": bool(np.all(calibrated <= INT32_MAX))},
                            "actual_fixture_raw_peak": actual_peaks[index, op, "raw"],
                            "actual_fixture_bias_included_peak": actual_peaks[index, op, "bias_included"]})
    return {"profile": "network4-C256", "status": oracle["status"],
            "oracle_manifest_sha256": sha256(oracle_path), "records": records}


def summarize(profile):
    maximum = {"full_range": None, "fixture_range": None, "actual_raw": None, "actual_bias_included": None}
    for record in profile["records"]:
        candidates = [("full_range", record["full_range_max"]["bound"],
                      record["full_range_max"]["channel"]),
                     ("fixture_range", record["fixture_range_max"]["bound"],
                      record["fixture_range_max"]["channel"]),
                     ("actual_raw", record["actual_fixture_raw_peak"]["abs_peak"],
                      record["actual_fixture_raw_peak"]["channel"]),
                     ("actual_bias_included", record["actual_fixture_bias_included_peak"]["abs_peak"],
                      record["actual_fixture_bias_included_peak"]["channel"])]
        for key, value, channel in candidates:
            if maximum[key] is None or value > maximum[key]["value"]:
                maximum[key] = {"value": int(value), "block": record["block"],
                                "op": record["op"], "channel": int(channel),
                                "fits_int32": int(value) <= INT32_MAX}
    return maximum


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--network2-oracle", default=str(N2_ORACLE))
    parser.add_argument("--network2-trace", default=str(N2_TRACE))
    parser.add_argument("--network4-oracle", default=str(N4_ORACLE))
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    profiles = [audit_n2(Path(args.network2_oracle), Path(args.network2_trace)),
                audit_n4(Path(args.network4_oracle))]
    for profile in profiles:
        profile["summary_maxima"] = summarize(profile)
        profile["any_full_range_overflow"] = any(not item["full_range_max"]["fits_int32"]
                                                   for item in profile["records"])
        profile["any_fixture_range_overflow"] = any(not item["fixture_range_max"]["fits_int32"]
                                                      for item in profile["records"])
    all_overflow = any(p["any_full_range_overflow"] or p["any_fixture_range_overflow"] for p in profiles)
    report = {"schema_version": 1,
              "status": "V4_ACCUMULATOR_AUDIT_OVERFLOW_REQUIRES_WIDER_ACCUMULATOR_OR_EXPLICIT_RANGE_CONTRACT"
                        if all_overflow else "V4_ACCUMULATOR_AUDIT_INT32_BOUNDS_PASS",
              "int32_max": int(INT32_MAX), "profiles": profiles,
              "overflow_policy": "Do not wrap or modify the existing oracle. Request wider accumulation or an evidence-based input-range contract for any failing profile.",
              "per_output_channel_bounds": True,
              "fixture_actual_peaks_include_block_op_channel_and_sample": True,
              "pl_execution": False}
    path = Path(args.output)
    if path.exists():
        raise FileExistsError(f"refusing to overwrite {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(path.resolve()), "status": report["status"],
                      "profiles": [{"profile": p["profile"], "full": p["summary_maxima"]["full_range"],
                                   "fixture": p["summary_maxima"]["fixture_range"],
                                   "actual": p["summary_maxima"]["actual_bias_included"],
                                   "full_overflow": p["any_full_range_overflow"],
                                   "fixture_overflow": p["any_fixture_range_overflow"]} for p in profiles]},
                     indent=2))


if __name__ == "__main__":
    main()
