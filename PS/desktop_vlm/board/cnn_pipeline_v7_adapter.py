"""Fixed-graph v7 adapter reusing the bounded, ordered v6 DAG runtime.

The injected stripe backend owns normal-profile tensor conversion and the
complete 4 + 12 + 20 block chains. This module supplies PS callbacks, ordering,
lease handling, wall/stage reporting, and the same drain semantics as v6. It is
an offline-capable integration layer, not a board-FPS benchmark.
"""

import math
import threading
import time

import numpy as np

try:
    from cnn_pipeline_v6 import CpuThreadBudget, FrameActivationLease, V6ExecutionPlan
    from cnn_pipeline_v6_runtime import CnnPipelineV6Runtime
except ImportError:
    from .cnn_pipeline_v6 import CpuThreadBudget, FrameActivationLease, V6ExecutionPlan
    from .cnn_pipeline_v6_runtime import CnnPipelineV6Runtime


_CLIENT_KEYS = ("stem-prefix", "network1-bridge", "network3-bridge", "suffix")
_STAGE_TO_BUDGET = {
    "stem-prefix": "stem_prefix",
    "network1-bridge": "network1_bridge",
    "network3-bridge": "network3_bridge",
    "suffix": "suffix",
}
_PROFILES = {
    "n0": {"input_shape": (1, 64, 64, 64), "output_shape": (1, 64, 64, 64),
           "blocks": 4, "width": 64},
    "n2": {"input_shape": (1, 128, 32, 32), "output_shape": (1, 128, 32, 32),
           "blocks": 12, "width": 32},
    "n4": {"input_shape": (1, 256, 16, 16), "output_shape": (1, 256, 16, 16),
           "blocks": 20, "width": 16},
}
_PROFILE_ORDER = ("n0", "n2", "n4")
_PS_CALLBACK_ORDER = (
    "capture", "decode", "preprocess", "stem_prefix", "normal_n0_chain",
    "network1_bridge", "normal_n2_chain", "network3_bridge",
    "normal_n4_chain", "suffix", "rank", "output",
)
_SCOPE = ("offline fixed-graph adapter wall time; excludes camera, host transfer, "
          "and production deployment effects; not a board FPS measurement")


def _monotonic_ns():
    return int(time.perf_counter() * 1000000000)


def _finite_fp32(value, shape, label):
    source = np.asarray(value, dtype=np.float32)
    if source.shape != shape or not np.isfinite(source).all():
        raise ValueError("%s must be finite FP32 %s" % (label, shape))
    return np.ascontiguousarray(source, dtype=np.float32)


class V7NormalStripeBackendAdapter(object):
    """Adapt a synchronous three-profile stripe executor to the v6 DAG API.

    The injected object must implement ``current_generation()`` and
    ``execute_normal_stage(profile, activation, frame_id)``. One call executes
    every block and every four-row stripe for that normal profile, then returns
    a mapping with ``activation``, ``block_count``, ``stripe_jobs``, and
    ``stage_events``. Expected jobs are 64 for n0, 96 for n2, and 80 for n4.
    """

    def __init__(self, stripe_backend):
        self.stripe_backend = stripe_backend
        self._execute = getattr(stripe_backend, "execute_normal_stage", None)
        self._generation = getattr(stripe_backend, "current_generation", None)
        if not callable(self._execute) or not callable(self._generation):
            raise ValueError(
                "stripe backend must implement current_generation and execute_normal_stage")
        self._lock = threading.RLock()
        self._active_leases = set()
        self._closed = False
        self._close_receipt = None

    @property
    def active_frame_count(self):
        with self._lock:
            return len(self._active_leases)

    def current_generation(self):
        generation = self._generation()
        if generation is None:
            raise RuntimeError("v7 stripe backend returned no generation token")
        return generation

    def acquire_frame(self, tag):
        with self._lock:
            if self._closed:
                raise RuntimeError("v7 stripe backend adapter is closed")
            generation = self.current_generation()
            token = (tag.sequence_index, id(tag))
            activations = dict((profile, ("v7-activation", token, profile))
                               for profile in _PROFILE_ORDER)
            parameters = dict((profile, ("v7-normal-profile", profile))
                              for profile in _PROFILE_ORDER)
            lease = FrameActivationLease(tag, activations, parameters)
            lease.generation = generation
            lease.stripe_events = []
            self._active_leases.add(lease)
            return lease

    def _check_lease(self, lease, profile):
        if profile not in _PROFILES:
            raise ValueError("unsupported v7 normal profile %r" % profile)
        with self._lock:
            if lease not in self._active_leases:
                raise ValueError("frame lease was not acquired by the v7 adapter")
        if self.current_generation() != lease.generation:
            raise RuntimeError("v7 generation changed during frame execution")

    def prepare(self, profile, lease, value):
        self._check_lease(lease, profile)
        shape = _PROFILES[profile]["input_shape"]
        source = _finite_fp32(value, shape, profile + " input")
        return {"profile": profile, "generation": lease.generation,
                "activation": source}

    def execute(self, profile, lease, prepared):
        self._check_lease(lease, profile)
        if (not isinstance(prepared, dict) or prepared.get("profile") != profile or
                prepared.get("generation") != lease.generation):
            raise ValueError("prepared v7 input does not match lease/profile")
        contract = _PROFILES[profile]
        source = _finite_fp32(prepared.get("activation"),
                              contract["input_shape"], profile + " input")
        started_ns = _monotonic_ns()
        record = self._execute(profile, source, lease.tag.frame_id)
        ended_ns = _monotonic_ns()
        self._check_lease(lease, profile)
        if not isinstance(record, dict):
            raise ValueError("v7 stripe backend must return a result mapping")
        expected_stripes = contract["blocks"] * (contract["width"] // 4)
        if (record.get("block_count") != contract["blocks"] or
                record.get("stripe_jobs") != expected_stripes):
            raise RuntimeError("%s chain did not complete its frozen block/stripe count" % profile)
        output = _finite_fp32(record.get("activation"), contract["output_shape"],
                              profile + " output")
        if "stage_events" not in record:
            raise ValueError("v7 stripe backend must provide stage_events")
        events = record["stage_events"]
        if not isinstance(events, (list, tuple)):
            raise ValueError("v7 stripe stage_events must be a sequence")
        timing = record.get("timing_ms", {})
        if not isinstance(timing, dict):
            raise ValueError("v7 stripe timing_ms must be a mapping")
        for key, value in timing.items():
            if (not isinstance(key, str) or isinstance(value, bool) or
                    not isinstance(value, (int, float)) or
                    not math.isfinite(value) or value < 0):
                raise ValueError("v7 stripe timing values must be finite non-negative milliseconds")
        completion = record.get("completion", {})
        if completion is None:
            completion = {}
        if not isinstance(completion, dict):
            raise ValueError("v7 stripe completion must be a mapping")
        reported_generation = completion.get("reset_generation", lease.generation)
        if reported_generation != lease.generation:
            raise RuntimeError("v7 completion belongs to another generation")
        completion = dict(completion)
        completion.update({"profile": profile, "block_count": contract["blocks"],
                           "stripe_jobs": expected_stripes,
                           "reset_generation": lease.generation})
        elapsed_ms = (ended_ns - started_ns) / 1000000.0
        timings = dict(timing)
        timings.setdefault("stripe_chain_wall", elapsed_ms)
        stripe_event = {
            "profile": profile,
            "block_count": contract["blocks"],
            "stripe_jobs": expected_stripes,
            "wall_ms": elapsed_ms,
            "stage_events": list(events),
        }
        completion["stage_events"] = list(events)
        completion["timing_ms"] = timings
        lease.stripe_events.append(stripe_event)
        return {"profile": profile, "generation": lease.generation,
                "completion": completion, "activation": output,
                "timing_ms": timings, "stripe_event": stripe_event}

    def execute_chained(self, profile, lease, previous):
        raise RuntimeError("v7 fixed-graph adapter executes one normal profile per PS transition")

    def finish(self, profile, lease, executed):
        self._check_lease(lease, profile)
        if (not isinstance(executed, dict) or executed.get("profile") != profile or
                executed.get("generation") != lease.generation):
            raise ValueError("executed v7 result does not match lease/profile")
        return {"activation": executed["activation"],
                "completion": executed["completion"],
                "completions": [executed["completion"]],
                "timing_ms": executed["timing_ms"]}

    def release_frame(self, lease):
        with self._lock:
            if lease not in self._active_leases:
                raise ValueError("frame lease was already released")
            self._active_leases.remove(lease)

    def close(self):
        with self._lock:
            if self._closed:
                return dict(self._close_receipt)
            if self._active_leases:
                raise RuntimeError("cannot close v7 stripe backend with active frame leases")
        close = getattr(self.stripe_backend, "close", None)
        if callable(close):
            receipt = close()
            if receipt is not None and not isinstance(receipt, dict):
                raise ValueError("v7 stripe backend close must return a mapping or None")
        else:
            receipt = None
        if receipt is None:
            result = {
                "quiesce_confirmed": None,
                "all_handles_freed": None,
                "transport_closed": None,
                "cleanup_status": "UNKNOWN",
                "cleanup_evidence": "stripe backend returned no explicit cleanup receipt",
            }
        else:
            result = dict(receipt)
            for key in ("quiesce_confirmed", "all_handles_freed",
                        "transport_closed"):
                if key not in result:
                    result[key] = None
            if all(result[key] is True for key in
                   ("quiesce_confirmed", "all_handles_freed",
                    "transport_closed")):
                result.setdefault("cleanup_status", "CONFIRMED")
            else:
                result.setdefault("cleanup_status", "FAILED_OR_UNKNOWN")
        with self._lock:
            self._closed = True
            self._close_receipt = dict(result)
            return dict(self._close_receipt)


class CnnPipelineV7Adapter(object):
    """Reconnect v7 normal stripes to the v6 bounded fixed-graph PS pipeline.

    ``clients`` contains the existing four split PS clients. Their default
    one-thread budgets sum to four cores. Supplying a CpuThreadBudget permits
    an alternate budget, which is still checked against all four client
    headers by CnnPipelineV6Runtime.
    """

    def __init__(self, stripe_backend, clients, capture=None, decode=None,
                 preprocess=None, rank=None, output=None, cpu_budget=None,
                 logical_cores=4, queue_capacity=4, max_in_flight=4,
                 ps_workers=4, run_timeout_s=300.0, cleanup_timeout_s=5.0):
        self.stripe_backend = stripe_backend
        self.backend = V7NormalStripeBackendAdapter(stripe_backend)
        self.closed = False
        self._close_receipt = None
        try:
            if not isinstance(clients, dict) or set(clients) != set(_CLIENT_KEYS):
                raise ValueError("clients must contain the four existing v6 split PS clients")
            if cpu_budget is None:
                thread_counts = {}
                for name, client in clients.items():
                    header = getattr(client, "header", None)
                    count = header.get("threads") if isinstance(header, dict) else None
                    if (isinstance(count, bool) or not isinstance(count, int) or count < 1):
                        raise ValueError("%s client must report a positive thread count" % name)
                    thread_counts[_STAGE_TO_BUDGET[name]] = count
                cpu_budget = CpuThreadBudget(logical_cores, thread_counts)
            plan = V6ExecutionPlan({"n1": "ps", "n3": "ps"})
            self.runtime = CnnPipelineV6Runtime(
                backend=self.backend, clients=clients, cpu_budget=cpu_budget,
                capture=capture, decode=decode, preprocess=preprocess,
                rank=rank, output=output, execution_plan=plan,
                queue_capacity=queue_capacity, max_in_flight=max_in_flight,
                ps_workers=ps_workers, run_timeout_s=run_timeout_s,
                cleanup_timeout_s=cleanup_timeout_s)
        except Exception:
            try:
                self.backend.close()
            except Exception:
                pass
            for client in reversed(list(clients.values()) if isinstance(clients, dict) else []):
                close = getattr(client, "close", None)
                if callable(close):
                    try:
                        close()
                    except Exception:
                        pass
            raise
        self.pipeline = self.runtime.pipeline

    def run(self, items, expected_frame_ids):
        if self.closed:
            raise RuntimeError("v7 fixed-graph adapter is closed")
        wall_start_ns = _monotonic_ns()
        results = self.runtime.run(items, expected_frame_ids)
        wall_end_ns = _monotonic_ns()
        batch_wall_ms = (wall_end_ns - wall_start_ns) / 1000000.0
        frames = []
        for result in results:
            raw512 = _finite_fp32(result.features, (512,), "raw512 suffix features").copy()
            stages = []
            for completion in result.completions:
                profile = completion.get("profile")
                if profile not in _PROFILE_ORDER:
                    continue
                stages.append({
                    "profile": profile,
                    "block_count": completion.get("block_count"),
                    "stripe_jobs": completion.get("stripe_jobs"),
                    "timing_ms": dict(completion.get("timing_ms", {})),
                    "stage_events": list(completion.get("stage_events", [])),
                })
            frames.append({
                "frame_id": result.frame_id,
                "raw512": raw512,
                "value": result.value,
                "metadata": result.metadata,
                "wall_ms": result.arrival_to_complete_ms,
                "frame_wall_ms": result.arrival_to_complete_ms,
                "batch_wall_ms": batch_wall_ms,
                "components_ms": dict(result.components_ms),
                "stage_events": dict(result.stage_events),
                "normal_stage_events": stages,
                "stage_order": list(_PS_CALLBACK_ORDER),
                "completions": list(result.completions),
                "scope": _SCOPE,
            })
        return {"frames": frames, "frame_count": len(frames),
                "batch_wall_ms": batch_wall_ms, "scope": _SCOPE}

    def recover(self, timeout_s=None):
        return self.runtime.recover(timeout_s)

    def close(self):
        if self.closed:
            return dict(self._close_receipt)
        try:
            receipt = self.runtime.close()
        except Exception:
            if self.runtime.closed:
                backend_receipt = self.backend._close_receipt
                retained = dict(backend_receipt or {
                    "quiesce_confirmed": None,
                    "all_handles_freed": None,
                    "transport_closed": None,
                    "cleanup_status": "UNKNOWN",
                })
                retained["clients_closed"] = all(
                    bool(getattr(client, "closed", False))
                    for client in self.runtime.clients.values())
                self._close_receipt = retained
                self.closed = True
            raise
        if not isinstance(receipt, dict):
            raise RuntimeError("v7 runtime returned no cleanup receipt")
        self._close_receipt = dict(receipt)
        self.closed = True
        return dict(self._close_receipt)


PS_CALLBACK_ORDER = _PS_CALLBACK_ORDER

__all__ = ["CnnPipelineV7Adapter", "V7NormalStripeBackendAdapter",
           "PS_CALLBACK_ORDER"]
