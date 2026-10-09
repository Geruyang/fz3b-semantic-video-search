import sys
import unittest

import numpy as np

from cnn_w16_contract import (PROFILES, expected_stride, layout, pack_pw_i16,
                              q31_round_even_wide, checked_i48)


class W16ContractTests(unittest.TestCase):
    def test_frozen_profile_sizes(self):
        expected = {
            0: (128, 358928, 22433, 262144, 12),
            1: (256, 976912, 61057, 131072, 20),
            2: (64, 195088, 12193, 524288, 4),
        }
        for profile, (channels, stride, words, slot, blocks) in expected.items():
            with self.subTest(profile=profile):
                spec = PROFILES[profile]
                fields, got = layout(channels)
                self.assertEqual((spec["channels"], got, got // 16,
                                  channels * spec["width"] ** 2 * 2, spec["blocks"]),
                                 (channels, stride, words, slot, blocks))
                self.assertEqual(fields[-1]["offset"] + fields[-1]["bytes"], stride)
                self.assertTrue(all(f["offset"] % 16 == 0 for f in fields))

    def test_wide_q31_signed_ties_even(self):
        self.assertEqual(q31_round_even_wide(5, 1, 1), 2)
        self.assertEqual(q31_round_even_wide(7, 1, 1), 4)
        self.assertEqual(q31_round_even_wide(-5, 1, 1), -2)
        self.assertEqual(q31_round_even_wide(-7, 1, 1), -4)
        self.assertEqual(q31_round_even_wide(1, -(1 << 31), 31), -1)
        self.assertGreater(q31_round_even_wide((1 << 47) - 1, (1 << 31) - 1, 31), 0)

    def test_pw_tile_group_reduction_order_and_zero_padding(self):
        matrix = np.arange(7 * 16, dtype=np.int16).reshape(7, 16).astype("<i2")
        packed = pack_pw_i16(matrix, 7, 16)
        self.assertEqual(len(packed), 2 * 192)
        tiles = np.frombuffer(packed, dtype="<i2").reshape(2, 6, 16)
        np.testing.assert_array_equal(tiles[0, :6], matrix[:6])
        np.testing.assert_array_equal(tiles[1, 0], matrix[6])
        np.testing.assert_array_equal(tiles[1, 1:], 0)

    def test_signed48_bounds(self):
        self.assertEqual(checked_i48(-(1 << 47)), -(1 << 47))
        self.assertEqual(checked_i48((1 << 47) - 1), (1 << 47) - 1)
        with self.assertRaises(OverflowError):
            checked_i48(1 << 47)


if __name__ == "__main__":
    unittest.main()
