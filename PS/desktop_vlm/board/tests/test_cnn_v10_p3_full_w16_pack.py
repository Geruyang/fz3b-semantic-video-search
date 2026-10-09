import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cnn_v10_p3_full_w16_pack import (pack_full_w16, unpack_pw_w16_tiled,
    validate_slot_contract, slot_contract, to_hcw_a16_bytes, SIN)


def test_p3_final_slot_contract_is_slot0_prefix_only():
    record = slot_contract()
    assert validate_slot_contract(record)
    assert (record["slot_words"], record["slot_bytes"]) == (32768, 524288)
    assert (record["arena_words"], record["arena_bytes"]) == (69632, 1114112)
    assert (record["input"]["input_words"], record["input"]["input_bytes"]) == (32768, 524288)
    assert record["input"]["word_range"] == "slot0[0,32768)"
    assert record["input"]["byte_range"] == "slot0[0,524288)"
    assert record["dw_intermediate"]["word_range"] == "slot1[32768,49152)"
    assert record["dw_intermediate"]["byte_range"] == "slot1[524288,786432)"
    assert (record["dw_intermediate"]["output_valid_words"], record["dw_intermediate"]["output_valid_bytes"]) == (16384, 262144)
    assert record["final_output"]["word_range"] == "slot0[0,16384)"
    assert record["final_output"]["byte_range"] == "slot0[0,262144)"
    assert (record["final_output"]["output_valid_words"], record["final_output"]["output_valid_bytes"]) == (16384, 262144)
    assert record["completion"]["consumer"] == "P0 base0"


def test_input_hcw_a16_serialization_uses_frozen_scale_ties_even_and_layout():
    x = np.zeros((1, 64, 64, 64), dtype=np.float32)
    x[0, 0, 1, 2] = np.float32(SIN * 2.0)
    x[0, 1, 2, 3] = np.float32(-SIN * 4.0)
    raw = to_hcw_a16_bytes(x)
    assert len(raw) == 524288
    got = np.frombuffer(raw, dtype="<i2").reshape(64, 64, 64)
    assert got[1, 0, 2] == 2
    assert got[2, 1, 3] == -4


def test_full_w16_packer_uses_frozen_pw_tiles_and_roundtrips_exactly():
    dw = np.arange(128 * 49, dtype=np.int16).reshape(128, 49)
    pw = np.arange(128 * 128, dtype=np.int16).reshape(128, 128)
    bias = np.zeros(128, dtype=np.int64)
    multiplier = np.ones(128, dtype=np.int32)
    shift = np.full(128, 36, dtype=np.int32)
    gelu = np.zeros(32768, dtype=np.int16)
    image, layout = pack_full_w16(dw, bias, multiplier, shift, gelu,
                                  pw, bias, multiplier, shift, gelu)
    assert len(image) == 11280 * 16 == 180480
    assert layout["pw_weights_i16_tiled_goc4_k16"]["word_offset"] == 5008
    start = layout["pw_weights_i16_tiled_goc4_k16"]["byte_offset"]
    length = layout["pw_weights_i16_tiled_goc4_k16"]["byte_length"]
    restored = unpack_pw_w16_tiled(image[start:start + length])
    np.testing.assert_array_equal(restored, pw)
    tiled = pw.reshape(32, 4, 8, 16).transpose(0, 2, 1, 3)
    np.testing.assert_array_equal(np.frombuffer(image[start:start + length], dtype="<i2").reshape(tiled.shape), tiled)
