"""Minimal full-model userspace orchestration for the paired V10 normal path.

The runtime is synchronous and deliberately reuses the proven PS partition
clients around three paired PL calls: stem -> N0 -> network1 bridge -> N2 ->
network3 bridge -> N4 -> suffix.  It owns the supplied transport and clients.

An odd final frame is submitted immediately with a mirrored shadow partner in
the second hardware lane; the shadow output is discarded.  This avoids an
unbounded wait for a second image without adding another queueing framework.
"""

import hashlib
import math
import time

import numpy as np

try:
    from activation_buffers import ActivationBufferWorkspace
    from cnn_ddr_v10_runtime import profile_contract
except ImportError:
    from .activation_buffers import ActivationBufferWorkspace
    from .cnn_ddr_v10_runtime import profile_contract


_CLIENT_SPECS = {
    "stem-prefix": ((1, 3, 256, 256), "n0_input", (1, 64, 64, 64)),
    "network1-bridge": ((1, 64, 64, 64), "n2_input", (1, 128, 32, 32)),
    "network3-bridge": ((1, 128, 32, 32), "n4_input", (1, 256, 16, 16)),
    "suffix": ((1, 256, 16, 16), "features", (1, 512)),
}
_STAGES = (
    (2, "n0", "stem-prefix", "network1-bridge"),
    (0, "n2", "network1-bridge", "network3-bridge"),
    (1, "n4", "network3-bridge", "suffix"),
)


def _sha256(value):
    return hashlib.sha256(bytes(value)).hexdigest()


def _valid_sha256(value, label):
    if (not isinstance(value, str) or len(value) != 64 or
            any(character not in "0123456789abcdefABCDEF" for character in value)):
        raise ValueError("%s must be a SHA256" % label)
    return value.lower()


def _positive_scale(value, label):
    if isinstance(value, bool):
        raise ValueError("%s must be finite and positive" % label)
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        raise ValueError("%s must be finite and positive" % label)
    if not math.isfinite(result) or result <= 0:
        raise ValueError("%s must be finite and positive" % label)
    return result


def normalize_v10_normal_contract(contract, expected_manifest_sha256):
    """Validate the three V10 blobs and PS/PL boundary scales."""
    expected = _valid_sha256(expected_manifest_sha256, "expected manifest")
    if not isinstance(contract, dict):
        raise ValueError("V10 parameter contract must be a mapping")
    if _valid_sha256(contract.get("manifest_sha256"), "manifest") != expected:
        raise ValueError("V10 parameter manifest identity mismatch")
    records = contract.get("profiles")
    if not isinstance(records, dict) or len(records) != 3:
        raise ValueError("V10 parameter contract must contain profiles 0, 1, and 2")
    normalized = {}
    for profile in (0, 1, 2):
        record = records.get(profile, records.get(str(profile)))
        if not isinstance(record, dict):
            raise ValueError("V10 parameter contract is missing profile %d" % profile)
        cfg = profile_contract(profile, (12, 20, 4)[profile])
        try:
            payload = bytes(record["params"])
        except (KeyError, TypeError, ValueError):
            raise ValueError("profile %d params must be bytes-like" % profile)
        actual_sha = _sha256(payload)
        if (len(payload) != cfg["params_bytes"] or
                _valid_sha256(record.get("params_sha256"),
                              "profile %d params" % profile) != actual_sha):
            raise ValueError("profile %d V10 parameter extent or SHA mismatch" % profile)
        normalized[profile] = {
            "params": payload,
            "params_sha256": actual_sha,
            "input_scale": _positive_scale(
                record.get("input_scale"), "profile %d input scale" % profile),
            "output_scale": _positive_scale(
                record.get("output_scale"), "profile %d output scale" % profile),
        }
    return {"manifest_sha256": expected, "profiles": normalized}


class V10PairedNormalRuntime(object):
    """Own a transport and four PS clients for synchronous paired inference."""

    def __init__(self, transport, parameter_contract, expected_manifest_sha256,
                 clients, timeout_s=120.0):
        if not isinstance(clients, dict) or set(clients) != set(_CLIENT_SPECS):
            raise ValueError("clients must contain the four normal-path PS partitions")
        if len(set(id(client) for client in clients.values())) != 4:
            raise ValueError("the four PS clients must be independent")
        self.transport = transport
        self.clients = dict(clients)
        self.timeout_s = float(timeout_s)
        if not math.isfinite(self.timeout_s) or self.timeout_s <= 0:
            raise ValueError("timeout_s must be finite and positive")
        self.contract = normalize_v10_normal_contract(
            parameter_contract, expected_manifest_sha256)
        self.parameter_handles = {}
        self.arena_handles = {}
        self.workspaces = {}
        self.closed = False
        self.last_run_summary = None
        try:
            for profile in (2, 0, 1):
                blocks = (12, 20, 4)[profile]
                cfg = profile_contract(profile, blocks)
                parameter = self.contract["profiles"][profile]["params"]
                handle = self.transport.alloc(cfg["params_bytes"], alignment=16)
                self.parameter_handles[profile] = handle
                self.transport.upload(handle, 0, parameter)
                arenas = (
                    self.transport.alloc(cfg["arena_bytes"], alignment=16),
                    self.transport.alloc(cfg["arena_bytes"], alignment=16),
                )
                self.arena_handles[profile] = arenas
                channels = (128, 256, 64)[profile]
                width = (32, 16, 64)[profile]
                self.workspaces[profile] = (
                    ActivationBufferWorkspace(profile, channels, width),
                    ActivationBufferWorkspace(profile, channels, width),
                )
        except Exception:
            self._close_owned_resources()
            raise

    @staticmethod
    def _finite(value, shape, label):
        result = np.asarray(value, dtype=np.float32)
        if result.shape != shape or not np.isfinite(result).all():
            raise ValueError("%s must be finite FP32 %s" % (label, shape))
        return np.ascontiguousarray(result, dtype=np.float32)

    def _client_timed(self, name, value):
        input_shape, output_name, output_shape = _CLIENT_SPECS[name]
        source = self._finite(value, input_shape, name + " input")
        started = time.perf_counter()
        response = self.clients[name].infer([source])
        call_wall_ms = (time.perf_counter() - started) * 1000.0
        if (not isinstance(response, tuple) or len(response) != 2 or
                not isinstance(response[0], dict)):
            raise ValueError("%s response is malformed" % name)
        outputs, run_ms = response
        if (isinstance(run_ms, bool) or not isinstance(run_ms, (int, float)) or
                not math.isfinite(run_ms) or run_ms < 0 or output_name not in outputs):
            raise ValueError("%s output or runtime is invalid" % name)
        return (self._finite(outputs[output_name], output_shape, name + " output"),
                {"partition": name, "ort_run_ms": float(run_ms),
                 "call_wall_ms": call_wall_ms})

    def _client(self, name, value):
        return self._client_timed(name, value)[0]

    def _upload_array(self, handle, value):
        upload_array = getattr(self.transport, "upload_array", None)
        if callable(upload_array):
            upload_array(handle, 0, value)
        else:
            self.transport.upload(handle, 0, value.tobytes(order="C"))

    def _download_array(self, handle, offset, target):
        download_into = getattr(self.transport, "download_into", None)
        if callable(download_into):
            download_into(handle, offset, target)
            return
        payload = self.transport.download(handle, offset, target.nbytes)
        if len(payload) != target.nbytes:
            raise ValueError("V10 activation download extent mismatch")
        np.copyto(target, np.frombuffer(payload, dtype="<i2").reshape(target.shape))

    def _run_profile(self, profile, left, right):
        total_started = time.perf_counter()
        blocks = (12, 20, 4)[profile]
        cfg = profile_contract(profile, blocks)
        scale = self.contract["profiles"][profile]["input_scale"]
        work_left, work_right = self.workspaces[profile]
        started = time.perf_counter()
        q_left = work_left.quantize_chw_to_hcw(left, scale, "profile %d A" % profile)
        q_right = work_right.quantize_chw_to_hcw(right, scale, "profile %d B" % profile)
        quantize_ms = (time.perf_counter() - started) * 1000.0
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
        started = time.perf_counter()
        self._download_array(arena_left, cfg["output_offset_bytes"], q_left)
        self._download_array(arena_right, cfg["output_offset_bytes"], q_right)
        download_ms = (time.perf_counter() - started) * 1000.0
        output_scale = self.contract["profiles"][profile]["output_scale"]
        started = time.perf_counter()
        out_left = work_left.dequantize_hcw_to_chw(
            q_left, output_scale, "profile %d A" % profile).copy()
        out_right = work_right.dequantize_hcw_to_chw(
            q_right, output_scale, "profile %d B" % profile).copy()
        dequantize_ms = (time.perf_counter() - started) * 1000.0
        return out_left, out_right, {
            "profile": profile, "block_count": blocks,
            "descriptor": descriptor, "completion": completion,
            "timing": {
                "quantize_ms": quantize_ms, "upload_ms": upload_ms,
                "submit_ms": submit_ms, "wait_ms": wait_ms,
                "download_ms": download_ms, "dequantize_ms": dequantize_ms,
                "pl_window_wall_ms": (time.perf_counter() - total_started) * 1000.0,
            },
        }

    @staticmethod
    def _parse_item(item):
        if not isinstance(item, (tuple, list)) or len(item) != 2:
            raise ValueError("each V10 input must be (frame_id, value)")
        frame_id, value = item
        if isinstance(frame_id, bool) or not isinstance(frame_id, int) or frame_id < 0:
            raise ValueError("frame_id must be a non-negative integer")
        return frame_id, value

    def _run_pair(self, first, second=None):
        pair_started = time.perf_counter()
        first_id, first_value = self._parse_item(first)
        shadow = second is None
        second_id, second_value = ((None, first_value) if shadow
                                   else self._parse_item(second))
        ps_events = []
        left, event = self._client_timed("stem-prefix", first_value)
        event["lane"] = "A"
        ps_events.append(event)
        right, event = self._client_timed("stem-prefix", second_value)
        event["lane"] = "B"
        ps_events.append(event)
        completions = []
        left, right, evidence = self._run_profile(2, left, right)
        completions.append(evidence)
        left, event = self._client_timed("network1-bridge", left)
        event["lane"] = "A"
        ps_events.append(event)
        right, event = self._client_timed("network1-bridge", right)
        event["lane"] = "B"
        ps_events.append(event)
        left, right, evidence = self._run_profile(0, left, right)
        completions.append(evidence)
        left, event = self._client_timed("network3-bridge", left)
        event["lane"] = "A"
        ps_events.append(event)
        right, event = self._client_timed("network3-bridge", right)
        event["lane"] = "B"
        ps_events.append(event)
        left, right, evidence = self._run_profile(1, left, right)
        completions.append(evidence)
        feature_left, event = self._client_timed("suffix", left)
        event["lane"] = "A"
        ps_events.append(event)
        feature_left = feature_left.reshape(512).copy()
        pair_timing = {
            "schedule": "synchronous_serial_ps_to_pl_no_cross_pair_pipeline",
            "frame_ids": [first_id, second_id],
            "real_frame_count": 1 if shadow else 2,
            "hardware_lane_frame_count": 2,
            "shadow_counts_as_real_throughput": False,
            "ps_events": ps_events,
            "pl_events": completions,
        }
        result_left = {
            "frame_id": first_id, "features": feature_left,
            "shadow_partner_used": shadow, "paired_with": second_id,
            "pl_completions": completions, "pair_timing": pair_timing,
        }
        if shadow:
            pair_timing["pair_wall_ms"] = (time.perf_counter() - pair_started) * 1000.0
            return [result_left]
        feature_right, event = self._client_timed("suffix", right)
        event["lane"] = "B"
        ps_events.append(event)
        feature_right = feature_right.reshape(512).copy()
        pair_timing["pair_wall_ms"] = (time.perf_counter() - pair_started) * 1000.0
        return [result_left, {
            "frame_id": second_id, "features": feature_right,
            "shadow_partner_used": False, "paired_with": first_id,
            "pl_completions": completions, "pair_timing": pair_timing,
        }]

    def run_one(self, frame_id, value):
        """Run one frame immediately using a mirrored, discarded B lane."""
        if self.closed:
            raise RuntimeError("V10 runtime is closed")
        result = self._run_pair((frame_id, value))[0]
        self.last_run_summary = {"pair_count": 1, "real_frame_count": 1,
                                 "pair_timings": [result["pair_timing"]]}
        return result

    def run(self, items):
        """Run a finite batch in input order, mirroring only the odd tail."""
        if self.closed:
            raise RuntimeError("V10 runtime is closed")
        pending = list(items)
        parsed = [self._parse_item(item) for item in pending]
        frame_ids = [item[0] for item in parsed]
        if len(frame_ids) != len(set(frame_ids)):
            raise ValueError("frame IDs must be unique")
        results = []
        pair_timings = []
        for index in range(0, len(parsed), 2):
            second = parsed[index + 1] if index + 1 < len(parsed) else None
            pair_results = self._run_pair(parsed[index], second)
            results.extend(pair_results)
            pair_timings.append(pair_results[0]["pair_timing"])
        self.last_run_summary = {
            "pair_count": len(pair_timings), "real_frame_count": len(results),
            "pair_timings": pair_timings,
            "schedule": "synchronous_serial_ps_to_pl_no_cross_pair_pipeline",
            "shadow_counts_as_real_throughput": False,
        }
        return results

    def _close_owned_resources(self):
        errors = []
        close_transport = getattr(self.transport, "close", None)
        if callable(close_transport):
            try:
                receipt = close_transport()
            except Exception as error:
                receipt = None
                errors.append(error)
        else:
            receipt = None
            errors.append(RuntimeError("V10 transport has no terminal close"))
        for client in reversed(list(self.clients.values())):
            close_client = getattr(client, "close", None)
            if callable(close_client):
                try:
                    close_client()
                except Exception as error:
                    errors.append(error)
        self.closed = True
        if errors:
            raise errors[0]
        return receipt

    def close(self):
        if self.closed:
            return {"transport_closed": True, "clients_closed": True}
        receipt = self._close_owned_resources()
        result = dict(receipt or {})
        result["clients_closed"] = True
        return result


__all__ = [
    "normalize_v10_normal_contract", "V10PairedNormalRuntime",
]
