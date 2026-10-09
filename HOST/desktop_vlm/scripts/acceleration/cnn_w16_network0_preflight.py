"""Three-image HOST W16 integer preflight for the four-block network0 profile."""
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
from cnn_w16_joint_oracle import make_params, execute_block, pack_block

HOST = ROOT / "artifacts/board-debug-20261005/acceleration/host"
OLD = ROOT / "artifacts/board-debug-20261004/host/s1-onnx-001"
N0_REF = HOST / "root-stage0-preflight-001"
MODEL_PATH = OLD / "mobileclip_s1_image.onnx"
OUT = HOST / "network0-w16-preflight-001"


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def session(model):
    opts = ort.SessionOptions()
    opts.intra_op_num_threads = 1
    opts.inter_op_num_threads = 1
    opts.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    return ort.InferenceSession(model.SerializeToString(), opts,
                                providers=["CPUExecutionProvider"])


def write(root, rel, data, dtype=None, shape=None):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    out = {"path": rel.replace("\\", "/"), "bytes": len(data), "sha256": sha(path)}
    if dtype is not None:
        out.update({"dtype": dtype, "shape": list(shape)})
    return out


def main():
    if OUT.exists():
        raise FileExistsError(f"refusing to overwrite {OUT}")
    source_sha = sha(MODEL_PATH)
    base = json.loads((N0_REF / "manifest.json").read_text(encoding="utf-8"))
    if base["model_sha256"] != source_sha:
        raise ValueError("network0 preflight source model mismatch")
    model = onnx.load(str(MODEL_PATH))
    layers = [n2.extract_block_parameters(model, block) for block in base["blocks"]]
    scale_specs = [x["scales"] for x in base["parameters"]]
    params = [make_params(layer, scales) for layer, scales in zip(layers, scale_specs)]
    suffix = session(onnx.utils.Extractor(model).extract_model(
        [base["blocks"][-1]["outputs"]["add"]], ["features"]))
    old_meta = json.loads((OLD / "manifest.json").read_text(encoding="utf-8"))
    text_features = np.fromfile(OLD / "text-features.f32", dtype="<f4").reshape(8, 512)
    text_ids = [item["id"] for item in old_meta["prompts"]]
    text_unit = text_features.astype(np.float64)
    text_unit /= np.maximum(np.linalg.norm(text_unit, axis=1, keepdims=True), 1e-300)
    OUT.mkdir(parents=True)
    param_refs = []
    for i, p in enumerate(params):
        packed = pack_block(p, 64)
        param_refs.append(write(OUT, f"params/profile2/block-{i:02d}.bin", packed))
    samples, global_bounds = [], {}
    for sample in base["samples"]:
        sid = sample["sample_id"]
        files = {Path(x["path"]).name: x for x in sample["files"]}
        input_entry = files["input.i16"]
        input_path = N0_REF / input_entry["path"]
        raw = input_path.read_bytes()
        if len(raw) != int(input_entry["bytes"]) or sha(input_path) != input_entry["sha256"]:
            raise ValueError("network0 prefix input integrity failure")
        q = np.frombuffer(raw, dtype="<i2").reshape(64, 64, 64).copy()
        source_input_codes = q.copy()
        sample_blocks = []
        for i, p in enumerate(params):
            q, stages, accum = execute_block(q, p)
            q_hcw = np.ascontiguousarray(q.transpose(1,0,2), dtype="<i2")
            qchw_meta = write(OUT, f"{sid}/profile2/block-{i:02d}-add-chw.i16le", q.tobytes(), "<i2", q.shape)
            qhcw_meta = write(OUT, f"{sid}/profile2/block-{i:02d}-add-hcw.i16le", q_hcw.tobytes(), "<i2", q_hcw.shape)
            sample_blocks.append({"index": i, "accumulators": accum,
                                  "output_chw": qchw_meta, "output_hcw": qhcw_meta})
        out_scale = float(scale_specs[-1]["add"])
        deq = (q[None].astype(np.float32) * np.float32(out_scale)).astype("<f4")
        feature = suffix.run(["features"], {suffix.get_inputs()[0].name: deq})[0].reshape(512).astype("<f4")
        ref_feature = np.fromfile(N0_REF / sample["feature"]["path"], dtype="<f4").reshape(512)
        fp = np.fromfile(N0_REF / sample["fp32_feature"]["path"], dtype="<f4").reshape(512)
        unit = feature.astype(np.float64) / max(float(np.linalg.norm(feature)), 1e-300)
        scores = unit @ text_unit.T
        rank = [text_ids[int(x)] for x in np.argsort(-scores, kind="stable")]
        fp_unit = fp.astype(np.float64) / max(float(np.linalg.norm(fp)), 1e-300)
        fp_scores = fp_unit @ text_unit.T
        fp_rank = [text_ids[int(x)] for x in np.argsort(-fp_scores, kind="stable")]
        metrics = n2.tensor_metrics(feature, fp)
        samples.append({"sample_id": sid, "source_input_sha256": sample["input_sha256"],
                        "profile2_input_hcw": write(OUT, f"{sid}/profile2/input-hcw.i16le",
                            np.ascontiguousarray(source_input_codes.transpose(1,0,2), dtype="<i2").tobytes(), "<i2", (64,64,64)),
                        "blocks": sample_blocks,
                        "feature": write(OUT, f"{sid}/w16-feature.f32", feature.tobytes(), "<f4", feature.shape),
                        "reference_pure_ps_feature_sha256": sha(N0_REF / sample["fp32_feature"]["path"]),
                        "metrics_vs_pure_fp32_ps": metrics,
                        "ranking": rank, "pure_fp32_ranking": fp_rank,
                        "full_ranking_matches_pure_fp32": rank == fp_rank,
                        "matches_legacy_stage0_int8_profile_ranking": rank == sample["quantized_ranking"]["ranking"]})
    for i, p in enumerate(params):
        global_bounds[str(i)] = {op: {"full_range_abs_bound_max": max(spec["full_range_abs_bound"]),
                                      "bias_abs_max": max(abs(int(v)) for v in spec["bias"]),
                                      "q31_multiplier_abs_max": int(np.max(np.abs(spec["multiplier"].astype(np.int64)))),
                                      "q31_shift_range": [int(spec["shift"].min()), int(spec["shift"].max())]}
                                 for op, spec in p["layers"].items()}
    report = {"schema_version": 1, "status": "HOST_REAL_FP32_SOURCE_W16_NETWORK0_4BLOCK_PREFLIGHT_NOT_PL",
              "source": {"model_sha256": source_sha, "network0_legacy_reference_manifest_sha256": sha(N0_REF / "manifest.json"),
                         "original_inputs_manifest_sha256": sha(OLD / "manifest.json"),
                         "text_features_sha256": sha(OLD / "text-features.f32")},
              "scope": {"network": "network0", "profile": 2, "channels": 64,
                        "width": 64, "block_count": 4, "all_other_stages": "FP32 suffix"},
              "params": {"stride_bytes": c16.expected_stride(64), "words_per_block": c16.expected_stride(64)//16,
                         "total_bytes": c16.expected_stride(64)*4, "blocks": param_refs},
              "quantization": {"activation": "symmetric INT16, ties-even, clamp [-32767,32767]",
                               "weights": "FP32 source per-output symmetric INT16, ties-even",
                               "bias": "round-even(FP32 bias / accumulator scale), signed48-checked i64",
                               "accumulator": "signed48 checked; Python integer bounds and arbitrary-precision Q31 products",
                               "q31": "signed i32 multiplier, shift 0..62, exact wide multiply, ties-even",
                               "scale_add": "one final saturation after adding wide Q31 scale/residual branches"},
              "calibration": "reuse root-stage0-preflight-001 scales calibrated on the same three images; HOST-only, not board PS calibration",
              "accumulator_product_bounds": {"activation_abs_bound": 32767, "by_block_op": global_bounds,
                 "max_allowed_q31_abs_product": ((1<<47)-1)*((1<<31)-1),
                 "fits_signed80": (((1<<47)-1)*((1<<31)-1)) < (1<<79)},
              "execution": {"host_only": True, "pl_execution": False,
                            "ORT_CPU": ort.__version__, "three_frozen_images": True},
              "results": samples,
              "quality_interpretation": "Three frozen engineering images only; compare cosine/max_abs/relative-L2 and full candidate ranking with pure FP32 PS; no independent accuracy or PL claim.",
              "checks": {"all_signed48_full_range_bounds_fit": all(
                    x["full_range_abs_bound_max"] <= (1<<47)-1
                    for b in global_bounds.values() for x in b.values()),
                    "all_three_rankings_match_pure_fp32": all(x["full_ranking_matches_pure_fp32"] for x in samples),
                    "four_blocks_per_image": all(len(x["blocks"]) == 4 for x in samples)}}
    report["files"] = {p.relative_to(OUT).as_posix(): {"bytes": p.stat().st_size, "sha256": sha(p)}
                       for p in sorted(OUT.rglob("*")) if p.is_file() and p.name != "manifest.json"}
    path = OUT / "manifest.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"manifest": str(path), "manifest_sha256": sha(path),
                      "results": [{"sample_id": x["sample_id"], "metrics": x["metrics_vs_pure_fp32_ps"],
                                   "ranking_matches": x["full_ranking_matches_pure_fp32"]} for x in samples]}, indent=2))


if __name__ == "__main__":
    main()
