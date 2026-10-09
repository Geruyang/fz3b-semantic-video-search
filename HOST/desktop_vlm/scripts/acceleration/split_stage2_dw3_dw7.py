"""Freeze the network.2.0 DW3->DW7 CPU partition and independent host references.

The generated ONNX partitions can be executed on the board CPU by
``desktop_vlm/board/collect_stage2_dw3_dw7.py``. Host references emitted here
are explicitly independent comparisons, never actual-board PS goldens.
"""
import argparse
import hashlib
import json
import math
import tempfile
from pathlib import Path

import numpy as np
import onnx
import onnxruntime as ort
from onnxruntime.tools.symbolic_shape_infer import SymbolicShapeInference


MODEL_SHA256 = "5b8494a03aa81a59b2bd0a3f3dcba91813363bb65060c32d6e4bf4243f8e3587"
INPUT_MANIFEST_SHA256 = "b11afa6e730ba04c164e6bc7a0fb40829227a6827614709abde19cbbffaff05a"
PARTITION_CLIENT_SHA256 = "30a35bd130de3e6c9a6850c73b890b251d25de37906286aa5739d98d76e95940"
PARTITION_RUNNER_SHA256 = "fe53666be409e9693a899bd08c29fe51f002f9a9894475c2e412b021c19e955c"
DW3_NODE = "/image_encoder/model/network.2/network.2.0/token_mixer/reparam_conv/Conv"
DW7_NODE = "/image_encoder/model/network.2/network.2.0/convffn/conv/conv/Conv"
OLD_INPUTS = [
    ("image-00-input.f32", "bb1d68f60f660ef824270dac40b0211df4c235d58944bafcc831845c17809e51"),
    ("image-01-input.f32", "32693e16acc4ee99beef72f25546e3b19fbbc8fcdd0988df3884bc63da115c8d"),
    ("image-02-input.f32", "eaec02ff7d4ac81ca3f3e01f88395f56bc8c997f8a224d721dff3dcad756c0e0"),
]
INPUTS_DIR_DEFAULT = Path("artifacts/board-debug-20261004/host/s1-onnx-001")
UPSTREAM = {
    "ffn_split_001": ("artifacts/board-debug-20261004/acceleration/host/ffn-split-001/manifest.json",
                      "86b0f1816e7a5350390abfd7538bd071b3701106d980b8c31036869fb42d23a7"),
    "stage2_split_001": ("artifacts/board-debug-20261004/acceleration/host/stage2-split-001/manifest.json",
                         "e2c05aa4257c7384fdc2975dab4c7ac33fb1dc6b72f6dbdd1400cc219f113c0b"),
    "ffn_int8_001": ("artifacts/board-debug-20261004/acceleration/host/ffn-int8-001/manifest.json",
                     "5f3a5cceacaa9ab637f470f181cd3e2cf6d5bd8d77e69f702c645b0316ec4a24"),
}


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _tensor_desc(value_info):
    tensor = value_info.type.tensor_type
    shape = [dimension.dim_value for dimension in tensor.shape.dim]
    if tensor.elem_type != onnx.TensorProto.FLOAT or not shape or any(d <= 0 for d in shape):
        raise ValueError("stage2 contract only supports fixed FP32 tensor: " + value_info.name)
    count = math.prod(shape)
    return {"name": value_info.name, "shape": shape, "dtype": "<f4",
            "bytes": count * 4}


def _conv_contract(node, expected_kernel):
    attrs = {attribute.name: onnx.helper.get_attribute_value(attribute)
             for attribute in node.attribute}
    if node.op_type != "Conv" or attrs.get("group") != 128:
        raise ValueError("stage2 requires depthwise Conv with groups=128: " + node.name)
    if list(attrs.get("kernel_shape", [])) != [expected_kernel, expected_kernel]:
        raise ValueError("stage2 depthwise kernel mismatch: " + node.name)
    if list(attrs.get("strides", [])) != [1, 1]:
        raise ValueError("stage2 depthwise stride must be 1: " + node.name)
    return {"op_type": node.op_type, "group": attrs["group"],
            "kernel_shape": list(attrs["kernel_shape"]),
            "strides": list(attrs["strides"]), "pads": list(attrs.get("pads", []))}


def _save_model(model, path):
    onnx.checker.check_model(model)
    onnx.save(model, str(path))
    return {"path": path.name, "bytes": path.stat().st_size, "sha256": sha256(path)}


def _make_live_cut(nodes, cut, static, producer, graph_outputs):
    needed = {value.name for value in graph_outputs}
    needed.update(name for node in nodes[cut:] for name in node.input if name)
    return sorted(name for name in needed
                  if name not in static and producer.get(name, -1) < cut)


def build(args):
    model_path = Path(args.model)
    input_manifest_path = Path(args.input_manifest)
    if sha256(model_path) != MODEL_SHA256:
        raise ValueError("model SHA256 mismatch; expected pinned MobileCLIP-S1 model")
    if sha256(input_manifest_path) != INPUT_MANIFEST_SHA256:
        raise ValueError("old-input manifest SHA256 mismatch")
    input_manifest = json.loads(input_manifest_path.read_text(encoding="utf-8"))
    for name, digest in OLD_INPUTS:
        record = input_manifest.get("files", {}).get(name)
        if not record or record.get("sha256", "").lower() != digest:
            raise ValueError("old input identity mismatch in source manifest: " + name)
    inputs_dir = Path(args.inputs_dir)
    for name, digest in OLD_INPUTS:
        path = inputs_dir / name
        if sha256(path) != digest:
            raise ValueError("old preprocessed tensor SHA256 mismatch: " + str(path))

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    host_dir = output / "host-reference"
    host_dir.mkdir()

    inferred = SymbolicShapeInference.infer_shapes(onnx.load(str(model_path)), auto_merge=True)
    nodes = list(inferred.graph.node)
    first = [index for index, node in enumerate(nodes) if node.name == DW3_NODE]
    last = [index for index, node in enumerate(nodes) if node.name == DW7_NODE]
    if len(first) != 1 or len(last) != 1 or first[0] >= last[0]:
        raise ValueError("expected unique topological DW3 then DW7 nodes")
    lo, hi = first[0], last[0]
    if hi != lo + 1:
        raise ValueError("DW3 and DW7 no longer form a contiguous two-node stage")
    first_contract = _conv_contract(nodes[lo], 3)
    last_contract = _conv_contract(nodes[hi], 7)

    initializers = {item.name for item in inferred.graph.initializer}
    constants = {name for node in nodes if node.op_type == "Constant" for name in node.output}
    static = initializers | constants
    producer = {name: index for index, node in enumerate(nodes) for name in node.output}
    cut_before = _make_live_cut(nodes, lo, static, producer, inferred.graph.output)
    cut_after = _make_live_cut(nodes, hi + 1, static, producer, inferred.graph.output)
    region_inputs = sorted({name for node in nodes[lo:hi + 1] for name in node.input
                            if name and name not in static and producer.get(name, -1) < lo})
    region_outputs = [name for name in cut_after
                      if lo <= producer.get(name, -1) <= hi]
    bypass = [name for name in cut_after if producer.get(name, -1) < lo]
    dw3_output, dw7_output = nodes[lo].output[0], nodes[hi].output[0]
    if dw3_output not in region_outputs or dw7_output not in region_outputs:
        raise ValueError("stage cut lost the DW3 intermediate or DW7 output")

    extractor = onnx.utils.Extractor(inferred)
    stage_specs = {
        "prefix": (extractor.extract_model([v.name for v in inferred.graph.input], cut_before),
                   "prefix.onnx"),
        "region": (extractor.extract_model(region_inputs, region_outputs), "region.onnx"),
    }
    info = {item.name: item for item in
            list(inferred.graph.input) + list(inferred.graph.value_info) + list(inferred.graph.output)}
    stage_records = {}
    for stage, (stage_model, filename) in stage_specs.items():
        path = output / filename
        stage_hash = _save_model(stage_model, path)
        stage_records[stage] = {
            **stage_hash,
            "inputs": [_tensor_desc(info[name]) for name in
                       ([v.name for v in inferred.graph.input] if stage == "prefix" else region_inputs)],
            "outputs": [_tensor_desc(info[name]) for name in
                        (cut_before if stage == "prefix" else region_outputs)],
        }

    suffix_model = extractor.extract_model(cut_after, [v.name for v in inferred.graph.output])
    onnx.checker.check_model(suffix_model)
    options = ort.SessionOptions()
    options.intra_op_num_threads = args.threads
    options.inter_op_num_threads = 1
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    ort.disable_telemetry_events()
    prefix_session = ort.InferenceSession(str(output / "prefix.onnx"), options,
                                          providers=["CPUExecutionProvider"])
    region_session = ort.InferenceSession(str(output / "region.onnx"), options,
                                          providers=["CPUExecutionProvider"])
    full_session = ort.InferenceSession(str(model_path), options,
                                        providers=["CPUExecutionProvider"])
    with tempfile.TemporaryDirectory(prefix="stage2_dw3_dw7_suffix_") as temporary:
        suffix_path = Path(temporary) / "suffix.onnx"
        onnx.save(suffix_model, str(suffix_path))
        suffix_session = ort.InferenceSession(str(suffix_path), options,
                                              providers=["CPUExecutionProvider"])
        samples = []
        for index, (input_name, input_digest) in enumerate(OLD_INPUTS):
            input_path = inputs_dir / input_name
            image = np.fromfile(str(input_path), dtype="<f4")
            if image.size != 3 * 256 * 256 or not np.isfinite(image).all():
                raise ValueError("invalid fixed old preprocessed NCHW tensor: " + str(input_path))
            image = image.reshape((1, 3, 256, 256))
            full_features = full_session.run(None, {"image": image})[0]
            prefix_values = prefix_session.run(None, {"image": image})
            values = {spec.name: value for spec, value in
                      zip(prefix_session.get_outputs(), prefix_values)}
            stage_inputs = {name: values[name] for name in region_inputs}
            region_values = region_session.run(None, stage_inputs)
            values.update({spec.name: value for spec, value in
                           zip(region_session.get_outputs(), region_values)})
            suffix_inputs = {name: values[name] for name in cut_after}
            split_features = suffix_session.run(None, suffix_inputs)[0]
            np.testing.assert_allclose(split_features, full_features, rtol=1e-3, atol=1e-4)
            files = {}
            for label, tensor_name, tensor in [
                    ("pre-dw3", cut_before[0], values[cut_before[0]]),
                    ("dw3-output", dw3_output, values[dw3_output]),
                    ("dw7-output", dw7_output, values[dw7_output])]:
                filename = "image-%02d-%s.f32" % (index, label)
                path = host_dir / filename
                array = np.ascontiguousarray(tensor, dtype="<f4")
                array.tofile(str(path))
                files[label] = {"path": "host-reference/" + filename,
                                "tensor_name": tensor_name, "shape": list(array.shape),
                                "dtype": "<f4", "bytes": path.stat().st_size,
                                "sha256": sha256(path),
                                "provenance": "independent_host_ort_reference_not_board_ps_golden"}
            samples.append({"sample_id": "image-%02d" % index,
                            "source_input": input_name, "input_sha256": input_digest,
                            "host_reference_files": files,
                            "full_model_feature_max_abs": float(np.max(np.abs(
                                split_features.astype(np.float64) - full_features.astype(np.float64))))})

    upstream = {}
    for name, (relative_path, expected_hash) in UPSTREAM.items():
        path = Path(relative_path)
        if sha256(path) != expected_hash:
            raise ValueError("pinned upstream reference changed: " + relative_path)
        upstream[name] = {"path": relative_path, "manifest_sha256": expected_hash,
                          "use": "inventory_only_not_stage2_dw3_dw7_reference"}
    collector_source = Path("desktop_vlm/board/collect_stage2_dw3_dw7.py")
    manifest = {
        "schema_version": 1,
        "status": "STAGE2_DW3_TO_DW7_PARTITION_HOST_VALIDATED_NOT_BOARD_CAPTURE",
        "scope": "MobileCLIP-S1 image_encoder.model.network.2.network.2.0 DW3 -> DW7",
        "source_model": {"path": str(model_path.resolve()), "sha256": MODEL_SHA256},
        "source_old_input_manifest": {"path": str(input_manifest_path.resolve()),
                                       "sha256": INPUT_MANIFEST_SHA256},
        "boundary": {
            "input_tensor": cut_before[0], "inputs": [_tensor_desc(info[name]) for name in cut_before],
            "dw3_node": DW3_NODE, "dw3_contract": first_contract, "dw3_output": dw3_output,
            "dw7_node": DW7_NODE, "dw7_contract": last_contract, "dw7_output": dw7_output,
            "output_tensors": [_tensor_desc(info[name]) for name in region_outputs],
            "preserved_bypass_tensors": [_tensor_desc(info[name]) for name in bypass],
            "stage3_starts_after": DW7_NODE,
        },
        "stages": stage_records,
        "host_reference": {"status": "INDEPENDENT_HOST_ORT_ONLY_NOT_ACTUAL_BOARD_PS_GOLDEN",
                           "runtime": ort.__version__, "threads": args.threads,
                           "suffix_model_persisted": False,
                           "suffix_check": "ephemeral extracted suffix compared with full source model",
                           "samples": samples},
        "three_old_preprocessed_inputs": [
            {"path": name, "shape": [1, 3, 256, 256], "dtype": "<f4",
             "bytes": 786432, "sha256": digest} for name, digest in OLD_INPUTS],
        "existing_reference_inventory": upstream,
        "collector": {"source": "desktop_vlm/board/collect_stage2_dw3_dw7.py",
                      "source_sha256": sha256(collector_source),
                      "partition_client_source_sha256": PARTITION_CLIENT_SHA256,
                      "partition_runner_binary_sha256": PARTITION_RUNNER_SHA256,
                      "execution": "board PS CPUExecutionProvider only; does not access PL",
                      "board_provenance_recorded_by_collector": True},
    }
    manifest_path = output / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False,
                                        sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output.resolve()), "manifest_sha256": sha256(manifest_path),
                      "dw3_output": dw3_output, "dw7_output": dw7_output,
                      "host_reference_only": True,
                      "samples": [{"sample_id": item["sample_id"],
                                   "input_sha256": item["input_sha256"],
                                   "full_model_feature_max_abs": item["full_model_feature_max_abs"]}
                                  for item in samples]}, indent=2, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="artifacts/board-debug-20261004/host/s1-onnx-001/mobileclip_s1_image.onnx")
    parser.add_argument("--input-manifest", default="artifacts/board-debug-20261004/host/s1-onnx-001/manifest.json")
    parser.add_argument("--inputs-dir", default=str(INPUTS_DIR_DEFAULT))
    parser.add_argument("--output", required=True, help="must be a new output directory")
    parser.add_argument("--threads", type=int, choices=(1, 2, 4), default=4)
    build(parser.parse_args())


if __name__ == "__main__":
    main()
