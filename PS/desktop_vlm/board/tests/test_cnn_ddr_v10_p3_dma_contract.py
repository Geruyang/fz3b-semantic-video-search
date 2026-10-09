import errno
import ctypes
import hashlib
import json
from pathlib import Path
import unittest

import numpy as np

import cnn_ddr_v10_p3_dma_contract as contract
import cnn_ddr_v10_p3_dma_runtime as runtime
import cnn_pipeline_v10_p3_dma_parameters as parameters
from cnn_v10_native_quant import V10NativeQuantWorkspace


PROJECT = Path(__file__).resolve().parents[3]
PARAM_ROOT = (PROJECT / "artifacts/board-debug-20261007/acceleration/host/"
              "cnn-v10.4-p3-dma-chain-parameters-001")
PARAM_SHA = "e285a08615111752f7c71b9541267a8a1f3b7062c9a8cbb36a7bb2b5a609d5c9"


class ContractTests(unittest.TestCase):
    def test_a0004_profiles_have_no_external_stage_ring(self):
        expected = (36864, 20480, 69632, 69632)
        for profile, arena in enumerate(expected):
            value = runtime.profile_contract(
                profile, runtime.PROFILE_MAX_BLOCKS[profile])
            self.assertEqual(value["arena_words"], arena)
            self.assertEqual(value["external_stage_ring_words"], 0)
            self.assertEqual(value["arena_words"],
                             2 * value["slot_words"] + 4096)
            self.assertEqual(value["output_offset_bytes"], 0)
        for profile in range(3):
            slot_bytes = runtime.PROFILE_SLOT_WORDS[profile] * 16
            self.assertEqual(runtime.profile_contract(
                profile, 1)["output_offset_bytes"], slot_bytes)
            self.assertEqual(runtime.profile_contract(
                profile, 2)["output_offset_bytes"], 0)
            self.assertEqual(runtime.profile_contract(
                profile, 3)["output_offset_bytes"], slot_bytes)
        self.assertEqual(runtime.profile_contract(
            3, 1)["output_offset_bytes"], 0)

    def test_a0004_combined_manifest_binds_internal_fifo_topology(self):
        loaded = parameters.load_v10_p3_dma_parameters(
            PARAM_ROOT / "manifest.json", PARAM_SHA)
        self.assertEqual(loaded["manifest_sha256"], PARAM_SHA)
        self.assertEqual(hashlib.sha256(loaded["params"]).hexdigest(),
                         parameters.P3_PARAMS_SHA256)
        manifest = json.loads((PARAM_ROOT / "manifest.json").read_text())
        self.assertFalse(manifest["deployment_ready"])
        topology = manifest["chain_contract"]["topology"]
        self.assertEqual(topology["stage_storage"], "internal_fifo_v1")
        self.assertEqual(topology["external_stage_ring_words"], 0)
        self.assertEqual(topology["activation_broker_clients_per_core"],
                         {"read": 2, "write": 2})
        for profile in manifest["chain_contract"]["profile_contracts"]:
            self.assertEqual(profile["external_stage_ring_words"], 0)
            self.assertNotIn("stage_ring_offsets_words", profile)
            rule = profile["output_offset_rule"]
            if profile["profile"] == 3:
                self.assertEqual(rule, {"kind": "fixed_slot0",
                                        "offset_words": 0})
            else:
                self.assertEqual(rule["kind"], "ping_pong_block_parity")
                self.assertEqual(rule["odd_block_count_offset_words"],
                                 profile["slot_words"])
            self.assertEqual(profile["full_count_output_offset_words"], 0)

    def test_old_fixed_slot0_manifest_is_rejected(self):
        old_root = (PROJECT / "artifacts/board-debug-20261007/acceleration/host/"
                    "cnn-v10.3-p3-dma-chain-parameters-001")
        old_sha = "0096fe12d3f570bc24ecd3bbd19d02fad38046757ba8ba507b2c7258b68a7560"
        with self.assertRaisesRegex(ValueError, "contract mismatch"):
            parameters.load_v10_p3_dma_parameters(
                old_root / "manifest.json", old_sha)

    def test_old_a0003_stage_ring_manifest_is_rejected(self):
        old_root = (PROJECT / "artifacts/board-debug-20261007/acceleration/host/"
                    "cnn-v10.3-p3-dma-chain-parameters-002")
        old_sha = "5c7f7aab2afd8aeffa8b47cf9c233cf3f86c054d78674a826af72274035b5ea2"
        with self.assertRaisesRegex(ValueError, "contract mismatch"):
            parameters.load_v10_p3_dma_parameters(
                old_root / "manifest.json", old_sha)

    def test_submission_uses_normal_parity_and_p3_fixed_slot0(self):
        allocations = {
            1: {"bytes": runtime.PROFILE_STRIDE_WORDS[0] * 3 * 16},
            2: {"bytes": runtime.PROFILE_ARENA_WORDS[0] * 16},
            3: {"bytes": runtime.PROFILE_ARENA_WORDS[0] * 16},
        }
        odd = runtime.validate_submission(allocations, 0, 3, 1, 2, 3)
        self.assertEqual(odd["output_a_offset_bytes"],
                         runtime.PROFILE_SLOT_WORDS[0] * 16)
        allocations[1]["bytes"] = runtime.PROFILE_STRIDE_WORDS[0] * 2 * 16
        even = runtime.validate_submission(allocations, 0, 2, 1, 2, 3)
        self.assertEqual(even["output_a_offset_bytes"], 0)

        allocations = {
            1: {"bytes": runtime.PROFILE_STRIDE_WORDS[3] * 16},
            2: {"bytes": runtime.PROFILE_ARENA_WORDS[3] * 16},
            3: {"bytes": runtime.PROFILE_ARENA_WORDS[3] * 16},
        }
        p3 = runtime.validate_submission(allocations, 3, 1, 1, 2, 3)
        self.assertEqual(p3["output_a_offset_bytes"], 0)

    def test_mapping_ownership_and_initialized_read(self):
        state = contract.ObjectState(8192)
        with self.assertRaises(contract.TransferContractError):
            state.begin_map(0, 4096, contract.ACCESS_READ)
        state.begin_map(0, 4096, contract.ACCESS_WRITE)
        self.assertFalse(state.can_pin_job())
        state.commit_write(0, 4096)
        state.end_map()
        self.assertTrue(state.can_pin_job())
        state.begin_map(0, 4096, contract.ACCESS_READ)
        state.end_map()

    def test_failed_direct_write_stays_uninitialized(self):
        state = contract.ObjectState(8192)
        state.begin_map(0, 4096, contract.ACCESS_WRITE)
        state.commit_write(0, 4096)
        state.end_map()
        self.assertTrue(state.covers(0, 4096))
        state.begin_map(0, 4096, contract.ACCESS_WRITE)
        state.end_map()
        self.assertFalse(state.covers(0, 4096))

    def test_copy_backend_requires_explicit_safe_fallback(self):
        caps = contract.CAP_CPU_WC_COPY | contract.CAP_DMAENGINE_COPY
        self.assertEqual(contract.choose_copy_backend(
            caps, contract.COPY_REQUIRE_DMAENGINE),
            contract.BACKEND_DMAENGINE)
        self.assertEqual(contract.choose_copy_backend(
            caps, contract.COPY_ALLOW_CPU_FALLBACK,
            dma_map_source=False), contract.BACKEND_CPU_WC)
        with self.assertRaises(contract.TransferContractError):
            contract.choose_copy_backend(
                caps, contract.COPY_REQUIRE_DMAENGINE,
                dma_map_destination=False)
        with self.assertRaises(contract.TransferContractError):
            contract.validate_copy(8192, 8192, 0, 2048, 4096,
                                   contract.COPY_ALLOW_CPU_FALLBACK,
                                   10, same_object=True)

    def test_cached_upload_contract_is_v2_capability_gated(self):
        expected = contract.validate_cached_dma_upload(
            8192, 0, 4096, 100, contract.CAP_CACHED_DMA_UPLOAD, 2)
        self.assertEqual(expected["bytes"], 4096)
        for version, caps in ((1, contract.CAP_CACHED_DMA_UPLOAD),
                              (2, contract.CAP_DMAENGINE_COPY)):
            with self.assertRaisesRegex(contract.TransferContractError,
                                        "ABI v2"):
                contract.validate_cached_dma_upload(
                    8192, 0, 4096, 100, caps, version)


class _FakeMap(bytearray):
    def __init__(self, size):
        super().__init__(size)
        self.closed = False

    def close(self):
        self.closed = True


class _FakeTransport(runtime.LinuxIoctlV10P3DmaTransport):
    def __init__(self):
        self.fd = 7
        self.closed = False
        self.quiesced = False
        self.allocations = {0x10001: {"bytes": 8192, "arena_index": 0},
                            0x10002: {"bytes": 8192, "arena_index": 0}}
        self.transfer_caps = {
            "caps": contract.CAP_WC_MMAP | contract.CAP_CPU_WC_COPY,
            "version": runtime.TRANSFER_ABI_VERSION,
            "page_size": 4096, "max_map_bytes": 8192,
            "max_copy_bytes": 8192, "max_timeout_ms": 1000,
        }
        self._cached_dma_poisoned = False
        self.calls = []
        self._next_map = None

        def factory(fd, size, flags, prot, offset):
            self.calls.append(("mmap", fd, size, flags, prot, offset))
            self._next_map = _FakeMap(size)
            return self._next_map
        self._mmap_factory = factory

    def _ioctl(self, request, raw=None):
        self.calls.append((request, bytes(raw) if raw is not None else None))
        if request == runtime.IOCTL_MAP_PREP:
            values = list(runtime._MAP.unpack(raw))
            values[4] = 9
            raw[:] = runtime._MAP.pack(*values)
        elif request == runtime.IOCTL_ARENA_COPY:
            values = list(runtime._COPY.unpack(raw))
            values[7] = contract.BACKEND_CPU_WC
            raw[:] = runtime._COPY.pack(*values)
        elif request == runtime.IOCTL_CACHED_DMA_UPLOAD:
            values = list(runtime._CACHED_UPLOAD.unpack(raw))
            self.cached_payload = ctypes.string_at(values[4], values[3])
            values[6] = contract.BACKEND_CACHED_DMA_UPLOAD
            values[7] = 2
            values[9] = 123456
            raw[:] = runtime._CACHED_UPLOAD.pack(*values)


class RuntimeTests(unittest.TestCase):
    def test_transfer_v1_remains_valid_for_direct_wc_but_not_cached_dma(self):
        transport = _FakeTransport()
        transport.transfer_caps["version"] = 1
        transport.transfer_caps["caps"] = contract.CAP_WC_MMAP
        self.assertTrue(transport._direct_capable())
        self.assertFalse(transport._cached_dma_capable())
        readonly = np.arange(8, dtype="<i2")
        readonly.flags.writeable = False
        with self.assertRaisesRegex(Exception, "ABI v2"):
            transport.cached_dma_upload(0x10001, 0, readonly)

    def test_cached_dma_uapi_is_64_bytes_and_retains_exact_payload(self):
        self.assertEqual(runtime._CACHED_UPLOAD.size, 64)
        transport = _FakeTransport()
        transport.transfer_caps["caps"] |= contract.CAP_CACHED_DMA_UPLOAD
        source = np.arange(2048, dtype="<i2")
        source.flags.writeable = False
        result = transport.cached_dma_upload(
            0x10001, 0, source, timeout_ms=100)
        self.assertEqual(transport.cached_payload, source.tobytes())
        self.assertEqual(result["backend"], "cached_dma")
        self.assertEqual(result["backend_id"], 3)
        self.assertEqual(result["segment_count"], 2)
        self.assertEqual(result["driver_dma_ns"], 123456)

    def test_cached_quantize_restores_workspace_after_proven_success(self):
        transport = _FakeTransport()
        transport.transfer_caps["caps"] |= contract.CAP_CACHED_DMA_UPLOAD
        workspace = V10NativeQuantWorkspace(0, 2, 32)
        source = np.zeros((1, 2, 32, 32), dtype=np.float32)
        owned = workspace._output_i16
        result = transport.quantize_upload_cached_dma(
            0x10001, 0, source, 0.001, workspace)
        self.assertEqual(result["backend"], "cached_dma")
        self.assertFalse(workspace._poisoned)
        self.assertTrue(owned.flags.writeable)
        self.assertIs(workspace._output_i16, owned)

    def test_cached_dma_failure_poison_retains_readonly_workspace_buffer(self):
        transport = _FakeTransport()
        transport.transfer_caps["caps"] |= contract.CAP_CACHED_DMA_UPLOAD
        workspace = V10NativeQuantWorkspace(0, 2, 32)
        source = np.zeros((1, 2, 32, 32), dtype=np.float32)
        quarantined_source = workspace._output_i16
        original_ioctl = transport._ioctl

        def fail_cached(request, raw=None):
            if request == runtime.IOCTL_CACHED_DMA_UPLOAD:
                raise OSError(errno.ETIMEDOUT, "unknown DMA outcome")
            return original_ioctl(request, raw)

        transport._ioctl = fail_cached
        with self.assertRaises(OSError):
            transport.quantize_upload_cached_dma(
                0x10001, 0, source, 0.001, workspace)
        self.assertTrue(workspace._poisoned)
        self.assertFalse(quarantined_source.flags.writeable)
        self.assertIs(workspace._output_i16, quarantined_source)
        self.assertTrue(transport._cached_dma_poisoned)
        self.assertTrue(any(item is quarantined_source
                            for item in runtime._QUARANTINED_CACHED_DMA_SOURCES))
        with self.assertRaisesRegex(RuntimeError, "poisoned"):
            workspace.quantize_chw_to_hcw(source, 0.001)

    def test_direct_public_cached_upload_failure_retains_source_and_poison(self):
        transport = _FakeTransport()
        transport.transfer_caps["caps"] |= contract.CAP_CACHED_DMA_UPLOAD
        source = np.arange(2048, dtype="<i2")
        source.flags.writeable = False

        def fail(request, raw=None):
            raise OSError(errno.EIO, "provider outcome unknown")

        transport._ioctl = fail
        with self.assertRaises(OSError):
            transport.cached_dma_upload(0x10001, 0, source)
        self.assertTrue(transport._cached_dma_poisoned)
        self.assertTrue(any(item is source
                            for item in runtime._QUARANTINED_CACHED_DMA_SOURCES))
        with self.assertRaisesRegex(Exception, "poisoned"):
            transport.cached_dma_upload(0x10001, 0, source)

    def test_direct_upload_is_one_copy_then_commit(self):
        transport = _FakeTransport()
        array = np.arange(2048, dtype=np.uint16)
        transport.upload_array(0x10001, 0, array)
        self.assertTrue(transport._next_map.closed)
        self.assertEqual(bytes(transport._next_map), array.tobytes())
        requests = [call[0] for call in transport.calls
                    if isinstance(call[0], int)]
        self.assertIn(runtime.IOCTL_MAP_PREP, requests)
        self.assertIn(runtime.IOCTL_SYNC_RANGE, requests)

    def test_unaligned_upload_uses_legacy_before_map_ticket(self):
        transport = _FakeTransport()
        array = np.arange(8, dtype=np.uint16)
        legacy = []
        original = runtime.LinuxIoctlV10P3A0004Transport.upload_array
        try:
            runtime.LinuxIoctlV10P3A0004Transport.upload_array = \
                lambda self, h, o, a: legacy.append((h, o, a.nbytes))
            transport.upload_array(0x10001, 0, array)
        finally:
            runtime.LinuxIoctlV10P3A0004Transport.upload_array = original
        self.assertEqual(legacy, [(0x10001, 0, 16)])
        self.assertFalse(any(call[0] == runtime.IOCTL_MAP_PREP
                             for call in transport.calls))

    def test_copy_reports_actual_backend(self):
        transport = _FakeTransport()
        result = transport.copy_arena(
            0x10001, 0, 0x10002, 0, 4096, timeout_ms=100,
            allow_cpu_fallback=True)
        self.assertEqual(result["backend"], contract.BACKEND_CPU_WC)

    def test_direct_download_pins_map_before_read_sync(self):
        transport = _FakeTransport()
        output = np.empty(2048, dtype=np.uint16)
        transport.download_into(0x10001, 0, output)
        mmap_index = next(index for index, call in enumerate(transport.calls)
                          if call[0] == "mmap")
        sync_index = next(index for index, call in enumerate(transport.calls)
                          if call[0] == runtime.IOCTL_SYNC_RANGE)
        self.assertLess(mmap_index, sync_index)
        self.assertTrue(transport._next_map.closed)

    def test_fused_quantization_writes_directly_to_mapping_then_commits(self):
        transport = _FakeTransport()
        workspace = V10NativeQuantWorkspace(0, 2, 32)
        source = np.linspace(-0.2, 0.2, 2 * 32 * 32,
                             dtype=np.float32).reshape(1, 2, 32, 32)
        expected = workspace.quantize_chw_to_hcw(source, 0.001).copy()
        result = transport.quantize_upload_into(
            0x10001, 0, source, 0.001, workspace)
        actual = np.frombuffer(bytes(transport._next_map), dtype="<i2").reshape(
            workspace.hcw_shape)
        self.assertTrue(np.array_equal(actual, expected))
        self.assertEqual(result["backend"], "wc_mmap_direct_quantize")
        self.assertTrue(transport._next_map.closed)
        requests = [call[0] for call in transport.calls
                    if isinstance(call[0], int)]
        self.assertEqual(requests.count(runtime.IOCTL_SYNC_RANGE), 1)

    def test_failed_fused_quantization_is_not_published(self):
        class FailingWorkspace(object):
            hcw_shape = (32, 2, 32)

            def quantize_chw_to_hcw_into(self, value, scale, output, label):
                output.fill(7)
                raise RuntimeError("conversion failed")

        transport = _FakeTransport()
        with self.assertRaisesRegex(RuntimeError, "conversion failed"):
            transport.quantize_upload_into(
                0x10001, 0, np.empty((1, 2, 32, 32), dtype=np.float32),
                0.001, FailingWorkspace())
        requests = [call[0] for call in transport.calls
                    if isinstance(call[0], int)]
        self.assertNotIn(runtime.IOCTL_SYNC_RANGE, requests)
        self.assertTrue(transport._next_map.closed)


if __name__ == "__main__":
    unittest.main()
