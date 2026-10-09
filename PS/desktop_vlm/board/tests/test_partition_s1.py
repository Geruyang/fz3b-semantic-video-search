import hashlib
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pytest

from partition_s1 import (OrtPartitionClient, PersistentPartitionS1,
                           _prepare_preprocessed_tensor, _validate_manifest)


BOARD = Path(__file__).resolve().parents[3]
SPLIT = BOARD / "artifacts/board-debug-20261004/acceleration/host/dw-split-001"


def _write_small_split(tmp_path):
    with open(str(SPLIT / "manifest.json"), "r") as stream:
        manifest = json.load(stream)
    for stage in manifest["stages"]:
        payload = ("fake-" + stage["stage"]).encode("ascii")
        path = tmp_path / (stage["stage"] + ".onnx")
        path.write_bytes(payload)
        stage["sha256"] = hashlib.sha256(payload).hexdigest()
        stage["bytes"] = len(payload)
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path, hashlib.sha256(path.read_bytes()).hexdigest()


FAKE_RUNNER = r'''import json, struct, sys
contract = json.loads(sys.argv[1])
stage = sys.argv[2]
mode = sys.argv[3]
if mode == "hang_startup":
    import time; time.sleep(3)
if mode == "hang_startup":
    import time; time.sleep(3)
inputs = contract["inputs"]
outputs = contract["outputs"]
def entry(item):
    return {"name":item["name"], "shape":item["shape"],
            "dtype":"float32", "bytes":item["bytes"]}
ready = {"kind":"ready", "ort_version":"1.16.3", "api_version":16,
         "threads":2, "load_ms":1.5,
         "input_bytes":sum(x["bytes"] for x in inputs),
         "output_bytes":sum(x["bytes"] for x in outputs),
         "inputs":[entry(x) for x in inputs], "outputs":[entry(x) for x in outputs]}
if mode == "bad_header":
    ready["inputs"][0]["shape"] = [999]
sys.stdout.write(json.dumps(ready) + "\n")
sys.stdout.flush()
request_id = 0
while True:
    vals = []
    for spec in inputs:
        data = bytearray()
        while len(data) < spec["bytes"]:
            block = sys.stdin.buffer.read(spec["bytes"] - len(data))
            if not block:
                if not data and not vals:
                    sys.exit(0)
                sys.exit(7)
            data.extend(block)
        vals.append(struct.unpack("<f", data[:4])[0])
    request_id += 1
    if mode == "hang_request":
        import time; time.sleep(3)
    if mode == "hang_request":
        import time; time.sleep(3)
    if mode == "short_output":
        sys.stdout.buffer.write(b"1234")
        sys.stdout.flush()
        sys.exit(0)
    if stage == "prefix":
        value = vals[0]
    elif stage == "region":
        value = vals[0] + 10.0
    elif stage == "suffix":
        # Input order matters: region result first, original prefix residual second.
        value = vals[0] + 2.0 * vals[1]
    else:
        value = vals[0] + 10.0 * vals[1]
    for spec in outputs:
        count = spec["bytes"] // 4
        sys.stdout.buffer.write(struct.pack("<f", value) * count)
    sys.stdout.flush()
    sys.stdout.write(json.dumps({"kind":"result", "request_id":request_id,
                                 "run_ms":2.0}) + "\n")
    sys.stdout.flush()
'''


def _factory(mode="ok"):
    def command(stage, model_path, threads):
        with open(str(SPLIT / "manifest.json"), "r") as stream:
            source = json.load(stream)
        index = ("prefix", "region", "suffix").index(stage)
        item = source["stages"][index]
        contract = {
            "inputs": [{"name": x["name"], "shape": x["shape"],
                        "bytes": x["bytes_fp32"]} for x in item["inputs"]],
            "outputs": [{"name": x["name"], "shape": x["shape"],
                         "bytes": x["bytes_fp32"]} for x in item["outputs"]]}
        script = FAKE_RUNNER.replace("MODE_UNUSED", repr(mode))
        return [sys.executable, "-c", script, json.dumps(contract), stage, mode]
    return command


def test_manifest_uses_real_ports_and_requires_residual_bypass():
    with open(str(SPLIT / "manifest.json"), "r") as stream:
        manifest = json.load(stream)
    contracts = _validate_manifest(manifest)
    assert contracts["prefix"]["inputs"][0]["name"] == "image"
    assert len(contracts["suffix"]["inputs"]) == 2
    assert contracts["suffix"]["inputs"][1] == contracts["prefix"]["outputs"][0]


def test_manifest_rejects_lost_residual_input():
    with open(str(SPLIT / "manifest.json"), "r") as stream:
        manifest = json.load(stream)
    manifest["stages"][2]["inputs"][1]["name"] = "wrong_tensor"
    with pytest.raises(ValueError, match="residual bypass"):
        _validate_manifest(manifest)


def test_preprocessed_tensor_accepts_chw_and_nchw_but_rejects_other_shape():
    expected = (1, 3, 256, 256)
    chw = np.zeros(expected[1:], dtype=np.float32)
    nchw = chw.reshape(expected)
    assert _prepare_preprocessed_tensor(chw, expected).shape == expected
    assert _prepare_preprocessed_tensor(nchw, expected).shape == expected
    with pytest.raises(ValueError, match="does not match manifest"):
        _prepare_preprocessed_tensor(np.zeros((3, 255, 256), dtype=np.float32), expected)


def test_three_sessions_keep_model_identity_and_residual_tensor(tmp_path):
    _, expected_manifest_sha = _write_small_split(tmp_path)
    runner = PersistentPartitionS1(str(tmp_path), "unused", threads=2,
                                   runner_command_factory=_factory(),
                                   expected_manifest_sha256=expected_manifest_sha)
    try:
        assert len(runner.clients) == 3
        assert runner.manifest_sha256 == hashlib.sha256((tmp_path / "manifest.json").read_bytes()).hexdigest()
        assert len(set(runner.model_sha256.values())) == 3
        tensor = np.zeros((1, 3, 256, 256), dtype=np.float32)
        tensor.flat[0] = 3.0
        result = runner.infer_tensor(tensor)
        assert result["features"].shape == (1, 512)
        assert np.all(result["features"] == 19.0)
        assert set(result["stage_run_ms"]) == {"prefix", "region", "suffix"}
    finally:
        runner.close()


def test_partition_rejects_model_sha_mismatch(tmp_path):
    _, expected_manifest_sha = _write_small_split(tmp_path)
    (tmp_path / "region.onnx").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="region model SHA256"):
        PersistentPartitionS1(str(tmp_path), "unused", runner_command_factory=_factory(),
                              expected_manifest_sha256=expected_manifest_sha)


def test_rewritten_manifest_model_fields_still_fail_trusted_manifest_sha(tmp_path):
    manifest_path, expected_manifest_sha = _write_small_split(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["ort_threads"] = 4
    # Keep all embedded model SHA/size fields valid for the copied model files.
    for stage in manifest["stages"]:
        payload = (tmp_path / (stage["stage"] + ".onnx")).read_bytes()
        stage["sha256"] = hashlib.sha256(payload).hexdigest()
        stage["bytes"] = len(payload)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="trusted expected hash"):
        PersistentPartitionS1(str(tmp_path), "unused", runner_command_factory=_factory(),
                              expected_manifest_sha256=expected_manifest_sha)


def test_image_entry_accepts_prebatched_preprocessor_output_with_fake_sessions(tmp_path, monkeypatch):
    _, expected_manifest_sha = _write_small_split(tmp_path)
    import preprocess_s1
    preprocessed = np.zeros((1, 3, 256, 256), dtype=np.float32)
    preprocessed.flat[0] = 3.0
    monkeypatch.setattr(preprocess_s1, "preprocess",
                        lambda path: (preprocessed, {"shape": [1, 3, 256, 256]}))
    image = tmp_path / "fake-image.bin"
    image.write_bytes(b"image bytes")
    runner = PersistentPartitionS1(str(tmp_path), "unused", runner_command_factory=_factory(),
                                   expected_manifest_sha256=expected_manifest_sha)
    try:
        result = runner.infer_image(str(image))
        assert result["features"].shape == (1, 512)
        assert np.all(result["features"] == 19.0)
        assert result["preprocess"]["shape"] == [1, 3, 256, 256]
    finally:
        runner.close()


def test_generic_client_preserves_manifest_order_for_multiple_inputs(tmp_path):
    a = {"name":"a", "shape":(1,), "bytes":4, "dtype":"float32"}
    b = {"name":"b", "shape":(1,), "bytes":4, "dtype":"float32"}
    out = {"name":"sum", "shape":(1,), "bytes":4, "dtype":"float32"}
    contract = {"inputs":[a, b], "outputs":[out]}
    script = FAKE_RUNNER
    command = [sys.executable, "-c", script, json.dumps(contract), "generic", "ok"]
    client = OrtPartitionClient(command, contract, threads=2)
    try:
        values, _ = client.infer([np.array([2], dtype=np.float32), np.array([5], dtype=np.float32)])
        assert values["sum"].tolist() == [52.0]
    finally:
        client.close()


def test_client_rejects_nonfinite_input_before_sending():
    a = {"name":"a", "shape":(1,), "bytes":4, "dtype":"float32"}
    out = {"name":"out", "shape":(1,), "bytes":4, "dtype":"float32"}
    contract = {"inputs":[a], "outputs":[out]}
    command = [sys.executable, "-c", FAKE_RUNNER, json.dumps(contract), "generic", "ok"]
    client = OrtPartitionClient(command, contract, threads=2)
    try:
        with pytest.raises(ValueError, match="finite"):
            client.infer([np.array([float("nan")], dtype=np.float32)])
    finally:
        client.close()


def test_client_rejects_half_response_frame():
    a = {"name":"a", "shape":(1,), "bytes":4, "dtype":"float32"}
    out = {"name":"out", "shape":(2,), "bytes":8, "dtype":"float32"}
    contract = {"inputs":[a], "outputs":[out]}
    command = [sys.executable, "-c", FAKE_RUNNER, json.dumps(contract), "generic", "short_output"]
    client = OrtPartitionClient(command, contract, threads=2)
    try:
        with pytest.raises(EOFError, match="short response frame"):
            client.infer([np.array([1.0], dtype=np.float32)])
    finally:
        client.close()


def test_client_rejects_startup_tensor_size_mismatch():
    a = {"name":"a", "shape":(1,), "bytes":4, "dtype":"float32"}
    out = {"name":"out", "shape":(1,), "bytes":4, "dtype":"float32"}
    contract = {"inputs":[a], "outputs":[out]}
    script = FAKE_RUNNER.replace('mode = sys.argv[3]', 'mode = "bad_header"')
    command = [sys.executable, "-c", script, json.dumps(contract), "generic", "ok"]
    with pytest.raises(ValueError, match="metadata mismatch"):
        OrtPartitionClient(command, contract, threads=2)


def test_startup_header_has_a_deadline_and_child_is_reaped():
    contract = {"inputs":[], "outputs":[]}
    command = [sys.executable, "-c", FAKE_RUNNER, json.dumps(contract), "generic", "hang_startup"]
    with pytest.raises(TimeoutError, match="startup header"):
        OrtPartitionClient(command, contract, threads=2, startup_timeout=0.05,
                           request_timeout=0.5, reap_timeout=0.5)


def test_request_frame_has_a_deadline_and_child_is_reaped():
    a = {"name":"a", "shape":(1,), "bytes":4, "dtype":"float32"}
    out = {"name":"out", "shape":(1,), "bytes":4, "dtype":"float32"}
    contract = {"inputs":[a], "outputs":[out]}
    command = [sys.executable, "-c", FAKE_RUNNER, json.dumps(contract), "generic", "hang_request"]
    client = OrtPartitionClient(command, contract, threads=2, request_timeout=0.05,
                                reap_timeout=0.5)
    process = client.process
    with pytest.raises(TimeoutError, match="partition output read"):
        client.infer([np.array([1.0], dtype=np.float32)])
    assert client._closed
    assert process.poll() is not None


def test_close_attempts_to_reap_every_child_after_one_close_fails():
    class BrokenClient(object):
        def __init__(self):
            self.closed = False
        def close(self):
            self.closed = True
            raise RuntimeError("reap failure")

    class GoodClient(object):
        def __init__(self):
            self.closed = False
        def close(self):
            self.closed = True

    runner = object.__new__(PersistentPartitionS1)
    broken, good = BrokenClient(), GoodClient()
    runner.clients = [good, broken]
    with pytest.raises(RuntimeError, match="failed to reap"):
        runner.close()
    assert broken.closed and good.closed


def test_startup_header_has_a_deadline_and_child_is_reaped():
    contract = {"inputs":[], "outputs":[]}
    command = [sys.executable, "-c", FAKE_RUNNER, json.dumps(contract), "generic", "hang_startup"]
    with pytest.raises(TimeoutError, match="startup header"):
        OrtPartitionClient(command, contract, threads=2, startup_timeout=0.05,
                           request_timeout=0.5, reap_timeout=0.5)


def test_request_frame_has_a_deadline_and_child_is_reaped():
    a = {"name":"a", "shape":(1,), "bytes":4, "dtype":"float32"}
    out = {"name":"out", "shape":(1,), "bytes":4, "dtype":"float32"}
    contract = {"inputs":[a], "outputs":[out]}
    command = [sys.executable, "-c", FAKE_RUNNER, json.dumps(contract), "generic", "hang_request"]
    client = OrtPartitionClient(command, contract, threads=2, request_timeout=0.05,
                                reap_timeout=0.5)
    process = client.process
    with pytest.raises(TimeoutError, match="partition output read"):
        client.infer([np.array([1.0], dtype=np.float32)])
    assert client._closed
    assert process.poll() is not None


def test_close_attempts_to_reap_every_child_after_one_close_fails():
    class BrokenClient(object):
        def __init__(self):
            self.closed = False
        def close(self):
            self.closed = True
            raise RuntimeError("reap failure")

    class GoodClient(object):
        def __init__(self):
            self.closed = False
        def close(self):
            self.closed = True

    runner = object.__new__(PersistentPartitionS1)
    broken, good = BrokenClient(), GoodClient()
    runner.clients = [good, broken]
    with pytest.raises(RuntimeError, match="failed to reap"):
        runner.close()
    assert broken.closed and good.closed
