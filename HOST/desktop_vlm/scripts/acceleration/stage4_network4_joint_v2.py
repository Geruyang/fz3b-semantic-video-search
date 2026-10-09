"""Diagnose network4 integer error and build a bounded HOST-only V2 candidate.

This reuses the frozen V1 scales and INT16/INT8/Q31/GELU contract. V2 searches
per-output-channel INT8 clipping ratios against weight reconstruction MSE, then
tests a mathematically motivated per-channel mean-output-error bias correction.
It never changes the on-wire tensor shapes, dtypes, order, or HLS/driver code.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import onnx
import onnxruntime as ort

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_network2_int_oracle as n2
import stage4_network4_int_oracle as n4

HOST = ROOT / "artifacts/board-debug-20261005/acceleration/host"
SOURCE_MODEL = ROOT / "artifacts/board-debug-20261004/host/s1-onnx-001/mobileclip_s1_image.onnx"
V1 = HOST / "v4-joint-feature-preflight-001"
N4_TRACE = HOST / "network4-host-trace-reference-001/manifest.json"
N4_CONTRACT = HOST / "network4-host-quant-contract-001/manifest.json"
SPLITS = HOST / "v4-runtime-models-001"
N2_MANIFEST = HOST / "network2-int-oracle-board-ps-001/manifest.json"
OLD = ROOT / "artifacts/board-debug-20261004/host/s1-onnx-001"
V2_SPLITS = (0.70, 0.74, 0.78, 0.82, 0.86, 0.90, 0.93, 0.96, 0.98, 1.00)
OPS = ("dw3", "dw7", "pw1", "pw2")
STAGES = ("dw3", "dw7", "pw1", "gelu", "pw2", "scale", "add")


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def metrics(actual, expected):
    a = np.asarray(actual, dtype=np.float64).reshape(-1)
    b = np.asarray(expected, dtype=np.float64).reshape(-1)
    d = a - b
    bn, an = float(np.linalg.norm(b)), float(np.linalg.norm(a))
    return {"max_abs": float(np.max(np.abs(d))), "rms_abs": float(np.sqrt(np.mean(d * d))),
            "relative_l2": float(np.linalg.norm(d) / max(bn, 1e-300)),
            "cosine": float(np.dot(a, b) / max(an * bn, 1e-300))}


def tobytes_sha(arr, dtype):
    return hashlib.sha256(np.ascontiguousarray(arr, dtype=dtype).tobytes()).hexdigest()


def save_array(root, rel, arr, dtype):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    a = np.ascontiguousarray(arr, dtype=dtype)
    a.tofile(p)
    return {"path": rel.replace("\\", "/"), "dtype": dtype, "shape": list(a.shape),
            "bytes": p.stat().st_size, "sha256": sha(p)}


def make_cut_sessions(model, n4_trace):
    """Create bounded ORT references for original network4 boundaries and Conv."""
    so = ort.SessionOptions()
    so.intra_op_num_threads = 1
    so.inter_op_num_threads = 1
    so.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    boundary_sessions = []
    chunk_blocks = 5
    for start in range(0, len(n4_trace["blocks"]), chunk_blocks):
        stop = min(start + chunk_blocks, len(n4_trace["blocks"]))
        chunk = n4_trace["blocks"][start:stop]
        outputs = [b["outputs"][key] for b in chunk for key in STAGES]
        cut = onnx.utils.Extractor(model).extract_model([chunk[0]["input"]], outputs)
        onnx.checker.check_model(cut)
        boundary_sessions.append(onnxruntime_session(cut, so))
    node_by_name = {node.name: node for node in model.graph.node}
    conv_inputs, conv_outputs, conv_map = [], [], {}
    for bi, block in enumerate(n4_trace["blocks"]):
        for op in OPS:
            node = node_by_name[block["nodes"][op]]
            conv_inputs.append(node.input[0])
            conv_outputs.append(node.output[0])
            conv_map[(bi, op)] = {"input": node.input[0], "output": node.output[0]}
    if len(set(conv_inputs)) != len(conv_inputs) or len(set(conv_outputs)) != len(conv_outputs):
        raise ValueError("unexpected duplicate Conv tensor boundary")
    conv_cut = onnx.utils.Extractor(model).extract_model(conv_inputs, conv_outputs)
    onnx.checker.check_model(conv_cut)
    conv_session = onnxruntime_session(conv_cut, so)
    return boundary_sessions, conv_session, conv_map


def onnxruntime_session(model, so):
    return ort.InferenceSession(model.SerializeToString(), so,
                                providers=["CPUExecutionProvider"])


def clip_search(layers, selected_ops=OPS):
    """Per-channel bounded clipping search minimizing INT8 weight MSE."""
    summary, ratios_by_op = {}, {}
    for op in selected_ops:
        layer = layers[op]
        weight = np.asarray(layer["weight_f32"], dtype=np.float64)
        flat = weight.reshape(weight.shape[0], -1)
        maxima = np.max(np.abs(flat), axis=1)
        q = np.empty_like(flat, dtype=np.int8)
        scales = np.ones((flat.shape[0],), dtype=np.float64)
        chosen = np.ones((flat.shape[0],), dtype=np.float64)
        before = np.zeros((flat.shape[0],), dtype=np.float64)
        after = np.zeros((flat.shape[0],), dtype=np.float64)
        for oc, row in enumerate(flat):
            mx = float(maxima[oc])
            if mx == 0.0:
                q[oc] = 0
                before[oc] = after[oc] = 0.0
                continue
            base_scale = mx / 127.0
            base_q = np.clip(np.rint(row / base_scale), -127, 127)
            before[oc] = float(np.mean((base_q * base_scale - row) ** 2))
            best_mse, best_ratio, best_scale, best_q = before[oc], 1.0, base_scale, base_q
            for ratio in V2_SPLITS[:-1]:
                candidate_scale = mx * ratio / 127.0
                candidate_q = np.clip(np.rint(row / candidate_scale), -127, 127)
                mse = float(np.mean((candidate_q * candidate_scale - row) ** 2))
                if mse < best_mse:
                    best_mse, best_ratio, best_scale, best_q = mse, ratio, candidate_scale, candidate_q
            q[oc] = best_q.astype(np.int8)
            scales[oc] = best_scale
            chosen[oc] = best_ratio
            after[oc] = best_mse
        layer["weight_i8"] = q.reshape(weight.shape)
        layer["weight_scales"] = scales
        ratios_by_op[op] = chosen
        summary[op] = {"channels": int(len(chosen)), "searched_clipping_ratio_grid": list(V2_SPLITS),
                       "changed_channel_count": int(np.count_nonzero(chosen < 1.0)),
                       "ratio_min": float(chosen.min()), "ratio_max": float(chosen.max()),
                       "weight_mse_before_sum": float(before.sum()),
                       "weight_mse_after_sum": float(after.sum()),
                       "weight_mse_reduction_fraction": float(1.0 - after.sum() / max(before.sum(), 1e-300))}
    return summary, ratios_by_op


def make_params(layers_by_block, scales_by_block):
    paired = [n4.block_parameters(layers, scales)
              for layers, scales in zip(layers_by_block, scales_by_block)]
    return [p for p, _ in paired], [a for _, a in paired]


def quantized_forward(n3_outputs, layers_by_block, scales_by_block, params_by_block,
                      arrays_by_block, collect_inputs=False):
    cases = []
    for sid, n3 in n3_outputs.items():
        q = n2.quantize_symmetric(n3, scales_by_block[0]["input"], 16)[0]
        blocks = []
        for bi, (layers, scales, params, arrays) in enumerate(zip(
                layers_by_block, scales_by_block, params_by_block, arrays_by_block)):
            qin = q.copy()
            qadd, stages = n2.execute_block(q, params, scales, layers, arrays["gelu_lut_i16"])
            qpw2 = n2.requantize_q31(stages["pw2_acc_bias_included"],
                                     params["pw2"]["multiplier_i32"], params["pw2"]["shift_i32"])
            activation = {"input": qin, "dw3": stages["dw3"], "dw7": stages["dw7"],
                          "pw1": stages["pw1"], "gelu": stages["gelu"], "pw2": qpw2,
                          "scale": stages["scale"], "add": qadd}
            op_inputs = {"dw3": (qin, scales["input"]),
                         "dw7": (stages["dw3"], scales["dw3"]),
                         "pw1": (stages["dw7"], scales["dw7"]),
                         "pw2": (stages["gelu"], scales["gelu"])}
            saturation = {}
            for stage in ("dw3", "dw7", "pw1", "gelu", "pw2", "add"):
                val = activation[stage]
                saturation[stage] = int(np.count_nonzero(np.abs(val.astype(np.int32)) == 32767))
            blocks.append({"activations": activation, "conv_inputs": op_inputs,
                           "saturation_count": saturation,
                           "scale_branch": stages["scale"], "residual_branch": stages["residual"],
                           "accumulators": stages["accumulators"]})
            q = qadd
        final = (q[None].astype(np.float32) * np.float32(scales_by_block[-1]["add"])).astype(np.float32)
        cases.append({"sample_id": sid, "blocks": blocks, "final_add": q.copy(),
                      "final_dequant": final})
    return cases


def collect_float_conv_outputs(session, conv_map, n3_inputs, cases, scales_by_block):
    refs = {}
    previous_raw = None
    lifetime = []
    for case in cases:
        feeds = {}
        for bi, block in enumerate(case["blocks"]):
            for op, (codes, scale) in block["conv_inputs"].items():
                feeds[conv_map[(bi, op)]["input"]] = (codes[None].astype(np.float32) * np.float32(scale)).astype(np.float32)
        outputs = session.run(None, feeds)
        if previous_raw is not None:
            prior_name, prior_value, prior_sha = previous_raw
            after_sha = tobytes_sha(prior_value, prior_value.dtype)
            lifetime.append({"next_run_sample": case["sample_id"], "prior_output": prior_name,
                             "prior_sha256_before_next_run": prior_sha,
                             "prior_sha256_after_next_run": after_sha,
                             "prior_still_finite_after_next_run": bool(np.isfinite(prior_value).all()),
                             "prior_changed_after_next_run": prior_sha != after_sha,
                             "no_local_math_applied_to_prior_output": True})
        names = [o.name for o in session.get_outputs()]
        # Detach ORT-owned output buffers before issuing the next Run; some
        # optimized kernels recycle backing storage for large multi-output cuts.
        item = {name: np.array(value, copy=True) for name, value in zip(names, outputs)}
        bad = [name for name, value in item.items() if not np.isfinite(value).all()]
        if bad:
            raise ValueError(f"nonfinite isolated FP32 Conv outputs for {case['sample_id']}: {bad[:5]}")
        refs[case["sample_id"]] = item
        first_name = names[0]
        first_value = outputs[0]
        previous_raw = (first_name, first_value,
                        hashlib.sha256(np.ascontiguousarray(first_value).tobytes()).hexdigest())
    return refs, lifetime


def calibrate_bias_correction(cases, float_conv, conv_map, layers_by_block,
                              scales_by_block, params_by_block):
    """Mean local float-minus-quantized output error, mapped to raw bias units."""
    corrections = [[{} for _ in OPS] for _ in range(20)]
    correction_summary = []
    for bi in range(20):
        by_op = {}
        for op in OPS:
            layer = layers_by_block[bi][op]
            out_scale = float(scales_by_block[bi][{"dw3":"dw3","dw7":"dw7","pw1":"pw1","pw2":"pw2"}[op]])
            acc_scale = np.asarray(params_by_block[bi][op]["accumulator_scales"], dtype=np.float64)
            qsum = np.zeros(layer["weight_f32"].shape[0], dtype=np.float64)
            count = 0
            for case in cases:
                b = case["blocks"][bi]
                if op == "dw3": qout = b["activations"]["dw3"]
                elif op == "dw7": qout = b["activations"]["dw7"]
                elif op == "pw1": qout = b["activations"]["pw1"]
                else: qout = b["activations"]["pw2"]
                target = float_conv[case["sample_id"]][conv_map[(bi, op)]["output"]][0]
                if not np.isfinite(target).all():
                    raise ValueError(f"nonfinite local float target at {case['sample_id']} block {bi} {op}")
                err = target.astype(np.float64) / out_scale - qout.astype(np.float64)
                qsum += np.sum(err, axis=(1, 2))
                count += int(err.shape[1] * err.shape[2])
            mean_code_error = qsum / max(count, 1)
            # Q31 maps one accumulator unit by acc_scale/out_scale. Bias lives in accumulator units.
            delta = np.rint(mean_code_error * out_scale / acc_scale).astype(np.int64)
            bias = params_by_block[bi][op]["bias_i32"].astype(np.int64)
            if np.any(bias + delta < np.iinfo(np.int32).min) or np.any(bias + delta > np.iinfo(np.int32).max):
                raise OverflowError(f"bias correction exceeds INT32 at block {bi} {op}")
            corrections[bi][OPS.index(op)] = delta.astype(np.int32)
            by_op[op] = {"channel_count": int(len(delta)), "sample_positions": count,
                         "nonzero_channel_count": int(np.count_nonzero(delta)),
                         "max_abs_delta_accumulator": int(np.max(np.abs(delta))) if len(delta) else 0,
                         "mean_abs_pre_correction_code_error": float(np.mean(np.abs(mean_code_error))),
                         "rationale": "least-squares constant bias correction: channelwise empirical mean Conv output residual over actual joint runtime inputs; converted through accumulator/output scale ratio and ties-even-rounded"}
        correction_summary.append({"block_index": bi, "ops": by_op})
    return corrections, correction_summary


def apply_bias_corrections(params_by_block, corrections):
    import copy
    updated = copy.deepcopy(params_by_block)
    for bi in range(20):
        for oi, op in enumerate(OPS):
            updated[bi][op]["bias_i32"] = (updated[bi][op]["bias_i32"].astype(np.int64) +
                                               corrections[bi][oi].astype(np.int64)).astype(np.int32)
    return updated


def compare_boundaries(cases, boundary_sessions, n4_trace, scales_by_block):
    compared = {}
    for case in cases:
        per_block = []
        max_growth = (None, -1.0)
        prior_rel = 0.0
        cut_input = case["n3_input"]
        for chunk_index, session in enumerate(boundary_sessions):
            start, stop = chunk_index * 5, min((chunk_index + 1) * 5, 20)
            ref = session.run(None, {session.get_inputs()[0].name: cut_input})
            ref_by_name = dict(zip([o.name for o in session.get_outputs()], ref))
            for bi in range(start, stop):
                b = case["blocks"][bi]
                per_stage = {}
                for label in STAGES:
                    qcodes = b["activations"][label]
                    if label == "scale":
                        qcodes = b["scale_branch"]
                    qdeq = qcodes.astype(np.float32) * np.float32(scales_by_block[bi]["add" if label == "scale" else label])
                    target = ref_by_name[n4_trace["blocks"][bi]["outputs"][label]][0]
                    m = metrics(qdeq, target)
                    m["saturation_count"] = b["saturation_count"].get(label, 0)
                    per_stage[label] = m
                    growth = m["relative_l2"] - prior_rel
                    if growth > max_growth[1]:
                        max_growth = ((bi, label), growth)
                    prior_rel = m["relative_l2"]
                per_block.append({"block_index": bi, "stages": per_stage})
            cut_input = ref_by_name[n4_trace["blocks"][stop - 1]["outputs"]["add"]]
        all_stages = [(bi, op, item["stages"][op]["relative_l2"])
                      for bi, item in enumerate(per_block) for op in STAGES]
        first_worst = max(all_stages, key=lambda x: x[2])
        compared[case["sample_id"]] = {"blocks": per_block,
                                        "largest_adjacent_relative_l2_increase": {"block": max_growth[0][0],
                                                                                  "stage": max_growth[0][1],
                                                                                  "increase": max_growth[1]},
                                        "largest_absolute_relative_l2": {"block": first_worst[0],
                                                                         "stage": first_worst[1],
                                                                         "value": first_worst[2]}}
    return compared


def evaluate_features(cases, suffix_session, text, text_ids, pure_refs):
    records = []
    text = text.astype(np.float64)
    text /= np.maximum(np.linalg.norm(text, axis=1, keepdims=True), 1e-300)
    for case in cases:
        feat = suffix_session.run(None, {suffix_session.get_inputs()[0].name: case["final_dequant"]})[0].reshape(512).astype(np.float32)
        fp = pure_refs[case["sample_id"]]
        fv = feat.astype(np.float64)
        fv /= max(float(np.linalg.norm(fv)), 1e-300)
        pv = fp.astype(np.float64)
        pv /= max(float(np.linalg.norm(pv)), 1e-300)
        js, ps = fv @ text.T, pv @ text.T
        jo, po = np.argsort(-js, kind="stable"), np.argsort(-ps, kind="stable")
        records.append({"sample_id": case["sample_id"], "feature": feat,
                        "metrics_vs_pure_ps": metrics(feat, fp),
                        "ranking_joint": [text_ids[int(i)] for i in jo],
                        "ranking_pure_ps": [text_ids[int(i)] for i in po],
                        "full_order_matches": bool(np.array_equal(jo, po)),
                        "scores_joint": {text_ids[i]: float(js[i]) for i in range(len(text_ids))},
                        "scores_pure_ps": {text_ids[i]: float(ps[i]) for i in range(len(text_ids))}})
    return records


def evaluate_n19ps(cases, source_model, trace, scales, suffix_session, text, text_ids, pure_refs):
    """First 19 V1 integer blocks, then original FP32 block19 and suffix."""
    block19_model = onnx.load(str(source_model))
    input_name = trace["blocks"][19]["input"]
    output_name = trace["blocks"][19]["outputs"]["add"]
    cut = onnx.utils.Extractor(block19_model).extract_model([input_name], [output_name])
    onnx.checker.check_model(cut)
    options = ort.SessionOptions()
    options.intra_op_num_threads = 1
    options.inter_op_num_threads = 1
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    block19 = ort.InferenceSession(cut.SerializeToString(), options, providers=["CPUExecutionProvider"])
    text = text.astype(np.float64)
    text /= np.maximum(np.linalg.norm(text, axis=1, keepdims=True), 1e-300)
    out = []
    for case in cases:
        q18 = case["blocks"][18]["activations"]["add"]
        x18 = (q18[None].astype(np.float32) * np.float32(scales[18]["add"])).astype(np.float32)
        fp19_add = block19.run(None, {block19.get_inputs()[0].name: x18})[0]
        final = suffix_session.run(None, {suffix_session.get_inputs()[0].name: fp19_add})[0].reshape(512).astype(np.float32)
        ref = pure_refs[case["sample_id"]]
        fv = final.astype(np.float64); fv /= max(float(np.linalg.norm(fv)), 1e-300)
        pv = ref.astype(np.float64); pv /= max(float(np.linalg.norm(pv)), 1e-300)
        fs, ps = fv @ text.T, pv @ text.T
        fo, po = np.argsort(-fs, kind="stable"), np.argsort(-ps, kind="stable")
        out.append({"sample_id": case["sample_id"], "feature": final,
                    "metrics_vs_pure_ps": metrics(final, ref),
                    "ranking_joint": [text_ids[int(i)] for i in fo],
                    "ranking_pure_ps": [text_ids[int(i)] for i in po],
                    "full_order_matches": bool(np.array_equal(fo, po)),
                    "scores_joint": {text_ids[i]: float(fs[i]) for i in range(len(text_ids))},
                    "scores_pure_ps": {text_ids[i]: float(ps[i]) for i in range(len(text_ids))},
                    "block18_add_codes_sha256": tobytes_sha(q18, "<i2"),
                    "network4_block19_fp32_add_sha256": tobytes_sha(fp19_add, "<f4")})
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()
    out = args.output.resolve()
    if (out / "manifest.json").exists():
        raise FileExistsError(f"refusing existing V2 artifact: {out}")
    out.mkdir(parents=True, exist_ok=True)
    v1_manifest_path = V1 / "manifest.json"
    v1 = json.loads(v1_manifest_path.read_text(encoding="utf-8"))
    trace = json.loads(N4_TRACE.read_text(encoding="utf-8"))
    contract = json.loads(N4_CONTRACT.read_text(encoding="utf-8"))
    n2m = json.loads(N2_MANIFEST.read_text(encoding="utf-8"))
    if v1["status"] != "HOST_JOINT_INT_FEATURE_PREFLIGHT_NOT_BOARD_NOT_PL":
        raise ValueError("V1 joint HOST reference/provenance mismatch")
    if sha(SOURCE_MODEL) != contract["source_model_sha256"]:
        raise ValueError("frozen original ONNX SHA mismatch")

    model = onnx.load(str(SOURCE_MODEL))
    print("stage: split ONNX boundary sessions", flush=True)
    boundary_sessions, conv_session, conv_map = make_cut_sessions(model, trace)
    print("stage: cut sessions ready", flush=True)
    blocks = trace["blocks"]
    if len(blocks) != 20:
        raise ValueError("expected exactly 20 network4 blocks")
    scales = [b["calibration_scales"] for b in contract["blocks"]]
    layers_orig = [n2.extract_block_parameters(model, b) for b in blocks]
    params_orig, arrays_orig = make_params(layers_orig, scales)

    n3_inputs = {}
    frozen_inputs = {}
    old_pure = {}
    for sample in v1["samples"]:
        sid = sample["sample_id"]
        n3_meta = sample["network3_bridge"]["output_sha256"]
        n3_path = V1 / "intermediates" / sid / "n3-output.f32"
        if sha(n3_path) != n3_meta:
            raise ValueError(f"V1 real-runtime N3 output SHA mismatch {sid}")
        n3_inputs[sid] = np.fromfile(n3_path, dtype="<f4").reshape(1,256,16,16)
        old_pure[sid] = np.fromfile(OLD / f"{sid}-ort.f32", dtype="<f4").reshape(512)
        image_path = OLD / f"{sid}-input.f32"
        frozen_inputs[sid] = {"path": str(image_path.relative_to(ROOT)).replace("\\", "/"), "sha256": sha(image_path)}

    # Original ONNX network4 boundaries are generated from the exact joint-run
    # N3 tensors, not from the old standalone network4 trace inputs.
    # Build actual V1 joint INT cases from saved bridge input; all 3 cases passed
    # through the same prefix->network2 oracle->N3 chain in artifact V1.
    def cases_for(layers, params, arrays):
        cases = quantized_forward(n3_inputs, layers, scales, params, arrays)
        for case in cases:
            case["n3_input"] = n3_inputs[case["sample_id"]]
        return cases

    v1_cases = cases_for(layers_orig, params_orig, arrays_orig)
    print("stage: V1 integer forward", flush=True)
    diag_v1 = compare_boundaries(v1_cases, boundary_sessions, trace, scales)
    print("stage: V1 boundary metrics ready", flush=True)
    outputs_v1 = evaluate_features(v1_cases, load_suffix(),
                                   np.fromfile(HOST / "network2-int-oracle-board-ps-001" / n2m["text_feature_reference"]["path"], dtype="<f4").reshape(8,512),
                                   [p["id"] for p in json.loads((OLD / "manifest.json").read_text(encoding="utf-8"))["prompts"]], old_pure)
    (out / "v1-diagnostic-progress.json").write_text(json.dumps({"boundary_metrics": diag_v1,
        "features": [{k:v for k,v in x.items() if k!="feature"} for x in outputs_v1]},
        indent=2, sort_keys=True) + "\n", encoding="utf-8")
    text_features = np.fromfile(HOST / "network2-int-oracle-board-ps-001" / n2m["text_feature_reference"]["path"], dtype="<f4").reshape(8,512)
    text_ids = [p["id"] for p in json.loads((OLD / "manifest.json").read_text(encoding="utf-8"))["prompts"]]
    suffix = load_suffix()
    print("stage: n19 INT + block19/suffix FP32 candidate", flush=True)
    n19ps_outputs = evaluate_n19ps(v1_cases, SOURCE_MODEL, trace, scales, suffix,
                                   text_features, text_ids, old_pure)

    clipping_summary = []
    layers_v2 = []
    for block_layers in layers_orig:
        # Preserve the original extraction for the V1 run; V2 owns new copies.
        copied = {k: ({kk: (vv.copy() if isinstance(vv, np.ndarray) else vv) for kk, vv in v.items()}
                      if isinstance(v, dict) else v.copy() if isinstance(v, np.ndarray) else v)
                  for k, v in block_layers.items()}
        summary, ratios = clip_search(copied)
        clipping_summary.append({"per_op": summary, "ratio_arrays": ratios})
        layers_v2.append(copied)
    print("stage: bounded per-channel clipping search ready", flush=True)
    target_layers = []
    for block_layers in layers_orig:
        copied = {k: ({kk: (vv.copy() if isinstance(vv, np.ndarray) else vv) for kk, vv in v.items()}
                      if isinstance(v, dict) else v.copy() if isinstance(v, np.ndarray) else v)
                  for k, v in block_layers.items()}
        target_layers.append(copied)
    targeted_dw7_summary, targeted_dw7_ratios = clip_search(target_layers[19], selected_ops=("dw7",))
    target_params, target_arrays = make_params(target_layers, scales)
    target_cases = cases_for(target_layers, target_params, target_arrays)
    outputs_targeted = evaluate_features(target_cases, suffix, text_features, text_ids, old_pure)
    print("stage: block19 DW7-only clipping candidate ready", flush=True)
    params_v2a, arrays_v2a = make_params(layers_v2, scales)
    cases_v2a = cases_for(layers_v2, params_v2a, arrays_v2a)
    conv_refs_v2a, conv_output_lifetime = collect_float_conv_outputs(conv_session, conv_map, n3_inputs, cases_v2a, scales)
    print("stage: isolated Conv targets ready", flush=True)

    # Save local op outputs from the int path for unbiased correction calculus.
    correction_tables, correction_report = calibrate_bias_correction(
        cases_v2a, conv_refs_v2a, conv_map, layers_v2, scales, params_v2a)
    params_v2b = apply_bias_corrections(params_v2a, correction_tables)
    # Re-running produces the new accumulated means; the fixed correction is not iterated.
    cases_v2b = cases_for(layers_v2, params_v2b, arrays_v2a)
    diag_v2 = compare_boundaries(cases_v2b, boundary_sessions, trace, scales)
    outputs_v2a = evaluate_features(cases_v2a, suffix, text_features, text_ids, old_pure)
    outputs_v2b = evaluate_features(cases_v2b, suffix, text_features, text_ids, old_pure)

    # Select B only if it is no worse than A on total relative L2 and ranking hold;
    # otherwise retain the best candidate using ranking-count then mean rel-L2.
    def score(records):
        return (sum(bool(x["full_order_matches"]) for x in records),
                -float(np.mean([x["metrics_vs_pure_ps"]["relative_l2"] for x in records])))
    full_candidates = {"clip_plus_bias_correction": outputs_v2b,
                       "clip_only": outputs_v2a,
                       "block19_dw7_clip_only": outputs_targeted}
    selected = max(full_candidates, key=lambda name: score(full_candidates[name]))
    if selected == "clip_plus_bias_correction":
        sel_cases, sel_params, sel_arrays, sel_outputs = cases_v2b, params_v2b, arrays_v2a, outputs_v2b
    elif selected == "clip_only":
        sel_cases, sel_params, sel_arrays, sel_outputs = cases_v2a, params_v2a, arrays_v2a, outputs_v2a
    else:
        sel_cases, sel_params, sel_arrays, sel_outputs = target_cases, target_params, target_arrays, outputs_targeted

    out.mkdir(parents=True, exist_ok=True)
    parameter_records = []
    for bi, (layers, scales_i, params_i, arrays_i) in enumerate(zip(layers_v2, scales, sel_params, sel_arrays)):
        block_files = {}
        for op in OPS:
            for key, arr in arrays_i[op].items():
                if key == "bias_i32":
                    arr = params_i[op]["bias_i32"]
                elif key == "multiplier_i32":
                    arr = params_i[op]["multiplier_i32"]
                elif key == "shift_i32":
                    arr = params_i[op]["shift_i32"]
                dtype = "|i1" if key == "weights_i8" else "<f8" if key.endswith("f64") else "<i4"
                name = f"params/block-{bi:02d}/{op}-{key}.bin"
                block_files[name] = save_array(out, name, arr, dtype)
            correction = correction_tables[bi][OPS.index(op)] if selected == "clip_plus_bias_correction" else np.zeros_like(params_i[op]["bias_i32"])
            cname = f"params/block-{bi:02d}/{op}-bias-correction-i32.bin"
            block_files[cname] = save_array(out, cname, correction, "<i4")
        for key in ("layer_scale_f32", "scale_multiplier_i32", "scale_shift_i32",
                    "residual_multiplier_i32", "residual_shift_i32", "gelu_lut_i16", "activation_scales_f64"):
            arr = arrays_i[key]
            dtype = "<f4" if key.endswith("f32") else "<i2" if key.endswith("i16") else "<f8" if key.endswith("f64") else "<i4"
            name = f"params/block-{bi:02d}/{key}.bin"
            block_files[name] = save_array(out, name, arr, dtype)
        parameter_records.append({"block_index": bi, "channel_counts": {op: int(len(layers[op]["weight_scales"])) for op in OPS},
                                  "files": block_files,
                                  "weight_scale_clip_search": clipping_summary[bi]["per_op"],
                                  "same_tensor_order_dtypes_shapes_as_v1": True,
                                  "calibration_scales_unchanged": {k: float(v) for k,v in scales_i.items()}})

    n19ps_index = {r["sample_id"]: r for r in n19ps_outputs}
    sample_records = []
    for case, result in zip(sel_cases, sel_outputs):
        sid = case["sample_id"]
        fixture_entries = {}
        for bi, block in enumerate(case["blocks"]):
            a = block["activations"]
            vals = {"input": (a["input"], "<i2"), "dw3": (a["dw3"], "<i2"),
                    "dw7": (a["dw7"], "<i2"), "pw1": (a["pw1"], "<i2"),
                    "gelu": (a["gelu"], "<i2"), "pw2": (a["pw2"], "<i2"),
                    "scale-branch": (block["scale_branch"], "<i8"),
                    "residual-branch": (block["residual_branch"], "<i8"), "add": (a["add"], "<i2")}
            for label, (arr, dtype) in vals.items():
                rel = f"fixtures/{sid}/block-{bi:02d}-{label}.bin"
                fixture_entries[rel] = save_array(out, rel, arr, dtype)
        fm = save_array(out, f"joint-int-reference/{sid}-feature.f32", result["feature"], "<f4")
        n19ps = n19ps_index[sid]
        n19ps_feature = save_array(out, f"candidate-n19ps/{sid}-feature.f32", n19ps["feature"], "<f4")
        n19ps_fixtures = {}
        for bi in range(19):
            rel = f"fixtures-n19ps/{sid}/block-{bi:02d}-add.i16"
            n19ps_fixtures[rel] = save_array(out, rel, v1_cases[[x["sample_id"] for x in v1_cases].index(sid)]["blocks"][bi]["activations"]["add"], "<i2")
        sample_records.append({"sample_id": sid, "source_n3_sha256": sha(V1 / "intermediates" / sid / "n3-output.f32"),
                              "fixture_files": fixture_entries, "joint_int_feature": fm,
                              "n19_int_plus_block19_ps_candidate": {"feature": n19ps_feature,
                                  "metrics_vs_pure_ps": n19ps["metrics_vs_pure_ps"],
                                  "ranking_joint": n19ps["ranking_joint"], "ranking_pure_ps": n19ps["ranking_pure_ps"],
                                  "full_order_matches": n19ps["full_order_matches"],
                                  "block18_add_codes_sha256": n19ps["block18_add_codes_sha256"],
                                  "network4_block19_fp32_add_sha256": n19ps["network4_block19_fp32_add_sha256"],
                                  "int_block_add_fixtures": n19ps_fixtures},
                              "joint_vs_pure_ps": result["metrics_vs_pure_ps"],
                              "ranking_joint": result["ranking_joint"], "ranking_pure_ps": result["ranking_pure_ps"],
                              "full_order_matches": result["full_order_matches"],
                              "scores_joint": result["scores_joint"], "scores_pure_ps": result["scores_pure_ps"]})

    report = {
        "schema_version": 1, "status": "HOST_JOINT_INT_V2_CANDIDATE_NOT_BOARD_NOT_PL",
        "provenance": {"host_only": True, "pl_execution": False,
                       "v1_joint_manifest_sha256": sha(v1_manifest_path),
                       "source_model_sha256": sha(SOURCE_MODEL), "network4_trace_manifest_sha256": sha(N4_TRACE),
                       "network4_v1_contract_manifest_sha256": sha(N4_CONTRACT),
                       "runtime_split_manifest_sha256": sha(SPLITS / "manifest.json"),
                       "network2_oracle_manifest_sha256": sha(N2_MANIFEST),
                       "actual_runtime_n3_outputs_reused_and_sha_verified": True,
                       "pure_ps_reference": "original frozen whole-model ORT features image-00..02"},
        "unchanged_quant_contract": {"activation": "signed INT16 symmetric zero-point 0 ties-even clip [-32767,32767]",
                                     "weight": "signed INT8 per-output-channel symmetric zero-point 0 ties-even clip [-127,127]",
                                     "q31": "signed Q31 nearest ties-even", "gelu": "frozen 65536-entry V1 LUT per block",
                                     "saturation": "existing INT16 output saturation", "block_count": 20,
                                     "scales_frozen_from_v1": True, "tensor_shapes_dtypes_order_unchanged": True},
        "diagnosis": {"scope": "actual joint prefix->network2 INT->network3 bridge output fed to original network4 FP32 ONNX and V1 INT oracle",
                      "boundary_metrics_vs_original_network4_float_run_from_same_joint_n3_input": diag_v1,
                      "v1_feature_metrics": [{k:v for k,v in x.items() if k!="feature"} for x in outputs_v1],
                      "interpretation": "reports measured stagewise error and largest adjacent relative-L2 rise; no arbitrary per-layer pass threshold"},
        "weight_clipping_search": {"objective": "minimize per-output-channel weight reconstruction MSE; bounded ratios include unchanged 1.0 baseline",
                                   "candidate_ratios": list(V2_SPLITS), "per_block": [x["per_op"] for x in clipping_summary]},
        "bias_correction": {"method": "mean local FP32 Conv output minus INT Conv output residual, using exact joint-runtime upstream INT activation codes dequantized at frozen scales; divide by accumulator scale, ties-even round, add to INT32 bias",
                            "one_pass_only": True, "per_block": correction_report,
                            "ort_output_buffer_lifetime_probe": conv_output_lifetime,
                            "probe_interpretation": "raw first Conv output retained across next Run; hash+finite checked without any in-place arithmetic. Copy is retained defensively; buffer reuse remains a hypothesis unless changed_after_next_run is true."},
        "candidate_comparison": {"clip_only": [{k:v for k,v in x.items() if k!="feature"} for x in outputs_v2a],
                                 "clip_plus_bias_correction": [{k:v for k,v in x.items() if k!="feature"} for x in outputs_v2b],
                                 "block19_dw7_clip_only": [{k:v for k,v in x.items() if k!="feature"} for x in outputs_targeted],
                                 "block19_dw7_only_weight_mse_search": targeted_dw7_summary,
                                 "block19_dw7_selected_clip_ratio_counts": {str(float(r)): int(np.count_nonzero(targeted_dw7_ratios["dw7"] == r)) for r in sorted(set(targeted_dw7_ratios["dw7"].tolist()))},
                                 "n19_int_plus_block19_ps": [{k:v for k,v in x.items() if k!="feature"} for x in n19ps_outputs],
                                 "selected": selected,
                                 "selection_rule": "among all-20-block candidates, maximize count of full ranking retentions, then minimize mean relative-L2; n19+PS is a separate partition candidate"},
        "parameters": parameter_records, "samples": sample_records,
        "strict_acceptance": {"HOST_vs_FP32": "reported only; no arbitrary numeric threshold; ranking hold is reported",
                              "future_BOARD_PL_vs_this_v2_joint_INT_reference": "max_abs<=1e-6 and cosine>=0.99999"},
    }
    report["generated_files"] = {}
    for path in sorted(p for p in out.rglob("*") if p.is_file()):
        report["generated_files"][path.relative_to(out).as_posix()] = {"bytes": path.stat().st_size, "sha256": sha(path)}
    (out / "manifest.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(out), "manifest_sha256": sha(out / "manifest.json"), "selected": selected,
                      "v1_ranking_matches": [x["full_order_matches"] for x in outputs_v1],
                      "v2_ranking_matches": [x["full_order_matches"] for x in sel_outputs],
                      "v2_metrics": [{"sample_id": x["sample_id"], **x["metrics_vs_pure_ps"]} for x in sel_outputs]}, indent=2))


def load_suffix():
    so = ort.SessionOptions()
    so.intra_op_num_threads = 1
    so.inter_op_num_threads = 1
    so.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    return ort.InferenceSession(str(SPLITS / "suffix.onnx"), so, providers=["CPUExecutionProvider"])


if __name__ == "__main__":
    main()
