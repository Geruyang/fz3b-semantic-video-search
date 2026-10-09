"""Fail-closed V10 PS candidate assembly and exact native boundary hooks.

The shared-mmap FP32 clients, exact C activation quantizer, native N1 bridge,
and target-qualified suffix candidate are explicit selections. Passing a
rejected or incomplete artifact raises instead of silently selecting FP32.
"""
from __future__ import print_function

import hashlib
import json
import math
import os

import numpy as np

try:
    from activation_buffers import ActivationBufferWorkspace
    from cnn_v10_native_quant import V10NativeQuantWorkspace
    from cnn_v10_native_quant_ctypes import CtypesV10Quantizer
    from cnn_v10_ps_shm_clients import load_shm_split_clients
except ImportError:
    from .activation_buffers import ActivationBufferWorkspace
    from .cnn_v10_native_quant import V10NativeQuantWorkspace
    from .cnn_v10_native_quant_ctypes import CtypesV10Quantizer
    from .cnn_v10_ps_shm_clients import load_shm_split_clients


def _sha256_path(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _candidate_failure(path, label):
    """Validate enough identity to return a precise fail-closed error."""
    absolute = os.path.abspath(os.fspath(path))
    if not os.path.isfile(absolute):
        raise ValueError("%s candidate does not exist: %s" % (label, absolute))
    identity = _sha256_path(absolute)
    try:
        with open(absolute, "rb") as stream:
            record = json.loads(stream.read().decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        raise ValueError(
            "%s candidate %s (%s) lacks a validated JSON selection manifest" %
            (label, absolute, identity))
    status = record.get("status")
    if status != "PASS":
        raise ValueError("%s candidate gate is not PASS: status=%r sha256=%s" %
                         (label, status, identity))
    raise ValueError(
        "%s candidate manifest passed its local gate but no executable backend "
        "is bound; refusing FP32 fallback (sha256=%s)" % (label, identity))


def _manifest_child(root, record, label):
    if not isinstance(record, dict):
        raise ValueError("%s record is missing" % label)
    relative = record.get("path")
    if (not isinstance(relative, str) or not relative or os.path.isabs(relative) or
            ".." in relative.replace("\\", "/").split("/")):
        raise ValueError("%s path is unsafe" % label)
    path = os.path.abspath(os.path.join(root, relative))
    if os.path.commonpath((root, path)) != root:
        raise ValueError("%s path escapes the selection package" % label)
    if (not os.path.isfile(path) or isinstance(record.get("bytes"), bool) or
            os.path.getsize(path) != record.get("bytes") or
            _sha256_path(path) != record.get("sha256")):
        raise ValueError("%s extent/SHA mismatch" % label)
    return path


def _load_suffix_selection(path, model_root):
    manifest_path = os.path.abspath(os.fspath(path))
    root = os.path.dirname(manifest_path)
    if not os.path.isfile(manifest_path):
        raise ValueError("suffix selection manifest does not exist")
    with open(manifest_path, "rb") as stream:
        manifest = json.loads(stream.read().decode("utf-8"))
    if (manifest.get("schema") != "cnn-v10.1-suffix-w8a8-selection-v2" or
            manifest.get("status") != "PASS"):
        raise ValueError("suffix selection schema/status mismatch")
    source = os.path.join(os.path.abspath(model_root), "suffix.onnx")
    if (not os.path.isfile(source) or
            _sha256_path(source) != manifest.get("source_model_sha256")):
        raise ValueError("suffix selection source model identity mismatch")
    candidate = _manifest_child(root, manifest.get("candidate"), "suffix candidate")
    evidence = manifest.get("evidence")
    required = {"host_profile", "host_receipt", "target_result",
                "target_wrapper_receipt", "target_profile_receipt",
                "target_profile_wrapper_receipt", "target_profile_analysis",
                "target_kernel_classification", "target_optimized_model"}
    if not isinstance(evidence, dict) or set(evidence) != required:
        raise ValueError("suffix selection evidence set is incomplete")
    records = dict((name, _manifest_child(root, evidence[name], name))
                   for name in required)
    with open(records["host_receipt"], "rb") as stream:
        host_receipt = json.loads(stream.read().decode("utf-8"))
    with open(records["target_result"], "rb") as stream:
        target_result = json.loads(stream.read().decode("utf-8"))
    with open(records["target_profile_receipt"], "rb") as stream:
        target_profile = json.loads(stream.read().decode("utf-8"))
    with open(records["target_kernel_classification"], "rb") as stream:
        kernel_classification = json.loads(stream.read().decode("utf-8"))
    candidate_sha = _sha256_path(candidate)
    integer_contract = manifest.get("target_integer_kernel_contract")
    if not isinstance(integer_contract, dict):
        raise ValueError("suffix target integer kernel contract is missing")
    kernel_count = integer_contract.get("kernel_count")
    qconv_count = integer_contract.get("qlinear_conv_count")
    qmatmul_count = integer_contract.get("qlinear_matmul_count")
    if (integer_contract.get("provider") != "CPUExecutionProvider" or
            any(isinstance(value, bool) or not isinstance(value, int) or value < 0
                for value in (kernel_count, qconv_count, qmatmul_count)) or
            kernel_count <= 0 or kernel_count != qconv_count + qmatmul_count):
        raise ValueError("suffix target integer kernel contract is invalid")
    if (host_receipt.get("status") != "PASS" or
            target_result.get("status") != "PASS_TARGET_ORT116_ENGINEERING_GATE" or
            target_result.get("candidate_gate") is not True or
            target_result.get("candidate_sha256") != candidate_sha or
            target_profile.get("status") !=
            "PASS_CANDIDATE_PROFILE_AND_ENGINEERING_ERROR_GATE" or
            target_profile.get("candidate_sha256") != candidate_sha or
            kernel_classification.get("status") !=
            "PASS_TARGET_ORT_INTEGER_KERNELS_CONFIRMED" or
            kernel_classification.get("candidate_sha256") != candidate_sha or
            kernel_classification.get("integer_kernel_count") != kernel_count or
            kernel_classification.get("qlinear_conv_count") != qconv_count or
            kernel_classification.get("qlinear_matmul_count") != qmatmul_count or
            kernel_classification.get("optimized_model_sha256") !=
            _sha256_path(records["target_optimized_model"])):
        raise ValueError("suffix selection host/target gate mismatch")
    return {"manifest_path": manifest_path,
            "manifest_sha256": _sha256_path(manifest_path),
            "candidate_path": candidate, "candidate_sha256": candidate_sha,
            "target_result_sha256": _sha256_path(records["target_result"]),
            "target_profile_sha256": _sha256_path(records["target_profile_receipt"]),
            "target_kernel_classification_sha256": _sha256_path(
                records["target_kernel_classification"]),
            "target_integer_kernel_contract": dict(integer_contract),
            "precision": manifest["candidate"].get("precision")}


def _load_n1_selection(path, model_root):
    """Load the target-proven native N1 package without trusting path names."""
    selection_path = os.path.abspath(os.fspath(path))
    root = os.path.dirname(selection_path)
    if not os.path.isfile(selection_path):
        raise ValueError("N1 selection manifest does not exist")
    with open(selection_path, "rb") as stream:
        selection = json.loads(stream.read().decode("utf-8"))
    if (selection.get("schema") != "cnn-v10.1-n1-w8a16-selection-v1" or
            selection.get("status") != "PASS"):
        raise ValueError("N1 selection schema/status mismatch")
    native_manifest_path = _manifest_child(
        root, selection.get("native_manifest"), "N1 native manifest")
    native_library_path = _manifest_child(
        root, selection.get("native_library"), "N1 native library")
    native_params_path = _manifest_child(
        root, selection.get("packed_parameters"), "N1 packed parameters")
    target_receipt_path = _manifest_child(
        root, selection.get("target_receipt"), "N1 target receipt")
    target_result_path = _manifest_child(
        root, selection.get("target_result"), "N1 target result")
    with open(native_manifest_path, "rb") as stream:
        native_manifest = json.loads(stream.read().decode("utf-8"))
    with open(target_receipt_path, "rb") as stream:
        target_receipt = json.loads(stream.read().decode("utf-8"))
    with open(target_result_path, "rb") as stream:
        target_result = json.loads(stream.read().decode("utf-8"))
    source_path = os.path.join(os.path.abspath(model_root), "network1-bridge.onnx")
    source_sha = _sha256_path(source_path) if os.path.isfile(source_path) else None
    native_manifest_sha = _sha256_path(native_manifest_path)
    library_sha = _sha256_path(native_library_path)
    params_sha = _sha256_path(native_params_path)
    sensitive_channels = native_manifest.get("pw_fp32_channels")
    selection_sensitive = selection.get("precision", {}).get("pw_fp32_channels")
    if (native_manifest.get("schema") != "cnn-v10.1-n1-w8a16-native-v1" or
            native_manifest.get("status") != "PASS" or
            source_sha != native_manifest.get("source_model", {}).get("sha256") or
            source_sha != selection.get("source_model_sha256") or
            native_manifest.get("native_abi", {}).get("library_sha256") != library_sha or
            native_manifest.get("packed_parameters", {}).get("sha256") != params_sha or
            target_receipt.get("status") !=
            "PASS_TARGET_N1_NATIVE_PTHREAD_NEON_TRACE18_UNCHANGED" or
            target_receipt.get("final_bundle", {}).get("manifest_sha256") !=
            native_manifest_sha or
            target_receipt.get("final_bundle", {}).get("library_sha256") !=
            library_sha or
            target_receipt.get("final_bundle", {}).get("params_sha256") !=
            params_sha or
            target_receipt.get("result", {}).get("sha256") !=
            _sha256_path(target_result_path) or
            target_result.get("status") !=
            "PASS_TARGET_NEON_SCALAR_EXACT_FP32_GELU_GATE" or
            target_result.get("manifest_sha256") != native_manifest_sha or
            target_result.get("library_sha256") != library_sha or
            target_result.get("source_model_sha256") != source_sha or
            target_result.get("threads") != 3 or
            not isinstance(sensitive_channels, list) or
            (selection_sensitive is not None and
             selection_sensitive != sensitive_channels) or
            not target_result.get("rows") or
            not all(row.get("neon_scalar_i16_byte_exact") is True
                    for row in target_result["rows"])):
        raise ValueError("N1 selection source/native/target proof mismatch")
    if (selection.get("logical_boundary_contract") != {
            "input_profile": 2, "output_profile": 0,
            "input_scale": native_manifest.get("input", {}).get(
                "logical_pl_scale_value_f64"),
            "output_scale": native_manifest.get("output", {}).get(
                "logical_pl_scale_value_f64")}):
        raise ValueError("N1 selection logical PL boundary contract mismatch")
    try:
        from cnn_v10_n1_native_ctypes import CtypesN1NativeClient
    except ImportError:
        from .cnn_v10_n1_native_ctypes import CtypesN1NativeClient
    client = CtypesN1NativeClient(
        native_manifest_path, native_library_path, native_manifest_sha)
    return client, {
        "selection_path": selection_path,
        "selection_sha256": _sha256_path(selection_path),
        "manifest_path": native_manifest_path,
        "manifest_sha256": native_manifest_sha,
        "library_path": native_library_path,
        "library_sha256": library_sha,
        "packed_parameters_sha256": params_sha,
        "target_receipt_sha256": _sha256_path(target_receipt_path),
        "target_result_sha256": _sha256_path(target_result_path),
        "precision": ("W8A16Acc32 with %d sensitive PW output channels FP32" %
                      len(sensitive_channels)),
        "pw_fp32_channels": list(sensitive_channels),
        "input_logical_scale": native_manifest["input"][
            "logical_pl_scale_value_f64"],
        "output_logical_scale": native_manifest["output"][
            "logical_pl_scale_value_f64"],
    }


class Int16HCWActivation(object):
    """Owned INT16 HCW boundary value with explicit scale and logical shape."""

    def __init__(self, payload, profile, scale, logical_shape):
        array = np.asarray(payload)
        if array.dtype != np.dtype("<i2") or array.ndim != 3:
            raise ValueError("payload must be three-dimensional little-endian INT16 HCW")
        if not array.flags.c_contiguous:
            raise ValueError("payload must be contiguous HCW")
        if isinstance(profile, bool) or not isinstance(profile, int) or profile not in (0, 1, 2):
            raise ValueError("profile must be 0, 1, or 2")
        try:
            scale = float(scale)
        except (TypeError, ValueError, OverflowError):
            raise ValueError("scale must be finite and positive")
        if not math.isfinite(scale) or scale <= 0:
            raise ValueError("scale must be finite and positive")
        shape = tuple(logical_shape)
        if len(shape) != 4 or shape[0] != 1 or any(
                isinstance(value, bool) or not isinstance(value, int) or value <= 0
                for value in shape):
            raise ValueError("logical_shape must be a positive batch-one NCHW shape")
        if array.shape != (shape[2], shape[1], shape[3]) or shape[2] != shape[3]:
            raise ValueError("HCW payload shape does not match logical NCHW shape")
        self.payload = array.copy()
        self.profile = profile
        self.scale = scale
        self.logical_shape = shape

    def copy(self):
        return Int16HCWActivation(
            self.payload, self.profile, self.scale, self.logical_shape)


class _NativeBoundaryWorkspace(object):
    """Use exact C quantization while retaining proven NumPy dequantization."""

    def __init__(self, profile, channels, width, native_lib):
        self._native = V10NativeQuantWorkspace(
            profile, channels, width, native_lib=native_lib)
        self._legacy = ActivationBufferWorkspace(profile, channels, width)

    def quantize_chw_to_hcw(self, value, scale, label):
        return self._native.quantize_chw_to_hcw(value, scale, label)

    def dequantize_hcw_to_chw(self, value, scale, label):
        return self._legacy.dequantize_hcw_to_chw(value, scale, label)


class V10MixedBoundaryMixin(object):
    """Mixin consumed before V10LiveRuntime in the runtime MRO."""

    def __init__(self, *args, **kwargs):
        native_lib = kwargs.pop("mixed_native_lib", None)
        active = kwargs.pop("active_quantized_partitions", ())
        if kwargs.get("n1_manifest") is not None or kwargs.get("suffix_candidate") is not None:
            raise ValueError("candidate selection belongs to build_v10_mixed_components")
        super(V10MixedBoundaryMixin, self).__init__(*args, **kwargs)
        self.active_quantized_partitions = tuple(active)
        self.mixed_native_lib = native_lib
        if native_lib is not None:
            replacements = {}
            for profile in (2, 0, 1):
                channels = (128, 256, 64)[profile]
                width = (32, 16, 64)[profile]
                replacements[profile] = (
                    _NativeBoundaryWorkspace(profile, channels, width, native_lib),
                    _NativeBoundaryWorkspace(profile, channels, width, native_lib),
                )
            self.workspaces = replacements

    def _client_timed(self, name, value):
        if isinstance(value, Int16HCWActivation):
            client = self.clients[name]
            method = getattr(client, "infer_int16_hcw", None)
            if not callable(method):
                raise RuntimeError("%s has no validated INT16 HCW backend" % name)
            started = __import__("time").perf_counter()
            # The native ABI consumes the envelope synchronously through a
            # const pointer; the caller-owned input remains alive for the full
            # call, so an additional HCW copy is unnecessary.
            response = method(value)
            call_wall_ms = (__import__("time").perf_counter() - started) * 1000.0
            if (not isinstance(response, tuple) or len(response) != 2 or
                    not isinstance(response[0], Int16HCWActivation)):
                raise ValueError("%s INT16 HCW response is malformed" % name)
            run_ms = float(response[1])
            if not math.isfinite(run_ms) or run_ms < 0:
                raise ValueError("%s INT16 runtime is invalid" % name)
            return response[0], {"partition": name, "ort_run_ms": 0.0,
                                 "native_run_ms": run_ms,
                                 "backend_run_ms": run_ms,
                                 "call_wall_ms": call_wall_ms,
                                 "precision": "W8A16Acc32"}
        return super(V10MixedBoundaryMixin, self)._client_timed(name, value)

    def _run_profile(self, profile, left, right):
        """Preserve HCW INT16 across the profile-2/N1/profile-0 boundary."""
        if "n1" not in self.active_quantized_partitions or profile not in (2, 0):
            return super(V10MixedBoundaryMixin, self)._run_profile(
                profile, left, right)
        import time
        try:
            from cnn_ddr_v10_runtime import profile_contract
        except ImportError:
            from .cnn_ddr_v10_runtime import profile_contract
        total_started = time.perf_counter()
        blocks = (12, 20, 4)[profile]
        cfg = profile_contract(profile, blocks)
        input_scale = self.contract["profiles"][profile]["input_scale"]
        work_left, work_right = self.workspaces[profile]
        started = time.perf_counter()
        if profile == 2:
            if isinstance(left, Int16HCWActivation) or isinstance(
                    right, Int16HCWActivation):
                raise ValueError("profile 2 mixed input must be FP32")
            q_left = work_left.quantize_chw_to_hcw(
                left, input_scale, "profile 2 A")
            q_right = work_right.quantize_chw_to_hcw(
                right, input_scale, "profile 2 B")
            quantize_ms = (time.perf_counter() - started) * 1000.0
            quantize_bypassed = False
        else:
            for lane, value in (("A", left), ("B", right)):
                if (not isinstance(value, Int16HCWActivation) or
                        value.profile != 0 or
                        value.logical_shape != (1, 128, 32, 32) or
                        value.scale != input_scale):
                    raise ValueError(
                        "profile 0 %s requires the exact native N1 HCW boundary" % lane)
            q_left, q_right = left.payload, right.payload
            quantize_ms = 0.0
            quantize_bypassed = True
        arena_left, arena_right = self.arena_handles[profile]
        started = time.perf_counter()
        self._upload_array(arena_left, q_left)
        self._upload_array(arena_right, q_right)
        upload_ms = (time.perf_counter() - started) * 1000.0
        started = time.perf_counter()
        descriptor = self.transport.submit(
            profile, blocks, self.parameter_handles[profile],
            arena_left, arena_right)
        submit_ms = (time.perf_counter() - started) * 1000.0
        started = time.perf_counter()
        completion = self.transport.wait_complete(profile, self.timeout_s)
        wait_ms = (time.perf_counter() - started) * 1000.0
        if profile == 0:
            q_left = np.empty_like(q_left)
            q_right = np.empty_like(q_right)
        started = time.perf_counter()
        self._download_array(arena_left, cfg["output_offset_bytes"], q_left)
        self._download_array(arena_right, cfg["output_offset_bytes"], q_right)
        download_ms = (time.perf_counter() - started) * 1000.0
        output_scale = self.contract["profiles"][profile]["output_scale"]
        started = time.perf_counter()
        if profile == 2:
            out_left = Int16HCWActivation(
                q_left, 2, output_scale, (1, 64, 64, 64))
            out_right = Int16HCWActivation(
                q_right, 2, output_scale, (1, 64, 64, 64))
            dequantize_ms = 0.0
            dequantize_bypassed = True
        else:
            out_left = work_left.dequantize_hcw_to_chw(
                q_left, output_scale, "profile 0 A").copy()
            out_right = work_right.dequantize_hcw_to_chw(
                q_right, output_scale, "profile 0 B").copy()
            dequantize_ms = (time.perf_counter() - started) * 1000.0
            dequantize_bypassed = False
        return out_left, out_right, {
            "profile": profile, "block_count": blocks,
            "descriptor": descriptor, "completion": completion,
            "int16_boundary_bypass": {
                "active": True,
                "quantize_bypassed": quantize_bypassed,
                "dequantize_bypassed": dequantize_bypassed,
                "lane_payload_bytes": int(q_left.nbytes),
                "logical_scale": output_scale if profile == 2 else input_scale,
            },
            "timing": {
                "quantize_ms": quantize_ms, "upload_ms": upload_ms,
                "submit_ms": submit_ms, "wait_ms": wait_ms,
                "download_ms": download_ms, "dequantize_ms": dequantize_ms,
                "pl_window_wall_ms": (time.perf_counter() - total_started) * 1000.0,
            },
        }


def build_v10_mixed_components(model_root, model_manifest,
                               expected_manifest_sha256, runner, threads=3,
                               n1_manifest=None, suffix_candidate=None,
                               native_lib=None):
    """Build shared FP32 clients plus optional exact native conversion hooks.

    ``None`` explicitly disables each research quantized candidate. Supplying
    a candidate makes validation mandatory; a rejected/malformed/unbound
    candidate raises and never becomes an FP32-labelled success.
    """
    n1_client = n1_selection = None
    if n1_manifest is not None:
        n1_client, n1_selection = _load_n1_selection(n1_manifest, model_root)
    suffix_selection = None
    if suffix_candidate is not None:
        suffix_selection = _load_suffix_selection(suffix_candidate, model_root)
    native_identity = None
    native_path = None
    if native_lib is not None:
        native_path = os.path.abspath(os.fspath(native_lib))
        if not os.path.isfile(native_path):
            raise ValueError("native quant library does not exist: %s" % native_path)
        # Loading and symbol binding are part of setup, before any device opens.
        CtypesV10Quantizer(native_path)
        native_identity = _sha256_path(native_path)
    overrides = None
    if suffix_selection is not None:
        overrides = {"suffix": {"path": suffix_selection["candidate_path"],
                                 "sha256": suffix_selection["candidate_sha256"]}}
    clients = None
    try:
        clients, manifest_sha = load_shm_split_clients(
            model_root, runner, model_manifest, expected_manifest_sha256,
            threads=int(threads), model_overrides=overrides)
        if n1_client is not None:
            previous = clients["network1-bridge"]
            clients["network1-bridge"] = n1_client
            close_previous = getattr(previous, "close", None)
            if callable(close_previous):
                close_previous()
    except Exception:
        if clients is not None:
            for client in clients.values():
                close_client = getattr(client, "close", None)
                if callable(close_client):
                    try:
                        close_client()
                    except Exception:
                        pass
        raise
    active = []
    if n1_selection:
        active.append("n1")
    if suffix_selection:
        active.append("suffix")
    evidence = {
        "schema": "cnn-v10.1-mixed-component-selection-v1",
        "active_quantized_partitions": active,
        "partition_selection": {
            "stem-prefix": {"selected_backend": "shared-mmap-ort", "precision": "FP32"},
            "network1-bridge": (
                {"selected_backend": "native-w8a16-acc32",
                 "precision": n1_selection["precision"]}
                if n1_selection else
                {"selected_backend": "shared-mmap-ort", "precision": "FP32"}),
            "network3-bridge": {"selected_backend": "shared-mmap-ort", "precision": "FP32"},
            "suffix": ({"selected_backend": "shared-mmap-ort-qdq",
                         "precision": suffix_selection["precision"]}
                       if suffix_selection else
                       {"selected_backend": "shared-mmap-ort", "precision": "FP32"}),
        },
        "model_manifest_sha256": manifest_sha,
        "n1_candidate": n1_selection,
        "suffix_candidate": suffix_selection,
        "activation_conversion": {
            "selected_backend": "native-c-exact" if native_path else "numpy-exact",
            "precision": "FP64 divide/ties-even to INT16 HCW",
            "library_path": native_path,
            "library_sha256": native_identity,
        },
    }
    mixin_kwargs = {
        "mixed_native_lib": native_path,
        "active_quantized_partitions": tuple(evidence["active_quantized_partitions"]),
    }
    return clients, manifest_sha, mixin_kwargs, evidence


__all__ = ["Int16HCWActivation", "V10MixedBoundaryMixin",
           "build_v10_mixed_components"]
