"""Offline v5 split and fake-runtime contract checks."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

import numpy as np

from desktop_vlm.board import cnn_ddr_v5_split as split
from desktop_vlm.board import cnn_ddr_v5_runtime as runtime
from desktop_vlm.board import cnn_ddr_v5_run as run_cli
from desktop_vlm.board import benchmark_cnn_ddr_v5 as benchmark


ROOT = Path(__file__).resolve().parents[3]
SOURCE_MODEL = ROOT / "artifacts/board-debug-20261004/host/s1-onnx-001/mobileclip_s1_image.onnx"
FIXTURE_ROOT = ROOT / "artifacts/board-debug-20261005/acceleration/host"


class V5SplitTests(unittest.TestCase):
    def test_split_bundle_replays_all_original_boundaries_exactly(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = split.build(SOURCE_MODEL, tmp, cases=1, threads=1)
            manifest = json.loads((Path(tmp) / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(report["manifest_sha256"], split.sha256(Path(tmp) / "manifest.json"))
            self.assertEqual(manifest["status"], "V5_FOUR_PS_SPLITS_ORIGINAL_ONNX_VALIDATED_NOT_PL")
            self.assertTrue(manifest["checks"]["split_boundaries_max_abs_zero"])
            self.assertEqual(set(manifest["models"]), {"stem-prefix", "network1-bridge", "network3-bridge", "suffix"})
            for check in manifest["cases"][0]["boundary_checks"].values():
                self.assertEqual(check["max_abs"], 0.0)
        
    def test_network3_bridge_keeps_complete_se_chain_and_suffix_starts_after_n4(self):
        self.assertTrue(any("/se/ReduceMean" in name for name in split.NETWORK3_REQUIRED_NODES))
        self.assertTrue(any("/se/fc1/Conv" in name for name in split.NETWORK3_REQUIRED_NODES))
        self.assertTrue(any("/se/fc2/Conv" in name for name in split.NETWORK3_REQUIRED_NODES))
        self.assertTrue(any("/se/gate/Sigmoid" in name for name in split.NETWORK3_REQUIRED_NODES))
        self.assertEqual(split.BOUNDARIES["n4_output"],
                         "/image_encoder/model/network.4/network.4.19/Add_output_0")
        self.assertEqual(split.BOUNDARIES["feature_output"], "features")


class V5FakeContractTests(unittest.TestCase):
    def test_profile_mapping_strides_and_slots_match_abi5(self):
        expected = {
            2: (64, 64, 4, 12193, 32768),
            0: (128, 32, 12, 22433, 16384),
            1: (256, 16, 20, 61057, 8192),
        }
        self.assertEqual({p: (s.channels, s.width, s.max_blocks,
                              s.block_stride_words, s.slot_words)
                          for p, s in runtime.PROFILE_SPECS.items()}, expected)
        self.assertEqual(runtime.PROFILE_ORDER, (2, 0, 1))
        self.assertEqual(runtime._IDENTITY_STRUCT.size, 136)

    def test_fzv5_identity_unpack_keeps_reserved_word_and_manifest_tail(self):
        words = [runtime.LinuxIoctlV5Transport.CORE_ID,
                 runtime.LinuxIoctlV5Transport.CORE_ABI,
                 runtime.LinuxIoctlV5Transport.GUARD_CAPS, 5,
                 runtime.LinuxIoctlV5Transport.CAPS, 40, 128, 1, 3,
                 12, 20, 4, 128, 256, 64, 32, 16, 64,
                 22433, 61057, 12193, 0, 0x3ff00000, 0,
                 0, 0, 0, 0, 0, 0, 0, 0]
        identity = runtime._identity_dict(tuple(words))
        self.assertEqual(identity["reserved0"], 0)
        self.assertEqual(identity["block_stride_words"], (22433, 61057, 12193))
        self.assertEqual(identity["parameter_manifest_words"], (0,) * 8)

    def test_ioctl_requests_match_frozen_v5_uapi_numbers_and_struct_sizes(self):
        self.assertEqual(runtime.IOCTL_REQUESTS, {
            "GET_IDENTITY": 0x80885840,
            "ALLOC": 0xC0205841,
            "FREE": 0x40085842,
            "UPLOAD": 0x40205843,
            "DOWNLOAD": 0x40205844,
            "SUBMIT": 0x40105845,
            "GET_STATUS": 0x803C5846,
            "QUIESCE": 0x00005847,
        })
        self.assertEqual(runtime._ALLOC_STRUCT.size, 32)
        self.assertEqual(runtime._TRANSFER_STRUCT.size, 32)
        self.assertEqual(runtime._SUBMIT_STRUCT.size, 16)
        self.assertEqual(runtime._STATUS_STRUCT.size, 60)

    def test_legacy_v4_fixture_is_rejected_before_transport_allocation(self):
        transport = runtime.FakeV5Transport()
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                runtime.V5ProfileAdapter(transport, fixture_root=tmp)
        self.assertEqual(transport.alloc_calls, [])

    def test_fake_profiles_keep_upload_once_two_slot_offsets_and_quiesce_cleanup(self):
        transport = runtime.FakeV5Transport()
        adapter = runtime.V5ProfileAdapter(transport, fixture_root=FIXTURE_ROOT)
        for profile in runtime.PROFILE_ORDER:
            params = adapter.parameter_handles[profile]
            activations = adapter.activation_handles[profile]
            self.assertNotEqual(params, activations)
            spec = runtime.PROFILE_SPECS[profile]
            output = adapter.run(profile, np.zeros((1, spec.channels, spec.width,
                                                     spec.width), dtype="<i2"),
                                 block_count=spec.max_blocks)
            self.assertEqual(output["activation"].nbytes, spec.activation_bytes)
            self.assertEqual(transport.arena_indices[params], 1)
            self.assertEqual(transport.arena_indices[activations], 0)
        odd_spec = runtime.PROFILE_SPECS[2]
        with self.assertRaisesRegex(ValueError, "complete pinned parameter profile"):
            adapter.run(2, np.zeros((1, 64, 64, 64), dtype="<i2"), block_count=3)
        uploads = [c for c in transport.calls if c[0] == "upload" and c[1] in adapter.parameter_handles.values()]
        self.assertEqual(len(uploads), 3)
        self.assertTrue(all(item["parameter_arena_index"] == 1 and
                            item["activation_arena_index"] == 0
                            for item in adapter.parameter_upload_receipts))
        self.assertEqual(adapter.close(), {"quiesce_confirmed": True,
                                           "all_handles_freed": True,
                                           "transport_closed": True})
        names = [c[0] for c in transport.calls]
        self.assertLess(names.index("quiesce"), names.index("free"))

        partial = runtime.FakeV5Transport()
        params = partial.alloc(odd_spec.block_stride_words * 16 * 3, 16, flags=1)
        activations = partial.alloc(odd_spec.activation_bytes * 2, 16, flags=1)
        partial.upload(activations, 0, bytes(odd_spec.activation_bytes))
        partial.submit(2, 3, params, activations)
        partial.wait_complete(2, 1.0)
        partial.download(activations, odd_spec.activation_bytes, odd_spec.activation_bytes)
        self.assertIn(("download", activations, odd_spec.activation_bytes,
                       odd_spec.activation_bytes), partial.calls)

    def test_low_only_runtime_uses_distinct_low_handles_for_all_profiles(self):
        transport = runtime.FakeV5Transport(caps=0x5)
        adapter = runtime.V5ProfileAdapter(transport, fixture_root=FIXTURE_ROOT)
        for profile in runtime.PROFILE_ORDER:
            self.assertEqual(transport.arena_indices[adapter.parameter_handles[profile]], 0)
            self.assertEqual(transport.arena_indices[adapter.activation_handles[profile]], 0)
        self.assertTrue(all(call[2] == 1 for call in transport.alloc_calls))
        self.assertTrue(all(item["parameter_arena_index"] == 0 and
                            item["activation_arena_index"] == 0
                            for item in adapter.parameter_upload_receipts))
        adapter.close()

    def test_full_runtime_executes_ps_and_pl_stages_in_frozen_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            adapter = runtime.V5ProfileAdapter(runtime.FakeV5Transport(), FIXTURE_ROOT)
            order = []

            def stage(name, shape):
                def run(_value):
                    order.append(name)
                    return np.zeros(shape, dtype=np.float32)
                return run

            runner = runtime.V5FullRuntime(
                adapter,
                stage("stem-prefix", (1, 64, 64, 64)),
                stage("network1-bridge", (1, 128, 32, 32)),
                stage("network3-se-bridge", (1, 256, 16, 16)),
                stage("suffix", (1, 512)))
            report = runner.run_frame(np.zeros((1, 3, 256, 256), dtype=np.float32))
            self.assertEqual(order, ["stem-prefix", "network1-bridge",
                                     "network3-se-bridge", "suffix"])
            self.assertEqual(report["features"].shape, (1, 512))
            self.assertEqual(len(report["driver_completions"]), 3)
            self.assertTrue({"n0_input_quantize", "n2_input_quantize", "n4_input_quantize",
                             "network3_se_bridge", "n4_output_dequantize"}.issubset(
                                 report["timing_ms"]))
            pipeline_results = runner.run([(7, np.zeros((1, 3, 256, 256), dtype=np.float32))],
                                          [7], queue_capacity=1, max_in_flight=1)
            self.assertEqual(len(pipeline_results), 1)
            self.assertEqual(pipeline_results[0].frame_id, 7)
            self.assertEqual(pipeline_results[0].value["features"].shape, (512,))
            adapter.close()

    def test_feature_files_are_sorted_and_sha_pinned(self):
        class Result(object):
            def __init__(self, frame_id, value):
                self.frame_id = frame_id
                self.value = {"features": value}

        with tempfile.TemporaryDirectory() as tmp:
            results = [Result(9, np.zeros(512, dtype=np.float32)),
                       Result(2, np.ones(512, dtype=np.float32))]
            files = run_cli._write_features(tmp, results)
            self.assertEqual([record["frame_id"] for record in files], [2, 9])
            self.assertTrue(all(record["bytes"] == 2048 and len(record["sha256"]) == 64
                                for record in files))

    def test_benchmark_keeps_three_warmups_out_of_thirty_frame_batch_wall(self):
        class Result(object):
            def __init__(self, frame_id, run_id):
                self.frame_id = frame_id
                self.run_id = run_id
                self.value = {"features": np.zeros(512, dtype=np.float32),
                              "timing_ms": {"components_sum_is_not_wall": 10000.0},
                              "driver_completions": []}
                self.admission_start_ms = 1.0
                self.admission_wait_ms = 2.0
                self.submit_ms = 3.0
                self.complete_ms = 8.0
                self.end_to_end_ms = 7.0
                self.components_ms = {"prefix": 3000.0, "backend": 4000.0,
                                      "suffix": 3000.0}
                self.correct = True

        class FakeRuntime(object):
            def __init__(self):
                self.calls = []
                self.pipeline = type("Pipeline", (), {
                    "_last_batch_start": None, "_last_batch_end": None})()
                self.options = None

            def run(self, items, frame_ids, **kwargs):
                self.calls.append(list(frame_ids))
                if self.options is None:
                    self.options = dict(kwargs)
                elif kwargs:
                    raise ValueError("pipeline options are frozen after first run")
                if len(items) == 3:
                    import time
                    time.sleep(0.02)
                else:
                    import time
                    self.pipeline._last_batch_start = time.perf_counter()
                    time.sleep(0.05)
                    self.pipeline._last_batch_end = time.perf_counter()
                run_id = "warm" if len(items) == 3 else "measure"
                return [Result(frame_id, run_id) for frame_id in frame_ids]

        runtime_fake = FakeRuntime()
        measured = benchmark.run_fixed_batches(
            runtime_fake,
            [(i, np.zeros((1, 3, 256, 256), dtype=np.float32)) for i in range(33)],
            queue_capacity=2, max_in_flight=2, run_timeout_s=30.0, cleanup_timeout_s=5.0)
        self.assertEqual([len(call) for call in runtime_fake.calls], [3, 30])
        self.assertEqual(measured["warmup"]["frames_completed"], 3)
        self.assertEqual(measured["measurement"]["frames_completed"], 30)
        self.assertGreater(measured["measurement"]["batch_wall_ms"], 0)
        self.assertEqual(measured["measurement"]["pipeline_run_id"], "measure")
        self.assertEqual(measured["measurement"]["batch_wall_source"],
                         "BoundedPipeline._last_batch_start/_last_batch_end")
        self.assertEqual(measured["measurement"]["throughput_fps"],
                         30000.0 / measured["measurement"]["batch_wall_ms"])
        self.assertLess(measured["measurement"]["batch_wall_ms"], 10000.0)
        self.assertLessEqual(measured["measurement"]["batch_wall_ms"],
                             measured["measurement"]["outer_call_wall_ms"])
        frame = measured["measurement"]["frames"][0]
        self.assertEqual(frame["arrival_ms"], 1.0)
        self.assertEqual(frame["admitted_ms"], 3.0)
        self.assertEqual(frame["submit_ms"], 3.0)
        self.assertEqual(frame["complete_ms"], 8.0)
        self.assertEqual(frame["end_to_end_ms"], 7.0)
        self.assertAlmostEqual(frame["event_monotonic_s"]["arrival_monotonic_s"],
                               measured["measurement"]["batch_wall_start_monotonic_s"] + 0.001)
        self.assertEqual(runtime_fake.options["max_in_flight"], 2)

    def test_missing_or_unpinned_v5_scales_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = FIXTURE_ROOT / runtime.V5_BUNDLE_DIRECTORY
            target = Path(tmp) / runtime.V5_BUNDLE_DIRECTORY
            shutil.copytree(source, target)
            scale_path = target / "scale-manifest.json"
            raw = scale_path.read_bytes()
            scale_path.write_bytes(raw[:-1] + (b" " if raw[-1:] != b" " else b"\n"))
            transport = runtime.FakeV5Transport()
            with self.assertRaisesRegex(ValueError, "scale manifest SHA256/size mismatch"):
                runtime.V5ProfileAdapter(transport, fixture_root=tmp)
            self.assertEqual(transport.alloc_calls, [])

    def test_real_bundle_parameter_and_boundary_scales_are_fully_bound(self):
        bundle = runtime._read_v5_bundle(FIXTURE_ROOT)
        self.assertEqual(bundle["manifest_sha256"], runtime.V5_BUNDLE_MANIFEST_SHA256)
        self.assertEqual(bundle["scale_manifest_sha256"], runtime.V5_SCALE_MANIFEST_SHA256)
        for profile, contract in bundle["contracts"].items():
            blocks = bundle["scale_manifest"]["profiles"][str(profile)]["per_block"]
            self.assertEqual(contract["input_scale"], blocks[0]["scales"]["input"])
            self.assertEqual(contract["output_scale"], blocks[-1]["scales"]["add"])
            for index in range(1, len(blocks)):
                self.assertEqual(blocks[index]["scales"]["input"],
                                 blocks[index - 1]["scales"]["add"])

    def test_quiesce_failure_keeps_handles_and_closes_transport_without_free(self):
        transport = runtime.FakeV5Transport(quiesce_error=RuntimeError("poisoned"))
        adapter = runtime.V5ProfileAdapter(transport, FIXTURE_ROOT)
        owned = list(adapter.handles)
        with self.assertRaisesRegex(RuntimeError, "poisoned"):
            adapter.close()
        self.assertEqual(adapter.handles, owned)
        self.assertEqual([c for c in transport.calls if c[0] == "free"], [])
        self.assertTrue(transport.closed)

    def test_generated_model_bundle_is_bound_to_exact_manifest_and_model_hashes(self):
        root = ROOT / "artifacts/board-debug-20261005/acceleration/host/v5-runtime-models-001"
        manifest_sha = runtime._sha256_file(str(root / "manifest.json"))
        bundle = runtime.load_v5_split_contracts(root, manifest_sha)
        self.assertEqual(set(bundle["models"]),
                         {"stem-prefix", "network1-bridge", "network3-bridge", "suffix"})

    def test_generated_model_contract_shapes_are_ready_for_ort_client(self):
        root = ROOT / "artifacts/board-debug-20261005/acceleration/host/v5-runtime-models-001"
        manifest_sha = runtime._sha256_file(str(root / "manifest.json"))
        bundle = runtime.load_v5_split_contracts(root, manifest_sha)
        for model in bundle["models"].values():
            for tensor in model["contract"]["inputs"] + model["contract"]["outputs"]:
                self.assertIsInstance(tensor["shape"], tuple)


if __name__ == "__main__":
    unittest.main()
