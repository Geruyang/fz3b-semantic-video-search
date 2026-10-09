"""Suffix W8A8 QDQ candidate builder and float graph profiling utilities.

Outputs are research artifacts. This does not replace or modify the FP32-only
production runner and it does not establish board ORT 1.16 compatibility.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import time

import numpy as np
import onnx
import onnxruntime as ort


EXPECTED_SUFFIX_SHA256 = "b8a558830d31873f590f66b6fd3a8e8be269968855b9c21814129f36e4edb175"
QUANTIZED_OPS = ("Conv", "MatMul")
FP32_SENSITIVE_OPS = ("BatchNormalization", "Softmax", "Sigmoid", "Erf", "Div", "ReduceMean", "AveragePool")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _shape(value_info):
    tensor = value_info.type.tensor_type
    if not tensor.HasField("shape"):
        return None
    return [int(d.dim_value) if d.dim_value else (d.dim_param or None) for d in tensor.shape.dim]


def inspect_suffix(model_path: str | Path, *, require_frozen_hash: bool = True) -> dict:
    path = Path(model_path)
    digest = sha256_file(path)
    if require_frozen_hash and digest != EXPECTED_SUFFIX_SHA256:
        raise ValueError(f"unexpected suffix model SHA256: {digest}")
    model = onnx.load(str(path), load_external_data=True)
    onnx.checker.check_model(model)
    ops = Counter(n.op_type for n in model.graph.node)
    sensitive = [n.name for n in model.graph.node if n.op_type in FP32_SENSITIVE_OPS]
    candidates = [n.name for n in model.graph.node if n.op_type in QUANTIZED_OPS]
    shapes = {v.name: _shape(v) for v in list(model.graph.input) + list(model.graph.output) + list(model.graph.value_info)}
    inputs = [{"name": v.name, "shape": shapes.get(v.name), "elem_type": v.type.tensor_type.elem_type} for v in model.graph.input]
    outputs = [{"name": v.name, "shape": shapes.get(v.name), "elem_type": v.type.tensor_type.elem_type} for v in model.graph.output]
    return {"model_sha256": digest, "model_bytes": path.stat().st_size,
            "node_count": len(model.graph.node), "operator_counts": dict(sorted(ops.items())),
            "input": inputs, "output": outputs,
            "independent_layer_normalization_nodes": sum(n.op_type == "LayerNormalization" for n in model.graph.node),
            "quantization_candidate_ops": list(QUANTIZED_OPS),
            "quantization_candidate_node_names": candidates,
            "fp32_sensitive_ops": list(FP32_SENSITIVE_OPS),
            "fp32_sensitive_node_names": sensitive,
            "production_boundary": "FP32-only runner; this module only builds/analyzes a separate candidate"}


def _session(model_path: Path, *, profiling: bool = False, threads: int = 1, optimize: bool = True):
    options = ort.SessionOptions()
    options.intra_op_num_threads = threads
    options.inter_op_num_threads = 1
    options.enable_profiling = profiling
    if not optimize:
        options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_DISABLE_ALL
    return ort.InferenceSession(str(model_path), sess_options=options, providers=["CPUExecutionProvider"])


def profile_fp32(model_path: str | Path, sample_arrays: list[np.ndarray], *, threads: int = 1,
                 warmup: int = 1, repeats: int = 3) -> dict:
    path = Path(model_path)
    session = _session(path, profiling=True, threads=threads)
    input_name, output_name = session.get_inputs()[0].name, session.get_outputs()[0].name
    per_case = []
    all_events = []
    for index, x in enumerate(sample_arrays):
        if x.dtype != np.float32 or x.shape != (1, 256, 16, 16) or not np.isfinite(x).all():
            raise ValueError("suffix profile samples must be finite float32 [1,256,16,16]")
        for _ in range(warmup):
            session.run([output_name], {input_name: x})
        elapsed = []
        for _ in range(repeats):
            start = time.perf_counter()
            session.run([output_name], {input_name: x})
            elapsed.append((time.perf_counter() - start) * 1000)
        per_case.append({"sample_index": index, "wall_ms": elapsed,
                         "median_ms": float(np.median(elapsed)), "warmup_runs": warmup})
    profile_path = Path(session.end_profiling())
    try:
        events = json.loads(profile_path.read_text(encoding="utf-8"))
    finally:
        profile_path.unlink(missing_ok=True)
    node_events = [e for e in events if e.get("cat") == "Node" and e.get("ph") == "X"]
    for event in node_events:
        args = event.get("args", {})
        all_events.append({"name": event.get("name"), "op_name": args.get("op_name"),
                           "provider": args.get("provider"),
                           "dur_us": event.get("dur", 0), "input_type_shape": args.get("input_type_shape"),
                           "output_type_shape": args.get("output_type_shape")})
    aggregated = defaultdict(lambda: {"count": 0, "dur_us": 0.0, "provider_counts": Counter()})
    for event in all_events:
        key = (event.get("name"), event.get("op_name"))
        row = aggregated[key]
        row["count"] += 1
        row["dur_us"] += float(event["dur_us"])
        row["provider_counts"][str(event.get("provider"))] += 1
    by_node = [{"name": name, "op_type": op, "profile_events": row["count"],
                "total_profile_ms": row["dur_us"] / 1000,
                "providers": dict(row["provider_counts"])}
               for (name, op), row in aggregated.items()]
    by_node.sort(key=lambda row: row["total_profile_ms"], reverse=True)
    return {"runtime": {"onnxruntime": ort.__version__, "providers": session.get_providers(),
                        "threads": threads, "profile_sample_count": len(sample_arrays),
                        "profile_warmup_per_sample": warmup, "timed_repeats_per_sample": repeats},
            "samples": per_case, "profile_event_count": len(all_events),
            "profiled_node_count": len(by_node), "all_nodes_by_profile_time": by_node,
            "top_nodes_by_profile_time": by_node[:50],
            "timing_scope": "host ORT CPUExecutionProvider only; no board timing claim"}


def node_tensor_statistics(model_path: str | Path, sample_arrays: list[np.ndarray], *, threads: int = 1) -> dict:
    """Collect ranges from FP32 node outputs by exposing intermediates in a copy."""
    path = Path(model_path)
    model = onnx.load(str(path), load_external_data=True)
    inferred = onnx.shape_inference.infer_shapes(model, strict_mode=False, data_prop=True)
    info = {v.name: v for v in list(inferred.graph.value_info) + list(inferred.graph.output) + list(inferred.graph.input)}
    existing = {v.name for v in inferred.graph.output}
    names = []
    for node in inferred.graph.node:
        for name in node.output:
            if not name or name in existing or name not in info:
                continue
            vi = info[name]
            if vi.type.HasField("tensor_type") and vi.type.tensor_type.elem_type in (onnx.TensorProto.FLOAT, onnx.TensorProto.FLOAT16, onnx.TensorProto.DOUBLE):
                inferred.graph.output.append(vi)
                existing.add(name)
                names.append(name)
    import tempfile
    with tempfile.TemporaryDirectory(prefix="cnn_v10_suffix_intermediates_") as temp:
        augmented_path = Path(temp) / "suffix-intermediates.onnx"
        onnx.save(inferred, str(augmented_path))
        session = _session(augmented_path, threads=threads, optimize=False)
        input_name = session.get_inputs()[0].name
        output_names = [o.name for o in session.get_outputs()]
        stats = {}
        for sample_index, x in enumerate(sample_arrays):
            values = session.run(output_names, {input_name: np.asarray(x, dtype=np.float32)})
            for name, value in zip(output_names, values):
                if name not in names or not np.issubdtype(value.dtype, np.number) or not np.isfinite(value).all():
                    continue
                flat = value.astype(np.float64, copy=False).ravel()
                row = stats.setdefault(name, {"shape": list(value.shape), "dtype": str(value.dtype),
                                              "min": float("inf"), "max": float("-inf"),
                                              "max_abs": 0.0, "sum_abs": 0.0, "count": 0,
                                              "sample_count": 0})
                row["min"] = min(row["min"], float(flat.min()))
                row["max"] = max(row["max"], float(flat.max()))
                row["max_abs"] = max(row["max_abs"], float(np.max(np.abs(flat))))
                row["sum_abs"] += float(np.sum(np.abs(flat), dtype=np.float64))
                row["count"] += int(flat.size)
                row["sample_count"] += 1
    for row in stats.values():
        row["mean_abs"] = row.pop("sum_abs") / max(1, row["count"])
    return {"tensor_count": len(stats), "sample_count": len(sample_arrays),
            "tensors": stats,
            "method": "FP32 ORT outputs exposed on a temporary unoptimized graph copy; profiling uses original graph separately"}


class _Reader:
    def __init__(self, input_name: str, samples: list[np.ndarray]):
        self.input_name = input_name
        self.samples = samples
        self.position = 0

    def get_next(self):
        if self.position >= len(self.samples):
            return None
        value = self.samples[self.position]
        self.position += 1
        return {self.input_name: value}

    def rewind(self):
        self.position = 0


def build_qdq_candidate(model_path: str | Path, sample_arrays: list[np.ndarray], output_path: str | Path,
                        *, per_channel: bool = True, selected_node_names: list[str] | None = None) -> dict:
    from onnxruntime.quantization import CalibrationMethod, QuantFormat, QuantType, quantize_static

    source = Path(model_path)
    destination = Path(output_path)
    if destination.exists():
        raise FileExistsError(f"refusing to overwrite candidate: {destination}")
    model = onnx.load(str(source))
    available = [n.name for n in model.graph.node if n.op_type in QUANTIZED_OPS]
    selected_nodes = available if selected_node_names is None else list(selected_node_names)
    if len(selected_nodes) != len(set(selected_nodes)) or any(n not in available for n in selected_nodes):
        raise ValueError("quantization node selection contains duplicates or unsupported node names")
    selected_ops = sorted({n.op_type for n in model.graph.node if n.name in set(selected_nodes)})
    input_name = model.graph.input[0].name
    reader = _Reader(input_name, sample_arrays)
    quantize_static(str(source), str(destination), reader,
                    quant_format=QuantFormat.QDQ, activation_type=QuantType.QUInt8,
                    weight_type=QuantType.QInt8, calibrate_method=CalibrationMethod.MinMax,
                    per_channel=per_channel, op_types_to_quantize=selected_ops,
                    nodes_to_quantize=selected_nodes,
                    extra_options={"ActivationSymmetric": True, "WeightSymmetric": True})
    graph = onnx.load(str(destination))
    onnx.checker.check_model(graph)
    return {"candidate_path": str(destination), "candidate_sha256": sha256_file(destination),
            "candidate_bytes": destination.stat().st_size, "quantized_candidate_node_names": selected_nodes,
            "quantized_candidate_op_types": selected_ops,
            "quantized_node_count": len(selected_nodes), "weight_per_channel": per_channel,
            "activation": "QUInt8 symmetric QDQ MinMax", "weight": "QInt8 symmetric QDQ",
            "fp32_sensitive_node_names": [n.name for n in model.graph.node if n.op_type in FP32_SENSITIVE_OPS],
            "production_state": "experimental host candidate; production runner remains FP32-only"}


def compare_suffix(source_model: str | Path, candidate_model: str | Path,
                   samples: list[np.ndarray], *, threads: int = 1) -> dict:
    fp32 = _session(Path(source_model), threads=threads)
    qdq = _session(Path(candidate_model), threads=threads)
    if fp32.get_inputs()[0].name != qdq.get_inputs()[0].name:
        raise ValueError("FP32 and QDQ input names differ")
    fp_name, q_name = fp32.get_inputs()[0].name, qdq.get_inputs()[0].name
    fp_out, q_out = fp32.get_outputs()[0].name, qdq.get_outputs()[0].name
    reports = []
    for index, x in enumerate(samples):
        start = time.perf_counter()
        reference = fp32.run([fp_out], {fp_name: x})[0]
        fp_ms = (time.perf_counter() - start) * 1000
        start = time.perf_counter()
        actual = qdq.run([q_out], {q_name: x})[0]
        qdq_ms = (time.perf_counter() - start) * 1000
        a, b = reference.astype(np.float64).ravel(), actual.astype(np.float64).ravel()
        denominator = float(np.linalg.norm(a) * np.linalg.norm(b))
        cosine = float(np.dot(a, b) / denominator) if denominator else (1.0 if not np.any(b) else 0.0)
        reports.append({"sample_index": index, "max_abs": float(np.max(np.abs(a - b))),
                        "relative_l2": float(np.linalg.norm(a - b) / max(float(np.linalg.norm(a)), 1e-30)),
                        "cosine": cosine, "fp32_host_ms": fp_ms, "qdq_host_ms": qdq_ms})
    return {"runtime": {"onnxruntime": ort.__version__, "providers": qdq.get_providers(), "threads": threads},
            "samples": reports,
            "timing_scope": "host ORT CPUExecutionProvider only; excludes model setup and does not predict board performance"}
