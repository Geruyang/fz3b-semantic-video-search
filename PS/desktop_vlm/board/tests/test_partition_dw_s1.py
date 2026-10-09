import hashlib
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pytest

from partition_dw_s1 import (ACTIVATION_SCALE, EXPECTED_DW_MANIFEST_SHA256,
                             EXPECTED_ACTUAL_PS_ORACLE_SHA256,
                             EXPECTED_SPLIT_MANIFEST_SHA256, PersistentDwS1,
                             _validate_dw_result, dequantize_dw,
                             quantize_activation)


BOARD = Path(__file__).resolve().parents[3]
SPLIT = BOARD / "artifacts/board-debug-20261004/acceleration/host/dw-split-001"
DW = BOARD / "artifacts/board-debug-20261004/acceleration/host/dw-int8-002"


def _make_small_split(tmp_path):
    with open(str(SPLIT / "manifest.json"), "r") as stream:
        manifest = json.load(stream)
    for stage in manifest["stages"]:
        payload = ("fake-model-" + stage["stage"]).encode("ascii")
        path = tmp_path / (stage["stage"] + ".onnx")
        path.write_bytes(payload)
        stage["sha256"] = hashlib.sha256(payload).hexdigest()
        stage["bytes"] = len(payload)
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path, hashlib.sha256(path.read_bytes()).hexdigest()


class FakeOrtClient(object):
    def __init__(self, stage, contract, prefix_value):
        self.stage = stage
        self.contract = contract
        self.prefix_value = prefix_value
        self.last_inputs = None
        self.closed = False

    def infer(self, inputs):
        self.last_inputs = [np.array(value, copy=True) for value in inputs]
        if self.stage == "prefix":
            name = self.contract["outputs"][0]["name"]
            return {name: self.prefix_value.copy()}, 0.0
        name = self.contract["outputs"][0]["name"]
        # Use both inputs so the test detects a lost/reordered residual bypass.
        value = np.float32(np.mean(inputs[0], dtype=np.float64) +
                           np.mean(inputs[1], dtype=np.float64))
        return {name: np.full((1, 512), value, dtype=np.float32)}, 0.0

    def close(self):
        self.closed = True


class FakeBatchClient(object):
    def __init__(self, weights, initial_job_id=0xfffffffe, corrupt_at=None,
                 wrong_value_at=None):
        self.weights = weights
        self.initial_job_id = initial_job_id
        self.calls = []
        self.corrupt_at = corrupt_at
        self.wrong_value_at = wrong_value_at
        self.closed = False
        self.next_request_id = 1
        self.last_job_id = initial_job_id

    def run(self, weights49_i8, pixels32x32_i8):
        channel = len(self.calls)
        self.calls.append((weights49_i8.copy(), pixels32x32_i8.copy()))
        request_id = self.next_request_id
        expected_job = (self.last_job_id + 1) & 0xffffffff
        self.next_request_id = (request_id + 1) & 0xffffffff
        self.last_job_id = expected_job
        output = np.full((32, 32), channel - 64, dtype="<i4")
        if channel == self.wrong_value_at:
            output[0, 0] += 1
        raw = output.tobytes()
        shape = (32, 31) if channel == self.corrupt_at else (32, 32)
        return {"outputs": raw, "outputs_dtype": "<i4", "output_shape": shape,
                "request_id": request_id, "job_id": expected_job,
                "weight_count": 49, "pixel_count": 1024, "output_count": 1024,
                "cycles": channel + 10}

    def close(self):
        self.closed = True


class FakeLayerBatchClient(FakeBatchClient):
    def __init__(self, weights, first_request_id=400, first_frame_id=9, bad_receipt=None):
        FakeBatchClient.__init__(self, weights)
        self.next_request_id = first_request_id
        self.next_frame_id = first_frame_id
        self.last_frame_id = (first_frame_id - 1) & 0xffffffff
        self.bad_receipt = bad_receipt
        self.layer_calls = []

    def run_layer(self, weights128_i8, pixels128_i8, logical_frame_id=None):
        self.layer_calls.append((weights128_i8.copy(), pixels128_i8.copy()))
        request_id = self.next_request_id
        frame_id = self.next_frame_id
        self.next_request_id = (request_id + 1) & 0xffffffff
        self.next_frame_id = (frame_id + 1) & 0xffffffff
        self.last_frame_id = frame_id
        outputs = np.broadcast_to(
            np.arange(128, dtype=np.int32).reshape(128, 1, 1),
            (128, 32, 32)).copy()
        receipt = {"outputs": outputs.astype("<i4").tobytes(),
                   "outputs_dtype": "<i4", "output_shape": (128, 32, 32),
                   "request_id": request_id, "frame_id": frame_id,
                   "weight_bytes": 6272, "pixel_bytes": 131072,
                   "input_bytes": 137344, "output_bytes": 524288,
                   "input_bytes_seen": 137344, "output_bytes_seen": 524288,
                   "completed_frames": 1, "mm2s_done": True,
                   "s2mm_done": True, "core_done": True, "error_code": 0,
                   "submit_ms": 12.0, "complete_ms": 14.5}
        if logical_frame_id is not None:
            receipt.update({"logical_frame_id": logical_frame_id,
                            "completed_frames_before": 72,
                            "completed_frames_after": 73,
                            "cycles": 901,
                            "pack_ms": 0.5,
                            "dma_write_ms": 1.25,
                            "output_copy_ms": 0.75,
                            "backend_wall_ms": 2.5})
        if self.bad_receipt:
            receipt.update(self.bad_receipt)
        return receipt


def _make_runner(tmp_path, prefix_value=None, corrupt_at=None, wrong_value_at=None,
                 actual_oracle_dir=None, expected_actual_oracle_manifest_sha256=None,
                 layer_client=False):
    split_dir = tmp_path / "split"
    split_dir.mkdir()
    _, split_sha = _make_small_split(split_dir)
    if prefix_value is None:
        prefix_value = np.arange(128, dtype=np.float32).reshape((1, 128, 1, 1))
        prefix_value = np.broadcast_to(prefix_value, (1, 128, 32, 32)).copy()
        prefix_value *= np.float32(ACTIVATION_SCALE)
    with open(str(DW / "weights-chw.i8"), "rb") as stream:
        weights = np.frombuffer(stream.read(), dtype=np.int8).reshape((128, 7, 7)).copy()
    batch = (FakeLayerBatchClient(weights) if layer_client else
             FakeBatchClient(weights, corrupt_at=corrupt_at,
                             wrong_value_at=wrong_value_at))
    clients = {}

    def factory(stage, model_path, contract, runner_path, threads):
        client = FakeOrtClient(stage, contract, prefix_value)
        clients[stage] = client
        return client

    runner = PersistentDwS1(str(split_dir), str(DW), "unused", batch,
                           expected_split_manifest_sha256=split_sha,
                           expected_dw_manifest_sha256=EXPECTED_DW_MANIFEST_SHA256,
                           ort_client_factory=factory,
                           actual_oracle_dir=actual_oracle_dir,
                           expected_actual_oracle_manifest_sha256=(
                               expected_actual_oracle_manifest_sha256 or
                               EXPECTED_ACTUAL_PS_ORACLE_SHA256))
    image = np.zeros((1, 3, 256, 256), dtype=np.float32)
    return runner, batch, clients, image, prefix_value


def test_quantize_uses_fp64_rint_ties_even_and_symmetric_clip():
    tensor = np.zeros((1, 128, 32, 32), dtype=np.float32)
    tensor.flat[:10] = np.array([-1000.0, -128.0, -127.5, -2.5, -1.5,
                                -0.5, 0.5, 1.5, 2.5, 1000.0], dtype=np.float32)
    quantized = quantize_activation(tensor, scale=1.0)
    assert quantized.dtype == np.int8
    assert quantized.shape == (128, 32, 32)
    assert quantized.flat[:10].tolist() == [-127, -127, -127, -2, -2, 0, 0, 2, 2, 127]


def test_quantize_rejects_nonfinite_or_wrong_shape():
    tensor = np.zeros((1, 128, 32, 32), dtype=np.float32)
    tensor.flat[0] = np.inf
    with pytest.raises(ValueError, match="finite"):
        quantize_activation(tensor)
    with pytest.raises(ValueError, match="shape"):
        quantize_activation(np.zeros((128, 32, 32), dtype=np.float32))


def test_mixed_pipeline_128_channels_order_bypass_counts_and_exports(tmp_path):
    runner, batch, clients, image, prefix = _make_runner(tmp_path)
    export_dir = tmp_path / "oracle-inputs"
    try:
        result = runner.infer_tensor(image, export_dir=str(export_dir),
                                     sample_id="capture-01", include_intermediates=True)
        assert len(batch.calls) == 128
        assert [r["request_id"] for r in result["job_receipts"]] == list(range(1, 129))
        assert result["job_ids"] == [0xffffffff, 126]
        assert all(r["weight_count"] == 49 and r["pixel_count"] == 1024 and
                   r["output_count"] == 1024 for r in result["job_receipts"])
        for channel in (0, 1, 63, 127):
            assert np.array_equal(batch.calls[channel][0], runner.weights[channel].reshape(49))
            expected_pixel = min(channel, 127)
            assert batch.calls[channel][1].shape == (1024,)
            assert np.all(batch.calls[channel][1] == expected_pixel)
        assert np.array_equal(clients["suffix"].last_inputs[1], prefix)
        assert np.array_equal(result["prefix_tensor"], prefix)
        assert result["dw_accumulators_i32"].shape == (128, 32, 32)
        assert result["dequantized_dw"].shape == (1, 128, 32, 32)
        expected_channel0 = ((-64) * ACTIVATION_SCALE * runner.weight_scales[0] + runner.bias[0])
        assert result["dequantized_dw"][0, 0, 0, 0] == np.float32(expected_channel0)
        assert result["features"].shape == (1, 512)
        assert result["timing_ms"]["infer_tensor_wall"] >= result["timing_ms"]["dw_128_batch_wall"]
        assert result["timing_ms"]["prefix_wall"] >= result["timing_ms"]["prefix_ort_run"]
        assert result["timing_ms"]["suffix_wall"] >= result["timing_ms"]["suffix_ort_run"]
        assert result["timing_ms"]["infer_tensor_wall"] >= result["timing_ms"]["dw_128_batch_wall"]
        assert result["timing_ms"]["prefix_wall"] >= result["timing_ms"]["prefix_ort_run"]
        assert result["timing_ms"]["suffix_wall"] >= result["timing_ms"]["suffix_ort_run"]
        assert result["export"]["artifacts"]["prefix"]["bytes"] == 128 * 32 * 32 * 4
        assert result["export"]["artifacts"]["quantized"]["bytes"] == 128 * 32 * 32
        record = json.loads((export_dir / "capture-01-ps-prefix-quantized.json").read_text())
        assert record["identity"]["dw_manifest_sha256"] == EXPECTED_DW_MANIFEST_SHA256
        assert record["artifacts"]["prefix"]["sha256"] == hashlib.sha256(
            (export_dir / "capture-01-prefix.f32").read_bytes()).hexdigest()
    finally:
        runner.close()
    assert batch.closed and clients["prefix"].closed and clients["suffix"].closed


def test_bad_dw_receipt_shape_stops_before_later_channels(tmp_path):
    runner, batch, _, image, _ = _make_runner(tmp_path, corrupt_at=4)
    try:
        with pytest.raises(ValueError, match="dtype/shape"):
            runner.infer_tensor(image)
        assert len(batch.calls) == 5
    finally:
        runner.close()


def test_same_session_keeps_request_and_job_sequences_across_images(tmp_path):
    runner, batch, _, image, _ = _make_runner(tmp_path)
    try:
        first = runner.infer_tensor(image)
        second = runner.infer_tensor(image)
        assert [first["job_receipts"][0]["request_id"],
                first["job_receipts"][-1]["request_id"]] == [1, 128]
        assert [second["job_receipts"][0]["request_id"],
                second["job_receipts"][-1]["request_id"]] == [129, 256]
        assert second["job_ids"][0] == (first["job_ids"][1] + 1) & 0xffffffff
        assert len(batch.calls) == 256
    finally:
        runner.close()


def test_optional_run_layer_submits_full_plane_once_and_preserves_residual(tmp_path):
    runner, batch, clients, image, prefix = _make_runner(tmp_path, layer_client=True)
    try:
        result = runner.infer_tensor(image, include_intermediates=True)
        assert result["execution_path"] == "layer"
        assert result["job_ids"] is None
        assert result["frame_ids"] == [9, 9]
        assert len(batch.layer_calls) == 1
        assert batch.layer_calls[0][0].shape == (128, 7, 7)
        assert batch.layer_calls[0][1].shape == (128, 32, 32)
        assert batch.layer_calls[0][0].dtype == np.dtype("int8")
        assert batch.layer_calls[0][1].dtype == np.dtype("int8")
        assert np.array_equal(batch.layer_calls[0][0], runner.weights)
        assert np.array_equal(batch.layer_calls[0][1], result["quantized_tensor"])
        assert not batch.calls
        assert result["dw_accumulators_i32"].shape == (128, 32, 32)
        assert result["dw_accumulators_i32"][:, 0, 0].tolist() == list(range(128))
        assert np.array_equal(clients["suffix"].last_inputs[0], result["dequantized_dw"])
        assert np.array_equal(clients["suffix"].last_inputs[1], prefix)
        assert result["job_receipts"] == [{
            "frame_id": 9, "request_id": 400, "weight_bytes": 6272,
            "pixel_bytes": 131072, "input_bytes": 137344,
            "output_bytes": 524288, "input_bytes_seen": 137344,
            "output_bytes_seen": 524288, "completed_frames": 1,
            "mm2s_done": True, "s2mm_done": True, "core_done": True,
            "error_code": 0, "submit_ms": 12.0, "complete_ms": 14.5}]
        assert result["components_ms"] == result["timing_ms"]
        assert len(result["input_sha256"]) == 64
        assert len(result["feature_sha256"]) == 64
    finally:
        runner.close()


def test_run_layer_binds_logical_to_hardware_frame_and_reports_dma_timing(tmp_path):
    runner, _, _, image, _ = _make_runner(tmp_path, layer_client=True)
    try:
        result = runner.infer_tensor(image, logical_frame_id=27)
        assert result["frame_mapping"] == {
            "logical_frame_id": 27, "hardware_frame_id": 9,
            "request_id": 400}
        assert result["job_receipts"][0]["completed_frames_before"] == 72
        assert result["job_receipts"][0]["completed_frames_after"] == 73
        assert result["timing_ms"]["dma_pack"] == 0.5
        assert result["timing_ms"]["dma_submit_to_completion"] == 1.25
        assert result["timing_ms"]["dma_output_copy"] == 0.75
        assert result["timing_ms"]["dma_backend_wall"] == 2.5
    finally:
        runner.close()


@pytest.mark.parametrize("bad_receipt", [
    {"mm2s_done": False}, {"s2mm_done": False}, {"core_done": False},
    {"error_code": 1}, {"input_bytes_seen": 137343},
    {"output_bytes_seen": 524287}, {"completed_frames": 0},
    {"output_shape": (128, 32, 31)}, {"request_id": 401}, {"frame_id": 10},
    {"submit_ms": "invalid"}, {"complete_ms": 11.0},
])
def test_run_layer_rejects_incomplete_or_malformed_frame(tmp_path, bad_receipt):
    runner, _, _, image, _ = _make_runner(tmp_path, layer_client=True)
    runner.batch_client.bad_receipt = bad_receipt
    try:
        with pytest.raises(ValueError):
            runner.infer_tensor(image)
        assert runner._failed
    finally:
        runner.close()


def test_run_layer_frame_and_request_sequence_wrap_across_images(tmp_path):
    runner, batch, _, image, _ = _make_runner(tmp_path, layer_client=True)
    batch.next_request_id = 0xffffffff
    runner._next_request_id = 0xffffffff
    batch.next_frame_id = 0xffffffff
    runner._next_frame_id = 0xffffffff
    try:
        first = runner.infer_tensor(image)
        second = runner.infer_tensor(image)
        assert first["frame_ids"] == [0xffffffff, 0xffffffff]
        assert first["job_receipts"][0]["request_id"] == 0xffffffff
        assert second["frame_ids"] == [0, 0]
        assert second["job_receipts"][0]["request_id"] == 0
        assert len(batch.layer_calls) == 2
    finally:
        runner.close()


def test_run_layer_requires_adapter_frame_sequence_seed(tmp_path):
    runner, batch, _, image, _ = _make_runner(tmp_path, layer_client=True)
    del batch.next_frame_id
    runner._next_frame_id = None
    try:
        with pytest.raises(ValueError, match="next_frame_id"):
            runner.infer_tensor(image)
        assert not batch.layer_calls
        assert runner._failed
    finally:
        runner.close()


def test_coordinator_adopts_batch_client_sequences_after_prior_jobs(tmp_path):
    split_dir = tmp_path / "split"
    split_dir.mkdir()
    _, split_sha = _make_small_split(split_dir)
    with open(str(DW / "weights-chw.i8"), "rb") as stream:
        weights = np.frombuffer(stream.read(), dtype=np.int8).reshape((128, 7, 7)).copy()
    batch = FakeBatchClient(weights, initial_job_id=40)
    batch.run(np.zeros((49,), dtype=np.int8), np.zeros((32, 32), dtype=np.int8))
    prefix_value = np.zeros((1, 128, 32, 32), dtype=np.float32)
    clients = {}

    def factory(stage, model_path, contract, runner_path, threads):
        client = FakeOrtClient(stage, contract, prefix_value)
        clients[stage] = client
        return client

    runner = PersistentDwS1(str(split_dir), str(DW), "unused", batch,
                           expected_split_manifest_sha256=split_sha,
                           ort_client_factory=factory)
    image = np.zeros((1, 3, 256, 256), dtype=np.float32)
    try:
        result = runner.infer_tensor(image)
        assert result["job_ids"] == [42, 169]
        assert result["job_receipts"][0]["request_id"] == 2
        assert result["job_receipts"][-1]["request_id"] == 129
    finally:
        runner.close()


def _make_synthetic_oracle(tmp_path, result, runner):
    oracle_dir = tmp_path / "oracle"
    oracle_dir.mkdir()
    arrays = {
        "quant": result["quantized_tensor"],
        "raw": result["dw_accumulators_i32"],
        "dequant": result["dequantized_dw"],
        "features": result["features"],
    }
    suffixes = {"quant": "ps-prefix-quant.i8", "raw": "dw-oracle.i32",
                "dequant": "dw-dequant.f32", "features": "mixed-features.f32"}
    case_sha = hashlib.sha256(np.ascontiguousarray(
        result["prefix_tensor"], dtype="<f4").tobytes()).hexdigest()
    files = {}
    for image in range(3):
        base = "image-%02d" % image
        for kind, array in arrays.items():
            path = oracle_dir / (base + "-" + suffixes[kind])
            dtype = {"quant":"|i1", "raw":"<i4", "dequant":"<f4", "features":"<f4"}[kind]
            payload = np.ascontiguousarray(array, dtype=dtype).tobytes()
            path.write_bytes(payload)
            files[path.name] = {"bytes": len(payload),
                                "sha256": hashlib.sha256(payload).hexdigest()}
    manifest = {"status":"INDEPENDENT_HOST_REFERENCE_FOR_ACTUAL_PS_INPUT_NOT_PL_RESULT",
                "quant_manifest_sha256": EXPECTED_DW_MANIFEST_SHA256,
                "split_manifest_sha256": runner.split_manifest_sha256,
                "host_suffix_ort_version":"1.20.1", "host_suffix_threads":2,
                "ps_prefix_threads_from_collector":4,
                "ps_prefix_collection_receipt_sha256":"6c17a0bb4cb8ed4c8a052570d270ad79fb984d1767518a8c3cba3afec445898e",
                "cases":[{"image":index, "actual_ps_prefix_sha256":case_sha,
                          "quantized_pixels_different_from_host":0,
                          "integer_outputs_different_from_host":0,
                          "integer_values":128 * 32 * 32} for index in range(3)],
                "files":files}
    path = oracle_dir / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return oracle_dir, hashlib.sha256(path.read_bytes()).hexdigest()


def test_actual_ps_oracle_is_pinned_and_integer_comparison_is_exact(tmp_path):
    baseline_dir = tmp_path / "baseline"
    baseline_dir.mkdir()
    baseline, _, _, image, _ = _make_runner(baseline_dir)
    try:
        baseline_result = baseline.infer_tensor(image, include_intermediates=True)
        oracle_dir, oracle_sha = _make_synthetic_oracle(tmp_path, baseline_result, baseline)
    finally:
        baseline.close()

    verify_dir = tmp_path / "verify"
    verify_dir.mkdir()
    runner, _, _, image, _ = _make_runner(
        verify_dir, actual_oracle_dir=str(oracle_dir),
        expected_actual_oracle_manifest_sha256=oracle_sha)
    try:
        result = runner.infer_tensor(image, oracle_case=0)
        assert result["actual_ps_oracle_sha256"] == oracle_sha
        assert runner.oracle["manifest"]["host_suffix_threads"] == 2
        assert runner.oracle["manifest"]["ps_prefix_threads_from_collector"] == 4
        assert result["oracle_feature_max_abs"] == 0.0
    finally:
        runner.close()

    timed_dir = tmp_path / "timed-output"
    timed_dir.mkdir()
    timed, _, _, image, _ = _make_runner(
        timed_dir, wrong_value_at=0, actual_oracle_dir=str(oracle_dir),
        expected_actual_oracle_manifest_sha256=oracle_sha)
    try:
        timed_result = timed.infer_tensor(image, validate_oracle=False)
        assert timed_result["actual_ps_oracle_sha256"] == oracle_sha
        assert not timed._failed
    finally:
        timed.close()

    bad_dir = tmp_path / "bad-output"
    bad_dir.mkdir()
    bad, _, _, image, _ = _make_runner(
        bad_dir, wrong_value_at=0, actual_oracle_dir=str(oracle_dir),
        expected_actual_oracle_manifest_sha256=oracle_sha)
    try:
        with pytest.raises(ValueError, match="INT32 outputs differ .* at 1 values"):
            bad.infer_tensor(image, oracle_case=0)
        assert bad._failed
    finally:
        bad.close()


@pytest.mark.parametrize("result", [
    {"request_id": 1, "job_id": 1, "weight_count": 48, "pixel_count": 1024,
     "output_count": 1024, "cycles": 1, "outputs_dtype": "<i4",
     "output_shape": (32, 32), "outputs": bytes(4096)},
    {"request_id": 1, "job_id": 1, "weight_count": 49, "pixel_count": 1024,
     "output_count": 1024, "cycles": 1, "outputs_dtype": "<i4",
     "output_shape": (32, 32), "outputs": bytes(4092)},
])
def test_receipt_count_and_frame_length_are_mandatory(result):
    with pytest.raises(ValueError):
        _validate_dw_result(result, 1)


def test_split_and_dw_manifest_sha_are_pinned_before_sessions(tmp_path):
    split_dir = tmp_path / "split"
    split_dir.mkdir()
    manifest_path, _ = _make_small_split(split_dir)
    modified = json.loads(manifest_path.read_text(encoding="utf-8"))
    modified["ort_threads"] = 3
    manifest_path.write_text(json.dumps(modified), encoding="utf-8")
    batch = FakeBatchClient(np.zeros((128, 7, 7), dtype=np.int8))
    with pytest.raises(ValueError, match="CPU split manifest SHA256"):
        PersistentDwS1(str(split_dir), str(DW), "unused", batch,
                       expected_split_manifest_sha256=EXPECTED_SPLIT_MANIFEST_SHA256,
                       expected_dw_manifest_sha256=EXPECTED_DW_MANIFEST_SHA256)
    assert batch.closed


def test_dw_file_tamper_rejected_by_manifest_file_hashes(tmp_path):
    split_dir = tmp_path / "split"
    split_dir.mkdir()
    _, split_sha = _make_small_split(split_dir)
    dw_dir = tmp_path / "dw"
    dw_dir.mkdir()
    with open(str(DW / "manifest.json"), "r") as stream:
        manifest = json.load(stream)
    for name in manifest["files"]:
        shutil.copyfile(str(DW / name), str(dw_dir / name))
    shutil.copyfile(str(DW / "manifest.json"), str(dw_dir / "manifest.json"))
    with open(str(dw_dir / "weight-scales.f64"), "r+b") as stream:
        stream.seek(0)
        stream.write(b"\x00")
    batch = FakeBatchClient(np.zeros((128, 7, 7), dtype=np.int8))
    with pytest.raises(ValueError, match="artifact SHA256 mismatch: weight-scales.f64"):
        PersistentDwS1(str(split_dir), str(dw_dir), "unused", batch,
                       expected_split_manifest_sha256=split_sha)
    assert batch.closed


def test_dequant_formula_uses_float64_scale_product_then_fp32_output():
    raw = np.zeros((128, 32, 32), dtype=np.int32)
    raw[3].fill(1234567)
    scales = np.full((128,), 0.125, dtype=np.float64)
    bias = np.zeros((128,), dtype=np.float32)
    bias[3] = -0.75
    output = dequantize_dw(raw, scales, bias)
    expected = np.float32(np.float64(1234567) *
                          (np.float64(ACTIVATION_SCALE) * np.float64(0.125)) +
                          np.float64(-0.75))
    assert output.dtype == np.dtype("float32")
    assert output[0, 3, 0, 0] == expected
