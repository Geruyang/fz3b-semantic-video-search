"""Bounded, ordered result delivery alongside the PS/PL compute owners.

The producer transfers an independently owned result to submit(). It must not
mutate that result afterward. The callback executes on one delivery thread and
must return; close() drains accepted results before reporting any failure.
"""
import queue
import threading
import time


class V10ResultDelivery(object):
    def __init__(self, emit, capacity=4):
        if not callable(emit) or type(capacity) is not int or capacity < 1:
            raise ValueError('delivery requires a callback and positive capacity')
        self._emit = emit
        self._queue = queue.Queue(maxsize=capacity)
        self._producer_lock = threading.Lock()
        self._closing = threading.Event()
        self._wake = object()
        self._error = None
        self._submitted = self._delivered = 0
        self._queue_high_water = 0
        self._submit_wait_ms = self._emit_ms = self._submit_to_emit_ms = 0.0
        self._max_submit_to_emit_ms = 0.0
        self._thread = threading.Thread(target=self._consume, name='v10-result-delivery')
        self._thread.start()

    def _check_error(self):
        if self._error is not None:
            raise RuntimeError('result delivery failed') from self._error

    def submit(self, result):
        started = time.perf_counter()
        with self._producer_lock:
            if self._closing.is_set():
                raise RuntimeError('result delivery is closed')
            while True:
                self._check_error()
                try:
                    self._queue.put((started, result), timeout=.02)
                    break
                except queue.Full:
                    continue
            self._submitted += 1
            self._queue_high_water = max(self._queue_high_water, self._queue.qsize())
            self._submit_wait_ms += (time.perf_counter()-started)*1000
            self._check_error()

    def _consume(self):
        try:
            while True:
                try:
                    item = self._queue.get(timeout=.02)
                except queue.Empty:
                    if self._closing.is_set():
                        return
                    continue
                if item is self._wake:
                    return
                requested, result = item
                started = time.perf_counter()
                # Includes backpressure before queue acceptance as well as
                # queue residence. Do not add this to producer_wait_ms.
                latency_ms = (started-requested)*1000
                self._submit_to_emit_ms += latency_ms
                self._max_submit_to_emit_ms = max(self._max_submit_to_emit_ms, latency_ms)
                self._emit(result)
                self._emit_ms += (time.perf_counter()-started)*1000
                self._delivered += 1
                if self._closing.is_set() and self._queue.empty():
                    return
        except BaseException as error:
            self._error = error

    def close(self):
        with self._producer_lock:
            self._closing.set()
            if self._thread.is_alive():
                try:
                    self._queue.put_nowait(self._wake)
                except queue.Full:
                    pass  # Consumer sees closing after draining the full queue.
        self._thread.join()
        # Drop undelivered references after a callback failure. The counts and
        # exception make the failed delivery explicit; it is never a success.
        while not self._queue.empty():
            self._queue.get_nowait()
        self._check_error()
        return self.summary()

    def summary(self):
        return dict(submitted=self._submitted, delivered=self._delivered,
                    status='FAILED' if self._error is not None else (
                        'DRAINED' if self._closing.is_set() and not self._thread.is_alive() else 'RUNNING'),
                    queue_capacity=self._queue.maxsize, queue_high_water=self._queue_high_water,
                    producer_wait_ms=self._submit_wait_ms, emit_ms=self._emit_ms,
                    submit_to_emit_start_sum_ms=self._submit_to_emit_ms,
                    submit_to_emit_start_max_ms=self._max_submit_to_emit_ms)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            self.close()
        except BaseException:
            if exc_type is None:
                raise
        return False
