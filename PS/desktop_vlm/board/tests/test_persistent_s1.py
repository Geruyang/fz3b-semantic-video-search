import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pytest

from persistent_s1 import OrtStreamClient, _require_unit_norm_text_features, _write_all
from benchmark_s1 import summarize


INPUT_BYTES = 3 * 256 * 256 * 4
OUTPUT_BYTES = 512 * 4


def test_summarize_reports_percentiles_and_extrema():
    summary = summarize([1.0, 2.0, 3.0, 4.0])
    assert summary["count"] == 4
    assert summary["min"] == 1.0
    assert summary["max"] == 4.0
    assert summary["mean"] == 2.5
    assert summary["p50"] == 2.5
    assert summary["p95"] == pytest.approx(3.85)


def test_write_all_retries_partial_writes():
    class PartialWriter(object):
        def __init__(self):
            self.data = bytearray()

        def write(self, chunk):
            piece = bytes(chunk[:3])
            self.data.extend(piece)
            return len(piece)

    writer = PartialWriter()
    _write_all(writer, b"abcdefgh")
    assert bytes(writer.data) == b"abcdefgh"


def test_write_all_rejects_zero_progress():
    class BlockedWriter(object):
        def write(self, chunk):
            return 0

    with pytest.raises(IOError, match="short write"):
        _write_all(BlockedWriter(), b"frame")


def test_text_feature_cache_rejects_non_unit_rows():
    features = np.zeros((8, 512), dtype=np.float32)
    features[:, 0] = 2.0
    with pytest.raises(ValueError, match="unit norm"):
        _require_unit_norm_text_features(features)


def test_text_feature_cache_accepts_unit_rows():
    features = np.zeros((8, 512), dtype=np.float32)
    features[:, 0] = 1.0
    norms = _require_unit_norm_text_features(features)
    assert norms.shape == (8,)
    assert np.all(np.abs(norms - 1.0) <= 1.0e-5)


def make_runner(tmp_path, mode="ok"):
    path = tmp_path / "fake_runner.py"
    source = r'''import json, os, struct, sys
mode = MODE
ready = {"kind":"ready", "ort_version":"1.16.3", "api_version":16,
         "input_name":"image", "output_name":"features",
         "input_shape":[1,3,256,256], "output_shape":[1,512],
         "threads":2, "load_ms":12.5}
if mode == "bad_metadata":
    ready["output_shape"] = [1, 511]
if mode == "bad_api_version":
    ready["api_version"] = 15
sys.stdout.write(json.dumps(ready) + "\n")
sys.stdout.flush()
request_id = 0
while True:
    data = bytearray()
    while len(data) < 786432:
        block = sys.stdin.buffer.read(786432 - len(data))
        if not block:
            if not data:
                sys.exit(0)
            sys.exit(7)
        data.extend(block)
    request_id += 1
    if mode == "short_output":
        sys.stdout.buffer.write(b"x" * 12)
        sys.stdout.flush()
        sys.exit(0)
    values_to_write = [float(request_id)] * 512
    if mode == "nan_output":
        values_to_write[0] = float("nan")
    values = struct.pack("<512f", *values_to_write)
    sys.stdout.buffer.write(values)
    sys.stdout.flush()
    result = {"kind":"result", "request_id":request_id, "run_ms":3.25}
    if mode == "bad_request_id":
        result["request_id"] += 1
    if mode == "bad_json":
        sys.stdout.write("not-json\n")
    else:
        sys.stdout.write(json.dumps(result) + "\n")
    sys.stdout.flush()
'''.replace("MODE", repr(mode))
    path.write_text(source, encoding="utf-8")
    return [sys.executable, str(path)]


def test_stream_client_reuses_process_and_frames_fixed_shape(tmp_path):
    client = OrtStreamClient(make_runner(tmp_path), threads=2)
    try:
        assert client.metadata["ort_version"] == "1.16.3"
        first = client.infer_tensor(np.zeros((1, 3, 256, 256), dtype=np.float32))
        second = client.infer_tensor(np.ones((1, 3, 256, 256), dtype=np.float32))
        assert first["request_id"] == 1
        assert second["request_id"] == 2
        assert first["run_ms"] == 3.25
        assert first["feature"].shape == (512,)
        assert np.all(first["feature"] == 1)
        assert np.all(second["feature"] == 2)
        assert client.process.poll() is None
    finally:
        client.close()


def test_stream_client_rejects_wrong_startup_metadata(tmp_path):
    with pytest.raises(ValueError, match="output_shape"):
        OrtStreamClient(make_runner(tmp_path, "bad_metadata"), threads=2)


def test_stream_client_rejects_wrong_api_version(tmp_path):
    with pytest.raises(ValueError, match="api_version"):
        OrtStreamClient(make_runner(tmp_path, "bad_api_version"), threads=2)


def test_stream_client_rejects_short_response(tmp_path):
    client = OrtStreamClient(make_runner(tmp_path, "short_output"), threads=2)
    try:
        with pytest.raises((EOFError, RuntimeError), match="(?i)(short|closed|response)"):
            client.infer_tensor(np.zeros((1, 3, 256, 256), dtype=np.float32))
    finally:
        client.close()


def test_stream_client_rejects_nonfinite_output(tmp_path):
    client = OrtStreamClient(make_runner(tmp_path, "nan_output"), threads=2)
    try:
        with pytest.raises(ValueError, match="non-finite"):
            client.infer_tensor(np.zeros((1, 3, 256, 256), dtype=np.float32))
    finally:
        client.close()


def test_stream_client_rejects_wrong_request_id(tmp_path):
    client = OrtStreamClient(make_runner(tmp_path, "bad_request_id"), threads=2)
    try:
        with pytest.raises(ValueError, match="request_id"):
            client.infer_tensor(np.zeros((1, 3, 256, 256), dtype=np.float32))
    finally:
        client.close()


def test_stream_client_closes_after_corrupt_response_json(tmp_path):
    client = OrtStreamClient(make_runner(tmp_path, "bad_json"), threads=2)
    process = client.process
    try:
        with pytest.raises(ValueError, match="invalid|JSON|json"):
            client.infer_tensor(np.zeros((1, 3, 256, 256), dtype=np.float32))
        assert client._closed
        assert process.poll() is not None
    finally:
        client.close()


def test_stream_client_reports_process_that_fails_before_startup():
    with pytest.raises(RuntimeError, match="before startup"):
        OrtStreamClient([sys.executable, "-c", "raise SystemExit(9)"], threads=2)


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_stream_client_rejects_nonfinite_tensor_before_write(tmp_path, bad):
    client = OrtStreamClient(make_runner(tmp_path), threads=2)
    try:
        tensor = np.zeros((1, 3, 256, 256), dtype=np.float32)
        tensor.flat[0] = bad
        with pytest.raises(ValueError, match="finite"):
            client.infer_tensor(tensor)
    finally:
        client.close()


def test_stream_client_rejects_float32_conversion_overflow(tmp_path):
    client = OrtStreamClient(make_runner(tmp_path), threads=2)
    try:
        tensor = np.zeros((1, 3, 256, 256), dtype=np.float64)
        tensor.flat[0] = 1.0e100
        with pytest.raises(ValueError, match="finite after float32"):
            client.infer_tensor(tensor)
    finally:
        client.close()
