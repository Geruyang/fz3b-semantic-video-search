"""Build a host-only, per-block trace split for MobileCLIP-S1 network.2.

The output contains a prefix, twelve independently runnable block models, and
one suffix.  Host traces are calibration references only.  They are never
labelled as tensors captured on the FZ3B PS.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import onnx
import onnxruntime as ort
from onnxruntime.tools.symbolic_shape_infer import SymbolicShapeInference


MODEL_SHA256 = "5b8494a03aa81a59b2bd0a3f3dcba91813363bb65060c32d6e4bf4243f8e3587"
INPUT_MANIFEST_SHA256 = "b11afa6e730ba04c164e6bc7a0fb40829227a6827614709abde19cbbffaff05a"
PARTITION_CLIENT_SHA256 = "30a35bd130de3e6c9a6850c73b890b251d25de37906286aa5739d98d76e95940"
PARTITION_RUNNER_SHA256 = "fe53666be409e9693a899bd08c29fe51f002f9a9894475c2e412b021c19e955c"
OLD_INPUTS = [
    ("image-00-input.f32", "bb1d68f60f660ef824270dac40b0211df4c235d58944bafcc831845c17809e51"),
    ("image-01-input.f32", "32693e16acc4ee99beef72f25546e3b19fbbc8fcdd0988df3884bc63da115c8d"),
    ("image-02-input.f32", "eaec02ff7d4ac81ca3f3e01f88395f56bc8c997f8a224d721dff3dcad756c0e0"),
]
TRACE_LABELS = ("dw3", "dw7", "pw1", "gelu", "pw2", "scale", "add")


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def block_node_names(index):
    base = "/image_encoder/model/network.2/network.2.%d" % index
    return {
        "dw3": base + "/token_mixer/reparam_conv/Conv",
        "dw7": base + "/convffn/conv/conv/Conv",
        "pw1": base + "/convffn/fc1/Conv",
        "gelu": base + "/convffn/act/Mul_1",
        "pw2": base + "/convffn/fc2/Conv",
        "scale": base + "/Mul",
        "add": base + "/Add",
    }


def _tensor_desc(value_info):
    tensor = value_info.type.tensor_type
    shape = [int(d.dim_value) for d in tensor.shape.dim]
    if tensor.elem_type != onnx.TensorProto.FLOAT or not shape or any(d <= 0 for d in shape):
        raise ValueError("trace split requires fixed FP32 tensor: " + value_info.name)
    return {"name": value_info.name, "shape": shape, "dtype": "<f4",
            "bytes": math.prod(shape) * 4}


def _save_model(model, path):
    onnx.checker.check_model(model)
    onnx.save(model, str(path))
    return {"path": path.name, "bytes": path.stat().st_size, "sha256": sha256(path)}


def _session(path, threads):
    options = ort.SessionOptions()
    options.intra_op_num_threads = threads
    options.inter_op_num_threads = 1
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    return ort.InferenceSession(str(path), options, providers=["CPUExecutionProvider"])


def _write_tensor(path, tensor, tensor_name):
    array = np.ascontiguousarray(tensor, dtype="<f4")
    if not np.isfinite(array).all():
        raise ValueError("non-finite host trace tensor: " + tensor_name)
    array.tofile(str(path))
    return {"path": path.as_posix(), "tensor_name": tensor_name,
            "shape": list(array.shape), "dtype": "<f4", "bytes": path.stat().st_size,
            "sha256": sha256(path),
            "provenance": "HOST_ORT_REFERENCE_ONLY_NOT_BOARD_PS_CAPTURE"}


def _validate_inputs(model_path, input_manifest_path, inputs_dir):
    if sha256(model_path) != MODEL_SHA256:
        raise ValueError("source model SHA256 mismatch")
    if sha256(input_manifest_path) != INPUT_MANIFEST_SHA256:
        raise ValueError("source input manifest SHA256 mismatch")
    source = json.loads(Path(input_manifest_path).read_text(encoding="utf-8"))
    for name, digest in OLD_INPUTS:
        record = source.get("files", {}).get(name)
        if not record or record.get("sha256") != digest:
            raise ValueError("source manifest input mismatch: " + name)
        if sha256(Path(inputs_dir) / name) != digest:
            raise ValueError("source tensor input mismatch: " + name)


def build(args):
    model_path = Path(args.model)
    input_manifest_path = Path(args.input_manifest)
    inputs_dir = Path(args.inputs_dir)
    output = Path(args.output)
    _validate_inputs(model_path, input_manifest_path, inputs_dir)
    output.mkdir(parents=True, exist_ok=False)
    host_dir = output / "host-reference"
    host_dir.mkdir()

    inferred = SymbolicShapeInference.infer_shapes(onnx.load(str(model_path)), auto_merge=True)
    nodes = list(inferred.graph.node)
    by_name = {node.name: node for node in nodes}
    if len(by_name) != len(nodes):
        raise ValueError("source model contains duplicate node names")
    infos = {item.name: item for item in
             list(inferred.graph.input) + list(inferred.graph.value_info) + list(inferred.graph.output)}
    blocks = []
    for index in range(12):
        names = block_node_names(index)
        try:
            selected = {label: by_name[name] for label, name in names.items()}
        except KeyError as error:
            raise ValueError("missing network.2 trace node: %s" % error)
        if selected["dw3"].op_type != "Conv" or selected["dw7"].op_type != "Conv" or \
                selected["pw1"].op_type != "Conv" or selected["pw2"].op_type != "Conv" or \
                selected["gelu"].op_type != "Mul" or selected["scale"].op_type != "Mul" or \
                selected["add"].op_type != "Add":
            raise ValueError("network.2 block operator contract changed at block %d" % index)
        input_name = selected["dw3"].input[0]
        outputs = {label: selected[label].output[0] for label in TRACE_LABELS}
        if index and input_name != blocks[-1]["outputs"]["add"]:
            raise ValueError("block %d input is not the preceding Add output" % index)
        blocks.append({"index": index, "input": input_name, "nodes": names, "outputs": outputs})

    extractor = onnx.utils.Extractor(inferred)
    image_name = inferred.graph.input[0].name
    feature_name = inferred.graph.output[0].name
    stage_models = {}
    prefix_model = extractor.extract_model([image_name], [blocks[0]["input"]])
    prefix_path = output / "prefix.onnx"
    stage_models["prefix"] = {
        **_save_model(prefix_model, prefix_path),
        "inputs": [_tensor_desc(infos[image_name])],
        "outputs": [_tensor_desc(infos[blocks[0]["input"]])],
    }
    for block in blocks:
        key = "block-%02d" % block["index"]
        model = extractor.extract_model([block["input"]],
                                        [block["outputs"][label] for label in TRACE_LABELS])
        path = output / (key + ".onnx")
        stage_models[key] = {
            **_save_model(model, path),
            "inputs": [_tensor_desc(infos[block["input"]])],
            "outputs": [_tensor_desc(infos[block["outputs"][label]])
                        for label in TRACE_LABELS],
        }
    suffix_model = extractor.extract_model([blocks[-1]["outputs"]["add"]], [feature_name])
    suffix_path = output / "suffix.onnx"
    stage_models["suffix"] = {
        **_save_model(suffix_model, suffix_path),
        "inputs": [_tensor_desc(infos[blocks[-1]["outputs"]["add"]])],
        "outputs": [_tensor_desc(infos[feature_name])],
    }

    ort.disable_telemetry_events()
    prefix_session = _session(prefix_path, args.threads)
    block_sessions = [_session(output / ("block-%02d.onnx" % index), args.threads)
                      for index in range(12)]
    suffix_session = _session(suffix_path, args.threads)
    full_session = _session(model_path, args.threads)
    samples = []
    for sample_index, (input_name, input_digest) in enumerate(OLD_INPUTS):
        raw = np.fromfile(str(inputs_dir / input_name), dtype="<f4")
        image = raw.reshape(tuple(stage_models["prefix"]["inputs"][0]["shape"]))
        full_feature = full_session.run(None, {image_name: image})[0]
        current = prefix_session.run(None, {image_name: image})[0]
        files = []
        continuity = []
        for block, session in zip(blocks, block_sessions):
            block_index = block["index"]
            input_file = host_dir / ("image-%02d-block-%02d-input.f32" %
                                     (sample_index, block_index))
            input_record = _write_tensor(input_file, current, block["input"])
            input_record["label"] = "input"
            input_record["block"] = block_index
            input_record["path"] = "host-reference/" + input_file.name
            files.append(input_record)
            values = session.run(None, {block["input"]: current})
            outputs = dict(zip([block["outputs"][label] for label in TRACE_LABELS], values))
            for label in TRACE_LABELS:
                path = host_dir / ("image-%02d-block-%02d-%s.f32" %
                                   (sample_index, block_index, label))
                record = _write_tensor(path, outputs[block["outputs"][label]],
                                       block["outputs"][label])
                record["label"] = label
                record["block"] = block_index
                record["path"] = "host-reference/" + path.name
                files.append(record)
            next_value = outputs[block["outputs"]["add"]]
            if block_index < 11:
                continuity.append({"from_block": block_index, "to_block": block_index + 1,
                                   "same_in_memory_tensor": True,
                                   "sha256": hashlib.sha256(np.ascontiguousarray(
                                       next_value, dtype="<f4").tobytes()).hexdigest()})
            current = next_value
        split_feature = suffix_session.run(None,
                                           {blocks[-1]["outputs"]["add"]: current})[0]
        delta = split_feature.astype(np.float64) - full_feature.astype(np.float64)
        max_abs = float(np.max(np.abs(delta)))
        if not np.allclose(split_feature, full_feature, rtol=1e-3, atol=1e-4):
            raise ValueError("host split feature check failed for image-%02d" % sample_index)
        samples.append({"sample_id": "image-%02d" % sample_index,
                        "source_input": input_name, "input_sha256": input_digest,
                        "files": files, "continuity": continuity,
                        "split_vs_full_feature_max_abs": max_abs})

    collector_source = Path("desktop_vlm/board/collect_network2_block_traces.py")
    if not collector_source.is_file():
        raise ValueError("board collector source must exist before freezing split")
    manifest = {
        "schema_version": 1,
        "status": "HOST_NETWORK2_TRACE_SPLIT_VALIDATED_NOT_BOARD_PS_CAPTURE",
        "scope": "MobileCLIP-S1 network.2 blocks 0..11 per-block trace",
        "source_model": {"path": str(model_path.resolve()), "sha256": MODEL_SHA256},
        "source_old_input_manifest": {"path": str(input_manifest_path.resolve()),
                                      "sha256": INPUT_MANIFEST_SHA256},
        "trace_labels": list(TRACE_LABELS),
        "blocks": blocks,
        "stages": stage_models,
        "host_reference": {
            "status": "HOST_ORT_REFERENCE_ONLY_NOT_BOARD_PS_CAPTURE",
            "runtime": ort.__version__, "threads": args.threads,
            "samples": samples,
        },
        "three_old_preprocessed_inputs": [
            {"path": name, "shape": [1, 3, 256, 256], "dtype": "<f4",
             "bytes": 786432, "sha256": digest} for name, digest in OLD_INPUTS],
        "collector": {
            "source": "desktop_vlm/board/collect_network2_block_traces.py",
            "source_sha256": sha256(collector_source),
            "partition_client_source_sha256": PARTITION_CLIENT_SHA256,
            "partition_runner_binary_sha256": PARTITION_RUNNER_SHA256,
            "execution": "FZ3B PS CPUExecutionProvider only; no PL/DMA access",
        },
        "checks": {
            "all_12_blocks_present": len(blocks) == 12,
            "each_block_has_7_named_outputs": all(len(item["outputs"]) == 7 for item in blocks),
            "block_add_to_next_input_chain_exact_by_tensor_name": True,
            "host_reference_kept_separate_from_future_board_ps_collection": True,
        },
    }
    manifest_path = output / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False,
                                        sort_keys=True) + "\n", encoding="utf-8")
    result = {"output": str(output.resolve()), "manifest_sha256": sha256(manifest_path),
              "status": manifest["status"], "blocks": 12,
              "host_trace_files": sum(len(item["files"]) for item in samples),
              "samples": [{"sample_id": item["sample_id"],
                           "split_vs_full_feature_max_abs": item["split_vs_full_feature_max_abs"]}
                          for item in samples]}
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="artifacts/board-debug-20261004/host/s1-onnx-001/mobileclip_s1_image.onnx")
    parser.add_argument("--input-manifest", default="artifacts/board-debug-20261004/host/s1-onnx-001/manifest.json")
    parser.add_argument("--inputs-dir", default="artifacts/board-debug-20261004/host/s1-onnx-001")
    parser.add_argument("--output", required=True, help="must be a new directory")
    parser.add_argument("--threads", type=int, choices=(1, 2, 4), default=4)
    build(parser.parse_args())


if __name__ == "__main__":
    main()
