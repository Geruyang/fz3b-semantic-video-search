"""HOST-only, isolated network.0 quantization preflight for the next PL profile.

Uses the existing audited integer arithmetic; never calls the board or changes
the frozen v4 hardware. Three regression images are not an accuracy dataset.
"""
import argparse
import json
from pathlib import Path

import numpy as np
import onnx
import onnxruntime as ort

import build_network2_int_oracle as integer
from stage4_network4_int_oracle import block_parameters
from stage4_network4_trace import INPUTS, MODEL_SHA256

LABELS = ("input", "dw3", "dw7", "pw1", "gelu", "pw2", "scale", "add")
SUFFIXES = ("/token_mixer/reparam_conv/Conv", "/convffn/conv/conv/Conv",
            "/convffn/fc1/Conv", "/convffn/act/Mul_1",
            "/convffn/fc2/Conv", "/Mul", "/Add")


def session(model):
    options = ort.SessionOptions()
    options.intra_op_num_threads = 1
    options.inter_op_num_threads = 1
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    return ort.InferenceSession(model.SerializeToString(), options,
                                providers=["CPUExecutionProvider"])


def raw(root, name, value, dtype):
    value = np.ascontiguousarray(value, dtype=dtype)
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    value.tofile(path)
    return {"path": name, "shape": list(value.shape), "dtype": dtype,
            "bytes": path.stat().st_size, "sha256": integer.sha256_file(path)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    model_path = args.source / "mobileclip_s1_image.onnx"
    if integer.sha256_file(model_path) != MODEL_SHA256:
        raise ValueError("source model identity mismatch")
    args.output.mkdir(parents=True, exist_ok=False)
    model = onnx.shape_inference.infer_shapes(onnx.load(str(model_path)))
    nodes = {node.name: node for node in model.graph.node}
    blocks = []
    for index in range(4):
        prefix = "/image_encoder/model/network.0/network.0.%d" % index
        names = dict(zip(LABELS[1:], (prefix + part for part in SUFFIXES)))
        selected = {label: nodes[name] for label, name in names.items()}
        input_name = selected["dw3"].input[0]
        outputs = {label: node.output[0] for label, node in selected.items()}
        if index and input_name != blocks[-1]["outputs"]["add"]:
            raise ValueError("network0 is not a continuous four-block chain")
        for label, kernel, group in (("dw3", 3, 64), ("dw7", 7, 64),
                                     ("pw1", 1, 1), ("pw2", 1, 1)):
            node = selected[label]
            attrs = {item.name: onnx.helper.get_attribute_value(item) for item in node.attribute}
            if (node.op_type != "Conv" or attrs.get("group", 1) != group or
                    attrs.get("kernel_shape") != [kernel, kernel] or
                    attrs.get("strides", [1, 1]) != [1, 1] or
                    attrs.get("dilations", [1, 1]) != [1, 1] or
                    attrs.get("pads", [0] * 4) != [kernel // 2] * 4):
                raise ValueError("unexpected network0 convolution semantics")
        if (selected["dw7"].input[0] != outputs["dw3"] or
                selected["pw1"].input[0] != outputs["dw7"] or
                selected["pw2"].input[0] != outputs["gelu"] or
                set(selected["add"].input) != {outputs["dw3"], outputs["scale"]} or
                outputs["pw2"] not in selected["scale"].input):
            raise ValueError("unexpected network0 residual/FFN wiring")
        blocks.append({"index": index, "input": input_name, "outputs": outputs, "nodes": names})
    extractor = onnx.utils.Extractor(model)
    fetches = [blocks[0]["input"]] + [b["outputs"][label] for b in blocks for label in LABELS[1:]]
    trace = session(extractor.extract_model(["image"], fetches))
    suffix = session(extractor.extract_model([blocks[-1]["outputs"]["add"]], ["features"]))
    full = session(model)
    samples = []
    for sample_id, name, digest in INPUTS:
        path = args.source / name
        if integer.sha256_file(path) != digest:
            raise ValueError("frozen input identity mismatch")
        image = np.fromfile(path, dtype="<f4").reshape(1, 3, 256, 256)
        values = [np.array(value, copy=True)[0] for value in trace.run(fetches, {"image": image})]
        if any(not np.isfinite(value).all() for value in values):
            raise ValueError("nonfinite FP32 trace")
        stage = []
        for index in range(4):
            record = dict(zip(LABELS[1:], values[1 + 7*index:8 + 7*index]))
            record["input"] = values[0] if index == 0 else stage[-1]["add"]
            for label, value in record.items():
                expected = (192, 64, 64) if label in ("pw1", "gelu") else (64, 64, 64)
                if value.shape != expected:
                    raise ValueError("unsupported network0 tensor shape")
            stage.append(record)
        samples.append({"id": sample_id, "input_sha256": digest, "blocks": stage,
                        "fp32_feature": np.array(full.run(["features"], {"image": image})[0], copy=True)})
    scales = []
    params = []
    layers = []
    manifests = []
    for index, block in enumerate(blocks):
        scale = {label: max(float(np.max(np.abs(s["blocks"][index][label].astype(np.float64))))
                            for s in samples) / 32767.0 for label in LABELS}
        scale = {key: value if value else 1.0 for key, value in scale.items()}
        if index:
            scale["input"] = scales[-1]["add"]
        layer = integer.extract_block_parameters(model, block)
        param, arrays = block_parameters(layer, scale)
        flat = {}
        for key, value in arrays.items():
            if isinstance(value, dict):
                flat.update({key + "__" + sub: item for sub, item in value.items()})
            else:
                flat[key] = value
        path = args.output / ("block-%02d-params.npz" % index)
        np.savez(path, **flat)
        bounds = {key: int(np.max(param[key]["worst_case_abs_including_bias"]))
                  for key in ("dw3", "dw7", "pw1", "pw2")}
        manifests.append({"block": index, "scales": scale, "accumulator_bounds": bounds,
                          "parameters": {"path": path.name, "bytes": path.stat().st_size,
                                         "sha256": integer.sha256_file(path)}})
        scales.append(scale); params.append(param); layers.append(layer)
    texts = np.fromfile(args.source / "text-features.f32", dtype="<f4").reshape(8, 512)
    ids = [item["id"] for item in json.loads((args.source / "manifest.json").read_text(encoding="utf-8"))["prompts"]]
    results = []
    for sample in samples:
        q = integer.quantize_symmetric(sample["blocks"][0]["input"], scales[0]["input"])
        records = [raw(args.output, sample["id"] + "/input.i16", q, "<i2")]
        diagnostics = []
        for index in range(4):
            q, detail = integer.execute_block(q, params[index], scales[index], layers[index],
                                               integer.gelu_lut(scales[index]["pw1"], scales[index]["gelu"]))
            records.append(raw(args.output, sample["id"] + "/block-%02d-add.i16" % index, q, "<i2"))
            diagnostics.append({"block": index, "saturated_codes": int(np.count_nonzero(np.abs(q.astype(np.int32)) == 32767)),
                                "metrics": integer.tensor_metrics(q.astype(np.float32) * np.float32(scales[index]["add"]),
                                                                  sample["blocks"][index]["add"])})
        dequant = (q.astype(np.float32) * np.float32(scales[-1]["add"]))[None]
        feature = suffix.run(["features"], {blocks[-1]["outputs"]["add"]: dequant})[0].copy()
        qrank = integer.rank_feature(feature, texts, ids)
        fprank = integer.rank_feature(sample["fp32_feature"], texts, ids)
        results.append({"sample_id": sample["id"], "input_sha256": sample["input_sha256"],
                        "files": records, "stages": diagnostics,
                        "feature": raw(args.output, sample["id"] + "/feature.f32", feature, "<f4"),
                        "fp32_feature": raw(args.output, sample["id"] + "/fp32-feature.f32", sample["fp32_feature"], "<f4"),
                        "feature_metrics": integer.tensor_metrics(feature, sample["fp32_feature"]),
                        "quantized_ranking": qrank, "fp32_ranking": fprank,
                        "full_ranking_preserved": qrank["ranking"] == fprank["ranking"]})
        print(sample["id"], results[-1]["feature_metrics"], "ranking=", results[-1]["full_ranking_preserved"], flush=True)
    report = {"status": "HOST_ISOLATED_NETWORK0_PREFLIGHT_NOT_PL", "pl_execution": False,
              "board_capture": False, "scope": "network0 four INT blocks; all other stages FP32",
              "model_sha256": MODEL_SHA256, "ort_version": ort.__version__,
              "script_sha256": integer.sha256_file(Path(__file__)),
              "integer_source_sha256": integer.sha256_file(Path(integer.__file__)),
              "text_features_sha256": integer.sha256_file(args.source / "text-features.f32"),
              "blocks": blocks, "parameters": manifests, "samples": results,
              "limitations": "Three old engineering images, not independent accuracy data; no combined N0/N2/N4 claim."}
    (args.output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
