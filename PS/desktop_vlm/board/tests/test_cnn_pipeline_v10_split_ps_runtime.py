import pathlib
import sys
import threading
import time
import unittest

import numpy as np


HERE = pathlib.Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent), str(HERE)]

from test_cnn_pipeline_v10_paired_runtime import (
    FakeClient, FakeTransport, MANIFEST_SHA, clients, contract, image)
from cnn_pipeline_v10_live_runtime import V10LiveRuntime
from cnn_pipeline_v10_mixed_runtime import V10MixedBoundaryMixin
from cnn_pipeline_v10_p3_dma_runtime import V10P3DmaChainMixin
from cnn_pipeline_v10_split_ps_runtime import V10SplitPsLiveRuntime
from test_cnn_pipeline_v10_p3_dma_runtime import (
    A0004ChainTransport, PARAM_ROOT, PARAM_SHA)
from cnn_pipeline_v10_p3_dma_parameters import load_v10_p3_dma_parameters


def runtime(cls=V10SplitPsLiveRuntime, owned=None):
    return cls(FakeTransport(), contract(), MANIFEST_SHA, owned or clients())


class _OverlapProbe(object):
    def __init__(self, fail_suffix=False):
        self.lock = threading.Lock()
        self.active = {"PS_FRONT": 0, "PS_SUFFIX": 0}
        self.per_client = {}
        self.overlap = threading.Event()
        self.suffix_active = threading.Event()
        self.front_during_suffix = threading.Event()
        self.fail_suffix = fail_suffix

    def enter(self, name):
        owner = "PS_SUFFIX" if name == "suffix" else "PS_FRONT"
        with self.lock:
            if self.per_client.get(name, 0):
                raise AssertionError("client %s was re-entered" % name)
            self.per_client[name] = 1
            self.active[owner] += 1
            if self.active["PS_FRONT"] and self.active["PS_SUFFIX"]:
                self.overlap.set()
            if owner == "PS_SUFFIX":
                self.suffix_active.set()
            elif self.suffix_active.is_set():
                self.front_during_suffix.set()
        if owner == "PS_SUFFIX":
            if not self.front_during_suffix.wait(2.0):
                raise AssertionError("suffix never overlapped a front call")
        else:
            time.sleep(0.01)
        return owner

    def leave(self, name, owner):
        with self.lock:
            self.per_client[name] = 0
            self.active[owner] -= 1


class _ProbeClient(FakeClient):
    def __init__(self, name, probe):
        super(_ProbeClient, self).__init__(name)
        self.probe = probe

    def infer(self, tensors):
        owner = self.probe.enter(self.name)
        try:
            if owner == "PS_SUFFIX" and self.probe.fail_suffix:
                raise ValueError("suffix probe failure")
            return super(_ProbeClient, self).infer(tensors)
        finally:
            self.probe.leave(self.name, owner)


class SplitPsRuntimeTests(unittest.TestCase):
    def test_actual_a0004_mro_keeps_direct_upload_and_profile_order(self):
        class Candidate(V10P3DmaChainMixin,
                        V10MixedBoundaryMixin,
                        V10SplitPsLiveRuntime):
            pass

        parameters = load_v10_p3_dma_parameters(
            PARAM_ROOT / "manifest.json", PARAM_SHA)
        transport = A0004ChainTransport()
        instance = Candidate(
            transport, contract(), MANIFEST_SHA, clients(),
            p3_dma_parameters=parameters, mixed_native_lib=None)
        try:
            result = instance.run(
                [(index, image(index + 1)) for index in range(8)],
                max_in_flight=3)
            self.assertEqual([item["frame_id"] for item in result], list(range(8)))
            self.assertEqual(
                [record["profile"] for record in transport.submits].count(2), 4)
            self.assertEqual(
                [record["profile"] for record in transport.submits].count(3), 4)
            self.assertEqual(
                [record["profile"] for record in transport.submits].count(0), 4)
            self.assertEqual(
                [record["profile"] for record in transport.submits].count(1), 4)
            for frame in result[::2]:
                events = frame["pair_timing"]["pl_events"]
                self.assertEqual(events[0]["profiles"], [2, 3, 0])
                self.assertEqual(events[1]["profile"], 1)
            self.assertEqual(len(transport.direct_quantize_calls), 4 * 4)
            self.assertEqual(transport.legacy_array_uploads, [])
            self.assertEqual(instance.last_run_summary["ps_workers"], 2)
        finally:
            instance.close()

    def test_opt_in_runtime_matches_single_ps_and_overlaps_distinct_clients(self):
        probe = _OverlapProbe()
        owned = dict((name, _ProbeClient(name, probe)) for name in FakeClient.SHAPES)
        baseline = runtime(V10LiveRuntime)
        candidate = runtime(owned=owned)
        items = [(index, image(index + 1)) for index in range(16)]
        try:
            expected = baseline.run(items, max_in_flight=4)
            actual = candidate.run(items, max_in_flight=4)
            self.assertEqual([item["frame_id"] for item in actual],
                             [item["frame_id"] for item in expected])
            for left, right in zip(actual, expected):
                np.testing.assert_array_equal(left["features"], right["features"])
            self.assertTrue(probe.overlap.is_set())
            summary = candidate.last_run_summary
            self.assertEqual(summary["schedule"],
                             "incremental_bounded_split_ps_pl")
            self.assertEqual(summary["ps_front_workers"], 1)
            self.assertEqual(summary["ps_suffix_workers"], 1)
            self.assertEqual(summary["pl_workers"], 1)
            self.assertGreater(summary["ps_front_worker_busy_ms"], 0)
            self.assertGreater(summary["ps_suffix_worker_busy_ms"], 0)
            self.assertTrue(summary["workers_drained"])
            self.assertLessEqual(summary["peak_in_flight_pairs"], 4)
            overlap = summary["overlap"]
            self.assertGreater(overlap["ps_union_busy_ms"], 0)
            self.assertGreater(overlap["front_suffix_overlap_ms"], 0)
            self.assertGreater(overlap["cross_pair_ps_pl_overlap_ms"], 0)
            self.assertAlmostEqual(
                overlap["ps_union_busy_ms"],
                overlap["ps_front_busy_ms"] +
                overlap["ps_suffix_busy_ms"] -
                overlap["front_suffix_overlap_ms"], places=4)
            self.assertLessEqual(
                overlap["cross_pair_ps_pl_overlap_ms"],
                min(overlap["ps_union_busy_ms"], overlap["pl_busy_ms"]) + .01)
        finally:
            baseline.close()
            candidate.close()

    def test_suffix_failure_drains_concurrent_front_owner(self):
        probe = _OverlapProbe(fail_suffix=True)
        owned = dict((name, _ProbeClient(name, probe)) for name in FakeClient.SHAPES)
        instance = runtime(owned=owned)
        try:
            with self.assertRaisesRegex(ValueError, "suffix probe failure"):
                instance.run([(index, image(index + 1)) for index in range(16)],
                             max_in_flight=4)
            self.assertEqual(probe.active, {"PS_FRONT": 0, "PS_SUFFIX": 0})
            self.assertEqual(instance.last_run_summary["status"], "FAILED_DRAINED")
            self.assertTrue(instance.last_run_summary["workers_drained"])
            self.assertTrue(instance.last_run_summary["drained_call_errors"] == [] or
                            isinstance(instance.last_run_summary[
                                "drained_call_errors"], list))
        finally:
            instance.close()


if __name__ == "__main__":
    unittest.main()
