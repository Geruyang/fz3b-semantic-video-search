import hashlib
import json
import os
import shutil
import tempfile
import unittest

import numpy as np

from desktop_vlm.board.stage6_transition_fixtures import (
    build_stage6_route_fixtures,
    build_reused_route_fixture_artifact,
    load_profile2_transition_fixtures,
)
from desktop_vlm.board.stage6_transition_offline import (
    build_stage6_pack,
    extract_n3_ps_se_gelu_subgraph,
    extract_transition,
    load_v5_boundary_scales,
    prepare_stage6_calibration,
)


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
HOST = os.path.join(ROOT, "artifacts", "board-debug-20261005", "acceleration", "host")
MODELS = os.path.join(HOST, "v5-runtime-models-001")
V5_MANIFEST = os.path.join(MODELS, "manifest.json")
BUNDLE_DIR = os.path.join(HOST, "network-w16-runtime-bundles-001")
BUNDLE_MANIFEST = os.path.join(BUNDLE_DIR, "manifest.json")
GOLDEN_DIR = os.path.join(HOST, "network-w16-same-board-golden-001")


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


class Stage6TransitionFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp(prefix="stage6-route-fixtures-test-")
        cls.pack_dir = os.path.join(cls.temp_dir, "pack")
        os.makedirs(cls.pack_dir)
        n1_path = os.path.join(MODELS, "network1-bridge.onnx")
        n3_path = os.path.join(MODELS, "network3-bridge.onnx")
        cls.n1 = extract_transition(n1_path, "N1")
        cls.n3 = extract_transition(n3_path, "N3")
        cls.boundaries = load_v5_boundary_scales(
            V5_MANIFEST, BUNDLE_MANIFEST, os.path.join(BUNDLE_DIR, "scale-manifest.json"))
        cls.calibration_path = os.path.join(cls.temp_dir, "calibration.json")
        calibration = prepare_stage6_calibration(
            n1_path, n3_path, GOLDEN_DIR, cls.boundaries, cls.calibration_path)
        cls.pack = build_stage6_pack(cls.n1, cls.n3, cls.boundaries, calibration)
        cls.pack_manifest_path = os.path.join(cls.pack_dir, "manifest.json")
        with open(cls.pack_manifest_path, "w") as stream:
            json.dump(cls.pack["manifest"], stream, indent=2, sort_keys=True)
            stream.write("\n")
        for profile in ("p3", "p4", "p5", "p6"):
            record = cls.pack["profiles"][profile]
            with open(os.path.join(cls.pack_dir, record["parameter_blob"]), "wb") as stream:
                stream.write(record["parameter_bytes"])
        cls.subgraph_path = os.path.join(cls.pack_dir, "network3-ps-se-gelu.onnx")
        extract_n3_ps_se_gelu_subgraph(n3_path, cls.subgraph_path)
        cls.output_dir = os.path.join(cls.temp_dir, "route")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.temp_dir)

    def test_profile2_checkpoints_use_canonical_input_and_fourth_add_output(self):
        scales_path = os.path.join(BUNDLE_DIR, "scale-manifest.json")
        result = load_profile2_transition_fixtures(
            GOLDEN_DIR, scales_path, expected_output_scale=8.370727368858105e-05)
        self.assertEqual(len(result["images"]), 3)
        self.assertEqual(result["profile_id"], "2")
        self.assertEqual(result["block_count"], 4)
        self.assertAlmostEqual(result["input_scale"], 0.00016495765799892816, places=15)
        self.assertAlmostEqual(result["output_scale"], 8.370727368858105e-05, places=18)
        with self.assertRaisesRegex(ValueError, "profile2 output scale"):
            load_profile2_transition_fixtures(
                GOLDEN_DIR, scales_path, expected_output_scale=1.0)
        for item in result["images"]:
            self.assertEqual(item["input_receipt"]["path"].split("/")[-1], "input-hcw.i16le")
            self.assertEqual(item["output_receipt"]["path"].split("/")[-1], "block-03-add-hcw.i16le")
            self.assertEqual(item["input_i16_chw"].shape, (64, 64, 64))
            self.assertEqual(item["output_i16_chw"].shape, (64, 64, 64))
            self.assertEqual(item["input_receipt"]["sha256"],
                             self._golden_file_sha(item["input_receipt"]["path"]))
            self.assertEqual(item["output_receipt"]["sha256"],
                             self._golden_file_sha(item["output_receipt"]["path"]))
            self.assertEqual(item["n1_dequant_check"]["reference_path"],
                             item["image_id"] + "/board/network1-bridge-input.f32")
            self.assertTrue(np.isfinite(item["n1_dequant_check"]["cosine"]))
            self.assertTrue(np.isfinite(item["n1_dequant_check"]["max_abs"]))
            self.assertEqual(item["n1_dequant_check"]["max_abs"], 0.0)
            self.assertEqual(item["n1_dequant_check"]["rms_abs"], 0.0)
            self.assertEqual(item["n1_dequant_check"]["dequantized_profile2_output_sha256"],
                             item["n1_dequant_check"]["reference_sha256"])

    def test_reuse_builder_corrects_p2_and_binds_unchanged_downstream(self):
        source_dir = os.path.join(HOST, "network-v6-route-fixtures-candidate-001")
        source_manifest = os.path.join(source_dir, "manifest.json")
        source_sha = sha256(source_manifest)
        output_dir = os.path.join(self.temp_dir, "network-v6-route-fixtures-candidate-002")
        result = build_reused_route_fixture_artifact(
            source_manifest, GOLDEN_DIR, os.path.join(BUNDLE_DIR, "scale-manifest.json"),
            output_dir, fixture_root=self.temp_dir)
        self.assertEqual(sha256(source_manifest), source_sha)
        manifest = result["manifest"]
        self.assertEqual(manifest["status"], "host_candidate_not_board_verified")
        self.assertEqual(manifest["candidate_status"], "candidate_failed_fallback_required")
        self.assertEqual(manifest["reused_artifact_provenance"]["source_manifest_sha256"], source_sha)
        with open(os.path.join(GOLDEN_DIR, "manifest.json"), "r", encoding="utf-8") as stream:
            golden_manifest = json.load(stream)
        for index, image in enumerate(manifest["images"]):
            image_id = "image-%02d" % index
            input_sha = golden_manifest["results"][index]["profile2_input_i16_hcw"]["sha256"]
            output_sha = golden_manifest["results"][index]["profile2_blocks"][3]["output"]["sha256"]
            self.assertEqual(image["fixtures"]["stem_p2_input"]["sha256"], input_sha)
            self.assertEqual(image["csim_intermediates"]["stem_p2_output"]["sha256"], output_sha)
            self.assertEqual(image["p2_profile2_checkpoint"]["n1_dequant_check"]["max_abs"], 0.0)
            self.assertEqual(image["source_inputs"]["p2_profile2_output_block03"]["sha256"], output_sha)
            old_p3_name = "route-%s-p3-output-hcw-i16le.bin" % image_id
            self.assertEqual(manifest["files"][old_p3_name]["sha256"],
                             result["source_manifest"]["files"][old_p3_name]["sha256"])

    def _golden_file_sha(self, relative_path):
        with open(os.path.join(GOLDEN_DIR, "manifest.json"), "r", encoding="utf-8") as stream:
            manifest = json.load(stream)
        return manifest["files"][relative_path.replace("\\", "/")]["sha256"]

    def test_three_image_host_route_fixtures_cover_real_v6_path_and_sha(self):
        result = build_stage6_route_fixtures(
            self.pack_manifest_path, self.pack_dir, BUNDLE_MANIFEST, GOLDEN_DIR,
            os.path.join(MODELS, "network1-bridge.onnx"),
            os.path.join(MODELS, "network3-bridge.onnx"), self.subgraph_path,
            self.output_dir)
        manifest = result["manifest"]
        self.assertEqual(manifest["status"], "host_candidate_not_board_verified")
        self.assertEqual(result["manifest_sha256"], sha256(os.path.join(self.output_dir, "manifest.json")))
        self.assertEqual(len(manifest["images"]), 3)
        self.assertEqual(manifest["quality_gate"]["cosine_threshold"], 0.99999)
        self.assertIn(manifest["candidate_status"],
                      ("candidate_passed_host_gate", "candidate_failed_fallback_required"))
        expected = {
            "stem_p2_input": ("stem-p2-input-hcw-i16le.bin", [64, 64, 64]),
            "p5_output": ("p5-output-hcw-i16le.bin", [256, 16, 16]),
            "se_gelu_p6_input": ("se-gelu-p6-input-hcw-i16le.bin", [256, 16, 16]),
            "p1_output": ("p1-output-hcw-i16le.bin", [256, 16, 16]),
        }
        for image in manifest["images"]:
            self.assertEqual(image["status"], "generated")
            self.assertTrue(image["p1_canonical_oracle_parity"]["checked"])
            self.assertEqual(image["p1_canonical_blocks"], 20)
            self.assertIn("max_abs", image["quality_metrics_vs_same_board"])
            self.assertIn("cosine", image["quality_metrics_vs_same_board"])
            self.assertIn("candidate_ranking", image["quality_metrics_vs_same_board"])
            self.assertIn("reference_ranking", image["quality_metrics_vs_same_board"])
            self.assertIn("quality_metrics_vs_pure_ps", image)
            self.assertIn("max_abs", image["quality_metrics_vs_pure_ps"])
            self.assertIn("cosine", image["quality_metrics_vs_pure_ps"])
            self.assertIn("candidate_ranking", image["quality_metrics_vs_pure_ps"])
            self.assertIn("reference_ranking", image["quality_metrics_vs_pure_ps"])
            for record_name, (suffix, shape) in expected.items():
                record = image["fixtures"][record_name]
                self.assertEqual(record["shape_chw"], shape)
                self.assertEqual(record["shape_hcw"], [shape[1], shape[0], shape[2]])
                self.assertEqual(record["layout"], "HCW")
                self.assertEqual(record["dtype"], "little_endian_signed_int16")
                self.assertEqual(record["header_bytes"], 0)
                self.assertEqual(record["bytes"], int(np.prod(shape)) * 2)
                path = os.path.join(self.output_dir, record["path"])
                self.assertTrue(path.endswith("route-image-%s-%s" % (image["image_id"][-2:], suffix)))
                self.assertEqual(record["sha256"], sha256(path))
            csim_expected = {
                "stem_p2_output": [64, 64, 64], "p3_output": [128, 32, 32],
                "p4_output": [128, 32, 32], "p0_output": [128, 32, 32],
                "p5_output": [256, 16, 16], "p6_output": [256, 16, 16],
                "p1_output": [256, 16, 16],
            }
            for name, shape in csim_expected.items():
                record = image["csim_intermediates"][name]
                self.assertEqual(record["shape_chw"], shape)
                self.assertEqual(record["shape_hcw"], [shape[1], shape[0], shape[2]])
                self.assertTrue(record["path"].startswith("route-image-%s-" % image["image_id"][-2:]))
                self.assertEqual(record["sha256"], sha256(os.path.join(self.output_dir, record["path"])))
                self.assertGreater(record["scale"], 0.0)
        self.assertEqual(manifest["execution"]["board_or_pl_execution"], False)
        self.assertIn("not board-verified", manifest["interpretation"])

    def test_refuses_existing_nonempty_output_directory_before_writing(self):
        occupied = os.path.join(self.temp_dir, "occupied")
        os.makedirs(occupied)
        marker = os.path.join(occupied, "keep.txt")
        with open(marker, "w") as stream:
            stream.write("preserve")
        with self.assertRaisesRegex(ValueError, "nonempty output directory"):
            build_stage6_route_fixtures(
                self.pack_manifest_path, self.pack_dir, BUNDLE_MANIFEST, GOLDEN_DIR,
                os.path.join(MODELS, "network1-bridge.onnx"),
                os.path.join(MODELS, "network3-bridge.onnx"), self.subgraph_path,
                occupied)
        with open(marker, "r") as stream:
            self.assertEqual(stream.read(), "preserve")

    def test_rejects_output_path_escape_and_pinned_input_hash_mismatch(self):
        outside = os.path.join(self.temp_dir, "..", "escaped")
        with self.assertRaisesRegex(ValueError, "output path escapes fixture root"):
            build_stage6_route_fixtures(
                self.pack_manifest_path, self.pack_dir, BUNDLE_MANIFEST, GOLDEN_DIR,
                os.path.join(MODELS, "network1-bridge.onnx"),
                os.path.join(MODELS, "network3-bridge.onnx"), self.subgraph_path,
                outside, fixture_root=self.temp_dir)
        bad_manifest = os.path.join(self.temp_dir, "bad-pack.json")
        changed = dict(self.pack["manifest"])
        changed["profiles"] = dict(changed["profiles"])
        changed["profiles"]["p3"] = dict(changed["profiles"]["p3"])
        changed["profiles"]["p3"]["parameter_sha256"] = "0" * 64
        with open(bad_manifest, "w") as stream:
            json.dump(changed, stream)
        with self.assertRaisesRegex(ValueError, "parameter blob SHA256 mismatch"):
            build_stage6_route_fixtures(
                bad_manifest, self.pack_dir, BUNDLE_MANIFEST, GOLDEN_DIR,
                os.path.join(MODELS, "network1-bridge.onnx"),
                os.path.join(MODELS, "network3-bridge.onnx"), self.subgraph_path,
                os.path.join(self.temp_dir, "bad-output"))


if __name__ == "__main__":
    unittest.main()
