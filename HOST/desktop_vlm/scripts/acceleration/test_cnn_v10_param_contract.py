from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
import cnn_v10_pack as packer
import cnn_v10_param_contract as v10


FIXTURES = {
    0: ROOT / "artifacts/board-debug-20261005/acceleration/host/root-v5-full-fixtures-001/profile0/params-12-blocks.bin",
    1: ROOT / "artifacts/board-debug-20261005/acceleration/host/root-v5-full-fixtures-001/profile1/params-20-blocks.bin",
    2: ROOT / "artifacts/board-debug-20261005/acceleration/host/root-v5-profile2-full-fixtures-001/profile2/params-4-blocks.bin",
}
V9_RECEIPT = ROOT / "artifacts/board-debug-20261005/acceleration/jtag/cnn-v9-native-full-002/receipt.json"


class V10ContractTest(unittest.TestCase):
    def test_identity_layout_and_arena(self):
        self.assertEqual(v10.CORE_IDENTITY, 0x465A5641)
        self.assertEqual(v10.ABI_IDENTITY, 0x000A0001)
        self.assertEqual(v10.SOFTWARE_IDENTITY, "sw10.1")
        expected = {64: (10985, 7913, 9449), 128: (21081, 8793, 14937),
                    256: (59705, 10553, 35129)}
        for c, (stride, pw1, pw2) in expected.items():
            layout = v10.v10_layout(c)
            self.assertEqual(layout["stride"][1] // 16, stride)
            self.assertEqual(layout["pw1"][0] // 16, pw1)
            self.assertEqual(layout["pw2"][0] // 16, pw2)
        for p, cfg in v10.PROFILE_CONFIG.items():
            self.assertEqual(v10.arena_words(p), 2 * cfg["slot_words"] + 4096)

    def test_pw4x16_exact_roundtrip_and_pw1_order(self):
        for c in (64, 128, 256):
            outputs, inputs = 3 * c, c
            values = (np.arange(outputs * inputs, dtype=np.int64) * 73 + 19)
            matrix = ((values % 65535) - 32767).astype("<i2").reshape(outputs, inputs)
            payload = v10.pack_pw4x16(matrix, outputs, inputs)
            self.assertEqual(len(payload), outputs * inputs * 2)
            first = np.frombuffer(payload[:128], dtype="<i2").reshape(4, 16)
            np.testing.assert_array_equal(first, matrix[:4, :16])
            np.testing.assert_array_equal(v10.unpack_pw4x16(payload, outputs, inputs), matrix)

    def test_pw2_r_outer_group_inner_against_independent_logical_oracle(self):
        outputs, inputs = 8, 32
        matrix = np.asarray([[1000 * out + lane for lane in range(inputs)]
                             for out in range(outputs)], dtype="<i2")
        payload = v10.pack_pw2_r_group_4x16(matrix, outputs, inputs)
        expected_values = []
        expected_tile_origins = []
        for red in range(inputs // 16):
            for group in range(outputs // 4):
                expected_tile_origins.append((red, group))
                for output_lane in range(4):
                    for input_lane in range(16):
                        expected_values.append(
                            1000 * (group * 4 + output_lane) +
                            red * 16 + input_lane)
        expected = np.asarray(expected_values, dtype="<i2").tobytes()
        self.assertEqual(payload, expected)
        self.assertEqual(expected_tile_origins,
                         [(0, 0), (0, 1), (1, 0), (1, 1)])
        self.assertNotEqual(payload, v10.pack_pw4x16(matrix, outputs, inputs))
        np.testing.assert_array_equal(
            v10.unpack_pw2_r_group_4x16(payload, outputs, inputs), matrix)

    def test_real_frozen_params_repack_bit_exact(self):
        for profile, path in FIXTURES.items():
            cfg = v10.profile_config(profile)
            source = path.read_bytes()
            old = v10.v5_layout(cfg["channels"])
            blocks = cfg["max_blocks"]
            self.assertEqual(len(source), blocks * old["stride"][1])
            for block in range(blocks):
                raw = source[block * old["stride"][1]:(block + 1) * old["stride"][1]]
                packed = packer.repack_block(raw, profile, block)
                new = v10.v10_layout(cfg["channels"])
                for name in ("dw3", "dw7", "bias", "multiplier", "shift",
                             "scale_multiplier", "scale_shift", "residual"):
                    oo, size = old[name]
                    no, nsize = new[name]
                    self.assertEqual(size, nsize)
                    self.assertEqual(packed[no:no + size], raw[oo:oo + size])
                old_gelu = np.frombuffer(raw[old["gelu"][0]:old["gelu"][0] + old["gelu"][1]], dtype="<i2")
                np.testing.assert_array_equal(v10.reconstruct_gelu(packed, profile, block), old_gelu)
                old_pw1 = v10.unpack_v5_pw6x16(raw[old["pw1"][0]:old["pw1"][0] + old["pw1"][1]],
                                               3 * cfg["channels"], cfg["channels"])
                old_pw2 = v10.unpack_v5_pw6x16(raw[old["pw2"][0]:old["pw2"][0] + old["pw2"][1]],
                                               cfg["channels"], 3 * cfg["channels"])
                np.testing.assert_array_equal(
                    v10.unpack_pw4x16(packed[new["pw1"][0]:new["pw1"][0] + new["pw1"][1]],
                                      3 * cfg["channels"], cfg["channels"]), old_pw1)
                np.testing.assert_array_equal(
                    v10.unpack_pw2_r_group_4x16(
                        packed[new["pw2"][0]:new["pw2"][0] + new["pw2"][1]],
                        cfg["channels"], 3 * cfg["channels"]), old_pw2)

    def test_bad_clipped_gelu_rejected_middle_preserved(self):
        profile = 2
        cfg = v10.profile_config(profile)
        old = v10.v5_layout(cfg["channels"])
        source = bytearray(FIXTURES[profile].read_bytes()[:old["stride"][1]])
        bound = v10.gelu_bound(profile, 0)
        gelu_off = old["gelu"][0]
        source[gelu_off + 2 * (bound.zero_prefix - 1):gelu_off + 2 * bound.zero_prefix] = (1).to_bytes(2, "little", signed=True)
        with self.assertRaisesRegex(ValueError, "prefix"):
            packer.repack_block(source, profile, 0)
        source = bytearray(FIXTURES[profile].read_bytes()[:old["stride"][1]])
        source[gelu_off + 2 * bound.tail_start:gelu_off + 2 * (bound.tail_start + 1)] = (32766).to_bytes(2, "little", signed=True)
        with self.assertRaisesRegex(ValueError, "tail"):
            packer.repack_block(source, profile, 0)
        source = bytearray(FIXTURES[profile].read_bytes()[:old["stride"][1]])
        middle = bound.zero_prefix
        source[gelu_off + 2 * middle:gelu_off + 2 * (middle + 1)] = (-1234).to_bytes(2, "little", signed=True)
        packed = packer.repack_block(source, profile, 0)
        self.assertEqual(int(v10.reconstruct_gelu(packed, profile, 0)[middle]), -1234)

    def test_invocation_gate(self):
        for profile, cfg in v10.PROFILE_CONFIG.items():
            v10.validate_invocation(profile, cfg["max_blocks"],
                                    cfg["max_blocks"] * v10.stride_words(cfg["channels"]),
                                    cfg["slot_words"], v10.arena_words(profile), 0)
            bad = [
                (0, cfg["max_blocks"] * v10.stride_words(cfg["channels"]), cfg["slot_words"], v10.arena_words(profile), 0),
                (cfg["max_blocks"], 0, cfg["slot_words"], v10.arena_words(profile), 0),
                (cfg["max_blocks"], cfg["max_blocks"] * v10.stride_words(cfg["channels"]), cfg["slot_words"] + 1, v10.arena_words(profile), 0),
                (cfg["max_blocks"], cfg["max_blocks"] * v10.stride_words(cfg["channels"]), cfg["slot_words"], v10.arena_words(profile) + 1, 0),
                (cfg["max_blocks"], cfg["max_blocks"] * v10.stride_words(cfg["channels"]), cfg["slot_words"], v10.arena_words(profile), 1),
            ]
            for args in bad:
                with self.assertRaises(ValueError):
                    v10.validate_invocation(profile, *args)

    def test_v9_frozen_sources_unchanged(self):
        receipt = json.loads(V9_RECEIPT.read_text(encoding="utf-8-sig"))
        base = ROOT / "desktop_vlm/hardware/acceleration"
        for name, expected in receipt["source_sha256"].items():
            actual = hashlib.sha256((base / name).read_bytes()).hexdigest()
            self.assertEqual(actual, expected, name)


if __name__ == "__main__":
    unittest.main(verbosity=2)

