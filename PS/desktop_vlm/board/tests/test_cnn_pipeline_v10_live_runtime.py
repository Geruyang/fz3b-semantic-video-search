import importlib.util
import pathlib
import sys
import threading
import unittest
from unittest import mock

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent), str(HERE)]
from test_cnn_pipeline_v10_paired_runtime import (
    FakeClient, FakeTransport, MANIFEST_SHA, clients, contract, image)
from cnn_pipeline_v10_stream_runtime import V10StreamRuntime

if importlib.util.find_spec('cnn_pipeline_v10_live_runtime') is not None:
    from cnn_pipeline_v10_live_runtime import V10LiveRuntime
else:
    V10LiveRuntime = V10StreamRuntime


def runtime(cls=V10LiveRuntime, owned=None):
    return cls(FakeTransport(), contract(), MANIFEST_SHA, owned or clients())


class LiveTests(unittest.TestCase):
    def test_validated_client_owns_finite_scan_and_rejects_bad_tensors(self):
        class ValidatingClient(FakeClient):
            validates_tensor_finiteness = True
            inject_nonfinite = False
            def infer(self, tensors):
                if not np.isfinite(tensors[0]).all():
                    raise ValueError('client rejected nonfinite input')
                outputs, ms = super(ValidatingClient, self).infer(tensors)
                if self.inject_nonfinite:
                    next(iter(outputs.values())).flat[0] = np.nan
                if not all(np.isfinite(value).all() for value in outputs.values()):
                    raise ValueError('client rejected nonfinite output')
                return outputs, ms
        owned = clients()
        owned['stem-prefix'] = client = ValidatingClient('stem-prefix')
        instance = runtime(owned=owned)
        try:
            with mock.patch.object(instance, '_finite', side_effect=AssertionError('duplicate scan')):
                result, event = instance._client_timed('stem-prefix', image(1))
                self.assertEqual(result.shape, (1, 64, 64, 64))
                self.assertEqual(event['finite_validation_owner'], 'client')
                invalid = image(1)
                invalid.flat[0] = np.nan
                with self.assertRaisesRegex(ValueError, 'nonfinite input'):
                    instance._client_timed('stem-prefix', invalid)
                client.inject_nonfinite = True
                with self.assertRaisesRegex(ValueError, 'nonfinite output'):
                    instance._client_timed('stem-prefix', image(1))
                with self.assertRaisesRegex(ValueError, 'shape mismatch'):
                    instance._client_timed('stem-prefix', image(1)[:, :, :1, :1])
        finally:
            instance.close()

    def test_first_result_precedes_source_exhaustion_with_bounded_admission(self):
        instance = runtime()
        pulled = []
        def source():
            for i in range(20):
                pulled.append(i)
                yield i, image(i + 1)
        try:
            self.assertTrue(callable(getattr(instance, 'iter_results', None)),
                            'live output API has not been implemented')
            with instance.iter_results(source(), max_in_flight=3) as stream:
                first = next(stream)
                self.assertEqual(first['frame_id'], 0)
                self.assertLessEqual(len(pulled), 6)
                self.assertLess(len(pulled), 20)
                result = [first] + list(stream)
            self.assertEqual([r['frame_id'] for r in result], list(range(20)))
            self.assertTrue(instance.last_run_summary['workers_drained'])
            self.assertLessEqual(instance.last_run_summary['peak_in_flight_pairs'], 3)
            self.assertEqual(instance.last_run_summary['emitted_frame_count'], 20)
            self.assertEqual(instance.last_run_summary['status'], 'COMPLETED')
        finally:
            instance.close()

    def test_order_odd_tail_and_run_compatibility(self):
        baseline, candidate = runtime(V10StreamRuntime), runtime()
        items = [(i + 20, image(i + 1)) for i in range(7)]
        try:
            expected = baseline.run(items, max_in_flight=2)
            actual = candidate.run(items, max_in_flight=2)
            for left, right in zip(actual, expected):
                self.assertEqual(left['frame_id'], right['frame_id'])
                self.assertEqual(left['shadow_partner_used'], right['shadow_partner_used'])
                np.testing.assert_array_equal(left['features'], right['features'])
            self.assertEqual(len(actual), 7)
            self.assertEqual(len(candidate.last_run_summary['pair_timings']), 4)
            self.assertEqual(candidate.last_run_summary['real_frame_count'], 7)
            self.assertFalse(candidate.last_run_summary['shadow_counts_as_real_throughput'])
        finally:
            baseline.close()
            candidate.close()

    def test_cancel_drains_active_pl_before_terminal_close(self):
        class BlockLaterPL(V10LiveRuntime):
            def __init__(self, *args, **kwargs):
                super(BlockLaterPL, self).__init__(*args, **kwargs)
                self.first_n4_done = False
                self.active = threading.Event()
                self.release = threading.Event()
                self.returned = threading.Event()
                self.pl_spans = []

            def _pl_pair(self, context, stage, origin):
                if self.first_n4_done:
                    self.active.set()
                    if not self.release.wait(5):
                        raise AssertionError('test did not release active PL')
                    result = super(BlockLaterPL, self)._pl_pair(context, stage, origin)
                    self.pl_spans.append(result[-1])
                    self.returned.set()
                    return result
                result = super(BlockLaterPL, self)._pl_pair(context, stage, origin)
                self.pl_spans.append(result[-1])
                if context['index'] == 0 and stage == 5:
                    self.first_n4_done = True
                return result

        instance = runtime(BlockLaterPL)
        stream = instance.iter_results([(i, image(i + 1)) for i in range(8)])
        closed = threading.Event()
        failures = []
        def cancel():
            try:
                stream.close()
            except BaseException as error:
                failures.append(error)
            finally:
                closed.set()
        try:
            next(stream)
            self.assertTrue(instance.active.wait(5))
            thread = threading.Thread(target=cancel)
            thread.start()
            self.assertFalse(closed.wait(.03))
            instance.release.set()
            thread.join(5)
            self.assertFalse(failures)
            self.assertTrue(instance.returned.is_set())
            self.assertTrue(closed.is_set())
            self.assertEqual(instance.last_run_summary['status'], 'CANCELLED_DRAINED')
            self.assertTrue(instance.last_run_summary['workers_drained'])
            self.assertAlmostEqual(instance.last_run_summary['pl_worker_busy_ms'],
                sum(s['end_ms']-s['start_ms'] for s in instance.pl_spans), places=6)
            with self.assertRaisesRegex(RuntimeError, 'close is required'):
                instance.run([])
        finally:
            instance.release.set()
            stream.close()
            self.assertTrue(instance.close()['quiesce_confirmed'])

    def test_consumer_error_cancels_and_releases_execution_lock(self):
        instance = runtime()
        try:
            with self.assertRaisesRegex(ValueError, 'consumer'):
                with instance.iter_results([(i, image(i + 1)) for i in range(8)]) as stream:
                    next(stream)
                    raise ValueError('consumer failed')
            self.assertEqual(instance.last_run_summary['status'], 'CANCELLED_DRAINED')
            self.assertTrue(instance.last_run_summary['workers_drained'])
            self.assertEqual(instance.last_run_summary['emitted_frame_count'], 1)
        finally:
            instance.close()

    def test_failure_from_call_draining_during_cancel_is_reported(self):
        class FailLaterPL(V10LiveRuntime):
            def __init__(self, *args, **kwargs):
                super(FailLaterPL, self).__init__(*args, **kwargs)
                self.first_n4_done = False
                self.entered = threading.Event()
                self.release = threading.Event()

            def _pl_pair(self, context, stage, origin):
                if self.first_n4_done:
                    self.entered.set()
                    self.release.wait(5)
                    raise ValueError('late hardware failure')
                result = super(FailLaterPL, self)._pl_pair(context, stage, origin)
                if context['index'] == 0 and stage == 5:
                    self.first_n4_done = True
                return result
        instance = runtime(FailLaterPL)
        stream = instance.iter_results([(i, image(i+1)) for i in range(8)])
        try:
            next(stream)
            self.assertTrue(instance.entered.wait(5))
            instance.release.set()
            with self.assertRaisesRegex(RuntimeError, 'draining'):
                stream.close()
            self.assertEqual(instance.last_run_summary['status'], 'FAILED_DRAINED')
            self.assertIn('late hardware failure',
                          instance.last_run_summary['drained_call_errors'][0]['error'])
        finally:
            instance.release.set()
            stream.close()
            instance.close()

    def test_live_lifetime_input_client_and_consumer_mutation(self):
        class Reuse(FakeClient):
            def infer(self, tensors):
                outputs, elapsed = super(Reuse, self).infer(tensors)
                key = next(iter(outputs))
                if not hasattr(self, 'buffer'):
                    self.buffer = outputs[key]
                else:
                    np.copyto(self.buffer, outputs[key])
                return {key: self.buffer}, elapsed
        instance = runtime(owned={n: Reuse(n) for n in FakeClient.SHAPES})
        buffer = image(0)
        def source():
            for i in range(10):
                buffer.fill(i + 1)
                yield i, buffer
        try:
            with instance.iter_results(source(), max_in_flight=2) as stream:
                first = next(stream)
                self.assertEqual(float(first['features'][0]), 1)
                first['features'].fill(-999)
                first['pair_timing']['frame_ids'][0] = -999
                first['pl_completions'].clear()
                remainder = list(stream)
            self.assertEqual([float(r['features'][0]) for r in remainder], list(range(2, 11)))
            self.assertEqual(remainder[0]['pair_timing']['frame_ids'], [0, 1])
            self.assertEqual(len(remainder[0]['pl_completions']), 3)
            self.assertTrue(np.all(first['features'] == -999))
        finally:
            instance.close()

    def test_reservation_unstarted_close_and_closed_rejection(self):
        instance = runtime()
        stream = instance.iter_results([])
        try:
            with self.assertRaisesRegex(RuntimeError, 'running'):
                instance.iter_results([])
            with self.assertRaisesRegex(RuntimeError, 'active'):
                instance.close()
            stream.close()
            self.assertEqual(instance.run([]), [])
            for cap in (0, 5, True, 1.0):
                with self.assertRaises(ValueError):
                    instance.iter_results([], max_in_flight=cap)
        finally:
            stream.close()
            instance.close()
        with self.assertRaisesRegex(RuntimeError, 'closed'):
            instance.iter_results([])

    def test_source_error_is_drained_and_ids_are_monotonic(self):
        for mode in ('producer', 'ids'):
            instance = runtime()
            def source():
                yield 2, image(1)
                if mode == 'producer':
                    raise ValueError('capture failed')
                yield 1, image(2)
            try:
                with self.assertRaises(ValueError):
                    with instance.iter_results(source()) as stream:
                        list(stream)
                self.assertEqual(instance.last_run_summary['status'], 'FAILED_DRAINED')
                self.assertTrue(instance.last_run_summary['workers_drained'])
            finally:
                instance.close()

    def test_default_stream_does_not_retain_full_histories(self):
        instance = runtime()
        try:
            with instance.iter_results([(i, image(i + 1)) for i in range(12)]) as stream:
                result = list(stream)
            summary = instance.last_run_summary
            self.assertEqual(summary['pair_timings'], [])
            self.assertEqual(summary['timeline'], [])
            self.assertEqual(summary['pair_count'], 6)
            self.assertEqual(len(result), 12)
            self.assertGreater(summary['ps_worker_busy_ms'], 0)
        finally:
            instance.close()


if __name__ == '__main__':
    unittest.main()
