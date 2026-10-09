"""Scheduler contracts for a whole-region PL call; no hardware claims."""
import pathlib
import sys
import unittest

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent), str(HERE)]
from test_cnn_pipeline_v10_paired_runtime import (
    FakeTransport, MANIFEST_SHA, clients, contract, image)
from cnn_pipeline_v10_live_runtime import V10LiveRuntime


class ChainRuntime(V10LiveRuntime):
    PIPELINE_STAGES = (
        ('PS', 'stem-prefix'), ('PL', 'n0-n1-n2'),
        ('PS', 'network3-bridge'), ('PL', 1), ('PS', 'suffix'),
    )

    def _run_pl_stage(self, key, left, right):
        if key != 'n0-n1-n2':
            return super(ChainRuntime, self)._run_pl_stage(key, left, right)
        # A mock whole-region call changes shape without a PS N1 invocation.
        outputs = [np.full((1, 128, 32, 32), value.flat[0], dtype='<f4')
                   for value in (left, right)]
        return outputs[0], outputs[1], {
            'profiles': [2, 3, 0], 'timing': {'pl_window_wall_ms': 0.0}}


class StagePlanTests(unittest.TestCase):
    def test_whole_region_plan_skips_ps_bridge_and_preserves_odd_tail(self):
        owned = clients()
        runtime = ChainRuntime(FakeTransport(), contract(), MANIFEST_SHA, owned)
        try:
            results = runtime.run(((i, image(i + 1)) for i in range(7)))
            self.assertEqual([value['frame_id'] for value in results], list(range(7)))
            for i, value in enumerate(results):
                np.testing.assert_array_equal(value['features'], np.full(512, i + 1))
            self.assertTrue(results[-1]['shadow_partner_used'])
            self.assertEqual(owned['network1-bridge'].calls, 0)
            summary = runtime.last_run_summary
            self.assertEqual(summary['status'], 'COMPLETED')
            self.assertEqual(summary['pipeline_stages'], list(ChainRuntime.PIPELINE_STAGES))
            for timing in summary['pair_timings']:
                self.assertEqual(len(timing['pl_events']), 2)
                self.assertEqual(timing['pl_events'][0]['profiles'], [2, 3, 0])
                self.assertNotIn('network1-bridge',
                                 [e['partition'] for e in timing['ps_events']])
        finally:
            runtime.close()
        self.assertTrue(all(client.closed for client in owned.values()))

    def test_unknown_pl_stage_is_rejected_and_workers_drain(self):
        class Unimplemented(ChainRuntime):
            _run_pl_stage = V10LiveRuntime._run_pl_stage
        runtime = Unimplemented(FakeTransport(), contract(), MANIFEST_SHA, clients())
        try:
            with self.assertRaisesRegex(ValueError, 'PL stage'):
                runtime.run([(0, image(1))])
            self.assertEqual(runtime.last_run_summary['status'], 'FAILED_DRAINED')
            self.assertTrue(runtime.last_run_summary['workers_drained'])
        finally:
            runtime.close()

    def test_bad_plan_rejected_before_transport_allocation(self):
        class BadPlan(V10LiveRuntime):
            PIPELINE_STAGES = (('PL', 2), ('PS', 'suffix'))
        transport = FakeTransport()
        with self.assertRaisesRegex(ValueError, 'pipeline'):
            BadPlan(transport, contract(), MANIFEST_SHA, clients())
        self.assertEqual(transport.allocations, {})


if __name__ == '__main__':
    unittest.main()
