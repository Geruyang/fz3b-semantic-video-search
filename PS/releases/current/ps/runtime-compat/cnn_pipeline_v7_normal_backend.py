"""Fixed-graph normal-stage backend for the frozen v7 block chains.

This module accepts the existing single-core or replicated-core Linux device
objects.  Device imports and file opens are delayed until an explicit factory
call so host tests can use an injected fake transport.
"""

from __future__ import print_function

import hashlib
import json
import math
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_ACCELERATION_DIR = os.path.join(_REPO_ROOT, "desktop_vlm", "scripts", "acceleration")
if _ACCELERATION_DIR not in sys.path:
    sys.path.insert(0, _ACCELERATION_DIR)

import cnn_shared_v7_contract as contract
import cnn_shared_v7_multicore_plan as multicore_plan
import cnn_shared_v7_scheduler as stripe_scheduler
try:
    from . import cnn_shared_v7_probe as single_probe
except (ImportError, ValueError):
    import cnn_shared_v7_probe as single_probe
try:
    from .activation_buffers import ActivationBufferWorkspace
except (ImportError, ValueError):
    from activation_buffers import ActivationBufferWorkspace


PROFILE_BY_STAGE = {"n0": 2, "n2": 0, "n4": 1}
STATUS_NAMES = single_probe.STATUS_NAMES
WORD_BYTES = 16
CANARY_BYTE = single_probe.CANARY_BYTE
MAX_CORES = 4


def _sha_bytes(payload):
    return hashlib.sha256(payload).hexdigest()


def _sha_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path):
    with open(path, "rb") as stream:
        return json.loads(stream.read().decode("utf-8-sig"))


def quantize_nchw_to_hcw(profile, activation, scale):
    spec = contract.profile_spec(profile)
    workspace = ActivationBufferWorkspace(
        int(profile), spec["channels"], spec["width"])
    result = workspace.quantize_chw_to_hcw(
        activation, scale, "v7 profile %d input" % int(profile))
    return np.array(result, dtype="<i2", order="C", copy=True)


def dequantize_hcw_to_nchw(profile, activation, scale):
    spec = contract.profile_spec(profile)
    workspace = ActivationBufferWorkspace(
        int(profile), spec["channels"], spec["width"])
    source = np.asarray(activation)
    expected = (spec["width"], spec["channels"], spec["width"])
    if source.shape != expected:
        raise ValueError("v7 output must be HCW %s" % (expected,))
    source = np.ascontiguousarray(source, dtype="<i2")
    return np.array(workspace.dequantize_hcw_to_chw(
        source, scale, "v7 profile %d output" % int(profile)),
        dtype=np.float32, order="C", copy=True)


class CnnPipelineV7NormalStageBackend(object):
    """Execute all frozen blocks and four-row stripes for one logical stage.

    The backend reuses one memory allocation per profile and serializes stage
    calls. Within each block it dispatches independent four-row stripes to
    distinct cores; blocks advance only after the scheduler confirms all
    predecessor rows, including halo4 dependencies, have committed.
    """

    def __init__(self, transport, bundle_root, runtime_bundle_root):
        self.transport = transport
        self.bundle_root = os.path.abspath(str(bundle_root))
        self.runtime_bundle_root = os.path.abspath(str(runtime_bundle_root))
        # State/status reads must stay short so the surrounding PS DAG can
        # validate a lease while another frame is executing a long PL chain.
        # Arena mutation and stage execution remain serialized separately:
        # this backend intentionally reuses one arena per profile.
        self._state_lock = threading.RLock()
        self._stage_lock = threading.RLock()
        self._closed = False
        self.board_operation_performed = False
        self._handles = []
        self._parameter_handles = {}
        self._memory_handles = {}
        self._plans = {}
        self._params = {}
        self._identity = None
        self._core_count = None
        self._generation = None
        self._close_receipt = {
            "quiesce_confirmed": False, "all_handles_freed": None,
            "transport_closed": False, "cleanup_status": "NOT_STARTED"}
        self._bundle_manifest = _load_json(
            os.path.join(self.bundle_root, "manifest.json"))
        self._runtime_manifest_path = os.path.join(
            self.runtime_bundle_root, "manifest.json")
        self._runtime_manifest = _load_json(self._runtime_manifest_path)
        self._load_and_validate_contracts()

    @property
    def profile_scales(self):
        return dict((profile, [dict(item) for item in records])
                    for profile, records in self._profile_scales.items())

    def _load_and_validate_contracts(self):
        bundle = self._bundle_manifest
        if bundle.get("status") != "CNN_SHARED_V7_NORMAL_CHAIN_BUNDLE_READY":
            raise ValueError("v7 normal chain bundle is not ready")
        runtime_sha = _sha_file(self._runtime_manifest_path)
        if runtime_sha != bundle.get("source_artifacts", {}).get(
                "runtime_manifest_sha256"):
            raise ValueError("runtime bundle manifest SHA does not match chain bundle")
        scale_record = self._runtime_manifest.get("scale_manifest", {})
        scale_path = os.path.join(self.runtime_bundle_root,
                                  scale_record.get("path", "scale-manifest.json"))
        if _sha_file(scale_path) != scale_record.get("sha256"):
            raise ValueError("frozen scale manifest SHA mismatch")
        self._scale_manifest = _load_json(scale_path)
        self._profile_scales = {}
        self._param_paths = {}
        for profile in (0, 1, 2):
            spec = contract.profile_spec(profile)
            profile_key = str(profile)
            bundle_profile = bundle["profiles"][profile_key]
            runtime_profile = self._runtime_manifest["profiles"][profile_key]
            scale_profile = self._scale_manifest["profiles"][profile_key]
            count = int(runtime_profile["block_count"])
            if (count != spec["blocks"] or
                    int(bundle_profile["block_count"]) != count):
                raise ValueError("profile %d frozen block count mismatch" % profile)
            if int(bundle_profile["stride_words"]) != spec["stride_words"]:
                raise ValueError("profile %d frozen parameter stride mismatch" % profile)
            block_sources = runtime_profile["block_parameter_sources"]
            per_block = scale_profile["per_block"]
            if len(block_sources) != count or len(per_block) != count:
                raise ValueError("profile %d scale/parameter block count mismatch" % profile)
            scales = []
            for index, (block_source, item) in enumerate(zip(block_sources, per_block)):
                if (int(block_source["index"]) != index or
                        int(item["block_index"]) != index or
                        item["parameter_block_sha256"] != block_source["sha256"]):
                    raise ValueError("profile %d block %d scale provenance mismatch" %
                                     (profile, index))
                block_scales = item.get("scales", {})
                normalized = {}
                for name in ("input", "add"):
                    value = float(block_scales[name])
                    if not math.isfinite(value) or value <= 0.0:
                        raise ValueError("profile %d block %d %s scale is invalid" %
                                         (profile, index, name))
                    normalized[name] = value
                if index and scales[index - 1]["add"] != normalized["input"]:
                    raise ValueError("profile %d block %d input scale is not chained" %
                                     (profile, index))
                scales.append(normalized)
            parameter_record = bundle_profile.get("params")
            runtime_parameter = runtime_profile["parameter_file"]
            if (parameter_record is None or
                    parameter_record["sha256"] != runtime_parameter["sha256"] or
                    int(parameter_record["bytes"]) != int(runtime_parameter["bytes"])):
                raise ValueError("profile %d combined params differ from runtime bundle" % profile)
            relative_parameter = str(parameter_record["path"]).replace("\\", "/")
            parameter_name = relative_parameter.rsplit("/", 1)[-1]
            if parameter_name != "params-profile%d.bin" % profile:
                raise ValueError("profile %d parameter bundle filename mismatch" % profile)
            parameter_path = os.path.join(self.bundle_root, parameter_name)
            self._param_paths[profile] = (parameter_path, parameter_record)
            self._profile_scales[profile] = scales

    def _device_identity(self):
        if self._identity is not None:
            return self._identity
        identity = self.transport.identity()
        core_count = int(identity.get("core_count", 1))
        if core_count < 1 or core_count > MAX_CORES:
            raise RuntimeError("v7 runtime core count must be in 1..4")
        expected = {
            "blocks": [12, 20, 4], "channels": [128, 256, 64],
            "widths": [32, 16, 64],
            "block_stride_words": [22433, 61057, 12193],
            "profile_count": 3,
        }
        for name, value in expected.items():
            if identity.get(name) != value:
                raise RuntimeError("v7 runtime %s differs from frozen contract" % name)
        self._identity = dict(identity)
        self._core_count = core_count
        return self._identity

    def _status(self, core_id=0):
        if self._core_count is None:
            self._device_identity()
        try:
            return self.transport.status(core_id)
        except TypeError:
            if self._core_count != 1:
                raise
            return self.transport.status()

    def current_generation(self):
        with self._state_lock:
            if self._closed:
                raise RuntimeError("v7 normal-stage backend is closed")
            self._device_identity()
            generations = tuple(int(self._status(core_id)["reset_generation"])
                                for core_id in range(self._core_count))
            generation = generations[0] if self._core_count == 1 else generations
            if self._generation is None:
                self._generation = generation
            elif generation != self._generation:
                raise RuntimeError("v7 device generation changed during fixed graph")
            return self._generation

    def _read_params(self, profile):
        if profile in self._params:
            return self._params[profile]
        path, item = self._param_paths[profile]
        with open(path, "rb") as stream:
            params = stream.read()
        if len(params) != int(item["bytes"]) or _sha_bytes(params) != item["sha256"]:
            raise ValueError("profile %d combined parameter file integrity mismatch" %
                             profile)
        expected_bytes = (contract.profile_spec(profile)["blocks"] *
                          contract.profile_spec(profile)["stride_words"] * WORD_BYTES)
        if len(params) != expected_bytes:
            raise ValueError("profile %d combined parameter extent mismatch" % profile)
        self._params[profile] = params
        return params

    def _alloc_profile(self, profile, frame_tag):
        if profile in self._parameter_handles:
            return
        self._device_identity()
        params = self._read_params(profile)
        plan = multicore_plan.build_plan(
            profile, self._core_count,
            "v7-profile%d-frame-%d" % (profile, frame_tag))
        params_alloc = self.transport.alloc(len(params))
        self._handles.append(params_alloc["handle"])
        self.transport.upload(params_alloc["handle"], 0, params)
        memory_alloc = self.transport.alloc(plan["memory_bytes"])
        self._handles.append(memory_alloc["handle"])
        self._parameter_handles[profile] = params_alloc["handle"]
        self._memory_handles[profile] = memory_alloc["handle"]
        self._plans[profile] = plan

    @staticmethod
    def _frame_tag(frame_id):
        if isinstance(frame_id, bool):
            raise ValueError("frame_id must be an unsigned 64-bit integer")
        if isinstance(frame_id, int):
            value = frame_id
        elif isinstance(frame_id, str) and frame_id.isdigit():
            value = int(frame_id)
        else:
            raise ValueError("frame_id must be an unsigned 64-bit integer")
        if value < 0 or value > 0xFFFFFFFFFFFFFFFF:
            raise ValueError("frame_id is outside uint64 range")
        return value

    def execute_normal_stage(self, profile, activation, frame_id):
        if profile not in PROFILE_BY_STAGE:
            raise ValueError("unsupported v7 normal stage %r" % profile)
        profile_id = PROFILE_BY_STAGE[profile]
        spec = contract.profile_spec(profile_id)
        with self._stage_lock:
            with self._state_lock:
                if self._closed:
                    raise RuntimeError("v7 normal-stage backend is closed")
            generation = self.current_generation()
            self._device_identity()
            frame_tag = self._frame_tag(frame_id)
            total_started = time.perf_counter()
            workspace = ActivationBufferWorkspace(
                profile_id, spec["channels"], spec["width"])
            quant_started = time.perf_counter()
            quantized = workspace.quantize_chw_to_hcw(
                activation, self._profile_scales[profile_id][0]["input"],
                "%s input" % profile)
            quantized_payload = quantized.tobytes(order="C")
            quant_ms = (time.perf_counter() - quant_started) * 1000.0
            self._alloc_profile(profile_id, frame_tag)
            plan = self._plans[profile_id]
            memory_handle = self._memory_handles[profile_id]
            parameter_handle = self._parameter_handles[profile_id]
            memory_init_started = time.perf_counter()
            memory_bytes = plan["memory_bytes"]
            canary = bytes(bytearray([CANARY_BYTE])) * memory_bytes
            self.transport.upload(memory_handle, 0, canary)
            input_offset = int(plan["tensor_regions"][0]["offset_words"]) * WORD_BYTES
            self.transport.upload(memory_handle, input_offset, quantized_payload)
            memory_upload_ms = (time.perf_counter() - memory_init_started) * 1000.0

            events = []
            total_cycles = 0
            last_status = None
            submit_started = time.perf_counter()
            scheduler = stripe_scheduler.StripeScheduler()
            for block_index in range(int(plan["block_count"])):
                block_started = time.perf_counter()
                first_stripe_event = len(events)
                def execute_stripe(item):
                    token, descriptor, core_id, start_row = item
                    before = self._status(core_id)
                    job_started = time.perf_counter()
                    self.transport.submit(descriptor, parameter_handle, memory_handle)
                    if self.transport.__class__.__module__.endswith(
                            ("cnn_shared_v7_probe", "cnn_shared_v7_multicore_linux")):
                        self.board_operation_performed = True
                    after = self._status(core_id)
                    job_ended = time.perf_counter()
                    counter_delta = single_probe._status_delta(before, after)
                    job_cycles = ((int(after["job_cycles_hi"]) << 32) |
                                  int(after["job_cycles_lo"]))
                    if job_cycles <= 0:
                        raise RuntimeError("v7 completed job cycles must be positive")
                    expected_generation = (generation[core_id]
                                           if isinstance(generation, tuple)
                                           else generation)
                    if int(after["reset_generation"]) != expected_generation:
                        raise RuntimeError("v7 job completed in another reset generation")
                    return {"token": token, "event": {
                        "event": "stripe_completed", "profile": profile,
                        "profile_id": profile_id, "frame_id": str(frame_id),
                        "frame_tag": frame_tag, "block_index": block_index,
                        "core_id": core_id, "start_row": start_row, "row_count": 4,
                        "wall_ms": (job_ended - job_started) * 1000.0,
                        "job_cycles": job_cycles, "counter_delta": counter_delta,
                        "last_status": after}}

                stripe_rows = list(range(0, spec["width"], 4))
                for batch_start in range(0, len(stripe_rows), self._core_count):
                    stripes = []
                    for core_id in range(min(self._core_count,
                                             len(stripe_rows) - batch_start)):
                        start_row = stripe_rows[batch_start + core_id]
                        descriptor = multicore_plan.stripe_descriptor(
                            plan, block_index, core_id, start_row, 4)
                        descriptor = contract.validate_descriptor(descriptor)
                        descriptor.update({"core_id": core_id, "frame_tag": frame_tag,
                                           "block_index": block_index})
                        scheduler_job = multicore_plan.scheduler_job(
                            plan, block_index, core_id, start_row, 4)
                        token = scheduler.dispatch(scheduler_job)
                        stripes.append((token, descriptor, core_id, start_row))
                    # The driver leases the whole arena object while any core
                    # is active. Prepare every private scratch region before
                    # submitting this wave; no transfer may race another core.
                    for unused_token, descriptor, core_id, unused_row in stripes:
                        scratch_capacity_bytes = (
                            int(plan["scratch_regions"][core_id]["extent_words"]) *
                            WORD_BYTES)
                        scratch_offset = int(descriptor["scratch_words"]) * WORD_BYTES
                        self.transport.upload(
                            memory_handle, scratch_offset,
                            bytes(bytearray([CANARY_BYTE])) * scratch_capacity_bytes)
                    completed = []
                    executor = ThreadPoolExecutor(max_workers=len(stripes))
                    futures = [executor.submit(execute_stripe, item)
                               for item in stripes]
                    failure = None
                    for future in futures:
                        try:
                            completed.append(future.result())
                        except Exception as error:
                            if failure is None:
                                failure = error
                    executor.shutdown(wait=True)
                    for item in stripes:
                        success = any(value["token"] == item[0]
                                      for value in completed)
                        scheduler.complete(item[0], success)
                    if failure is not None:
                        raise failure
                    for item in completed:
                        total_cycles += item["event"]["job_cycles"]
                        last_status = item["event"].pop("last_status")
                        events.append(item["event"])
                events.append({
                    "event": "block_completed", "profile": profile,
                    "profile_id": profile_id, "frame_id": str(frame_id),
                    "block_index": block_index,
                    "stripe_jobs": len(events) - first_stripe_event,
                    "wall_ms": (time.perf_counter() - block_started) * 1000.0,
                })
            submit_ms = (time.perf_counter() - submit_started) * 1000.0
            output_region = plan["tensor_regions"][int(plan["block_count"])]
            output_offset = int(output_region["offset_words"]) * WORD_BYTES
            tensor_bytes = spec["channels"] * spec["width"] * spec["width"] * 2
            download_started = time.perf_counter()
            output_payload = self.transport.download(
                memory_handle, output_offset, tensor_bytes)
            download_ms = (time.perf_counter() - download_started) * 1000.0
            if len(output_payload) != tensor_bytes:
                raise RuntimeError("v7 final normal activation extent mismatch")
            hcw = np.frombuffer(output_payload, dtype="<i2").reshape(
                (spec["width"], spec["channels"], spec["width"]))
            dequant_started = time.perf_counter()
            result_activation = workspace.dequantize_hcw_to_chw(
                hcw, self._profile_scales[profile_id][-1]["add"],
                "%s output" % profile)
            result_activation = np.ascontiguousarray(result_activation.copy(),
                                                     dtype=np.float32)
            dequant_ms = (time.perf_counter() - dequant_started) * 1000.0
            if not np.isfinite(result_activation).all():
                raise RuntimeError("v7 final normal activation contains NaN/Inf")
            if self.current_generation() != generation:
                raise RuntimeError("v7 generation changed during normal stage")
            total_ms = (time.perf_counter() - total_started) * 1000.0
            timing_ms = {
                "quantize_layout": quant_ms,
                "memory_initialize_upload": memory_upload_ms,
                "stripe_submit_to_completion": submit_ms,
                "activation_download": download_ms,
                "dequantize_layout": dequant_ms,
                "normal_stage_total": total_ms,
            }
            events.append({"event": "normal_stage_completed", "profile": profile,
                           "profile_id": profile_id, "frame_id": str(frame_id),
                           "block_count": int(plan["block_count"]),
                           "stripe_jobs": len(range(0, spec["width"], 4)) *
                           int(plan["block_count"])})
            return {
                "activation": result_activation,
                "block_count": int(plan["block_count"]),
                "stripe_jobs": int(plan["block_count"]) * (spec["width"] // 4),
                "stage_events": events,
                "completion": {
                    "profile": profile, "profile_id": profile_id,
                    "frame_id": str(frame_id), "frame_tag": frame_tag,
                    "block_count": int(plan["block_count"]),
                    "stripe_jobs": int(plan["block_count"]) * (spec["width"] // 4),
                    "reset_generation": generation,
                    "core_count": self._core_count,
                    "executed_core_ids": sorted(set(
                        item["core_id"] for item in events
                        if item.get("event") == "stripe_completed")),
                    "job_cycles_sum": total_cycles,
                    "last_status": last_status,
                    "output_sha256": _sha_bytes(output_payload),
                },
                "timing_ms": timing_ms,
            }

    def close(self):
        # Wait for the one arena-mutating stage to drain, then prevent new
        # executions before terminal QUIESCE/free. Do not make ordinary
        # current_generation() checks wait behind that stage lock.
        with self._stage_lock:
            with self._state_lock:
                if self._closed:
                    return dict(self._close_receipt)
            errors = []
            free_failures = []
            quiesced = False
            try:
                self.transport.quiesce()
                quiesced = True
            except Exception as error:
                errors.append(error)
            all_freed = False
            if quiesced:
                all_freed = True
                for handle in reversed(self._handles):
                    try:
                        self.transport.free(handle)
                    except Exception as error:
                        all_freed = False
                        free_failures.append({"handle": handle,
                                              "error": "%s: %s" %
                                              (type(error).__name__, error)})
                        errors.append(error)
                if all_freed:
                    self._handles = []
            transport_closed = False
            close = getattr(self.transport, "close", None)
            if callable(close) and (quiesced and all_freed):
                try:
                    close()
                    transport_closed = True
                except Exception as error:
                    errors.append(error)
            if not quiesced:
                all_freed = None
                cleanup_status = "UNKNOWN"
            elif errors:
                cleanup_status = "FAILED"
            else:
                cleanup_status = "PASS"
            self._close_receipt = {
                "quiesce_confirmed": quiesced,
                "all_handles_freed": all_freed,
                "transport_closed": transport_closed,
                "cleanup_status": cleanup_status,
                "free_failures": free_failures,
                "cleanup_errors": ["%s: %s" % (type(error).__name__, error)
                                   for error in errors],
            }
            with self._state_lock:
                self._closed = True
            if not quiesced:
                raise RuntimeError("v7 terminal cleanup outcome is unknown: %s" % errors[0])
            if errors:
                raise RuntimeError("v7 terminal cleanup failed: %s" % errors[0])
            return dict(self._close_receipt)


def create_linux_transport(device_path, multicore=False):
    """Explicitly open an existing Linux transport; never called on import."""
    if multicore:
        try:
            from . import cnn_shared_v7_multicore_linux as linux_transport
        except (ImportError, ValueError):
            import cnn_shared_v7_multicore_linux as linux_transport
        return linux_transport.MulticoreLinuxDevice(device_path)
    return single_probe.V7Device(device_path)


__all__ = ["CnnPipelineV7NormalStageBackend", "create_linux_transport",
           "quantize_nchw_to_hcw", "dequantize_hcw_to_nchw"]
