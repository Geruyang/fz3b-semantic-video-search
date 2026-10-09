"""Bounded, board-Python-3.6-compatible three-stage pipeline.

The callable backend is intentionally generic. A simulation summary is not
evidence of board throughput; callers must provide the measured execution
identity and an explicit correctness validator before creating a summary.
"""

import copy
import hashlib
import queue
import threading
import time
import uuid


_STOP = object()
_UINT32_MAX = (1 << 32) - 1
_POLL_SECONDS = 0.02


class PipelineStageError(RuntimeError):
    """An exception from a stage, correctness validator, or memory hook."""

    def __init__(self, stage, frame_id, cause):
        self.stage = stage
        self.frame_id = frame_id
        self.cause = cause
        RuntimeError.__init__(self, "%s frame %s failed: %s" % (stage, frame_id, cause))


class PipelineShutdownTimeout(RuntimeError):
    """A worker did not exit before the bounded cleanup deadline."""

    def __init__(self, names):
        self.thread_names = tuple(names)
        RuntimeError.__init__(self, "workers did not stop before timeout: %s" %
                              ", ".join(self.thread_names))


class PipelineRunTimeout(RuntimeError):
    """The configured total-run deadline elapsed before pipeline drain."""


class PipelineResult(object):
    """Full result, including pre-admission wait and end-to-end timings.

    ``submit_ms`` is actual queue admission time from batch start;
    ``admission_start_ms`` is when the producer received this item, before
    copying or waiting for a global permit.
    """

    def __init__(self, frame_id, value, submit_ms, complete_ms,
                 components_ms, correct, run_id, postprocess_ms,
                 admission_start_ms=None, admission_wait_ms=None,
                 end_to_end_ms=None):
        self.frame_id = frame_id
        self.value = value
        self.submit_ms = submit_ms
        self.complete_ms = complete_ms
        self.components_ms = dict(components_ms)
        self.correct = correct
        self.run_id = run_id
        self.postprocess_ms = postprocess_ms
        self.admission_start_ms = admission_start_ms
        self.admission_wait_ms = admission_wait_ms
        self.end_to_end_ms = end_to_end_ms


class PipelineReceipt(object):
    """Small result with admission and end-to-end timings for streaming use."""

    def __init__(self, frame_id, submit_ms, complete_ms, components_ms,
                 correct, run_id, postprocess_ms, admission_start_ms=None,
                 admission_wait_ms=None, end_to_end_ms=None):
        self.frame_id = frame_id
        self.value = None
        self.submit_ms = submit_ms
        self.complete_ms = complete_ms
        self.components_ms = dict(components_ms)
        self.correct = correct
        self.run_id = run_id
        self.postprocess_ms = postprocess_ms
        self.admission_start_ms = admission_start_ms
        self.admission_wait_ms = admission_wait_ms
        self.end_to_end_ms = end_to_end_ms


class _Pending(object):
    """Queue reservation whose submit time is set after successful admission."""

    def __init__(self, frame_id, value, ready, lease=None,
                 admission_start_ns=None):
        self.frame_id = frame_id
        self.value = value
        self.ready = ready
        self.lease = lease
        self.admission_start_ns = admission_start_ns
        self.submit_ns = None


class _InFlightLease(object):
    """One reserved admission permit, released once after completion/cleanup."""

    def __init__(self, semaphore, on_release):
        self.semaphore = semaphore
        self.on_release = on_release
        self.lock = threading.Lock()
        self.released = False

    def release(self):
        with self.lock:
            if self.released:
                return
            self.released = True
        self.on_release(self)
        if self.semaphore is not None:
            self.semaphore.release()


def _lease_copy(value):
    """Take an owned snapshot before the producer of a buffer can reuse it."""
    return copy.deepcopy(value)


class BoundedPipeline(object):
    """One worker per stage, with bounded queues and an optional global cap.

    ``items`` are consumed incrementally and must match ``expected_frame_ids``.
    Results are returned in expected order by default. For bounded output
    retention, pass ``result_consumer`` and ``retain_results=False`` to receive
    only lightweight receipts from ``run``. A callable already executing in a
    Python thread cannot be killed. ``run_timeout_s`` bounds ordinary execution
    and drain; ``cleanup_timeout_s`` bounds waiting after failure/cancellation.
    A timed-out instance stays poisoned while any old worker remains alive.
    """

    def __init__(self, prefix, backend, suffix, queue_capacity=2,
                 memory_hook=None, thread_name="bounded-pipeline",
                 run_timeout_s=300.0, cleanup_timeout_s=5.0,
                 max_in_flight=None):
        if isinstance(queue_capacity, bool) or not isinstance(queue_capacity, int) or queue_capacity < 1:
            raise ValueError("queue_capacity must be a positive integer")
        if run_timeout_s <= 0 or cleanup_timeout_s <= 0:
            raise ValueError("run_timeout_s and cleanup_timeout_s must be positive")
        if (max_in_flight is not None and
                (isinstance(max_in_flight, bool) or not isinstance(max_in_flight, int) or
                 max_in_flight < 1)):
            raise ValueError("max_in_flight must be a positive integer or None")
        self.stages = {"prefix": prefix, "backend": backend, "suffix": suffix}
        self.queue_capacity = queue_capacity
        self.memory_hook = memory_hook
        self.thread_name = thread_name
        self.run_timeout_s = float(run_timeout_s)
        self.cleanup_timeout_s = float(cleanup_timeout_s)
        self.max_in_flight = max_in_flight
        self._run_lock = threading.Lock()
        self._threads = ()
        self._active_run_id = None
        self._run_completed = False
        self._poisoned = False
        self._expected_frame_ids = ()
        self._last_batch_start = None
        self._last_batch_end = None
        self._memory_start = None
        self._memory_end = None
        self._memory_peak = None
        self.queue_stats = self._new_stats()

    def _new_stats(self):
        return {"capacity": self.queue_capacity,
                "peak": {name: 0 for name in ("prefix", "backend", "suffix")},
                "submit_wait_ms": 0.0,
                "max_in_flight": self.max_in_flight,
                "in_flight_peak": 0,
                "in_flight_current": 0}

    @property
    def threads_alive(self):
        return tuple(thread.name for thread in self._threads if thread.is_alive())

    @staticmethod
    def _validate_expected(expected_frame_ids):
        expected = list(expected_frame_ids)
        for frame_id in expected:
            if (isinstance(frame_id, bool) or not isinstance(frame_id, int) or
                    frame_id < 0 or frame_id > _UINT32_MAX):
                raise ValueError("frame IDs must be uint32 integers")
        if len(expected) != len(set(expected)):
            raise ValueError("duplicate expected frame ID")
        return expected

    def _observe_queue(self, name, q, lock):
        with lock:
            self.queue_stats["peak"][name] = max(self.queue_stats["peak"][name], q.qsize())

    def _put_pending(self, target, pending, cancel, stats_lock, run_deadline,
                     semaphore, register_lease):
        started = time.perf_counter()
        waited = False
        while not cancel.is_set():
            if time.perf_counter() >= run_deadline:
                cancel.set()
                return False
            if semaphore is not None and not semaphore.acquire(timeout=_POLL_SECONDS):
                waited = True
                continue
            lease = _InFlightLease(semaphore, register_lease)
            pending.lease = lease
            while not cancel.is_set() and time.perf_counter() < run_deadline:
                try:
                    target.put(pending, timeout=_POLL_SECONDS)
                    pending.submit_ns = time.perf_counter()
                    register_lease(lease, activate=True)
                    pending.ready.set()
                    elapsed_ms = (pending.submit_ns - started) * 1000.0
                    if waited or elapsed_ms > 1.0:
                        with stats_lock:
                            self.queue_stats["submit_wait_ms"] += elapsed_ms
                    return True
                except queue.Full:
                    waited = True
            # A reserved token was never admitted, so return it directly.
            lease.release()
            if time.perf_counter() >= run_deadline:
                cancel.set()
            return False
        return False

    def _put_stop(self, target, cancel):
        while not cancel.is_set():
            try:
                target.put(_STOP, timeout=_POLL_SECONDS)
                return True
            except queue.Full:
                pass
        return False

    def _sample_memory(self):
        if self.memory_hook is None:
            return None
        return float(self.memory_hook())

    def _bounded_join(self, threads, cancel, timeout_s, cleanup_timeout_s):
        deadline = time.perf_counter() + timeout_s
        cleanup_mode = cancel.is_set()
        if cleanup_mode:
            deadline = time.perf_counter() + cleanup_timeout_s
        while True:
            alive = [thread for thread in threads if thread.is_alive()]
            if not alive:
                return []
            now = time.perf_counter()
            if cancel.is_set() and not cleanup_mode:
                # A stage/producer error may arrive during an otherwise normal
                # drain. Switch immediately to one fixed cleanup window.
                cleanup_mode = True
                deadline = now + cleanup_timeout_s
            elif now >= deadline:
                if not cleanup_mode:
                    cancel.set()
                    cleanup_mode = True
                    deadline = now + cleanup_timeout_s
                else:
                    return [thread.name for thread in alive]
            remaining = max(0.0, deadline - time.perf_counter())
            alive[0].join(min(_POLL_SECONDS, remaining))

    def run(self, items, expected_frame_ids, validator=None,
            result_consumer=None, retain_results=True, cancel_event=None):
        expected = self._validate_expected(expected_frame_ids)
        if not self._run_lock.acquire(False):
            raise RuntimeError("this pipeline is already running")
        if self._poisoned:
            if any(thread.is_alive() for thread in self._threads):
                self._run_lock.release()
                raise RuntimeError("pipeline is poisoned while an old worker is alive")
            self._poisoned = False
        queues = [queue.Queue(self.queue_capacity) for unused in range(3)]
        cancel = threading.Event()
        stop_watchdog = threading.Event()
        run_deadline = time.perf_counter() + self.run_timeout_s
        timeout_reason = [None]
        stats_lock = threading.Lock()
        error_lock = threading.Lock()
        result_lock = threading.Lock()
        inflight_lock = threading.Lock()
        active_leases = set()
        inflight_semaphore = (threading.BoundedSemaphore(self.max_in_flight)
                              if self.max_in_flight is not None else None)
        errors = []
        results_by_id = {}
        returned_receipts = []
        self.queue_stats = self._new_stats()
        run_id = uuid.uuid4().hex
        self._active_run_id = run_id
        self._run_completed = False
        self._validation_enabled = validator is not None
        self._consumer_enabled = result_consumer is not None
        self._expected_frame_ids = tuple(expected)
        self._last_batch_start = time.perf_counter()
        self._last_batch_end = self._last_batch_start
        self._memory_start = None
        self._memory_end = None
        self._memory_peak = None

        def record_error(stage, frame_id, cause):
            with error_lock:
                if not errors:
                    errors.append(PipelineStageError(stage, frame_id, cause))
            cancel.set()

        def track_lease(lease, activate=False):
            with inflight_lock:
                if activate:
                    active_leases.add(lease)
                    count = len(active_leases)
                    self.queue_stats["in_flight_current"] = count
                    self.queue_stats["in_flight_peak"] = max(
                        self.queue_stats["in_flight_peak"], count)
                elif lease in active_leases:
                    active_leases.remove(lease)
                    self.queue_stats["in_flight_current"] = len(active_leases)

        def release_outstanding_leases():
            with inflight_lock:
                outstanding = list(active_leases)
            for lease in outstanding:
                lease.release()

        def watchdog():
            while not stop_watchdog.wait(0.01):
                if cancel_event is not None and cancel_event.is_set():
                    timeout_reason[0] = "external cancellation requested"
                    cancel.set()
                    return
                if time.perf_counter() >= run_deadline:
                    timeout_reason[0] = "pipeline run deadline elapsed"
                    cancel.set()
                    return

        def worker(index):
            name = ("prefix", "backend", "suffix")[index]
            current_q = queues[index]
            next_q = queues[index + 1] if index < 2 else None
            function = self.stages[name]
            while not cancel.is_set():
                try:
                    entry = current_q.get(timeout=_POLL_SECONDS)
                except queue.Empty:
                    continue
                lease = None
                try:
                    if entry is _STOP:
                        if next_q is not None:
                            self._put_stop(next_q, cancel)
                        return
                    if isinstance(entry, _Pending):
                        pending = entry
                        while not pending.ready.wait(_POLL_SECONDS):
                            if cancel.is_set():
                                return
                        frame_id = pending.frame_id
                        value = pending.value
                        submit_ns = pending.submit_ns
                        lease = pending.lease
                        admission_start_ns = pending.admission_start_ns
                        components = {}
                    else:
                        (frame_id, value, submit_ns, components, lease,
                         admission_start_ns) = entry
                    stage_start = time.perf_counter()
                    try:
                        output = _lease_copy(function(frame_id, value))
                    except BaseException as exc:
                        record_error(name, frame_id, exc)
                        return
                    stage_end = time.perf_counter()
                    next_components = dict(components)
                    next_components[name] = (stage_end - stage_start) * 1000.0
                    if next_q is not None:
                        next_entry = (frame_id, output, submit_ns, next_components,
                                      lease, admission_start_ns)
                        while not cancel.is_set():
                            try:
                                next_q.put(next_entry, timeout=_POLL_SECONDS)
                                self._observe_queue(("backend", "suffix")[index], next_q, stats_lock)
                                break
                            except queue.Full:
                                continue
                        continue

                    postprocess_start = time.perf_counter()
                    correct = None
                    if validator is not None:
                        try:
                            correct = bool(validator(frame_id, output))
                        except BaseException as exc:
                            record_error("validator", frame_id, exc)
                            return
                    if result_consumer is not None:
                        try:
                            consumer_ready = time.perf_counter()
                            provisional = PipelineResult(
                                frame_id, output, (submit_ns - self._last_batch_start) * 1000.0,
                                (consumer_ready - self._last_batch_start) * 1000.0,
                                next_components, correct, run_id, 0.0,
                                (admission_start_ns - self._last_batch_start) * 1000.0,
                                (submit_ns - admission_start_ns) * 1000.0,
                                (consumer_ready - admission_start_ns) * 1000.0)
                            result_consumer(provisional)
                        except BaseException as exc:
                            record_error("consumer", frame_id, exc)
                            return
                    postprocess_end = time.perf_counter()
                    postprocess_ms = (postprocess_end - postprocess_start) * 1000.0
                    result = PipelineResult(
                        frame_id, output, (submit_ns - self._last_batch_start) * 1000.0,
                        (postprocess_end - self._last_batch_start) * 1000.0,
                        next_components, correct, run_id, postprocess_ms,
                        (admission_start_ns - self._last_batch_start) * 1000.0,
                        (submit_ns - admission_start_ns) * 1000.0,
                        (postprocess_end - admission_start_ns) * 1000.0)
                    with result_lock:
                        if retain_results:
                            results_by_id[frame_id] = result
                        else:
                            returned_receipts.append(PipelineReceipt(
                                frame_id, result.submit_ms, result.complete_ms,
                                result.components_ms, result.correct, run_id,
                                result.postprocess_ms, result.admission_start_ms,
                                result.admission_wait_ms, result.end_to_end_ms))
                    # The consumer boundary is complete once its receipt/result
                    # is committed. The finally block remains an idempotent
                    # fallback for exceptions before this point.
                    if lease is not None:
                        lease.release()
                    if self.memory_hook is not None:
                        try:
                            memory = self._sample_memory()
                            self._memory_peak = memory if self._memory_peak is None else max(self._memory_peak, memory)
                        except BaseException as exc:
                            record_error("memory", frame_id, exc)
                            return
                finally:
                    if index == 2 and lease is not None:
                        lease.release()
                    current_q.task_done()

        threads = [threading.Thread(target=worker, args=(i,),
                                    name="%s-%s" % (self.thread_name, name), daemon=True)
                   for i, name in enumerate(("prefix", "backend", "suffix"))]
        producer_error = None
        started_threads = []
        watchdog_thread = threading.Thread(target=watchdog,
                                           name="%s-watchdog" % self.thread_name,
                                           daemon=True)
        producer_error_box = []

        def producer():
            count = 0
            try:
                for item in items:
                    admission_start_ns = time.perf_counter()
                    if cancel.is_set():
                        return
                    if not isinstance(item, (tuple, list)) or len(item) != 2:
                        raise ValueError("items must yield (frame_id, payload) pairs")
                    frame_id, payload = item
                    if count >= len(expected) or frame_id != expected[count]:
                        raise ValueError("submitted frame IDs must match the expected sequence")
                    if (isinstance(frame_id, bool) or not isinstance(frame_id, int) or
                            frame_id < 0 or frame_id > _UINT32_MAX):
                        raise ValueError("frame IDs must be uint32 integers")
                    leased_payload = _lease_copy(payload)
                    if cancel.is_set():
                        return
                    pending = _Pending(frame_id, leased_payload, threading.Event(),
                                       admission_start_ns=admission_start_ns)
                    if not self._put_pending(queues[0], pending, cancel, stats_lock,
                                             run_deadline, inflight_semaphore, track_lease):
                        if time.perf_counter() >= run_deadline and timeout_reason[0] is None:
                            timeout_reason[0] = "pipeline run deadline elapsed"
                        return
                    count += 1
                    self._observe_queue("prefix", queues[0], stats_lock)
                if not cancel.is_set() and count != len(expected):
                    raise ValueError("submitted frame IDs do not match expected frame IDs")
                if not cancel.is_set():
                    self._put_stop(queues[0], cancel)
            except BaseException as exc:
                producer_error_box.append(exc)
                cancel.set()

        producer_thread = threading.Thread(target=producer,
                                           name="%s-producer" % self.thread_name,
                                           daemon=True)
        all_threads = [watchdog_thread] + threads + [producer_thread]
        self._threads = tuple(all_threads)
        started_threads = []
        join_threads = []
        try:
            try:
                self._memory_start = self._sample_memory()
                self._memory_peak = self._memory_start
                watchdog_thread.start()
                started_threads.append(watchdog_thread)
                for thread in threads:
                    thread.start()
                    started_threads.append(thread)
                    join_threads.append(thread)
                producer_thread.start()
                started_threads.append(producer_thread)
                join_threads.append(producer_thread)
            except BaseException as exc:
                producer_error = exc
                cancel.set()
        finally:
            if producer_error is not None or errors or producer_error_box:
                cancel.set()
            if timeout_reason[0] is not None:
                cancel.set()
            normal_drain = producer_error is None and not errors and not producer_error_box and timeout_reason[0] is None
            if normal_drain:
                join_timeout = max(0.0, run_deadline - time.perf_counter())
            else:
                join_timeout = self.cleanup_timeout_s
            alive = self._bounded_join(join_threads, cancel, join_timeout,
                                       self.cleanup_timeout_s)
            if time.perf_counter() >= run_deadline and timeout_reason[0] is None:
                timeout_reason[0] = "pipeline run deadline elapsed"
            stop_watchdog.set()
            if watchdog_thread.is_alive():
                watchdog_thread.join(self.cleanup_timeout_s)
            release_outstanding_leases()
            alive = [thread.name for thread in started_threads if thread.is_alive()]
            self._last_batch_end = time.perf_counter()
            try:
                self._memory_end = self._sample_memory()
                if self._memory_end is not None:
                    self._memory_peak = (self._memory_end if self._memory_peak is None else
                                         max(self._memory_peak, self._memory_end))
            except BaseException as exc:
                if producer_error is None and not errors:
                    producer_error = exc
            if producer_error_box:
                producer_error = producer_error_box[0]
            if alive:
                self._poisoned = True
            self._run_lock.release()

        if alive:
            raise PipelineShutdownTimeout(alive)
        if timeout_reason[0] is not None:
            if timeout_reason[0] == "pipeline run deadline elapsed":
                raise PipelineRunTimeout(timeout_reason[0])
            raise RuntimeError(timeout_reason[0])
        if producer_error is not None:
            raise producer_error
        if errors:
            raise errors[0]
        if cancel.is_set():
            raise RuntimeError("pipeline cancelled without a recorded exception")
        if retain_results:
            if set(results_by_id) != set(expected):
                missing = sorted(set(expected) - set(results_by_id))
                raise RuntimeError("pipeline drained without all outputs; missing %s" % missing)
            self._run_completed = True
            return [results_by_id[frame_id] for frame_id in expected]
        if len(returned_receipts) != len(expected):
            raise RuntimeError("pipeline drained without all receipts")
        returned_receipts.sort(key=lambda result: expected.index(result.frame_id))
        self._run_completed = True
        return returned_receipts

    def schema_v1_summary(self, results, stage, execution, model_sha256,
                          boundary, threads, cpu_frequency_khz, profile,
                          warmup_count, identity, input_sha256,
                          feature_sha256):
        if execution not in ("board", "simulation"):
            raise ValueError("execution must be 'board' or 'simulation'")
        if self._active_run_id is None or not self._run_completed:
            raise ValueError("no completed run is available for a summary")
        frame_ids = [result.frame_id for result in results]
        if tuple(frame_ids) != self._expected_frame_ids:
            raise ValueError("summary results do not match this run's expected frame IDs")
        if any(result.run_id != self._active_run_id for result in results):
            raise ValueError("summary contains stale results from another run")
        if any(result.correct is None for result in results):
            raise ValueError("benchmark summary requires an explicit correctness validator")

        def check_sha(label, value):
            if (not isinstance(value, str) or len(value) != 64 or
                    any(ch not in "0123456789abcdef" for ch in value)):
                raise ValueError("%s must be a 64-character lowercase SHA-256" % label)
            return value

        check_sha("model_sha256", model_sha256)
        records = []
        input_sequence = hashlib.sha256()
        for result in results:
            source_hash = check_sha("input_sha256", input_sha256[result.frame_id])
            output_hash = check_sha("feature_sha256", feature_sha256[result.frame_id])
            input_sequence.update((source_hash + "\n").encode("ascii"))
            records.append({
                "frame_id": result.frame_id,
                "input_sha256": source_hash,
                "feature_sha256": output_hash,
                "submit_ms": result.submit_ms,
                "complete_ms": result.complete_ms,
                "admission_start_ms": result.admission_start_ms,
                "admission_wait_ms": result.admission_wait_ms,
                "end_to_end_ms": result.end_to_end_ms,
                "correct": bool(result.correct),
                "postprocess_ms": result.postprocess_ms,
                "components_ms": dict(result.components_ms),
            })
        batch_ms = max(0.0, (self._last_batch_end - self._last_batch_start) * 1000.0)
        summary = {
            "schema_version": 1,
            "stage": stage,
            "execution": execution,
            "model_sha256": model_sha256,
            "input_sequence_sha256": input_sequence.hexdigest(),
            "boundary": boundary,
            "threads": dict(threads),
            "cpu_frequency_khz": list(cpu_frequency_khz),
            "profile": bool(profile),
            "warmup_count": int(warmup_count),
            "expected_frame_ids": list(self._expected_frame_ids),
            "records": records,
            "batch_start_ms": 0.0,
            "batch_end_ms": batch_ms,
            "identity": dict(identity),
            "run_id": self._active_run_id,
            "postprocess_timing": {
                "included_in_complete_ms": True,
                "validator_enabled": self._validation_enabled,
                "consumer_enabled": self._consumer_enabled,
            },
            "queue": {"capacity": self.queue_capacity,
                      "peak": dict(self.queue_stats["peak"]),
                      "max_in_flight": self.max_in_flight,
                      "in_flight_peak": self.queue_stats["in_flight_peak"]},
        }
        if self._memory_start is not None:
            summary["memory"] = {"start_kib": self._memory_start,
                                  "end_kib": self._memory_end,
                                  "peak_kib": self._memory_peak}
        return summary
