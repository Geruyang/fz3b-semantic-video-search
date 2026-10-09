"""Low-overhead fixed-contract clients for the V10 PS ONNX partitions.

The public loader mirrors ``load_existing_split_clients`` so the V10 runtime
can select this implementation without changing its stage callback contract.
It keeps one process/session per partition, uses deadline-aware POSIX pipe I/O
without creating helper threads for each read or write, and returns independent
NumPy arrays suitable for the cross-pair scheduler.
"""
from __future__ import print_function

import json
import errno
import os
import select
import subprocess
import time

import numpy as np

try:
    import fcntl
except ImportError:  # The production target is POSIX; keep host imports usable.
    fcntl = None


_LOGICAL_OUTPUT_NAMES = {
    "stem-prefix": "n0_input",
    "network1-bridge": "n2_input",
    "network3-bridge": "n4_input",
    "suffix": "features",
}


def _remaining(deadline, label):
    value = deadline - time.monotonic()
    if value <= 0:
        raise TimeoutError("%s exceeded its deadline" % label)
    return value


def _wait_readable(fd, deadline, label):
    while True:
        try:
            ready, unused_write, unused_error = select.select(
                [fd], [], [], _remaining(deadline, label))
        except InterruptedError:
            continue
        if not ready:
            raise TimeoutError("%s exceeded its deadline" % label)
        return


def _wait_writable(fd, deadline, label):
    while True:
        try:
            unused_read, ready, unused_error = select.select(
                [], [fd], [], _remaining(deadline, label))
        except InterruptedError:
            continue
        if not ready:
            raise TimeoutError("%s exceeded its deadline" % label)
        return


def _write_fd_all(fd, payload, deadline, label):
    view = memoryview(payload).cast("B")
    offset = 0
    while offset < len(view):
        _wait_writable(fd, deadline, label)
        try:
            count = os.write(fd, view[offset:])
        except InterruptedError:
            continue
        except BlockingIOError:
            continue
        except OSError as error:
            if error.errno in (errno.EAGAIN, errno.EWOULDBLOCK):
                continue
            raise
        if count <= 0:
            raise EOFError("%s pipe closed during write" % label)
        offset += count


def _read_fd_into(fd, destination, deadline, label):
    view = memoryview(destination).cast("B")
    offset = 0
    while offset < len(view):
        _wait_readable(fd, deadline, label)
        try:
            if hasattr(os, "readv"):
                count = os.readv(fd, [view[offset:]])
            else:
                block = os.read(fd, len(view) - offset)
                count = len(block)
                view[offset:offset + count] = block
        except InterruptedError:
            continue
        except BlockingIOError:
            continue
        except OSError as error:
            if error.errno in (errno.EAGAIN, errno.EWOULDBLOCK):
                continue
            raise
        if count <= 0:
            raise EOFError("%s pipe closed during read" % label)
        offset += count


def _read_fd_line(fd, pending, deadline, label):
    while True:
        newline = pending.find(b"\n")
        if newline >= 0:
            result = bytes(pending[:newline + 1])
            del pending[:newline + 1]
            return result
        _wait_readable(fd, deadline, label)
        try:
            block = os.read(fd, 4096)
        except InterruptedError:
            continue
        except BlockingIOError:
            continue
        except OSError as error:
            if error.errno in (errno.EAGAIN, errno.EWOULDBLOCK):
                continue
            raise
        if not block:
            raise EOFError("%s pipe closed before newline" % label)
        pending.extend(block)
        if len(pending) > 1024 * 1024:
            raise ValueError("%s line exceeds 1 MiB" % label)


class OptimizedOrtPartitionClient(object):
    """Persistent partition client with one deadline and zero I/O threads."""

    def __init__(self, command, contract, threads=4, expected_version="1.16.3",
                 startup_timeout=30.0, request_timeout=30.0, reap_timeout=5.0,
                 allow_spinning=None, preallocate_outputs=None):
        self.contract = contract
        self.request_timeout = float(request_timeout)
        self.reap_timeout = float(reap_timeout)
        if min(float(startup_timeout), self.request_timeout,
               self.reap_timeout) <= 0:
            raise ValueError("startup, request, and reap timeouts must be positive")
        if allow_spinning is None:
            allow_spinning = int(os.environ.get(
                "ORT_PARTITION_ALLOW_SPINNING", "0"))
        if preallocate_outputs is None:
            preallocate_outputs = int(os.environ.get(
                "ORT_PARTITION_PREALLOC_OUTPUTS", "0"))
        if allow_spinning not in (0, 1) or preallocate_outputs not in (0, 1):
            raise ValueError("spin and preallocation controls must be 0 or 1")
        environment = os.environ.copy()
        environment["ORT_PARTITION_ALLOW_SPINNING"] = str(allow_spinning)
        environment["ORT_PARTITION_PREALLOC_OUTPUTS"] = str(preallocate_outputs)
        self.process = subprocess.Popen(
            command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=None, bufsize=0, env=environment)
        self._input_fd = self.process.stdin.fileno()
        self._output_fd = self.process.stdout.fileno()
        if fcntl is None:
            self.process.terminate()
            self.process.wait()
            raise RuntimeError("optimized partition client requires POSIX fcntl")
        for descriptor in (self._input_fd, self._output_fd):
            flags = fcntl.fcntl(descriptor, fcntl.F_GETFL)
            fcntl.fcntl(descriptor, fcntl.F_SETFL, flags | os.O_NONBLOCK)
        self._pending = bytearray()
        self._closed = False
        self._request_id = 0
        try:
            line = _read_fd_line(
                self._output_fd, self._pending,
                time.monotonic() + float(startup_timeout),
                "partition startup header")
            header = json.loads(line.decode("utf-8"))
            self._validate_header(
                header, threads, expected_version,
                bool(allow_spinning), bool(preallocate_outputs))
            self.header = header
        except Exception:
            self.close()
            raise

    def _validate_header(self, header, threads, expected_version,
                         allow_spinning, preallocate_outputs):
        if header.get("kind") != "ready" or header.get("api_version") != 16:
            raise ValueError("partition runner protocol/API mismatch")
        if header.get("ort_version") != expected_version:
            raise ValueError("ORT runtime mismatch: expected %s, got %r" %
                             (expected_version, header.get("ort_version")))
        if header.get("threads") != int(threads):
            raise ValueError("partition runner thread count mismatch")
        if header.get("allow_spinning") is not allow_spinning:
            raise ValueError("partition runner spin mode mismatch")
        if header.get("preallocated_outputs") is not preallocate_outputs:
            raise ValueError("partition runner output allocation mode mismatch")
        load_ms = header.get("load_ms")
        if (not isinstance(load_ms, (int, float)) or
                not np.isfinite(load_ms) or load_ms < 0):
            raise ValueError("partition runner load_ms is invalid")
        for direction in ("inputs", "outputs"):
            expected = self.contract[direction]
            actual = header.get(direction)
            if not isinstance(actual, list) or len(actual) != len(expected):
                raise ValueError("partition runner %s count mismatch" % direction)
            for index, spec in enumerate(expected):
                wanted = {"name": spec["name"], "shape": list(spec["shape"]),
                          "dtype": "float32", "bytes": spec["bytes"]}
                if actual[index] != wanted:
                    raise ValueError("partition runner %s[%d] metadata mismatch" %
                                     (direction, index))
        for key, direction in (("input_bytes", "inputs"),
                               ("output_bytes", "outputs")):
            if header.get(key) != sum(item["bytes"]
                                      for item in self.contract[direction]):
                raise ValueError("partition runner %s mismatch" % key)

    def infer(self, tensors):
        if self._closed or self.process.poll() is not None:
            raise RuntimeError("partition runner process is not running")
        if isinstance(tensors, dict):
            values = [tensors[item["name"]]
                      for item in self.contract["inputs"]]
        else:
            values = list(tensors)
        if len(values) != len(self.contract["inputs"]):
            raise ValueError("wrong number of partition inputs")
        inputs = []
        for value, spec in zip(values, self.contract["inputs"]):
            array = np.asarray(value, dtype="<f4", order="C")
            if array.shape != tuple(spec["shape"]):
                raise ValueError("input %s shape mismatch" % spec["name"])
            if not np.isfinite(array).all():
                raise ValueError("input %s must be finite float32" % spec["name"])
            if array.nbytes != spec["bytes"]:
                raise ValueError("input %s byte count mismatch" % spec["name"])
            inputs.append(array)
        deadline = time.monotonic() + self.request_timeout
        try:
            for array, spec in zip(inputs, self.contract["inputs"]):
                _write_fd_all(self._input_fd, array, deadline,
                              "partition input %s" % spec["name"])
            outputs = []
            for spec in self.contract["outputs"]:
                array = np.empty(tuple(spec["shape"]), dtype="<f4", order="C")
                _read_fd_into(self._output_fd, array, deadline,
                              "partition output %s" % spec["name"])
                if not np.isfinite(array).all():
                    raise ValueError("output %s contains non-finite values" %
                                     spec["name"])
                outputs.append(array)
            line = _read_fd_line(self._output_fd, self._pending, deadline,
                                 "partition result header")
            result = json.loads(line.decode("utf-8"))
            expected_id = self._request_id + 1
            if (result.get("kind") != "result" or
                    result.get("request_id") != expected_id):
                raise ValueError("partition result id/kind mismatch")
            run_ms = result.get("run_ms")
            if (not isinstance(run_ms, (int, float)) or
                    not np.isfinite(run_ms) or run_ms < 0):
                raise ValueError("partition run_ms is invalid")
        except (IOError, OSError, EOFError, ValueError, UnicodeDecodeError,
                AttributeError, TimeoutError) as error:
            self.close()
            if isinstance(error, (ValueError, EOFError, AttributeError,
                                  TimeoutError)):
                raise
            raise RuntimeError("partition frame exchange failed: %s" % error)
        self._request_id = expected_id
        return ({spec["name"]: array for spec, array in
                 zip(self.contract["outputs"], outputs)}, float(run_ms))

    def close(self):
        if self._closed:
            return
        self._closed = True
        if self.process.stdin:
            try:
                self.process.stdin.close()
            except (IOError, OSError):
                pass
        try:
            self.process.wait(timeout=self.reap_timeout)
        except subprocess.TimeoutExpired:
            self.process.terminate()
            try:
                self.process.wait(timeout=self.reap_timeout)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=self.reap_timeout)
        if self.process.stdout:
            self.process.stdout.close()


class _LogicalOutputClient(object):
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


def load_optimized_split_clients(model_root, runner, manifest_path,
                                 expected_manifest_sha256, threads):
    """Return clients with the same keys and infer contract as the legacy loader."""
    try:
        from cnn_ddr_v5_runtime import load_v5_split_contracts
    except ImportError:
        from .cnn_ddr_v5_runtime import load_v5_split_contracts
    manifest_path = os.path.abspath(manifest_path)
    expected_path = os.path.abspath(os.path.join(model_root, "manifest.json"))
    if manifest_path != expected_path:
        raise ValueError("model manifest path must match the selected split bundle")
    bundle = load_v5_split_contracts(model_root, expected_manifest_sha256)
    clients = {}
    try:
        for name, record in bundle["models"].items():
            client = OptimizedOrtPartitionClient(
                [runner, "--stream", record["path"], str(int(threads))],
                record["contract"], threads=int(threads))
            source_name = record["contract"]["outputs"][0]["name"]
            clients[name] = _LogicalOutputClient(
                client, source_name, _LOGICAL_OUTPUT_NAMES[name])
    except Exception:
        for client in clients.values():
            try:
                client.close()
            except Exception:
                pass
        raise
    return clients, bundle["manifest_sha256"]


__all__ = ["OptimizedOrtPartitionClient", "load_optimized_split_clients"]
