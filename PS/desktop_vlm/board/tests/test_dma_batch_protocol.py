import sys
from pathlib import Path

import numpy as np
import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dma_batch_protocol import (DW128_INPUT_BYTES, DW128_OUTPUT_BYTES,
                                axis_last_tkeep, pack_dw128_input,
                                unpack_dw128_output)


def test_pack_dw128_input_interleaves_each_channels_weights_then_pixels():
    weights = np.zeros((128, 7, 7), dtype=np.int8)
    pixels = np.zeros((128, 32, 32), dtype=np.int8)
    weights[0].reshape(-1)[:] = np.arange(49, dtype=np.int8) - 24
    pixels[0].reshape(-1)[:4] = [-128, -1, 0, 127]
    weights[1].fill(-7)
    pixels[1].fill(9)

    packet = pack_dw128_input(weights, pixels)

    assert len(packet) == 137344 == DW128_INPUT_BYTES
    assert packet[:4] == bytes([232, 233, 234, 235])
    assert packet[48] == 24
    assert packet[49:53] == bytes([128, 255, 0, 127])
    assert packet[1073:1077] == bytes([249, 249, 249, 249])
    assert packet[1073 + 49:1073 + 53] == bytes([9, 9, 9, 9])


@pytest.mark.parametrize("weights_shape,pixels_shape", [
    ((127, 7, 7), (128, 32, 32)),
    ((128, 7, 7), (128, 31, 32)),
])
def test_pack_dw128_input_rejects_a_shape_that_would_change_the_dma_contract(
        weights_shape, pixels_shape):
    weights = np.zeros(weights_shape, dtype=np.int8)
    pixels = np.zeros(pixels_shape, dtype=np.int8)
    with pytest.raises(ValueError, match="shape"):
        pack_dw128_input(weights, pixels)


def test_pack_dw128_input_rejects_non_int8_instead_of_silently_narrowing():
    weights = np.zeros((128, 7, 7), dtype=np.int16)
    pixels = np.zeros((128, 32, 32), dtype=np.int8)
    with pytest.raises(ValueError, match="int8"):
        pack_dw128_input(weights, pixels)


def test_unpack_dw128_output_uses_little_endian_signed_int32_and_exact_length():
    payload = bytearray(524288)
    payload[0:4] = bytes([255, 255, 255, 255])
    payload[4:8] = bytes([120, 86, 52, 18])
    payload[-4:] = bytes([0, 0, 0, 128])

    output = unpack_dw128_output(bytes(payload))

    assert len(payload) == DW128_OUTPUT_BYTES
    assert output.shape == (128, 32, 32)
    assert output.dtype.str == "<i4"
    assert int(output[0, 0, 0]) == -1
    assert int(output[0, 0, 1]) == 0x12345678
    assert int(output[-1, -1, -1]) == -0x80000000
    with pytest.raises(ValueError, match="524288"):
        unpack_dw128_output(bytes(payload[:-4]))


def test_unpack_dw128_output_detaches_from_a_reusable_dma_slot():
    dma_slot = bytearray(524288)
    dma_slot[0:4] = bytes([1, 0, 0, 0])
    output = unpack_dw128_output(dma_slot)

    dma_slot[0:4] = bytes([2, 0, 0, 0])

    assert int(output[0, 0, 0]) == 1


@pytest.mark.parametrize("length,expected", [(8, 0xff), (13, 0x1f), (1, 0x01)])
def test_axis_last_tkeep_marks_only_contiguous_low_valid_lanes(length, expected):
    assert axis_last_tkeep(length, beat_bytes=8) == expected


def test_axis_last_tkeep_rejects_empty_packets():
    with pytest.raises(ValueError, match="positive"):
        axis_last_tkeep(0, beat_bytes=8)


@pytest.mark.parametrize("length,beat_bytes", [(8, 0), (8, -1), (8, True), (8, 4),
                                                (True, 8), (1.5, 8)])
def test_axis_last_tkeep_rejects_an_invalid_or_non_64_bit_contract(
        length, beat_bytes):
    with pytest.raises(ValueError):
        axis_last_tkeep(length, beat_bytes=beat_bytes)
