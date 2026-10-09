import ast
import hashlib
import json
import sys
from pathlib import Path

import pytest
import numpy as np

BOARD = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BOARD))

from benchmark_stage23_serial_v1 import (
    FEATURE_COSINE_MINIMUM, FEATURE_MAX_ABS_TOLERANCE,
    RUNTIME_SPLIT_SHA256, _check_backend, _feature_metrics, _validate_records,
    run_serial_benchmark)
from stage23_dma_protocol import NotReady
from stage23_dma_protocol import Stage23DmaProtocol


class IncompleteBackend(object):
    execution_identity = {"pl_execution": True}

    def __init__(self, quiesce_result):
        self.quiesce_result = quiesce_result
        self.closed = False

    def quiesce(self):
        return self.quiesce_result

    def close(self):
        self.closed = True


def test_benchmark_requires_real_complete_pl_identity_and_lifecycle_methods():
    with pytest.raises(NotReady, match="must be injected"):
        _check_backend(None, 2)
    with pytest.raises(NotReady, match="identity is incomplete"):
        _check_backend(IncompleteBackend({"quiesced": True, "poisoned": False}), 3)


@pytest.mark.parametrize("profile,threads", [
    ("baseline-4-4", {"ort_intra": 4, "ort_inter": 1}),
    ("pipeline-control-1-3", {
        "prefix_ort_intra": 1, "prefix_ort_inter": 1,
        "suffix_ort_intra": 3, "suffix_ort_inter": 1}),
])
def test_failed_not_ready_run_is_persisted_and_never_compare_eligible(tmp_path, profile, threads):
    output = tmp_path / "serial.json"
    with pytest.raises(NotReady, match="must be injected"):
        run_serial_benchmark(
            2, ["unused0", "unused1", "unused2"], str(output), None,
            "unused-runtime", "unused-stage2", "unused-stage3", "unused-runner",
            profile=profile)
    report = json.loads(output.read_text(encoding="utf-8"))
    saved = report
    assert report["status"] == saved["status"] == "FAILED"
    assert report["compare_eligible"] is False
    assert report["records"] == []
    assert report["quiesce_status"]["attempted"] is False
    assert report["profile"] is False
    assert report["metadata"]["profile_name"] == profile
    assert report["expected_frame_ids"] == list(range(30))
    assert report["warmup_frame_ids"] == [0xffffff00, 0xffffff01, 0xffffff02]
    assert all(isinstance(value, int) for value in report["cpu_frequency_khz"])
    assert report["threads"] == threads
    assert report["same_input_repeated"] is False
    assert isinstance(report["boundary"], str) and report["boundary"]
    assert "NotReady" in report["error"]


def test_invalid_identity_still_records_cleanup_and_cleanup_failure_blocks_pass(tmp_path):
    backend = IncompleteBackend({"quiesced": False, "poisoned": True})
    path = tmp_path / "serial.json"
    with pytest.raises(NotReady, match="identity is incomplete"):
        run_serial_benchmark(
            3, ["unused0", "unused1", "unused2"], str(path), backend,
            "unused-runtime", "unused-stage2", "unused-stage3", "unused-runner")
    report = json.loads(path.read_text(encoding="utf-8"))
    assert backend.closed is True
    assert report["status"] == "FAILED"
    assert report["compare_eligible"] is False
    assert report["quiesce_status"]["success"] is False
    assert report["quiesce_status"]["close_success"] is True


def test_serial_benchmark_source_parses_with_python36_grammar():
    path = BOARD / "benchmark_stage23_serial_v1.py"
    ast.parse(path.read_text(encoding="utf-8"), filename=str(path), feature_version=(3, 6))


def test_numeric_feature_tolerance_accepts_cross_host_noise_and_keeps_bytes_diagnostic():
    expected_feature = np.ones(512, dtype=np.float32)
    actual_feature = expected_feature.copy()
    actual_feature[0] += FEATURE_MAX_ABS_TOLERANCE / 2.0
    expected = {"image-00": {"pl_input_sha256": "a" * 64,
                             "pl_output_sha256": "b" * 64}}
    record = {"sample_id": "image-00", "pl_input_sha256": "a" * 64,
              "pl_output_sha256": "b" * 64, "feature": actual_feature}
    assert _validate_records([record], expected, {"image-00": expected_feature}) is True
    assert record["validation"]["feature"]["numeric_thresholds"] == {
        "max_abs_lte": FEATURE_MAX_ABS_TOLERANCE,
        "cosine_gte": FEATURE_COSINE_MINIMUM}
    assert record["validation"]["feature"]["byte_exact_match"] is False
    assert record["correct"] is True

    bad = expected_feature.copy()
    bad[0] += FEATURE_MAX_ABS_TOLERANCE * 2.0
    rejected = {"sample_id": "image-00", "pl_input_sha256": "a" * 64,
                "pl_output_sha256": "b" * 64, "feature": bad}
    assert _validate_records([rejected], expected, {"image-00": expected_feature}) is False
    assert rejected["correct"] is False


def test_feature_cosine_uses_one_float64_domain_for_collinear_vectors():
    values = np.linspace(-0.2, 0.3, 512, dtype=np.float32)
    metrics = _feature_metrics(values, values.copy())
    assert metrics["cosine"] == pytest.approx(1.0, abs=1e-15)
    assert metrics["max_abs"] == 0.0


def test_stage2_production_packet_decode_skips_unused_requantization():
    protocol = Stage23DmaProtocol()
    frozen = protocol.frozen_sample("image-00")["stage2_receipt"]
    production = protocol.unpack_stage2_receipt("image-00", frozen.transfer)
    assert production.dw3_residual_i16 is None
    assert production.dw7_stage3_i16 is None
    reference = protocol.unpack_stage2_receipt(
        "image-00", frozen.transfer, include_requantized=True)
    assert reference.dw3_residual_i16 is not None
    assert reference.dw7_stage3_i16 is not None
    np.testing.assert_array_equal(reference.dw3_residual_i16, frozen.dw3_residual_i16)
    np.testing.assert_array_equal(reference.dw7_stage3_i16, frozen.dw7_stage3_i16)


def test_three_feature_references_are_sha_bound_by_frozen_runtime_manifest():
    root = BOARD.parents[1]
    ref_dir = root / "artifacts" / "board-debug-20261004" / "acceleration" / "host" / "stage23-runtime-split-001"
    raw = (ref_dir / "manifest.json").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == RUNTIME_SPLIT_SHA256
    manifest = json.loads(raw.decode("utf-8"))
    cases = {item["sample_id"]: item for item in manifest["cases"]}
    assert set(cases) == {"image-00", "image-01", "image-02"}
    for sample_id, case in cases.items():
        for stage in (2, 3):
            path = ref_dir / ("%s-stage%d-feature.f32" % (sample_id, stage))
            expected_sha = case["stage%d" % stage]["feature_sha256"]
            assert hashlib.sha256(path.read_bytes()).hexdigest() == expected_sha
