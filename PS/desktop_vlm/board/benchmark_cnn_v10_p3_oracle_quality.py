#!/usr/bin/env python3
"""Quality-only full-model gate with exact P3 boundary-oracle injection.

This never represents P3 hardware execution or performance.  It accepts only
the two frozen bridge inputs whose HCW SHA256 values and full-W16 outputs are
bound by the P3 host oracle manifest, then delegates the rest of the pipeline
to the ordinary live benchmark.
"""
from __future__ import print_function

import argparse
import hashlib
import json
import os
import pathlib
import sys

import numpy as np

import benchmark_cnn_pipeline_v10_live as benchmark
import cnn_pipeline_v10_mixed_runtime as mixed


OUTPUT_SCALE = 9.687628574169352e-05


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


class P3BoundaryOracleClient(object):
    outputs_have_independent_lifetime = True

    def __init__(self, manifest_path):
        self.manifest_path = pathlib.Path(manifest_path).resolve()
        raw = self.manifest_path.read_bytes()
        self.manifest_sha256 = _sha(raw)
        manifest = json.loads(raw.decode("utf-8"))
        identity = manifest.get("runtime_identity", {})
        if (manifest.get("status") != "PASS" or
                identity.get("candidate_identity") != "A0002/sw10.2" or
                identity.get("input", {}).get("input_words") != 32768 or
                identity.get("final_output", {}).get("output_valid_words") != 16384):
            raise ValueError("P3 oracle manifest identity/word contract mismatch")
        self._outputs = {}
        for case in manifest.get("cases", [])[:2]:
            input_record = case.get("input_hcw_a16", {})
            output_record = case.get("output_i16", {})
            input_path = self.manifest_path.parent / input_record.get("path", "")
            output_path = self.manifest_path.parent / output_record.get("path", "")
            input_raw, output_raw = input_path.read_bytes(), output_path.read_bytes()
            if (len(input_raw) != 524288 or len(output_raw) != 262144 or
                    _sha(input_raw) != input_record.get("sha256") or
                    _sha(output_raw) != output_record.get("sha256")):
                raise ValueError("P3 oracle fixture size/SHA mismatch")
            self._outputs[input_record["sha256"]] = np.frombuffer(
                output_raw, dtype="<i2").copy().reshape(32, 128, 32)
        if len(self._outputs) != 2:
            raise ValueError("P3 oracle requires two distinct frozen fixtures")
        self.header = {
            "kind": "quality-only-p3-boundary-oracle-injection",
            "backend": "host-oracle-lookup-not-hardware",
            "manifest_sha256": self.manifest_sha256,
            "performance_valid": False,
            "threads": 0,
        }
        self._closed = False

    def infer_int16_hcw(self, value):
        if self._closed:
            raise RuntimeError("P3 boundary oracle is closed")
        if (not isinstance(value, mixed.Int16HCWActivation) or
                value.profile != 2 or value.logical_shape != (1, 64, 64, 64)):
            raise ValueError("P3 boundary oracle input contract mismatch")
        digest = _sha(value.payload.astype("<i2", copy=False).tobytes(order="C"))
        if digest not in self._outputs:
            raise ValueError("P3 boundary oracle rejects unknown N0 output SHA")
        output = mixed.Int16HCWActivation(
            self._outputs[digest], 0, OUTPUT_SCALE, (1, 128, 32, 32))
        return output, 0.0

    def close(self):
        self._closed = True


class SuffixInputCaptureClient(object):
    """Capture the N4 output consumed by suffix without changing inference."""

    def __init__(self, client, output_dir):
        self._client = client
        self.header = client.header
        self.output_dir = pathlib.Path(output_dir).resolve()
        self.output_dir.mkdir(parents=True, exist_ok=False)
        self._records = {}
        self._closed = False

    @property
    def outputs_have_independent_lifetime(self):
        return bool(getattr(self._client, "outputs_have_independent_lifetime",
                            False))

    @property
    def validates_tensor_finiteness(self):
        return bool(getattr(self._client, "validates_tensor_finiteness", False))

    def infer(self, tensors):
        if self._closed:
            raise RuntimeError("suffix input capture client is closed")
        values = list(tensors.values()) if isinstance(tensors, dict) else list(tensors)
        if len(values) != 1:
            raise ValueError("suffix input capture requires exactly one tensor")
        value = np.asarray(values[0], dtype="<f4", order="C")
        if not np.isfinite(value).all():
            raise ValueError("suffix input capture rejects non-finite tensor")
        raw = value.tobytes(order="C")
        digest = _sha(raw)
        if digest not in self._records:
            name = "suffix-input-%s.f32" % digest
            path = self.output_dir / name
            path.write_bytes(raw)
            self._records[digest] = {
                "path": name,
                "sha256": digest,
                "bytes": len(raw),
                "dtype": "float32-le",
                "shape": list(value.shape),
            }
        return self._client.infer(tensors)

    def close(self):
        if self._closed:
            return
        self._closed = True
        try:
            self._client.close()
        finally:
            manifest = {
                "schema": "cnn-v10-p3-domain-suffix-input-capture-v1",
                "scope": "N4 output / PS suffix input captured during P3 oracle quality run",
                "records": [self._records[key] for key in sorted(self._records)],
            }
            raw = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
            (self.output_dir / "manifest.json").write_bytes(raw)


def main(argv=None):
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--p3-oracle-manifest", required=True)
    parser.add_argument("--capture-suffix-input-dir")
    known, remaining = parser.parse_known_args(argv)
    manifest_path = os.path.abspath(known.p3_oracle_manifest)
    capture_dir = (os.path.abspath(known.capture_suffix_input_dir)
                   if known.capture_suffix_input_dir else None)
    original = mixed.build_v10_mixed_components

    def build(*args, **kwargs):
        requested = kwargs.pop("n1_manifest", None)
        if os.path.abspath(os.fspath(requested)) != manifest_path:
            raise ValueError("P3 oracle request identity mismatch")
        clients, model_sha, mixin_kwargs, evidence = original(
            *args, n1_manifest=None, **kwargs)
        previous = clients["network1-bridge"]
        oracle = P3BoundaryOracleClient(manifest_path)
        clients["network1-bridge"] = oracle
        previous.close()
        if capture_dir is not None:
            clients["suffix"] = SuffixInputCaptureClient(
                clients["suffix"], capture_dir)
        evidence = dict(evidence)
        active = list(evidence.get("active_quantized_partitions", []))
        active.append("n1")
        evidence["active_quantized_partitions"] = active
        partitions = dict(evidence["partition_selection"])
        partitions["network1-bridge"] = {
            "selected_backend": "quality-only-p3-boundary-oracle-injection",
            "precision": "full-W16 P3 integer oracle",
            "performance_valid": False,
            "manifest_sha256": oracle.manifest_sha256,
        }
        evidence["partition_selection"] = partitions
        evidence["p3_oracle_injection"] = {
            "manifest_sha256": oracle.manifest_sha256,
            "known_input_count": 2,
            "performance_valid": False,
            "hardware_execution": False,
        }
        evidence["p3_domain_suffix_input_capture"] = {
            "enabled": capture_dir is not None,
            "path": capture_dir,
            "excluded_from_timing_claims": True,
        }
        mixin_kwargs = dict(mixin_kwargs)
        mixin_kwargs["active_quantized_partitions"] = tuple(active)
        return clients, model_sha, mixin_kwargs, evidence

    mixed.build_v10_mixed_components = build
    if "--n1-manifest" not in remaining:
        remaining.extend(["--n1-manifest", manifest_path])
    try:
        return benchmark.main(remaining)
    finally:
        mixed.build_v10_mixed_components = original


if __name__ == "__main__":
    raise SystemExit(main())
