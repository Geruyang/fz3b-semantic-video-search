"""Focused checks for the board-pinned stage2 INT8 reference artifacts."""
import hashlib
import json
import os
from pathlib import Path
import unittest

import numpy as np

import build_stage2_int8_reference as ref


ROOT = Path(__file__).resolve().parents[3]
ARTIFACT = Path(os.environ.get(
    "STAGE2_INT8_REFERENCE_DIR",
    ROOT / "artifacts/board-debug-20261004/acceleration/host/stage2-dw3-dw7-int8-007"))


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class Stage2Int8ReferenceTests(unittest.TestCase):
    def test_int64_depthwise_reference_matches_manual_center_kernel(self):
        source = np.arange(-4, 5, dtype=np.int8).reshape(1, 3, 3)
        kernel = np.zeros((1, 1, 3, 3), dtype=np.int8)
        kernel[0, 0, 1, 1] = 7
        actual = ref._depthwise_accumulate(source, kernel)
        np.testing.assert_array_equal(actual, source.astype(np.int64) * 7)
        self.assertEqual(actual.dtype, np.int64)

    def test_float_reference_uses_ties_even_and_signed_clip(self):
        accum = np.asarray([[[1, 3, 5, -1, -3, -5, 999, -999]]], dtype=np.int64)
        ratio = np.asarray([0.5], dtype=np.float64)
        actual = ref._round_reference(accum, ratio)
        np.testing.assert_array_equal(actual, np.asarray([[[0, 2, 2, 0, -2, -2, 127, -127]]], dtype=np.int8))

    def test_manifest_pins_dual_output_and_preserves_host_dw7_failures(self):
        manifest_path = ARTIFACT / "manifest.json"
        self.assertTrue(manifest_path.is_file(), "run the stage2 reference builder first")
        report = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(report["status"], "STAGE2_INT8_CPU_REFERENCE_FROM_ACTUAL_BOARD_PS_TENSORS_NOT_PL")
        self.assertEqual(report["source_model_sha256"], ref.MODEL_SHA256)
        self.assertEqual(report["split_manifest_sha256"], ref.SPLIT_MANIFEST_SHA256)
        self.assertEqual(report["board_collection_manifest_sha256"], ref.COLLECTION_MANIFEST_SHA256)
        self.assertTrue(report["actual_board_outputs_are_authoritative"])
        self.assertTrue(report["host_ort_is_independent_comparison_only"])
        self.assertTrue(report["host_comparison_report"]["failures_preserved"])
        for sample_id in ("image-00", "image-01", "image-02"):
            comparison = report["host_comparison_report"]["dw7_allclose_by_sample"][sample_id]
            self.assertFalse(comparison["allclose_rtol_1e-4_atol_1e-5"])

        packet_contract = report["stage3_handoff"]["dual_output_packet_contract"]
        self.assertEqual(packet_contract["packet_shape"], [1, 128, 32, 32])
        self.assertEqual(packet_contract["packet_bytes"], 131072)
        self.assertEqual(packet_contract["zero_points"], {"dw3_q3": 0, "dw7_q7": 0})
        self.assertEqual(packet_contract["file_order"], ["DW3 q3 packet", "DW7 q7 packet"])
        for sample in report["results"]:
            files = sample["files"]
            packet_record = files["stage2_dual_output_packet"]
            packet_path = ARTIFACT / packet_record["path"]
            self.assertEqual(packet_path.stat().st_size, 262144)
            self.assertEqual(sha256(packet_path), packet_record["sha256"])
            q3 = np.fromfile(ARTIFACT / files["dw3-output.i8"]["path"], dtype=np.int8)
            q7 = np.fromfile(ARTIFACT / files["dw7-output.i8"]["path"], dtype=np.int8)
            packet = np.fromfile(packet_path, dtype=np.int8)
            np.testing.assert_array_equal(packet[:131072], q3)
            np.testing.assert_array_equal(packet[131072:], q7)
            self.assertEqual(packet_record["packets"][0]["scale"],
                             report["calibration"]["activation_scales"]["dw3_to_dw7"])
            self.assertEqual(packet_record["packets"][1]["scale"],
                             report["calibration"]["activation_scales"]["dw7_to_stage3"])
            self.assertTrue(sample["dw3_requantized_value_is_stage3_residual_source"])
            self.assertTrue(sample["dw7_requantized_value_is_stage3_main_input"])
            self.assertFalse(sample["dw7"]["requant_dequant_vs_actual_board_ps"][
                "allclose_rtol_1e-4_atol_1e-5"])


if __name__ == "__main__":
    unittest.main()
