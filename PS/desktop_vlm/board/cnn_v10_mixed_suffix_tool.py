"""Build local suffix profiling/calibration artifacts and a separate QDQ model."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import tempfile

import numpy as np
import onnx

from cnn_v10_mixed_suffix import (build_qdq_candidate, compare_suffix, inspect_suffix,
                                  node_tensor_statistics, profile_fp32, sha256_file)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_inputs(root: Path) -> list[tuple[Path, np.ndarray]]:
    rows = []
    for index in range(3):
        path = root / f"image-{index:02d}" / "board" / "suffix-input.f32"
        if path.stat().st_size != 256 * 16 * 16 * 4:
            raise ValueError(f"bad suffix fixture size: {path}")
        x = np.fromfile(path, dtype="<f4").reshape((1, 256, 16, 16)).astype(np.float32, copy=False)
        if not np.isfinite(x).all():
            raise ValueError(f"nonfinite suffix fixture: {path}")
        rows.append((path, x))
    return rows


def _gate(comparison: dict, *, max_abs: float, min_cosine: float, max_relative_l2: float) -> dict:
    rows = comparison["samples"]
    for row in rows:
        row["error_gate"] = {"max_abs_limit": max_abs, "min_cosine": min_cosine,
                             "max_relative_l2": max_relative_l2,
                             "pass": row["max_abs"] <= max_abs and row["cosine"] >= min_cosine
                             and row["relative_l2"] <= max_relative_l2}
    return {"two_image_pass": len(rows) >= 2 and all(r["error_gate"]["pass"] for r in rows[:2]),
            "three_image_pass": len(rows) >= 3 and all(r["error_gate"]["pass"] for r in rows[:3]),
            "per_case": [r["error_gate"] for r in rows]}


def _hot_groups(model_path: Path) -> list[dict]:
    model = onnx.load(str(model_path))
    nodes = [n for n in model.graph.node if n.op_type in ("Conv", "MatMul")]
    groups = []
    conv_by_region = {}
    for node in nodes:
        name = node.name
        if node.op_type == "Conv":
            groups.append({"id": f"conv-node:{name}", "label": f"single Conv transition {name}", "new_nodes": [name]})
            region = next((f"convffn-block-{i}" for i in range(4) if f"network.7.{i}/convffn/" in name), None)
            if region:
                conv_by_region.setdefault(region, []).append(name)
        else:
            block = next((i for i in range(4) if f"network.7.{i}/" in name), None)
            if block is None:
                continue  # keep the final embedding head FP32
            groups.append({"id": f"matmul-node:{name}", "label": f"single MatMul hotspot {name}", "new_nodes": [name]})
    for region, region_nodes in sorted(conv_by_region.items()):
        groups.append({"id": region, "label": f"complete ConvFFN region {region}", "new_nodes": region_nodes})
    return groups


def _search_hot_groups(model_path: Path, samples: list[np.ndarray], output_dir: Path, *,
                       threads: int, max_abs: float, min_cosine: float,
                       max_relative_l2: float, profile: dict) -> dict:
    groups = _hot_groups(model_path)
    name_to_time = {}
    per_run_count = max(1, len(samples) * (profile["runtime"]["profile_warmup_per_sample"]
                                             + profile["runtime"]["timed_repeats_per_sample"]))
    for row in profile["all_nodes_by_profile_time"]:
        name_to_time[row["name"]] = float(row["total_profile_ms"]) / per_run_count

    def hotspot_ms(group):
        total = 0.0
        for node_name in group["new_nodes"]:
            matches = [ms for profile_name, ms in name_to_time.items()
                       if node_name in profile_name or profile_name.startswith(node_name)]
            total += max(matches, default=0.0)
        return total

    for group in groups:
        group["host_profile_hotspot_ms_per_run"] = hotspot_ms(group)
    single_trials = []
    with tempfile.TemporaryDirectory(prefix="cnn_v10_suffix_qdq_search_") as temp:
        for step, group in enumerate(groups):
            selected = list(group["new_nodes"])
            candidate_path = Path(temp) / f"candidate-{step:02d}.onnx"
            build = build_qdq_candidate(model_path, samples, candidate_path,
                                        selected_node_names=selected)
            comparison = compare_suffix(model_path, candidate_path, samples, threads=threads)
            gate = _gate(comparison, max_abs=max_abs, min_cosine=min_cosine,
                         max_relative_l2=max_relative_l2)
            single_trials.append({"step": step, "group_tested": group["id"], "group_label": group["label"],
                           "new_node_names": group["new_nodes"],
                           "host_profile_hotspot_ms_per_run": group["host_profile_hotspot_ms_per_run"],
                           "quantized_node_count": len(selected),
                           "candidate_sha256": build["candidate_sha256"],
                           "two_image_pass": gate["two_image_pass"],
                           "three_image_pass": gate["three_image_pass"],
                           "per_case": comparison["samples"],
                           "runtime": comparison["runtime"]})

    eligible = [trial for trial in single_trials if trial["three_image_pass"]]
    eligible.sort(key=lambda trial: trial["host_profile_hotspot_ms_per_run"], reverse=True)
    chosen_nodes = []
    accepted_groups = []
    cumulative_trials = []
    with tempfile.TemporaryDirectory(prefix="cnn_v10_suffix_qdq_cumulative_") as temp:
        for step, trial in enumerate(eligible):
            delta = [name for name in trial["new_node_names"] if name not in chosen_nodes]
            if not delta:
                continue
            proposal = chosen_nodes + delta
            candidate_path = Path(temp) / f"cumulative-{step:02d}.onnx"
            build = build_qdq_candidate(model_path, samples, candidate_path,
                                        selected_node_names=proposal)
            comparison = compare_suffix(model_path, candidate_path, samples, threads=threads)
            gate = _gate(comparison, max_abs=max_abs, min_cosine=min_cosine,
                         max_relative_l2=max_relative_l2)
            accepted = gate["three_image_pass"]
            cumulative_trials.append({"group_added": trial["group_tested"], "new_nodes": delta,
                                      "host_profile_hotspot_ms_per_run": trial["host_profile_hotspot_ms_per_run"],
                                      "quantized_node_count": len(proposal),
                                      "candidate_sha256": build["candidate_sha256"],
                                      "two_image_pass": gate["two_image_pass"],
                                      "three_image_pass": gate["three_image_pass"],
                                      "accepted_into_final": accepted,
                                      "per_case": comparison["samples"]})
            if accepted:
                chosen_nodes = proposal
                accepted_groups.append(trial["group_tested"])

    chosen_path = output_dir / "suffix-w8a8-qdq-candidate.onnx"
    if chosen_nodes:
        chosen_build = build_qdq_candidate(model_path, samples, chosen_path,
                                           selected_node_names=chosen_nodes)
    else:
        import shutil
        shutil.copyfile(model_path, chosen_path)
        chosen_build = {"candidate_path": str(chosen_path), "candidate_sha256": sha256_file(chosen_path),
                        "candidate_bytes": chosen_path.stat().st_size,
                        "quantized_candidate_node_names": [], "quantized_node_count": 0,
                        "production_state": "FP32 fallback copy; no individual quantized group passed"}
    chosen_comparison = compare_suffix(model_path, chosen_path, samples, threads=threads)
    chosen_gate = _gate(chosen_comparison, max_abs=max_abs, min_cosine=min_cosine,
                        max_relative_l2=max_relative_l2)
    return {"strategy": "test each Conv transition and ConvFFN region individually; test MatMul nodes individually; greedily combine only gate-passing groups in host-profile hotspot order",
            "groups": groups, "single_group_trials": single_trials,
            "cumulative_trials": cumulative_trials, "accepted_groups": accepted_groups,
            "selection_reason": "retain only individually and cumulatively passing groups, ordered by measured FP32 host profile hotspot; target per-node profile is unavailable locally",
            "chosen_candidate": chosen_build,
            "chosen_comparison": chosen_comparison, "chosen_gate": chosen_gate,
            "head_projection_matmul": "kept FP32 as a sensitive output head",
            "two_image_gate": chosen_gate["two_image_pass"],
            "three_image_gate": chosen_gate["three_image_pass"]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--fixture-root", type=Path, default=Path("artifacts/board-debug-20261005/acceleration/host/network-w16-same-board-golden-001"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--max-abs", type=float, default=0.02)
    parser.add_argument("--min-cosine", type=float, default=0.999)
    parser.add_argument("--max-relative-l2", type=float, default=0.05)
    parser.add_argument("--skip-qdq", action="store_true")
    parser.add_argument("--search-hot-groups", action="store_true",
                        help="test cumulative Conv-first, then MatMul hotspot groups with 2/3-image gates")
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite output directory: {args.output}")
    args.output.mkdir(parents=True)
    loaded = read_inputs(args.fixture_root)
    samples = [x for _, x in loaded]
    contract = inspect_suffix(args.model)
    profile = profile_fp32(args.model, samples, threads=args.threads, warmup=args.warmup, repeats=args.repeats)
    tensors = node_tensor_statistics(args.model, samples, threads=args.threads)
    candidate_result = None
    comparison = None
    search_result = None
    if args.search_hot_groups:
        search_result = _search_hot_groups(args.model, samples, args.output, threads=args.threads,
                                           max_abs=args.max_abs, min_cosine=args.min_cosine,
                                           max_relative_l2=args.max_relative_l2,
                                           profile=profile)
        candidate_result = search_result["chosen_candidate"]
        comparison = search_result["chosen_comparison"]
    elif not args.skip_qdq:
        candidate_path = args.output / "suffix-w8a8-qdq-candidate.onnx"
        candidate_result = build_qdq_candidate(args.model, samples, candidate_path)
        comparison = compare_suffix(args.model, candidate_path, samples, threads=args.threads)
        _gate(comparison, max_abs=args.max_abs, min_cosine=args.min_cosine,
              max_relative_l2=args.max_relative_l2)
    report = {"schema_version": 1, "purpose": "suffix FP32 per-node profile and W8A8 QDQ research candidate",
              "source_contract": contract,
              "fixtures": [{"path": str(path), "sha256": sha256_file(path), "shape": list(x.shape)} for path, x in loaded],
              "fp32_node_profile": profile, "fp32_node_tensor_ranges": tensors,
              "qdq_candidate": candidate_result, "qdq_comparison": comparison,
              "qdq_gate": search_result["chosen_gate"] if search_result else {
                  "max_abs_limit": args.max_abs, "min_cosine": args.min_cosine,
                  "max_relative_l2": args.max_relative_l2,
                  "two_image_pass": all(i["error_gate"]["pass"] for i in comparison["samples"][:2]) if comparison else None,
                  "three_image_pass": all(i["error_gate"]["pass"] for i in comparison["samples"][:3]) if comparison else None},
              "hot_group_search": search_result,
              "sensitive_fp32_boundary": "BatchNormalization(4), Softmax(4), Sigmoid(2), Erf(7), Div(7), ReduceMean(2), AveragePool(1); only Conv/MatMul selected for QDQ",
              "production_boundary": "production runner remains FP32-only; host candidate does not establish target ORT 1.16.3 or board execution",
              "timing_boundary": "all times measured on local CPU ORT; no static MAC substituted for timing"}
    path = args.output / "suffix-mixed-profile.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    files = {p.name: {"bytes": p.stat().st_size, "sha256": file_sha256(p)}
             for p in sorted(args.output.iterdir()) if p.is_file()}
    receipt = {"schema_version": 1, "status": "PASS" if comparison and report["qdq_gate"].get("three_image_pass") else ("PROFILE_ONLY" if comparison is None else "QD_CANDIDATE_FAIL"),
               "files": files, "source_model_sha256": contract["model_sha256"],
               "onnxruntime": profile["runtime"]["onnxruntime"], "board_execution": False,
               "production_runner_fp32_only": True}
    (args.output / "receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    pass_gate = comparison and report["qdq_gate"].get("three_image_pass", report["qdq_gate"].get("pass", False))
    print(json.dumps({"status": "PASS" if pass_gate else ("PROFILE_ONLY" if comparison is None else "QD_CANDIDATE_FAIL"),
                      "report": str(path), "fp32_profile_events": profile["profile_event_count"],
                      "tensor_stats": tensors["tensor_count"],
                      "qdq_gate": report["qdq_gate"]}, indent=2))
    if comparison and not pass_gate:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
