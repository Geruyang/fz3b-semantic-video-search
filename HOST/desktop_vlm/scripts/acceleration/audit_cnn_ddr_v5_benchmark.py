"""Offline FZV5 benchmark audit. Does not contact or operate the board.

Checks timing boundaries, hardware job continuity and retained feature files.
Numerical equivalence and quantization quality remain separate evidence.
"""
import argparse
import hashlib
import json
import math
import struct
import uuid
from pathlib import Path

from compare_stages import percentile


COUNTERS = ("completed_frames", "ar_total", "rlast_total", "aw_total", "wlast_total", "b_total")
STATUS_FIELDS = COUNTERS + ("profile", "reset_generation", "protocol_error", "flags",
                           "guard_status", "guard_acks", "guard_error_flags", "job_cycles")
PROFILE_ORDER = (2, 0, 1)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def number(value, label, minimum=0):
    require(type(value) in (int, float) and math.isfinite(value) and value >= minimum,
            "invalid number: " + label)
    return float(value)


def uint(value, label, bits=32):
    require(type(value) is int and 0 <= value < 2 ** bits, "invalid unsigned: " + label)
    return value


def near(a, b, label, tolerance=1e-6):
    require(math.isclose(a, b, rel_tol=1e-9, abs_tol=tolerance), "mismatch: " + label)


def stats(values):
    require(bool(values), "empty statistics")
    return {"mean": sum(values) / len(values), "p50": percentile(values, .5),
            "p95": percentile(values, .95), "max": max(values)}


def sha(value):
    require(isinstance(value, str) and len(value) == 64 and
            all(c in "0123456789abcdef" for c in value), "invalid SHA256")
    return value


def status_check(status, generation, complete=False):
    for key in STATUS_FIELDS:
        uint(status[key], key, 64 if key == "job_cycles" else 32)
    require(status["reset_generation"] == generation, "reset generation changed")
    require(not any(status[k] for k in ("flags", "protocol_error", "guard_error_flags")),
            "driver/guard error")
    require(not status["guard_status"] & ((1 << 7) | (1 << 8) | (1 << 9)), "guard poisoned/error")
    require(status["ar_total"] == status["rlast_total"] and
            status["aw_total"] == status["wlast_total"] == status["b_total"], "outstanding AXI")
    if complete:
        required = (1 << 4) | (1 << 10) | (1 << 11)
        require(status["guard_status"] & required == required and
                not status["guard_status"] & ((1 << 13) | (1 << 15)), "job not cleanly complete")
        require(status["job_cycles"] > 0, "empty cycle count")


def audit(report, root):
    require(report["status"] == "BOARD_V5_BENCHMARK_COMPLETED" and
            report["execution"] == "board_linux_ioctl_fzv5" and report["pl_execution"] is True,
            "not a completed board benchmark")
    require(str(uuid.UUID(report["kernel_boot_id"])) == report["kernel_boot_id"], "invalid boot identity")
    sha(report["runtime_config_sha256"])
    sha(report["split_manifest_sha256"])
    sha(report["pl_clock"]["design_sha256"])
    sha(report["pl_clock"]["deployment_receipt_sha256"])
    require(report["warmup_policy"]["frames"] == 3 and
            report["warmup_policy"]["completed"] is True and
            report["warmup_policy"]["included_in_statistics"] is False, "warmup policy")
    require(all(report["cleanup_receipt"][k] is True for k in
                ("quiesce_confirmed", "all_handles_freed", "transport_closed")), "incomplete cleanup")
    measurement = report["measurement"]
    frames = measurement["frames"]
    require(len(frames) == measurement["frames_completed"] == report["measurement_policy"]["frames"] == 30,
            "requires 30 measured frames")
    origin = number(measurement["batch_wall_start_monotonic_s"], "origin")
    end = number(measurement["batch_wall_end_monotonic_s"], "end")
    wall = number(measurement["batch_wall_ms"], "wall")
    require(wall > 0, "nonpositive wall")
    near(wall, (end - origin) * 1000, "wall")
    near(origin, number(report["host_clock"]["origin_monotonic_s"], "origin"), "origin")
    near(measurement["throughput_fps"], 30000 / wall, "throughput")
    require(measurement["outer_call_wall_ms"] + 1e-6 >= wall, "batch exceeds enclosing call")
    cpu_before = measurement["cpu_before"]
    require(cpu_before == measurement["cpu_after"], "CPU environment changed")
    require(cpu_before["frequency_status"] == "measured_from_sysfs" and
            cpu_before["online_cpu_list"] == "0-3", "CPU identity unavailable")
    samples = cpu_before["current_frequency_samples"]
    require([s["cpu"] for s in samples] == [0, 1, 2, 3], "CPU frequency sample coverage")
    frequencies = [uint(s["scaling_cur_freq_khz"], "CPU frequency") for s in samples]
    require(all(frequencies), "zero CPU frequency")
    hz = uint(report["pl_clock"]["hz"], "PL clock", 64)
    require(hz > 0, "zero PL clock")
    generation = uint(report["driver_generation"], "generation")
    feature_records = {r["frame_id"]: r for r in report["feature_outputs"]}
    require(len(feature_records) == len(report["feature_outputs"]) == 30, "feature coverage/duplicates")
    warm_tail = report["warmup_policy"]["last_frame_driver_completions"]
    require(len(warm_tail) == 3, "missing warmup tail evidence")
    require(report["warmup_policy"]["pipeline_run_id"] != measurement["pipeline_run_id"],
            "warmup and measurement reused a run identity")
    for profile, completion in zip(PROFILE_ORDER, warm_tail):
        after = completion["status_after"]
        status_check(after, generation, complete=True)
        require(after["profile"] == profile, "warmup profile order")
    previous = warm_tail[-1]["status_after"]
    seen = set()
    input_sequence = hashlib.sha256()
    boundaries = {k: [] for k in ("arrival_to_complete_ms", "admission_wait_ms", "admitted_to_complete_ms")}
    components = {}
    hardware = {str(p): [] for p in PROFILE_ORDER}
    for frame in frames:
        fid = uint(frame["frame_id"], "frame id")
        require(fid not in seen and fid in feature_records, "frame duplicate/missing feature")
        seen.add(fid)
        input_sequence.update((sha(frame["input_sha256"]) + "\n").encode("ascii"))
        require(frame["pipeline_run_id"] == measurement["pipeline_run_id"], "stale pipeline run")
        arrival, admitted, done = [number(frame[k], k) for k in ("arrival_ms", "admitted_ms", "complete_ms")]
        require(0 <= arrival <= admitted <= done <= wall + 1e-6, "timestamp order/outside batch")
        near(admitted, frame["submit_ms"], "admission/submit")
        near(admitted - arrival, frame["admission_wait_ms"], "admission wait")
        near(done - arrival, frame["end_to_end_ms"], "end-to-end")
        for key in ("arrival", "admitted", "submit", "complete"):
            near(frame["event_monotonic_s"][key + "_monotonic_s"],
                 origin + frame[key + "_ms"] / 1000, "absolute event " + key)
        for key, value in zip(boundaries, (done - arrival, admitted - arrival, done - admitted)):
            boundaries[key].append(value)
        for group in ("components_ms", "runtime_timing_ms"):
            for key, value in frame[group].items():
                components.setdefault(group + "." + key, []).append(number(value, key))
        completions = frame["driver_completions"]
        require(len(completions) == 3, "missing PL stage")
        for profile, completion in zip(PROFILE_ORDER, completions):
            before, after = completion["status_before"], completion["status_after"]
            status_check(before, generation)
            status_check(after, generation, complete=True)
            require(all(completion[k] == after[k] for k in STATUS_FIELDS), "completion/after differs")
            require(after["profile"] == profile, "wrong profile order")
            require((after["completed_frames"] - before["completed_frames"]) & 0xffffffff == 1,
                    "job counter did not increment once")
            if previous is not None:
                require(all(before[k] == previous[k] for k in COUNTERS), "job counter discontinuity")
            for key in COUNTERS[1:]:
                require((after[key] - before[key]) & 0xffffffff > 0, "AXI counter did not advance")
            previous = after
            hardware[str(profile)].append(after["job_cycles"] * 1000 / hz)
        rec = feature_records[fid]
        path = (root / rec["relative_path"]).resolve()
        require(path.is_relative_to(root.resolve()), "feature escapes report directory")
        blob = path.read_bytes()
        require(len(blob) == rec["bytes"] == 2048 and
                hashlib.sha256(blob).hexdigest() == rec["sha256"], "feature bytes/SHA")
        require(all(math.isfinite(v) for v in struct.unpack("<512f", blob)), "nonfinite feature")
    final = report["driver_status_after_measurement"]
    require(all(final[k] == previous[k] for k in STATUS_FIELDS), "final status differs from last job")
    latency = stats(boundaries["arrival_to_complete_ms"])
    near(latency["p50"], measurement["latency_ms"]["median"], "reported median")
    near(latency["p95"], measurement["latency_ms"]["p95"], "reported linear p95")
    return {"status": "TIMING_COUNTERS_FEATURE_FILES_PASS", "numerical_equivalence": "SEPARATE_AUDIT_REQUIRED",
            "execution": "offline_audit_of_board_evidence", "measured_frames": 30, "measured_pl_jobs": 90,
            "batch_wall_ms": wall, "throughput_fps": 30000 / wall,
            "latency_boundaries": {k: stats(v) for k, v in boundaries.items()},
            "components_ms": {k: stats(v) for k, v in components.items()},
            "hardware_job_ms_by_profile": {k: stats(v) for k, v in hardware.items()},
            "percentile_method": "linear interpolation at (n-1)*q, matching PS/v3 audit",
            "cpu_frequency_khz": frequencies, "pl_clock_hz": hz,
            "kernel_boot_id": report["kernel_boot_id"],
            "input_sequence_sha256": input_sequence.hexdigest(),
            "runtime_config_sha256": report["runtime_config_sha256"],
            "warning": "Component means can overlap across frames; do not sum them to infer batch throughput."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    blob = args.report.read_bytes()
    result = audit(json.loads(blob), args.report.parent)
    result["source"] = {"path": str(args.report.resolve()), "sha256": hashlib.sha256(blob).hexdigest()}
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
