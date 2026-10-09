"""Recompute Network2 v3 counters, time boundaries and retained features offline."""
import argparse
import json
import math
from pathlib import Path

import numpy as np

from audit_network2_features import audit_board_report, digest, load_oracle, require


def finite(value, label):
    require(isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value), "invalid numeric " + label)
    return float(value)


def u32(value):
    require(type(value) is int and 0 <= value <= 0xffffffff, "invalid uint32 counter")
    return value


def timing_records(data):
    profile = data["metadata"]["profile_name"]
    require(profile in ("serial4", "serial1-3", "pipeline1-3"), "unknown timing profile")
    pipeline = profile == "pipeline1-3"
    records = data["records"]
    require(len(records) == 30, "expected 30 measured frames")
    duration = finite(data["batch_wall_ms"], "batch duration")
    require(duration > 0, "nonpositive batch duration")
    if pipeline:
        require("latency_clock_origin_offset_ms" in data, "missing pipeline clock origin offset")
    offset = finite(data.get("latency_clock_origin_offset_ms", 0), "clock origin offset")
    require(offset >= 0, "negative clock origin offset")
    require(pipeline or offset == 0, "serial must use the outer batch clock origin")
    fps = 30000.0 / duration
    require(math.isclose(fps, finite(data["throughput_fps"], "FPS"), rel_tol=1e-10),
            "saved FPS differs from batch duration")
    boundaries = {"arrival_to_complete_ms": []}
    if pipeline:
        boundaries.update({"admission_wait_ms": [], "admitted_to_complete_ms": []})
    previous = None
    for index, record in enumerate(records):
        require(record["frame_id"] == index, "frame order mismatch")
        mapping = record["frame_mapping"]
        require(mapping["logical_frame_id"] == index, "logical frame mismatch")
        before = u32(mapping["completed_frames_before"])
        after = u32(mapping["completed_frames_after"])
        hardware = u32(mapping["hardware_frame_id"])
        request = u32(mapping["request_id"])
        require(after == ((before + 1) & 0xffffffff), "completion did not increment once")
        if previous is not None:
            require(before == previous[0] and hardware == ((previous[1] + 1) & 0xffffffff)
                    and request == ((previous[2] + 1) & 0xffffffff), "counter continuity mismatch")
        previous = (after, hardware, request)
        arrival = finite(record["arrival_ms"], "arrival")
        dma = finite(record["dma_admitted_ms"], "DMA admission")
        done = finite(record["complete_ms"], "completion")
        require(0 <= arrival <= dma <= done and done + offset <= duration + 1e-6,
                "invalid timestamp order/origin")
        boundaries["arrival_to_complete_ms"].append(done - arrival)
        if "end_to_end_ms" in record:
            require(math.isclose(done - arrival, finite(record["end_to_end_ms"], "latency"),
                                 rel_tol=1e-9, abs_tol=1e-6), "end-to-end boundary mismatch")
        if pipeline:
            admitted = finite(record["pipeline_admission_ms"], "pipeline admission")
            require(arrival <= admitted <= dma, "pipeline/DMA admission order")
            wait = admitted - arrival
            require(math.isclose(wait, finite(record["admission_wait_ms"], "admission wait"),
                                 rel_tol=1e-9, abs_tol=1e-6), "admission wait mismatch")
            boundaries["admission_wait_ms"].append(wait)
            boundaries["admitted_to_complete_ms"].append(done - admitted)
    if pipeline:
        require(data["observed_return_order"] == list(range(30)), "consumer order mismatch")
        queue = data["queue"]
        require(queue["max_in_flight"] == 2 and 0 < queue["in_flight_peak"] <= 2
                and queue["in_flight_current"] == 0, "in-flight bound or lease leak")
        require(all(0 <= count <= queue["capacity_per_boundary"]
                    for count in queue["peak"].values()), "queue capacity exceeded")
        require(not data["pipeline_threads_alive_after_run"], "pipeline threads remain alive")
    return {"profile": profile, "batch_wall_ms": duration, "throughput_fps": fps,
            "boundaries": {key: {"p50": float(np.percentile(values, 50)),
                                  "p95": float(np.percentile(values, 95)),
                                  "max": max(values)} for key, values in boundaries.items()},
            "latency_clock_origin_offset_ms": offset,
            "counter_scope": "u32 wrap-safe exact per-frame increments and cross-frame continuity"}


def audit(data, references, text):
    features = audit_board_report(data, references, text)
    require(data["stage"] == "network2-cascade-12block-v3" and data["profile"] is False,
            "wrong stage or profiling enabled")
    metadata = data["metadata"]
    require(metadata["warmup_count"] == 3 and metadata["measured_count"] == 30,
            "wrong formal sample counts")
    before = metadata["cpu_frequency_snapshot_before_khz"]
    after = metadata["cpu_frequency_snapshot_after_khz"]
    require(len(before) == 4 and all(type(freq) is int and freq > 0 for freq in before)
            and before == after == data["cpu_frequency_khz"], "frequency condition differs")
    require(data["quiesce_status"]["success"] and data["quiesce_status"]["close_success"]
            and not data["quiesce_status"]["poisoned"] and data["runtime_close_success"],
            "verified teardown incomplete")
    expected_threads = (4, 4) if metadata["profile_name"] == "serial4" else (1, 3)
    actual_threads = data["threads"]
    require((actual_threads["prefix_ort_intra"], actual_threads["suffix_ort_intra"])
            == expected_threads and actual_threads["prefix_ort_inter"]
            == actual_threads["suffix_ort_inter"] == 1, "thread conditions differ")
    return {"status": "PASS_INDEPENDENT_NETWORK2_RECEIPT_AUDIT",
            "timing": timing_records(data), "features": features,
            "cpu_frequency_khz": before,
            "scope": "Saved receipt consistency, retained feature recomputation and boundary/counter math only. Hardware provenance and packet-byte equality require the separately archived board/ILA evidence and runtime validation."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("oracle_dir", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    blob = args.report.read_bytes()
    result = audit(json.loads(blob), *load_oracle(args.oracle_dir))
    result["report_sha256"] = digest(blob)
    result["checker_sha256"] = digest(Path(__file__).read_bytes())
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "timing": result["timing"]}))


if __name__ == "__main__":
    main()
