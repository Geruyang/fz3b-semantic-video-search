import hashlib
import os
import sys

import numpy as np
import pytest


BOARD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ROOT = os.path.abspath(os.path.join(BOARD_DIR, "..", ".."))
if BOARD_DIR not in sys.path:
    sys.path.insert(0, BOARD_DIR)

from partition_stage23_s1 import (PRE_DW3, PersistentStage23S1,
                                  RUNTIME_SPLIT_MANIFEST_SHA256)
from stage23_dma_protocol import DmaTransfer, NotReady, Stage23DmaProtocol


RUNTIME_DIR = os.path.join(
    ROOT, "artifacts", "board-debug-20261004", "acceleration", "host",
    "stage23-runtime-split-001")
STAGE2_DIR = os.path.join(
    ROOT, "artifacts", "board-debug-20261004", "acceleration", "host",
    "stage2-dw3-dw7-int16act-007")
STAGE3_DIR = os.path.join(
    ROOT, "artifacts", "board-debug-20261004", "acceleration", "host",
    "stage3-network20-int16-004")


class FrozenBackend(object):
    execution_identity = {"pl_execution": False, "kind": "frozen-contract-test"}

    def __init__(self, protocol, sample_id):
        self.sample = protocol.frozen_sample(sample_id)

    def _result(self, logical_frame_id, transfer):
        return {"transfer": transfer,
                "logical_frame_id": logical_frame_id,
                "hardware_frame_id": 41,
                "request_id": 9,
                "completed_frames_before": 100,
                "completed_frames_after": 101,
                "timing_ms": {"submit_to_completion": 1.25}}

    def run_stage2(self, logical_frame_id, input_transfer):
        expected = self.sample["pre_dw3_i16"].astype("<i2", copy=False).tobytes(order="C")
        assert input_transfer.payload == expected
        frozen = self.sample["stage2_receipt"].transfer
        return self._result(logical_frame_id,
                            DmaTransfer(frozen.payload, frozen.tlast_offset,
                                        logical_frame_id))

    def run_stage3(self, logical_frame_id, input_transfer):
        expected = self.sample["pre_dw3_i16"].astype("<i2", copy=False).tobytes(order="C")
        assert input_transfer.payload == expected
        frozen = self.sample["stage3_receipt"].transfer
        return self._result(logical_frame_id,
                            DmaTransfer(frozen.payload, frozen.tlast_offset,
                                        logical_frame_id))


class FrozenOrtClient(object):
    def __init__(self, name, stage, contract, protocol, sample_id):
        self.name = name
        self.stage = stage
        self.contract = contract
        self.protocol = protocol
        self.sample = protocol.frozen_sample(sample_id)
        self.closed = False

    def infer(self, values):
        if self.name == "prefix":
            scale = self.protocol.stage2_manifest["stage2_jtag_parameters"]["dw3"]["input_scale"]
            value = (self.sample["pre_dw3_i16"].astype(np.float64) * scale).astype(np.float32)[None, :]
            return {PRE_DW3: value}, 2.0
        if self.stage == 2:
            expected = self.sample["stage2_receipt"]
            np.testing.assert_array_equal(
                values[0], expected.dw3_reconstructed.astype(np.float32))
            np.testing.assert_array_equal(
                values[1], expected.dw7_reconstructed.astype(np.float32))
        else:
            expected = self.sample["stage3_receipt"].output_i16.astype(np.float64)
            scale = self.protocol.stage3_manifest["activation_scales"]["block_output"]
            np.testing.assert_array_equal(values[0], (expected * scale).astype(np.float32))
        path = os.path.join(RUNTIME_DIR,
                            "image-00-stage%d-feature.f32" % self.stage)
        feature = np.fromfile(path, dtype="<f4").reshape((1, 512))
        return {"features": feature}, 3.0

    def close(self):
        self.closed = True


def make_runtime(stage):
    protocol = Stage23DmaProtocol(STAGE2_DIR, STAGE3_DIR)
    backend = FrozenBackend(protocol, "image-00")

    def factory(name, unused_model_path, contract, unused_threads):
        return FrozenOrtClient(name, stage, contract, protocol, "image-00")

    return PersistentStage23S1(
        stage, RUNTIME_DIR, STAGE2_DIR, STAGE3_DIR, "unused-runner", backend,
        prefix_threads=1, suffix_threads=3,
        expected_runtime_manifest_sha256=RUNTIME_SPLIT_MANIFEST_SHA256,
        ort_client_factory=factory, allow_non_pl_backend=True)


@pytest.mark.parametrize("stage", [2, 3])
def test_frozen_frame_runs_through_persistent_runtime(stage):
    runtime = make_runtime(stage)
    sample = runtime.protocol.frozen_sample("image-00")
    try:
        result = runtime.infer_tensor(np.zeros((1, 3, 256, 256), dtype=np.float32), 7)
    finally:
        runtime.close()
    assert result["stage"] == stage
    assert result["pl_execution"] is False
    assert result["frame_mapping"] == {
        "logical_frame_id": 7, "hardware_frame_id": 41, "request_id": 9,
        "completed_frames_before": 100, "completed_frames_after": 101}
    assert result["backend_identity"]["kind"] == "frozen-contract-test"
    assert result["timing_ms"]["backend_submit_to_completion"] == 1.25
    assert result["pl_input_sha256"] == hashlib.sha256(
        sample["pre_dw3_i16"].astype("<i2", copy=False).tobytes(order="C")).hexdigest()
    expected_receipt = sample["stage2_receipt"] if stage == 2 else sample["stage3_receipt"]
    assert result["pl_output_sha256"] == expected_receipt.transfer.sha256


def test_non_pl_backend_is_rejected_without_explicit_contract_test_opt_in():
    protocol = Stage23DmaProtocol(STAGE2_DIR, STAGE3_DIR)
    with pytest.raises(NotReady, match="non-PL backend"):
        PersistentStage23S1(
            2, RUNTIME_DIR, STAGE2_DIR, STAGE3_DIR, "unused-runner",
            FrozenBackend(protocol, "image-00"), ort_client_factory=lambda *args: None)


def test_completion_counter_must_advance_once():
    runtime = make_runtime(2)
    original = runtime.backend.run_stage2

    def stale(logical_frame_id, input_transfer):
        result = original(logical_frame_id, input_transfer)
        result["completed_frames_after"] = result["completed_frames_before"]
        return result

    runtime.backend.run_stage2 = stale
    try:
        with pytest.raises(Exception, match="completion counter"):
            runtime.infer_tensor(np.zeros((1, 3, 256, 256), dtype=np.float32), 8)
        assert runtime._failed is True
    finally:
        runtime.close()


def test_runtime_stages_execute_inside_bounded_pipeline():
    runtime = make_runtime(3)
    pipeline = runtime.create_pipeline(queue_capacity=1, run_timeout_s=5.0,
                                       cleanup_timeout_s=0.5)
    try:
        results = pipeline.run(
            [(11, np.zeros((1, 3, 256, 256), dtype=np.float32))], [11],
            validator=lambda frame_id, value: (
                frame_id == 11 and value["frame_mapping"]["logical_frame_id"] == 11))
    finally:
        runtime.close()
    assert len(results) == 1
    assert results[0].correct is True
    assert set(results[0].components_ms) == {"prefix", "backend", "suffix"}
    assert results[0].value["pl_execution"] is False


def test_runtime_rejects_replayed_hardware_and_request_sequence():
    runtime = make_runtime(2)
    try:
        runtime.infer_tensor(np.zeros((1, 3, 256, 256), dtype=np.float32), 20)
        with pytest.raises(Exception, match="hardware frame sequence"):
            runtime.infer_tensor(np.zeros((1, 3, 256, 256), dtype=np.float32), 21)
        assert runtime._failed is True
    finally:
        runtime.close()


def test_runtime_requires_explicit_transfer_logical_frame():
    runtime = make_runtime(3)
    original = runtime.backend.run_stage3

    def missing_frame(logical_frame_id, input_transfer):
        result = original(logical_frame_id, input_transfer)
        result["transfer"].frame_id = None
        return result

    runtime.backend.run_stage3 = missing_frame
    try:
        with pytest.raises(Exception, match="carry the submitted logical frame"):
            runtime.infer_tensor(np.zeros((1, 3, 256, 256), dtype=np.float32), 22)
    finally:
        runtime.close()
