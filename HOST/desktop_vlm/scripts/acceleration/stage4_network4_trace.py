"""Build and collect CPU traces for MobileCLIP-S1 network.4.0..19.

The collector is intended to run with CPUExecutionProvider on the FZ3B PS.
It makes no PL/DMA/JTAG or network calls. A trace from the workstation is
labelled HOST_ONLY and must never be used as board-calibrated evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import onnxruntime as ort


MODEL_SHA256 = "5b8494a03aa81a59b2bd0a3f3dcba91813363bb65060c32d6e4bf4243f8e3587"
INPUT_MANIFEST_SHA256 = "b11afa6e730ba04c164e6bc7a0fb40829227a6827614709abde19cbbffaff05a"
INPUTS = (
    ("image-00", "image-00-input.f32", "bb1d68f60f660ef824270dac40b0211df4c235d58944bafcc831845c17809e51"),
    ("image-01", "image-01-input.f32", "32693e16acc4ee99beef72f25546e3b19fbbc8fcdd0988df3884bc63da115c8d"),
    ("image-02", "image-02-input.f32", "eaec02ff7d4ac81ca3f3e01f88395f56bc8c997f8a224d721dff3dcad756c0e0"),
)
BLOCK_COUNT = 20
LABELS = ("input", "dw3", "dw7", "pw1", "gelu", "pw2", "scale", "add")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def nodes_for(index: int):
    base = f"/image_encoder/model/network.4/network.4.{index}"
    paths = {
        "dw3": "/token_mixer/reparam_conv/Conv",
        "dw7": "/convffn/conv/conv/Conv",
        "pw1": "/convffn/fc1/Conv",
        "gelu": "/convffn/act/Mul_1",
        "pw2": "/convffn/fc2/Conv",
        "scale": "/Mul",
        "add": "/Add",
    }
    return {key: base + suffix for key, suffix in paths.items()}


def session(model_path: Path, threads: int):
    options = ort.SessionOptions()
    options.intra_op_num_threads = threads
    options.inter_op_num_threads = 1
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    ort.disable_telemetry_events()
    return ort.InferenceSession(str(model_path), options,
                                providers=["CPUExecutionProvider"])


def write_array(root: Path, relative: str, array, dtype):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    packed = np.ascontiguousarray(array, dtype=dtype)
    packed.tofile(path)
    return {"path": relative.replace("\\", "/"), "dtype": dtype,
            "shape": list(packed.shape), "bytes": path.stat().st_size,
            "sha256": sha256(path)}


def build(args):
    import onnx

    source = Path(args.model)
    inputs_dir = Path(args.inputs_dir)
    input_manifest = Path(args.input_manifest)
    if sha256(source) != MODEL_SHA256:
        raise ValueError("pinned MobileCLIP-S1 ONNX SHA mismatch")
    if sha256(input_manifest) != INPUT_MANIFEST_SHA256:
        raise ValueError("pinned three-input manifest SHA mismatch")
    input_info = json.loads(input_manifest.read_text(encoding="utf-8"))
    for sample_id, name, digest in INPUTS:
        record = input_info.get("files", {}).get(name)
        path = inputs_dir / name
        if not record or record.get("sha256") != digest or sha256(path) != digest:
            raise ValueError("frozen real input mismatch: " + name)

    model = onnx.shape_inference.infer_shapes(onnx.load(str(source)), check_type=True)
    nodes = {node.name: node for node in model.graph.node}
    block_specs = []
    for index in range(BLOCK_COUNT):
        names = nodes_for(index)
        if any(name not in nodes for name in names.values()):
            raise ValueError(f"network.4.{index} has a missing expected node")
        block_input = nodes[names["dw3"]].input[0]
        outputs = {label: nodes[node_name].output[0]
                   for label, node_name in names.items()}
        if index and block_input != block_specs[-1]["outputs"]["add"]:
            raise ValueError(f"broken Add-to-input tensor chain at network.4.{index}")
        block_specs.append({"index": index, "input": block_input,
                            "nodes": names, "outputs": outputs})

    graph_input = model.graph.input[0].name
    feature_output = "features"
    stage_input = block_specs[0]["input"]
    stage_output = block_specs[-1]["outputs"]["add"]
    extractor = onnx.utils.Extractor(model)
    output = Path(args.output)
    if output.exists():
        raise FileExistsError(f"refusing to overwrite {output}")
    output.mkdir(parents=True)
    segments = {}
    for name, feeds, fetches in (
            ("prefix", [graph_input], [stage_input]),
            ("network4-region", [stage_input], [stage_output]),
            ("suffix", [stage_output], [feature_output])):
        segment = extractor.extract_model(feeds, fetches)
        onnx.checker.check_model(segment)
        path = output / f"{name}.onnx"
        onnx.save(segment, str(path))
        segments[name] = {"path": path.name, "bytes": path.stat().st_size,
                          "sha256": sha256(path),
                          "inputs": [item.name for item in segment.graph.input],
                          "outputs": [item.name for item in segment.graph.output]}

    # One trace graph emits all eight named boundaries for each block. This is
    # retained as host reference and can also be executed by PS CPU ORT.
    trace_model = extractor.extract_model(
        [block_specs[0]["input"]], [block_specs[0]["input"]] +
        [block["outputs"][label] for block in block_specs for label in LABELS[1:]])
    onnx.checker.check_model(trace_model)
    trace_path = output / "network4-trace.onnx"
    onnx.save(trace_model, str(trace_path))
    segments["trace"] = {"path": trace_path.name, "bytes": trace_path.stat().st_size,
                         "sha256": sha256(trace_path)}

    # Package exact preprocessed inputs for reproducible PS collection.
    input_files = {}
    for sample_id, name, digest in INPUTS:
        target = output / "inputs" / name
        target.parent.mkdir(exist_ok=True)
        target.write_bytes((inputs_dir / name).read_bytes())
        input_files[name] = {"path": f"inputs/{name}", "sha256": digest,
                             "bytes": target.stat().st_size, "shape": [1, 3, 256, 256],
                             "dtype": "<f4", "sample_id": sample_id}

    manifest = {
        "schema_version": 1,
        "status": "NETWORK4_TRACE_PACKAGE_READY_NOT_BOARD_PS_CAPTURE",
        "scope": {"first_block": "network.4.0", "last_block": "network.4.19",
                  "block_count": BLOCK_COUNT, "trace_labels": list(LABELS),
                  "source_onnx_sha256": MODEL_SHA256,
                  "input_tensor": stage_input, "output_tensor": stage_output,
                  "suffix_feature_tensor": feature_output},
        "shapes_from_onnx_shape_inference": _shape_contract(model, block_specs, onnx),
        "segments": segments,
        "source_inputs": {"manifest_path": str(input_manifest),
                          "manifest_sha256": INPUT_MANIFEST_SHA256,
                          "preprocessed_f32": input_files},
        "blocks": block_specs,
        "capture_contract": {"execution_provider": "CPUExecutionProvider on PS",
                             "provenance_required": "BOARD_PS",
                             "per_sample_per_block": list(LABELS),
                             "tensor_dtype": "little-endian float32",
                             "pl_execution": False,
                             "host_trace_is_calibration_only": True},
        "builder_runtime": {"onnx": onnx.__version__},
    }
    (output / "package.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                                          encoding="utf-8")
    print(json.dumps({"output": str(output.resolve()), "blocks": BLOCK_COUNT,
                      "segments": segments,
                      "source_inputs": input_files,
                      "package_sha256": sha256(output / "package.json")}, indent=2))


def _shape_contract(model, blocks, onnx):
    infos = {item.name: item for item in
             list(model.graph.value_info) + list(model.graph.output) + list(model.graph.input)}
    contract = {}
    for index, block in enumerate(blocks):
        tensors = {}
        for label, tensor_name in [("input", block["input"])] + list(block["outputs"].items()):
            value = infos.get(tensor_name)
            if value is None:
                raise ValueError("ONNX shape inference omitted tensor " + tensor_name)
            tensor = value.type.tensor_type
            shape = [int(dim.dim_value) for dim in tensor.shape.dim]
            if tensor.elem_type != onnx.TensorProto.FLOAT or not shape or any(not d for d in shape):
                raise ValueError("expected fixed FP32 tensor: " + tensor_name)
            tensors[label] = {"tensor": tensor_name, "shape": shape, "dtype": "<f4",
                              "bytes": math.prod(shape) * 4}
        contract[str(index)] = tensors
    return contract


def collect(args):
    package_dir = Path(args.package)
    manifest = json.loads((package_dir / "package.json").read_text(encoding="utf-8"))
    if manifest["status"] != "NETWORK4_TRACE_PACKAGE_READY_NOT_BOARD_PS_CAPTURE":
        raise ValueError("unsupported trace package status")
    trace_path = package_dir / manifest["segments"]["trace"]["path"]
    if sha256(trace_path) != manifest["segments"]["trace"]["sha256"]:
        raise ValueError("network4 trace ONNX SHA mismatch")
    prefix_session = session(package_dir / manifest["segments"]["prefix"]["path"], args.threads)
    trace_session = session(trace_path, args.threads)
    final_add = manifest["scope"]["output_tensor"]
    suffix_session = session(package_dir / manifest["segments"]["suffix"]["path"], args.threads)
    out = Path(args.output)
    if out.exists():
        raise FileExistsError(f"refusing to overwrite {out}")
    out.mkdir(parents=True)
    sample_records = []
    block_specs = manifest["blocks"]
    output_names = [item.name for item in trace_session.get_outputs()]
    if len(output_names) != 1 + BLOCK_COUNT * (len(LABELS) - 1):
        raise ValueError("unexpected trace output count")
    for sample_id, name, digest in INPUTS:
        input_path = package_dir / "inputs" / name
        if sha256(input_path) != digest:
            raise ValueError("packaged input SHA mismatch: " + name)
        image = np.fromfile(input_path, dtype="<f4").reshape((1, 3, 256, 256))
        feed_name = prefix_session.get_inputs()[0].name
        boundary = prefix_session.run(None, {feed_name: image})[0]
        stage_input_name = manifest["scope"]["input_tensor"]
        trace_outputs = trace_session.run(None, {stage_input_name: boundary})
        if trace_outputs[0].shape != boundary.shape or not np.array_equal(trace_outputs[0], boundary):
            raise ValueError("network4 trace model input passthrough mismatch")
        file_records = []
        by_node = {}
        cursor = 1
        for block in block_specs:
            per_block = {}
            for label in LABELS[1:]:
                value = trace_outputs[cursor]
                cursor += 1
                tensor_name = block["outputs"][label]
                if not np.isfinite(value).all():
                    raise ValueError(f"nonfinite output at {block['index']}:{label}")
                entry = write_array(out, f"{sample_id}/block-{block['index']:02d}-{label}.f32",
                                    value, "<f4")
                entry.update({"block": block["index"], "label": label,
                              "tensor_name": tensor_name})
                file_records.append(entry)
                per_block[label] = value
            input_value = boundary if block["index"] == 0 else by_node[block["index"] - 1]["add"]
            entry = write_array(out, f"{sample_id}/block-{block['index']:02d}-input.f32",
                                input_value, "<f4")
            entry.update({"block": block["index"], "label": "input",
                          "tensor_name": block["input"]})
            file_records.append(entry)
            per_block["input"] = input_value
            by_node[block["index"]] = per_block
        same_run_feature = suffix_session.run(["features"], {final_add: trace_outputs[-1]})[0]
        feature_ref = write_array(out, f"{sample_id}/suffix-feature.f32", same_run_feature, "<f4")
        sample_records.append({"sample_id": sample_id, "input_sha256": digest,
                               "stage4_input_sha256": hashlib.sha256(
                                   np.ascontiguousarray(boundary, dtype="<f4").tobytes()).hexdigest(),
                               "files": file_records, "suffix_feature": feature_ref})
    provenance = "BOARD_PS" if args.board_ps else "HOST_ONLY"
    report = {"schema_version": 1,
              "status": "BOARD_PS_CPU_NETWORK4_TRACE_COLLECTION" if args.board_ps else
                        "HOST_NETWORK4_TRACE_REFERENCE_NOT_BOARD_PS_CAPTURE",
              "provenance": provenance, "claim": "PS CPU ORT traces; no PL execution",
              "package_sha256": sha256(package_dir / "package.json"),
              "source_model_sha256": MODEL_SHA256,
              "blocks": block_specs, "samples": sample_records,
              "runtime": {"onnx_builder_version": manifest.get("builder_runtime", {}).get("onnx"),
                          "onnxruntime": ort.__version__,
                          "provider": "CPUExecutionProvider", "threads": args.threads},
              "checks": {"three_frozen_real_preprocessed_inputs": True,
                         "all_20_blocks_and_8_boundaries": True,
                         "same_run_suffix_feature": True, "pl_execution": False}}
    for path in sorted(out.rglob("*")):
        if path.is_file():
            report.setdefault("files", {})[path.relative_to(out).as_posix()] = {
                "bytes": path.stat().st_size, "sha256": sha256(path)}
    manifest_path = out / "manifest.json"
    manifest_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(out.resolve()), "status": report["status"],
                      "manifest_sha256": sha256(manifest_path),
                      "tensor_file_count": sum(len(sample["files"]) for sample in sample_records)},
                     indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    pbuild = sub.add_parser("build")
    pbuild.add_argument("--model", default="artifacts/board-debug-20261004/host/s1-onnx-001/mobileclip_s1_image.onnx")
    pbuild.add_argument("--input-manifest", default="artifacts/board-debug-20261004/host/s1-onnx-001/manifest.json")
    pbuild.add_argument("--inputs-dir", default="artifacts/board-debug-20261004/host/s1-onnx-001")
    pbuild.add_argument("--output", required=True)
    pbuild.set_defaults(func=build)
    pcollect = sub.add_parser("collect")
    pcollect.add_argument("--package", required=True)
    pcollect.add_argument("--output", required=True)
    pcollect.add_argument("--threads", type=int, default=2)
    pcollect.add_argument("--board-ps", action="store_true")
    pcollect.set_defaults(func=collect)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
