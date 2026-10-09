"""Independently verify FZ3B PS network.2 traces against frozen host traces."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import onnxruntime as ort


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def metric(actual, expected):
    a = actual.astype(np.float64).ravel()
    e = expected.astype(np.float64).ravel()
    delta = a - e
    denom = float(np.linalg.norm(a) * np.linalg.norm(e))
    cosine = float(np.dot(a, e) / denom) if denom else (1.0 if np.array_equal(a, e) else 0.0)
    return {"max_abs": float(np.max(np.abs(delta))),
            "rms": float(np.sqrt(np.mean(delta * delta))),
            "cosine": cosine,
            "byte_exact": bool(np.array_equal(actual, expected))}


def read_tensor(path, record):
    if path.stat().st_size != record["bytes"] or sha256(path) != record["sha256"]:
        raise ValueError("tensor size/SHA mismatch: " + str(path))
    if record["dtype"] != "<f4":
        raise ValueError("unexpected tensor dtype: " + str(path))
    value = np.fromfile(str(path), dtype="<f4").reshape(tuple(record["shape"]))
    if not np.isfinite(value).all():
        raise ValueError("non-finite tensor: " + str(path))
    return value


def verify(args):
    board_dir = Path(args.board_dir)
    split_dir = Path(args.split_dir)
    board_path = board_dir / "board-ps-collection-manifest.json"
    split_path = split_dir / "manifest.json"
    if sha256(board_path) != args.board_manifest_sha256:
        raise ValueError("board collection manifest SHA mismatch")
    if sha256(split_path) != args.split_manifest_sha256:
        raise ValueError("split manifest SHA mismatch")
    board = json.loads(board_path.read_text(encoding="utf-8"))
    split = json.loads(split_path.read_text(encoding="utf-8"))
    if board.get("split_manifest_sha256") != args.split_manifest_sha256:
        raise ValueError("board collection points at a different split")
    if board.get("status") != "BOARD_PS_CPU_NETWORK2_BLOCK_TRACE_COLLECTION":
        raise ValueError("board collection status is not accepted")

    host_samples = {item["sample_id"]: item for item in split["host_reference"]["samples"]}
    records = []
    continuity = []
    for case in board["cases"]:
        sample_id = case["sample_id"]
        host_files = {(item["block"], item["label"]): item
                      for item in host_samples[sample_id]["files"]}
        board_by_block = {item["block"]: item for item in case["blocks"]}
        for block_index in range(12):
            board_block = board_by_block[block_index]
            for label in ("input", "dw3", "dw7", "pw1", "gelu", "pw2", "scale", "add"):
                board_record = board_block["files"][label]
                host_record = host_files[(block_index, label)]
                board_value = read_tensor(board_dir / sample_id / board_record["path"], board_record)
                host_value = read_tensor(split_dir / host_record["path"], host_record)
                if board_record["tensor_name"] != host_record["tensor_name"] or \
                        list(board_value.shape) != list(host_value.shape):
                    raise ValueError("host/board tensor contract mismatch")
                records.append({"sample_id": sample_id, "block": block_index,
                                "label": label, "tensor_name": board_record["tensor_name"],
                                "board_sha256": board_record["sha256"],
                                "host_sha256": host_record["sha256"],
                                "metrics": metric(board_value, host_value)})
            if block_index < 11:
                add_record = board_block["files"]["add"]
                next_record = board_by_block[block_index + 1]["files"]["input"]
                add_path = board_dir / sample_id / add_record["path"]
                next_path = board_dir / sample_id / next_record["path"]
                exact = add_path.read_bytes() == next_path.read_bytes()
                continuity.append({"sample_id": sample_id, "from_block": block_index,
                                   "to_block": block_index + 1,
                                   "add_sha256": add_record["sha256"],
                                   "next_input_sha256": next_record["sha256"],
                                   "byte_exact": exact})
                if not exact:
                    raise ValueError("board Add-to-next-input continuity failed")

    options = ort.SessionOptions()
    options.intra_op_num_threads = 4
    options.inter_op_num_threads = 1
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    session = ort.InferenceSession(args.model, options, providers=["CPUExecutionProvider"])
    feature_records = []
    for case in board["cases"]:
        sample_id = case["sample_id"]
        source_name = case["source_input"]["path"]
        source_path = Path(args.inputs_dir) / source_name
        if sha256(source_path) != case["source_input"]["sha256"]:
            raise ValueError("source input identity mismatch: " + sample_id)
        image = np.fromfile(str(source_path), dtype="<f4").reshape((1, 3, 256, 256))
        host_feature = session.run(None, {session.get_inputs()[0].name: image})[0]
        board_feature = read_tensor(board_dir / case["feature"]["path"], case["feature"])
        metrics = metric(board_feature, host_feature)
        feature_records.append({"sample_id": sample_id,
                                "board_sha256": case["feature"]["sha256"],
                                "host_feature_sha256": hashlib.sha256(np.ascontiguousarray(
                                    host_feature, dtype="<f4").tobytes()).hexdigest(),
                                "metrics": metrics,
                                "allclose_atol_1e_6_rtol_1e_5": bool(np.allclose(
                                    board_feature, host_feature, atol=1e-6, rtol=1e-5))})

    report = {
        "schema_version": 1,
        "status": "PASS_IDENTITY_CONTINUITY_WITH_CROSS_ORT_METRICS",
        "board_collection_manifest_sha256": args.board_manifest_sha256,
        "split_manifest_sha256": args.split_manifest_sha256,
        "source_model_sha256": sha256(args.model),
        "comparison": "FZ3B PS ORT 1.16.3 vs host ORT %s; host tensors are not board goldens" %
                      ort.__version__,
        "tensor_records": records,
        "continuity": continuity,
        "feature_records": feature_records,
        "summary": {
            "tensor_count": len(records),
            "continuity_edges": len(continuity),
            "byte_exact_tensor_count": sum(item["metrics"]["byte_exact"] for item in records),
            "max_tensor_max_abs": max(item["metrics"]["max_abs"] for item in records),
            "max_tensor_rms": max(item["metrics"]["rms"] for item in records),
            "min_tensor_cosine": min(item["metrics"]["cosine"] for item in records),
            "all_feature_thresholds_pass": all(item["allclose_atol_1e_6_rtol_1e_5"]
                                                for item in feature_records),
            "max_feature_max_abs": max(item["metrics"]["max_abs"] for item in feature_records),
            "min_feature_cosine": min(item["metrics"]["cosine"] for item in feature_records),
        },
    }
    output = Path(args.output)
    payload = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode("utf-8")
    output.write_bytes(payload)
    if output.read_bytes() != payload:
        raise RuntimeError("verification report readback mismatch")
    print(json.dumps({"output": str(output.resolve()), "sha256": sha256(output),
                      "status": report["status"], "summary": report["summary"]}, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--board-dir", required=True)
    parser.add_argument("--board-manifest-sha256", required=True)
    parser.add_argument("--split-dir", required=True)
    parser.add_argument("--split-manifest-sha256", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--inputs-dir", required=True)
    parser.add_argument("--output", required=True)
    verify(parser.parse_args())


if __name__ == "__main__":
    main()
