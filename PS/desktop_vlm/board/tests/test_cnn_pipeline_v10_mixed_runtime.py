import json
import os
import pathlib
import sys
import tempfile
import types
import unittest
from unittest import mock

import numpy as np

BOARD = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BOARD))
import cnn_pipeline_v10_mixed_runtime as mixed


class MixedRuntimeTests(unittest.TestCase):
    @staticmethod
    def _sha(raw):
        import hashlib
        return hashlib.sha256(raw).hexdigest()

    def test_int16_activation_copy_has_independent_storage(self):
        original = mixed.Int16HCWActivation(
            np.arange(12, dtype="<i2").reshape(2, 3, 2), 0, .125,
            (1, 3, 2, 2))
        copied = original.copy()
        copied.payload[0, 0, 0] = -7
        self.assertNotEqual(original.payload[0, 0, 0], copied.payload[0, 0, 0])

    def test_rejected_n1_candidate_is_fail_closed_before_loader(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "candidate.json")
            with open(path, "w") as stream:
                json.dump({"status": "FAIL"}, stream)
            with mock.patch.object(mixed, "load_shm_split_clients") as loader:
                with self.assertRaisesRegex(ValueError, "schema/status mismatch"):
                    mixed.build_v10_mixed_components(
                        root, "manifest", "0" * 64, "runner",
                        n1_manifest=path)
                loader.assert_not_called()

    def test_n1_profile_boundary_bypasses_only_dequant_then_quant(self):
        class Workspace(object):
            def __init__(self):
                self.quantized = self.dequantized = 0

            def quantize_chw_to_hcw(self, value, scale, label):
                self.quantized += 1
                return np.zeros((64, 64, 64), dtype="<i2")

            def dequantize_hcw_to_chw(self, value, scale, label):
                self.dequantized += 1
                return np.zeros((1, 128, 32, 32), dtype="<f4")

        class Transport(object):
            def submit(self, *args):
                return {"submitted": True}

            def wait_complete(self, profile, timeout):
                return {"profile": profile}

        runtime = object.__new__(mixed.V10MixedBoundaryMixin)
        runtime.active_quantized_partitions = ("n1",)
        runtime.contract = {"profiles": {
            2: {"input_scale": .25, "output_scale": .125},
            0: {"input_scale": .0625, "output_scale": .03125}}}
        p2a, p2b, p0a, p0b = Workspace(), Workspace(), Workspace(), Workspace()
        runtime.workspaces = {2: (p2a, p2b), 0: (p0a, p0b)}
        runtime.arena_handles = {2: (20, 21), 0: (10, 11)}
        runtime.parameter_handles = {2: 2, 0: 0}
        runtime.transport = Transport()
        runtime.timeout_s = 1.0
        runtime._upload_array = lambda handle, value: None
        runtime._download_array = lambda handle, offset, target: target.fill(3)
        left, right, p2 = runtime._run_profile(
            2, np.zeros((1, 64, 64, 64), dtype="<f4"),
            np.zeros((1, 64, 64, 64), dtype="<f4"))
        self.assertIsInstance(left, mixed.Int16HCWActivation)
        self.assertEqual(left.scale, .125)
        self.assertTrue(p2["int16_boundary_bypass"]["dequantize_bypassed"])
        self.assertEqual((p2a.dequantized, p2b.dequantized), (0, 0))
        n1_left = mixed.Int16HCWActivation(
            np.zeros((32, 128, 32), dtype="<i2"), 0, .0625,
            (1, 128, 32, 32))
        n1_right = n1_left.copy()
        out_left, out_right, p0 = runtime._run_profile(0, n1_left, n1_right)
        self.assertEqual(out_left.shape, (1, 128, 32, 32))
        self.assertTrue(p0["int16_boundary_bypass"]["quantize_bypassed"])
        self.assertEqual((p0a.quantized, p0b.quantized), (0, 0))

    def test_n1_profile_rejects_nonidentical_logical_scale(self):
        runtime = object.__new__(mixed.V10MixedBoundaryMixin)
        runtime.active_quantized_partitions = ("n1",)
        runtime.contract = {"profiles": {0: {"input_scale": .0625}}}
        runtime.workspaces = {0: (object(), object())}
        bad = mixed.Int16HCWActivation(
            np.zeros((32, 128, 32), dtype="<i2"), 0,
            np.nextafter(.0625, 1.0), (1, 128, 32, 32))
        with self.assertRaisesRegex(ValueError, "exact native N1"):
            runtime._run_profile(0, bad, bad.copy())

    def test_missing_native_library_is_fail_closed(self):
        with mock.patch.object(mixed, "load_shm_split_clients") as loader:
            with self.assertRaisesRegex(ValueError, "does not exist"):
                mixed.build_v10_mixed_components(
                    ".", "manifest", "0" * 64, "runner",
                    native_lib="definitely-missing.so")
            loader.assert_not_called()

    def test_fp32_shared_selection_has_no_active_quantized_partition(self):
        sentinel = {"suffix": object()}
        with mock.patch.object(
                mixed, "load_shm_split_clients",
                return_value=(sentinel, "1" * 64)):
            clients, identity, kwargs, evidence = mixed.build_v10_mixed_components(
                ".", "manifest", "1" * 64, "runner", threads=3)
        self.assertIs(clients, sentinel)
        self.assertEqual(identity, "1" * 64)
        self.assertEqual(evidence["active_quantized_partitions"], [])
        self.assertIsNone(kwargs["mixed_native_lib"])
        self.assertTrue(all(item["precision"] == "FP32"
                            for item in evidence["partition_selection"].values()))

    def test_partition_thread_map_is_forwarded_and_recorded(self):
        selected = {"stem-prefix": 1, "network1-bridge": 1,
                    "network3-bridge": 1, "suffix": 2}
        sentinel = {"suffix": object()}
        with mock.patch.object(
                mixed, "load_shm_split_clients",
                return_value=(sentinel, "1" * 64)) as loader:
            clients, identity, kwargs, evidence = mixed.build_v10_mixed_components(
                ".", "manifest", "1" * 64, "runner", threads=3,
                partition_threads=selected)
        self.assertIs(clients, sentinel)
        self.assertEqual(identity, "1" * 64)
        self.assertEqual(evidence["partition_threads"], selected)
        loader.assert_called_once_with(
            ".", "runner", "manifest", "1" * 64, threads=3,
            model_overrides=None, partition_threads=selected)

    def test_suffix_selection_activates_only_verified_override(self):
        with tempfile.TemporaryDirectory() as root:
            model_root = os.path.join(root, "models")
            os.mkdir(model_root)
            source = b"source suffix"
            candidate = b"candidate suffix"
            optimized = b"target optimized suffix"
            with open(os.path.join(model_root, "suffix.onnx"), "wb") as stream:
                stream.write(source)
            records = {}
            payloads = {
                "host-profile.json": b"{}",
                "host-receipt.json": json.dumps({"status": "PASS"}).encode(),
                "target-result.json": json.dumps({
                    "status": "PASS_TARGET_ORT116_ENGINEERING_GATE",
                    "candidate_gate": True,
                    "candidate_sha256": self._sha(candidate)}).encode(),
                "target-wrapper.json": b"{}",
                "target-profile-receipt.json": json.dumps({
                    "status": "PASS_CANDIDATE_PROFILE_AND_ENGINEERING_ERROR_GATE",
                    "candidate_sha256": self._sha(candidate)}).encode(),
                "target-profile-wrapper.json": b"{}",
                "target-profile-analysis.json": b"{}",
                "target-kernel-classification.json": json.dumps({
                    "status": "PASS_TARGET_ORT_INTEGER_KERNELS_CONFIRMED",
                    "candidate_sha256": self._sha(candidate),
                    "optimized_model_sha256": self._sha(optimized),
                    "integer_kernel_count": 11, "qlinear_conv_count": 5,
                    "qlinear_matmul_count": 6}).encode(),
                "target-optimized.onnx": optimized,
            }
            for name, raw in payloads.items():
                with open(os.path.join(root, name), "wb") as stream:
                    stream.write(raw)
                records[name] = {"path": name, "bytes": len(raw),
                                 "sha256": self._sha(raw)}
            with open(os.path.join(root, "candidate.onnx"), "wb") as stream:
                stream.write(candidate)
            manifest = {
                "schema": "cnn-v10.1-suffix-w8a8-selection-v2", "status": "PASS",
                "source_model_sha256": self._sha(source),
                "candidate": {"path": "candidate.onnx", "bytes": len(candidate),
                              "sha256": self._sha(candidate), "precision": "mixed"},
                "target_integer_kernel_contract": {
                    "kernel_count": 11, "qlinear_conv_count": 5,
                    "qlinear_matmul_count": 6,
                    "provider": "CPUExecutionProvider"},
                "evidence": {
                    "host_profile": records["host-profile.json"],
                    "host_receipt": records["host-receipt.json"],
                    "target_result": records["target-result.json"],
                    "target_wrapper_receipt": records["target-wrapper.json"],
                    "target_profile_receipt": records["target-profile-receipt.json"],
                    "target_profile_wrapper_receipt": records["target-profile-wrapper.json"],
                    "target_profile_analysis": records["target-profile-analysis.json"],
                    "target_kernel_classification": records["target-kernel-classification.json"],
                    "target_optimized_model": records["target-optimized.onnx"],
                }}
            selection = os.path.join(root, "selection.json")
            with open(selection, "w") as stream:
                json.dump(manifest, stream)
            with mock.patch.object(
                    mixed, "load_shm_split_clients",
                    return_value=({"suffix": object()}, "2" * 64)) as loader:
                unused_clients, unused_identity, kwargs, evidence = (
                    mixed.build_v10_mixed_components(
                        model_root, "manifest", "2" * 64, "runner",
                        suffix_candidate=selection))
            self.assertEqual(evidence["active_quantized_partitions"], ["suffix"])
            self.assertEqual(kwargs["active_quantized_partitions"], ("suffix",))
            override = loader.call_args.kwargs["model_overrides"]["suffix"]
            self.assertEqual(override["sha256"], self._sha(candidate))

    def test_frozen_n1_selection_replaces_only_network1_client(self):
        project = BOARD.parents[1]
        selection = (project / "artifacts/board-debug-20261007/acceleration/host/"
                     "cnn-v10-n1-native-selection-001/selection.json")
        model_root = (project / "artifacts/board-debug-20261006/acceleration/host/"
                      "network10-v10.1-release-bundle-003/models")
        if not selection.is_file() or not model_root.is_dir():
            self.skipTest("frozen N1 selection fixture is unavailable")

        class OldClient(object):
            def __init__(self):
                self.closed = False

            def close(self):
                self.closed = True

        old = OldClient()
        clients = {"stem-prefix": object(), "network1-bridge": old,
                   "network3-bridge": object(), "suffix": object()}
        native = object()
        import cnn_v10_n1_native_ctypes as ctypes_module
        with mock.patch.object(ctypes_module, "CtypesN1NativeClient",
                               return_value=native), mock.patch.object(
                mixed, "load_shm_split_clients",
                return_value=(clients, "3" * 64)):
            actual, unused_identity, kwargs, evidence = (
                mixed.build_v10_mixed_components(
                    os.fspath(model_root), "manifest", "3" * 64, "runner",
                    n1_manifest=os.fspath(selection)))
        self.assertIs(actual["network1-bridge"], native)
        self.assertTrue(old.closed)
        self.assertEqual(evidence["active_quantized_partitions"], ["n1"])
        self.assertEqual(kwargs["active_quantized_partitions"], ("n1",))
        self.assertEqual(evidence["partition_selection"]["network1-bridge"]
                         ["selected_backend"], "native-w8a16-acc32")


if __name__ == "__main__":
    unittest.main()
