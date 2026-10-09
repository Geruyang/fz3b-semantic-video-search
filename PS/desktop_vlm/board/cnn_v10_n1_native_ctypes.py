"""Fail-closed ctypes client for the packed N1 AArch64 native bridge."""
from __future__ import print_function

import ctypes
import hashlib
import json
import os
from pathlib import Path
import struct
import time

import numpy as np

try:
    from cnn_pipeline_v10_mixed_runtime import Int16HCWActivation
except ImportError:
    from .cnn_pipeline_v10_mixed_runtime import Int16HCWActivation


SCHEMA = "cnn-v10.1-n1-w8a16-native-v1"
MAGIC = b"N1W8A16\0"
HEADER = struct.Struct("<8sIIIIIfff")


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def _read_manifest(path):
    manifest_path = Path(path).resolve()
    raw = manifest_path.read_bytes()
    try:
        record = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError("N1 manifest is not valid UTF-8 JSON") from exc
    if record.get("schema") != SCHEMA or record.get("status") != "PASS":
        raise ValueError("N1 manifest schema/status is not a passing native artifact")
    if record.get("source_model", {}).get("sha256") is None:
        raise ValueError("N1 manifest is missing source model identity")
    if record.get("native_threads") != 3:
        raise ValueError("N1 manifest native_threads must be 3")
    return manifest_path, raw, record


class CtypesN1NativeClient(object):
    """Run one packed model with independent INT16 HCW output ownership."""

    def __init__(self, manifest_path, library_path, expected_manifest_sha256):
        self.manifest_path, manifest_raw, self.manifest = _read_manifest(manifest_path)
        self.manifest_sha256 = _sha256(manifest_raw)
        if (not isinstance(expected_manifest_sha256, str) or
                self.manifest_sha256 != expected_manifest_sha256.lower()):
            raise ValueError("N1 manifest SHA256 does not match the expected identity")
        self.library_path = Path(library_path).resolve()
        self.library_sha256 = _sha256(self.library_path.read_bytes())
        expected_library_sha = self.manifest.get("native_abi", {}).get("library_sha256")
        if expected_library_sha is not None and self.library_sha256 != expected_library_sha:
            raise ValueError("N1 native library SHA256 mismatch")
        self._library = ctypes.CDLL(os.fspath(self.library_path))
        abi = self._library.cnn_v10_n1_native_abi_version
        abi.argtypes = []
        abi.restype = ctypes.c_int
        if abi() != 1 or self.manifest.get("native_abi", {}).get("version") != 1:
            raise ValueError("N1 native ABI version mismatch")
        if self.manifest.get("native_abi", {}).get("threads") != 3:
            raise ValueError("N1 native ABI thread count differs from manifest")
        expected_symbol = self.manifest.get("native_abi", {}).get("symbol")
        if expected_symbol != "cnn_v10_n1_infer_int16_hcw":
            raise ValueError("N1 manifest names an unsupported native symbol")
        expected_scalar = self.manifest.get("native_abi", {}).get("scalar_symbol")
        if expected_scalar != "cnn_v10_n1_infer_int16_hcw_scalar":
            raise ValueError("N1 manifest names an unsupported scalar validation symbol")
        expected_profile = self.manifest.get("native_abi", {}).get("profile_symbol")
        if expected_profile != "cnn_v10_n1_infer_int16_hcw_profile":
            raise ValueError("N1 manifest names an unsupported stage-profile symbol")
        try:
            self._infer = getattr(self._library, expected_symbol)
            self._infer_scalar = getattr(self._library, expected_scalar)
            self._infer_profile = getattr(self._library, expected_profile)
        except AttributeError as exc:
            raise ValueError("N1 native library is missing an inference export") from exc
        for function in (self._infer, self._infer_scalar):
            function.argtypes = [ctypes.POINTER(ctypes.c_uint8), ctypes.c_size_t,
                                 ctypes.POINTER(ctypes.c_int16),
                                 ctypes.POINTER(ctypes.c_int16)]
            function.restype = ctypes.c_int
        self._infer_profile.argtypes = [ctypes.POINTER(ctypes.c_uint8), ctypes.c_size_t,
                                        ctypes.POINTER(ctypes.c_int16),
                                        ctypes.POINTER(ctypes.c_int16),
                                        ctypes.POINTER(ctypes.c_double),
                                        ctypes.POINTER(ctypes.c_double)]
        self._infer_profile.restype = ctypes.c_int

        packed = self.manifest["packed_parameters"]
        params_path = (self.manifest_path.parent / packed["path"]).resolve()
        if params_path.parent != self.manifest_path.parent.resolve():
            raise ValueError("packed parameter path escapes the manifest directory")
        self._params = params_path.read_bytes()
        if len(self._params) != packed.get("bytes") or _sha256(self._params) != packed.get("sha256"):
            raise ValueError("packed parameter size/SHA256 mismatch")
        for name, section in packed.get("sections", {}).items():
            offset, size = section.get("offset"), section.get("bytes")
            if (type(offset) is not int or type(size) is not int or offset < HEADER.size or
                    size < 0 or offset + size > len(self._params)):
                raise ValueError("packed section %s has invalid bounds" % name)
            if _sha256(self._params[offset:offset + size]) != section.get("sha256"):
                raise ValueError("packed section %s SHA256 mismatch" % name)
        if len(self._params) < HEADER.size:
            raise ValueError("packed parameter file is truncated")
        expected_bytes = (HEADER.size + 128 * 49 + 128 * 4 * 2 + 128 * 49 * 4 + 128
                          + 128 * 128 + 128 * 4 * 2 + 128 * 128 * 4 + 128)
        if len(self._params) != expected_bytes:
            raise ValueError("packed parameter length does not match N1 ABI")
        self._params_buffer = ctypes.create_string_buffer(self._params)
        self._params_pointer = ctypes.cast(
            self._params_buffer, ctypes.POINTER(ctypes.c_uint8))
        magic, version, dwc, pwc, outc, reserved, input_scale, pw_scale, output_scale = HEADER.unpack_from(self._params)
        if (magic != MAGIC or version != 1 or (dwc, pwc, outc, reserved) != (128, 128, 128, 0)):
            raise ValueError("packed parameter header does not match N1 ABI")
        self._input_scale = float(input_scale)
        self._pw_input_scale = float(pw_scale)
        self._output_scale = float(output_scale)
        if (self.manifest["input"].get("scale") != "profile2_output" or
                float(self.manifest["input"].get("arithmetic_scale_value_f32")) != self._input_scale or
                self.manifest["input"].get("packed_scale_f32_hex") !=
                struct.pack("<f", self._input_scale).hex()):
            raise ValueError("manifest input scale differs from packed ABI")
        if (self.manifest["output"].get("scale") != "profile0_input" or
                float(self.manifest["output"].get("arithmetic_scale_value_f32")) != self._output_scale or
                self.manifest["output"].get("packed_scale_f32_hex") !=
                struct.pack("<f", self._output_scale).hex()):
            raise ValueError("manifest output scale differs from packed ABI")
        self._input_logical_scale = float(
            self.manifest["input"].get("logical_pl_scale_value_f64"))
        self._output_logical_scale = float(
            self.manifest["output"].get("logical_pl_scale_value_f64"))
        if (float(np.float32(self._input_logical_scale)) != self._input_scale or
                float(np.float32(self._output_logical_scale)) != self._output_scale):
            raise ValueError("logical PL scale does not map exactly to packed FP32 scale")
        if float(self.manifest["pw_input_a16_scale"]) != self._pw_input_scale:
            raise ValueError("manifest PW input scale differs from packed ABI")
        for direction in ("input", "output"):
            item = self.manifest[direction]
            expected = ((2, [1, 64, 64, 64]) if direction == "input"
                        else (0, [1, 128, 32, 32]))
            if item.get("profile") != expected[0] or item.get("shape") != expected[1] or item.get("layout") != "HCW" or item.get("dtype") != "<i2":
                raise ValueError("N1 manifest %s boundary does not match frozen HCW contract" % direction)
        self._input_shape = (64, 64, 64)
        self._output_shape = (32, 128, 32)
        self.header = {
            "kind": "ready-native-n1", "protocol": 1,
            "native_abi_version": 1,
            "backend": "W8A16Acc32-sensitive-FP32",
            "manifest_sha256": self.manifest_sha256,
            "library_sha256": self.library_sha256,
            "source_sha256": self.manifest["native_abi"]["source_sha256"],
            "threads": 3,
        }
        self._closed = False

    def _infer_int16_hcw(self, activation, scalar, profile=False):
        if self._closed:
            raise RuntimeError("N1 native client is closed")
        if not isinstance(activation, Int16HCWActivation):
            raise TypeError("infer_int16_hcw requires Int16HCWActivation")
        if activation.profile != 2 or tuple(activation.logical_shape) != (1, 64, 64, 64):
            raise ValueError("N1 input must be profile-2 [1,64,64,64]")
        if activation.scale != self._input_logical_scale:
            raise ValueError("N1 input scale does not match logical profile-2 boundary")
        payload = np.asarray(activation.payload)
        if (payload.shape != self._input_shape or payload.dtype != np.dtype("<i2") or
                not payload.flags.c_contiguous):
            raise ValueError("N1 input payload must be contiguous little-endian INT16 HCW")
        source = np.ascontiguousarray(payload, dtype="<i2")
        output = np.empty(self._output_shape, dtype="<i2")
        src_ptr = source.ctypes.data_as(ctypes.POINTER(ctypes.c_int16))
        out_ptr = output.ctypes.data_as(ctypes.POINTER(ctypes.c_int16))
        start = time.perf_counter()
        dw_ms, pw_ms = ctypes.c_double(), ctypes.c_double()
        if profile:
            status = self._infer_profile(
                self._params_pointer, len(self._params), src_ptr, out_ptr,
                ctypes.byref(dw_ms), ctypes.byref(pw_ms))
        else:
            function = self._infer_scalar if scalar else self._infer
            status = function(self._params_pointer, len(self._params), src_ptr, out_ptr)
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        if status != 0:
            messages = {-1: "invalid N1 native ABI or buffer", -2: "N1 native allocation failed",
                        -3: "N1 observed Acc32 overflow",
                        -4: "N1 could not launch all three workers"}
            raise RuntimeError(messages.get(status, "N1 native bridge returned status %d" % status))
        # The activation constructor takes a copy, so result lifetime is
        # independent of this stack-local NumPy output buffer and future calls.
        result = Int16HCWActivation(output, profile=0,
                                    scale=self._output_logical_scale,
                                    logical_shape=(1, 128, 32, 32))
        if profile:
            return result, elapsed_ms, dw_ms.value, pw_ms.value
        return result, elapsed_ms

    def infer_int16_hcw(self, activation):
        return self._infer_int16_hcw(activation, False)

    def infer_int16_hcw_scalar(self, activation):
        """Run the shared scalar PW implementation for target comparisons."""
        return self._infer_int16_hcw(activation, True)

    def infer_int16_hcw_profile(self, activation):
        """Return result, total wall time, DW wall time, and PW wall time."""
        return self._infer_int16_hcw(activation, False, profile=True)

    def close(self):
        """Match the partition-client lifecycle; ctypes owns no child process."""
        self._closed = True


__all__ = ["CtypesN1NativeClient"]
