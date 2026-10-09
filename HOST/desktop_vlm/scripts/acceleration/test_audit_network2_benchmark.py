"""Synthetic arithmetic tests only; no board or performance evidence."""
import unittest

from audit_network2_benchmark import timing_records


def synthetic_timeline():
    records = []
    for frame in range(30):
        before = (0xfffffff0 + frame) & 0xffffffff
        records.append({"frame_id": frame, "arrival_ms": frame * 10.0,
                        "pipeline_admission_ms": frame * 10.0 + 1,
                        "admission_wait_ms": 1.0,
                        "dma_admitted_ms": frame * 10.0 + 2,
                        "complete_ms": frame * 10.0 + 8,
                        "end_to_end_ms": 8.0,
                        "frame_mapping": {"logical_frame_id": frame,
                                          "completed_frames_before": before,
                                          "completed_frames_after": (before + 1) & 0xffffffff,
                                          "hardware_frame_id": before,
                                          "request_id": before}})
    return {"metadata": {"profile_name": "pipeline1-3"}, "records": records,
            "batch_wall_ms": 301.0, "throughput_fps": 30000.0 / 301,
            "latency_clock_origin_offset_ms": 1.0,
            "observed_return_order": list(range(30)),
            "queue": {"max_in_flight": 2, "in_flight_peak": 2,
                      "in_flight_current": 0, "capacity_per_boundary": 2,
                      "peak": {"input": 1, "output": 1}},
            "pipeline_threads_alive_after_run": []}


class TimelineTests(unittest.TestCase):
    def test_wrap_and_separate_latency_boundaries(self):
        result = timing_records(synthetic_timeline())
        self.assertEqual(result["boundaries"]["arrival_to_complete_ms"]["p50"], 8)
        self.assertEqual(result["boundaries"]["admitted_to_complete_ms"]["p50"], 7)

    def test_wrong_clock_origin_rejected(self):
        data = synthetic_timeline()
        data["latency_clock_origin_offset_ms"] = 10
        with self.assertRaisesRegex(ValueError, "timestamp order/origin"):
            timing_records(data)

    def test_missing_pipeline_clock_origin_rejected(self):
        data = synthetic_timeline()
        del data["latency_clock_origin_offset_ms"]
        with self.assertRaisesRegex(ValueError, "missing pipeline clock origin"):
            timing_records(data)

    def test_counter_gap_rejected(self):
        data = synthetic_timeline()
        data["records"][12]["frame_mapping"]["request_id"] += 1
        with self.assertRaisesRegex(ValueError, "continuity"):
            timing_records(data)

    def test_arrival_latency_cannot_be_replaced_by_admitted_latency(self):
        data = synthetic_timeline()
        data["records"][12]["end_to_end_ms"] = 7
        with self.assertRaisesRegex(ValueError, "end-to-end boundary"):
            timing_records(data)

    def test_claimed_fps_cannot_ignore_batch_overhead(self):
        data = synthetic_timeline()
        data["throughput_fps"] = 100
        with self.assertRaisesRegex(ValueError, "saved FPS"):
            timing_records(data)


if __name__ == "__main__":
    unittest.main()
