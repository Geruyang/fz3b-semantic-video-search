"""Tests for ABI-v6 bridge profile offsets and initialized spans."""

import unittest

from desktop_vlm.board.cnn_pipeline_v6_bridge_contract import (
    BRIDGE_PROFILES,
    validate_input_offset,
    validate_bridge_submit,
    validate_normal_submit,
)


class CnnPipelineV6BridgeContractTests(unittest.TestCase):
    def test_profile_spans_match_frozen_dw_and_pw_shapes(self):
        expected = {
            3: (32768, 16384, 0, 0, 32768),
            4: (16384, 16384, 0, 32768, 16384),
            5: (16384, 8192, 16384, 0, 16384),
            6: (8192, 8192, 0, 0, 8192),
        }
        self.assertEqual(
            {profile: (spec.input_words, spec.output_words,
                       spec.activation_base_offset_words,
                       spec.input_offset_words, spec.output_offset_words)
             for profile, spec in BRIDGE_PROFILES.items()}, expected)
        self.assertEqual(BRIDGE_PROFILES[3].logical_name, "n1_dw")
        self.assertEqual(BRIDGE_PROFILES[4].logical_name, "n1_pw")
        self.assertEqual(BRIDGE_PROFILES[5].logical_name, "n3_dw")
        self.assertEqual(BRIDGE_PROFILES[6].logical_name, "n3_pw")

    def test_chained_p4_reads_p3_output_without_overlapping_its_own_output(self):
        p3 = validate_bridge_submit(3, 1, 0, 0, 65536 * 16,
                                    [(0, 32768 * 16)])
        p4 = validate_bridge_submit(4, 1, 32768 * 16, 0, 65536 * 16,
                                    [p3["output_span"]])
        self.assertEqual(p3["output_span"], (32768 * 16, 49152 * 16))
        self.assertEqual(p4["input_span"], p3["output_span"])
        self.assertEqual(p4["output_span"], (16384 * 16, 32768 * 16))
        self.assertTrue(p4["output_span"][1] <= p4["input_span"][0])

    def test_p5_then_ps_reupload_makes_p6_slot0_initialized(self):
        p5 = validate_bridge_submit(5, 1, 0, 16384 * 16, 65536 * 16,
                                    [(16384 * 16, 32768 * 16)])
        self.assertEqual(p5["output_span"], (32768 * 16, 40960 * 16))
        p6 = validate_bridge_submit(6, 1, 0, 0, 65536 * 16,
                                    [(0, 8192 * 16)])
        self.assertEqual(p6["output_span"], (8192 * 16, 16384 * 16))

    def test_rejects_wrong_offset_blocks_extent_overlap_or_uninitialized_input(self):
        with self.assertRaisesRegex(ValueError, "block_count"):
            validate_bridge_submit(3, 2, 0, 0, 65536 * 16, [(0, 32768 * 16)])
        with self.assertRaisesRegex(ValueError, "input_offset"):
            validate_bridge_submit(4, 1, 0, 0, 65536 * 16,
                                   [(32768 * 16, 49152 * 16)])
        with self.assertRaisesRegex(ValueError, "allocation"):
            validate_bridge_submit(3, 1, 0, 0, 49152 * 16 - 16,
                                   [(0, 32768 * 16)])
        with self.assertRaisesRegex(ValueError, "initialized"):
            validate_bridge_submit(5, 1, 0, 16384 * 16, 65536 * 16, [])

    def test_normal_profiles_forbid_nonzero_input_offset(self):
        for profile in (0, 1, 2):
            self.assertEqual(validate_input_offset(profile, 0), 0)
            with self.assertRaisesRegex(ValueError, "normal profile"):
                validate_input_offset(profile, 16)

    def test_normal_profiles_apply_base_to_both_slots_and_require_initialized_input(self):
        n2 = validate_normal_submit(
            0, 12, 16384 * 16, 0, 65536 * 16, 16384,
            [(16384 * 16, 32768 * 16)])
        self.assertEqual(n2["input_span"], (16384 * 16, 32768 * 16))
        self.assertEqual(n2["output_span"], (16384 * 16, 32768 * 16))
        n4 = validate_normal_submit(
            1, 20, 8192 * 16, 0, 65536 * 16, 8192,
            [(8192 * 16, 16384 * 16)])
        self.assertEqual(n4["output_span"], (8192 * 16, 16384 * 16))
        with self.assertRaisesRegex(ValueError, "two slots"):
            validate_normal_submit(
                0, 12, 16384 * 16, 0, 49152 * 16 - 16, 16384,
                [(16384 * 16, 32768 * 16)])


if __name__ == "__main__":
    unittest.main()
