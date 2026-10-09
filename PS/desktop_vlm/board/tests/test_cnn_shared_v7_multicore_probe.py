import sys
import threading
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
BOARD = ROOT / "desktop_vlm/board"
sys.path.insert(0, str(BOARD))
sys.path.insert(0, str(ROOT / "desktop_vlm/scripts/acceleration"))

import cnn_shared_v7_multicore_probe as probe


class FakeBackend(object):
    def __init__(self, core_count, expected):
        self.core_count = core_count
        self.expected = expected
        self.next_handle = 1
        self.objects = {}
        self.statuses = [self._empty_status() for unused in range(core_count)]
        for state in self.statuses:
            state["job_cycles_lo"] = 1000
        self.lock = threading.Lock()
        self.active = []
        self.busy_handles = {}
        self.max_active = 0
        self.events = []
        self.submit_count = 0
        self.fail_on_submit = None
        self.quiesced = False

    @staticmethod
    def _empty_status():
        return dict((name, 0) for name in probe.STATUS_NAMES)

    def identity(self):
        return {"core_count": self.core_count}

    def alloc(self, size):
        handle = self.next_handle
        self.next_handle += 1
        self.objects[handle] = bytearray(size)
        return {"handle": handle, "bytes": size}

    def upload(self, handle, offset, payload):
        self.objects[handle][offset:offset + len(payload)] = payload

    def download(self, handle, offset, size):
        with self.lock:
            if self.busy_handles.get(handle, 0):
                raise RuntimeError("object-level transfer/job exclusion violated")
        return bytes(self.objects[handle][offset:offset + size])

    def status(self, core_id):
        result = dict(self.statuses[core_id])
        result["job_cycles"] = result["job_cycles_lo"]
        return result

    def submit(self, request, params_handle, memory_handle):
        with self.lock:
            self.submit_count += 1
            submit_number = self.submit_count
            self.active.append(request)
            self.busy_handles[memory_handle] = self.busy_handles.get(memory_handle, 0) + 1
            self.max_active = max(self.max_active, len(self.active))
            self.events.append(("start", request["frame_tag"],
                                request["block_index"], request["start_row"],
                                request["core_id"], request["scratch_words"]))
        if self.fail_on_submit == submit_number:
            with self.lock:
                self.active.remove(request)
                self.busy_handles[memory_handle] -= 1
                if not self.busy_handles[memory_handle]:
                    del self.busy_handles[memory_handle]
            raise RuntimeError("injected backend failure")
        time.sleep(0.002)
        profile = request["profile"]
        block = request["block_index"]
        frame = request["frame_tag"]
        expected = self.expected[(frame, profile, block)]
        row_bytes = 512 * 16
        start = request["start_row"] * row_bytes
        count = request["row_count"] * row_bytes
        dst = request["dst_words"] * 16
        scratch = request["scratch_words"] * 16
        geometry_words = request["scratch_required_words"] * 16
        self.objects[memory_handle][dst + start:dst + start + count] = \
            expected[start:start + count]
        self.objects[memory_handle][scratch:scratch + geometry_words] = \
            bytes(bytearray([0x3C])) * geometry_words
        state = self.statuses[request["core_id"]]
        state["completed_jobs"] += 1
        state["profile"] = profile
        state["job_cycles_lo"] = 23
        for name in ("ar_total", "rlast_total"):
            state[name] += 4
        for name in ("aw_total", "wlast_total", "b_total"):
            state[name] += 2
        with self.lock:
            self.active.remove(request)
            self.busy_handles[memory_handle] -= 1
            if not self.busy_handles[memory_handle]:
                del self.busy_handles[memory_handle]
            self.events.append(("done", frame, block, request["start_row"],
                                request["core_id"], request["scratch_words"]))

    def quiesce(self):
        self.quiesced = True

    def free(self, handle):
        if not self.quiesced:
            raise RuntimeError("FREE before QUIESCE")
        del self.objects[handle]


def make_workloads(profile, core_count, frames, blocks):
    tensor_bytes = 64 * 64 * 64 * 2
    params_bytes = probe.PROFILE_STRIDES[profile] * probe.PROFILE_BLOCKS[profile] * 16
    expected = {}
    specs = []
    for frame_tag, frame_id in frames:
        expected_blocks = {}
        for block_index in blocks:
            value = (frame_tag * 31 + block_index * 7) & 0xFF
            payload = bytes(bytearray([value])) * tensor_bytes
            expected[(frame_tag, profile, block_index)] = payload
            expected_blocks[block_index] = payload
        specs.append({"frame_id": frame_id, "frame_tag": frame_tag,
                      "params": bytes(params_bytes),
                      "source": bytes(bytearray([frame_tag & 0xFF])) * tensor_bytes,
                      "expected_blocks": expected_blocks})
    workloads = probe.prepare_workloads(profile, core_count, specs, blocks)
    return workloads, expected


class SharedV7MulticoreProbeTests(unittest.TestCase):
    def test_interval_metrics_use_monotonic_time_when_unix_clock_moves(self):
        metrics = probe._interval_metrics([
            {"success": True, "started_unix_ns": 900, "finished_unix_ns": 100,
             "started_monotonic_ns": 10, "finished_monotonic_ns": 30},
            {"success": True, "started_unix_ns": 50, "finished_unix_ns": 40,
             "started_monotonic_ns": 20, "finished_monotonic_ns": 40},
        ])
        self.assertEqual(metrics["job_makespan_ns"], 30)
        self.assertEqual(metrics["sum_job_wall_ns"], 40)
        self.assertEqual(metrics["union_busy_ns"], 30)
        self.assertEqual(metrics["overlap_job_ns"], 10)
        self.assertEqual(metrics["max_parallel_jobs"], 2)

    def test_independent_frames_run_concurrently_with_core_private_scratch(self):
        workloads, expected = make_workloads(2, 4, [(1, "frame-a"), (2, "frame-b")], [0])
        device = FakeBackend(4, expected)
        result = probe.run_workloads(device, workloads,
                                     "independent_frames")
        self.assertEqual(result["status"], "CNN_SHARED_V7_MULTICORE_PASS")
        self.assertTrue(result["independent_frame_overlap_observed"])
        self.assertGreaterEqual(device.max_active, 2)
        self.assertEqual(result["verified_blocks"], 2)
        self.assertGreater(result["performance"]["overlap_job_ns"], 0)
        self.assertGreaterEqual(result["performance"]["max_parallel_jobs"], 2)
        self.assertEqual(result["performance"]["max_inflight"], 4)
        self.assertEqual(result["performance"]["work_cycles_sum"], 16 * 2 * 23)
        self.assertEqual(set(result["performance"]["per_core"]),
                         set(("0", "1", "2", "3")))
        self.assertTrue(result["cleanup"]["quiesced"])
        self.assertFalse(device.objects)
        scratch_by_frame = {}
        for event in [event for event in device.events if event[0] == "start"]:
            self.assertEqual(len(event), 6)
            scratch_by_frame.setdefault(event[1], {})[event[4]] = event[5]
        for per_core in scratch_by_frame.values():
            self.assertEqual(len(per_core), 4)
            self.assertEqual(len(set(per_core.values())), 4)

    def test_same_frame_adjacent_blocks_obey_halo4_and_can_overlap(self):
        workloads, expected = make_workloads(2, 4, [(9, "one-frame")], [0, 1])
        device = FakeBackend(4, expected)
        result = probe.run_workloads(device, workloads,
                                     "same_frame_adjacent_blocks")
        self.assertEqual(result["status"], "CNN_SHARED_V7_MULTICORE_PASS")
        self.assertTrue(result["adjacent_block_overlap_observed"])
        self.assertEqual(result["verified_blocks"], 2)
        self.assertEqual(len(result["jobs"]), 32)
        self.assertTrue(any(job["status_before"]["job_cycles"] >
                            job["status_after"]["job_cycles"]
                            for job in result["jobs"]))
        self.assertTrue(all(job["job_cycles"] == 23
                            for job in result["jobs"] if job["success"]))
        events = device.events
        next_block_row0 = next(index for index, event in enumerate(events)
                               if event[0] == "start" and event[2] == 1 and event[3] == 0)
        committed_halo_events = [index for index, event in enumerate(events)
                                 if event[0] == "done" and event[2] == 0 and
                                 event[3] in (0, 4)]
        self.assertEqual(len(committed_halo_events), 2)
        self.assertTrue(all(index < next_block_row0
                            for index in committed_halo_events))

    def test_failure_stops_admission_drains_inflight_and_preserves_partial_results(self):
        workloads, expected = make_workloads(2, 4, [(3, "failure-frame")], [0, 1])
        device = FakeBackend(4, expected)
        device.fail_on_submit = 3
        result = probe.run_workloads(device, workloads,
                                     "same_frame_adjacent_blocks")
        self.assertEqual(result["status"], "CNN_SHARED_V7_MULTICORE_INCOMPLETE")
        self.assertIn("injected backend failure", result["failure"]["error"])
        self.assertEqual(result["admitted_after_failure"], 0)
        self.assertGreaterEqual(result["drained_jobs"], 1)
        self.assertTrue(result["cleanup"]["quiesced"])
        self.assertTrue(result["cleanup"]["handles_freed"])
        self.assertFalse(device.objects)

    def test_rejects_core_counts_outside_final_driver_range(self):
        workloads, expected = make_workloads(2, 2, [(1, "x")], [0, 1])
        device = FakeBackend(5, expected)
        with self.assertRaisesRegex(RuntimeError, "core_count"):
            probe.run_workloads(device, workloads, "same_frame_adjacent_blocks")

    def test_final_runtime_core_counts_one_through_four_are_accepted(self):
        for core_count in range(1, 5):
            workloads, expected = make_workloads(
                2, core_count, [(20 + core_count, "core-count-%d" % core_count)],
                [0, 1])
            device = FakeBackend(core_count, expected)
            result = probe.run_workloads(device, workloads,
                                         "same_frame_adjacent_blocks")
            self.assertEqual(result["runtime_core_count"], core_count)
            self.assertEqual(result["status"], "CNN_SHARED_V7_MULTICORE_PASS")

    def test_same_multicore_image_can_limit_inflight_to_one_for_baseline(self):
        workloads, expected = make_workloads(
            2, 4, [(81, "single-inflight-a"), (82, "single-inflight-b")], [0])
        device = FakeBackend(4, expected)
        result = probe.run_workloads(device, workloads, "independent_frames",
                                     max_inflight=1)
        self.assertEqual(result["status"], "CNN_SHARED_V7_MULTICORE_PASS")
        self.assertEqual(result["performance"]["max_inflight"], 1)
        self.assertEqual(result["performance"]["max_parallel_jobs"], 1)
        self.assertEqual(device.max_active, 1)
        self.assertFalse(result["independent_frame_overlap_observed"])


if __name__ == "__main__":
    unittest.main()
