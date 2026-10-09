"""Capture the first distinct suffix inputs without changing client semantics."""
from __future__ import print_function

import hashlib
import json
import os
import pathlib

import numpy as np


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


class _SuffixCaptureClient(object):
    def __init__(self, client, directory, max_distinct):
        if (isinstance(max_distinct, bool) or not isinstance(max_distinct, int) or
                max_distinct <= 0):
            raise ValueError("max_distinct must be a positive integer")
        root = pathlib.Path(directory)
        if root.exists():
            raise ValueError("suffix capture directory already exists")
        root.mkdir(parents=True)
        self._client = client
        self._root = root
        self._max_distinct = max_distinct
        self._records = []
        self._by_sha = {}
        self._infer_calls = 0
        self._closed = False
        self.header = client.header
        self.outputs_have_independent_lifetime = (
            getattr(client, "outputs_have_independent_lifetime", False) is True)
        self.validates_tensor_finiteness = (
            getattr(client, "validates_tensor_finiteness", False) is True)
        self._write_manifest()

    @property
    def closed(self):
        return self._closed or bool(getattr(self._client, "closed", False))

    def __getattr__(self, name):
        return getattr(self._client, name)

    def _manifest(self):
        return {
            "schema": "cnn-v10.2-p3-suffix-input-capture-v1",
            "status": "CAPTURE_COMPLETE" if self._closed else "CAPTURE_ACTIVE",
            "performance_valid": False,
            "first_occurrence_order_preserved": True,
            "max_distinct": self._max_distinct,
            "distinct_count": len(self._records),
            "infer_calls": self._infer_calls,
            "records": list(self._records),
        }

    def _write_manifest(self):
        raw = (json.dumps(self._manifest(), indent=2, sort_keys=True) + "\n").encode("utf-8")
        temporary = self._root / "manifest.json.part"
        temporary.write_bytes(raw)
        os.replace(str(temporary), str(self._root / "manifest.json"))

    def infer(self, tensors):
        if self._closed:
            raise RuntimeError("suffix capture client is closed")
        if not isinstance(tensors, (list, tuple)) or len(tensors) != 1:
            raise ValueError("suffix capture expects one tensor")
        value = np.asarray(tensors[0])
        if (value.shape != (1, 256, 16, 16) or value.dtype != np.dtype("<f4") or
                not value.flags.c_contiguous or not np.isfinite(value).all()):
            raise ValueError("suffix capture input must be finite contiguous FP32 NCHW")
        raw = value.tobytes(order="C")
        digest = _sha(raw)
        self._infer_calls += 1
        if digest not in self._by_sha:
            if len(self._records) >= self._max_distinct:
                raise RuntimeError("suffix capture exceeded distinct-input bound")
            index = len(self._records)
            name = "suffix-input-%02d.f32" % index
            path = self._root / name
            path.write_bytes(raw)
            record = {
                "capture_index": index,
                "first_infer_call": self._infer_calls - 1,
                "path": name,
                "bytes": len(raw),
                "sha256": digest,
                "dtype": "<f4",
                "shape": [1, 256, 16, 16],
            }
            self._records.append(record)
            self._by_sha[digest] = index
        self._write_manifest()
        return self._client.infer(tensors)

    def close(self):
        if not self._closed:
            try:
                return self._client.close()
            finally:
                self._closed = True
                self._write_manifest()
        return None

    def capture_summary(self):
        path = self._root / "manifest.json"
        raw = path.read_bytes()
        manifest = json.loads(raw.decode("utf-8"))
        return {
            "manifest_path": str(path),
            "manifest_bytes": len(raw),
            "manifest_sha256": _sha(raw),
            "status": manifest["status"],
            "performance_valid": False,
            "distinct_count": manifest["distinct_count"],
            "infer_calls": manifest["infer_calls"],
            "records": manifest["records"],
        }


def wrap_suffix_capture_client(client, directory, max_distinct=2):
    """Return a transparent suffix client that records bounded distinct inputs."""
    return _SuffixCaptureClient(client, directory, max_distinct)


__all__ = ["wrap_suffix_capture_client"]
