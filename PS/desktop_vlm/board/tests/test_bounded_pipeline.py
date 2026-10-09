import hashlib
import sys
import threading
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bounded_pipeline import BoundedPipeline, PipelineStageError


def test_consumer_receipt_uses_one_completion_timestamp(monkeypatch):
    import itertools
    from types import SimpleNamespace
    import bounded_pipeline

    ticks = itertools.count(1000000)
    monkeypatch.setattr(bounded_pipeline, "time", SimpleNamespace(
        perf_counter=lambda: next(ticks) / 1000.0))
    observed = []
    pipeline = BoundedPipeline(lambda fid, x: x, lambda fid, x: x,
                               lambda fid, x: x)
    pipeline.run([(0, 1)], [0], result_consumer=observed.append)
    receipt = observed[0]
    assert receipt.end_to_end_ms == pytest.approx(
        receipt.complete_ms - receipt.admission_start_ms, rel=0, abs=1e-9)


def test_three_stage_pipeline_returns_32_frames_in_expected_order_and_copies_values():
    scratch = [0]

    def prefix(frame_id, payload):
        time.sleep((31 - frame_id % 32) * 0.00005)
        return [payload + 1]

    def backend(frame_id, value):
        scratch[0] = value[0] * 2
        return scratch

    def suffix(frame_id, value):
        return value[0] + frame_id

    pipeline = BoundedPipeline(prefix, backend, suffix, queue_capacity=2)
    expected = list(range(32))
    results = pipeline.run([(frame_id, frame_id) for frame_id in expected], expected)

    assert [result.frame_id for result in results] == expected
    assert [result.value for result in results] == [3 * frame_id + 2 for frame_id in expected]
    assert all(set(result.components_ms) == {"prefix", "backend", "suffix"}
               for result in results)
    assert pipeline.queue_stats["capacity"] == 2
    assert all(0 <= peak <= 2 for peak in pipeline.queue_stats["peak"].values())
    assert pipeline.queue_stats["submit_wait_ms"] >= 0


def test_bounded_pipeline_exposes_backpressure_when_first_stage_is_slow():
    release = threading.Event()

    def slow_prefix(frame_id, payload):
        if frame_id == 0:
            release.wait(0.15)
        return payload

    pipeline = BoundedPipeline(slow_prefix, lambda fid, x: x, lambda fid, x: x,
                               queue_capacity=1)
    results = pipeline.run([(i, i) for i in range(12)], list(range(12)))

    assert len(results) == 12
    assert pipeline.queue_stats["submit_wait_ms"] >= 20
    assert pipeline.queue_stats["peak"]["prefix"] <= 1


def test_pipeline_failure_stops_workers_reaps_threads_and_preserves_exception():
    def backend(frame_id, value):
        if frame_id == 5:
            raise LookupError("backend frame 5 failed")
        return value

    pipeline = BoundedPipeline(lambda fid, x: x, backend, lambda fid, x: x,
                               queue_capacity=1, thread_name="failure-check")
    with pytest.raises(PipelineStageError, match="backend frame 5 failed") as caught:
        pipeline.run([(i, i) for i in range(32)], list(range(32)))

    assert caught.value.stage == "backend"
    assert pipeline.threads_alive == ()


@pytest.mark.parametrize("items,expected", [
    ([(1, "a"), (1, "b")], [1, 1]),
    ([(1, "a")], [1, 2]),
    ([(2, "a"), (1, "b")], [1, 2]),
    ([(2 ** 32, "a")], [2 ** 32]),
])
def test_pipeline_rejects_duplicate_missing_unexpected_or_non_uint32_ids(items, expected):
    pipeline = BoundedPipeline(lambda fid, x: x, lambda fid, x: x, lambda fid, x: x)
    with pytest.raises(ValueError):
        pipeline.run(items, expected)


def test_timing_summary_has_schema_v1_frame_timing_queue_and_memory_hooks():
    pipeline = BoundedPipeline(lambda fid, x: x + 1, lambda fid, x: x * 2,
                               lambda fid, x: x + 3, memory_hook=lambda: 128)
    results = pipeline.run([(7, 7)], [7], validator=lambda fid, value: value == 24)
    input_hash = hashlib.sha256(b"input").hexdigest()
    feature_hash = hashlib.sha256(b"feature").hexdigest()
    summary = pipeline.schema_v1_summary(
        results, stage="cpu-only-pipeline", execution="simulation",
        model_sha256="a" * 64, boundary="submit-to-output", threads={"host": 1},
        cpu_frequency_khz=[1000], profile=False, warmup_count=0,
        identity={"backend": "python-callables"},
        input_sha256={7: input_hash}, feature_sha256={7: feature_hash})

    assert summary["schema_version"] == 1
    record = summary["records"][0]
    assert record["frame_id"] == 7
    assert record["complete_ms"] >= record["submit_ms"]
    assert set(record["components_ms"]) == {"prefix", "backend", "suffix"}
    assert summary["queue"] == {
        "capacity": 2,
        "peak": pipeline.queue_stats["peak"],
        "max_in_flight": None,
        "in_flight_peak": 1,
    }
    assert summary["memory"] == {"start_kib": 128, "end_kib": 128, "peak_kib": 128}


def test_streaming_starts_after_clock_and_memory_sample_without_materializing_input():
    sampled = []
    first_stage = threading.Event()

    def source():
        assert sampled == ["memory"]
        yield 0, 0
        assert first_stage.wait(0.5)
        raise LookupError("iterator stopped after first frame")

    pipeline = BoundedPipeline(lambda fid, x: (first_stage.set() or x),
                               lambda fid, x: x, lambda fid, x: x,
                               memory_hook=lambda: (sampled.append("memory") or 1),
                               cleanup_timeout_s=0.5)
    with pytest.raises(LookupError, match="iterator stopped"):
        pipeline.run(source(), [0, 1])
    assert pipeline.threads_alive == ()


def test_unvalidated_result_cannot_be_marked_correct_in_benchmark_summary():
    pipeline = BoundedPipeline(lambda fid, x: x, lambda fid, x: x, lambda fid, x: x)
    results = pipeline.run([(1, 4)], [1])
    assert results[0].correct is None
    with pytest.raises(ValueError, match="correctness validator"):
        pipeline.schema_v1_summary(
            results, stage="cpu-only", execution="simulation", model_sha256="a" * 64,
            boundary="submit-to-output", threads={"host": 1}, cpu_frequency_khz=[],
            profile=False, warmup_count=0, identity={},
            input_sha256={1: "b" * 64}, feature_sha256={1: "c" * 64})


def test_schema_rejects_stale_or_incomplete_results_from_another_run():
    pipeline = BoundedPipeline(lambda fid, x: x, lambda fid, x: x, lambda fid, x: x)
    results = pipeline.run([(1, 4)], [1], validator=lambda fid, value: True)
    pipeline.run([(1, 5)], [1], validator=lambda fid, value: True)
    with pytest.raises(ValueError, match="stale results"):
        pipeline.schema_v1_summary(
            results, stage="cpu-only", execution="simulation", model_sha256="a" * 64,
            boundary="submit-to-output", threads={"host": 1}, cpu_frequency_khz=[],
            profile=False, warmup_count=0, identity={},
            input_sha256={1: "b" * 64}, feature_sha256={1: "c" * 64})


def test_payload_copy_finishes_before_submit_timestamp():
    copied = []

    class SlowCopy(object):
        def __deepcopy__(self, memo):
            time.sleep(0.05)
            copied.append(time.perf_counter())
            return "payload"

    pipeline = BoundedPipeline(lambda fid, x: x, lambda fid, x: x, lambda fid, x: x)
    result = pipeline.run([(1, SlowCopy())], [1])[0]
    assert result.submit_ms / 1000.0 >= copied[0] - pipeline._last_batch_start
    assert result.admission_wait_ms >= 45.0
    assert result.end_to_end_ms >= result.admission_wait_ms


def test_memory_hook_error_is_propagated_and_workers_are_reaped():
    calls = [0]

    def memory_hook():
        calls[0] += 1
        if calls[0] == 2:
            raise OSError("memory sample failed")
        return 4

    pipeline = BoundedPipeline(lambda fid, x: x, lambda fid, x: x, lambda fid, x: x,
                               memory_hook=memory_hook)
    with pytest.raises(PipelineStageError, match="memory sample failed"):
        pipeline.run([(1, 1)], [1])
    assert pipeline.threads_alive == ()


def test_payload_copy_failure_cancels_and_reaps_workers():
    class BrokenCopy(object):
        def __deepcopy__(self, memo):
            raise ArithmeticError("copy failed")

    pipeline = BoundedPipeline(lambda fid, x: x, lambda fid, x: x, lambda fid, x: x)
    with pytest.raises(ArithmeticError, match="copy failed"):
        pipeline.run(iter([(1, BrokenCopy())]), [1])
    assert pipeline.threads_alive == ()


def test_thread_start_failure_reaps_threads_started_earlier(monkeypatch):
    original_start = threading.Thread.start

    def failing_start(thread):
        if thread.name.endswith("-backend"):
            raise RuntimeError("thread start failed")
        return original_start(thread)

    monkeypatch.setattr(threading.Thread, "start", failing_start)
    pipeline = BoundedPipeline(lambda fid, x: x, lambda fid, x: x, lambda fid, x: x)
    with pytest.raises(RuntimeError, match="thread start failed"):
        pipeline.run([(1, 1)], [1])
    assert pipeline.threads_alive == ()


def test_consumer_and_receipt_mode_avoid_retaining_output_values():
    consumed = []
    pipeline = BoundedPipeline(lambda fid, x: x + 1, lambda fid, x: x * 2,
                               lambda fid, x: x + 3)
    receipts = pipeline.run([(i, i) for i in range(3)], list(range(3)),
                            validator=lambda fid, value: value == 2 * fid + 5,
                            result_consumer=lambda result: consumed.append(result.value),
                            retain_results=False)
    assert consumed == [5, 7, 9]
    assert [receipt.frame_id for receipt in receipts] == [0, 1, 2]
    assert all(receipt.value is None and receipt.correct for receipt in receipts)


def test_worker_callable_timeout_is_bounded_and_reported_without_claiming_kill():
    release = threading.Event()
    pipeline = BoundedPipeline(lambda fid, x: (release.wait(), x)[1],
                               lambda fid, x: x, lambda fid, x: x,
                               run_timeout_s=0.03, cleanup_timeout_s=0.03)
    started = time.perf_counter()
    with pytest.raises(Exception, match="workers did not stop"):
        pipeline.run([(1, 1)], [1])
    assert time.perf_counter() - started < 0.5
    release.set()
    for thread in pipeline._threads:
        thread.join(0.5)


def test_blocked_backend_cannot_deadlock_full_queues_and_poison_blocks_reuse():
    release_backend = threading.Event()

    def blocked_backend(frame_id, value):
        release_backend.wait()
        return value

    pipeline = BoundedPipeline(lambda fid, x: x, blocked_backend, lambda fid, x: x,
                               queue_capacity=1, run_timeout_s=0.15,
                               cleanup_timeout_s=0.03, max_in_flight=2)
    started = time.perf_counter()
    with pytest.raises(Exception, match="workers did not stop"):
        pipeline.run(((i, i) for i in range(100)), list(range(100)))
    assert time.perf_counter() - started < 0.8
    assert pipeline.queue_stats["in_flight_peak"] <= 2
    assert pipeline.queue_stats["in_flight_current"] == 0
    assert pipeline.threads_alive
    with pytest.raises(RuntimeError, match="poisoned"):
        pipeline.run([(0, 0)], [0])

    release_backend.set()
    for thread in pipeline._threads:
        thread.join(0.5)
    assert pipeline.threads_alive == ()
    result = pipeline.run([(0, 3)], [0])
    assert result[0].value == 3


@pytest.mark.parametrize("blocking_kind", ["iterator", "deepcopy"])
def test_blocking_producer_operations_obey_deadline_and_poison_until_they_return(blocking_kind):
    entered = threading.Event()
    release = threading.Event()

    class BlockingCopy(object):
        def __deepcopy__(self, memo):
            entered.set()
            release.wait()
            return "copied"

    def source():
        if blocking_kind == "iterator":
            yield 0, 1
            entered.set()
            release.wait()
            yield 1, 2
        else:
            yield 0, BlockingCopy()

    pipeline = BoundedPipeline(lambda fid, x: x, lambda fid, x: x, lambda fid, x: x,
                               run_timeout_s=0.08, cleanup_timeout_s=0.03)
    started = time.perf_counter()
    with pytest.raises(Exception, match="workers did not stop"):
        pipeline.run(source(), [0, 1] if blocking_kind == "iterator" else [0])
    assert entered.wait(0.2)
    assert time.perf_counter() - started < 0.6
    assert pipeline.threads_alive
    with pytest.raises(RuntimeError, match="poisoned"):
        pipeline.run([(0, 1)], [0])

    release.set()
    for thread in pipeline._threads:
        thread.join(0.5)
    assert pipeline.threads_alive == ()


def test_poison_is_set_before_run_lock_release_for_concurrent_reuse():
    release_worker = threading.Event()
    competing_result = []
    competing_done = threading.Event()

    class InterceptLock(object):
        def __init__(self):
            self.lock = threading.Lock()
            self.on_release = None

        def acquire(self, blocking=True):
            return self.lock.acquire(blocking)

        def release(self):
            self.lock.release()
            callback = self.on_release
            self.on_release = None
            if callback is not None:
                callback()

    pipeline = BoundedPipeline(lambda fid, x: (release_worker.wait(), x)[1],
                               lambda fid, x: x, lambda fid, x: x,
                               run_timeout_s=0.04, cleanup_timeout_s=0.02)
    lock = InterceptLock()
    pipeline._run_lock = lock

    def try_reuse():
        def competing_run():
            try:
                pipeline.run([(1, 1)], [1])
            except Exception as exc:
                competing_result.append(exc)
            finally:
                competing_done.set()
        contender = threading.Thread(target=competing_run)
        contender.start()
        assert competing_done.wait(0.5)
        contender.join(0.5)

    lock.on_release = try_reuse
    with pytest.raises(Exception, match="workers did not stop"):
        pipeline.run([(1, 1)], [1])
    assert len(competing_result) == 1
    assert isinstance(competing_result[0], RuntimeError)
    assert "poisoned" in str(competing_result[0])
    release_worker.set()
    for thread in pipeline._threads:
        thread.join(0.5)


@pytest.mark.parametrize("limit", [2, 3])
def test_global_in_flight_limit_bounds_admissions_and_preserves_completion_fifo(limit):
    completed = []
    pipeline = BoundedPipeline(lambda fid, x: x, lambda fid, x: x,
                               lambda fid, x: (time.sleep(0.01) or x),
                               queue_capacity=4, max_in_flight=limit)
    results = pipeline.run(
        [(i, i) for i in range(12)], list(range(12)),
        result_consumer=lambda result: completed.append(result.frame_id))

    assert [result.frame_id for result in results] == list(range(12))
    assert completed == list(range(12))
    assert pipeline.queue_stats["in_flight_peak"] == limit
    assert pipeline.queue_stats["in_flight_peak"] <= pipeline.queue_stats["max_in_flight"]
    assert pipeline.queue_stats["in_flight_current"] == 0


def test_global_in_flight_permit_wait_is_counted_as_submit_backpressure():
    release_consumer = threading.Event()
    first_consumer_started = threading.Event()

    def consume(result):
        if result.frame_id == 0:
            first_consumer_started.set()
            release_consumer.wait(0.15)

    pipeline = BoundedPipeline(lambda fid, x: x, lambda fid, x: x, lambda fid, x: x,
                               queue_capacity=4, max_in_flight=1)
    release_thread = threading.Thread(
        target=lambda: (first_consumer_started.wait(0.5), time.sleep(0.06), release_consumer.set()))
    release_thread.start()
    results = pipeline.run([(0, 0), (1, 1)], [0, 1], result_consumer=consume)
    release_thread.join(0.5)

    assert [result.frame_id for result in results] == [0, 1]
    assert pipeline.queue_stats["in_flight_peak"] == 1
    assert pipeline.queue_stats["submit_wait_ms"] >= 30.0
    assert results[1].submit_ms - results[0].submit_ms >= 30.0
    assert results[1].admission_wait_ms >= 30.0
    assert results[1].end_to_end_ms >= results[1].admission_wait_ms
    assert pipeline.queue_stats["in_flight_current"] == 0


def test_in_flight_wait_and_deepcopy_remain_visible_in_per_item_end_to_end_timing():
    release_consumer = threading.Event()
    first_consumer_started = threading.Event()

    class SlowCopy(object):
        def __deepcopy__(self, memo):
            time.sleep(0.05)
            return 1

    def consume(result):
        if result.frame_id == 0:
            first_consumer_started.set()
            release_consumer.wait(0.2)

    def release_later():
        assert first_consumer_started.wait(0.5)
        time.sleep(0.06)
        release_consumer.set()

    pipeline = BoundedPipeline(lambda fid, x: x, lambda fid, x: x, lambda fid, x: x,
                               queue_capacity=4, max_in_flight=1)
    release_thread = threading.Thread(target=release_later)
    release_thread.start()
    results = pipeline.run([(0, 0), (1, SlowCopy())], [0, 1], result_consumer=consume)
    release_thread.join(0.5)

    second = results[1]
    assert second.admission_wait_ms >= 50.0
    assert second.end_to_end_ms >= second.admission_wait_ms
    assert second.complete_ms - second.submit_ms < 50.0
    assert second.submit_ms >= second.admission_start_ms + second.admission_wait_ms


def test_schema_records_per_item_admission_and_end_to_end_timings():
    pipeline = BoundedPipeline(lambda fid, x: x, lambda fid, x: x, lambda fid, x: x,
                               max_in_flight=1)
    results = pipeline.run([(7, 9)], [7], validator=lambda fid, value: True)
    summary = pipeline.schema_v1_summary(
        results, stage="cpu-only", execution="simulation", model_sha256="a" * 64,
        boundary="submit-to-output", threads={"host": 1}, cpu_frequency_khz=[1000],
        profile=False, warmup_count=0, identity={},
        input_sha256={7: "b" * 64}, feature_sha256={7: "c" * 64})

    record = summary["records"][0]
    assert record["admission_start_ms"] <= record["submit_ms"]
    assert record["admission_wait_ms"] == pytest.approx(
        record["submit_ms"] - record["admission_start_ms"])
    assert record["end_to_end_ms"] == pytest.approx(
        record["complete_ms"] - record["admission_start_ms"])


def test_global_in_flight_permits_release_after_early_stage_failure():
    def backend(frame_id, value):
        if frame_id == 2:
            raise LookupError("early backend failure")
        return value

    pipeline = BoundedPipeline(lambda fid, x: x, backend, lambda fid, x: x,
                               queue_capacity=4, max_in_flight=2,
                               cleanup_timeout_s=0.2)
    with pytest.raises(PipelineStageError, match="early backend failure"):
        pipeline.run([(i, i) for i in range(20)], list(range(20)))

    assert pipeline.queue_stats["in_flight_peak"] <= 2
    assert pipeline.queue_stats["in_flight_current"] == 0
    assert pipeline.threads_alive == ()


@pytest.mark.parametrize("failure_stage", ["validator", "consumer"])
def test_global_in_flight_permits_release_after_completion_callback_failure(failure_stage):
    def fail(frame_id, value):
        if frame_id == 0:
            raise LookupError("%s failed" % failure_stage)
        return True

    pipeline = BoundedPipeline(lambda fid, x: x, lambda fid, x: x, lambda fid, x: x,
                               queue_capacity=4, max_in_flight=2,
                               cleanup_timeout_s=0.2)
    with pytest.raises(PipelineStageError, match="%s failed" % failure_stage):
        if failure_stage == "validator":
            pipeline.run([(i, i) for i in range(20)], list(range(20)), validator=fail)
        else:
            pipeline.run([(i, i) for i in range(20)], list(range(20)),
                         result_consumer=lambda result: fail(result.frame_id, result.value))

    assert pipeline.queue_stats["in_flight_peak"] <= 2
    assert pipeline.queue_stats["in_flight_current"] == 0
    assert pipeline.threads_alive == ()


def test_normal_drain_uses_run_deadline_not_short_failure_cleanup_timeout():
    pipeline = BoundedPipeline(lambda fid, x: x, lambda fid, x: x,
                               lambda fid, x: (time.sleep(0.08) or x),
                               run_timeout_s=2.0, cleanup_timeout_s=0.03)
    results = pipeline.run([(i, i) for i in range(8)], list(range(8)))
    assert len(results) == 8


def test_stage_error_shortens_an_already_started_normal_join_to_cleanup_window():
    producer_finished = threading.Event()
    release_backend = threading.Event()

    def source():
        for frame_id in range(12):
            yield frame_id, frame_id
        producer_finished.set()

    def prefix(frame_id, value):
        if frame_id == 3:
            assert producer_finished.wait(0.5)
            raise LookupError("late prefix failure")
        return value

    def backend(frame_id, value):
        if frame_id == 0:
            release_backend.wait()
        return value

    pipeline = BoundedPipeline(prefix, backend, lambda fid, x: x,
                               queue_capacity=16, run_timeout_s=0.8,
                               cleanup_timeout_s=0.05)
    started = time.perf_counter()
    with pytest.raises(Exception, match="workers did not stop"):
        pipeline.run(source(), list(range(12)))
    elapsed = time.perf_counter() - started
    assert producer_finished.is_set()
    assert elapsed < 0.4
    release_backend.set()
    for thread in pipeline._threads:
        thread.join(0.5)


def test_validator_and_consumer_time_are_explicitly_in_completion_timing():
    pipeline = BoundedPipeline(lambda fid, x: x, lambda fid, x: x, lambda fid, x: x)
    results = pipeline.run(
        [(1, 1)], [1],
        validator=lambda fid, value: (time.sleep(0.02) or True),
        result_consumer=lambda result: time.sleep(0.02))
    assert results[0].postprocess_ms >= 35
    summary = pipeline.schema_v1_summary(
        results, stage="cpu-only", execution="simulation", model_sha256="a" * 64,
        boundary="submit-to-output", threads={"host": 1}, cpu_frequency_khz=[1000],
        profile=False, warmup_count=0, identity={"runtime": "test"},
        input_sha256={1: "b" * 64}, feature_sha256={1: "c" * 64})
    assert summary["postprocess_timing"] == {
        "included_in_complete_ms": True,
        "validator_enabled": True,
        "consumer_enabled": True,
    }
    assert summary["records"][0]["postprocess_ms"] >= 35


def test_schema_rejects_missing_results_for_the_completed_run():
    pipeline = BoundedPipeline(lambda fid, x: x, lambda fid, x: x, lambda fid, x: x)
    results = pipeline.run([(1, 1), (2, 2)], [1, 2], validator=lambda fid, value: True)
    with pytest.raises(ValueError, match="expected frame IDs"):
        pipeline.schema_v1_summary(
            results[:1], stage="cpu-only", execution="simulation", model_sha256="a" * 64,
            boundary="submit-to-output", threads={"host": 1}, cpu_frequency_khz=[],
            profile=False, warmup_count=0, identity={},
            input_sha256={1: "b" * 64, 2: "b" * 64},
            feature_sha256={1: "c" * 64, 2: "c" * 64})
