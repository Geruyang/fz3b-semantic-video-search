import hashlib
import json

import numpy as np
import pytest

from evaluate_cnn_v10_p3_suffix_domain import (
    _load_candidate, _load_capture, _load_capture_benchmark_result)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def make_capture(root):
    records = []
    for index in range(2):
        raw = np.full((1, 256, 16, 16), index + 1, dtype="<f4").tobytes()
        name = "suffix-input-%02d.f32" % index
        (root / name).write_bytes(raw)
        records.append({"capture_index": index, "first_infer_call": index,
                        "path": name, "bytes": len(raw), "sha256": sha(raw),
                        "dtype": "<f4", "shape": [1, 256, 16, 16]})
    manifest = {"schema": "cnn-v10.2-p3-suffix-input-capture-v1",
                "status": "CAPTURE_COMPLETE", "performance_valid": False,
                "first_occurrence_order_preserved": True, "max_distinct": 2,
                "distinct_count": 2, "infer_calls": 6, "records": records}
    raw = (json.dumps(manifest, sort_keys=True) + "\n").encode()
    path = root / "manifest.json"
    path.write_bytes(raw)
    return path, sha(raw)


def test_capture_and_benchmark_bind_ordered_domains(tmp_path):
    capture, capture_sha = make_capture(tmp_path)
    manifest, values = _load_capture(capture, capture_sha)
    assert manifest["infer_calls"] == 6
    assert [value[2] for value in values] == [
        manifest["records"][0]["sha256"], manifest["records"][1]["sha256"]]
    images = ["1" * 64, "2" * 64]
    references = ["3" * 64, "4" * 64]
    runner = "5" * 64
    result = {"status": "ENGINEERING_FEATURE_REGRESSION_PROTOCOL_CLEAN",
              "active_quantized_partitions": ["n1_pl"],
              "performance_valid": False,
              "suffix_input_capture": {"manifest_sha256": capture_sha},
              "input_tensor_sha256": images,
              "expected_feature_sha256": references,
              "runner_sha256": runner, "runner_sha256_after": runner}
    raw = (json.dumps(result, sort_keys=True) + "\n").encode()
    path = tmp_path / "result.json"
    path.write_bytes(raw)
    assert _load_capture_benchmark_result(
        path, sha(raw), capture_sha, images, references, runner)[0] == result
    result["input_tensor_sha256"] = list(reversed(images))
    raw = (json.dumps(result, sort_keys=True) + "\n").encode()
    path.write_bytes(raw)
    with pytest.raises(ValueError, match="domain identity"):
        _load_capture_benchmark_result(
            path, sha(raw), capture_sha, images, references, runner)


def test_candidate_identity_and_path_are_strict(tmp_path):
    model = tmp_path / "candidate.onnx"
    model.write_bytes(b"model")
    source_sha = "a" * 64
    manifest = {"schema": "cnn-v10.1-suffix-w8a8-selection-v2",
                "status": "PASS", "source_model_sha256": source_sha,
                "engineering_gate": {"pass": True},
                "candidate": {"path": model.name, "bytes": 5,
                              "sha256": sha(b"model")}}
    raw = (json.dumps(manifest, sort_keys=True) + "\n").encode()
    path = tmp_path / "selection.json"
    path.write_bytes(raw)
    loaded = _load_candidate("six=" + str(path), "six=" + sha(raw), source_sha)
    assert loaded[0] == "six" and loaded[3] == model
    manifest["candidate"]["path"] = "../escape.onnx"
    raw = (json.dumps(manifest, sort_keys=True) + "\n").encode()
    path.write_bytes(raw)
    with pytest.raises(ValueError, match="path invalid"):
        _load_candidate("six=" + str(path), "six=" + sha(raw), source_sha)
