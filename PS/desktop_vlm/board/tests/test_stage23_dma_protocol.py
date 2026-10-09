import hashlib
import json
import shutil
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from stage23_dma_protocol import (
    DmaTransfer,
    NotReady,
    ProtocolError,
    STAGE2_BYTES,
    STAGE2_SEGMENT_BYTES,
    STAGE2_TLAST_OFFSET,
    STAGE3_OUTPUT_BYTES,
    STAGE3_TLAST_OFFSET,
    STAGE2_MANIFEST_SHA256,
    STAGE3_MANIFEST_SHA256,
    Stage23DmaProtocol,
    _read_record,
)


ROOT = Path(__file__).resolve().parents[3]
HOST = ROOT / "artifacts" / "board-debug-20261004" / "acceleration" / "host"
STAGE2 = HOST / "stage2-dw3-dw7-int16act-007"
STAGE3 = HOST / "stage3-network20-int16-004"
SAMPLES = ("image-00", "image-01", "image-02")


@pytest.fixture(scope="module")
def protocol():
    return Stage23DmaProtocol(STAGE2, STAGE3)


@pytest.mark.parametrize("sample_id", SAMPLES)
def test_frozen_stage2_packets_and_stage3_arrays_match_exact_contract(protocol, sample_id):
    sample = protocol.frozen_sample(sample_id)
    s2 = sample["stage2_receipt"]
    s3_inputs = sample["stage3_inputs"]
    s3 = sample["stage3_receipt"]

    assert s2.frame_id == sample_id
    assert len(s2.transfer.payload) == STAGE2_BYTES
    assert s2.transfer.tlast_offset == STAGE2_TLAST_OFFSET
    assert s2.transfer.sha256 == protocol.stage2_manifest["results"][int(sample_id[-2:])]["files"]["dual_accumulator_packet"]["sha256"]
    assert s2.dw3_accumulator.shape == (1, 128, 32, 32)
    assert s2.dw7_accumulator.shape == (1, 128, 32, 32)
    assert s2.dw3_accumulator.dtype == np.dtype("<i4")
    assert s2.dw7_accumulator.dtype == np.dtype("<i4")
    assert s2.dw3_residual_i16.shape == (1, 128, 32, 32)
    assert s2.dw7_stage3_i16.shape == (1, 128, 32, 32)
    assert s2.dw3_residual_i16.dtype == np.dtype("<i2")
    assert s2.dw7_stage3_i16.dtype == np.dtype("<i2")

    assert s3_inputs.dw7_i16.shape == (1, 128, 32, 32)
    assert s3_inputs.dw3_residual_i16.shape == (1, 128, 32, 32)
    assert s3_inputs.dw7_i16.dtype == np.dtype("<i2")
    assert s3_inputs.dw3_residual_i16.dtype == np.dtype("<i2")
    assert protocol.pw1["weight"].shape == (384, 128)
    assert protocol.pw2["weight"].shape == (128, 384)

    assert s3.output_i16.shape == (1, 128, 32, 32)
    assert s3.output_i16.dtype == np.dtype("<i2")
    assert len(s3.transfer.payload) == STAGE3_OUTPUT_BYTES
    assert s3.transfer.tlast_offset == STAGE3_TLAST_OFFSET
    assert s3.transfer.payload == s3.output_i16.tobytes(order="C")
    assert s3.source == "frozen-host-reference"


def test_stage2_offsets_are_exact_and_accumulators_are_not_bias_added_again(protocol):
    sample = protocol.frozen_sample("image-00")
    receipt = sample["stage2_receipt"]
    packed = protocol.pack_stage2_accumulators(
        receipt.frame_id, receipt.dw3_accumulator, receipt.dw7_accumulator)
    assert packed.payload == receipt.transfer.payload
    assert packed.payload[:STAGE2_SEGMENT_BYTES] == receipt.dw3_accumulator.astype("<i4").tobytes()
    assert packed.payload[STAGE2_SEGMENT_BYTES:] == receipt.dw7_accumulator.astype("<i4").tobytes()
    assert packed.tlast_offset == STAGE2_TLAST_OFFSET

    scale3 = protocol.s2_dw3["accumulator_scale"].reshape(1, 128, 1, 1)
    scale7 = protocol.s2_dw7["accumulator_scale"].reshape(1, 128, 1, 1)
    expected3 = receipt.dw3_accumulator.astype(np.float64) * scale3
    expected7 = receipt.dw7_accumulator.astype(np.float64) * scale7
    np.testing.assert_array_equal(receipt.dw3_reconstructed, expected3)
    np.testing.assert_array_equal(receipt.dw7_reconstructed, expected7)
    assert receipt.dw3_reconstructed.dtype == np.dtype("float64")
    assert receipt.dw7_reconstructed.dtype == np.dtype("float64")
    bias3 = protocol.stage2_manifest["stage2_jtag_parameters"]["dw3"]["bias_i32_file"]
    bias7 = protocol.stage2_manifest["stage2_jtag_parameters"]["dw7"]["bias_i32_file"]
    b3 = _read_record(STAGE2, bias3, "DW3 bias").reshape(1, 128, 1, 1)
    b7 = _read_record(STAGE2, bias7, "DW7 bias").reshape(1, 128, 1, 1)
    assert not np.array_equal(receipt.dw3_reconstructed, (receipt.dw3_accumulator + b3) * scale3)
    assert not np.array_equal(receipt.dw7_reconstructed, (receipt.dw7_accumulator + b7) * scale7)


def test_q31_requant_uses_signed_ties_even_and_clips_activation_range(protocol):
    accum = np.zeros((1, 128, 32, 32), dtype="<i4")
    accum[0, :6, 0, 0] = [3, 5, -3, -5, 65535, -65535]
    params = {"multiplier": np.ones((128,), dtype="<i4"),
              "shift": np.ones((128,), dtype="<i4")}
    quantized = protocol._requant_stage2(accum, params)
    assert quantized[0, :6, 0, 0].tolist() == [2, 2, -2, -2, 32767, -32767]
    assert int(quantized.max()) <= 32767
    assert int(quantized.min()) >= -32767


def test_stage2_and_stage3_external_packets_take_only_one_predw3_tensor(protocol):
    sample = protocol.frozen_sample("image-00")
    pre = sample["pre_dw3_i16"][None, ...]
    expected_input = sample["pre_dw3_i16"].astype("<i2").tobytes(order="C")
    _, input2 = protocol.pack_stage2_input("image-00", pre)
    _, input3 = protocol.pack_stage3_input("image-00", pre)
    assert input2.payload == expected_input
    assert input3.payload == expected_input
    assert len(input2.payload) == len(input3.payload) == 262144
    assert input2.tlast_offset == input3.tlast_offset == 262143

    seen2 = []
    def fake_stage2(frame_id, transfer):
        seen2.append((frame_id, transfer))
        return sample["stage2_receipt"].transfer

    receipt2 = protocol.submit_stage2("image-00", pre, executor=fake_stage2)
    assert receipt2.transfer.payload == sample["stage2_receipt"].transfer.payload
    assert seen2[0][0] == "image-00" and seen2[0][1].payload == expected_input

    seen3 = []
    def fake_stage3(frame_id, transfer):
        seen3.append((frame_id, transfer))
        return sample["stage3_receipt"].transfer

    receipt3 = protocol.submit_stage3("image-00", pre, executor=fake_stage3)
    assert receipt3.transfer.payload == sample["stage3_receipt"].transfer.payload
    assert seen3[0][0] == "image-00" and seen3[0][1].payload == expected_input


def test_no_executor_reports_not_ready_and_does_not_guess_driver_mode(protocol):
    sample = protocol.frozen_sample("image-00")
    pre = sample["pre_dw3_i16"][None, ...]
    with pytest.raises(NotReady, match="driver mode/register ABI"):
        protocol.submit_stage2("image-00", pre)
    with pytest.raises(NotReady, match="driver mode/register ABI"):
        protocol.submit_stage3("image-00", pre)


def test_packets_reject_wrong_tlast_size_frame_and_input_dtype_or_shape(protocol):
    sample = protocol.frozen_sample("image-00")
    with pytest.raises(ProtocolError, match="TLAST"):
        protocol.unpack_stage2_receipt("image-00", DmaTransfer(sample["stage2_receipt"].transfer.payload,
                                                                 STAGE2_TLAST_OFFSET - 1))
    with pytest.raises(ProtocolError, match="frame_id"):
        protocol.unpack_stage2_receipt("image-01", sample["stage2_receipt"].transfer)
    with pytest.raises(ProtocolError, match="length"):
        protocol.unpack_stage2_receipt("image-00", DmaTransfer(b"x", STAGE2_TLAST_OFFSET))
    with pytest.raises(ProtocolError, match="shape"):
        protocol.pack_stage2_input(1, np.zeros((128, 32, 32), dtype=np.int16))
    with pytest.raises(ProtocolError, match="dtype"):
        protocol.pack_stage3_input(1, np.zeros((1, 128, 32, 32), dtype=np.int8))


def test_stage3_rejects_two_tensor_external_fake_and_wrong_output_tlast(protocol):
    sample = protocol.frozen_sample("image-00")
    pre = sample["pre_dw3_i16"][None, ...]
    def bad_executor(frame_id, transfer):
        assert isinstance(transfer, DmaTransfer)
        return DmaTransfer(sample["stage3_receipt"].transfer.payload,
                           STAGE3_TLAST_OFFSET - 1, frame_id)
    with pytest.raises(ProtocolError, match="final byte"):
        protocol.submit_stage3("image-00", pre, executor=bad_executor)


def test_frozen_manifest_sha_and_consumed_file_sha_are_strict(protocol, tmp_path):
    altered_dir = tmp_path / "s2"
    altered_dir.mkdir()
    manifest_bytes = (STAGE2 / "manifest.json").read_bytes()
    (altered_dir / "manifest.json").write_bytes(manifest_bytes + b"\n")
    with pytest.raises(ProtocolError, match="manifest SHA-256 mismatch"):
        Stage23DmaProtocol(altered_dir, STAGE3)

    record = protocol.stage2_manifest["stage2_jtag_parameters"]["dw3"]["weight_file"]
    corrupt_dir = tmp_path / "corrupt"
    corrupt_dir.mkdir()
    raw = (STAGE2 / record["path"]).read_bytes()
    (corrupt_dir / record["path"]).write_bytes(bytes([raw[0] ^ 1]) + raw[1:])
    with pytest.raises(ProtocolError, match="SHA-256 mismatch"):
        _read_record(corrupt_dir, record, "corrupt weight")


def test_frozen_authority_hashes_are_the_expected_accepted_versions(protocol):
    assert hashlib.sha256((STAGE2 / "manifest.json").read_bytes()).hexdigest() == STAGE2_MANIFEST_SHA256
    assert hashlib.sha256((STAGE3 / "manifest.json").read_bytes()).hexdigest() == STAGE3_MANIFEST_SHA256
    assert protocol.stage3_manifest["stage2_b_manifest_sha256"] == STAGE2_MANIFEST_SHA256
