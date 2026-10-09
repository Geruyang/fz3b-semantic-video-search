"""Synthetic in-memory tamper tests; no board execution or board evidence."""
import copy
import hashlib
import struct
import tempfile
import unittest
from pathlib import Path

from audit_cnn_ddr_v5_benchmark import audit


class AuditTests(unittest.TestCase):
    def fixture(self, root):
        def state(count, profile=1):
            return dict(completed_frames=count, ar_total=count * 2, rlast_total=count * 2,
                        aw_total=count, wlast_total=count, b_total=count,
                        profile=profile, reset_generation=1, protocol_error=0, flags=0,
                        guard_status=(1 << 4) | (1 << 10) | (1 << 11), guard_acks=0,
                        guard_error_flags=0, job_cycles=100000)
        blob = struct.pack("<512f", *([.1] * 512))
        (root / "synthetic.f32").write_bytes(blob)
        digest = hashlib.sha256(blob).hexdigest()
        cpu = dict(frequency_status="measured_from_sysfs", online_cpu_list="0-3",
                   current_frequency_samples=[dict(cpu=i, scaling_cur_freq_khz=1066666) for i in range(4)])
        frames, features = [], []
        before = state(9)
        for i in range(30):
            jobs = []
            for profile in (2, 0, 1):
                after = state(before["completed_frames"] + 1, profile)
                jobs.append(dict(after, status_before=before, status_after=after))
                before = after
            events = dict(arrival_ms=i*10, admitted_ms=i*10+1, submit_ms=i*10+1, complete_ms=i*10+9)
            frames.append(dict(events, frame_id=i+3, input_sha256="0"*64,
                               pipeline_run_id="synthetic-measure", admission_wait_ms=1, end_to_end_ms=9,
                               event_monotonic_s={k.replace("_ms", "_monotonic_s"): 100+v/1000 for k,v in events.items()},
                               components_ms={"prefix": 1}, runtime_timing_ms={"suffix": 2}, driver_completions=jobs))
            features.append(dict(frame_id=i+3, relative_path="synthetic.f32", bytes=2048, sha256=digest))
        return dict(status="BOARD_V5_BENCHMARK_COMPLETED", execution="board_linux_ioctl_fzv5", pl_execution=True,
                    kernel_boot_id="00000000-0000-0000-0000-000000000001", runtime_config_sha256="0"*64,
                    split_manifest_sha256="0"*64, driver_generation=1,
                    warmup_policy=dict(frames=3, completed=True, included_in_statistics=False,
                        pipeline_run_id="synthetic-warm", last_frame_driver_completions=[
                            dict(status_after=state(7+i,p)) for i,p in enumerate((2,0,1))]),
                    measurement_policy=dict(frames=30),
                    cleanup_receipt=dict(quiesce_confirmed=True, all_handles_freed=True, transport_closed=True),
                    host_clock=dict(origin_monotonic_s=100),
                    pl_clock=dict(hz=100000000, design_sha256="0"*64, deployment_receipt_sha256="0"*64),
                    measurement=dict(frames=frames, frames_completed=30, batch_wall_start_monotonic_s=100,
                        batch_wall_end_monotonic_s=100.3, batch_wall_ms=300, throughput_fps=100,
                        outer_call_wall_ms=301, cpu_before=cpu, cpu_after=cpu,
                        pipeline_run_id="synthetic-measure", latency_ms=dict(median=9, p95=9)),
                    driver_status_after_measurement=before, feature_outputs=features)

    def test_valid_synthetic_timing(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            result = audit(self.fixture(root), root)
            self.assertEqual(result["throughput_fps"], 100)
            self.assertEqual(result["measured_pl_jobs"], 90)
            self.assertEqual(result["numerical_equivalence"], "SEPARATE_AUDIT_REQUIRED")

    def test_tampered_evidence_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = self.fixture(root)
            def mutate(path, value):
                report = copy.deepcopy(source)
                parent = report
                for key in path[:-1]:
                    parent = parent[key]
                parent[path[-1]] = value
                return report
            cases = [
                (("measurement", "throughput_fps"), 101),
                (("measurement", "frames", 0, "admission_wait_ms"), 0),
                (("measurement", "frames", 0, "driver_completions", 0, "status_before", "completed_frames"), 8),
                (("warmup_policy", "last_frame_driver_completions", 2, "status_after", "completed_frames"), 8),
                (("measurement", "frames", 0, "driver_completions", 0, "status_after", "guard_error_flags"), 1),
                (("feature_outputs", 0, "sha256"), "1"*64),
                (("cleanup_receipt", "all_handles_freed"), False),
                (("measurement", "cpu_after", "online_cpu_list"), "0-1"),
            ]
            for path, value in cases:
                with self.subTest(path=path), self.assertRaises(ValueError):
                    audit(mutate(path, value), root)


if __name__ == "__main__":
    unittest.main()
