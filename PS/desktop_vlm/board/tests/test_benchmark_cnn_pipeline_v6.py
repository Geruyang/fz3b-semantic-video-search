"""Tests for v6 fixed-batch timing and latency semantics."""

import unittest

import numpy as np

from desktop_vlm.board.benchmark_cnn_pipeline_v6 import (
    build_board_report,
    run_fixed_batches,
)


class Result(object):
    def __init__(self, frame_id, base):
        self.frame_id = frame_id
        self.tag = type("Tag", (), {"generation": 9,
                                     "sequence_index": int(base)})()
        self.arrival_ms = base
        self.admitted_ms = base + 2.0
        self.admission_wait_ms = 2.0
        self.complete_ms = base + 12.0
        self.compute_ready_ms = base + 9.0
        self.output_start_ms = base + 10.0
        self.output_done_ms = base + 12.0
        self.ready_to_emit_wait_ms = 1.0
        self.admitted_to_ready_ms = 7.0
        self.end_to_end_ms = 10.0
        self.arrival_to_complete_ms = 12.0
        self.components_ms = {"stem_prefix": 1.0, "pl_n4": 8.0}
        self.stage_events = {"stem_prefix": {"queued_ms": base + 2.0,
                                               "start_ms": base + 2.5,
                                               "end_ms": base + 3.5}}
        start_completed = 21 + int(base) * 3
        start_hardware_generation = 12 + int(base) * 3
        profiles = (2, 0, 1)
        previous_profile = 1
        self.completions = []
        for index, profile in enumerate(profiles):
            before_completed = start_completed + index
            before_generation = start_hardware_generation + index
            after_generation = before_generation + 1
            self.completions.append({
                "profile": profile, "reset_generation": 9,
                "generation_token": 9,
                "hardware_reset_generation": after_generation,
                "reset_generation_before": before_generation,
                "mode_switch_reset": True,
                "status_before": {
                    "completed_frames": before_completed,
                    "profile": previous_profile,
                    "reset_generation": before_generation,
                },
                "status_after": {
                    "completed_frames": before_completed + 1,
                    "profile": profile,
                    "reset_generation": after_generation,
                },
            })
            previous_profile = profile
        self.features = np.zeros(512, dtype=np.float32)


class FakePipeline(object):
    def __init__(self):
        self.last_batch_start = None
        self.last_batch_end = None
        self.stats = {"in_flight_peak": 3}


class FakeRuntime(object):
    def __init__(self):
        self.pipeline = FakePipeline()
        self.calls = []

    def run(self, items, expected):
        import time
        self.calls.append(list(expected))
        self.pipeline.last_batch_start = time.perf_counter()
        self.pipeline.last_batch_end = self.pipeline.last_batch_start + 0.5
        return [Result(frame_id, float(index))
                for index, frame_id in enumerate(expected)]


class BenchmarkCnnPipelineV6Tests(unittest.TestCase):
    def test_three_warmups_are_excluded_and_thirty_frames_use_batch_wall(self):
        runtime = FakeRuntime()
        items = [(index, index) for index in range(33)]
        statuses = iter([{"completed_frames": 21, "profile": 1,
                          "reset_generation": 12},
                         {"completed_frames": 111, "profile": 1,
                          "reset_generation": 102}])
        sha_by_id = {index: "%064x" % index for index in range(33)}
        cpu_snapshots = iter([{"phase": "before-measurement"},
                              {"phase": "after-measurement"}])
        report = run_fixed_batches(
            runtime, items, input_sha256_by_id=sha_by_id,
            status_reader=lambda: next(statuses),
            cpu_reader=lambda: next(cpu_snapshots))
        self.assertEqual([len(call) for call in runtime.calls], [3, 30])
        self.assertEqual(report["warmup"]["frames_completed"], 3)
        measurement = report["measurement"]
        self.assertEqual(measurement["frames_completed"], 30)
        self.assertEqual(measurement["batch_wall_ms"], 500.0)
        self.assertEqual(measurement["throughput_fps"], 60.0)
        self.assertEqual(measurement["admitted_to_complete_ms"]["median"], 10.0)
        self.assertEqual(measurement["admitted_to_ready_ms"]["median"], 7.0)
        self.assertEqual(measurement["ready_to_emit_wait_ms"]["median"], 1.0)
        self.assertEqual(measurement["arrival_to_complete_ms"]["median"], 12.0)
        self.assertEqual(measurement["admission_wait_ms"]["median"], 2.0)
        self.assertEqual(measurement["frames"][0]["features_shape"], [512])
        self.assertEqual(measurement["frames"][0]["driver_completion_count"], 3)
        self.assertEqual(measurement["frames"][0]["output_done_ms"], 12.0)
        self.assertIn("stem_prefix", measurement["frames"][0]["stage_events_ms"])
        self.assertEqual(measurement["pipeline_stats"]["in_flight_peak"], 3)
        self.assertEqual(report["driver_status_before_measurement"]["completed_frames"], 21)
        self.assertEqual(report["driver_status_after_measurement"]["completed_frames"], 111)
        self.assertEqual(report["cpu_before_measurement"],
                         {"phase": "before-measurement"})
        self.assertEqual(report["cpu_after_measurement"],
                         {"phase": "after-measurement"})
        self.assertEqual(measurement["frames"][0]["input_sha256"], "%064x" % 3)

        board = build_board_report(
            report, driver_generation=9,
            feature_outputs=[{"frame_id": index} for index in range(3, 33)],
            pl_clock={"hz": 101375992, "source": "PS FCLK0",
                      "design_sha256": "b" * 64,
                      "deployment_receipt_sha256": "c" * 64},
            parameter_binding={"manifest_sha256": "a" * 64},
            cleanup_receipt={"quiesce_confirmed": True,
                             "all_handles_freed": True,
                             "transport_closed": True},
            cpu_before={"logical_cpu_count": 4},
            cpu_after={"logical_cpu_count": 4},
            kernel_boot_id="774b9485-2465-4f16-b60e-a4081467f468",
            runtime_config_sha256="d" * 64,
            split_manifest_sha256="e" * 64)
        self.assertEqual(board["status"], "BOARD_V6_BENCHMARK_COMPLETED")
        self.assertEqual(board["execution"], "board_linux_ioctl_fzv6")
        self.assertEqual(board["driver_generation"], 9)
        self.assertEqual(board["driver_status_before_measurement"]["reset_generation"], 12)
        self.assertEqual(board["driver_status_after_measurement"]["reset_generation"], 102)
        self.assertEqual(len(board["feature_outputs"]), 30)
        self.assertEqual(board["warmup_policy"]["frames"], 3)
        self.assertEqual(board["measurement_policy"]["frames"], 30)
        self.assertTrue(board["pl_execution"])
        self.assertEqual(board["measurement"]["cpu_before"],
                         {"logical_cpu_count": 4})

        report["measurement"]["frames"][0]["driver_completions"][0][
            "reset_generation"] = 10
        with self.assertRaisesRegex(ValueError, "logical driver generation"):
            build_board_report(
                report, driver_generation=9,
                feature_outputs=[{"frame_id": index} for index in range(3, 33)],
                pl_clock={"hz": 101375992}, parameter_binding={},
                cleanup_receipt={"quiesce_confirmed": True,
                                 "all_handles_freed": True,
                                 "transport_closed": True},
                cpu_before={}, cpu_after={}, kernel_boot_id="boot",
                runtime_config_sha256="d" * 64,
                split_manifest_sha256="e" * 64)
        report["measurement"]["frames"][0]["driver_completions"][0][
            "reset_generation"] = 9
        report["measurement"]["frames"][0]["driver_completions"][0][
            "mode_switch_reset"] = False
        with self.assertRaisesRegex(ValueError, "logical driver generation"):
            build_board_report(
                report, driver_generation=9,
                feature_outputs=[{"frame_id": index} for index in range(3, 33)],
                pl_clock={"hz": 101375992}, parameter_binding={},
                cleanup_receipt={"quiesce_confirmed": True,
                                 "all_handles_freed": True,
                                 "transport_closed": True},
                cpu_before={}, cpu_after={}, kernel_boot_id="boot",
                runtime_config_sha256="d" * 64,
                split_manifest_sha256="e" * 64)

    def test_rejects_wrong_batch_size_or_duplicate_ids(self):
        runtime = FakeRuntime()
        with self.assertRaisesRegex(ValueError, "33"):
            run_fixed_batches(runtime, [(index, index) for index in range(32)])
        items = [(index, index) for index in range(33)]
        items[-1] = (0, 99)
        with self.assertRaisesRegex(ValueError, "unique"):
            run_fixed_batches(runtime, items)


if __name__ == "__main__":
    unittest.main()
