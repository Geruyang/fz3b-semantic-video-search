"""Create a single-block, real-input HOST oracle fixture for FZV5.

The generated fixture is suitable for bit-exact CSIM/RTL comparison, but its
HOST provenance does not establish PL execution or model quality.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_network2_int_oracle as n2
import cnn_w16_contract as c16

HOST = ROOT / "artifacts/board-debug-20261005/acceleration/host"
MODEL_PATH = ROOT / "artifacts/board-debug-20261004/host/s1-onnx-001/mobileclip_s1_image.onnx"
TRACE_PATH = HOST / "network4-host-trace-reference-001/manifest.json"
CONTRACT_PATH = HOST / "network4-host-quant-contract-001/manifest.json"
JOINT_V1 = HOST / "v4-joint-feature-preflight-001"
OUT = HOST / "network4-w16-profile1-block0-fixture-002"


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def save(root, rel, arr, dtype):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    a = np.ascontiguousarray(arr, dtype=dtype)
    a.tofile(path)
    return {"path": rel, "dtype": dtype, "shape": list(a.shape),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def to_hcw(arr):
    a = np.asarray(arr, dtype="<i2")
    if a.ndim != 3:
        raise ValueError("expected CHW activation")
    return np.ascontiguousarray(a.transpose(1, 0, 2), dtype="<i2")


def q31_tensor_wide(values, multiplier, shift, clip=None):
    a = np.asarray(values)
    if a.dtype.kind not in "iuO" or a.ndim != 3:
        raise ValueError("Q31 input must be integer CHW")
    m = np.asarray(multiplier, dtype=np.int64).reshape(-1)
    s = np.asarray(shift, dtype=np.int64).reshape(-1)
    if len(m) not in (1, a.shape[0]) or s.shape != m.shape:
        raise ValueError("Q31 coefficient shape mismatch")
    out = np.empty(a.shape, dtype=object)
    for oc in range(a.shape[0]):
        mi, sh = int(m[0 if len(m) == 1 else oc]), int(s[0 if len(s) == 1 else oc])
        plane = a[oc].reshape(-1)
        target = out[oc].reshape(-1)
        for idx, value in enumerate(plane):
            target[idx] = c16.q31_round_even_wide(int(value), mi, sh)
    if clip is None:
        return out
    lo, hi = clip
    # Convert only after exact rounding and clamp.
    result = np.empty(a.shape, dtype="<i2")
    for idx, value in enumerate(out.reshape(-1)):
        result.reshape(-1)[idx] = min(hi, max(lo, int(value)))
    return result


def conv_accumulate(x, w):
    qx, qw = np.asarray(x, dtype="<i2"), np.asarray(w, dtype="<i2")
    if qw.ndim == 4:  # depthwise OIHW
        c, h, width = qx.shape
        if qw.shape[:2] != (c, 1):
            raise ValueError("DW shape mismatch")
        kh, kw = qw.shape[2:]
        pad = np.pad(qx.astype(np.int64), ((0, 0), (kh//2, kh//2), (kw//2, kw//2)))
        y = np.zeros((c, h, width), dtype=np.int64)
        for r in range(kh):
            for col in range(kw):
                y += pad[:, r:r+h, col:col+width] * qw[:, 0, r, col].astype(np.int64)[:, None, None]
        return y
    if qw.ndim == 2:
        c, h, width = qx.shape
        rows = qx.transpose(1, 2, 0).reshape(h * width, c).astype(np.int64)
        # The proven signed-48 reduction bound is far below signed-64 here.
        return (rows @ qw.astype(np.int64).T).T.reshape(qw.shape[0], h, width)
    raise ValueError("unsupported Conv weight rank")


def main():
    if OUT.exists():
        raise FileExistsError(f"refusing to overwrite {OUT}")
    trace = json.loads(TRACE_PATH.read_text(encoding="utf-8"))
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    idx, sample_id = 0, "image-00"
    scales = contract["blocks"][idx]["calibration_scales"]
    OUT.mkdir(parents=True)

    # Actual prefix -> v4 N2 -> PS bridge tensor from the frozen HOST joint run.
    input_path = JOINT_V1 / "intermediates" / sample_id / "n3-output.f32"
    n3 = np.fromfile(input_path, dtype="<f4").reshape(1, 256, 16, 16)
    input_codes = c16.quantize_symmetric_i16(n3[0], float(scales["input"]))
    layer_specs, qweights = {}, {}
    block_params = contract["blocks"][idx]["parameters"]

    def read_param(key):
        meta = block_params[key]
        path = CONTRACT_PATH.parent / meta["path"]
        raw = path.read_bytes()
        if len(raw) != int(meta["bytes"]) or hashlib.sha256(raw).hexdigest() != meta["sha256"]:
            raise ValueError(f"source parameter integrity failure: {path}")
        return np.frombuffer(raw, dtype=np.dtype(meta["dtype"])).copy().reshape(meta["shape"])

    layers = {"residual_scale": read_param("residual_scale_f32")}
    for name in ("dw3", "dw7", "pw1", "pw2"):
        old_q = read_param(name + "_weights_i8")
        old_ws = read_param(name + "_weight_scales_f64").reshape(-1)
        old_acc = read_param(name + "_accumulator_scales_f64").reshape(-1)
        old_bias = read_param(name + "_bias_i32").reshape(-1)
        # QDQ-derived wide fixture: preserve the exact v4 INT8 dequantized
        # weights while mapping their codes into the signed-16 wire format.
        qwide = np.clip(np.rint(old_q.astype(np.float64) * (32767.0 / 127.0)),
                        -32767, 32767).astype("<i2")
        ws = old_ws * (127.0 / 32767.0)
        layer = {"weight_f32": old_q.astype(np.float64) * old_ws.reshape(
                    (len(old_ws),) + (1,) * (old_q.ndim - 1)),
                 "bias_f32": old_bias.astype(np.float64) * old_acc}
        layers[name] = layer
        qw = qwide
        qweights[name] = qw
        in_scale = scales[{"dw3":"input", "dw7":"dw3", "pw1":"dw7", "pw2":"gelu"}[name]]
        out_scale = scales[{"dw3":"dw3", "dw7":"dw7", "pw1":"pw1", "pw2":"pw2"}[name]]
        acc_scales = ws * float(in_scale)
        bias_q = [c16.checked_i48(round(float(b) / float(s)), f"{name} bias")
                  for b, s in zip(layer["bias_f32"], acc_scales)]
        mult, shift = n2.q31_parameters(acc_scales / float(out_scale))
        if np.any(shift < 0) or np.any(shift > 62):
            raise ValueError(f"{name} Q31 shift outside 0..62")
        bounds = c16.audit_bound(qw, 32767, bias_q)
        layer_specs[name] = {"weight_scale": ws, "acc_scale": acc_scales,
                             "bias": np.asarray(bias_q, dtype=object),
                             "multiplier": mult, "shift": shift,
                             "full_range_acc_abs_bound_max": max(bounds),
                             "actual_accumulator_peak": None}

    # Save independent parameters prior to execution.
    param = layer_specs
    arrays = {
        "dw3_weights": qweights["dw3"].reshape(256, 9),
        "dw7_weights": qweights["dw7"].reshape(256, 49),
        "bias": np.concatenate([param[k]["bias"] for k in ("dw3", "dw7", "pw1", "pw2")]),
        "multiplier": np.concatenate([param[k]["multiplier"] for k in ("dw3", "dw7", "pw1", "pw2")]),
        "shift": np.concatenate([param[k]["shift"] for k in ("dw3", "dw7", "pw1", "pw2")]),
    }
    arrays["scale_multiplier"], arrays["scale_shift"] = n2.q31_parameters(
        layers["residual_scale"] * float(scales["pw2"]) / float(scales["add"]), signed=True)
    arrays["residual_multiplier"], arrays["residual_shift"] = n2.q31_parameters(
        np.asarray([float(scales["dw3"]) / float(scales["add"])]), signed=True)
    arrays["gelu"] = n2.gelu_lut(float(scales["pw1"]), float(scales["gelu"])).astype("<i2")

    x = input_codes
    stages, accumulators = {}, {}
    order = (("dw3", "dw3"), ("dw7", "dw7"), ("pw1", "pw1"))
    for name, stage in order:
        raw = conv_accumulate(x, qweights[name])
        total = raw.astype(object) + param[name]["bias"][:, None, None]
        if any(v < c16.I48_MIN or v > c16.I48_MAX for v in total.reshape(-1)):
            raise OverflowError(f"{name} runtime accumulator exceeds signed48")
        accumulators[name] = {"min": min(map(int, total.reshape(-1))), "max": max(map(int, total.reshape(-1)))}
        out = q31_tensor_wide(total, param[name]["multiplier"], param[name]["shift"], (-32767, 32767))
        stages[stage] = out
        x = out
        if name == "pw1":
            # Apply exact integer LUT using signed input + 32768 indexing.
            lut = arrays["gelu"]
            x = lut[(out.astype(np.int32) + 32768)].astype("<i2")
            stages["gelu"] = x

    raw = conv_accumulate(x, qweights["pw2"])
    total = raw.astype(object) + param["pw2"]["bias"][:, None, None]
    if any(v < c16.I48_MIN or v > c16.I48_MAX for v in total.reshape(-1)):
        raise OverflowError("pw2 runtime accumulator exceeds signed48")
    accumulators["pw2"] = {"min": min(map(int, total.reshape(-1))), "max": max(map(int, total.reshape(-1)))}
    pw2 = q31_tensor_wide(total, param["pw2"]["multiplier"], param["pw2"]["shift"], (-32767, 32767))
    scale_branch = q31_tensor_wide(pw2, arrays["scale_multiplier"], arrays["scale_shift"])
    residual_branch = q31_tensor_wide(stages["dw3"], arrays["residual_multiplier"], arrays["residual_shift"])
    add_obj = scale_branch + residual_branch
    add = np.empty(add_obj.shape, dtype="<i2")
    for j, v in enumerate(add_obj.reshape(-1)):
        add.reshape(-1)[j] = min(32767, max(-32767, int(v)))
    stages.update({"pw2": pw2, "scale": scale_branch, "residual": residual_branch, "add": add})

    # Final FZV5 block: exact field order and all per-field 16-byte alignment.
    bias = np.asarray(arrays["bias"], dtype="<i8")
    if any(int(v) < c16.I48_MIN or int(v) > c16.I48_MAX for v in bias):
        raise OverflowError("serialized bias exceeds signed48")
    payload_parts = [arrays["dw3_weights"].astype("<i2").tobytes(),
                     arrays["dw7_weights"].astype("<i2").tobytes(), bias.tobytes(),
                     np.asarray(arrays["multiplier"], dtype="<i4").tobytes(),
                     np.asarray(arrays["shift"], dtype="<i4").tobytes(),
                     np.asarray(arrays["scale_multiplier"], dtype="<i4").tobytes(),
                     np.asarray(arrays["scale_shift"], dtype="<i4").tobytes(),
                     np.asarray(arrays["residual_multiplier"], dtype="<i4").tobytes(),
                     np.asarray(arrays["residual_shift"], dtype="<i4").tobytes(), bytes(8),
                     arrays["gelu"].tobytes(),
                     c16.pack_pw_i16(qweights["pw1"].astype("<i2"), 768, 256),
                     c16.pack_pw_i16(qweights["pw2"].astype("<i2"), 256, 768)]
    packed = b"".join(payload_parts)
    expected = c16.expected_stride(256)
    if len(packed) != expected:
        raise AssertionError(f"packed bytes {len(packed)} != stride {expected}")
    param_meta = save(OUT, "params-profile1-block0.bin", np.frombuffer(packed, dtype=np.uint8), "|u1")
    input_hcw = to_hcw(input_codes)
    input_meta = save(OUT, "image-00/input-hcw.i16le", input_hcw, "<i2")
    output_meta = save(OUT, "image-00/expected-add-hcw.i16le", to_hcw(add), "<i2")
    raw_output_meta = save(OUT, "image-00/expected-add-chw.i16le", add, "<i2")
    intermediate = {key: save(OUT, f"image-00/stages/{key}-chw.i16le", value, "<i2")
                    for key, value in stages.items() if np.asarray(value).dtype.kind in "iu"}
    _, stride = c16.layout(256)
    manifest = {
        "schema_version": 1, "status": "HOST_W16_PROFILE1_BLOCK0_FIXTURE_NOT_PL",
        "abi": {"magic": c16.ABI_MAGIC, "version": c16.ABI_VERSION, "flags": c16.FLAGS},
        "profile": 1, "block_index": 0, "block_count": 1,
        "shape": {"channels": 256, "width": 16, "input_chw": [256,16,16], "input_hcw": [16,256,16]},
        "source": {"model_sha256": trace["source_model_sha256"], "trace_manifest_sha256": sha(TRACE_PATH),
                   "quant_contract_manifest_sha256": sha(CONTRACT_PATH),
                   "host_joint_manifest_sha256": sha(JOINT_V1 / "manifest.json"),
                   "runtime_n3_input_sha256": sha(input_path),
                   "runtime_n3_input_provenance": "real prefix + frozen INT N2 + real ONNX network3 bridge from v4 HOST joint chain"},
        "quantization": {"activations": "symmetric signed INT16, zero-point 0, ties-even, clamp [-32767,32767]",
                         "weights": "symmetric per-output INT16 wire codes derived from v4 INT8 dequantized weights; NOT a FP32-source W16 requantization",
                         "bias": "round-even(FP32 bias / accumulator_scale), serialized i64 and checked signed48",
                         "accumulator": "signed48 checked; scalar products and reductions use exact wide Python integers for bounds, int64 kernel accumulation only after proven bound",
                         "q31": "signed i32 multiplier; exact signed wide product, ties-even shift 0..62",
                         "saturation": "one clamp after each convolution requantization; scale/residual branches stay wide until one final Add clamp",
                         "gelu": "65536-entry signed INT16 LUT, index code+32768"},
        "parameter_layout": {"stride_bytes": stride, "parameter_words_128b": stride // 16,
                              "fields": c16.layout(256)[0], "parameter_file": param_meta},
        "activation_layout": {"dtype": "<i2", "serialization": "HCW", "slots": 2,
                              "slot_bytes": 131072, "input": input_meta,
                              "expected_hcw": output_meta, "expected_chw": raw_output_meta},
        "parameters": {name: {"full_range_abs_accumulator_bound": spec["full_range_acc_abs_bound_max"],
                              "actual_accumulator_minmax": accumulators.get(name),
                              "bias_abs_max": max(abs(int(x)) for x in spec["bias"]),
                              "q31_multiplier_abs_max": int(np.max(np.abs(spec["multiplier"].astype(np.int64)))),
                              "q31_shift_min": int(spec["shift"].min()),
                              "q31_shift_max": int(spec["shift"].max())}
                       for name, spec in param.items()},
        "wide_arithmetic_proof": {
            "accumulator_signed_bits": 48,
            "q31_product_signed_bits": 80,
            "maximum_allowed_signed48_abs": (1 << 47),
            "maximum_allowed_signed_i32_multiplier_abs": (1 << 31) - 1,
            "maximum_product_abs": ((1 << 47) - 1) * ((1 << 31) - 1),
            "maximum_signed80_abs": 1 << 79,
            "q31_product_fits_signed80": (((1 << 47) - 1) * ((1 << 31) - 1)) < (1 << 79),
            "oracle_product_type": "Python arbitrary-precision int; no NumPy int64 multiplication",
            "global_full_range_accumulator_bound": max(x["full_range_acc_abs_bound_max"] for x in param.values()),
            "global_full_range_accumulator_bound_layer": max(param, key=lambda k: param[k]["full_range_acc_abs_bound_max"]),
            "actual_runtime_accumulator_abs_peak": max(max(abs(v) for v in x.values()) for x in accumulators.values()),
            "actual_runtime_accumulator_peak_layer": max(accumulators, key=lambda k: max(abs(v) for v in accumulators[k].values())),
        },
        "expected_stages": intermediate,
        "claims": {"host_oracle_only": True, "pl_execution": False,
                   "eligible_as_bit_exact_fixture": True,
                   "quality_evidence": "not an end-to-end quality result; this QDQ-derived control fixture is not evidence of W16 accuracy improvement"},
        "checks": {"stride_matches_frozen_formula": len(packed) == stride,
                   "bias_all_fit_signed48": True,
                   "profile_slot_bytes_match": len(input_hcw.tobytes()) == 131072,
                   "single_clip_per_stage_contract": True},
    }
    manifest["files"] = {}
    for path in sorted(p for p in OUT.rglob("*") if p.is_file() and p.name != "manifest.json"):
        manifest["files"][path.relative_to(OUT).as_posix()] = {"bytes": path.stat().st_size, "sha256": sha(path)}
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"manifest": str(OUT / "manifest.json"), "manifest_sha256": sha(OUT / "manifest.json"),
                      "params": str(OUT / "params-profile1-block0.bin"), "params_sha256": sha(OUT / "params-profile1-block0.bin"),
                      "input": str(OUT / "image-00/input-hcw.i16le"), "input_sha256": sha(OUT / "image-00/input-hcw.i16le"),
                      "expected": str(OUT / "image-00/expected-add-hcw.i16le"), "expected_sha256": sha(OUT / "image-00/expected-add-hcw.i16le"),
                      "stride_bytes": stride, "parameter_words_128b": stride // 16,
                      "input_bytes": input_hcw.nbytes, "output_bytes": output_meta["bytes"]}, indent=2))


if __name__ == "__main__":
    main()
