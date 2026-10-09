"""Shared-mmap ONNX Runtime partition clients for V10 PS stages.

Tensor payloads live in one bounded shared mapping. Pipes carry only a uint64
request sequence and a small JSON result record, so the existing ``infer`` API
and its independent NumPy output lifetime are preserved.
"""
from __future__ import print_function

import hashlib
import json
import mmap
import os
import select
import struct
import subprocess
import tempfile
import time

import numpy as np

try:
    import fcntl
except ImportError:  # Keep module importable on non-POSIX development hosts.
    fcntl = None

_HEADER_BYTES = 64
_MAX_TENSOR_BYTES = 64 * 1024 * 1024
_MAX_TOTAL_BYTES = 128 * 1024 * 1024
_LOGICAL_OUTPUT_NAMES = {
    "stem-prefix": "n0_input", "network1-bridge": "n2_input",
    "network3-bridge": "n4_input", "suffix": "features",
}


def _deadline_wait(fd, read, deadline, label):
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("%s exceeded its deadline" % label)
        try:
            ready = select.select([fd] if read else [], [] if read else [fd], [], remaining)[0 if read else 1]
        except InterruptedError:
            continue
        if not ready:
            raise TimeoutError("%s exceeded its deadline" % label)
        return


def _write_all(fd, payload, deadline, label):
    view = memoryview(payload).cast("B")
    offset = 0
    while offset < len(view):
        _deadline_wait(fd, False, deadline, label)
        try:
            count = os.write(fd, view[offset:])
        except InterruptedError:
            continue
        except BlockingIOError:
            continue
        if count <= 0:
            raise EOFError("%s pipe closed during write" % label)
        offset += count


def _read_exact(fd, destination, deadline, label):
    view = memoryview(destination).cast("B")
    offset = 0
    while offset < len(view):
        _deadline_wait(fd, True, deadline, label)
        try:
            count = os.readv(fd, [view[offset:]]) if hasattr(os, "readv") else 0
            if not hasattr(os, "readv"):
                block = os.read(fd, len(view) - offset)
                count = len(block)
                view[offset:offset + count] = block
        except InterruptedError:
            continue
        except BlockingIOError:
            continue
        if count <= 0:
            raise EOFError("%s pipe closed during read" % label)
        offset += count


def _read_line(fd, pending, deadline, label):
    while True:
        index = pending.find(b"\n")
        if index >= 0:
            line = bytes(pending[:index + 1])
            del pending[:index + 1]
            return line
        _deadline_wait(fd, True, deadline, label)
        try:
            block = os.read(fd, 4096)
        except InterruptedError:
            continue
        except BlockingIOError:
            continue
        if not block:
            raise EOFError("%s pipe closed before newline" % label)
        pending.extend(block)
        if len(pending) > 1024 * 1024:
            raise ValueError("%s line exceeds 1 MiB" % label)


def _validate_contract(contract):
    if not isinstance(contract, dict):
        raise ValueError("contract must be a mapping")
    for direction in ("inputs", "outputs"):
        specs = contract.get(direction)
        if not isinstance(specs, list) or not 1 <= len(specs) <= 8:
            raise ValueError("%s count must be in [1,8]" % direction)
        total = 0
        for spec in specs:
            shape = spec.get("shape")
            if (not isinstance(shape, (list, tuple)) or not 1 <= len(shape) <= 8 or
                    any(type(dim) is not int or dim <= 0 for dim in shape)):
                raise ValueError("%s shape must contain positive static dimensions" % direction)
            count = 1
            for dim in shape:
                count *= dim
                if count > _MAX_TENSOR_BYTES // 4:
                    raise ValueError("%s tensor exceeds the protocol byte limit" % direction)
            size = count * 4
            if type(spec.get("bytes")) is not int or spec["bytes"] != size:
                raise ValueError("%s byte count does not match shape" % direction)
            if spec.get("dtype", "float32") not in ("float32", "<f4"):
                raise ValueError("only float32 tensors are supported")
            if not isinstance(spec.get("name"), str) or not spec["name"]:
                raise ValueError("tensor name must be non-empty")
            total += size
        if total > _MAX_TOTAL_BYTES:
            raise ValueError("%s total exceeds the protocol byte limit" % direction)


class ShmOrtPartitionClient(object):
    """Persistent v3 client; ``command`` is [runner, model_path, threads]."""

    outputs_have_independent_lifetime = True
    # infer() validates every external input and copied output with np.isfinite.
    # Runtimes may use this explicit capability to avoid scanning the same
    # tensors a second time while retaining all shape/dtype/response checks.
    validates_tensor_finiteness = True

    def __init__(self, command, contract, threads=4, expected_version="1.16.3",
                 startup_timeout=30.0, request_timeout=30.0, reap_timeout=5.0,
                 allow_spinning=None, preallocate_outputs=None, shm_dir=None):
        _validate_contract(contract)
        self.contract = contract
        self.request_timeout = float(request_timeout)
        self.reap_timeout = float(reap_timeout)
        if min(float(startup_timeout), self.request_timeout, self.reap_timeout) <= 0:
            raise ValueError("startup, request, and reap timeouts must be positive")
        if len(command) != 3:
            raise ValueError("command must be [runner, model_path, threads]")
        if allow_spinning is None:
            allow_spinning = int(os.environ.get("ORT_PARTITION_ALLOW_SPINNING", "0"))
        if preallocate_outputs is None:
            preallocate_outputs = int(os.environ.get("ORT_PARTITION_PREALLOC_OUTPUTS", "0"))
        if allow_spinning not in (0, 1) or preallocate_outputs not in (0, 1):
            raise ValueError("spin and preallocation controls must be 0 or 1")
        self._input_bytes = sum(s["bytes"] for s in contract["inputs"])
        self._output_bytes = sum(s["bytes"] for s in contract["outputs"])
        self._mapping_bytes = _HEADER_BYTES + self._input_bytes + self._output_bytes
        if shm_dir is None and os.name == "posix":
            shm_dir = "/dev/shm"
        if os.name == "posix":
            if (not isinstance(shm_dir, str) or not os.path.isdir(shm_dir) or
                    not os.access(shm_dir, os.W_OK | os.X_OK)):
                raise RuntimeError("shared-mmap client requires a writable tmpfs directory")
            stats = os.statvfs(shm_dir)
            if stats.f_bavail * stats.f_frsize < self._mapping_bytes:
                raise RuntimeError("shared-mmap tmpfs does not have enough free space")
        self._shm_dir = shm_dir
        self._temp = tempfile.TemporaryFile(dir=shm_dir)
        self._temp.truncate(self._mapping_bytes)
        self._mapping = mmap.mmap(self._temp.fileno(), self._mapping_bytes,
                                  access=mmap.ACCESS_WRITE)
        self._mapping[:_HEADER_BYTES] = b"ORTSHM3\0" + struct.pack("<I", 3) + bytes(52)
        self._closed = False
        self.process = None
        environment = os.environ.copy()
        environment["ORT_PARTITION_ALLOW_SPINNING"] = str(allow_spinning)
        environment["ORT_PARTITION_PREALLOC_OUTPUTS"] = str(preallocate_outputs)
        try:
            self.process = subprocess.Popen(
                [command[0], "--shm", str(self._temp.fileno()), command[1], str(command[2])],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=None, bufsize=0,
                env=environment, pass_fds=(self._temp.fileno(),))
            self._input_fd = self.process.stdin.fileno()
            self._output_fd = self.process.stdout.fileno()
            if fcntl is None:
                raise RuntimeError("shared-mmap partition client requires POSIX fcntl")
            for fd in (self._input_fd, self._output_fd):
                flags = fcntl.fcntl(fd, fcntl.F_GETFL)
                fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
            self._pending = bytearray()
            self._request_id = 0
            line = _read_line(self._output_fd, self._pending,
                              time.monotonic() + float(startup_timeout),
                              "partition startup header")
            self.header = json.loads(line.decode("utf-8"))
            self._validate_header(self.header, threads, expected_version,
                                  bool(allow_spinning), bool(preallocate_outputs))
        except Exception:
            self.close()
            raise

    def _validate_header(self, header, threads, version, spinning, preallocated):
        if header.get("kind") != "ready" or header.get("protocol") != 3 or header.get("api_version") != 16:
            raise ValueError("partition runner protocol/API mismatch")
        if header.get("ort_version") != version:
            raise ValueError("ORT runtime mismatch: expected %s, got %r" % (version, header.get("ort_version")))
        if header.get("threads") != int(threads):
            raise ValueError("partition runner thread count mismatch")
        if header.get("allow_spinning") is not spinning or header.get("preallocated_outputs") is not preallocated:
            raise ValueError("partition runner runtime option mismatch")
        load_ms = header.get("load_ms")
        if not isinstance(load_ms, (int, float)) or not np.isfinite(load_ms) or load_ms < 0:
            raise ValueError("partition runner load_ms is invalid")
        for direction in ("inputs", "outputs"):
            actual, expected = header.get(direction), self.contract[direction]
            if not isinstance(actual, list) or len(actual) != len(expected):
                raise ValueError("partition runner %s count mismatch" % direction)
            for i, spec in enumerate(expected):
                wanted = {"name": spec["name"], "shape": list(spec["shape"]), "dtype": "float32", "bytes": spec["bytes"]}
                if actual[i] != wanted:
                    raise ValueError("partition runner %s[%d] metadata mismatch" % (direction, i))
        for key, direction in (("input_bytes", "inputs"), ("output_bytes", "outputs")):
            if header.get(key) != sum(s["bytes"] for s in self.contract[direction]):
                raise ValueError("partition runner %s mismatch" % key)

    def infer(self, tensors):
        if self._closed or self.process.poll() is not None:
            raise RuntimeError("partition runner process is not running")
        values = ([tensors[s["name"]] for s in self.contract["inputs"]]
                  if isinstance(tensors, dict) else list(tensors))
        if len(values) != len(self.contract["inputs"]):
            raise ValueError("wrong number of partition inputs")
        arrays = []
        for value, spec in zip(values, self.contract["inputs"]):
            array = np.asarray(value, dtype="<f4", order="C")
            if array.shape != tuple(spec["shape"]):
                raise ValueError("input %s shape mismatch" % spec["name"])
            if not np.isfinite(array).all():
                raise ValueError("input %s must be finite float32" % spec["name"])
            if array.nbytes != spec["bytes"]:
                raise ValueError("input %s byte count mismatch" % spec["name"])
            arrays.append(array)
        offset = _HEADER_BYTES
        for array in arrays:
            end = offset + array.nbytes
            self._mapping[offset:end] = memoryview(array).cast("B")
            offset = end
        deadline = time.monotonic() + self.request_timeout
        expected_id = self._request_id + 1
        try:
            _write_all(self._input_fd, struct.pack("<Q", expected_id), deadline, "partition request id")
            line = _read_line(self._output_fd, self._pending, deadline, "partition result header")
            result = json.loads(line.decode("utf-8"))
            if result.get("kind") != "result" or result.get("request_id") != expected_id:
                raise ValueError("partition result id/kind mismatch")
            run_ms = result.get("run_ms")
            if not isinstance(run_ms, (int, float)) or not np.isfinite(run_ms) or run_ms < 0:
                raise ValueError("partition run_ms is invalid")
            outputs = []
            offset = _HEADER_BYTES + self._input_bytes
            for spec in self.contract["outputs"]:
                end = offset + spec["bytes"]
                # Copy after the acknowledgment; outputs survive later requests and close().
                array = np.frombuffer(
                    self._mapping, dtype="<f4", count=spec["bytes"] // 4,
                    offset=offset).reshape(tuple(spec["shape"])).copy()
                if not np.isfinite(array).all():
                    raise ValueError("output %s contains non-finite values" % spec["name"])
                outputs.append(array)
                offset = end
            if time.monotonic() >= deadline:
                raise TimeoutError("partition output copy exceeded its deadline")
        except (IOError, OSError, EOFError, ValueError, UnicodeDecodeError,
                AttributeError, TimeoutError) as error:
            self.close()
            if isinstance(error, (ValueError, EOFError, AttributeError, TimeoutError)):
                raise
            raise RuntimeError("partition frame exchange failed: %s" % error)
        self._request_id = expected_id
        return ({s["name"]: a for s, a in zip(self.contract["outputs"], outputs)}, float(run_ms))

    def close(self):
        if getattr(self, "_closed", False):
            return
        self._closed = True
        process = getattr(self, "process", None)
        if process is not None:
            if process.stdin:
                try:
                    process.stdin.close()
                except (IOError, OSError):
                    pass
            try:
                process.wait(timeout=self.reap_timeout)
            except subprocess.TimeoutExpired:
                process.terminate()
                try:
                    process.wait(timeout=self.reap_timeout)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=self.reap_timeout)
            if process.stdout:
                process.stdout.close()
        mapping = getattr(self, "_mapping", None)
        if mapping is not None:
            mapping.close()
            self._mapping = None
        temp = getattr(self, "_temp", None)
        if temp is not None:
            temp.close()
            self._temp = None


class _LogicalOutputClient(object):
    outputs_have_independent_lifetime = True
    validates_tensor_finiteness = True

    def __init__(self, client, source_name, logical_name):
        self._client = client
        self.source_name = source_name
        self.logical_name = logical_name
        self.header = client.header

    @property
    def closed(self):
        return bool(getattr(self._client, "_closed", False))

    def infer(self, tensors):
        outputs, run_ms = self._client.infer(tensors)
        if self.source_name not in outputs:
            raise ValueError("ORT output %s is missing" % self.source_name)
        return {self.logical_name: outputs[self.source_name]}, run_ms

    def close(self):
        return self._client.close()


def _file_sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_shm_split_clients(model_root, runner, manifest_path,
                           expected_manifest_sha256, threads,
                           model_overrides=None):
    try:
        from cnn_ddr_v5_runtime import load_v5_split_contracts
    except ImportError:
        from .cnn_ddr_v5_runtime import load_v5_split_contracts
    manifest_path = os.path.abspath(manifest_path)
    if manifest_path != os.path.abspath(os.path.join(model_root, "manifest.json")):
        raise ValueError("model manifest path must match the selected split bundle")
    bundle = load_v5_split_contracts(model_root, expected_manifest_sha256)
    overrides = {} if model_overrides is None else dict(model_overrides)
    if any(name not in bundle["models"] for name in overrides):
        raise ValueError("model override names must match the split bundle")
    normalized_overrides = {}
    for name, value in overrides.items():
        if not isinstance(value, dict):
            raise ValueError("model override must contain path and SHA")
        path = os.path.abspath(value.get("path", ""))
        expected_sha = value.get("sha256")
        if (not os.path.isfile(path) or not isinstance(expected_sha, str) or
                len(expected_sha) != 64 or _file_sha256(path) != expected_sha):
            raise ValueError("model override path/SHA mismatch for %s" % name)
        normalized_overrides[name] = path
    clients = {}
    try:
        for name, record in bundle["models"].items():
            model_path = normalized_overrides.get(name, record["path"])
            client = ShmOrtPartitionClient([runner, model_path, str(int(threads))],
                                           record["contract"], threads=int(threads))
            source = record["contract"]["outputs"][0]["name"]
            clients[name] = _LogicalOutputClient(client, source, _LOGICAL_OUTPUT_NAMES[name])
    except Exception:
        for client in clients.values():
            client.close()
        raise
    return clients, bundle["manifest_sha256"]


__all__ = ["ShmOrtPartitionClient", "load_shm_split_clients"]
