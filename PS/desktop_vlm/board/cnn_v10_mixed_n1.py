"""Run the experimental W8/A16 N1 oracle against the frozen FP32 bridge."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import tempfile
import time

import numpy as np
import onnx
import onnxruntime as ort

from cnn_v10_mixed_int import (calibrate_n1, error_metrics, load_n1_contract,
                               run_n1_w8a16, sha256_file)


def read_f32(path: Path, shape: tuple[int, ...]) -> np.ndarray:
    expected_bytes = int(np.prod(shape)) * 4
    if path.stat().st_size != expected_bytes:
        raise ValueError(f"bad fixture byte size at {path}: {path.stat().st_size} != {expected_bytes}")
    array = np.fromfile(path, dtype="<f4").reshape(shape).astype(np.float32, copy=False)
    if not np.isfinite(array).all():
        raise ValueError(f"nonfinite fixture: {path}")
    return array


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def reference_intermediates(model_path: Path, inputs: list[np.ndarray], *, threads: int) -> tuple[list[np.ndarray], list[np.ndarray]]:
    model = onnx.shape_inference.infer_shapes(onnx.load(str(model_path)), strict_mode=False)
    stage = next((n.output[0] for n in model.graph.node
                  if n.output and "/network.1/proj/proj.0/activation/Mul_1_output_0" in n.output[0]), None)
    final = model.graph.output[0].name
    if not stage:
        raise ValueError("could not find frozen N1 post-DW-GELU tensor")
    values = {v.name: v for v in list(model.graph.value_info) + list(model.graph.output)}
    model.graph.output.append(values[stage])
    options = ort.SessionOptions()
    options.intra_op_num_threads = threads
    options.inter_op_num_threads = 1
    with tempfile.TemporaryDirectory(prefix="cnn_v10_n1_fp32_intermediates_") as temp:
        copy_path = Path(temp) / "n1-with-intermediate.onnx"
        onnx.save(model, str(copy_path))
        session = ort.InferenceSession(str(copy_path), sess_options=options, providers=["CPUExecutionProvider"])
        inp = session.get_inputs()[0].name
        out = session.run([final, stage], {inp: inputs[0]})
        finals, stages = [out[0]], [out[1]]
        for x in inputs[1:]:
            out = session.run([final, stage], {inp: x})
            finals.append(out[0])
            stages.append(out[1])
    return finals, stages


def aggregate_metrics(expected: list[np.ndarray], actual: list[np.ndarray]) -> dict:
    return error_metrics(np.concatenate([x.ravel() for x in expected]),
                         np.concatenate([x.ravel() for x in actual]))


def _evaluate_masks(convs, cases, scales, *, dw_channels=(), pw_channels=()):
    outputs, stages, proofs = [], [], []
    for case in cases:
        output, layer_proofs, stage = run_n1_w8a16(
            convs, case["input"], scales,
            dw_fp32_channels=dw_channels, pw_fp32_channels=pw_channels)
        outputs.append(output)
        stages.append(stage)
        proofs.extend(layer_proofs)
    return outputs, stages, proofs


def search_fp32_weight_channels(convs, cases, references, scales, *, min_cosine: float, max_relative_l2: float):
    """Greedy channel fallback search; exact channel masks are recorded in the result."""
    selected_pw = []
    base_outputs, _, _ = _evaluate_masks(convs, cases, scales)
    base_metrics = aggregate_metrics(references, base_outputs)
    pw_trials = []
    for channel in range(convs[1].weight.shape[0]):
        outputs, _, _ = _evaluate_masks(convs, cases, scales, pw_channels=(channel,))
        metrics = aggregate_metrics(references, outputs)
        gain = base_metrics["relative_l2"] ** 2 - metrics["relative_l2"] ** 2
        pw_trials.append({"channel": channel, "relative_l2": metrics["relative_l2"],
                          "cosine": metrics["cosine"], "squared_error_improvement": gain})
    pw_trials.sort(key=lambda row: (row["squared_error_improvement"], row["cosine"]), reverse=True)
    selected_dw = []
    search_trace = []

    def accepted(metrics, outputs):
        aggregate_ok = metrics["cosine"] >= min_cosine and metrics["relative_l2"] <= max_relative_l2
        case_ok = all((m := error_metrics(ref, out))["cosine"] >= min_cosine
                      and m["relative_l2"] <= max_relative_l2
                      for ref, out in zip(references, outputs))
        return aggregate_ok and case_ok

    current_outputs, _, _ = _evaluate_masks(convs, cases, scales)
    current = aggregate_metrics(references, current_outputs)
    for row in pw_trials:
        selected_pw.append(row["channel"])
        current_outputs, _, _ = _evaluate_masks(convs, cases, scales, pw_channels=selected_pw)
        current = aggregate_metrics(references, current_outputs)
        search_trace.append({"layer": "pw1", "channel_added": row["channel"],
                             "fallback_channel_count": len(selected_pw), **current})
        if accepted(current, current_outputs):
            return {"status": "PASS", "fallback": "native A16 dequantized input + FP32 weights/accumulation per selected output channel",
                    "dw_fp32_channels": [], "pw_fp32_channels": selected_pw,
                    "dw_fp32_channel_fraction": 0.0,
                    "pw_fp32_channel_fraction": len(selected_pw) / convs[1].weight.shape[0],
                    "metrics": current,
                    "per_case_metrics": [error_metrics(ref, out) for ref, out in zip(references, current_outputs)],
                    "channel_importance": pw_trials,
                    "search_trace": search_trace, "fallback_channel_storage": "FP32 weights; these channels leave Acc32/W8 path"}

    # If PW output channels alone cannot recover enough quality, fix DW channels
    # from the most useful one-channel substitutions while retaining selected PW.
    dw_trials = []
    for channel in range(convs[0].weight.shape[0]):
        outputs, _, _ = _evaluate_masks(convs, cases, scales,
                                        dw_channels=(channel,), pw_channels=selected_pw)
        metrics = aggregate_metrics(references, outputs)
        gain = current["relative_l2"] ** 2 - metrics["relative_l2"] ** 2
        dw_trials.append({"channel": channel, "relative_l2": metrics["relative_l2"],
                          "cosine": metrics["cosine"], "squared_error_improvement": gain})
    dw_trials.sort(key=lambda row: (row["squared_error_improvement"], row["cosine"]), reverse=True)
    for row in dw_trials:
        selected_dw.append(row["channel"])
        current_outputs, _, _ = _evaluate_masks(convs, cases, scales,
                                                dw_channels=selected_dw, pw_channels=selected_pw)
        current = aggregate_metrics(references, current_outputs)
        search_trace.append({"layer": "dw7", "channel_added": row["channel"],
                             "fallback_channel_count": len(selected_dw), **current})
        if accepted(current, current_outputs):
            return {"status": "PASS", "fallback": "native A16 dequantized input + FP32 weights/accumulation per selected output channel",
                    "dw_fp32_channels": selected_dw, "pw_fp32_channels": selected_pw,
                    "dw_fp32_channel_fraction": len(selected_dw) / convs[0].weight.shape[0],
                    "pw_fp32_channel_fraction": len(selected_pw) / convs[1].weight.shape[0],
                    "metrics": current,
                    "per_case_metrics": [error_metrics(ref, out) for ref, out in zip(references, current_outputs)],
                    "channel_importance": {"pw": pw_trials, "dw": dw_trials},
                    "search_trace": search_trace, "fallback_channel_storage": "FP32 weights; these channels leave Acc32/W8 path"}
    return {"status": "NO_PASSING_MIX", "dw_fp32_channels": selected_dw,
            "pw_fp32_channels": selected_pw,
            "dw_fp32_channel_fraction": len(selected_dw) / convs[0].weight.shape[0],
            "pw_fp32_channel_fraction": len(selected_pw) / convs[1].weight.shape[0],
            "metrics": current, "channel_importance": {"pw": pw_trials, "dw": dw_trials},
            "search_trace": search_trace,
            "fallback_channel_storage": "FP32 weights; these channels leave Acc32/W8 path"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--fixture-root", type=Path, default=Path("artifacts/board-debug-20261005/acceleration/host/network-w16-same-board-golden-001"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--max-abs", type=float, default=0.08)
    parser.add_argument("--min-cosine", type=float, default=0.999)
    parser.add_argument("--max-relative-l2", type=float, default=0.05)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite output directory: {args.output}")
    args.output.mkdir(parents=True)
    conv0, conv1, contract = load_n1_contract(args.model)
    cases = []
    for index in range(3):
        root = args.fixture_root / f"image-{index:02d}" / "board"
        cases.append({"input_path": root / "network1-bridge-input.f32",
                      "expected_path": root / "network1-bridge-output.f32",
                      "input": read_f32(root / "network1-bridge-input.f32", (1, 64, 64, 64)),
                      "expected": read_f32(root / "network1-bridge-output.f32", (1, 128, 32, 32))})
    references, fp32_stage0 = reference_intermediates(args.model, [case["input"] for case in cases], threads=args.threads)
    scales = calibrate_n1((conv0, conv1), [case["input"] for case in cases], fp32_stage0)
    options = ort.SessionOptions()
    options.intra_op_num_threads = args.threads
    options.inter_op_num_threads = 1
    reference_session = ort.InferenceSession(str(args.model), sess_options=options, providers=["CPUExecutionProvider"])
    input_name, output_name = reference_session.get_inputs()[0].name, reference_session.get_outputs()[0].name
    rows = []
    proofs = []
    for index, case in enumerate(cases):
        start = time.perf_counter()
        reference = references[index]
        # Time the production-shaped FP32 session separately from the instrumented
        # intermediate-output session used for calibration and attribution.
        reference_session.run([output_name], {input_name: case["input"]})
        start = time.perf_counter()
        reference_session.run([output_name], {input_name: case["input"]})
        fp32_ms = (time.perf_counter() - start) * 1000
        start = time.perf_counter()
        candidate, conv_proofs, candidate_stage = run_n1_w8a16((conv0, conv1), case["input"], scales)
        mixed_ms = (time.perf_counter() - start) * 1000
        fixture_error = error_metrics(case["expected"], reference)
        quant_error = error_metrics(reference, candidate)
        quant_error["cosine_to_fixture"] = error_metrics(case["expected"], candidate)["cosine"]
        gate = (quant_error["max_abs"] <= args.max_abs and quant_error["cosine"] >= args.min_cosine
                and quant_error["relative_l2"] <= args.max_relative_l2)
        candidate_path = args.output / f"image-{index:02d}-w8a16-output.f32"
        candidate.astype("<f4").tofile(candidate_path)
        rows.append({"case_id": f"image-{index:02d}", "input_sha256": sha256_file(case["input_path"]),
                     "expected_sha256": sha256_file(case["expected_path"]),
                     "candidate_path": candidate_path.name, "candidate_sha256": sha256_file(candidate_path),
                     "fp32_vs_saved_board_fixture": fixture_error,
                     "dw7_w8a16_post_gelu_vs_fp32": error_metrics(fp32_stage0[index], candidate_stage),
                     "mixed_w8a16_vs_local_fp32": quant_error,
                     "fp32_host_ms": fp32_ms, "mixed_oracle_host_ms": mixed_ms,
                     "error_gate": {"max_abs_limit": args.max_abs, "min_cosine": args.min_cosine,
                                    "max_relative_l2": args.max_relative_l2,
                                    "pass": gate}})
        proofs.extend(conv_proofs)
    proof_by_name = {}
    for proof in proofs:
        entry = proof_by_name.setdefault(proof["name"], {**proof, "observed_accumulator_min": 0,
                                                               "observed_accumulator_max": 0,
                                                               "integer_conv_ms_samples": []})
        entry["observed_accumulator_min"] = min(entry["observed_accumulator_min"], proof["observed_accumulator_min"])
        entry["observed_accumulator_max"] = max(entry["observed_accumulator_max"], proof["observed_accumulator_max"])
        entry["integer_conv_ms_samples"].append(proof["integer_conv_ms"])
    for entry in proof_by_name.values():
        entry["integer_conv_ms_median"] = float(np.median(entry.pop("integer_conv_ms_samples")))
        entry.pop("integer_conv_ms", None)
    quant_outputs, _, _ = _evaluate_masks((conv0, conv1), cases, scales)
    attribution = {
        "dw_only_w8a16": aggregate_metrics(fp32_stage0, [run_n1_w8a16((conv0, conv1), c["input"], scales)[2] for c in cases]),
        "dw_fp32_weight_fallback_all_channels": aggregate_metrics(references, _evaluate_masks((conv0, conv1), cases, scales, dw_channels=range(conv0.weight.shape[0]))[0]),
        "pw_fp32_weight_fallback_all_channels": aggregate_metrics(references, _evaluate_masks((conv0, conv1), cases, scales, pw_channels=range(conv1.weight.shape[0]))[0]),
        "both_layers_fp32_weight_fallback": aggregate_metrics(references, _evaluate_masks((conv0, conv1), cases, scales, dw_channels=range(conv0.weight.shape[0]), pw_channels=range(conv1.weight.shape[0]))[0]),
        "mixed_candidate_search": search_fp32_weight_channels((conv0, conv1), cases, references, scales,
                                                               min_cosine=args.min_cosine,
                                                               max_relative_l2=args.max_relative_l2),
        "interpretation": "channel fallback reads the native signed A16 tensor, dequantizes using its channel-input scale, applies original FP32 weights and FP32 accumulation; it does not use original FP32 layer inputs",
    }
    mixed = attribution["mixed_candidate_search"]
    if mixed["status"] == "PASS":
        mixed_outputs, _, _ = _evaluate_masks((conv0, conv1), cases, scales,
                                              dw_channels=mixed["dw_fp32_channels"],
                                              pw_channels=mixed["pw_fp32_channels"])
        mixed["candidate_files"] = []
        for index, candidate in enumerate(mixed_outputs):
            candidate_path = args.output / f"image-{index:02d}-mixed-fp32-fallback.f32"
            candidate.astype("<f4").tofile(candidate_path)
            mixed["candidate_files"].append({"path": candidate_path.name,
                                               "sha256": file_sha256(candidate_path),
                                               "bytes": candidate_path.stat().st_size})
        mixed["per_case_gate"] = [{"case_index": i, "metrics": error_metrics(ref, out),
                                   "pass": error_metrics(ref, out)["cosine"] >= args.min_cosine
                                   and error_metrics(ref, out)["relative_l2"] <= args.max_relative_l2}
                                  for i, (ref, out) in enumerate(zip(references, mixed_outputs))]
        mixed["all_cases_pass"] = all(row["pass"] for row in mixed["per_case_gate"])
    base_pass = all(r["error_gate"]["pass"] for r in rows)
    mixed_pass = attribution["mixed_candidate_search"]["status"] == "PASS"
    status = "PASS" if base_pass else ("MIXED_PASS" if mixed_pass else "FAIL")
    report = {"schema_version": 2, "status": status,
              "base_w8a16_status": "PASS" if base_pass else "FAIL",
              "purpose": "local_integer_oracle_only; not a production ORT model",
              "contract": contract, "calibration": scales, "overflow_proofs": list(proof_by_name.values()),
              "runtime": {"onnxruntime": ort.__version__, "providers": reference_session.get_providers(), "threads": args.threads},
              "gate_policy": {"max_abs": args.max_abs, "min_cosine": args.min_cosine,
                              "max_relative_l2": args.max_relative_l2,
                              "score_gap_gate": "NOT_EVALUATED; N1 boundary is spatial activation, not final feature scores"},
              "cases": rows, "layer_error_attribution": attribution,
              "mixed_execution_contract": {
                  "status": attribution["mixed_candidate_search"]["status"],
                  "dw7": {"arithmetic": "W8/A16/Acc32 for every output channel except listed fallback channels",
                          "fallback_channels": attribution["mixed_candidate_search"].get("dw_fp32_channels", []),
                          "fallback_fraction": attribution["mixed_candidate_search"].get("dw_fp32_channel_fraction")},
                  "pw1": {"arithmetic": "W8/A16/Acc32 for every output channel except listed fallback channels",
                          "fallback_channels": attribution["mixed_candidate_search"].get("pw_fp32_channels", []),
                          "fallback_fraction": attribution["mixed_candidate_search"].get("pw_fp32_channel_fraction")},
                  "fallback_semantics": "native_a16_dequant_input_fp32_weights_accum; listed output channels dequantize the exact native A16 tensor and bypass the Acc32 MAC datapath; remaining channels use ties-even symmetric quantization and full-storage-domain Acc32 proof"},
              "timing_scope": "measured local CPU runtime; not target timing and not static MAC estimate"}
    result_path = args.output / "n1-w8a16-oracle.json"
    result_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    files = {path.name: {"bytes": path.stat().st_size, "sha256": file_sha256(path)}
             for path in sorted(args.output.iterdir()) if path.is_file()}
    receipt = {"schema_version": 1, "status": report["status"], "files": files,
               "source_model_sha256": contract["model_sha256"],
               "runtime": report["runtime"], "board_execution": False}
    (args.output / "receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    mixed_summary = attribution["mixed_candidate_search"]
    print(json.dumps({"status": report["status"], "base_w8a16_status": report["base_w8a16_status"],
                      "mixed_candidate_status": mixed_summary["status"],
                      "mixed_relative_l2": mixed_summary.get("metrics", {}).get("relative_l2"),
                      "mixed_cosine": mixed_summary.get("metrics", {}).get("cosine"),
                      "mixed_fallback_channel_fractions": {
                          "dw7": mixed_summary.get("dw_fp32_channel_fraction"),
                          "pw1": mixed_summary.get("pw_fp32_channel_fraction")},
                      "report": str(result_path),
                      "case_count": len(rows), "overflow_fits": all(p["bound"]["fits_signed32"] for p in proof_by_name.values()),
                      "max_abs": max(r["mixed_w8a16_vs_local_fp32"]["max_abs"] for r in rows),
                      "min_cosine": min(r["mixed_w8a16_vs_local_fp32"]["cosine"] for r in rows)}, indent=2))
    if report["status"] not in ("PASS", "MIXED_PASS"):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
