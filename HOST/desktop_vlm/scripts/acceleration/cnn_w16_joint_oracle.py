"""Run the real HOST INT16-activation/INT16-weight N2+N4 joint oracle.

Only prefix/network3/suffix use ORT; N2 and N4 are independent integer
oracles using Python-wide Q31 products. No output is board/PL evidence.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import onnx
import onnxruntime as ort

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_network2_int_oracle as n2
import cnn_w16_contract as c16
from cnn_w16_fixture import conv_accumulate, q31_tensor_wide, to_hcw

HOST = ROOT / "artifacts/board-debug-20261005/acceleration/host"
OLD = ROOT / "artifacts/board-debug-20261004/host/s1-onnx-001"
MODEL = OLD / "mobileclip_s1_image.onnx"
SPLITS = HOST / "v4-runtime-models-001"
N2_DIR = HOST / "network2-int-oracle-board-ps-001"
N2_MANIFEST_PATH = N2_DIR / "manifest.json"
N2_TRACE_PATH = (HOST / ".." / "network" / "network2-block-traces-ps-001" /
                 "board-ps-collection-manifest.json").resolve()
N4_TRACE_PATH = HOST / "network4-host-trace-reference-001/manifest.json"
N4_CONTRACT_PATH = HOST / "network4-host-quant-contract-001/manifest.json"
OUT = HOST / "network-w16-joint-oracle-001"


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def save_bytes(root, rel, data):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return {"path": rel.replace("\\", "/"), "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest()}


def save_array(root, rel, value, dtype):
    arr = np.ascontiguousarray(value, dtype=dtype)
    return save_bytes(root, rel, arr.tobytes(order="C")) | {
        "dtype": dtype, "shape": list(arr.shape)}


def metrics(a, b):
    x, y = np.asarray(a, dtype=np.float64).reshape(-1), np.asarray(b, dtype=np.float64).reshape(-1)
    d = x - y
    return {"cosine": float(np.dot(x, y) / max(float(np.linalg.norm(x) * np.linalg.norm(y)), 1e-300)),
            "max_abs": float(np.max(np.abs(d))), "relative_l2": float(np.linalg.norm(d) / max(float(np.linalg.norm(y)), 1e-300)),
            "rms_abs": float(np.sqrt(np.mean(d * d)))}


def make_params(layers, scales):
    names = ("dw3", "dw7", "pw1", "pw2")
    input_key = {"dw3": "input", "dw7": "dw3", "pw1": "dw7", "pw2": "gelu"}
    output_key = {"dw3": "dw3", "dw7": "dw7", "pw1": "pw1", "pw2": "pw2"}
    params, quantized = {}, {}
    for name in names:
        layer = layers[name]
        qw, ws = c16.quantize_weight_i16_per_output(layer["weight_f32"])
        in_scale = float(scales[input_key[name]])
        out_scale = float(scales[output_key[name]])
        acc_scale = ws * in_scale
        bias = np.asarray([c16.checked_i48(round(float(b) / float(s)), name + " bias")
                           for b, s in zip(layer["bias_f32"], acc_scale)], dtype=object)
        mult, shift = n2.q31_parameters(acc_scale / out_scale)
        if np.any(shift < 0) or np.any(shift > 62):
            raise ValueError(name + " has Q31 shift outside 0..62")
        bound = c16.audit_bound(qw, 32767, bias)
        params[name] = {"weights": qw, "bias": bias, "multiplier": mult, "shift": shift,
                        "accumulator_scales": acc_scale,
                        "full_range_abs_bound": bound}
        quantized[name] = qw
    scale_m, scale_s = n2.q31_parameters(
        np.asarray(layers["residual_scale"], dtype=np.float64) * float(scales["pw2"]) / float(scales["add"]), signed=True)
    residual_m, residual_s = n2.q31_parameters(
        np.asarray([float(scales["dw3"]) / float(scales["add"])], dtype=np.float64), signed=True)
    gelu = n2.gelu_lut(float(scales["pw1"]), float(scales["gelu"])).astype("<i2")
    return {"layers": params, "scale_multiplier": scale_m, "scale_shift": scale_s,
            "residual_multiplier": residual_m, "residual_shift": residual_s,
            "gelu": gelu, "quantized_weights": quantized}


def execute_block(qinput, params):
    current = np.asarray(qinput, dtype="<i2")
    stages, accum = {}, {}
    for name in ("dw3", "dw7", "pw1"):
        spec = params["layers"][name]
        raw = conv_accumulate(current, spec["weights"])
        total_obj = raw.astype(object) + spec["bias"][:, None, None]
        for v in total_obj.reshape(-1):
            if int(v) < c16.I48_MIN or int(v) > c16.I48_MAX:
                raise OverflowError(f"{name} accumulator exceeds signed48")
        total64 = np.asarray(total_obj, dtype=np.int64)
        accum[name] = {"raw_abs_peak": int(np.max(np.abs(raw))),
                       "bias_included_abs_peak": max(abs(int(v)) for v in total_obj.reshape(-1)),
                       "full_range_abs_bound": max(spec["full_range_abs_bound"])}
        current = q31_tensor_wide(total64, spec["multiplier"], spec["shift"], (-32767, 32767))
        stages[name] = current
        if name == "pw1":
            current = params["gelu"][(current.astype(np.int32) + 32768)].astype("<i2")
            stages["gelu"] = current
    spec = params["layers"]["pw2"]
    raw = conv_accumulate(current, spec["weights"])
    total_obj = raw.astype(object) + spec["bias"][:, None, None]
    for v in total_obj.reshape(-1):
        if int(v) < c16.I48_MIN or int(v) > c16.I48_MAX:
            raise OverflowError("pw2 accumulator exceeds signed48")
    total64 = np.asarray(total_obj, dtype=np.int64)
    accum["pw2"] = {"raw_abs_peak": int(np.max(np.abs(raw))),
                     "bias_included_abs_peak": max(abs(int(v)) for v in total_obj.reshape(-1)),
                     "full_range_abs_bound": max(spec["full_range_abs_bound"])}
    pw2 = q31_tensor_wide(total64, spec["multiplier"], spec["shift"], (-32767, 32767))
    scale = q31_tensor_wide(pw2, params["scale_multiplier"], params["scale_shift"])
    residual = q31_tensor_wide(stages["dw3"], params["residual_multiplier"], params["residual_shift"])
    summed = scale + residual
    add = np.empty(summed.shape, dtype="<i2")
    for j, v in enumerate(summed.reshape(-1)):
        add.reshape(-1)[j] = min(32767, max(-32767, int(v)))
    stages.update({"pw2": pw2, "scale": scale, "residual": residual, "add": add})
    return add, stages, accum


def pack_block(params, channels):
    p, w = params, params["quantized_weights"]
    parts = [w["dw3"].reshape(channels, 9).astype("<i2").tobytes(),
             w["dw7"].reshape(channels, 49).astype("<i2").tobytes(),
             np.asarray(np.concatenate([p["layers"][k]["bias"] for k in ("dw3","dw7","pw1","pw2")]), dtype="<i8").tobytes(),
             np.asarray(np.concatenate([p["layers"][k]["multiplier"] for k in ("dw3","dw7","pw1","pw2")]), dtype="<i4").tobytes(),
             np.asarray(np.concatenate([p["layers"][k]["shift"] for k in ("dw3","dw7","pw1","pw2")]), dtype="<i4").tobytes(),
             np.asarray(p["scale_multiplier"], dtype="<i4").tobytes(),
             np.asarray(p["scale_shift"], dtype="<i4").tobytes(),
             np.asarray(p["residual_multiplier"], dtype="<i4").tobytes(),
             np.asarray(p["residual_shift"], dtype="<i4").tobytes(), bytes(8),
             p["gelu"].tobytes(),
             c16.pack_pw_i16(w["pw1"].astype("<i2"), 3 * channels, channels),
             c16.pack_pw_i16(w["pw2"].astype("<i2"), channels, 3 * channels)]
    payload = b"".join(parts)
    if len(payload) != c16.expected_stride(channels):
        raise AssertionError("packed v5 block size mismatch")
    return payload


def ort_session(path):
    opts = ort.SessionOptions()
    opts.intra_op_num_threads = 1
    opts.inter_op_num_threads = 1
    opts.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    return ort.InferenceSession(str(path), opts, providers=["CPUExecutionProvider"])


def read_boundary_scales(oracle):
    scales = []
    for i in range(len(oracle["blocks"])):
        path = N2_DIR / f"block-{i:02d}" / "manifest.json"
        item = json.loads(path.read_text(encoding="utf-8"))
        scales.append(item.get("calibration_scales", item.get("boundary_scales")))
    return scales


def main():
    if OUT.exists():
        raise FileExistsError(f"refusing to overwrite {OUT}")
    source_sha = sha(MODEL)
    model = onnx.load(str(MODEL))
    if source_sha != "5b8494a03aa81a59b2bd0a3f3dcba91813363bb65060c32d6e4bf4243f8e3587":
        raise ValueError("source model hash differs from the frozen MobileCLIP-S1 ONNX")
    n2m = json.loads(N2_MANIFEST_PATH.read_text(encoding="utf-8"))
    n2trace = json.loads(N2_TRACE_PATH.read_text(encoding="utf-8"))
    n2samples = n2.load_trace_arrays(N2_TRACE_PATH, n2trace)
    n2layers = [n2.extract_block_parameters(model, spec) for spec in n2trace["blocks"]]
    n2scales = read_boundary_scales(n2m)
    n2input_scale = float(n2m["results"][0]["qinput_scale"])
    n4trace = json.loads(N4_TRACE_PATH.read_text(encoding="utf-8"))
    n4contract = json.loads(N4_CONTRACT_PATH.read_text(encoding="utf-8"))
    n4layers = [n2.extract_block_parameters(model, spec) for spec in n4trace["blocks"]]
    n4scales = [b["calibration_scales"] for b in n4contract["blocks"]]
    n2params = [make_params(l, s) for l, s in zip(n2layers, n2scales)]
    n4params = [make_params(l, s) for l, s in zip(n4layers, n4scales)]
    prefix, bridge, suffix = (ort_session(SPLITS / name) for name in
                              ("prefix.onnx", "network3-bridge.onnx", "suffix.onnx"))
    split_manifest = json.loads((SPLITS / "manifest.json").read_text(encoding="utf-8"))
    old_manifest = json.loads((OLD / "manifest.json").read_text(encoding="utf-8"))
    text_features = np.fromfile(N2_DIR / n2m["text_feature_reference"]["path"], dtype="<f4").reshape(8, 512)
    text_ids = [v["id"] for v in old_manifest["prompts"]]
    text_unit = text_features.astype(np.float64)
    text_unit /= np.maximum(np.linalg.norm(text_unit, axis=1, keepdims=True), 1e-300)
    samples_by_id = {x["sample_id"]: x for x in n2samples}
    OUT.mkdir(parents=True)
    profile_params = {"profile0": [], "profile1": []}
    results = []
    global_bounds = {"profile0": {}, "profile1": {}}

    for rec in n2m["results"]:
        sid = rec["sample_id"]
        image_path = OLD / f"{sid}-input.f32"
        image = np.fromfile(image_path, dtype="<f4").reshape(1, 3, 256, 256)
        if sha(image_path) != rec["input_sha256"]:
            raise ValueError("frozen image input SHA mismatch")
        prefix_float = prefix.run(None, {prefix.get_inputs()[0].name: image})[0]
        q = c16.quantize_symmetric_i16(prefix_float, n2input_scale)[0]
        prefix_codes = q.copy()
        n2_adds, n2_blocks = [], []
        for i, p in enumerate(n2params):
            add, stages, accum = execute_block(q, p)
            n2_adds.append(add)
            n2_blocks.append({"block": i, "accumulators": accum,
                              "output": save_array(OUT, f"{sid}/profile0/block-{i:02d}-add-chw.i16le", add, "<i2")})
            q = add
        n2_qout = q[None].astype("<i2")
        n2_add_scale = float(n2scales[-1]["add"])
        n2_deq = (n2_qout.astype(np.float32) * np.float32(n2_add_scale)).astype("<f4")
        n3 = bridge.run(None, {bridge.get_inputs()[0].name: n2_deq})[0]
        n4_q = c16.quantize_symmetric_i16(n3, float(n4scales[0]["input"]))[0]
        n4_input_codes = n4_q.copy()
        n4_blocks = []
        for i, p in enumerate(n4params):
            add, stages, accum = execute_block(n4_q, p)
            n4_blocks.append({"block": i, "accumulators": accum,
                              "output": save_array(OUT, f"{sid}/profile1/block-{i:02d}-add-chw.i16le", add, "<i2")})
            n4_q = add
        n4_deq = (n4_q[None].astype(np.float32) * np.float32(n4scales[-1]["add"])).astype("<f4")
        feature = suffix.run(None, {suffix.get_inputs()[0].name: n4_deq})[0].reshape(512).astype("<f4")
        pure = np.fromfile(OLD / f"{sid}-ort.f32", dtype="<f4").reshape(512)
        quant_ref = np.fromfile(N2_DIR / rec["reference_feature_file"]["path"], dtype="<f4").reshape(512)
        unit = feature.astype(np.float64)
        unit /= max(float(np.linalg.norm(unit)), 1e-300)
        scores = unit @ text_unit.T
        rank = [text_ids[int(i)] for i in np.argsort(-scores, kind="stable")]
        pure_u = pure.astype(np.float64) / max(float(np.linalg.norm(pure)), 1e-300)
        pure_rank = [text_ids[int(i)] for i in np.argsort(-(pure_u @ text_unit.T), kind="stable")]
        full_u = quant_ref.astype(np.float64) / max(float(np.linalg.norm(quant_ref)), 1e-300)
        full_rank = [text_ids[int(i)] for i in np.argsort(-(full_u @ text_unit.T), kind="stable")]
        result = {"sample_id": sid,
                  "frozen_image_sha256": sha(image_path),
                  "prefix_output_f32_sha256": hashlib.sha256(np.ascontiguousarray(prefix_float, dtype="<f4").tobytes()).hexdigest(),
                  "profile0_input_i16": save_array(OUT, f"{sid}/profile0/input-hcw.i16le", to_hcw(prefix_codes), "<i2"),
                  "profile0_add_scale": n2_add_scale,
                  "profile0_blocks": n2_blocks,
                  "network3_bridge_output": save_array(OUT, f"{sid}/network3-bridge-output.f32", n3, "<f4"),
                  "profile1_input_i16": save_array(OUT, f"{sid}/profile1/input-hcw.i16le", to_hcw(n4_input_codes), "<i2"),
                  "profile1_input_scale": float(n4scales[0]["input"]),
                  "profile1_blocks": n4_blocks,
                  "feature": save_array(OUT, f"{sid}/joint-int-w16-feature.f32", feature, "<f4"),
                  "pure_ps_feature_sha256": sha(OLD / f"{sid}-ort.f32"),
                  "metrics_vs_pure_ps": metrics(feature, pure),
                  "ranking": rank, "pure_ps_ranking": pure_rank,
                  "ranking_matches_pure_ps": rank == pure_rank,
                  "ranking_matches_legacy_n2_board_ps_suffix_reference": rank == full_rank,
                  "legacy_n2_board_ps_suffix_reference_ranking": full_rank}
        results.append(result)

    for p, layers in (("profile0", n2params), ("profile1", n4params)):
        c = 128 if p == "profile0" else 256
        for i, params in enumerate(layers):
            payload = pack_block(params, c)
            profile_params[p].append(save_bytes(OUT, f"params/{p}/block-{i:02d}.bin", payload))
            global_bounds[p][str(i)] = {
                op: {"full_range_abs_bound_max": max(spec["full_range_abs_bound"]),
                     "bias_abs_max": max(abs(int(x)) for x in spec["bias"]),
                     "q31_multiplier_abs_max": int(np.max(np.abs(spec["multiplier"].astype(np.int64)))),
                     "q31_shift_min": int(spec["shift"].min()), "q31_shift_max": int(spec["shift"].max())}
                for op, spec in params["layers"].items()}

    features = [np.fromfile(OUT / r["feature"]["path"], dtype="<f4") for r in results]
    manifest = {
        "schema_version": 1, "status": "HOST_REAL_FP32_SOURCE_W16_JOINT_N2_N4_ORACLE_NOT_PL",
        "claim": "N2/N4 weights freshly quantized per output from frozen FP32 ONNX; actual prefix/N2-W16/real N3 bridge/N4-W16/real suffix joint reference",
        "source_hashes": {"model_sha256": source_sha, "network2_oracle_manifest_sha256": sha(N2_MANIFEST_PATH),
                          "network2_trace_manifest_sha256": sha(N2_TRACE_PATH),
                          "network4_trace_manifest_sha256": sha(N4_TRACE_PATH),
                          "network4_contract_manifest_sha256": sha(N4_CONTRACT_PATH),
                          "runtime_split_manifest_sha256": sha(SPLITS / "manifest.json"),
                          "old_frozen_inputs_manifest_sha256": sha(OLD / "manifest.json")},
        "profiles": {"profile0": {"role": "network2", **c16.PROFILES[0],
                                    "stride_bytes": c16.expected_stride(128),
                                    "parameter_words_per_block": c16.expected_stride(128)//16,
                                    "parameter_bytes": sum(x["bytes"] for x in profile_params["profile0"]),
                                    "slot_bytes": 262144,
                                    "params": profile_params["profile0"]},
                      "profile1": {"role": "network4", **c16.PROFILES[1],
                                    "stride_bytes": c16.expected_stride(256),
                                    "parameter_words_per_block": c16.expected_stride(256)//16,
                                    "parameter_bytes": sum(x["bytes"] for x in profile_params["profile1"]),
                                    "slot_bytes": 131072,
                                    "params": profile_params["profile1"]},
                      "profile2": {"role": "network0", **c16.PROFILES[2], "stride_bytes": c16.expected_stride(64),
                                    "parameter_words_per_block": c16.expected_stride(64)//16,
                                    "parameter_bytes": c16.expected_stride(64)*4,
                                    "slot_bytes": 524288,
                                    "status": "NETWORK0_PROFILE_EVALUATED_SEPARATELY_IN_NETWORK0_W16_PREFLIGHT"}},
        "arithmetic": {"activation": "symmetric INT16 zero point zero; ties-even; clamp [-32767,32767]",
                       "weight": "FP32 ONNX per-output symmetric INT16; ties-even; clamp [-32767,32767]",
                       "bias": "round-even FP32 bias / input_scale*weight_scale; serialized i64; every code checked signed48",
                       "accumulator": "signed48 checked; explicit Python integer bias and bound checks; NumPy int64 raw conv only under proven signed48 reduction bounds",
                       "q31": "signed i32 multiplier, shift 0..62; exact Python arbitrary-precision signed product; ties-even",
                       "saturation": "clamp once after each op requantization; scale and residual branches remain wide until final Add saturation",
                       "gelu": "65536-entry signed INT16 LUT; index signed code + 32768",
                       "q31_global_allowed_product_abs_max": ((1<<47)-1)*((1<<31)-1),
                       "q31_product_signed80_limit": (1<<79),
                       "q31_global_product_fits_signed80": (((1<<47)-1)*((1<<31)-1)) < (1<<79),
                       "accumulator_bounds_by_profile_block_op": global_bounds},
        "calibration_provenance": {"network2": "frozen BOARD_PS-calibrated network2 per-block calibration manifests; HOST recomputation only",
                                   "network4": "network4-host-trace-reference-001 on exactly the three frozen inputs; HOST calibration, not BOARD_PS"},
        "joint_chain": ["real prefix.onnx", "profile0 N2 W16 integer oracle", "dequantize using frozen N2 Add scale",
                        "real network3-bridge.onnx", "profile1 N4 W16 integer oracle", "dequantize using frozen N4 Add scale", "real suffix.onnx"],
        "execution_provenance": {"host_only": True, "pl_execution": False,
                                 "runtime": "ORT CPU prefix/network3-bridge/suffix; independent wide integer N2/N4 oracle",
                                 "onnx_version": onnx.__version__, "onnxruntime_version": ort.__version__, "numpy_version": np.__version__},
        "quality_interpretation": "Three frozen engineering regressions only; report quality versus pure FP32 PS and ranking; no independent accuracy claim and no PL pass claim.",
        "results": results,
        "checks": {"profile0_12_blocks": all(len(r["profile0_blocks"]) == 12 for r in results),
                   "profile1_20_blocks": all(len(r["profile1_blocks"]) == 20 for r in results),
                   "all_signed48_full_range_bounds_fit": all(
                       op["full_range_abs_bound_max"] <= (1 << 47)-1
                       for profile in global_bounds.values() for block in profile.values() for op in block.values()),
                   "q31_wide_product_fits_signed80": (((1<<47)-1)*((1<<31)-1)) < (1<<79),
                   "three_images": len(results) == 3,
                   "board_or_pl_execution": False},
    }
    manifest["files"] = {p.relative_to(OUT).as_posix(): {"bytes": p.stat().st_size, "sha256": sha(p)}
                         for p in sorted(OUT.rglob("*")) if p.is_file() and p.name != "manifest.json"}
    path = OUT / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"manifest": str(path), "manifest_sha256": sha(path),
                      "results": [{"sample_id": r["sample_id"], "metrics_vs_pure_ps": r["metrics_vs_pure_ps"],
                                   "ranking_matches_pure_ps": r["ranking_matches_pure_ps"]} for r in results]}, indent=2))


if __name__ == "__main__":
    main()
