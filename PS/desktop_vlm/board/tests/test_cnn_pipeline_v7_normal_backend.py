import hashlib
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

import numpy as np


ROOT = Path(__file__).resolve().parents[3]
from desktop_vlm.board import cnn_pipeline_v7_normal_backend as normal
from desktop_vlm.board import run_cnn_pipeline_v7_fixed as fixed


HOST = ROOT / "artifacts/board-debug-20261005/acceleration/host"
BUNDLE = HOST / "cnn-shared-v7-normal-chain-bundle-001"
RUNTIME = HOST / "network-w16-runtime-bundles-001"


class FakeTransport(object):
    def __init__(self, core_count=1):
        self.core_count = core_count
        self.next_handle = 1
        self.objects = {}
        self.states = []
        for unused in range(core_count):
            state = dict((name, 0) for name in normal.STATUS_NAMES)
            state["reset_generation"] = 7
            state["job_cycles_lo"] = 1000
            self.states.append(state)
        self.state = self.states[0]
        self.submits = []
        self._submit_lock = threading.Lock()
        self.active_submits = 0
        self.max_active_submits = 0
        self.busy_memory_handles = {}
        self.fail_quiesce = False
        self.generation_change_core = None
        self.submit_entered = None
        self.submit_release = None
        self.quiesced = False
        self.closed = False

    def identity(self):
        return {"core_count": self.core_count,
                "blocks": [12, 20, 4], "channels": [128, 256, 64],
                "widths": [32, 16, 64],
                "block_stride_words": [22433, 61057, 12193],
                "profile_count": 3}

    def status(self, core_id=None):
        state = self.states[0 if core_id is None else core_id]
        result = dict(state)
        if core_id is not None:
            result["core_id"] = core_id
        result["job_cycles"] = ((result["job_cycles_hi"] << 32) |
                                result["job_cycles_lo"])
        return result

    def alloc(self, size, alignment=65536, flags=1):
        handle = self.next_handle
        self.next_handle += 1
        self.objects[handle] = bytearray(size)
        return {"handle": handle, "bytes": size, "alignment": alignment,
                "flags": flags, "arena_index": 0}

    def upload(self, handle, offset, payload):
        with self._submit_lock:
            if self.busy_memory_handles.get(handle, 0):
                raise RuntimeError("object-level transfer/job exclusion violated")
        self.objects[handle][offset:offset + len(payload)] = payload

    def download(self, handle, offset, size):
        return bytes(self.objects[handle][offset:offset + size])

    def submit(self, descriptor, params_handle, memory_handle):
        with self._submit_lock:
            self.submits.append(dict(descriptor))
            self.active_submits += 1
            self.max_active_submits = max(self.max_active_submits,
                                          self.active_submits)
            self.busy_memory_handles[memory_handle] = (
                self.busy_memory_handles.get(memory_handle, 0) + 1)
        if self.submit_entered is not None:
            self.submit_entered.set()
        if self.submit_release is not None:
            if not self.submit_release.wait(5.0):
                raise RuntimeError("synthetic long submit was not released")
        time.sleep(0.001)
        row_bytes = int(descriptor["row_words"]) * 16
        start = int(descriptor["start_row"]) * row_bytes
        count = int(descriptor["row_count"]) * row_bytes
        source = int(descriptor["src_words"]) * 16
        destination = int(descriptor["dst_words"]) * 16
        memory = self.objects[memory_handle]
        memory[destination + start:destination + start + count] = \
            memory[source + start:source + start + count]
        scratch = int(descriptor["scratch_words"]) * 16
        extent = int(descriptor["scratch_required_words"]) * 16
        memory[scratch:scratch + extent] = bytes(bytearray([0x31])) * extent
        state = self.states[int(descriptor["core_id"])]
        state["completed_jobs"] += 1
        state["profile"] = int(descriptor["profile"])
        state["job_cycles_lo"] = 29
        for name, delta in (("ar_total", 3), ("rlast_total", 3),
                            ("aw_total", 2), ("wlast_total", 2),
                            ("b_total", 2)):
            state[name] += delta
        if self.generation_change_core == int(descriptor["core_id"]):
            state["reset_generation"] += 1
            self.generation_change_core = None
        with self._submit_lock:
            self.active_submits -= 1
            self.busy_memory_handles[memory_handle] -= 1
            if not self.busy_memory_handles[memory_handle]:
                del self.busy_memory_handles[memory_handle]

    def quiesce(self):
        if self.fail_quiesce:
            raise RuntimeError("synthetic quiesce failure")
        self.quiesced = True

    def free(self, handle):
        if not self.quiesced:
            raise RuntimeError("FREE before terminal QUIESCE")
        del self.objects[handle]

    def close(self):
        self.closed = True


class FakeClient(object):
    def __init__(self, output_name, shape):
        self.header = {"threads": 1}
        self.output_name = output_name
        self.shape = shape
        self.calls = 0
        self.closed = False

    def infer(self, tensors):
        self.calls += 1
        return ({self.output_name: np.zeros(self.shape, dtype=np.float32)}, 0.01)

    def close(self):
        self.closed = True


def fake_clients():
    return {
        "stem-prefix": FakeClient("n0_input", (1, 64, 64, 64)),
        "network1-bridge": FakeClient("n2_input", (1, 128, 32, 32)),
        "network3-bridge": FakeClient("n4_input", (1, 256, 16, 16)),
        "suffix": FakeClient("features", (1, 512)),
    }


class V7NormalBackendTests(unittest.TestCase):
    def test_logical_output_client_maps_original_onnx_tensor_name(self):
        class Client(object):
            header = {"threads": 1}
            _closed = False

            def infer(self, tensors):
                return {"/long/original/name": np.ones((1, 2), np.float32)}, 1.25

            def close(self):
                self._closed = True

        wrapped = fixed._LogicalOutputClient(
            Client(), "/long/original/name", "n0_input")
        outputs, run_ms = wrapped.infer([np.zeros((1,), np.float32)])
        self.assertEqual(set(outputs), {"n0_input"})
        self.assertEqual(outputs["n0_input"].shape, (1, 2))
        self.assertEqual(run_ms, 1.25)
        wrapped.close()
        self.assertTrue(wrapped.closed)

    def test_mobileclip_preprocess_accepts_frozen_f32_nchw_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "image-00-input.f32"
            source = np.arange(3 * 256 * 256, dtype=np.float32).reshape(
                1, 3, 256, 256)
            path.write_bytes(source.astype("<f4").tobytes(order="C"))
            actual = fixed.mobileclip_preprocess(str(path))
            self.assertEqual(actual.shape, (1, 3, 256, 256))
            self.assertEqual(actual.dtype, np.float32)
            np.testing.assert_array_equal(actual, source)

    def test_frozen_scales_are_loaded_from_scale_manifest(self):
        transport = FakeTransport()
        backend = normal.CnnPipelineV7NormalStageBackend(transport, BUNDLE, RUNTIME)
        manifest = json.loads((RUNTIME / "scale-manifest.json").read_text(encoding="utf-8"))
        expected = manifest["profiles"]["2"]["per_block"][0]["scales"]["input"]
        self.assertEqual(backend.profile_scales[2][0]["input"], expected)
        self.assertEqual(len(backend.profile_scales[2]), 4)
        backend.close()

    def test_quantize_uses_ties_even_and_hcw_axis_order(self):
        scale = 0.25
        nchw = np.zeros((1, 64, 64, 64), dtype=np.float32)
        nchw[0, 1, 2, 3] = scale * 0.5
        nchw[0, 0, 1, 4] = scale * 1.5
        nchw[0, 2, 3, 5] = -scale * 1.5
        quantized = normal.quantize_nchw_to_hcw(2, nchw, scale)
        self.assertEqual(quantized.shape, (64, 64, 64))
        self.assertEqual(quantized.dtype, np.dtype("<i2"))
        self.assertEqual(int(quantized[2, 1, 3]), 0)
        self.assertEqual(int(quantized[1, 0, 4]), 2)
        self.assertEqual(int(quantized[3, 2, 5]), -2)

    def test_backend_runs_complete_block_stripe_chain_and_dequantizes(self):
        transport = FakeTransport(core_count=4)
        backend = normal.CnnPipelineV7NormalStageBackend(transport, BUNDLE, RUNTIME)
        activation = np.zeros((1, 64, 64, 64), dtype=np.float32)
        result = backend.execute_normal_stage("n0", activation, 31)
        self.assertEqual(result["block_count"], 4)
        self.assertEqual(result["stripe_jobs"], 64)
        self.assertEqual(result["activation"].shape, activation.shape)
        self.assertEqual(result["activation"].dtype, np.dtype(np.float32))
        self.assertEqual(result["completion"]["reset_generation"],
                         (7, 7, 7, 7))
        stripes = [event for event in result["stage_events"]
                   if event.get("event") == "stripe_completed"]
        self.assertEqual(len(stripes), 64)
        self.assertTrue(all(event["job_cycles"] == 29 for event in stripes))
        self.assertEqual(set(item["core_id"] for item in transport.submits),
                         set((0, 1, 2, 3)))
        self.assertTrue(all(item["frame_tag"] == 31
                            for item in transport.submits))
        self.assertEqual(len(set(item["param_base_words"]
                                 for item in transport.submits)), 4)
        receipt = backend.close()
        self.assertTrue(receipt["quiesce_confirmed"])
        self.assertTrue(receipt["all_handles_freed"])
        self.assertFalse(transport.objects)

    def test_runtime_three_cores_use_each_core_and_finish_partial_wave(self):
        transport = FakeTransport(core_count=3)
        backend = normal.CnnPipelineV7NormalStageBackend(transport, BUNDLE, RUNTIME)
        activation = np.zeros((1, 64, 64, 64), dtype=np.float32)
        result = backend.execute_normal_stage("n0", activation, 0x123)
        self.assertEqual(result["completion"]["executed_core_ids"], [0, 1, 2])
        self.assertGreater(transport.max_active_submits, 1)
        self.assertEqual(transport.max_active_submits, 3)
        for block in range(4):
            block_submits = [item for item in transport.submits
                             if item["block_index"] == block]
            self.assertEqual(len(block_submits), 16)
            self.assertEqual([item["core_id"] for item in block_submits[-1:]], [0])
            self.assertEqual([item["start_row"] for item in block_submits[-1:]], [60])
        backend.close()

    def test_runtime_accepts_each_routed_core_count_from_one_through_four(self):
        activation = np.zeros((1, 64, 64, 64), dtype=np.float32)
        for core_count in (1, 2, 3, 4):
            transport = FakeTransport(core_count=core_count)
            backend = normal.CnnPipelineV7NormalStageBackend(
                transport, BUNDLE, RUNTIME)
            result = backend.execute_normal_stage("n0", activation, 900 + core_count)
            self.assertEqual(result["completion"]["core_count"], core_count)
            self.assertEqual(result["completion"]["executed_core_ids"],
                             list(range(core_count)))
            self.assertEqual(result["stripe_jobs"], 64)
            self.assertEqual(transport.max_active_submits, core_count)
            backend.close()

    def test_failed_quiesce_is_unknown_and_close_receipt_is_repeat_safe(self):
        transport = FakeTransport()
        transport.fail_quiesce = True
        backend = normal.CnnPipelineV7NormalStageBackend(transport, BUNDLE, RUNTIME)
        with self.assertRaises(RuntimeError):
            backend.close()
        receipt = backend.close()
        self.assertEqual(receipt["cleanup_status"], "UNKNOWN")
        self.assertIsNone(receipt["all_handles_freed"])
        self.assertFalse(transport.closed)

    def test_generation_change_on_any_core_fails_the_stage(self):
        transport = FakeTransport(core_count=3)
        transport.generation_change_core = 2
        backend = normal.CnnPipelineV7NormalStageBackend(transport, BUNDLE, RUNTIME)
        activation = np.zeros((1, 64, 64, 64), dtype=np.float32)
        with self.assertRaisesRegex(RuntimeError, "another reset generation"):
            backend.execute_normal_stage("n0", activation, 23)
        backend.close()

    def test_generation_check_does_not_wait_for_long_stage_but_second_stage_does(self):
        transport = FakeTransport(core_count=1)
        transport.submit_entered = threading.Event()
        transport.submit_release = threading.Event()
        backend = normal.CnnPipelineV7NormalStageBackend(transport, BUNDLE, RUNTIME)
        activation = np.zeros((1, 256, 16, 16), dtype=np.float32)
        results = []
        failures = []

        def execute(frame_id):
            try:
                results.append(backend.execute_normal_stage("n4", activation, frame_id))
            except Exception as error:
                failures.append(error)

        first = threading.Thread(target=execute, args=(401,))
        first.start()
        self.assertTrue(transport.submit_entered.wait(5.0))
        checked_at = time.perf_counter()
        self.assertEqual(backend.current_generation(), 7)
        self.assertLess(time.perf_counter() - checked_at, 0.25)

        second = threading.Thread(target=execute, args=(402,))
        second.start()
        time.sleep(0.05)
        self.assertEqual(transport.active_submits, 1)
        self.assertEqual(len(transport.submits), 1)

        transport.submit_release.set()
        first.join(15.0)
        second.join(15.0)
        self.assertFalse(first.is_alive())
        self.assertFalse(second.is_alive())
        self.assertFalse(failures)
        self.assertEqual(len(results), 2)
        backend.close()

    def test_production_split_wiring_uses_verified_contract_and_lazy_clients(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest_path = root / "manifest.json"
            manifest_path.write_text("{}", encoding="utf-8")
            records = {}
            for name in ("stem-prefix", "network1-bridge",
                         "network3-bridge", "suffix"):
                records[name] = {"path": str(root / (name + ".onnx")),
                                 "contract": {"inputs": [], "outputs": [
                                     {"name": "/original/" + name}]}}
            fake_bundle = {"models": records, "manifest_sha256": "a" * 64}
            fake_loader = mock.Mock(return_value=fake_bundle)
            fake_ort_client = mock.Mock(side_effect=lambda *args, **kwargs: FakeClient("x", ()))
            with mock.patch("desktop_vlm.board.cnn_ddr_v5_runtime.load_v5_split_contracts",
                            fake_loader), \
                    mock.patch("desktop_vlm.board.partition_s1.OrtPartitionClient",
                               fake_ort_client):
                clients, manifest_sha = fixed.load_existing_split_clients(
                    root, "ort-c-runner", manifest_path, "a" * 64, threads=2)
            fake_loader.assert_called_once_with(root, "a" * 64)
            self.assertEqual(manifest_sha, "a" * 64)
            self.assertEqual(set(clients), set(records))
            self.assertEqual(fake_ort_client.call_count, 4)
            command = fake_ort_client.call_args_list[0][0][0]
            self.assertEqual(command[:2], ["ort-c-runner", "--stream"])
            self.assertEqual(command[-1], "2")

    def test_fixed_graph_reuses_split_clients_and_reports_fake_transport_scope(self):
        transport = FakeTransport(core_count=1)
        backend = normal.CnnPipelineV7NormalStageBackend(transport, BUNDLE, RUNTIME)
        split = fake_clients()
        callback_calls = {"capture": 0, "decode": 0, "preprocess": 0}

        def capture(item):
            callback_calls["capture"] += 1
            return item

        def decode(item):
            callback_calls["decode"] += 1
            return item

        def preprocess(item):
            callback_calls["preprocess"] += 1
            return np.zeros((1, 3, 256, 256), dtype=np.float32)

        report = fixed.run_fixed_graph(
            [(8, "fake-frame")], [8], backend, split,
            capture=capture, decode=decode, preprocess=preprocess,
            rank=lambda raw: int(np.argmax(raw)),
            output=lambda value: value)
        self.assertFalse(report["board_operation_performed"])
        self.assertEqual(report["frame_count"], 1)
        self.assertEqual(callback_calls, {"capture": 1, "decode": 1,
                                          "preprocess": 1})
        self.assertTrue(all(client.calls == 1 for client in split.values()))
        self.assertTrue(all(client.closed for client in split.values()))
        self.assertTrue(transport.closed)


if __name__ == "__main__":
    unittest.main()
