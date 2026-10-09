"""Main-MRO host integration for the isolated A0004 fused upload path."""
import hashlib
import mmap
import pathlib
import sys
import unittest

import numpy as np


HERE = pathlib.Path(__file__).resolve().parent
BOARD = HERE.parent
ROOT = BOARD.parents[1]
sys.path[:0] = [str(BOARD), str(HERE)]

import cnn_ddr_v10_p3_dma_contract as dma_contract
from cnn_ddr_v10_p3_dma_runtime import LinuxIoctlV10P3DmaTransport
from cnn_pipeline_v10_live_runtime import V10LiveRuntime
from cnn_pipeline_v10_mixed_runtime import V10MixedBoundaryMixin
from cnn_pipeline_v10_p3_dma_parameters import load_v10_p3_dma_parameters
from cnn_pipeline_v10_p3_dma_runtime import V10P3DmaChainMixin
from cnn_v10_native_quant import V10NativeQuantWorkspace
from test_cnn_pipeline_v10_p3_runtime import ChainTransport
from test_cnn_pipeline_v10_paired_runtime import (
    MANIFEST_SHA, clients, contract, image)


PARAM_ROOT = (ROOT / "artifacts/board-debug-20261007/acceleration/host/"
              "cnn-v10.4-p3-dma-chain-parameters-001")
PARAM_SHA = "e285a08615111752f7c71b9541267a8a1f3b7062c9a8cbb36a7bb2b5a609d5c9"


class _MappedAllocation(object):
    def __init__(self, transport, handle, offset, size):
        self.transport = transport
        self.handle = handle
        self.offset = offset
        self.size = size
        self.mapping = mmap.mmap(-1, size)
        self.published = False

    def publish_host_write(self):
        self.mapping.seek(0)
        self.transport.allocations[self.handle][
            self.offset:self.offset + self.size] = self.mapping.read(self.size)
        self.published = True

    def close(self):
        self.mapping.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.close()


class A0004ChainTransport(ChainTransport):
    quantize_upload_into = LinuxIoctlV10P3DmaTransport.quantize_upload_into

    def __init__(self):
        super(A0004ChainTransport, self).__init__()
        self.direct_quantize_calls = []
        self.legacy_array_uploads = []
        self.cached_dma_calls = []
        self.boundary_events = []
        self.transfer_caps = {
            "caps": dma_contract.CAP_WC_MMAP,
            "page_size": 4096,
            "max_map_bytes": 32 * 1024 * 1024,
        }

    def _direct_capable(self):
        return True

    def map_arena(self, handle, offset, size, access):
        self.direct_quantize_calls.append((handle, offset, size, access))
        if access != dma_contract.ACCESS_WRITE:
            raise AssertionError("test only expects direct write maps")
        return _MappedAllocation(self, handle, offset, size)

    def upload_array(self, handle, offset, array):
        self.legacy_array_uploads.append((handle, offset, np.asarray(array).nbytes))
        return super(A0004ChainTransport, self).upload_array(handle, offset, array)

    def quantize_upload_cached_dma(self, handle, offset, value, scale,
                                   workspace, label="V10 activation",
                                   timeout_ms=2000):
        import time
        started = time.perf_counter()
        with workspace.locked_quantized_hcw(value, scale, label) as quantized:
            payload = quantized.tobytes(order="C")
            self.allocations[handle][offset:offset + len(payload)] = payload
            self.cached_dma_calls.append((handle, offset, len(payload), label))
            self.boundary_events.append(("dma_complete", handle, label))
        return {"backend": "cached_dma", "backend_id": 3,
                "bytes": len(payload), "segment_count": 1,
                "driver_dma_ns": 1000, "dma_ioctl_wall_ms": 0.01,
                "conversion_ms": 0.02,
                "total_ms": (time.perf_counter() - started) * 1000.0,
                "timeout_ms": timeout_ms, "direct_target": False}

    def submit(self, profile, blocks, params, arena_a, arena_b):
        self.boundary_events.append(("submit", profile))
        return super(A0004ChainTransport, self).submit(
            profile, blocks, params, arena_a, arena_b)


class A0004MainRuntime(V10P3DmaChainMixin,
                       V10MixedBoundaryMixin,
                       V10LiveRuntime):
    pass


class A0004RuntimeIntegrationTests(unittest.TestCase):
    def test_main_mro_uses_direct_target_conversion_for_profile2(self):
        parameters = load_v10_p3_dma_parameters(
            PARAM_ROOT / "manifest.json", PARAM_SHA)
        transport = A0004ChainTransport()
        owned_clients = clients()
        runtime = A0004MainRuntime(
            transport, contract(), MANIFEST_SHA, owned_clients,
            p3_dma_parameters=parameters, mixed_native_lib=None)
        try:
            # Base initialization allocates 3 parameter blobs + 6 arenas. A0004
            # adds only the P3 parameter blob; it reuses base P2/P1 arenas.
            self.assertEqual(len(transport.allocations), 10)
            results = runtime.run(((0, image(1.0)), (1, image(2.0))),
                                  max_in_flight=1)
            self.assertEqual([item["frame_id"] for item in results], [0, 1])
            self.assertEqual([item["profile"] for item in transport.submits],
                             [2, 3, 0, 1])
            self.assertEqual(len(transport.direct_quantize_calls), 4)
            self.assertEqual([call[2] for call in transport.direct_quantize_calls],
                             [64 * 64 * 64 * 2, 64 * 64 * 64 * 2,
                              256 * 16 * 16 * 2, 256 * 16 * 16 * 2])
            # Both PS->PL boundaries are direct-target. No activation uses the
            # legacy staged INT16 upload in the A0004 main MRO.
            self.assertEqual(transport.legacy_array_uploads, [])

            scale = runtime.contract["profiles"][2]["input_scale"]
            expected_a = V10NativeQuantWorkspace(2, 64, 64).quantize_chw_to_hcw(
                np.full((1, 64, 64, 64), 1.0, dtype=np.float32), scale).copy()
            expected_b = V10NativeQuantWorkspace(2, 64, 64).quantize_chw_to_hcw(
                np.full((1, 64, 64, 64), 2.0, dtype=np.float32), scale).copy()
            first = transport.submits[0]
            self.assertEqual(first["input_a_sha256"], hashlib.sha256(
                expected_a.tobytes(order="C")).hexdigest())
            self.assertEqual(first["input_b_sha256"], hashlib.sha256(
                expected_b.tobytes(order="C")).hexdigest())
            expected_p1_a = V10NativeQuantWorkspace(
                1, 256, 16).quantize_chw_to_hcw(
                    np.full((1, 256, 16, 16), 1.0, dtype=np.float32),
                    runtime.contract["profiles"][1]["input_scale"]).copy()
            expected_p1_b = V10NativeQuantWorkspace(
                1, 256, 16).quantize_chw_to_hcw(
                    np.full((1, 256, 16, 16), 2.0, dtype=np.float32),
                    runtime.contract["profiles"][1]["input_scale"]).copy()
            p1 = transport.submits[-1]
            self.assertEqual(p1["input_a_sha256"], hashlib.sha256(
                expected_p1_a.tobytes(order="C")).hexdigest())
            self.assertEqual(p1["input_b_sha256"], hashlib.sha256(
                expected_p1_b.tobytes(order="C")).hexdigest())
            upload = results[0]["pair_timing"]["pl_events"][0]["timing"][
                "profile2_input_upload"]
            self.assertTrue(upload["direct_target"])
            self.assertEqual(upload["backend"], "wc_mmap_direct_quantize")
            self.assertGreaterEqual(upload["conversion_ms"], 0.0)
            self.assertGreaterEqual(upload["transfer_ms"], 0.0)
            p1_upload = results[0]["pair_timing"]["pl_events"][1]["timing"][
                "quantize_upload"]
            self.assertTrue(p1_upload["direct_target"])
            self.assertEqual(p1_upload["backend"],
                             "wc_mmap_direct_quantize")
        finally:
            runtime.close()
        self.assertTrue(transport.closed)
        self.assertTrue(all(client.closed for client in owned_clients.values()))

    def test_main_mro_explicit_cached_dma_covers_p2_and_p1_before_submit(self):
        parameters = load_v10_p3_dma_parameters(
            PARAM_ROOT / "manifest.json", PARAM_SHA)
        transport = A0004ChainTransport()
        owned_clients = clients()
        runtime = A0004MainRuntime(
            transport, contract(), MANIFEST_SHA, owned_clients,
            p3_dma_parameters=parameters, mixed_native_lib=None,
            activation_upload_backend="cached_dma")
        try:
            results = runtime.run(((0, image(1.0)), (1, image(2.0))),
                                  max_in_flight=1)
            self.assertEqual(len(results), 2)
            self.assertEqual(len(transport.cached_dma_calls), 4)
            self.assertEqual(transport.direct_quantize_calls, [])
            self.assertEqual(transport.legacy_array_uploads, [])
            events = transport.boundary_events
            p2_submit = events.index(("submit", 2))
            p1_submit = events.index(("submit", 1))
            self.assertEqual(sum(event[0] == "dma_complete"
                                 for event in events[:p2_submit]), 2)
            self.assertEqual(sum(event[0] == "dma_complete"
                                 for event in events[:p1_submit]), 4)
            p2_upload = results[0]["pair_timing"]["pl_events"][0]["timing"][
                "profile2_input_upload"]
            self.assertEqual(p2_upload["backend"], "cached_dma")
            self.assertFalse(p2_upload["direct_target"])
            self.assertEqual(p2_upload["driver_dma_ns"], 2000)
            p1_upload = results[0]["pair_timing"]["pl_events"][1]["timing"][
                "quantize_upload"]
            self.assertEqual(p1_upload["backend"], "cached_dma")
            self.assertEqual(p1_upload["driver_dma_ns"], 2000)
        finally:
            runtime.close()


if __name__ == "__main__":
    unittest.main()
