import json
import sys
from pathlib import Path

import pytest
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import benchmark_network2_cascade_v3 as benchmark
from stage23_v3_candidate.network2_dma_backend_v3 import NotReady


class HostContractBackend(object):
    def __init__(self):
        self.execution_identity = {"pl_execution": False, "contract_test_only": True}
        self.quiesce_calls = 0
        self.close_calls = 0

    def quiesce(self):
        self.quiesce_calls += 1
        return {"quiesced": True, "poisoned": False}

    def close(self):
        self.close_calls += 1


def test_host_contract_backend_writes_explicit_nonperformance_schema_and_quiesces(tmp_path):
    backend = HostContractBackend()
    output_path = tmp_path / "host-contract.json"
    with pytest.raises(NotReady, match="rejects host/fake"):
        benchmark.run_benchmark(
            "serial4", ["unused0", "unused1", "unused2"], str(output_path),
            backend=backend)

    report = json.loads(output_path.read_text())
    assert report["status"] == "FAILED"
    assert report["execution"] == "HOST_CONTRACT_ONLY"
    assert report["pl_execution"] is False
    assert report["compare_eligible"] is False
    assert report["profile"] is False
    assert report["metadata"]["host_contract_only"] is True
    assert report["records"] == []
    assert report["quiesce_status"]["success"] is True
    assert report["quiesce_status"]["close_success"] is True
    assert backend.quiesce_calls == 1
    assert backend.close_calls == 1


def test_frequency_condition_is_not_eligible_when_snapshots_missing_or_differ():
    assert benchmark._read_frequency_conditions([], []) == {
        "cpu_frequency_match": False,
        "reason": "before/after CPU frequency vectors are empty or differ"}
    assert benchmark._read_frequency_conditions([1000, 1000], [1000, 1100])["cpu_frequency_match"] is False
    assert benchmark._read_frequency_conditions([1000, 1000], [1000, 1000])["cpu_frequency_match"] is True


def _valid_receipt_rows():
    feature_refs, text_features, text_ids = benchmark._load_feature_references(benchmark.CASCADE_ORACLE_DIR)
    fixture_rows = benchmark._load_fixture_rows(benchmark.CASCADE_FIXTURE_DIR)
    with open(benchmark.os.path.join(benchmark.TRACE_SPLIT_DIR, "manifest.json"), "r") as stream:
        split_manifest = json.load(stream)
    input_hashes = [row["sha256"] for row in split_manifest["three_old_preprocessed_inputs"]]
    records = []
    for frame_id in range(benchmark.MEASURED_COUNT):
        sample_id = benchmark.SAMPLE_IDS[frame_id % 3]
        fixture = fixture_rows[sample_id]
        feature = feature_refs[sample_id]["feature"].astype("<f4").copy()
        feature_bytes = feature.tobytes()
        before = 700 + frame_id
        records.append({
            "frame_id": frame_id,
            "sample_id": sample_id,
            "input_sha256": input_hashes[frame_id % 3],
            "packet_sha256": fixture["input_sha256"],
            "output_i16_sha256": fixture["output_sha256"],
            "feature": feature,
            "feature_sha256": benchmark._sha_bytes(feature_bytes),
            "frame_mapping": {"logical_frame_id": frame_id,
                              "hardware_frame_id": 1200 + frame_id,
                              "request_id": 1500 + frame_id,
                              "completed_frames_before": before,
                              "completed_frames_after": before + 1},
        })
    return records, input_hashes, fixture_rows, feature_refs, text_features, text_ids


def test_post_batch_gate_accepts_all_thirty_exact_reference_frames():
    args = _valid_receipt_rows()
    correct, summary = benchmark._validate_post_batch(*args)
    assert correct is True
    assert summary == {"request_id_first": 1500, "request_id_last": 1529,
                       "hardware_frame_id_first": 1200, "hardware_frame_id_last": 1229,
                       "completed_frames_before_first": 700,
                       "completed_frames_after_last": 730, "wrap_u32": False}
    assert all(row["correct"] for row in args[0])


def test_post_batch_gate_rejects_feature_numeric_deviation_even_with_updated_sha():
    args = _valid_receipt_rows()
    args[0][4]["feature"][0] += np.float32(0.01)
    args[0][4]["feature_sha256"] = benchmark._sha_bytes(args[0][4]["feature"].tobytes())
    correct, unused_summary = benchmark._validate_post_batch(*args)
    assert correct is False
    assert args[0][4]["validation"]["feature"]["max_abs"] > benchmark.FEATURE_MAX_ABS
    assert args[0][4]["correct"] is False


def test_post_batch_gate_rejects_request_id_gap():
    args = _valid_receipt_rows()
    args[0][10]["frame_mapping"]["request_id"] += 1
    correct, unused_summary = benchmark._validate_post_batch(*args)
    assert correct is False
    assert args[0][10]["validation"]["frame_counter_advance_once"] is False


def test_pipeline_capture_preserves_observed_order_and_rejects_duplicate():
    class Receipt(object):
        def __init__(self, frame_id):
            self.frame_id = frame_id
            self.value = {"sample_id": "sample", "packet_sha256": "p",
                          "output_i16_sha256": "o", "expected_output_sha256": None,
                          "features": np.zeros((1, 512), dtype="<f4"),
                          "frame_mapping": {"logical_frame_id": frame_id}}
            self.components_ms = {}
            self.admission_start_ms = 1.0
            self.admission_wait_ms = 0.1
            self.submit_ms = 1.1
            self.complete_ms = 2.0
            self.end_to_end_ms = 1.0

    captured = {}
    observed = []
    benchmark._capture_pipeline_result(Receipt(1), captured, observed)
    benchmark._capture_pipeline_result(Receipt(0), captured, observed)
    assert observed == [1, 0]
    with pytest.raises(RuntimeError, match="duplicate pipeline consumer"):
        benchmark._capture_pipeline_result(Receipt(1), captured, observed)


def test_bad_fixture_manifest_directory_fails_closed(tmp_path):
    with pytest.raises(ValueError, match="fixture manifest unavailable/mismatch"):
        benchmark._load_fixture_rows(str(tmp_path))


def test_cli_accepts_matched_serial_one_three_profile(tmp_path):
    # Parsing reaches runner setup, where the expected absent production backend fails closed.
    output_path = str(tmp_path / "cli-report.json")
    with pytest.raises(NotReady):
        benchmark.main(["--profile", "serial1-3", "--input", "a", "--input", "b",
                        "--input", "c", "--device", "/dev/null",
                        "--bitstream-sha256", "0" * 64,
                        "--driver-module-sha256", "0" * 64,
                        "--pl-clock-hz", "1",
                        "--pl-clock-evidence-sha256", "0" * 64,
                        "--output", output_path])

