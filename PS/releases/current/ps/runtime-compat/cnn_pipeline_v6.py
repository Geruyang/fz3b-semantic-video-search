"""Bounded cross-frame DAG scheduler for the FZ3B CNN v6 runtime.

The scheduler owns no board-specific allocation or tensor conversion policy.
Those operations live behind the backend lease protocol so the same DAG can
exercise a deterministic fake transport, the v5 compatibility backend, and a
future v6 driver without changing its failure or ordering semantics.

This module intentionally uses Python 3.6 syntax only.
"""

import copy
import queue
import threading
import time


_UINT32_MAX = (1 << 32) - 1
_POLL_SECONDS = 0.02
_PS_ORT_STAGES = ("stem_prefix", "network1_bridge",
                  "network3_bridge", "suffix")
_ORT_STAGE_KEYS = ("stem_prefix", "network1_bridge", "network3_bridge",
                   "network3_se_gelu", "suffix")


def _identity(value):
    return value


class CpuThreadBudget(object):
    """Explicit ORT budget, optionally for serialized active stages only.

    Legacy construction keeps all four original ORT clients active and sums
    their threads. With ``active_stage_keys``, only those named clients count;
    ``exclusive_ort`` budgets their maximum because the pipeline guarantees
    one admitted frame and one PS worker.
    """

    def __init__(self, logical_cores, ort_intra_op_threads,
                 active_stage_keys=None, exclusive_ort=False):
        if (isinstance(logical_cores, bool) or
                not isinstance(logical_cores, int) or logical_cores < 1):
            raise ValueError("logical_cores must be a positive integer")
        if not isinstance(exclusive_ort, bool):
            raise ValueError("exclusive_ort must be a boolean")
        supplied = dict(ort_intra_op_threads)
        if not supplied or not set(supplied).issubset(_ORT_STAGE_KEYS):
            raise ValueError("ORT thread budget contains unknown or no stage keys")
        if active_stage_keys is None:
            if set(supplied) != set(_PS_ORT_STAGES):
                raise ValueError("legacy ORT budget must name all four PS model stages")
            active = _PS_ORT_STAGES
        else:
            if isinstance(active_stage_keys, str):
                raise ValueError("active_stage_keys must be a collection of stage keys")
            active_supplied = tuple(active_stage_keys)
            if (not active_supplied or len(active_supplied) != len(set(active_supplied)) or
                    not set(active_supplied).issubset(_ORT_STAGE_KEYS)):
                raise ValueError("active_stage_keys must uniquely name known ORT stages")
            if not set(active_supplied).issubset(supplied):
                raise ValueError("active ORT stages must have configured thread counts")
            active = tuple(name for name in _ORT_STAGE_KEYS
                           if name in set(active_supplied))
        for name, count in supplied.items():
            if isinstance(count, bool) or not isinstance(count, int) or count < 1:
                raise ValueError("ORT thread budget values must be positive integers")
        active_total = sum(supplied[name] for name in active)
        active_peak = max(supplied[name] for name in active)
        budgeted = active_peak if exclusive_ort else active_total
        if budgeted > logical_cores:
            raise ValueError("ORT thread budget exceeds logical CPU cores")
        self.logical_cores = logical_cores
        self.ort_intra_op_threads = supplied
        self.active_stage_keys = active
        self.exclusive_ort = exclusive_ort
        self.total_ort_threads = active_total
        self.active_ort_threads = active_total
        self.peak_active_ort_threads = active_peak
        self.budgeted_ort_threads = budgeted


class FrameTag(object):
    """Identity that prevents a stale completion entering a later generation."""

    __slots__ = ("generation", "frame_id", "sequence_index")

    def __init__(self, generation, frame_id, sequence_index):
        self.generation = generation
        self.frame_id = frame_id
        self.sequence_index = sequence_index

    def __repr__(self):
        return "FrameTag(generation=%r, frame_id=%r, sequence_index=%r)" % (
            self.generation, self.frame_id, self.sequence_index)


class FrameActivationLease(object):
    """Per-frame activation handles plus immutable shared parameter handles."""

    def __init__(self, tag, activation_handles, parameter_handles):
        self.tag = tag
        self.activation_handles = dict(activation_handles)
        self.parameter_handles = dict(parameter_handles)


class V6ExecutionPlan(object):
    """Route N1/N3 through PS fallbacks or future PL transition profiles."""

    def __init__(self, transition_routes=None):
        routes = {"n1": "ps", "n3": "ps"}
        if transition_routes is not None:
            routes.update(dict(transition_routes))
        if set(routes) != {"n1", "n3"}:
            raise ValueError("transition routes may only name n1 and n3")
        if routes["n1"] not in ("ps", "pl_split", "pl_fused"):
            raise ValueError("n1 transition route must be ps, pl_split, or pl_fused")
        if routes["n3"] not in ("ps", "hybrid_split", "hybrid_fused"):
            raise ValueError("n3 transition route must be ps, hybrid_split, or hybrid_fused")
        fused = (routes["n1"] == "pl_fused" or
                 routes["n3"] == "hybrid_fused")
        if fused and routes != {"n1": "pl_fused", "n3": "hybrid_fused"}:
            raise ValueError("full fusion requires pl_fused plus hybrid_fused")
        self.transition_routes = routes
        self.full_fusion = fused
        profiles = ["n0"]
        if routes["n1"] in ("pl_split", "pl_fused"):
            profiles.extend(("n1_dw", "n1_pw"))
        profiles.append("n2")
        if routes["n3"] in ("hybrid_split", "hybrid_fused"):
            profiles.extend(("n3_dw", "n3_pw"))
        profiles.append("n4")
        self.pl_profiles = tuple(profiles)
        if fused:
            self.activation_alias_groups = (frozenset(self.pl_profiles),)
        else:
            self.activation_alias_groups = (
                frozenset(("n1_dw", "n1_pw")),
                frozenset(("n3_dw", "n3_pw")),
            )


class V6StageCallbacks(object):
    """PS callbacks, including adapters around the four split-model stages."""

    def __init__(self, stem_prefix, network1_bridge, network3_bridge, suffix,
                 capture=None, decode=None, preprocess=None, rank=None,
                 output=None, network3_se_gelu=None):
        def missing_se(unused_value):
            raise RuntimeError("network3_se_gelu callback is required by hybrid plan")

        callbacks = {
            "capture": capture or _identity,
            "decode": decode or _identity,
            "preprocess": preprocess or _identity,
            "stem_prefix": stem_prefix,
            "network1_bridge": network1_bridge,
            "network3_bridge": network3_bridge,
            "network3_se_gelu": network3_se_gelu or missing_se,
            "suffix": suffix,
            "rank": rank or _identity,
            "output": output or _identity,
        }
        for name, callback in callbacks.items():
            if not callable(callback):
                raise ValueError("%s callback must be callable" % name)
        self.callbacks = callbacks
        self._request_locks = {
            name: threading.Lock() for name in _PS_ORT_STAGES}

    def get(self, name):
        return self.callbacks[name]

    def call(self, name, value):
        """Keep one outstanding request per persistent ORT subprocess."""
        lock_name = "network3_bridge" if name == "network3_se_gelu" else name
        lock = self._request_locks.get(lock_name)
        if lock is None:
            return self.callbacks[name](value)
        with lock:
            return self.callbacks[name](value)


class PipelineStageError(RuntimeError):
    """First DAG failure, with its exact frame/generation and cleanup errors."""

    def __init__(self, stage, tag, cause):
        self.stage = stage
        self.tag = tag
        self.frame_id = None if tag is None else tag.frame_id
        self.cause = cause
        self.cleanup_errors = []
        RuntimeError.__init__(
            self, "%s %r failed: %s" % (stage, tag, cause))


class PipelineRunTimeout(RuntimeError):
    pass


class PipelineShutdownTimeout(RuntimeError):
    def __init__(self, thread_names):
        self.thread_names = tuple(thread_names)
        RuntimeError.__init__(
            self, "v6 DAG workers did not stop: %s" %
            ", ".join(self.thread_names))


class V6FrameResult(object):
    """Ordered result that retains raw features and downstream output."""

    def __init__(self, tag, value, features, metadata, components_ms,
                 completions, arrival_ms, admitted_ms, compute_ready_ms,
                 output_start_ms, output_done_ms, stage_events):
        self.tag = tag
        self.frame_id = tag.frame_id
        self.value = value
        self.features = features
        self.metadata = metadata
        self.components_ms = dict(components_ms)
        self.completions = list(completions)
        self.arrival_ms = arrival_ms
        self.admitted_ms = admitted_ms
        self.admission_wait_ms = admitted_ms - arrival_ms
        self.compute_ready_ms = compute_ready_ms
        self.output_start_ms = output_start_ms
        self.output_done_ms = output_done_ms
        self.ready_to_emit_wait_ms = output_start_ms - compute_ready_ms
        self.complete_ms = output_done_ms
        self.end_to_end_ms = output_done_ms - admitted_ms
        self.admitted_to_ready_ms = compute_ready_ms - admitted_ms
        self.arrival_to_complete_ms = output_done_ms - arrival_ms
        self.stage_events = dict(stage_events)


class _FrameContext(object):
    def __init__(self, tag, value, metadata, lease, arrival_ns):
        self.tag = tag
        self.value = value
        self.metadata = metadata
        self.lease = lease
        self.arrival_ns = arrival_ns
        self.admitted_ns = None
        self.timings = {}
        self.prepared = {}
        self.executed = {}
        self.completions = []
        self.features = None
        self.released = False
        self.stage_events = {}


class V6DagPipeline(object):
    """Execute a bounded per-frame DAG with one exclusive PL queue owner.

    Backend protocol::

      current_generation() -> generation token
      acquire_frame(FrameTag) -> FrameActivationLease
      prepare(profile, lease, value) -> opaque prepared value
      execute(profile, lease, prepared) -> opaque executed value
      finish(profile, lease, executed) -> {activation, completion, timing_ms}
      release_frame(lease)

    ``prepare`` and ``finish`` run on the bounded PS pool, which permits
    quantization, packing, upload, download, and dequantization for one frame
    to overlap the PL transaction of another. Only ``execute`` reaches the PL
    owner thread.
    """

    def __init__(self, backend, callbacks, execution_plan=None,
                 queue_capacity=4, max_in_flight=4, ps_workers=4,
                 cpu_budget=None, run_timeout_s=300.0,
                 cleanup_timeout_s=5.0, thread_name="cnn-pipeline-v6"):
        for name, value in (("queue_capacity", queue_capacity),
                            ("max_in_flight", max_in_flight),
                            ("ps_workers", ps_workers)):
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError("%s must be a positive integer" % name)
        if queue_capacity < max_in_flight:
            raise ValueError("queue_capacity must cover max_in_flight")
        if run_timeout_s <= 0 or cleanup_timeout_s <= 0:
            raise ValueError("pipeline timeouts must be positive")
        if not isinstance(callbacks, V6StageCallbacks):
            raise ValueError("callbacks must be V6StageCallbacks")
        self.cpu_budget = cpu_budget or CpuThreadBudget(
            4, {name: 1 for name in _PS_ORT_STAGES})
        if not isinstance(self.cpu_budget, CpuThreadBudget):
            raise ValueError("cpu_budget must be CpuThreadBudget")
        if (self.cpu_budget.exclusive_ort and
                (max_in_flight != 1 or ps_workers != 1)):
            raise ValueError(
                "exclusive_ort requires max_in_flight=1 and ps_workers=1")
        if ps_workers > self.cpu_budget.logical_cores:
            raise ValueError("ps_workers exceeds logical CPU budget")
        self.backend = backend
        self.callbacks = callbacks
        self.execution_plan = execution_plan or V6ExecutionPlan()
        self.queue_capacity = queue_capacity
        self.max_in_flight = max_in_flight
        self.ps_workers = ps_workers
        self.run_timeout_s = float(run_timeout_s)
        self.cleanup_timeout_s = float(cleanup_timeout_s)
        self.thread_name = thread_name
        self._run_lock = threading.Lock()
        self._threads = ()
        self._active_activation_handles = set()
        self._parameter_identity = None
        self._orphaned_contexts = []
        self.last_batch_start = None
        self.last_batch_end = None
        self.stats = self._new_stats()

    def _new_stats(self):
        return {
            "queue_capacity": self.queue_capacity,
            "max_in_flight": self.max_in_flight,
            "in_flight_peak": 0,
            "ps_workers": self.ps_workers,
            "logical_cpu_budget": self.cpu_budget.logical_cores,
            "ort_intra_op_threads": dict(self.cpu_budget.ort_intra_op_threads),
            "active_ort_stage_keys": self.cpu_budget.active_stage_keys,
            "exclusive_ort": self.cpu_budget.exclusive_ort,
            "budgeted_ort_threads": self.cpu_budget.budgeted_ort_threads,
        }

    @property
    def threads_alive(self):
        return tuple(thread.name for thread in self._threads if thread.is_alive())

    @property
    def requires_recovery(self):
        return bool(self._orphaned_contexts)

    @staticmethod
    def _expected_ids(expected_frame_ids):
        expected = list(expected_frame_ids)
        for frame_id in expected:
            if (isinstance(frame_id, bool) or not isinstance(frame_id, int) or
                    frame_id < 0 or frame_id > _UINT32_MAX):
                raise ValueError("frame IDs must be uint32 integers")
        if len(expected) != len(set(expected)):
            raise ValueError("duplicate expected frame ID")
        return expected

    @staticmethod
    def _parse_item(item):
        if not isinstance(item, (tuple, list)) or len(item) not in (2, 3):
            raise ValueError("items must be (frame_id, value[, metadata])")
        metadata = {} if len(item) == 2 else item[2]
        if not isinstance(metadata, dict):
            raise ValueError("frame metadata must be a dictionary")
        return item[0], copy.deepcopy(item[1]), copy.deepcopy(metadata)

    def _register_lease(self, lease, tag):
        if not isinstance(lease, FrameActivationLease) or lease.tag is not tag:
            raise ValueError("backend returned an invalid frame activation lease")
        missing = set(self.execution_plan.pl_profiles) - set(lease.activation_handles)
        if missing:
            raise ValueError("frame lease lacks activation handles: %s" %
                             ", ".join(sorted(missing)))
        missing_params = set(self.execution_plan.pl_profiles) - set(lease.parameter_handles)
        if missing_params:
            raise ValueError("frame lease lacks parameter handles: %s" %
                             ", ".join(sorted(missing_params)))
        activation_values = tuple(lease.activation_handles.values())
        profiles_by_handle = {}
        for profile, handle in lease.activation_handles.items():
            profiles_by_handle.setdefault(handle, set()).add(profile)
        for profiles in profiles_by_handle.values():
            if (len(profiles) > 1 and
                    not any(profiles.issubset(group)
                            for group in self.execution_plan.activation_alias_groups)):
                raise ValueError("one frame reused an undeclared activation handle alias")
        if self._active_activation_handles.intersection(activation_values):
            raise ValueError("active frames reused an activation handle")
        parameter_identity = tuple(sorted(lease.parameter_handles.items()))
        if self._parameter_identity is None:
            self._parameter_identity = parameter_identity
        elif parameter_identity != self._parameter_identity:
            raise ValueError("parameter handles must be immutable and shared")
        self._active_activation_handles.update(activation_values)

    def _release_context(self, context):
        if context.released:
            return
        self.backend.release_frame(context.lease)
        self._active_activation_handles.difference_update(
            context.lease.activation_handles.values())
        context.released = True

    def _next_after_profile(self, profile):
        if profile == "n0":
            if self.execution_plan.transition_routes["n1"] == "pl_split":
                return "prepare_n1_dw"
            return "network1_bridge"
        if profile == "n1_pw":
            return "prepare_n2"
        if profile == "n2":
            if self.execution_plan.transition_routes["n3"] == "hybrid_split":
                return "prepare_n3_dw"
            return "network3_bridge"
        if profile == "n3_dw":
            return "network3_se_gelu"
        if profile == "n3_pw":
            return "prepare_n4"
        if profile == "n4":
            return "suffix"
        raise ValueError("unknown PL profile %s" % profile)

    @staticmethod
    def _put_bounded(target, item, stop):
        while not stop.is_set():
            try:
                target.put(item, timeout=_POLL_SECONDS)
                return True
            except queue.Full:
                pass
        return False

    def _queue_stage(self, target, stage, context, stop):
        context.stage_events[stage] = {"queued_ns": time.perf_counter()}
        return self._put_bounded(target, (stage, context), stop)

    def _run_ps_stage(self, stage, context):
        started = time.perf_counter()
        if stage.startswith("prepare_"):
            profile = stage[len("prepare_"):]
            context.prepared[profile] = self.backend.prepare(
                profile, context.lease, context.value)
            next_stage = "pl_" + profile
        elif stage.startswith("finish_"):
            profile = stage[len("finish_"):]
            finished = self.backend.finish(
                profile, context.lease, context.executed.pop(profile))
            if (not isinstance(finished, dict) or "activation" not in finished or
                    "completion" not in finished):
                raise ValueError("backend finish result is incomplete")
            completions = finished.get("completions")
            if completions is None:
                completions = [finished["completion"]]
            if (not isinstance(completions, list) or not completions or
                    any(not isinstance(completion, dict) or
                        completion.get("reset_generation") != context.tag.generation
                        for completion in completions)):
                raise RuntimeError("completion generation changed")
            context.value = finished["activation"]
            context.completions.extend(completions)
            for name, elapsed in finished.get("timing_ms", {}).items():
                context.timings["%s_%s" % (profile, name)] = float(elapsed)
            next_stage = self._next_after_profile(profile)
        else:
            context.value = self.callbacks.call(stage, context.value)
            if stage == "suffix":
                context.features = context.value
            sequence = {
                "capture": "decode",
                "decode": "preprocess",
                "preprocess": "stem_prefix",
                "stem_prefix": "prepare_n0",
                "network1_bridge": "prepare_n2",
                "network3_bridge": "prepare_n4",
                "network3_se_gelu": "prepare_n3_pw",
                "suffix": "rank",
                "rank": None,
            }
            next_stage = sequence[stage]
        context.timings[stage] = (time.perf_counter() - started) * 1000.0
        return next_stage

    def _run_pl_stage(self, stage, context):
        chained = stage.startswith("plchain_")
        profile = stage[len("plchain_"):] if chained else stage[len("pl_"):]
        if self.backend.current_generation() != context.tag.generation:
            raise RuntimeError("driver generation changed before PL submit")
        started = time.perf_counter()
        if chained:
            execute_chained = getattr(self.backend, "execute_chained", None)
            if not callable(execute_chained):
                raise RuntimeError("backend lacks execute_chained")
            previous_by_profile = {
                "n1_dw": "n0", "n1_pw": "n1_dw", "n2": "n1_pw",
                "n3_dw": "n2", "n4": "n3_pw"}
            if profile not in previous_by_profile:
                raise ValueError("unsupported chained PL profile")
            executed = execute_chained(
                profile, context.lease,
                context.executed.pop(previous_by_profile[profile]))
        else:
            executed = self.backend.execute(
                profile, context.lease, context.prepared.pop(profile))
        context.timings[stage] = (time.perf_counter() - started) * 1000.0
        if self.backend.current_generation() != context.tag.generation:
            raise RuntimeError("driver generation changed during PL submit")
        if (isinstance(executed, dict) and "generation" in executed and
                executed["generation"] != context.tag.generation):
            raise RuntimeError("PL result generation changed")
        context.executed[profile] = executed
        if self.execution_plan.full_fusion:
            next_profile = {
                "n0": "n1_dw", "n1_dw": "n1_pw", "n1_pw": "n2",
                "n2": "n3_dw", "n3_pw": "n4"}.get(profile)
            if next_profile is not None:
                return "plchain_" + next_profile
        if (profile == "n1_dw" and
                self.execution_plan.transition_routes["n1"] == "pl_split"):
            return "plchain_n1_pw"
        return "finish_" + profile

    def _worker(self, worker_kind, work_queue, ps_queue, pl_queue,
                terminal_queue, stop):
        while not stop.is_set():
            try:
                stage, context = work_queue.get(timeout=_POLL_SECONDS)
            except queue.Empty:
                continue
            if stop.is_set():
                continue
            event = context.stage_events.setdefault(
                stage, {"queued_ns": time.perf_counter()})
            event["start_ns"] = time.perf_counter()
            try:
                if worker_kind == "pl":
                    next_stage = self._run_pl_stage(stage, context)
                else:
                    next_stage = self._run_ps_stage(stage, context)
                event["end_ns"] = time.perf_counter()
                context.timings[stage] = (
                    event["end_ns"] - event["start_ns"]) * 1000.0
                if next_stage is None:
                    terminal_queue.put(("ready", (context, event["end_ns"])))
                else:
                    target = (pl_queue if next_stage.startswith(("pl_", "plchain_"))
                              else ps_queue)
                    self._queue_stage(target, next_stage, context, stop)
            except Exception as error:
                event["end_ns"] = time.perf_counter()
                context.timings[stage] = (
                    event["end_ns"] - event["start_ns"]) * 1000.0
                wrapped = (error if isinstance(error, PipelineStageError)
                           else PipelineStageError(stage, context.tag, error))
                terminal_queue.put(("error", wrapped))
                stop.set()

    def _join_workers(self, stop, timeout_s):
        stop.set()
        deadline = time.perf_counter() + timeout_s
        for thread in self._threads:
            remaining = max(0.0, deadline - time.perf_counter())
            thread.join(remaining)
        return [thread.name for thread in self._threads if thread.is_alive()]

    def recover(self, timeout_s=None):
        """Finish a timed-out drain before releasing any live DDR lease."""
        timeout_s = self.cleanup_timeout_s if timeout_s is None else float(timeout_s)
        if timeout_s < 0:
            raise ValueError("recovery timeout must be non-negative")
        if not self._run_lock.acquire(False):
            raise RuntimeError("cannot recover while the v6 DAG is running")
        try:
            deadline = time.perf_counter() + timeout_s
            for thread in self._threads:
                remaining = max(0.0, deadline - time.perf_counter())
                thread.join(remaining)
            alive = self.threads_alive
            if alive:
                raise PipelineShutdownTimeout(alive)
            released = 0
            pending = list(self._orphaned_contexts)
            for context in pending:
                self._release_context(context)
                released += 1
                self._orphaned_contexts.remove(context)
            return {"frames_released": released, "workers_alive": ()}
        finally:
            self._run_lock.release()

    def run(self, items, expected_frame_ids):
        expected = self._expected_ids(expected_frame_ids)
        if not self._run_lock.acquire(False):
            raise RuntimeError("this v6 DAG pipeline is already running")
        if self._orphaned_contexts:
            self._run_lock.release()
            raise RuntimeError("pipeline requires recover() before another run")
        self.stats = self._new_stats()
        self._active_activation_handles = set()
        self._parameter_identity = None
        generation = self.backend.current_generation()
        ps_queue = queue.Queue(self.queue_capacity)
        pl_queue = queue.Queue(self.queue_capacity)
        terminal_queue = queue.Queue()
        stop = threading.Event()
        contexts = {}
        results = {}
        ready_by_sequence = {}
        item_iterator = iter(items)
        admitted_count = 0
        completed_count = 0
        pending = [None]
        batch_start = time.perf_counter()
        self.last_batch_start = batch_start
        self.last_batch_end = None
        deadline = batch_start + self.run_timeout_s
        primary_error = None

        threads = []
        for index in range(self.ps_workers):
            threads.append(threading.Thread(
                target=self._worker,
                args=("ps", ps_queue, ps_queue, pl_queue, terminal_queue, stop),
                name="%s-ps-%d" % (self.thread_name, index)))
        threads.append(threading.Thread(
            target=self._worker,
            args=("pl", pl_queue, ps_queue, pl_queue, terminal_queue, stop),
            name="%s-pl-owner" % self.thread_name))
        self._threads = tuple(threads)
        for thread in self._threads:
            thread.daemon = True
            thread.start()

        def prefetch_one():
            if pending[0] is not None or admitted_count >= len(expected):
                return pending[0] is not None
            arrival_ns = time.perf_counter()
            try:
                item = next(item_iterator)
            except StopIteration:
                raise ValueError("items ended before expected frame IDs")
            frame_id, value, metadata = self._parse_item(item)
            if frame_id != expected[admitted_count]:
                raise ValueError("item frame ID does not match expected order")
            pending[0] = (frame_id, value, metadata, arrival_ns)
            return True

        def admit_one():
            nonlocal admitted_count
            if not prefetch_one():
                return False
            frame_id, value, metadata, arrival_ns = pending[0]
            tag = FrameTag(generation, frame_id, admitted_count)
            lease = None
            try:
                lease = self.backend.acquire_frame(tag)
                self._register_lease(lease, tag)
                context = _FrameContext(
                    tag, value, metadata, lease, arrival_ns)
                context.admitted_ns = time.perf_counter()
                contexts[admitted_count] = context
                if not self._queue_stage(ps_queue, "capture", context, stop):
                    raise RuntimeError("admission stopped")
            except Exception:
                if lease is not None:
                    try:
                        self.backend.release_frame(lease)
                    except Exception:
                        pass
                raise
            pending[0] = None
            admitted_count += 1
            self.stats["in_flight_peak"] = max(
                self.stats["in_flight_peak"], admitted_count - completed_count)
            return True

        try:
            while (admitted_count < len(expected) and
                   admitted_count - completed_count < self.max_in_flight):
                admit_one()
            # Match streaming producer semantics: one next frame may arrive
            # and wait behind the global in-flight bound.
            prefetch_one()
            if not expected:
                self.last_batch_end = batch_start
                try:
                    next(item_iterator)
                    raise ValueError("items contain frames but expected IDs are empty")
                except StopIteration:
                    pass

            while completed_count < len(expected) and primary_error is None:
                remaining = deadline - time.perf_counter()
                if remaining <= 0:
                    primary_error = PipelineStageError(
                        "run", None, PipelineRunTimeout("v6 DAG run timed out"))
                    stop.set()
                    break
                try:
                    kind, payload = terminal_queue.get(
                        timeout=min(_POLL_SECONDS, remaining))
                except queue.Empty:
                    continue
                if kind == "error":
                    primary_error = payload
                    stop.set()
                    break
                context, compute_ready_ns = payload
                ready_by_sequence[context.tag.sequence_index] = (
                    context, compute_ready_ns)
                while completed_count in ready_by_sequence:
                    context, compute_ready_ns = ready_by_sequence.pop(completed_count)
                    output_start_ns = time.perf_counter()
                    context.stage_events["output"] = {
                        "queued_ns": compute_ready_ns,
                        "start_ns": output_start_ns,
                    }
                    try:
                        context.value = self.callbacks.call("output", context.value)
                        output_done_ns = time.perf_counter()
                        context.stage_events["output"]["end_ns"] = output_done_ns
                        context.timings["output"] = (
                            output_done_ns - output_start_ns) * 1000.0
                        self._release_context(context)
                    except Exception as error:
                        context.stage_events["output"]["end_ns"] = time.perf_counter()
                        primary_error = PipelineStageError(
                            "output", context.tag, error)
                        stop.set()
                        break
                    event_times = {}
                    for stage_name, stage_event in context.stage_events.items():
                        event_times[stage_name] = {
                            name.replace("_ns", "_ms"):
                                (value - batch_start) * 1000.0
                            for name, value in stage_event.items()}
                    results[context.tag.sequence_index] = V6FrameResult(
                        context.tag, context.value, context.features,
                        context.metadata, context.timings, context.completions,
                        (context.arrival_ns - batch_start) * 1000.0,
                        (context.admitted_ns - batch_start) * 1000.0,
                        (compute_ready_ns - batch_start) * 1000.0,
                        (output_start_ns - batch_start) * 1000.0,
                        (output_done_ns - batch_start) * 1000.0,
                        event_times)
                    completed_count += 1
                    if completed_count == len(expected):
                        self.last_batch_end = output_done_ns
                    contexts.pop(context.tag.sequence_index, None)
                    while (admitted_count < len(expected) and
                           admitted_count - completed_count < self.max_in_flight):
                        admit_one()
                    prefetch_one()
                if primary_error is not None:
                    break

            if primary_error is None and admitted_count == len(expected):
                try:
                    next(item_iterator)
                    primary_error = PipelineStageError(
                        "admission", None,
                        ValueError("items contain more frames than expected IDs"))
                    stop.set()
                except StopIteration:
                    pass
        except Exception as error:
            primary_error = (error if isinstance(error, PipelineStageError)
                             else PipelineStageError("admission", None, error))
            stop.set()
        finally:
            alive = self._join_workers(
                stop, self.cleanup_timeout_s if primary_error else self.run_timeout_s)
            if alive and primary_error is None:
                primary_error = PipelineStageError(
                    "shutdown", None, PipelineShutdownTimeout(alive))
            elif alive:
                primary_error.cleanup_errors.append(PipelineShutdownTimeout(alive))
            if alive:
                # A Python thread cannot be killed. Keep every potentially
                # referenced DDR activation alive until recover() observes the
                # PL/PS call boundary and can release it safely.
                self._orphaned_contexts = [
                    contexts[index] for index in sorted(contexts)
                    if not contexts[index].released]
            else:
                for index in sorted(contexts):
                    context = contexts[index]
                    if context.released:
                        continue
                    try:
                        self._release_context(context)
                    except Exception as cleanup_error:
                        if primary_error is None:
                            primary_error = PipelineStageError(
                                "release", context.tag, cleanup_error)
                        else:
                            primary_error.cleanup_errors.append(cleanup_error)
            self._run_lock.release()

        if primary_error is not None:
            raise primary_error
        return [results[index] for index in range(len(expected))]

