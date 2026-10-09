"""Bounded V2 diagnostics: local Conv error, INT32 audit, and weight-group ablation."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import onnx
from onnx import numpy_helper
import onnxruntime as ort

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_network2_int_oracle as n2
import cnn_ddr_v4_accum_audit as v4audit

HOST = ROOT / "artifacts/board-debug-20261005/acceleration/host"
V2 = HOST / "v4-joint-feature-preflight-v2-001"
V1 = HOST / "v4-joint-feature-preflight-001"
N4_TRACE = HOST / "network4-host-trace-reference-001/manifest.json"
N4_CONTRACT = HOST / "network4-host-quant-contract-001/manifest.json"
N2_MANIFEST = HOST / "network2-int-oracle-board-ps-001/manifest.json"
ORIGINAL = ROOT / "artifacts/board-debug-20261004/host/s1-onnx-001/mobileclip_s1_image.onnx"
OLD = ROOT / "artifacts/board-debug-20261004/host/s1-onnx-001"
OPS = ("dw3", "dw7", "pw1", "pw2")
STAGES = ("dw3", "dw7", "pw1", "gelu", "pw2", "scale", "add")
INT32_MAX = int(np.iinfo(np.int32).max)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def arrsha(a, dtype):
    return hashlib.sha256(np.ascontiguousarray(a, dtype=dtype).tobytes()).hexdigest()


def save_array(root, rel, arr, dtype):
    path=root/rel
    path.parent.mkdir(parents=True,exist_ok=True)
    value=np.ascontiguousarray(arr,dtype=dtype)
    value.tofile(path)
    return {"path":rel.replace("\\","/"),"dtype":dtype,"shape":list(value.shape),
            "bytes":path.stat().st_size,"sha256":sha(path)}


def meta_read(root, meta):
    path = root / meta["path"]
    raw = path.read_bytes()
    if len(raw) != int(meta["bytes"]) or hashlib.sha256(raw).hexdigest() != meta["sha256"]:
        raise ValueError(f"fixture/parameter SHA mismatch: {path}")
    value = np.frombuffer(raw, dtype=np.dtype(meta["dtype"]))
    if value.size != int(np.prod(meta["shape"])):
        raise ValueError(f"fixture/parameter shape mismatch: {path}")
    return value.reshape(meta["shape"]).copy()


def load_ref(root, rel, dtype, shape):
    path = root / rel
    return np.fromfile(path, dtype=dtype).reshape(shape)


def metrics(a, b):
    av, bv = np.asarray(a, dtype=np.float64).reshape(-1), np.asarray(b, dtype=np.float64).reshape(-1)
    d = av - bv
    na, nb = float(np.linalg.norm(av)), float(np.linalg.norm(bv))
    return {"max_abs": float(np.max(np.abs(d))), "rms_abs": float(np.sqrt(np.mean(d*d))),
            "relative_l2": float(np.linalg.norm(d) / max(nb, 1e-300)),
            "cosine": float(np.dot(av,bv) / max(na*nb, 1e-300))}


def cut_ort(model, inputs, outputs):
    cut = onnx.utils.Extractor(model).extract_model(inputs, outputs)
    onnx.checker.check_model(cut)
    so = ort.SessionOptions()
    so.intra_op_num_threads = 1
    so.inter_op_num_threads = 1
    so.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    return ort.InferenceSession(cut.SerializeToString(), so, providers=["CPUExecutionProvider"]), cut


def verify_v2_generated_files(v2, root):
    bad = []
    for rel, item in v2["generated_files"].items():
        path = root / rel
        if not path.is_file() or path.stat().st_size != item["bytes"] or sha(path) != item["sha256"]:
            bad.append(rel)
    if bad:
        raise ValueError(f"V2 integrity index failed: {bad[:5]}")


def make_fixtures(v2, out_root):
    sample_map = {}
    for sample in v2["samples"]:
        sid = sample["sample_id"]
        files = sample["fixture_files"]
        blocks = []
        for bi in range(20):
            stage_values = {}
            for label in ("input", "dw3", "dw7", "pw1", "gelu", "pw2", "scale-branch", "residual-branch", "add"):
                rel = f"fixtures/{sid}/block-{bi:02d}-{label}.bin"
                meta = files[rel]
                stage_values[label] = meta_read(V2, meta)
            blocks.append(stage_values)
        sample_map[sid] = {"blocks": blocks,
                           "joint_feature": meta_read(V2, sample["joint_int_feature"]),
                           "pure_feature": np.fromfile(OLD / f"{sid}-ort.f32", dtype="<f4").reshape(512),
                           "n3": np.fromfile(V1 / "intermediates" / sid / "n3-output.f32", dtype="<f4").reshape(1,256,16,16)}
    return sample_map


def local_conv_reference(model, trace, samples, scales):
    nodes = {node.name: node for node in model.graph.node}
    inputs, outputs, index = [], [], {}
    for bi, block in enumerate(trace["blocks"]):
        for op in OPS:
            node = nodes[block["nodes"][op]]
            inputs.append(node.input[0]); outputs.append(node.output[0])
            index[bi,op] = {"input": node.input[0], "output": node.output[0]}
    if len(set(inputs)) != 80 or len(set(outputs)) != 80:
        raise ValueError("expected 80 distinct Conv tensor ports")
    session, model_cut = cut_ort(model, inputs, outputs)
    out_map, lifetime = {}, []
    previous_raw = None
    op_input_scale = {"dw3":"input", "dw7":"dw3", "pw1":"dw7", "pw2":"gelu"}
    op_output_scale = {"dw3":"dw3", "dw7":"dw7", "pw1":"pw1", "pw2":"pw2"}
    for sid, sample in samples.items():
        feeds = {}
        for bi, block in enumerate(sample["blocks"]):
            for op in OPS:
                codes = block[op_input_scale[op] if op != "dw3" else "input"]
                scale = float(scales[bi][op_input_scale[op]])
                feeds[index[bi,op]["input"]] = (codes[None].astype(np.float32) * np.float32(scale)).astype(np.float32)
        raw_outputs = session.run(None, feeds)
        if previous_raw is not None:
            name, old, before = previous_raw
            after = arrsha(old, old.dtype)
            lifetime.append({"after_next_run_sample": sid, "output_tensor": name,
                             "sha256_before_next_run": before, "sha256_after_next_run": after,
                             "changed": before != after, "finite_after_next_run": bool(np.isfinite(old).all()),
                             "no_local_math_applied": True})
        names = [x.name for x in session.get_outputs()]
        outputs_by_name = {name: np.array(value, copy=True) for name,value in zip(names,raw_outputs)}
        nonfinite = [n for n,x in outputs_by_name.items() if not np.isfinite(x).all()]
        if nonfinite:
            raise ValueError(f"nonfinite raw ORT Conv outputs {sid}: {nonfinite[:4]}")
        previous_raw = (names[0], raw_outputs[0], arrsha(raw_outputs[0], raw_outputs[0].dtype))
        records = []
        for bi in range(20):
            for op in OPS:
                input_key = op_input_scale[op]
                output_key = op_output_scale[op]
                q = sample["blocks"][bi][input_key]
                qout = sample["blocks"][bi][op]
                y = outputs_by_name[index[bi,op]["output"]][0]
                scales_i = scales[bi]
                qdeq = qout.astype(np.float32) * np.float32(scales_i[output_key])
                if qdeq.shape != y.shape:
                    raise ValueError(f"local Conv shape mismatch {sid} b{bi} {op}: {qdeq.shape}/{y.shape}")
                # No saturation/no nan replacement: fail on invalid target or dequant values.
                if not np.isfinite(qdeq).all() or not np.isfinite(y).all():
                    raise ValueError(f"nonfinite local comparison {sid} b{bi} {op}")
                diff = qdeq.astype(np.float64) - y.astype(np.float64)
                per_channel = np.sqrt(np.mean(diff * diff, axis=(1,2)))
                records.append({"block": bi, "op": op, "metrics": metrics(qdeq,y),
                                "input_codes_sha256": arrsha(q,"<i2"),
                                "float_target_sha256": arrsha(y,"<f4"),
                                "int_output_sha256": arrsha(qout,"<i2"),
                                "max_local_rmse_channel": int(np.argmax(per_channel)),
                                "max_local_rmse": float(per_channel.max()),
                                "input_abs_max_code": int(np.max(np.abs(q.astype(np.int32))))})
        out_map[sid] = records
    return out_map, lifetime, hashlib.sha256(model_cut.SerializeToString()).hexdigest()


def run_weight_ablation(original_model, trace, samples, v2_manifest, out_root, text_features, text_ids):
    init_source = {x.name: numpy_helper.to_array(x).copy() for x in original_model.graph.initializer}
    node_by_name = {n.name:n for n in original_model.graph.node}
    v2_parameter_files = [b["files"] for b in v2_manifest["parameters"]]
    weight_cache = {}
    orig_weight_names = {}
    for bi, block in enumerate(trace["blocks"]):
        for op in OPS:
            node = node_by_name[block["nodes"][op]]
            orig = init_source[node.input[1]]
            orig_weight_names[bi,op] = (node.input[1], orig)
            key = f"params/block-{bi:02d}/{op}-weights_i8.bin"
            meta = v2_parameter_files[bi][key]
            q = meta_read(V2, meta)
            skey = f"params/block-{bi:02d}/{op}-weight_scales_f64.bin"
            scale = meta_read(V2, v2_parameter_files[bi][skey]).reshape(-1)
            if op.startswith("pw"):
                shaped_scale = scale.reshape((-1,1))
            else:
                shaped_scale = scale.reshape((-1,1,1,1))
            dequant = q.astype(np.float64) * shaped_scale
            if op.startswith("pw"):
                dequant = dequant.reshape(orig.shape)
            weight_cache[bi,op] = (q, scale, dequant.astype(np.float32), orig)

    n4_out = trace["blocks"][-1]["outputs"]["add"]
    n4_input = trace["blocks"][0]["input"]
    suffix_options=ort.SessionOptions(); suffix_options.intra_op_num_threads=1; suffix_options.inter_op_num_threads=1
    suffix_options.execution_mode=ort.ExecutionMode.ORT_SEQUENTIAL
    suffix = ort.InferenceSession(str(HOST / "v4-runtime-models-001/suffix.onnx"), suffix_options,
                                  providers=["CPUExecutionProvider"])
    text = text_features.astype(np.float64)
    text /= np.maximum(np.linalg.norm(text, axis=1, keepdims=True), 1e-300)
    candidates = [{"name":"int8_dequant_all_weights", "restore_group":None, "weight_bits":8}]
    candidates += [{"name":f"restore_fp32_{op}", "restore_group":op, "weight_bits":8} for op in OPS]
    candidates += [{"name":"int16_dequant_all_weights_host_upper_bound", "restore_group":None, "weight_bits":16}]
    reports = []
    for candidate in candidates:
        graph = copy.deepcopy(original_model)
        inits = {x.name:x for x in graph.graph.initializer}
        for bi, block in enumerate(trace["blocks"]):
            for op in OPS:
                if candidate["weight_bits"] == 8:
                    q, scale, deq8, orig = weight_cache[bi,op]
                    value = orig if op == candidate["restore_group"] else deq8
                else:
                    orig = weight_cache[bi,op][3]
                    axes = tuple(range(1,orig.ndim))
                    maximum = np.max(np.abs(orig.astype(np.float64)), axis=axes)
                    scale16 = np.where(maximum > 0, maximum / 32767.0, 1.0)
                    reshape = (len(scale16),) + (1,)*(orig.ndim-1)
                    q16 = np.clip(np.rint(orig.astype(np.float64) / scale16.reshape(reshape)), -32767, 32767).astype(np.int16)
                    value = (q16.astype(np.float64) * scale16.reshape(reshape)).astype(np.float32)
                node = node_by_name[block["nodes"][op]]
                inits[node.input[1]].CopyFrom(numpy_helper.from_array(np.ascontiguousarray(value), name=node.input[1]))
        cut = onnx.utils.Extractor(graph).extract_model([n4_input], [n4_out])
        onnx.checker.check_model(cut)
        cut_bytes = cut.SerializeToString()
        options=ort.SessionOptions(); options.intra_op_num_threads=1; options.inter_op_num_threads=1
        options.execution_mode=ort.ExecutionMode.ORT_SEQUENTIAL
        n4_session=ort.InferenceSession(cut_bytes,options,providers=["CPUExecutionProvider"])
        per_sample=[]
        for sid,sample in samples.items():
            boundary=sample["n3"]
            add=n4_session.run(None,{n4_session.get_inputs()[0].name:boundary})[0]
            feature=suffix.run(None,{suffix.get_inputs()[0].name:add})[0].reshape(512).astype(np.float32)
            pure=sample["pure_feature"]
            joint=sample["joint_feature"]
            vector=feature.astype(np.float64); vector/=max(float(np.linalg.norm(vector)),1e-300)
            ps=pure.astype(np.float64); ps/=max(float(np.linalg.norm(ps)),1e-300)
            scores=vector@text.T; pscores=ps@text.T
            order=np.argsort(-scores,kind="stable"); porder=np.argsort(-pscores,kind="stable")
            rel=f"group-ablation/{candidate['name']}/{sid}-feature.f32"
            meta=save_array(out_root,rel,feature,"<f4")
            per_sample.append({"sample_id":sid,"feature":meta,"metrics_vs_pure_ps":metrics(feature,pure),
                               "metrics_vs_full_joint_int":metrics(feature,joint),
                               "ranking": [text_ids[int(i)] for i in order],
                               "pure_ps_ranking": [text_ids[int(i)] for i in porder],
                               "full_order_matches_pure_ps":bool(np.array_equal(order,porder)),
                               "scores":{text_ids[i]:float(scores[i]) for i in range(len(text_ids))}})
        reports.append({**candidate,"onnx_cut_sha256":hashlib.sha256(cut_bytes).hexdigest(),
                        "purpose":"HOST-only FP32-activation weight-group ablation; not executable INT hardware proof",
                        "samples":per_sample})
        del n4_session, cut, cut_bytes, graph
    return reports


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output",required=True,type=Path)
    args=ap.parse_args()
    out=args.output.resolve()
    if (out/"manifest.json").exists(): raise FileExistsError(out)
    out.mkdir(parents=True,exist_ok=True)
    v2_path=V2/"manifest.json"
    v2=json.loads(v2_path.read_text(encoding="utf-8"))
    verify_v2_generated_files(v2,V2)
    trace=json.loads(N4_TRACE.read_text(encoding="utf-8"))
    contract=json.loads(N4_CONTRACT.read_text(encoding="utf-8"))
    model=onnx.load(str(ORIGINAL))
    scales=[b["calibration_scales"] for b in contract["blocks"]]
    samples=make_fixtures(v2,V2)
    print("stage: local Conv references",flush=True)
    local_metrics,buffer_probe,conv_cut_sha=local_conv_reference(model,trace,samples,scales)
    print("stage: local Conv references done",flush=True)

    # Full per-output-channel INT32 audit from the exact frozen V2 activation fixtures.
    print("stage: INT32 bounds and v4 audit adapter",flush=True)
    parameter_records=[b["files"] for b in v2["parameters"]]
    activation_inputs={"dw3":"input","dw7":"dw3","pw1":"dw7","pw2":"gelu"}
    acc_report={"int32_max":INT32_MAX,"all_layers":[],"per_output_channel":[]}
    compat_blocks=[]; compat_results=[]
    for bi in range(20):
        layer_records={}
        for op in OPS:
            f=parameter_records[bi]
            prefix=f"params/block-{bi:02d}/{op}-"
            qw=meta_read(V2,f[prefix+"weights_i8.bin"])
            bias=meta_read(V2,f[prefix+"bias_i32.bin"]).astype(np.int64)
            axes=tuple(range(1,qw.ndim)); l1=np.sum(np.abs(qw.astype(np.int64)),axis=axes)
            max_input=0; raw_peak=0; biased_peak=0; raw_where={}; biased_where={}
            for sid,sample in samples.items():
                xin=sample["blocks"][bi][activation_inputs[op]].astype(np.int16)
                max_input=max(max_input,int(np.max(np.abs(xin.astype(np.int32)))))
                layer={"weight_i8":qw}
                raw=n2._layer_raw(layer,xin)
                total=n2.checked_accumulator_with_bias(raw,bias.astype(np.int32))
                raw_abs=int(np.max(np.abs(raw.astype(np.int64))))
                total_abs=int(np.max(np.abs(total.astype(np.int64))))
                if raw_abs>raw_peak:
                    idx=np.unravel_index(np.argmax(np.abs(raw.astype(np.int64))),raw.shape)
                    raw_peak=raw_abs; raw_where={"sample_id":sid,"channel":int(idx[0]),"y":int(idx[1]),"x":int(idx[2])}
                if total_abs>biased_peak:
                    idx=np.unravel_index(np.argmax(np.abs(total.astype(np.int64))),total.shape)
                    biased_peak=total_abs; biased_where={"sample_id":sid,"channel":int(idx[0]),"y":int(idx[1]),"x":int(idx[2])}
                if op in ("pw1","pw2"):
                    raw_rel=f"accumulators/{sid}/block-{bi:02d}/{op}-raw-i64.bin"
                    total_rel=f"accumulators/{sid}/block-{bi:02d}/{op}-bias-included-i32.bin"
                    raw_meta=save_array(out,raw_rel,raw,"<i8")
                    total_meta=save_array(out,total_rel,total,"<i4")
                    layer_records.setdefault(sid,{})[op]={"raw":raw_meta,"biased":total_meta}
            full=32767*l1+np.abs(bias)
            calibrated=max_input*l1+np.abs(bias)
            channel_records=[{"channel":i,"weight_l1":int(l1[i]),"abs_bias":int(abs(bias[i])),
                              "full_range_bound":int(full[i]),"fixture_range_bound":int(calibrated[i]),
                              "full_fits_int32":bool(full[i]<=INT32_MAX),"fixture_fits_int32":bool(calibrated[i]<=INT32_MAX)}
                             for i in range(len(l1))]
            rec={"block":bi,"op":op,"output_channels":int(len(l1)),"reduction":int(np.prod(qw.shape[1:])),
                 "input_abs_bound_full":32767,"input_abs_bound_fixture":max_input,
                 "full_range_max":int(full.max()),"full_range_max_channel":int(np.argmax(full)),
                 "fixture_range_max":int(calibrated.max()),"fixture_range_max_channel":int(np.argmax(calibrated)),
                 "actual_raw_abs_peak":raw_peak,"actual_raw_peak_location":raw_where,
                 "actual_bias_included_abs_peak":biased_peak,"actual_bias_included_peak_location":biased_where,
                 "fits_int32":bool(np.all(full<=INT32_MAX) and np.all(calibrated<=INT32_MAX) and raw_peak<=INT32_MAX and biased_peak<=INT32_MAX)}
            acc_report["all_layers"].append(rec); acc_report["per_output_channel"].append({"block":bi,"op":op,"channels":channel_records})
        compat_param={}
        for op in ("pw1","pw2"):
            f=parameter_records[bi]; base=f"params/block-{bi:02d}/{op}-"
            for suffix in ("weights_i8.bin","bias_i32.bin"):
                meta=f[base+suffix].copy()
                meta["path"]="../v4-joint-feature-preflight-v2-001/"+meta["path"]
                compat_param[f"{op}_{'weights' if suffix.startswith('weights') else 'bias'}_i8" if suffix.startswith('weights') else f"{op}_bias_i32"]=meta
        compat_blocks.append({"parameters":compat_param})
    for sid,sample in samples.items():
        bresults=[]
        for bi in range(20):
            files=v2["samples"][[x["sample_id"] for x in v2["samples"]].index(sid)]["fixture_files"]
            outputs={}
            for alias,label in (("dw7_output_i16","dw7"),("gelu_output_i16","gelu")):
                rel=f"fixtures/{sid}/block-{bi:02d}-{label}.bin"
                meta=files[rel].copy(); meta["path"]="../v4-joint-feature-preflight-v2-001/"+meta["path"]
                outputs[alias]=meta
            for op in ("pw1","pw2"):
                refs=layer_records[sid][op]
                outputs[f"{op}_raw_i64"]={**refs["raw"],"path":refs["raw"]["path"]}
                outputs[f"{op}_bias_included_i32"]={**refs["biased"],"path":refs["biased"]["path"]}
            bresults.append({"index":bi,"outputs":outputs})
        compat_results.append({"sample_id":sid,"blocks":bresults})
    compat_path=out/"accumulator-audit-input.json"
    compat_path.write_text(json.dumps({"status":"NETWORK4_V2_AUDIT_ADAPTER_HOST_ONLY","blocks":compat_blocks,"results":compat_results},indent=2,sort_keys=True)+"\n",encoding="utf-8")
    pwaudit=v4audit.audit_n4(compat_path)
    pwaudit["summary_maxima"]=v4audit.summarize(pwaudit)
    acc_report["cnn_ddr_v4_accum_audit_pw1_pw2"]=pwaudit
    acc_report["all_fit_int32"]=all(x["fits_int32"] for x in acc_report["all_layers"])
    (out/"accumulator-audit.json").write_text(json.dumps(acc_report,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print("stage: group ablations",flush=True)
    textmeta=json.loads(N2_MANIFEST.read_text(encoding="utf-8"))["text_feature_reference"]
    text=np.fromfile(HOST/"network2-int-oracle-board-ps-001"/textmeta["path"],dtype="<f4").reshape(8,512)
    text_ids=[p["id"] for p in json.loads((OLD/"manifest.json").read_text(encoding="utf-8"))["prompts"]]
    ablations=run_weight_ablation(model,trace,samples,v2,out,text,text_ids)

    report={"schema_version":1,"status":"V2_LOCAL_ORACLE_AUDIT_AND_WEIGHT_ABLATION_HOST_ONLY_NOT_PL",
            "provenance":{"v2_manifest_sha256":sha(V2/"manifest.json"),"original_model_sha256":sha(ORIGINAL),
                          "network4_contract_manifest_sha256":sha(N4_CONTRACT),"network4_trace_manifest_sha256":sha(N4_TRACE),
                          "local_conv_cut_sha256":conv_cut_sha,"pl_execution":False,
                          "n3_inputs":"SHA-verified runtime outputs produced by actual prefix->network2 INT->network3 bridge in V1 joint run"},
            "local_conv_output_error":local_metrics,
            "ort_raw_output_lifetime_probe":{"samples":buffer_probe,"observation":"raw first Conv output SHA checked before/after subsequent Run, without any local operation. Changed=true establishes backing buffer mutation/overwrite for the retained array; all outputs used for math were copied immediately."},
            "accumulator_audit":acc_report,
            "weight_group_ablation":{"method":"original network4 graph with FP32 activations and FP32 biases; replace each block Conv weight initializer with V2 per-channel dequantized INT8 weights, then restore exactly one all-block op group to original FP32 weights; separate all-group INT16-dequantized HOST upper bound",
                                  "not_pl_or_hls_proof":True,"candidates":ablations},
            "interpretation":{"strict_gate":"future BOARD/PL-vs-same-quantization frozen joint reference only: max_abs<=1e-6 and cosine>=0.99999",
                              "host_results":"diagnostic/regression only; no independent accuracy claim"}}
    report["generated_files"]={}
    for p in sorted(x for x in out.rglob("*") if x.is_file() and x.name!="manifest.json"):
        report["generated_files"][p.relative_to(out).as_posix()]={"bytes":p.stat().st_size,"sha256":sha(p)}
    (out/"manifest.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({"artifact":str(out),"manifest_sha256":sha(out/"manifest.json"),
                      "accumulators_fit_int32":acc_report["all_fit_int32"],
                      "groups":{x["name"]:[s["full_order_matches_pure_ps"] for s in x["samples"]] for x in ablations}},indent=2))


if __name__=="__main__": main()
