import json
import os
import pathlib
import struct
import sys
import tempfile
import textwrap
import time

import numpy as np
import pytest

BOARD = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BOARD))
import cnn_v10_ps_shm_clients as shm  # noqa: E402


CONTRACT = {
    "inputs": [{"name": "x", "shape": [1, 2], "dtype": "float32", "bytes": 8}],
    "outputs": [{"name": "y", "shape": [1, 2], "dtype": "float32", "bytes": 8}],
}


def _fake_runner(slow=False, nonfinite=False):
    tmp = tempfile.TemporaryDirectory()
    path = pathlib.Path(tmp.name) / "fake_ort_runner"
    script = r'''#!/usr/bin/env python3
import json, mmap, os, struct, sys, time
fd = int(sys.argv[2])
mm = mmap.mmap(fd, 80, access=mmap.ACCESS_WRITE)
header = {"kind":"ready", "protocol":3, "api_version":16, "ort_version":"1.16.3",
          "threads":2, "load_ms":0.1, "allow_spinning":False,
          "preallocated_outputs":False, "input_bytes":8, "output_bytes":8,
          "inputs":[{"name":"x","shape":[1,2],"dtype":"float32","bytes":8}],
          "outputs":[{"name":"y","shape":[1,2],"dtype":"float32","bytes":8}]}
print(json.dumps(header), flush=True)
while True:
    packet = sys.stdin.buffer.read(8)
    if not packet: break
    if len(packet) != 8: sys.exit(3)
    request_id = struct.unpack('<Q', packet)[0]
    if ''' + str(bool(slow)) + r''': time.sleep(1.0)
    a, b = struct.unpack_from('<ff', mm, 64)
    if ''' + str(bool(nonfinite)) + r''': a = float('nan')
    struct.pack_into('<ff', mm, 72, a + 1.0, b + 1.0)
    print(json.dumps({"kind":"result", "request_id":request_id, "run_ms":0.25}), flush=True)
'''
    path.write_text(script, encoding="utf-8")
    path.chmod(0o755)
    return tmp, str(path)


@pytest.mark.skipif(os.name != "posix" or shm.fcntl is None, reason="v3 runner uses POSIX inherited fds")
def test_shared_client_returns_independent_arrays():
    tmp, runner = _fake_runner()
    client = shm.ShmOrtPartitionClient([runner, "unused.onnx", "2"], CONTRACT,
                                      threads=2, request_timeout=1.0)
    try:
        first, elapsed = client.infer([np.asarray([[2.0, 4.0]], dtype=np.float32)])
        second, unused = client.infer([np.asarray([[5.0, 7.0]], dtype=np.float32)])
        assert first["y"].tolist() == [[3.0, 5.0]]
        assert second["y"].tolist() == [[6.0, 8.0]]
        assert elapsed == 0.25
        assert first["y"].tolist() == [[3.0, 5.0]]
        assert first["y"].flags.owndata
    finally:
        client.close()
        tmp.cleanup()


@pytest.mark.skipif(os.name != "posix" or shm.fcntl is None, reason="v3 runner uses POSIX inherited fds")
def test_request_timeout_terminates_and_reaps_child():
    tmp, runner = _fake_runner(slow=True)
    client = shm.ShmOrtPartitionClient([runner, "unused.onnx", "2"], CONTRACT,
                                      threads=2, request_timeout=0.1, reap_timeout=0.1)
    process = client.process
    with pytest.raises(TimeoutError):
        client.infer([np.asarray([[1.0, 2.0]], dtype=np.float32)])
    assert client._closed
    assert process.poll() is not None
    tmp.cleanup()


def test_contract_rejects_shape_byte_mismatch():
    invalid = {"inputs": [dict(CONTRACT["inputs"][0], bytes=4)],
               "outputs": CONTRACT["outputs"]}
    with pytest.raises(ValueError, match="byte count"):
        shm.ShmOrtPartitionClient(["runner", "model", "2"], invalid)


def test_shared_client_declares_owned_finite_output_contract():
    assert shm.ShmOrtPartitionClient.outputs_have_independent_lifetime is True
    assert shm.ShmOrtPartitionClient.validates_tensor_finiteness is True
    assert shm._LogicalOutputClient.validates_tensor_finiteness is True


def test_partition_thread_map_is_strict_and_legacy_threads_remain_uniform():
    names = ("stem-prefix", "network1-bridge", "network3-bridge", "suffix")
    assert shm._partition_thread_map(names, 3, None) == dict(
        (name, 3) for name in names)
    selected = {"stem-prefix": 1, "network1-bridge": 1,
                "network3-bridge": 1, "suffix": 2}
    assert shm._partition_thread_map(names, 3, selected) == selected
    for invalid in (
            {"stem-prefix": 1},
            dict(selected, suffix=0),
            dict(selected, suffix=True),
            dict(selected, unknown=1)):
        with pytest.raises(ValueError, match="partition_threads"):
            shm._partition_thread_map(names, 3, invalid)


def test_loader_applies_each_partition_thread_count(monkeypatch, tmp_path):
    import cnn_ddr_v5_runtime

    names = ("stem-prefix", "network1-bridge", "network3-bridge", "suffix")
    model_root = tmp_path / "models"
    model_root.mkdir()
    manifest = model_root / "manifest.json"
    manifest.write_text("{}", encoding="utf-8")
    bundle = {
        "manifest_sha256": "a" * 64,
        "models": dict((name, {
            "path": str(model_root / (name + ".onnx")),
            "contract": CONTRACT}) for name in names),
    }
    monkeypatch.setattr(
        cnn_ddr_v5_runtime, "load_v5_split_contracts",
        lambda root, expected: bundle)
    constructed = []

    class FakeShmClient(object):
        def __init__(self, command, contract, threads):
            constructed.append((command[1], command[2], threads))
            self.header = {"threads": threads}

        def close(self):
            pass

    monkeypatch.setattr(shm, "ShmOrtPartitionClient", FakeShmClient)
    selected = {"stem-prefix": 1, "network1-bridge": 1,
                "network3-bridge": 1, "suffix": 2}
    clients, identity = shm.load_shm_split_clients(
        str(model_root), "runner", str(manifest), "a" * 64, threads=3,
        partition_threads=selected)
    assert identity == "a" * 64
    assert set(clients) == set(names)
    assert [entry[2] for entry in constructed] == [selected[name] for name in names]
    assert [entry[1] for entry in constructed] == [str(selected[name]) for name in names]


@pytest.mark.skipif(os.name != "posix", reason="tmpfs directory contract is POSIX-only")
def test_missing_explicit_shm_directory_fails_closed(tmp_path):
    with pytest.raises(RuntimeError, match="writable tmpfs"):
        shm.ShmOrtPartitionClient(
            ["runner", "model", "2"], CONTRACT, shm_dir=str(tmp_path / "missing"))


@pytest.mark.skipif(os.name != "posix" or shm.fcntl is None, reason="v3 runner uses POSIX inherited fds")
def test_nonfinite_shared_output_is_rejected():
    tmp, runner = _fake_runner(nonfinite=True)
    client = shm.ShmOrtPartitionClient([runner, "unused.onnx", "2"], CONTRACT,
                                      threads=2, request_timeout=1.0)
    with pytest.raises(ValueError, match="non-finite"):
        client.infer([np.asarray([[1.0, 2.0]], dtype=np.float32)])
    assert client._closed
    tmp.cleanup()
