"""Full-shape A ablation: emit DW3/DW7 bias-included INT32 accumulators.

Inputs, scale constants, and integer accumulators are pinned to the board-backed
stage2-dw3-dw7-int8-007 reference. All suffix execution is host CPU ORT only.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import onnx
import onnxruntime as ort

import build_stage2_int8_reference as base


BASE_MANIFEST_SHA256 = "baa9b584b075462b5d7dbd77aac8a83daa5227dace23dc5cbc6f933795b59a4f"
TEXT_SHA256 = base.TEXT_SHA256
TEXT_MANIFEST = Path("artifacts/board-debug-20261004/host/s1-onnx-001/manifest.json")


def _sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _save_array(out, name, value, dtype):
    path = out / name
    packed = np.ascontiguousarray(value, dtype=dtype)
    packed.tofile(str(path))
    return {"path": name, "shape": list(packed.shape), "dtype": dtype,
            "bytes": path.stat().st_size, "sha256": _sha(path)}


def _feature_metrics(actual, reference):
    delta = actual.astype(np.float64) - reference.astype(np.float64)
    denom = float(np.linalg.norm(reference.astype(np.float64)))
    a = actual.astype(np.float64).reshape(-1)
    b = reference.astype(np.float64).reshape(-1)
    cos = float(np.dot(a, b) / max(float(np.linalg.norm(a) * np.linalg.norm(b)), 1e-30))
    return {"max_abs": float(np.max(np.abs(delta))),
            "rms_abs": float(np.sqrt(np.mean(delta * delta))),
            "relative_l2": float(np.linalg.norm(delta) / max(denom, 1e-30)),
            "cosine": cos,
            "allclose_rtol_1e-4_atol_1e-5": bool(np.allclose(
                actual, reference, rtol=1e-4, atol=1e-5))}


def _extract_suffix(model_path, threads):
    model = onnx.load(str(model_path))
    suffix = onnx.utils.Extractor(model).extract_model([base.DW3_OUT, base.DW7_OUT], ["features"])
    onnx.checker.check_model(suffix)
    options = ort.SessionOptions()
    options.intra_op_num_threads = threads
    options.inter_op_num_threads = 1
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    ort.disable_telemetry_events()
    return ort.InferenceSession(suffix.SerializeToString(), options,
                                providers=["CPUExecutionProvider"]), _sha(model_path)


def _rank(features, text_unit, ids):
    unit = features.astype(np.float64).reshape(-1)
    unit /= max(float(np.linalg.norm(unit)), 1e-30)
    scores = unit @ text_unit.T
    order = np.argsort(-scores, kind="stable")
    return scores.tolist(), [ids[int(i)] for i in order]


def run(args):
    source = Path(args.source)
    manifest_path = source / "manifest.json"
    if _sha(manifest_path) != BASE_MANIFEST_SHA256:
        raise ValueError("stage2-dw3-dw7-int8-007 manifest SHA mismatch")
    prior = json.loads(manifest_path.read_text(encoding="utf-8"))
    if prior["status"] != "STAGE2_INT8_CPU_REFERENCE_FROM_ACTUAL_BOARD_PS_TENSORS_NOT_PL":
        raise ValueError("base reference is not the pinned PS-backed CPU oracle")
    if not prior["actual_board_outputs_are_authoritative"]:
        raise ValueError("base reference does not preserve board PS authority")
    if prior["board_collection_manifest_sha256"] != base.COLLECTION_MANIFEST_SHA256:
        raise ValueError("base board collection identity mismatch")
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=False)

    collection_dir = Path(args.collection_dir)
    collection, split, board_records, host_comparison = base._load_board_collection(
        collection_dir, Path(args.split_manifest))
    if _sha(Path(args.text_features)) != TEXT_SHA256:
        raise ValueError("pinned 8-text feature SHA mismatch")
    text = np.fromfile(str(args.text_features), dtype="<f4").reshape((8, 512))
    text_unit = text.astype(np.float64)
    text_unit /= np.maximum(np.linalg.norm(text_unit, axis=1, keepdims=True), 1e-30)
    prompts = json.loads(TEXT_MANIFEST.read_text(encoding="utf-8"))["prompts"]
    ids = [item["id"] for item in prompts]
    session, model_sha = _extract_suffix(Path(args.model), args.threads)
    if model_sha != base.MODEL_SHA256:
        raise ValueError("pinned model changed while loading suffix")

    scale3 = np.fromfile(str(source / "dw3-accumulator-scale.f64"), dtype="<f8")
    scale7 = np.fromfile(str(source / "dw7-accumulator-scale.f64"), dtype="<f8")
    if scale3.shape != (128,) or scale7.shape != (128,):
        raise ValueError("per-channel accumulator scale shape must be 128")
    scale_int8 = prior["calibration"]["activation_scales"]
    feature_dir = Path(args.board_feature_dir)
    run_dir = Path(args.board_run_dir)

    names = ["A_both_i32", "A_only_q7_int8", "A_only_q3_residual_int8", "A_both_int8"]
    metrics_by_name = {name: [] for name in names}
    records = []
    for index, board in enumerate(board_records):
        sample_id = board["sample_id"]
        prior_sample = prior["results"][index]
        if prior_sample["sample_id"] != sample_id:
            raise ValueError("board sample order mismatch")
        accum3 = np.fromfile(str(source / prior_sample["files"]["dw3-with-bias.i32"]["path"]),
                             dtype="<i4").reshape((128, 32, 32))
        accum7 = np.fromfile(str(source / prior_sample["files"]["dw7-with-bias.i32"]["path"]),
                             dtype="<i4").reshape((128, 32, 32))
        q3 = np.fromfile(str(source / prior_sample["files"]["dw3-output.i8"]["path"]),
                         dtype=np.int8).reshape((128, 32, 32))
        q7 = np.fromfile(str(source / prior_sample["files"]["dw7-output.i8"]["path"]),
                         dtype=np.int8).reshape((128, 32, 32))
        q3_dequant = (q3.astype(np.float64) * scale_int8["dw3_to_dw7"]).astype("<f4")[None, ...]
        q7_dequant = (q7.astype(np.float64) * scale_int8["dw7_to_stage3"]).astype("<f4")[None, ...]
        acc3_dequant = (accum3.astype(np.float64) * scale3[:, None, None]).astype("<f4")[None, ...]
        acc7_dequant = (accum7.astype(np.float64) * scale7[:, None, None]).astype("<f4")[None, ...]

        packet_path = out / (sample_id + "-stage2-dual-accumulator-packet.i32le")
        with packet_path.open("wb") as packet:
            packet.write(np.ascontiguousarray(accum3, dtype="<i4").tobytes(order="C"))
            packet.write(np.ascontiguousarray(accum7, dtype="<i4").tobytes(order="C"))
        packet_record = {
            "path": packet_path.name, "sha256": _sha(packet_path),
            "dtype": "signed int32 little-endian", "total_bytes": 1048576,
            "one_physical_dma_packet": True,
            "shared_frame_id": sample_id,
            "TLAST": "only after final byte at offset 1048575; no intermediate TLAST",
            "segments": [
                {"order": 0, "name": "DW3 residual accumulator", "tensor": base.DW3_OUT,
                 "shape": [1, 128, 32, 32], "offset_bytes": 0,
                 "bytes": 524288, "alignment_bytes": 4,
                 "accumulator_contains_bias": True,
                 "accumulator_scale_per_channel_file": "dw3-accumulator-scale.f64",
                 "reconstruction": "DW3_fp32[c,y,x] = int32_packet0[c,y,x] * Spre * Sw3[c]",
                 "zero_point": 0, "tlast": False},
                {"order": 1, "name": "DW7 main accumulator", "tensor": base.DW7_OUT,
                 "shape": [1, 128, 32, 32], "offset_bytes": 524288,
                 "bytes": 524288, "alignment_bytes": 4,
                 "accumulator_contains_bias": True,
                 "accumulator_scale_per_channel_file": "dw7-accumulator-scale.f64",
                 "reconstruction": "DW7_fp32[c,y,x] = int32_packet1[c,y,x] * Smid * Sw7[c]",
                 "zero_point": 0, "tlast": True},
            ],
        }
        input_variants = {
            "A_both_i32": (acc3_dequant, acc7_dequant),
            "A_only_q7_int8": (acc3_dequant, q7_dequant),
            "A_only_q3_residual_int8": (q3_dequant, acc7_dequant),
            "A_both_int8": (q3_dequant, q7_dequant),
        }
        baseline_path, baseline_sha = base.BOARD_FEATURES[index]
        board_feature_path = feature_dir / baseline_path
        if _sha(board_feature_path) != baseline_sha:
            raise ValueError("pure PS feature hash mismatch")
        board_features = np.fromfile(str(board_feature_path), dtype="<f4").reshape((1, 512))
        board_scores, board_rank = _rank(board_features, text_unit, ids)
        host_ref = session.run(["features"], {
            base.DW3_OUT: board["tensors"]["dw3-output"][None, ...],
            base.DW7_OUT: board["tensors"]["dw7-output"][None, ...],
        })[0]
        host_metrics = _feature_metrics(host_ref, board_features)
        variants = {}
        packet_q3 = _save_array(out, sample_id + "-dw3-reconstructed-from-i32.f32", acc3_dequant, "<f4")
        packet_q7 = _save_array(out, sample_id + "-dw7-reconstructed-from-i32.f32", acc7_dequant, "<f4")
        for name, (residual, main_input) in input_variants.items():
            features = session.run(["features"], {
                base.DW3_OUT: residual,
                base.DW7_OUT: main_input,
            })[0]
            scores, rank = _rank(features, text_unit, ids)
            metric = _feature_metrics(features, board_features)
            top1_changed = rank[0] != board_rank[0]
            metric_record = {"feature_vs_pure_ps": metric,
                             "sample_id": sample_id,
                             "board_ps_top1": board_rank[0],
                             "variant_top1": rank[0],
                             "top1_changed": top1_changed,
                             "board_ps_ranking": board_rank,
                             "variant_ranking": rank,
                             "board_ps_scores": board_scores,
                             "variant_scores": scores,
                             "rank_matches_pure_ps": rank == board_rank,
                             "features": _save_array(
                                 out, sample_id + "-" + name + "-features.f32", features, "<f4")}
            variants[name] = metric_record
            metrics_by_name[name].append(metric_record)
        records.append({
            "sample_id": sample_id,
            "input_sha256": board["input_sha256"],
            "board_ps_source_tensors": board["board_files"],
            "pure_ps_feature_sha256": baseline_sha,
            "pure_ps_feature_source": prior["final_feature_results"][index][
                "pure_ps_feature_source"],
            "host_float_suffix_vs_pure_ps": host_metrics,
            "i32_reconstruction_files": {"dw3": packet_q3, "dw7": packet_q7},
            "stage2_tensor_errors_vs_actual_board_ps": {
                "dw3_accumulator_reconstruction": base._error_record(
                    acc3_dequant, board["tensors"]["dw3-output"][None, ...]),
                "dw3_q3_int8_reconstruction": base._error_record(
                    q3_dequant, board["tensors"]["dw3-output"][None, ...]),
                "dw7_accumulator_reconstruction": base._error_record(
                    acc7_dequant, board["tensors"]["dw7-output"][None, ...]),
                "dw7_q7_int8_reconstruction": base._error_record(
                    q7_dequant, board["tensors"]["dw7-output"][None, ...]),
            },
            "packet": packet_record,
            "variants": variants,
            "suffix_residual_rule": "all variants use only their named DW3 reconstruction: accumulator*per-channel accumulator-scale for A_both_i32/A_only_q7_int8; q3*S_mid only in A_only_q3_residual_int8/A_both_int8; no original FP32 DW3 is used for A inputs.",
        })

    report = {
        "schema_version": 1,
        "status": "STAGE2_A_INT32_DUAL_ACCUMULATOR_ABLATION_CPU_ONLY_NOT_PL",
        "base_int8_reference_manifest_sha256": BASE_MANIFEST_SHA256,
        "source_model_sha256": base.MODEL_SHA256,
        "split_manifest_sha256": base.SPLIT_MANIFEST_SHA256,
        "board_collection_manifest_sha256": base.COLLECTION_MANIFEST_SHA256,
        "board_ps_outputs_authoritative": True,
        "host_cpu_suffix_is_comparison_only": True,
        "pl_execution": False,
        "actual_board_ps_feature_files": [{"path": name, "sha256": digest}
                                           for name, digest in base.BOARD_FEATURES],
        "activation_quantization": {
            "pre_dw3": scale_int8["pre_dw3"], "dw3_to_dw7": scale_int8["dw3_to_dw7"],
            "dw7_to_stage3": scale_int8["dw7_to_stage3"],
            "zero_point": 0, "rounding": "ties-to-even", "clip": [-127, 127],
        },
        "A_accumulator_dual_output_contract": {
            "packet_count": 1, "format": "raw concatenated two-segment simple-S2MM payload; no header",
            "dtype": "signed int32 little-endian", "total_bytes": 1048576,
            "segment_shape": [1, 128, 32, 32], "segment_bytes": 524288,
            "segment_alignment_bytes": 4, "TLAST": "one TLAST only at final packet byte (offset 1048575)",
            "frame_relation": "both segments belong to same input frame; packet is one launch/frame; sample_id records host identity",
            "bias": "each packet segment contains raw INT64 convolution accumulation plus quantized INT32 bias, checked to fit signed INT32; no activation requantization in either segment",
            "reconstruction": {
                "dw3": "packet0[c,y,x] * (Spre * Sw3[c]); result is DW3 residual to stage3",
                "dw7": "packet1[c,y,x] * (Smid * Sw7[c]); result is stage3 main activation",
                "zero_point": 0,
                "per_channel_scales": {"dw3": {"path": "dw3-accumulator-scale.f64",
                                                  "sha256": prior["files"]["dw3-accumulator-scale.f64"]["sha256"]},
                                        "dw7": {"path": "dw7-accumulator-scale.f64",
                                                  "sha256": prior["files"]["dw7-accumulator-scale.f64"]["sha256"]}},
            },
            "internal_pl_connectivity": "DW3 remains directly connected to DW7; both accumulators are also returned as the Stage2 cut outputs.",
        },
        "stage3_suffix_contract": "A_both_i32 feeds reconstructed DW3 accumulator value to residual input and reconstructed DW7 accumulator value to main input. The q7-only and q3-only variants change one side at a time to isolate quantization error.",
        "suffix_host_runtime": {"runtime": ort.__version__, "threads": args.threads,
                                 "execution_mode": "ORT_SEQUENTIAL CPUExecutionProvider"},
        "text_features_sha256": TEXT_SHA256,
        "text_candidate_count": len(ids),
        "results": records,
        "summary": {
            name: [{"sample_id": record["sample_id"],
                    "board_ps_top1": record["board_ps_top1"],
                    "variant_top1": record["variant_top1"],
                    "top1_changed": record["top1_changed"],
                    "ranking": record["variant_ranking"],
                    "cosine": record["feature_vs_pure_ps"]["cosine"],
                    "max_abs": record["feature_vs_pure_ps"]["max_abs"],
                    "rms_abs": record["feature_vs_pure_ps"]["rms_abs"]}
                   for record in metrics_by_name[name]] for name in names},
        "checks": {"all_three_input_hashes_pinned": True,
                   "full_shape_128x32x32": True,
                   "board_ps_feature_hashes_verified": True,
                   "host_dw7_allclose_failures_preserved": True,
                   "packet_has_single_final_tlast": True,
                   "accumulator_packet_is_bias_included": True,
                   "pl_execution": False},
    }
    report["files"] = {path.name: {"bytes": path.stat().st_size, "sha256": _sha(path)}
                       for path in sorted(out.iterdir()) if path.is_file()}
    report_path = out / "manifest.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
                           encoding="utf-8")
    print(json.dumps({"output": str(out.resolve()), "manifest_sha256": _sha(report_path),
                      "summary": report["summary"]}, indent=2, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default="artifacts/board-debug-20261004/acceleration/host/stage2-dw3-dw7-int8-007")
    parser.add_argument("--collection-dir", default="artifacts/board-debug-20261004/acceleration/network/stage2-dw3-dw7-ps-001")
    parser.add_argument("--split-manifest", default="artifacts/board-debug-20261004/acceleration/host/stage2-dw3-dw7-003/manifest.json")
    parser.add_argument("--model", default="artifacts/board-debug-20261004/host/s1-onnx-001/mobileclip_s1_image.onnx")
    parser.add_argument("--board-feature-dir", default="artifacts/board-debug-20261004/network/runtime/board-runs")
    parser.add_argument("--board-run-dir", default="artifacts/board-debug-20261004/network/runtime/board-runs")
    parser.add_argument("--text-features", default="artifacts/board-debug-20261004/host/s1-onnx-001/text-features.f32")
    parser.add_argument("--output", required=True)
    parser.add_argument("--threads", type=int, choices=(1, 2, 4), default=2)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
