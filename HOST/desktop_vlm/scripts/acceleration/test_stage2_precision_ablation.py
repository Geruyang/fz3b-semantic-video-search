"""Integrity checks for A/B board-pinned stage2 precision ablations."""
import hashlib
import json
import os
from pathlib import Path
import unittest
from argparse import Namespace

import numpy as np


ROOT = Path(__file__).resolve().parents[3]
A_DIR = Path(os.environ.get(
    "STAGE2_INT32_ABLATION_DIR",
    ROOT / "artifacts/board-debug-20261004/acceleration/host/stage2-dw3-dw7-int32acc-003"))
B_DIR = Path(os.environ.get(
    "STAGE2_INT16_ABLATION_DIR",
    ROOT / "artifacts/board-debug-20261004/acceleration/host/stage2-dw3-dw7-int16act-007"))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class Stage2PrecisionAblationTests(unittest.TestCase):
    def test_a_packet_is_single_1mib_s2mm_payload_with_only_final_tlast(self):
        report = json.loads((A_DIR / "manifest.json").read_text(encoding="utf-8"))
        contract = report["A_accumulator_dual_output_contract"]
        self.assertEqual(contract["packet_count"], 1)
        self.assertEqual(contract["total_bytes"], 1048576)
        self.assertIn("only at final packet byte", contract["TLAST"])
        self.assertIn("one TLAST only", contract["TLAST"])
        for sample in report["results"]:
            packet = sample["packet"]
            path = A_DIR / packet["path"]
            self.assertEqual(path.stat().st_size, 1048576)
            self.assertEqual(sha(path), packet["sha256"])
            self.assertEqual(packet["segments"][0]["offset_bytes"], 0)
            self.assertEqual(packet["segments"][1]["offset_bytes"], 524288)
            self.assertTrue(all(item["accumulator_contains_bias"]
                                for item in packet["segments"]))

    def test_a_records_quantization_isolation_and_unresolved_top1(self):
        report = json.loads((A_DIR / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(set(report["summary"]), {
            "A_both_i32", "A_only_q7_int8", "A_only_q3_residual_int8", "A_both_int8"})
        self.assertTrue(report["checks"]["host_dw7_allclose_failures_preserved"])
        self.assertTrue(report["summary"]["A_both_i32"][0]["top1_changed"])

    def test_b_has_exact_8way_rank_and_top1_on_all_real_cases(self):
        report = json.loads((B_DIR / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(report["status"], "STAGE2_B_INT16_ACTIVATION_INT8_WEIGHT_CPU_ABLATION_NOT_PL")
        self.assertEqual(len(report["results"]), 3)
        self.assertFalse(report["pl_execution"])
        for sample in report["results"]:
            self.assertFalse(sample["top1_changed"])
            self.assertEqual(sample["board_ps_ranking"], sample["b_ranking"])
            self.assertEqual(len(sample["b_ranking"]), 8)
            self.assertGreater(sample["feature_vs_pure_ps"]["cosine"], 0.9999)
            self.assertEqual(sample["files"]["dual_accumulator_packet"]["total_bytes"], 1048576)
            packet = B_DIR / sample["files"]["dual_accumulator_packet"]["path"]
            self.assertEqual(packet.stat().st_size, 1048576)
            self.assertEqual(sha(packet), sample["files"]["dual_accumulator_packet"]["sha256"])
        self.assertEqual(report["activation_quantization"]["zero_point"], 0)
        self.assertEqual(report["activation_quantization"]["clip"], [-32767, 32767])

    def test_int32_candidate_budgets_cover_stage2_and_stage3_full_shapes(self):
        report = json.loads((B_DIR / "manifest.json").read_text(encoding="utf-8"))
        budget = report["int32_budget"]
        self.assertLessEqual(budget["dw7_depthwise_k49"][
            "worst_case_abs_accumulator_including_bias"], np.iinfo(np.int32).max)
        self.assertLessEqual(budget["stage3_pw384_to_128"][
            "worst_case_abs_accumulator_including_bias"], np.iinfo(np.int32).max)
        self.assertEqual(budget["stage3_pw384_to_128"]["reduction_length"], 384)
        self.assertEqual(len(report["stage3_int16_activation_int8_weight_recommendation"][
            "full_32x32_real_activation_accumulator_checks"]["fc2_pw384_to_128"]), 3)
        self.assertTrue(all(item["raw_accum_fits_int32"] and item["bias_added_fits_int32"]
                            for operator in report["stage3_int16_activation_int8_weight_recommendation"][
                                "full_32x32_real_activation_accumulator_checks"].values()
                            for item in operator))
        self.assertIn("1597981056", budget["reference_ceiling"])

    def test_b_direct_stage2_parameters_are_independently_recomputed(self):
        from verify_stage2_int16_parameters import verify
        result = verify(Namespace(stage2_b=str(B_DIR), model=str(
            ROOT / "artifacts/board-debug-20261004/host/s1-onnx-001/mobileclip_s1_image.onnx")))
        self.assertEqual(result["status"], "PASS_INDEPENDENT_B_DW_BIAS_WEIGHT_Q31_RECOMPUTE")
        report = json.loads((B_DIR / "manifest.json").read_text(encoding="utf-8"))
        self.assertIn("stage2_jtag_parameters", report)
        for layer in ("dw3", "dw7"):
            params = report["stage2_jtag_parameters"][layer]
            self.assertEqual(params["bias_i32_file"]["shape"], [128])
            self.assertEqual(params["weight_scale_file"]["shape"], [128])
            self.assertEqual(params["accumulator_scale_file"]["shape"], [128])
            self.assertTrue(params["requant_to_dw7" if layer == "dw3" else
                                 "requant_to_stage3"]["rounding"].endswith("clip [-32767,32767]"))


if __name__ == "__main__":
    unittest.main()
