import ast
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

BOARD = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BOARD))

from benchmark_stage23_pipeline_v1 import (
    MATCHED_THREADS, _capture_consumed_result,
    _matched_frequency_conditions, _require_observed_return_order,
    run_pipeline_benchmark)
from benchmark_stage23_serial_v1 import run_serial_benchmark
from stage23_dma_protocol import NotReady


def test_pipeline_without_real_backend_writes_failed_noneligible_receipt(tmp_path):
    output = tmp_path / "pipeline.json"
    with pytest.raises(NotReady, match="must be injected"):
        run_pipeline_benchmark(
            2, ["unused0", "unused1", "unused2"], str(output), None,
            "unused-runtime", "unused-stage2", "unused-stage3", "unused-runner")
    report = json.loads(output.read_text(encoding="utf-8"))
    saved = report
    assert saved["status"] == report["status"] == "FAILED"
    assert saved["compare_eligible"] is report["compare_eligible"] is False
    assert saved["records"] == []
    assert saved["profile"] is False
    assert saved["metadata"]["profile_name"] == "pipeline-1-3"
    assert saved["expected_frame_ids"] == list(range(30))
    assert saved["warmup_frame_ids"] == [0xffffff00, 0xffffff01, 0xffffff02]
    assert saved["same_input_repeated"] is False
    assert isinstance(saved["boundary"], str) and saved["boundary"]
    assert all(isinstance(value, int) for value in saved["cpu_frequency_khz"])
    assert saved["quiesce_status"]["attempted"] is False
    assert saved["scheduler"]["workers"] == {"prefix": 1, "backend": 1, "suffix": 1}
    assert saved["comparison_conditions"]["pure_ps_4_4_baseline_comparable"] is False
    assert "NotReady" in saved["error"]


def test_pipeline_and_matched_serial_control_have_same_ort_thread_map(tmp_path):
    serial_path = tmp_path / "serial.json"
    pipeline_path = tmp_path / "pipeline.json"
    with pytest.raises(NotReady):
        run_serial_benchmark(
            3, ["a", "b", "c"], str(serial_path), None,
            "r", "s2", "s3", "runner", profile="pipeline-control-1-3")
    with pytest.raises(NotReady):
        run_pipeline_benchmark(
            3, ["a", "b", "c"], str(pipeline_path), None,
            "r", "s2", "s3", "runner")
    serial = json.loads(serial_path.read_text(encoding="utf-8"))
    pipeline = json.loads(pipeline_path.read_text(encoding="utf-8"))
    serial_map = {key: value for key, value in serial["threads"].items()}
    assert serial_map == MATCHED_THREADS
    assert pipeline["threads"] == MATCHED_THREADS
    assert serial["profile"] is False and pipeline["profile"] is False
    assert serial["metadata"]["profile_name"] == "pipeline-control-1-3"
    assert serial["expected_frame_ids"] == pipeline["expected_frame_ids"] == list(range(30))
    assert pipeline["comparison_conditions"]["do_not_attribute_4_4_vs_1_3_gap_to_pipeline_overlap"] is True
    assert pipeline["compare_eligible"] is False


def test_failed_pipeline_preserves_quiesce_status_even_when_backend_is_incomplete(tmp_path):
    class Backend(object):
        execution_identity = {"pl_execution": True}

        def quiesce(self):
            return {"quiesced": False, "poisoned": True}

        def close(self):
            self.closed = True

    backend = Backend()
    path = tmp_path / "pipeline.json"
    with pytest.raises(NotReady, match="identity is incomplete"):
        run_pipeline_benchmark(
            2, ["a", "b", "c"], str(path), backend,
            "r", "s2", "s3", "runner")
    report = json.loads(path.read_text(encoding="utf-8"))
    assert backend.closed is True
    assert report["quiesce_status"]["success"] is False
    assert report["quiesce_status"]["close_success"] is True
    assert report["status"] == "FAILED"


def test_pipeline_benchmark_source_parses_with_python36_grammar():
    path = BOARD / "benchmark_stage23_pipeline_v1.py"
    ast.parse(path.read_text(encoding="utf-8"), filename=str(path), feature_version=(3, 6))


def test_out_of_order_fake_pipeline_is_rejected_by_observed_callback_order():
    class FakePipeline(object):
        def run(self, consumer):
            for frame_id in (1, 0):
                consumer(SimpleNamespace(
                    frame_id=frame_id,
                    value={"features": [float(frame_id)]},
                    submit_ms=float(frame_id), complete_ms=float(frame_id + 1),
                    components_ms={}))

    captured = {}
    observed = []
    FakePipeline().run(
        lambda result: _capture_consumed_result(result, captured, observed))
    assert observed == [1, 0]
    with pytest.raises(RuntimeError, match="return order mismatch"):
        _require_observed_return_order(observed, [0, 1])


def test_duplicate_consumer_frame_is_rejected_and_preserved_in_order_evidence():
    captured = {}
    observed = []
    result = SimpleNamespace(
        frame_id=7, value={"features": [7.0]},
        submit_ms=0.0, complete_ms=1.0, components_ms={})
    _capture_consumed_result(result, captured, observed)
    with pytest.raises(RuntimeError, match="duplicate frame_id 7"):
        _capture_consumed_result(result, captured, observed)
    assert observed == [7, 7]


def test_matched_frequency_conditions_accept_four_equal_nonempty_snapshots():
    snapshot = [{"cpu": 0, "khz": 1200000}, {"cpu": 1, "khz": 1200000}]
    eligible, vectors, differences = _matched_frequency_conditions(
        snapshot, list(snapshot), list(snapshot), list(snapshot))
    assert eligible is True
    assert differences == []
    assert vectors["serial_after_khz"] == [1200000, 1200000]


def test_matched_frequency_conditions_reject_serial_drift():
    stable = [{"cpu": 0, "khz": 1200000}, {"cpu": 1, "khz": 1200000}]
    drifted = [{"cpu": 0, "khz": 1200000}, {"cpu": 1, "khz": 1000000}]
    eligible, vectors, differences = _matched_frequency_conditions(
        stable, stable, stable, drifted)
    assert eligible is False
    assert vectors["serial_after_khz"] == [1200000, 1000000]
    assert differences == ["serial_after_khz differs from pipeline_before_khz"]
