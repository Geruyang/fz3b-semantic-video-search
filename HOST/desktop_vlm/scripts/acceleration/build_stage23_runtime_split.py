"""Persist and validate the Stage-2/3 CPU suffix models used around PL cuts."""

import argparse
import hashlib
import json
import shutil
from pathlib import Path

import numpy as np
import onnx
import onnxruntime as ort


MODEL_SHA256 = "5b8494a03aa81a59b2bd0a3f3dcba91813363bb65060c32d6e4bf4243f8e3587"
STAGE2_SHA256 = "68e2a29131ca0965783b00eea54049c313de669e1c758b738f4c530bb78cd282"
STAGE3_SHA256 = "164fdff3ab1a09e0b6282f4281ed09e7846cb44ace36ddbdca86ab57237e94c7"
PREFIX_SHA256 = "0f4b6674641af36dfab7448aa209cc4a3a4d002bf3f4be3a90ef9c2caaf88895"
PRE_DW3 = "/image_encoder/model/network.1/proj/proj.1/activation/Mul_1_output_0"
DW3_OUT = "/image_encoder/model/network.2/network.2.0/token_mixer/reparam_conv/Conv_output_0"
DW7_OUT = "/image_encoder/model/network.2/network.2.0/convffn/conv/conv/Conv_output_0"
ADD_NODE = "/image_encoder/model/network.2/network.2.0/Add"


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def metric(actual, expected):
    actual64 = actual.astype(np.float64)
    expected64 = expected.astype(np.float64)
    delta = actual64 - expected64
    flat_a = actual64.reshape(-1)
    flat_b = expected64.reshape(-1)
    norm = float(np.linalg.norm(flat_a) * np.linalg.norm(flat_b))
    return {
        "max_abs": float(np.max(np.abs(delta))),
        "rms_abs": float(np.sqrt(np.mean(delta * delta))),
        "relative_l2": float(np.linalg.norm(delta) /
                             max(float(np.linalg.norm(expected64)), 1e-30)),
        "cosine": float(np.dot(flat_a, flat_b) / max(norm, 1e-30)),
        "allclose_rtol_1e-4_atol_1e-5": bool(np.allclose(
            actual, expected, rtol=1e-4, atol=1e-5)),
    }


def check_metric(actual, frozen, label):
    for key in ("max_abs", "rms_abs", "relative_l2", "cosine"):
        if not np.isclose(actual[key], frozen[key], rtol=0.0, atol=1e-12):
            raise ValueError("%s metric differs at %s" % (label, key))
    if actual["allclose_rtol_1e-4_atol_1e-5"] != \
            frozen["allclose_rtol_1e-4_atol_1e-5"]:
        raise ValueError("%s allclose status differs" % label)


def session(model_path, threads):
    options = ort.SessionOptions()
    options.intra_op_num_threads = threads
    options.inter_op_num_threads = 1
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    ort.disable_telemetry_events()
    return ort.InferenceSession(str(model_path), options,
                                providers=["CPUExecutionProvider"])


def contract(value):
    shape = [int(item) for item in value.shape]
    if value.type != "tensor(float)" or any(item <= 0 for item in shape):
        raise ValueError("runtime split requires fixed FP32 tensors")
    return {"name": value.name, "dtype": "<f4", "shape": shape,
            "bytes": int(np.prod(shape)) * 4}


def save_model(model, path):
    onnx.checker.check_model(model)
    onnx.save(model, str(path))
    return {"path": path.name, "bytes": path.stat().st_size,
            "sha256": sha256(path)}


def build(args):
    model_path = Path(args.model)
    stage2_dir = Path(args.stage2)
    stage3_dir = Path(args.stage3)
    prefix_path = Path(args.prefix)
    board_feature_dir = Path(args.board_features)
    output = Path(args.output)
    if output.exists():
        raise ValueError("output directory already exists")
    identities = ((model_path, MODEL_SHA256, "source model"),
                  (stage2_dir / "manifest.json", STAGE2_SHA256, "stage2 B007"),
                  (stage3_dir / "manifest.json", STAGE3_SHA256, "stage3 004"),
                  (prefix_path, PREFIX_SHA256, "prefix model"))
    for path, expected, label in identities:
        if sha256(path) != expected:
            raise ValueError(label + " SHA256 mismatch")
    stage2 = json.loads((stage2_dir / "manifest.json").read_text(encoding="utf-8"))
    stage3 = json.loads((stage3_dir / "manifest.json").read_text(encoding="utf-8"))
    if stage3.get("stage2_b_manifest_sha256") != STAGE2_SHA256:
        raise ValueError("stage3 does not bind the accepted stage2 manifest")

    inferred = onnx.shape_inference.infer_shapes(onnx.load(str(model_path)))
    nodes = {item.name: item for item in inferred.graph.node}
    if ADD_NODE not in nodes:
        raise ValueError("network.2.0 Add node is missing")
    add_output = nodes[ADD_NODE].output[0]
    extractor = onnx.utils.Extractor(inferred)
    output.mkdir(parents=True)
    deployed_prefix_path = output / "prefix.onnx"
    shutil.copyfile(str(prefix_path), str(deployed_prefix_path))
    stage2_model_path = output / "stage2-suffix.onnx"
    stage3_model_path = output / "stage3-suffix.onnx"
    models = {
        "stage2_suffix": save_model(
            extractor.extract_model([DW3_OUT, DW7_OUT], ["features"]),
            stage2_model_path),
        "stage3_suffix": save_model(
            extractor.extract_model([add_output], ["features"]),
            stage3_model_path),
    }
    stage2_session = session(stage2_model_path, args.threads)
    stage3_session = session(stage3_model_path, args.threads)
    models["stage2_suffix"].update({
        "inputs": [contract(item) for item in stage2_session.get_inputs()],
        "outputs": [contract(item) for item in stage2_session.get_outputs()],
    })
    models["stage3_suffix"].update({
        "inputs": [contract(item) for item in stage3_session.get_inputs()],
        "outputs": [contract(item) for item in stage3_session.get_outputs()],
    })

    dw3_scales = np.fromfile(str(stage2_dir / "dw3-int16-accumulator-scales.f64"),
                             dtype="<f8")
    dw7_scales = np.fromfile(str(stage2_dir / "dw7-int16-accumulator-scales.f64"),
                             dtype="<f8")
    block_scale = np.fromfile(str(stage3_dir / "stage3-block-output-scale.f64"),
                              dtype="<f8")
    if dw3_scales.shape != (128,) or dw7_scales.shape != (128,) or \
            block_scale.shape != (1,):
        raise ValueError("stage scale file shape mismatch")
    cases = []
    for index in range(3):
        board_feature_path = board_feature_dir / ("image-%02d-partition.f32" % index)
        board_feature = np.fromfile(str(board_feature_path), dtype="<f4")
        expected_board_sha = stage3["results"][index]["board_ps_feature_sha256"]
        if (board_feature.shape != (512,) or sha256(board_feature_path) != expected_board_sha or
                expected_board_sha != stage2["results"][index]["pure_ps_feature_sha256"]):
            raise ValueError("board feature reference identity mismatch")

        dw3_raw = np.fromfile(str(stage2_dir / ("image-%02d-dw3-with-bias.i32" % index)),
                              dtype="<i4").reshape((128, 32, 32))
        dw7_raw = np.fromfile(str(stage2_dir / ("image-%02d-dw7-with-bias.i32" % index)),
                              dtype="<i4").reshape((128, 32, 32))
        # Both raw accumulator tensors already include quantized bias. Only the
        # per-channel accumulator scale is applied here.
        dw3_float = (dw3_raw.astype(np.float64) *
                     dw3_scales[:, None, None]).astype(np.float32)[None, :]
        dw7_float = (dw7_raw.astype(np.float64) *
                     dw7_scales[:, None, None]).astype(np.float32)[None, :]
        stage2_feature = stage2_session.run(
            None, {DW3_OUT: dw3_float, DW7_OUT: dw7_float})[0]
        stage2_metric = metric(stage2_feature.reshape(-1), board_feature)
        check_metric(stage2_metric, stage2["results"][index]["feature_vs_pure_ps"],
                     "stage2 image-%02d" % index)

        block = np.fromfile(
            str(stage3_dir / ("image-%02d-stage3-block-add-output.i16" % index)),
            dtype="<i2").reshape((1, 128, 32, 32))
        block_float = (block.astype(np.float64) * float(block_scale[0])).astype(np.float32)
        stage3_feature = stage3_session.run(None, {add_output: block_float})[0]
        stage3_metric = metric(stage3_feature.reshape(-1), board_feature)
        check_metric(stage3_metric,
                     stage3["results"][index]["feature_metrics"][
                         "quantized_stage3_final512_vs_pure_ps_feature"],
                     "stage3 image-%02d" % index)

        stage2_file = output / ("image-%02d-stage2-feature.f32" % index)
        stage3_file = output / ("image-%02d-stage3-feature.f32" % index)
        np.ascontiguousarray(stage2_feature, dtype="<f4").tofile(str(stage2_file))
        np.ascontiguousarray(stage3_feature, dtype="<f4").tofile(str(stage3_file))
        cases.append({
            "sample_id": "image-%02d" % index,
            "board_feature_sha256": expected_board_sha,
            "stage2": {"feature_sha256": sha256(stage2_file),
                       "feature_metrics": stage2_metric},
            "stage3": {"feature_sha256": sha256(stage3_file),
                       "feature_metrics": stage3_metric},
        })

    report = {
        "schema_version": 1,
        "status": "STAGE23_RUNTIME_SPLIT_HOST_VALIDATED_NOT_PL",
        "pl_execution": False,
        "source_model_sha256": MODEL_SHA256,
        "stage2_b_manifest_sha256": STAGE2_SHA256,
        "stage3_manifest_sha256": STAGE3_SHA256,
        "prefix": {"path": deployed_prefix_path.name,
                   "bytes": deployed_prefix_path.stat().st_size,
                   "sha256": PREFIX_SHA256,
                   "input": {"name": "image", "dtype": "<f4",
                             "shape": [1, 3, 256, 256], "bytes": 786432},
                   "output": {"name": PRE_DW3,
                              "dtype": "<f4", "shape": [1, 128, 32, 32],
                              "bytes": 524288}},
        "models": models,
        "cuts": {
            "stage2": {"pl_input": "pre-DW3 INT16 NCHW 262144 bytes",
                       "pl_output": "DW3 biased INT32 + DW7 biased INT32, one 1048576-byte packet",
                       "suffix_inputs": [DW3_OUT, DW7_OUT],
                       "ps_postprocess": "per-channel accumulator scale only; bias is already included"},
            "stage3": {"pl_input": "pre-DW3 INT16 NCHW 262144 bytes",
                       "pl_output": "network.2.0 Add INT16 NCHW 262144 bytes",
                       "suffix_inputs": [add_output],
                       "ps_postprocess": "multiply by stage3 block output scale"},
        },
        "ort": {"runtime": ort.__version__, "threads": args.threads,
                "execution_mode": "sequential", "provider": "CPUExecutionProvider"},
        "cases": cases,
        "checks": {"three_board_feature_references": True,
                   "stage2_biased_accumulator_scale_only": True,
                   "stage2_frozen_metrics_reproduced": True,
                   "stage3_frozen_metrics_reproduced": True,
                   "no_pl_execution": True},
    }
    manifest_path = output / "manifest.json"
    manifest_path.write_bytes((json.dumps(report, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    print(json.dumps({"output": str(output), "manifest_sha256": sha256(manifest_path),
                      "models": models}, indent=2, sort_keys=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="artifacts/board-debug-20261004/host/s1-onnx-001/mobileclip_s1_image.onnx")
    parser.add_argument("--stage2", default="artifacts/board-debug-20261004/acceleration/host/stage2-dw3-dw7-int16act-007")
    parser.add_argument("--stage3", default="artifacts/board-debug-20261004/acceleration/host/stage3-network20-int16-004")
    parser.add_argument("--prefix", default="artifacts/board-debug-20261004/acceleration/host/stage2-dw3-dw7-003/prefix.onnx")
    parser.add_argument("--board-features", default="artifacts/board-debug-20261004/acceleration/network/partition-001")
    parser.add_argument("--output", default="artifacts/board-debug-20261004/acceleration/host/stage23-runtime-split-001")
    parser.add_argument("--threads", type=int, choices=(1, 2, 4), default=2)
    build(parser.parse_args())


if __name__ == "__main__":
    main()
