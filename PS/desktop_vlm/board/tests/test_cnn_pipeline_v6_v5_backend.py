"""Compatibility-boundary tests for running the v6 DAG on the v5 ABI."""

import unittest
from pathlib import Path

import numpy as np

from desktop_vlm.board import cnn_ddr_v5_runtime as v5
from desktop_vlm.board.cnn_pipeline_v6 import (
    CpuThreadBudget,
    V6DagPipeline,
    V6StageCallbacks,
)
from desktop_vlm.board.cnn_pipeline_v6_v5_backend import V5CompatDagBackend


ROOT = Path(__file__).resolve().parents[3]
FIXTURE_ROOT = ROOT / "artifacts/board-debug-20261005/acceleration/host"


class V5CompatDagBackendTests(unittest.TestCase):
    def test_array_transport_hooks_keep_hot_path_buffers_preallocated(self):
        class ArrayFake(v5.FakeV5Transport):
            def __init__(self):
                v5.FakeV5Transport.__init__(self)
                self.upload_array_addresses = []
                self.download_array_addresses = []

            def upload_array(self, handle, offset, array):
                self.upload_array_addresses.append(array.__array_interface__["data"][0])
                self.upload(handle, offset, memoryview(array).cast("B"))

            def download_into(self, handle, offset, array):
                self.download_array_addresses.append(array.__array_interface__["data"][0])
                raw = self.download(handle, offset, array.nbytes)
                np.copyto(array.reshape(-1), np.frombuffer(raw, dtype=array.dtype))
                return array

        transport = ArrayFake()
        adapter = v5.V5ProfileAdapter(transport, FIXTURE_ROOT)
        backend = V5CompatDagBackend(adapter, pool_size=1, generation=8)
        tag = type("Tag", (), {"frame_id": 1, "generation": 8})()
        lease = backend.acquire_frame(tag)
        value = np.zeros((1, 64, 64, 64), dtype=np.float32)
        for unused in range(2):
            prepared = backend.prepare("n0", lease, value)
            executed = backend.execute("n0", lease, prepared)
            backend.finish("n0", lease, executed)
        self.assertEqual(len(set(transport.upload_array_addresses)), 1)
        self.assertEqual(transport.upload_array_addresses,
                         transport.download_array_addresses)
        backend.release_frame(lease)
        backend.close()

    def test_prepare_execute_finish_matches_frozen_v5_quant_layout_contract(self):
        transport = v5.FakeV5Transport()
        adapter = v5.V5ProfileAdapter(transport, FIXTURE_ROOT)
        backend = V5CompatDagBackend(adapter, pool_size=1, generation=23)
        tag = type("Tag", (), {"frame_id": 7, "generation": 23})()
        lease = backend.acquire_frame(tag)
        value = np.linspace(-1.0, 1.0, 64 * 64 * 64,
                            dtype=np.float32).reshape(1, 64, 64, 64)

        prepared = backend.prepare("n0", lease, value)
        executed = backend.execute("n0", lease, prepared)
        finished = backend.finish("n0", lease, executed)

        expected_q = v5.quantize_chw(
            value, adapter.contracts[2]["input_scale"], 2, "expected")
        expected = v5.dequantize_chw(
            expected_q, adapter.contracts[2]["output_scale"], 2, "expected")
        self.assertTrue(np.array_equal(finished["activation"], expected))
        self.assertEqual(finished["completion"]["logical_profile"], "n0")
        self.assertEqual(finished["completion"]["reset_generation"], 23)
        backend.release_frame(lease)
        receipt = backend.close()
        self.assertTrue(receipt["quiesce_confirmed"])
        self.assertTrue(receipt["all_handles_freed"])

    def test_two_inflight_frames_get_distinct_activations_and_shared_params(self):
        adapter = v5.V5ProfileAdapter(v5.FakeV5Transport(), FIXTURE_ROOT)
        backend = V5CompatDagBackend(adapter, pool_size=2, generation=4)
        tag0 = type("Tag", (), {"frame_id": 0, "generation": 4})()
        tag1 = type("Tag", (), {"frame_id": 1, "generation": 4})()
        lease0 = backend.acquire_frame(tag0)
        lease1 = backend.acquire_frame(tag1)
        self.assertEqual(lease0.parameter_handles, lease1.parameter_handles)
        self.assertTrue(set(lease0.activation_handles.values()).isdisjoint(
            lease1.activation_handles.values()))
        backend.release_frame(lease0)
        backend.release_frame(lease1)
        backend.close()

    def test_scheduler_uses_split_v5_transport_without_giant_backend_callback(self):
        adapter = v5.V5ProfileAdapter(v5.FakeV5Transport(), FIXTURE_ROOT)
        backend = V5CompatDagBackend(adapter, pool_size=2, generation=31)
        callbacks = V6StageCallbacks(
            stem_prefix=lambda unused: np.zeros((1, 64, 64, 64), dtype=np.float32),
            network1_bridge=lambda unused: np.zeros((1, 128, 32, 32), dtype=np.float32),
            network3_bridge=lambda unused: np.zeros((1, 256, 16, 16), dtype=np.float32),
            suffix=lambda unused: np.arange(512, dtype=np.float32).reshape(1, 512))
        runtime = V6DagPipeline(
            backend, callbacks, queue_capacity=2, max_in_flight=2, ps_workers=4,
            cpu_budget=CpuThreadBudget(
                4, {"stem_prefix": 1, "network1_bridge": 1,
                    "network3_bridge": 1, "suffix": 1}))
        results = runtime.run(
            [(0, np.zeros((1, 3, 256, 256), dtype=np.float32)),
             (1, np.ones((1, 3, 256, 256), dtype=np.float32))],
            [0, 1])
        self.assertEqual([result.features.shape for result in results], [(1, 512), (1, 512)])
        self.assertTrue(all(len(result.completions) == 3 for result in results))
        calls = [call[0] for call in adapter.transport.calls]
        self.assertEqual(calls.count("submit"), 6)
        self.assertEqual(calls.count("download"), 6)
        backend.close()


if __name__ == "__main__":
    unittest.main()
