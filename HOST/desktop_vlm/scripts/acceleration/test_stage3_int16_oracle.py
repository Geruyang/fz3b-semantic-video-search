"""Contract checks for the full network.2.0 stage3 CPU oracle."""
import hashlib
import json
import os
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[3]
STAGE3 = Path(os.environ.get(
    "STAGE3_INT16_ORACLE_DIR",
    ROOT / "artifacts/board-debug-20261004/acceleration/host/stage3-network20-int16-004"))
B_STAGE2 = ROOT / "artifacts/board-debug-20261004/acceleration/host/stage2-dw3-dw7-int16act-007"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class Stage3Int16OracleTests(unittest.TestCase):
    def test_stage2_packet_identity_and_single_tlast_contract(self):
        report = json.loads((STAGE3 / "manifest.json").read_text(encoding="utf-8"))
        contract = report["stage2_to_stage3_physical_packet"]
        self.assertEqual(contract["packet_count"], 1)
        self.assertEqual(contract["total_bytes"], 1048576)
        self.assertEqual(contract["segment_0"]["offset_bytes"], 0)
        self.assertEqual(contract["segment_1"]["offset_bytes"], 524288)
        self.assertIn("only at packet byte offset 1048575", contract["TLAST"])
        for item in report["results"]:
            packet = item["stage2_boundary_packet"]
            self.assertEqual(packet["path"], item["stage2_boundary_packet"]["path"])
            self.assertEqual(packet["total_bytes"], 1048576)
            self.assertEqual(sha(B_STAGE2 / packet["path"]), packet["sha256"])

    def test_full_stage3_quant_files_and_boundary_metadata(self):
        report = json.loads((STAGE3 / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(report["status"], "STAGE3_FULL_BLOCK_INT16_ACTIVATION_INT8_WEIGHT_CPU_ORACLE_NOT_PL")
        self.assertFalse(report["pl_execution"])
        shapes = report["shape_and_layout"]
        self.assertEqual(shapes["input_main"]["shape"], [1, 128, 32, 32])
        self.assertEqual(shapes["input_residual"]["dtype"], "signed INT16 little-endian NCHW")
        self.assertEqual(shapes["fc1_output"]["shape"], [1, 384, 32, 32])
        self.assertEqual(shapes["gelu_output"]["shape"], [1, 384, 32, 32])
        self.assertEqual(shapes["fc2_output"]["shape"], [1, 128, 32, 32])
        lut = report["gelu_lut"]
        self.assertEqual(lut["bytes"], 131072)
        self.assertEqual(sha(STAGE3 / lut["path"]), lut["sha256"])
        for section in report["parameter_files"].values():
            if isinstance(section, dict):
                for value in section.values():
                    if isinstance(value, dict) and "path" in value and "sha256" in value:
                        self.assertEqual(sha(STAGE3 / value["path"]), value["sha256"])
        for filename, metadata in report["files"].items():
            self.assertEqual(sha(STAGE3 / filename), metadata["sha256"])
            self.assertEqual((STAGE3 / filename).stat().st_size, metadata["bytes"])

    def test_three_real_cases_preserve_full_rank_top1_and_allclose(self):
        report = json.loads((STAGE3 / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(len(report["results"]), 3)
        self.assertTrue(report["checks"]["three_real_32x32_inputs"])
        self.assertTrue(report["checks"]["stage3_pw_accumulations_computed_in_int64"])
        self.assertTrue(report["checks"]["bias_adds_checked_against_int32"])
        for item in report["results"]:
            similarity = item["text_similarity"]
            self.assertFalse(similarity["top1_changed"])
            self.assertTrue(similarity["full_rank_matches_pure_ps"])
            self.assertEqual(similarity["pure_ps_ranking"], similarity["int16_int8_stage3_ranking"])
            self.assertEqual(len(similarity["int16_int8_stage3_ranking"]), 8)
            metric = item["feature_metrics"]["quantized_stage3_final512_vs_pure_ps_feature"]
            self.assertFalse(metric["allclose_rtol_1e-4_atol_1e-5"])
            packet = item["files"]["stage3_output_packet"]
            self.assertEqual(packet["bytes"], 262144)
            self.assertEqual(sha(STAGE3 / packet["path"]), packet["sha256"])
            self.assertTrue(item["int64_and_int32_checks"]["add_int32_fits"])

    def test_stage3_actual_and_conservative_accumulator_bounds_fit_int32(self):
        report = json.loads((STAGE3 / "manifest.json").read_text(encoding="utf-8"))
        budget = report["int32_budget"]
        self.assertEqual(budget["stage3_fc2_pw384_to_128"][
            "all_int8_max_code_absolute_bound_before_bias"], 1597981056)
        for name in ("stage3_fc1_pw128_to_384", "stage3_fc2_pw384_to_128"):
            self.assertTrue(budget[name]["worst_case_fits_int32"])
        for operator in budget["actual_all_1024_pixels"].values():
            for record in operator:
                self.assertEqual(record["spatial_positions"], 1024)
                self.assertTrue(record["raw_accum_fits_int32"])
                self.assertTrue(record["accum_plus_bias_fits_int32"])


if __name__ == "__main__":
    unittest.main()
