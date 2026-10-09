#!/usr/bin/env python3
"""Run the validated MobileCLIP-S1 CPU split through three persistent ORT processes.

The protocol is binary float32 tensors in manifest order, with one JSON ready
line at startup and one JSON result line after each binary output frame.
"""
import hashlib
import json
import os
import queue
import subprocess
import threading
import time

import numpy as np


EXPECTED_SOURCE_SHA256 = "5b8494a03aa81a59b2bd0a3f3dcba91813363bb65060c32d6e4bf4243f8e3587"
EXPECTED_MANIFEST_SHA256 = "ab19a87c8fac6661611f6e35bd2b31fc59e2be4b133df7a663611c238b2bd8c4"
STAGE_NAMES = ("prefix", "region", "suffix")
MAX_TOTAL_BYTES = 128 * 1024 * 1024


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _tensor_contract(item):
    name = item.get("name")
    shape = item.get("shape")
    if not isinstance(name, str) or not name:
        raise ValueError("manifest tensor name is missing")
    if not isinstance(shape, list) or not shape or len(shape) > 8:
        raise ValueError("manifest tensor shape is invalid for %s" % name)
    count = 1
    for dim in shape:
        if not isinstance(dim, int) or dim <= 0 or count > MAX_TOTAL_BYTES // 4 // dim:
            raise ValueError("manifest tensor shape is dynamic or too large for %s" % name)
        count *= dim
    expected_bytes = count * 4
    if item.get("bytes_fp32") != expected_bytes or expected_bytes > 64 * 1024 * 1024:
        raise ValueError("manifest float32 byte count mismatch for %s" % name)
    return {"name": name, "shape": tuple(shape), "bytes": expected_bytes,
            "dtype": "float32"}


def _validate_manifest(manifest):
    if manifest.get("source_sha256") != EXPECTED_SOURCE_SHA256:
        raise ValueError("split manifest source model SHA256 mismatch")
    stages = manifest.get("stages")
    if not isinstance(stages, list) or [x.get("stage") for x in stages] != list(STAGE_NAMES):
        raise ValueError("manifest must declare prefix, region, suffix in order")
    parsed = {}
    total_model_bytes = 0
    for item in stages:
        name = item["stage"]
        inputs, outputs = item.get("inputs"), item.get("outputs")
        if not isinstance(inputs, list) or not 1 <= len(inputs) <= 8:
            raise ValueError("invalid %s inputs" % name)
        if not isinstance(outputs, list) or not 1 <= len(outputs) <= 8:
            raise ValueError("invalid %s outputs" % name)
        parsed[name] = {"inputs": [_tensor_contract(x) for x in inputs],
                        "outputs": [_tensor_contract(x) for x in outputs],
                        "sha256": item.get("sha256"), "bytes": item.get("bytes")}
        if not isinstance(parsed[name]["sha256"], str) or len(parsed[name]["sha256"]) != 64:
            raise ValueError("invalid %s model SHA256" % name)
        if not isinstance(parsed[name]["bytes"], int) or parsed[name]["bytes"] <= 0:
            raise ValueError("invalid %s model byte count" % name)
        total_model_bytes += parsed[name]["bytes"]
        for direction in ("inputs", "outputs"):
            if sum(t["bytes"] for t in parsed[name][direction]) > MAX_TOTAL_BYTES:
                raise ValueError("%s %s exceed protocol limit" % (name, direction))

    # Verify the graph cut and keep the prefix tensor as the residual bypass.
    prefix_out = parsed["prefix"]["outputs"]
    region_in, region_out = parsed["region"]["inputs"], parsed["region"]["outputs"]
    suffix_in = parsed["suffix"]["inputs"]
    if len(prefix_out) != 1 or len(region_in) != 1 or len(region_out) != 1 or len(suffix_in) != 2:
        raise ValueError("split tensor arity does not match the validated S1 cut")
    if prefix_out[0] != region_in[0] or region_out[0] != suffix_in[0]:
        raise ValueError("manifest stage tensor names/order do not join")
    bypass = prefix_out[0]
    if suffix_in[1] != bypass:
        raise ValueError("suffix must receive the original prefix tensor as residual bypass")
    feature = parsed["suffix"]["outputs"]
    if len(feature) != 1 or feature[0]["name"] != "features" or feature[0]["shape"] != (1, 512):
        raise ValueError("suffix feature output contract mismatch")
    if total_model_bytes > 256 * 1024 * 1024:
        raise ValueError("split model bundle exceeds size limit")
    return parsed


def _normalize_expected_sha256(value):
    if (not isinstance(value, str) or len(value) != 64 or
            any(char not in "0123456789abcdefABCDEF" for char in value)):
        raise ValueError("expected_manifest_sha256 must be 64 hexadecimal characters")
    return value.lower()


def _prepare_preprocessed_tensor(tensor, expected_shape):
    """Accept the current CHW preprocess result or a ready NCHW tensor."""
    array = np.asarray(tensor)
    expected_shape = tuple(expected_shape)
    if array.shape == expected_shape:
        return array
    if len(expected_shape) > 1 and expected_shape[0] == 1 and array.shape == expected_shape[1:]:
        return array.reshape(expected_shape)
    raise ValueError("preprocessed image shape %r does not match manifest input %r" %
                     (array.shape, expected_shape))


def _read_exact(stream, count):
    chunks = []
    remaining = count
    while remaining:
        block = stream.read(remaining)
        if not block:
            received = count - remaining
            raise EOFError("short response frame: expected %d bytes, received %d" %
                           (count, received))
        chunks.append(block)
        remaining -= len(block)
    return b"".join(chunks)


def _write_all(stream, payload):
    view = memoryview(payload)
    offset = 0
    while offset < len(view):
        count = stream.write(view[offset:])
        if count is None or count <= 0:
            raise IOError("short write while sending tensor frame")
        offset += count


def _call_with_timeout(callback, timeout, label):
    """Run potentially blocking pipe I/O with a Python 3.6-compatible deadline."""
    result_queue = queue.Queue(1)

    def invoke():
        try:
            result_queue.put((True, callback()))
        except BaseException as error:
            result_queue.put((False, error))

    worker = threading.Thread(target=invoke)
    worker.daemon = True
    worker.start()
    try:
        succeeded, value = result_queue.get(timeout=max(0.0, timeout))
    except queue.Empty:
        raise TimeoutError("%s exceeded %.3f second deadline" % (label, timeout))
    if not succeeded:
        raise value
    return value


class OrtPartitionClient(object):
    """One persistent C runner and its manifest-derived binary contract."""
    def __init__(self, command, contract, threads=2, expected_version="1.16.3",
                 startup_timeout=30.0, request_timeout=30.0, reap_timeout=5.0):
        self.contract = contract
        self.startup_timeout = float(startup_timeout)
        self.request_timeout = float(request_timeout)
        self.reap_timeout = float(reap_timeout)
        if min(self.startup_timeout, self.request_timeout, self.reap_timeout) <= 0:
            raise ValueError("startup, request, and reap timeouts must be positive")
        self.process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=None, bufsize=0)
        self._closed = False
        self._request_id = 0
        try:
            line = _call_with_timeout(self.process.stdout.readline, self.startup_timeout,
                                      "partition startup header")
            if not line:
                raise RuntimeError("partition runner exited before its ready header")
            try:
                header = json.loads(line.decode("utf-8"))
            except (ValueError, UnicodeDecodeError) as error:
                raise ValueError("invalid partition ready header: %s" % error)
            self._validate_header(header, threads, expected_version)
            self.header = header
        except Exception:
            self.close()
            raise

    def _validate_header(self, header, threads, expected_version):
        if header.get("kind") != "ready" or header.get("api_version") != 16:
            raise ValueError("partition runner protocol/API mismatch")
        if header.get("ort_version") != expected_version:
            raise ValueError("ORT runtime mismatch: expected %s, got %r" %
                             (expected_version, header.get("ort_version")))
        if header.get("threads") != int(threads):
            raise ValueError("partition runner thread count mismatch")
        for key in ("load_ms",):
            value = header.get(key)
            if not isinstance(value, (int, float)) or not np.isfinite(value) or value < 0:
                raise ValueError("partition runner %s is invalid" % key)
        for direction in ("inputs", "outputs"):
            expected = self.contract[direction]
            actual = header.get(direction)
            if not isinstance(actual, list) or len(actual) != len(expected):
                raise ValueError("partition runner %s count mismatch" % direction)
            for index, spec in enumerate(expected):
                entry = actual[index]
                wanted = {"name": spec["name"], "shape": list(spec["shape"]),
                          "dtype": "float32", "bytes": spec["bytes"]}
                if entry != wanted:
                    raise ValueError("partition runner %s[%d] metadata mismatch" % (direction, index))
        for key, direction in (("input_bytes", "inputs"), ("output_bytes", "outputs")):
            total = sum(item["bytes"] for item in self.contract[direction])
            if header.get(key) != total:
                raise ValueError("partition runner %s mismatch" % key)

    def infer(self, tensors):
        if self._closed or self.process.poll() is not None:
            raise RuntimeError("partition runner process is not running")
        if isinstance(tensors, dict):
            values = [tensors[item["name"]] for item in self.contract["inputs"]]
        else:
            values = list(tensors)
        if len(values) != len(self.contract["inputs"]):
            raise ValueError("wrong number of partition inputs")
        payloads = []
        for value, spec in zip(values, self.contract["inputs"]):
            array = np.asarray(value)
            if array.shape != spec["shape"]:
                raise ValueError("input %s shape mismatch" % spec["name"])
            with np.errstate(over="ignore", invalid="ignore"):
                array = np.asarray(array, dtype="<f4", order="C")
            if not np.isfinite(array).all():
                raise ValueError("input %s must be finite float32" % spec["name"])
            raw = array.tobytes(order="C")
            if len(raw) != spec["bytes"]:
                raise ValueError("input %s byte count mismatch" % spec["name"])
            payloads.append(raw)
        try:
            deadline = time.time() + self.request_timeout

            def remaining(label):
                left = deadline - time.time()
                if left <= 0:
                    raise TimeoutError("partition request exceeded %.3f second deadline" % self.request_timeout)
                return left

            for raw in payloads:
                _call_with_timeout(lambda raw=raw: _write_all(self.process.stdin, raw),
                                   remaining("input write"), "partition input write")
            _call_with_timeout(self.process.stdin.flush, remaining("input flush"), "partition input flush")
            output_arrays = []
            for spec in self.contract["outputs"]:
                raw = _call_with_timeout(lambda count=spec["bytes"]: _read_exact(self.process.stdout, count),
                                         remaining("output read"), "partition output read")
                array = np.frombuffer(raw, dtype="<f4").copy().reshape(spec["shape"])
                if not np.isfinite(array).all():
                    raise ValueError("output %s contains non-finite values" % spec["name"])
                output_arrays.append(array)
            line = _call_with_timeout(self.process.stdout.readline, remaining("result header"),
                                      "partition result header")
            if not line:
                raise EOFError("runner closed before result header")
            try:
                result = json.loads(line.decode("utf-8"))
            except (ValueError, UnicodeDecodeError) as error:
                raise ValueError("invalid partition result header: %s" % error)
            expected_id = self._request_id + 1
            if result.get("kind") != "result" or result.get("request_id") != expected_id:
                raise ValueError("partition result id/kind mismatch")
            run_ms = result.get("run_ms")
            if not isinstance(run_ms, (int, float)) or not np.isfinite(run_ms) or run_ms < 0:
                raise ValueError("partition run_ms is invalid")
        except (IOError, OSError, EOFError, ValueError, UnicodeDecodeError, AttributeError,
                TimeoutError) as error:
            self.close()
            if isinstance(error, (ValueError, EOFError, AttributeError, TimeoutError)):
                raise
            raise RuntimeError("partition frame exchange failed: %s" % error)
        self._request_id = expected_id
        return {spec["name"]: array for spec, array in zip(self.contract["outputs"], output_arrays)}, float(run_ms)

    def close(self):
        if self._closed:
            return
        self._closed = True
        if self.process.stdin:
            try:
                self.process.stdin.close()
            except (IOError, OSError):
                pass
        failure = None
        try:
            self.process.wait(timeout=self.reap_timeout)
        except subprocess.TimeoutExpired:
            try:
                self.process.terminate()
            except (OSError, ProcessLookupError):
                pass
            try:
                self.process.wait(timeout=self.reap_timeout)
            except subprocess.TimeoutExpired:
                try:
                    self.process.kill()
                except (OSError, ProcessLookupError):
                    pass
                try:
                    self.process.wait(timeout=self.reap_timeout)
                except subprocess.TimeoutExpired:
                    failure = RuntimeError("partition runner PID %d did not exit after kill" % self.process.pid)
        if self.process.stdout:
            self.process.stdout.close()
        if failure is not None:
            raise failure


class PersistentPartitionS1(object):
    """Three persistent sessions with manifest-checked in-memory tensor flow."""
    def __init__(self, split_dir, runner_path, threads=2, runner_command_factory=None,
                 expected_manifest_sha256=EXPECTED_MANIFEST_SHA256):
        if not 1 <= int(threads) <= 8:
            raise ValueError("threads must be in [1,8]")
        expected_manifest_sha256 = _normalize_expected_sha256(expected_manifest_sha256)
        self.split_dir = os.path.abspath(split_dir)
        manifest_path = os.path.join(self.split_dir, "manifest.json")
        actual_manifest_sha256 = sha256(manifest_path)
        if actual_manifest_sha256.lower() != expected_manifest_sha256:
            raise ValueError("split manifest SHA256 does not match trusted expected hash")
        with open(manifest_path, "r") as stream:
            manifest = json.load(stream)
        self.contracts = _validate_manifest(manifest)
        self.manifest = manifest
        self.manifest_sha256 = actual_manifest_sha256
        self.model_sha256 = {}
        model_paths = {}
        for name in STAGE_NAMES:
            path = os.path.join(self.split_dir, name + ".onnx")
            actual = sha256(path)
            if actual != self.contracts[name]["sha256"]:
                raise ValueError("%s model SHA256 does not match split manifest" % name)
            if os.path.getsize(path) != self.contracts[name]["bytes"]:
                raise ValueError("%s model size does not match split manifest" % name)
            self.model_sha256[name] = actual
            model_paths[name] = path
        self.clients = []
        try:
            for name in STAGE_NAMES:
                command = (runner_command_factory(name, model_paths[name], int(threads))
                           if runner_command_factory is not None else
                           [os.path.abspath(runner_path), "--stream", model_paths[name], str(int(threads))])
                client = OrtPartitionClient(command, self.contracts[name], int(threads))
                self.clients.append(client)
        except Exception:
            self.close()
            raise

    def infer_tensor(self, tensor):
        prefix, region, suffix = self.clients
        prefix_out, prefix_ms = prefix.infer([tensor])
        # Keep the original prefix output alive for suffix input 2 (residual).
        bypass_name = self.contracts["prefix"]["outputs"][0]["name"]
        bypass = prefix_out[bypass_name]
        region_out, region_ms = region.infer([bypass])
        features_name = self.contracts["suffix"]["outputs"][0]["name"]
        suffix_out, suffix_ms = suffix.infer([region_out[self.contracts["region"]["outputs"][0]["name"]], bypass])
        return {"features": suffix_out[features_name],
                "stage_run_ms": {"prefix": prefix_ms, "region": region_ms, "suffix": suffix_ms},
                "manifest_sha256": self.manifest_sha256,
                "model_sha256": dict(self.model_sha256)}

    def infer_image(self, image_path):
        try:
            from preprocess_s1 import preprocess
        except ImportError:
            from .preprocess_s1 import preprocess
        tensor, info = preprocess(image_path)
        input_shape = self.contracts["prefix"]["inputs"][0]["shape"]
        model_tensor = _prepare_preprocessed_tensor(tensor, input_shape)
        result = self.infer_tensor(model_tensor)
        result["preprocess"] = info
        result["image_sha256"] = sha256(image_path)
        return result

    def close(self):
        failures = []
        for client in reversed(getattr(self, "clients", [])):
            try:
                client.close()
            except Exception as error:
                failures.append(error)
        self.clients = []
        if failures:
            raise RuntimeError("failed to reap %d partition process(es): %s" %
                               (len(failures), failures[0]))

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
