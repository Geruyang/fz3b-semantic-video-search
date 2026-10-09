import pathlib
import sys
import threading
import unittest

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent), str(HERE)]
from cnn_pipeline_v10_stream_runtime import V10StreamRuntime
from cnn_pipeline_v10_paired_runtime import V10PairedNormalRuntime
from test_cnn_pipeline_v10_paired_runtime import (
    FakeClient, FakeTransport, MANIFEST_SHA, clients, contract, image)


def runtime(cls=V10StreamRuntime):
    return cls(FakeTransport(), contract(), MANIFEST_SHA, clients())


class OverlapRuntime(V10StreamRuntime):
    """Handshake proves cross-pair overlap rather than relying on wall time."""
    def __init__(self, *args, **kwargs):
        super(OverlapRuntime, self).__init__(*args, **kwargs)
        self.pl_entered = threading.Event()
        self.next_ps_entered = threading.Event()
        self.pl_finished = threading.Event()
        self.stem_calls = 0
        self.pl_calls = 0
        self.pl_active = False
        self.fail_ps = False
        self.overlap_proven = False

    def _client_timed(self, name, value):
        if name == 'stem-prefix':
            self.stem_calls += 1
            if self.stem_calls == 3:
                if not self.pl_entered.wait(5):
                    raise AssertionError('PL did not start while second pair PS was ready')
                self.overlap_proven = self.pl_active
                self.next_ps_entered.set()
                if self.fail_ps:
                    raise ValueError('injected PS failure')
        return super(OverlapRuntime, self)._client_timed(name, value)

    def _run_profile(self, profile, left, right):
        if self.pl_active:
            raise AssertionError('two PL calls overlapped on one arena')
        self.pl_active = True
        self.pl_calls += 1
        try:
            if self.pl_calls == 1:
                self.pl_entered.set()
                if not self.next_ps_entered.wait(5):
                    raise AssertionError('PS could not run while PL task was active')
            return super(OverlapRuntime, self)._run_profile(profile, left, right)
        finally:
            self.pl_active = False
            self.pl_finished.set()


class StreamTests(unittest.TestCase):
    def test_generator_reusing_input_buffer_is_snapshotted_before_next_yield(self):
        instance = runtime()
        buffer = image(0)
        def items():
            for i in range(4):
                buffer.fill(i+1)
                yield i, buffer
        try:
            result = instance.run(items(), max_in_flight=2)
            self.assertEqual([float(r['features'][0]) for r in result], [1, 2, 3, 4])
        finally:
            instance.close()

    def test_pl_completion_error_requires_terminal_close(self):
        class FaultTransport(FakeTransport):
            def wait_complete(self, profile, timeout_s):
                raise RuntimeError('injected completion failure')
        transport = FaultTransport()
        instance = V10StreamRuntime(transport, contract(), MANIFEST_SHA, clients())
        try:
            with self.assertRaisesRegex(RuntimeError, 'completion failure'):
                instance.run([(i, image(i+1)) for i in range(4)], max_in_flight=2)
            self.assertFalse(transport.closed)
            self.assertTrue(instance.last_run_summary['workers_drained'])
            with self.assertRaisesRegex(RuntimeError, 'close is required'):
                instance.run([])
        finally:
            self.assertTrue(instance.close()['quiesce_confirmed'])

    def test_generator_failure_stops_admission_and_drains_workers(self):
        instance = runtime()
        def items():
            for i in range(4):
                yield i, image(i+1)
            raise ValueError('capture producer failed')
        try:
            with self.assertRaisesRegex(ValueError, 'capture producer failed'):
                instance.run(items(), max_in_flight=2)
            self.assertTrue(instance.last_run_summary['workers_drained'])
            self.assertGreaterEqual(instance.last_run_summary['completed_pair_count'], 1)
        finally:
            instance.close()

    def test_ps_client_reused_output_cannot_alias_a_and_b_or_later_pairs(self):
        class ReuseClient(FakeClient):
            def infer(self, tensors):
                result, elapsed = super(ReuseClient, self).infer(tensors)
                key = next(iter(result))
                if not hasattr(self, 'buffer'):
                    self.buffer = result[key]
                else:
                    np.copyto(self.buffer, result[key])
                return {key: self.buffer}, elapsed
        owned = {name: ReuseClient(name) for name in FakeClient.SHAPES}
        instance = V10StreamRuntime(FakeTransport(), contract(), MANIFEST_SHA, owned)
        try:
            result = instance.run([(i, image(i+1)) for i in range(6)], max_in_flight=3)
            self.assertEqual([float(r['features'][0]) for r in result], [1, 2, 3, 4, 5, 6])
        finally:
            instance.close()

    def test_order_and_exact_features_equal_serial_with_odd_tail(self):
        serial, streamed = runtime(V10PairedNormalRuntime), runtime()
        items = [(i+40, image(float(i+1))) for i in range(7)]
        try:
            expected = serial.run(items)
            actual = streamed.run(iter(items), max_in_flight=2)
            self.assertEqual([r['frame_id'] for r in actual], [r['frame_id'] for r in expected])
            for a, b in zip(actual, expected):
                np.testing.assert_array_equal(a['features'], b['features'])
                self.assertEqual(a['paired_with'], b['paired_with'])
                self.assertEqual(a['shadow_partner_used'], b['shadow_partner_used'])
                self.assertEqual([c['profile'] for c in a['pl_completions']], [2, 0, 1])
            self.assertEqual(streamed.last_run_summary['real_frame_count'], 7)
            self.assertFalse(streamed.last_run_summary['shadow_counts_as_real_throughput'])
            self.assertLessEqual(streamed.last_run_summary['peak_in_flight_pairs'], 2)
            self.assertEqual(len(streamed.transport.submits), 12)
        finally:
            serial.close()
            streamed.close()

    def test_real_cross_pair_overlap_single_pl_owner_and_bounded_admission(self):
        instance = runtime(OverlapRuntime)
        yielded = []
        def items():
            for i in range(8):
                # Admission of third pair must wait for some suffix work.
                if i == 4:
                    self.assertGreater(instance.clients['suffix'].calls, 0)
                yielded.append(i)
                yield i, image(float(i+1))
        try:
            result = instance.run(items(), max_in_flight=2)
            self.assertTrue(instance.overlap_proven)
            self.assertEqual(len(result), 8)
            self.assertEqual(yielded, list(range(8)))
            spans = sorted((s for s in instance.last_run_summary['timeline'] if s['owner']=='PL'),
                           key=lambda s: s['start_ms'])
            self.assertTrue(all(a['end_ms'] <= b['start_ms'] for a, b in zip(spans, spans[1:])))
        finally:
            instance.close()

    def test_failure_drains_active_pl_before_caller_can_close(self):
        instance = runtime(OverlapRuntime)
        instance.fail_ps = True
        try:
            with self.assertRaisesRegex(ValueError, 'injected PS failure'):
                instance.run([(i, image(i+1)) for i in range(4)], max_in_flight=2)
            self.assertTrue(instance.pl_finished.is_set())
            self.assertFalse(instance.pl_active)
            self.assertEqual(instance.last_run_summary['status'], 'FAILED_DRAINED')
            self.assertTrue(instance.last_run_summary['workers_drained'])
        finally:
            self.assertTrue(instance.close()['quiesce_confirmed'])

    def test_empty_single_repeated_runs_duplicate_and_closed(self):
        instance = runtime()
        try:
            self.assertEqual(instance.run([]), [])
            result = instance.run_one(8, image(3))
            self.assertTrue(result['shadow_partner_used'])
            self.assertEqual(instance.last_run_summary['real_frame_count'], 1)
            for cap in (0, 5, True, 1.0):
                with self.assertRaises(ValueError):
                    instance.run([], max_in_flight=cap)
            with self.assertRaisesRegex(ValueError, 'unique'):
                instance.run([(1, image(1)), (1, image(2))])
            instance._execution_lock.acquire()
            try:
                with self.assertRaises(RuntimeError):
                    instance.close()
                with self.assertRaises(RuntimeError):
                    instance.run([])
            finally:
                instance._execution_lock.release()
        finally:
            instance.close()
        with self.assertRaises(RuntimeError):
            instance.run([])


if __name__ == '__main__':
    unittest.main()
