"""Offline tests for the v7 fixed-graph adapter; no ORT process or board."""

import unittest

import numpy as np

from desktop_vlm.board.cnn_pipeline_v6 import PipelineStageError
from desktop_vlm.board.cnn_pipeline_v7_adapter import CnnPipelineV7Adapter


class FakeClient(object):
    def __init__(self, output_name, output_shape):
        self.header = {"threads": 1}
        self.output_name = output_name
        self.output_shape = output_shape
        self.calls = []
        self.closed = False

    def infer(self, tensors):
        source = np.asarray(tensors[0])
        self.calls.append(tuple(source.shape))
        return ({self.output_name: np.zeros(self.output_shape, dtype=np.float32)}, 0.01)

    def close(self):
        self.closed = True


def clients():
    return {
        "stem-prefix": FakeClient("n0_input", (1, 64, 64, 64)),
        "network1-bridge": FakeClient("n2_input", (1, 128, 32, 32)),
        "network3-bridge": FakeClient("n4_input", (1, 256, 16, 16)),
        "suffix": FakeClient("features", (1, 512)),
    }


class FakeStripeBackend(object):
    PROFILE_CONTRACT = {
        "n0": ((1, 64, 64, 64), 4, 64),
        "n2": ((1, 128, 32, 32), 12, 96),
        "n4": ((1, 256, 16, 16), 20, 80),
    }

    def __init__(self, fail_at=None):
        self.generation = 17
        self.fail_at = fail_at
        self.calls = []
        self.closed = False

    def current_generation(self):
        return self.generation

    def execute_normal_stage(self, profile, activation, frame_id):
        shape, blocks, stripes = self.PROFILE_CONTRACT[profile]
        self.calls.append((frame_id, profile))
        if self.fail_at == (frame_id, profile):
            raise RuntimeError("stub stripe failure")
        self.assert_shape = tuple(np.asarray(activation).shape)
        return {
            "activation": np.asarray(activation, dtype=np.float32),
            "block_count": blocks,
            "stripe_jobs": stripes,
            "stage_events": [{"event": "all_stripes_joined", "profile": profile}],
            "completion": {"reset_generation": self.generation, "profile": profile},
        }

    def close(self):
        self.closed = True
        return {"quiesce_confirmed": True, "all_handles_freed": True,
                "transport_closed": True}


class CnnPipelineV7AdapterTests(unittest.TestCase):
    def test_fixed_graph_returns_ordered_raw512_and_complete_timing_events(self):
        split = clients()
        backend = FakeStripeBackend()
        adapter = CnnPipelineV7Adapter(
            backend, split,
            capture=lambda item: item,
            decode=lambda item: item,
            preprocess=lambda item: np.zeros((1, 3, 256, 256), dtype=np.float32),
            rank=lambda raw: {"top": int(np.argmax(raw))},
            output=lambda value: value,
        )
        self.assertEqual(adapter.pipeline.execution_plan.transition_routes,
                         {"n1": "ps", "n3": "ps"})
        items = [(29, np.zeros((1,), dtype=np.float32)),
                 (7, np.ones((1,), dtype=np.float32))]
        batch = adapter.run(items, [29, 7])
        reports = batch["frames"]
        self.assertEqual(batch["frame_count"], 2)
        self.assertGreater(batch["batch_wall_ms"], 0)
        self.assertEqual([record["frame_id"] for record in reports], [29, 7])
        for report in reports:
            self.assertEqual(report["raw512"].shape, (512,))
            self.assertEqual(report["raw512"].dtype, np.dtype(np.float32))
            self.assertGreater(report["wall_ms"], 0)
            self.assertIn("stem_prefix", report["stage_events"])
            self.assertIn("network1_bridge", report["stage_events"])
            self.assertIn("network3_bridge", report["stage_events"])
            self.assertIn("suffix", report["stage_events"])
            self.assertEqual(len(report["normal_stage_events"]), 3)
            self.assertEqual(sum(x["block_count"] for x in report["normal_stage_events"]), 36)
            self.assertEqual(sum(x["stripe_jobs"] for x in report["normal_stage_events"]), 240)
            self.assertEqual(report["stage_order"], [
                "capture", "decode", "preprocess", "stem_prefix",
                "normal_n0_chain", "network1_bridge", "normal_n2_chain",
                "network3_bridge", "normal_n4_chain", "suffix", "rank", "output"])
            self.assertIn("not a board FPS", report["scope"])
        for frame_id in (29, 7):
            self.assertEqual([profile for fid, profile in backend.calls if fid == frame_id],
                             ["n0", "n2", "n4"])
        adapter.close()
        self.assertTrue(backend.closed)
        self.assertTrue(all(client.closed for client in split.values()))

    def test_close_requires_explicit_backend_evidence_and_is_repeatable(self):
        split = clients()
        backend = FakeStripeBackend()
        backend.close = None
        adapter = CnnPipelineV7Adapter(backend, split)
        first = adapter.close()
        second = adapter.close()
        self.assertEqual(first, second)
        self.assertEqual(first["cleanup_status"], "UNKNOWN")
        self.assertIsNone(first["quiesce_confirmed"])
        self.assertIsNone(first["all_handles_freed"])
        self.assertIsNone(first["transport_closed"])
        self.assertTrue(first["clients_closed"])

    def test_repeated_close_preserves_explicit_cleanup_receipt(self):
        split = clients()
        backend = FakeStripeBackend()
        adapter = CnnPipelineV7Adapter(backend, split)
        first = adapter.close()
        second = adapter.close()
        self.assertEqual(first, second)
        self.assertEqual(first["cleanup_status"], "CONFIRMED")
        self.assertTrue(first["quiesce_confirmed"])
        self.assertTrue(first["all_handles_freed"])
        self.assertTrue(first["transport_closed"])

    def test_explicit_failed_cleanup_is_not_promoted_to_success(self):
        split = clients()
        backend = FakeStripeBackend()
        backend.close = lambda: {
            "quiesce_confirmed": False,
            "all_handles_freed": False,
            "transport_closed": True,
            "cleanup_error": "injected cleanup failure",
        }
        adapter = CnnPipelineV7Adapter(backend, split)
        receipt = adapter.close()
        self.assertEqual(receipt["cleanup_status"], "FAILED_OR_UNKNOWN")
        self.assertFalse(receipt["quiesce_confirmed"])
        self.assertFalse(receipt["all_handles_freed"])
        self.assertEqual(receipt["cleanup_error"], "injected cleanup failure")

    def test_backend_failure_drains_frames_and_releases_leases(self):
        split = clients()
        backend = FakeStripeBackend(fail_at=(2, "n2"))
        adapter = CnnPipelineV7Adapter(backend, split, max_in_flight=2)
        image = np.zeros((1, 3, 256, 256), dtype=np.float32)
        with self.assertRaises(PipelineStageError) as raised:
            adapter.run([(1, image), (2, image), (3, image)], [1, 2, 3])
        self.assertEqual(raised.exception.frame_id, 2)
        self.assertFalse(adapter.pipeline.requires_recovery)
        self.assertEqual(adapter.backend.active_frame_count, 0)
        adapter.close()
        self.assertTrue(backend.closed)

    def test_runtime_rejects_thread_budget_over_four_core_limit(self):
        split = clients()
        for client in split.values():
            client.header["threads"] = 2
        with self.assertRaises(ValueError):
            CnnPipelineV7Adapter(FakeStripeBackend(), split)
        self.assertTrue(all(client.closed for client in split.values()))


if __name__ == "__main__":
    unittest.main()
