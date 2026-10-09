import hashlib
import pathlib
import sys
import unittest

import numpy as np


BOARD = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BOARD))

from cnn_ddr_v10_runtime import profile_contract
from cnn_pipeline_v10_paired_runtime import V10PairedNormalRuntime
from run_cnn_pipeline_v10_board_window import create_full_model_runtime


MANIFEST_SHA = "1" * 64


class FakeClient(object):
    SHAPES = {
        "stem-prefix": ((1, 64, 64, 64), "n0_input"),
        "network1-bridge": ((1, 128, 32, 32), "n2_input"),
        "network3-bridge": ((1, 256, 16, 16), "n4_input"),
        "suffix": ((1, 512), "features"),
    }

    def __init__(self, name):
        self.name = name
        self.calls = 0
        self.closed = False

    def infer(self, tensors):
        self.calls += 1
        marker = float(np.asarray(tensors[0], dtype=np.float32).reshape(-1)[0])
        shape, output = self.SHAPES[self.name]
        return {output: np.full(shape, marker, dtype=np.float32)}, 0.25

    def close(self):
        self.closed = True


class FakeTransport(object):
    def __init__(self):
        self.allocations = {}
        self.next_handle = 1
        self.submits = []
        self.pending = None
        self.closed = False

    def alloc(self, size, alignment=16):
        self.assert_aligned(alignment)
        handle = self.next_handle
        self.next_handle += 1
        self.allocations[handle] = bytearray(size)
        return handle

    @staticmethod
    def assert_aligned(alignment):
        if alignment != 16:
            raise AssertionError("unexpected alignment")

    def upload(self, handle, offset, payload):
        raw = bytes(payload)
        self.allocations[handle][offset:offset + len(raw)] = raw

    def upload_array(self, handle, offset, array):
        self.upload(handle, offset, np.asarray(array).tobytes(order="C"))

    def submit(self, profile, blocks, params, arena_a, arena_b):
        if arena_a == arena_b:
            raise AssertionError("paired arenas must be distinct")
        cfg = profile_contract(profile, blocks)
        record = {
            "profile": profile, "blocks": blocks, "params": params,
            "arena_a": arena_a, "arena_b": arena_b,
            "input_a_sha256": hashlib.sha256(
                self.allocations[arena_a][:cfg["slot_bytes"]]).hexdigest(),
            "input_b_sha256": hashlib.sha256(
                self.allocations[arena_b][:cfg["slot_bytes"]]).hexdigest(),
        }
        # The mock PL is an identity in quantized HCW. All production normal
        # profiles use even block counts, so final output is slot0.
        if cfg["output_offset_bytes"]:
            for handle in (arena_a, arena_b):
                source = bytes(self.allocations[handle][:cfg["slot_bytes"]])
                at = cfg["output_offset_bytes"]
                self.allocations[handle][at:at + len(source)] = source
        self.submits.append(record)
        self.pending = profile
        return {"profile": profile, "blocks": blocks}

    def wait_complete(self, profile, timeout_s):
        if profile != self.pending or timeout_s <= 0:
            raise AssertionError("bad completion wait")
        self.pending = None
        return {"profile": profile, "protocol_error": 0, "job_cycles": 1}

    def download_into(self, handle, offset, array):
        target = np.asarray(array)
        raw = bytes(self.allocations[handle][offset:offset + target.nbytes])
        np.copyto(target, np.frombuffer(raw, dtype=target.dtype).reshape(target.shape))

    def close(self):
        self.allocations.clear()
        self.closed = True
        return {"quiesce_confirmed": True, "all_handles_freed": True,
                "transport_closed": True}


def contract():
    profiles = {}
    for profile, blocks in ((0, 12), (1, 20), (2, 4)):
        size = profile_contract(profile, blocks)["params_bytes"]
        payload = bytes(size)
        profiles[profile] = {
            "params": payload,
            "params_sha256": hashlib.sha256(payload).hexdigest(),
            "input_scale": 1.0,
            "output_scale": 1.0,
        }
    return {"manifest_sha256": MANIFEST_SHA, "profiles": profiles}


def clients():
    return {name: FakeClient(name) for name in FakeClient.SHAPES}


def image(marker):
    value = np.zeros((1, 3, 256, 256), dtype=np.float32)
    value.reshape(-1)[0] = marker
    return value


class V10PairedNormalRuntimeTests(unittest.TestCase):
    def test_board_runner_factory_exposes_full_normal_path(self):
        transport = FakeTransport()
        runtime = create_full_model_runtime(
            transport, contract(), MANIFEST_SHA, clients(), timeout_s=9.0)
        self.assertIsInstance(runtime, V10PairedNormalRuntime)
        self.assertEqual(runtime.timeout_s, 9.0)
        runtime.close()

    def test_single_frame_uses_immediate_shadow_partner(self):
        transport = FakeTransport()
        owned_clients = clients()
        runtime = V10PairedNormalRuntime(
            transport, contract(), MANIFEST_SHA, owned_clients)
        result = runtime.run_one(7, image(3.0))
        self.assertEqual(result["frame_id"], 7)
        self.assertTrue(result["shadow_partner_used"])
        self.assertEqual(result["pair_timing"]["real_frame_count"], 1)
        self.assertFalse(result["pair_timing"]["shadow_counts_as_real_throughput"])
        self.assertEqual([event["partition"] for event in result["pair_timing"]["ps_events"]],
                         ["stem-prefix", "stem-prefix", "network1-bridge",
                          "network1-bridge", "network3-bridge",
                          "network3-bridge", "suffix"])
        self.assertEqual(len(result["pair_timing"]["pl_events"]), 3)
        self.assertIsNone(result["paired_with"])
        self.assertTrue(np.all(result["features"] == 3.0))
        self.assertEqual([item["profile"] for item in transport.submits], [2, 0, 1])
        self.assertTrue(all(item["input_a_sha256"] == item["input_b_sha256"]
                            for item in transport.submits))
        cleanup = runtime.close()
        self.assertTrue(cleanup["transport_closed"])
        self.assertTrue(all(client.closed for client in owned_clients.values()))

    def test_three_frames_pair_then_mirror_tail_and_preserve_order(self):
        transport = FakeTransport()
        runtime = V10PairedNormalRuntime(
            transport, contract(), MANIFEST_SHA, clients())
        results = runtime.run([(10, image(1.0)), (11, image(2.0)),
                               (12, image(4.0))])
        self.assertEqual([item["frame_id"] for item in results], [10, 11, 12])
        self.assertEqual([float(item["features"][0]) for item in results],
                         [1.0, 2.0, 4.0])
        self.assertEqual([item["shadow_partner_used"] for item in results],
                         [False, False, True])
        self.assertEqual(runtime.last_run_summary["pair_count"], 2)
        self.assertEqual(runtime.last_run_summary["real_frame_count"], 3)
        self.assertEqual(results[0]["pair_timing"]["real_frame_count"], 2)
        self.assertEqual([item["profile"] for item in transport.submits],
                         [2, 0, 1, 2, 0, 1])
        for item in transport.submits[:3]:
            self.assertNotEqual(item["input_a_sha256"], item["input_b_sha256"])
        for item in transport.submits[3:]:
            self.assertEqual(item["input_a_sha256"], item["input_b_sha256"])
        runtime.close()

    def test_rejects_duplicate_ids_before_pl_submission(self):
        transport = FakeTransport()
        runtime = V10PairedNormalRuntime(
            transport, contract(), MANIFEST_SHA, clients())
        with self.assertRaisesRegex(ValueError, "unique"):
            runtime.run([(5, image(1.0)), (5, image(2.0))])
        self.assertEqual(transport.submits, [])
        runtime.close()


if __name__ == "__main__":
    unittest.main()
