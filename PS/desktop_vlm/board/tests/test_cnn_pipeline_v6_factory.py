"""Production factory wiring tests using in-memory clients and transport."""

import hashlib
import unittest

import numpy as np

from desktop_vlm.board.cnn_pipeline_v6_factory import (
    create_cnn_pipeline_v6_runtime,
)
from desktop_vlm.board.cnn_pipeline_v6_fzv6_backend import PROFILE_SPECS


MANIFEST_SHA256 = "b" * 64
SE_SHAPE = (1, 256, 16, 16)


class FakeTransport(object):
    def __init__(self):
        self.identity = {"core_id": 0x465A5636, "core_abi": 0x60000,
                         "guard_caps": 0x1ff, "abi_version": 6,
                         "profile_count": 7}
        self.allocations = {}
        self.next_handle = 1
        self.generation = 9
        self.quiesced = False
        self.closed = False
        self.submits = []

    def alloc(self, size_bytes, alignment=16, flags=0):
        handle = self.next_handle
        self.next_handle += 1
        self.allocations[handle] = size_bytes
        return handle

    def upload_array(self, handle, offset, value):
        return None

    def upload(self, handle, offset, value):
        return None

    def submit(self, profile, block_count, params_handle, activation_handle,
               activation_base_offset_bytes, input_offset_bytes):
        self.submits.append((profile, block_count))

    def wait_complete(self, profile, timeout_s):
        return {"profile": profile, "reset_generation": self.generation,
                "completed_frames": len(self.submits), "job_cycles": 10}

    def get_status(self):
        return {"reset_generation": self.generation}

    def download_into(self, handle, offset, output):
        output.fill(0)

    def download(self, handle, offset, size_bytes):
        return bytes(size_bytes)

    def quiesce(self):
        self.quiesced = True

    def free(self, handle):
        if not self.quiesced:
            raise AssertionError("FREE must follow QUIESCE")
        del self.allocations[handle]

    def close_device(self):
        self.closed = True


class FakeClient(object):
    def __init__(self, output_name, output_shape, threads=1, header=None):
        self.output_name = output_name
        self.output_shape = output_shape
        self.header = header or {"threads": threads}
        self.calls = 0
        self.closed = False

    def infer(self, tensors):
        self.calls += 1
        value = np.asarray(tensors[0])
        if self.output_name == "se_output":
            result = value + np.float32(1)
        else:
            result = np.zeros(self.output_shape, dtype=np.float32)
        return ({self.output_name: result}, 0.1)

    def close(self):
        self.closed = True


def split_clients(threads=None):
    threads = threads or {"stem-prefix": 1, "network1-bridge": 1,
                          "network3-bridge": 1, "suffix": 1}
    return {
        "stem-prefix": FakeClient("n0_input", (1, 64, 64, 64), threads=threads["stem-prefix"]),
        "network1-bridge": FakeClient("n2_input", (1, 128, 32, 32), threads=threads["network1-bridge"]),
        "network3-bridge": FakeClient("n4_input", SE_SHAPE, threads=threads["network3-bridge"]),
        "suffix": FakeClient("features", (1, 512), threads=threads["suffix"]),
    }


def se_client(threads=1):
    tensor_bytes = 1 * 256 * 16 * 16 * 4
    return FakeClient("se_output", SE_SHAPE, header={
        "threads": threads,
        "inputs": [{"name": "se_input", "shape": list(SE_SHAPE),
                    "dtype": "float32", "bytes": tensor_bytes}],
        "outputs": [{"name": "se_output", "shape": list(SE_SHAPE),
                     "dtype": "float32", "bytes": tensor_bytes}],
    })


def parameter_contract():
    records = {}
    for profile, spec in PROFILE_SPECS.items():
        payload = bytes(spec.parameter_bytes)
        records[profile] = {
            "params": payload,
            "params_sha256": hashlib.sha256(payload).hexdigest(),
            "input_scale": 0.125,
            "output_scale": 0.25,
        }
    return {"manifest_sha256": MANIFEST_SHA256, "profiles": records}


class CnnPipelineV6FactoryTests(unittest.TestCase):
    def test_full_fused_calls_independent_n3_client_and_owns_all_clients(self):
        transport = FakeTransport()
        clients = split_clients({"stem-prefix": 1, "network1-bridge": 1,
                                 "network3-bridge": 1, "suffix": 2})
        se = se_client()
        runtime = create_cnn_pipeline_v6_runtime(
            transport, parameter_contract(), MANIFEST_SHA256, clients,
            mode="full_fused", network3_se_gelu_client=se)
        self.assertEqual(runtime.pipeline.ps_workers, 4)
        self.assertEqual(runtime.pipeline.queue_capacity, 4)
        self.assertEqual(runtime.pipeline.cpu_budget.logical_cores, 4)
        self.assertEqual(runtime.pipeline.cpu_budget.active_stage_keys,
                         ("stem_prefix", "network3_se_gelu", "suffix"))
        self.assertEqual(runtime.pipeline.cpu_budget.ort_intra_op_threads,
                         {"stem_prefix": 1, "network3_se_gelu": 1, "suffix": 2})
        self.assertEqual(runtime.pipeline.cpu_budget.budgeted_ort_threads, 4)
        self.assertFalse(runtime.pipeline.cpu_budget.exclusive_ort)
        self.assertEqual(runtime.pipeline.cpu_budget.active_ort_threads, 4)
        item = np.zeros((1, 3, 256, 256), dtype=np.float32)
        runtime.run([(14, item)], [14])
        self.assertEqual(se.calls, 1)
        receipt = runtime.close()
        self.assertTrue(receipt["clients_closed"])
        self.assertTrue(se.closed)
        self.assertTrue(transport.closed)
        self.assertTrue(all(client.closed for client in clients.values()))

    def test_normal_fallback_needs_and_calls_no_se_client(self):
        transport = FakeTransport()
        clients = split_clients()
        runtime = create_cnn_pipeline_v6_runtime(
            transport, parameter_contract(), MANIFEST_SHA256, clients,
            mode="normal_fallback")
        self.assertEqual(runtime.pipeline.cpu_budget.active_stage_keys,
                         ("stem_prefix", "network1_bridge",
                          "network3_bridge", "suffix"))
        self.assertEqual(runtime.pipeline.cpu_budget.ort_intra_op_threads,
                         {"stem_prefix": 1, "network1_bridge": 1,
                          "network3_bridge": 1, "suffix": 1})
        self.assertFalse(runtime.pipeline.cpu_budget.exclusive_ort)
        self.assertEqual(runtime.pipeline.max_in_flight, 4)
        self.assertEqual(runtime.pipeline.ps_workers, 4)
        item = np.zeros((1, 3, 256, 256), dtype=np.float32)
        runtime.run([(15, item)], [15])
        self.assertEqual(transport.submits, [(2, 4), (0, 12), (1, 20)])
        runtime.close()
        self.assertTrue(all(client.closed for client in clients.values()))

    def test_normal_fallback_ignores_an_optional_se_client_but_closes_it(self):
        transport = FakeTransport()
        clients = split_clients()
        se = se_client()
        runtime = create_cnn_pipeline_v6_runtime(
            transport, parameter_contract(), MANIFEST_SHA256, clients,
            mode="normal_fallback", network3_se_gelu_client=se)
        runtime.run([(16, np.zeros((1, 3, 256, 256), dtype=np.float32))], [16])
        self.assertEqual(se.calls, 0)
        runtime.close()
        self.assertTrue(se.closed)

    def test_bad_full_fused_se_contract_rolls_back_transport_and_clients(self):
        transport = FakeTransport()
        clients = split_clients({"stem-prefix": 1, "network1-bridge": 1,
                                 "network3-bridge": 1, "suffix": 2})
        invalid = se_client()
        invalid.header["outputs"][0]["shape"] = [1, 1]
        with self.assertRaises(ValueError):
            create_cnn_pipeline_v6_runtime(
                transport, parameter_contract(), MANIFEST_SHA256, clients,
                mode="full_fused", network3_se_gelu_client=invalid)
        self.assertTrue(transport.quiesced)
        self.assertTrue(transport.closed)
        self.assertTrue(all(client.closed for client in clients.values()))
        self.assertTrue(invalid.closed)

    def test_failed_parameter_pin_closes_supplied_clients_and_transport(self):
        transport = FakeTransport()
        clients = split_clients({"stem-prefix": 1, "network1-bridge": 1,
                                 "network3-bridge": 1, "suffix": 2})
        se = se_client()
        with self.assertRaises(ValueError):
            create_cnn_pipeline_v6_runtime(
                transport, parameter_contract(), "c" * 64, clients,
                mode="full_fused", network3_se_gelu_client=se)
        self.assertTrue(transport.closed)
        self.assertTrue(all(client.closed for client in clients.values()))
        self.assertTrue(se.closed)

    def test_full_fused_exclusive_serial4_uses_four_threads_one_at_a_time(self):
        transport = FakeTransport()
        clients = split_clients({"stem-prefix": 4, "network1-bridge": 4,
                                 "network3-bridge": 4, "suffix": 4})
        se = se_client(threads=4)
        runtime = create_cnn_pipeline_v6_runtime(
            transport, parameter_contract(), MANIFEST_SHA256, clients,
            mode="full_fused", thread_mode="exclusive_serial4",
            max_in_flight=4, ps_workers=4,
            network3_se_gelu_client=se)
        self.assertEqual(runtime.pipeline.ps_workers, 1)
        self.assertEqual(runtime.pipeline.max_in_flight, 1)
        self.assertTrue(runtime.pipeline.cpu_budget.exclusive_ort)
        self.assertEqual(runtime.pipeline.cpu_budget.budgeted_ort_threads, 4)
        self.assertEqual(runtime.pipeline.cpu_budget.ort_intra_op_threads,
                         {"stem_prefix": 4, "network3_se_gelu": 4, "suffix": 4})
        runtime.run([(17, np.zeros((1, 3, 256, 256), dtype=np.float32))], [17])
        self.assertEqual(se.calls, 1)
        runtime.close()

    def test_fallback_exclusive_serial4_uses_four_threads_one_at_a_time(self):
        transport = FakeTransport()
        clients = split_clients({"stem-prefix": 4, "network1-bridge": 4,
                                 "network3-bridge": 4, "suffix": 4})
        runtime = create_cnn_pipeline_v6_runtime(
            transport, parameter_contract(), MANIFEST_SHA256, clients,
            mode="normal_fallback", thread_mode="exclusive_serial4",
            max_in_flight=4, ps_workers=4)
        self.assertEqual(runtime.pipeline.ps_workers, 1)
        self.assertEqual(runtime.pipeline.max_in_flight, 1)
        self.assertTrue(runtime.pipeline.cpu_budget.exclusive_ort)
        self.assertEqual(runtime.pipeline.cpu_budget.budgeted_ort_threads, 4)
        self.assertEqual(runtime.pipeline.cpu_budget.ort_intra_op_threads,
                         {"stem_prefix": 4, "network1_bridge": 4,
                          "network3_bridge": 4, "suffix": 4})
        runtime.run([(18, np.zeros((1, 3, 256, 256), dtype=np.float32))], [18])
        runtime.close()


if __name__ == "__main__":
    unittest.main()
