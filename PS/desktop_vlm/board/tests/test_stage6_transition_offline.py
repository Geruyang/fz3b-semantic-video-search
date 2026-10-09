import hashlib
import json
import os
import tempfile
import unittest

import numpy as np

from desktop_vlm.board.stage6_transition_offline import (
    build_stage6_pack,
    extract_transition,
    extract_n3_ps_se_gelu_subgraph,
    integer_oracle,
    integer_oracle_n3_integer_se_experimental,
    load_v5_boundary_scales,
    main as stage6_main,
    prepare_stage6_calibration,
    quantize_weight_w16,
    checked_accumulator,
)


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
HOST = os.path.join(ROOT, "artifacts", "board-debug-20261005", "acceleration", "host")
MODELS = os.path.join(HOST, "v5-runtime-models-001")
V5_MANIFEST = os.path.join(MODELS, "manifest.json")
BUNDLE_DIR = os.path.join(HOST, "network-w16-runtime-bundles-001")
BUNDLE_MANIFEST = os.path.join(BUNDLE_DIR, "manifest.json")
SCALE_MANIFEST = os.path.join(BUNDLE_DIR, "scale-manifest.json")
GOLDEN_DIR = os.path.join(HOST, "network-w16-same-board-golden-001")


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def calibration_for(boundaries, source_path):
    n1 = boundaries["stages"]["N1"]
    n3 = boundaries["stages"]["N3"]
    return {
        "case_count": 3,
        "case_ids": ["image-00", "image-01", "image-02"],
        "source_manifest_path": source_path,
        "source_manifest_sha256": sha256(source_path),
        "scales": {
            "p3_input": n1["input"], "p3_dw_output": 0.01, "p3_gelu_output": 0.01,
            "p4_pw_output": 0.01, "p4_output": n1["output"],
            "p5_input": n3["input"], "p5_output": 0.01,
            "ps_se_fc1_output": 0.01, "ps_se_fc2_output": 0.01,
            "ps_se_gate": 1.0 / 32767.0, "ps_se_gelu_output": 0.01,
            "p6_pw_output": 0.01, "p6_output": n3["output"],
        },
    }


class Stage6TransitionOfflineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.n1 = extract_transition(os.path.join(MODELS, "network1-bridge.onnx"), "N1")
        cls.n3 = extract_transition(os.path.join(MODELS, "network3-bridge.onnx"), "N3")
        cls.boundaries = load_v5_boundary_scales(V5_MANIFEST, BUNDLE_MANIFEST, SCALE_MANIFEST)
        handle, cls.calibration_path = tempfile.mkstemp(prefix="stage6-calibration-", suffix=".json")
        os.close(handle)
        cls.calibration = calibration_for(cls.boundaries, cls.calibration_path)
        fixture = {"case_count": 3, "case_ids": cls.calibration["case_ids"],
                   "scales": cls.calibration["scales"],
                   "note": "synthetic test scales; not real image calibration evidence"}
        with open(cls.calibration_path, "w") as stream:
            json.dump(fixture, stream, sort_keys=True)
        cls.calibration["source_manifest_sha256"] = sha256(cls.calibration_path)
        cls.pack = build_stage6_pack(cls.n1, cls.n3, cls.boundaries, cls.calibration)

    @classmethod
    def tearDownClass(cls):
        if os.path.isfile(cls.calibration_path):
            os.remove(cls.calibration_path)

    def test_real_onnx_sequences_and_shapes_are_split_at_frozen_boundaries(self):
        self.assertEqual([step["kind"] for step in self.n1["sequence"]],
                         ["depthwise_conv", "gelu", "pointwise_conv", "gelu"])
        self.assertEqual([step["kind"] for step in self.n3["sequence"]],
                         ["depthwise_conv", "se_reduce_mean", "se_fc1", "relu", "se_fc2",
                          "sigmoid", "se_gate_mul", "gelu", "pointwise_conv", "gelu"])
        self.assertEqual(self.n1["input"]["shape"], [1, 64, 64, 64])
        self.assertEqual(self.n1["output"]["shape"], [1, 128, 32, 32])
        self.assertEqual(self.n3["input"]["shape"], [1, 128, 32, 32])
        self.assertEqual(self.n3["output"]["shape"], [1, 256, 16, 16])
        self.assertEqual(self.n3["sequence"][0]["weight_shape"], [256, 1, 7, 7])
        self.assertEqual(self.n3["sequence"][2]["weight_shape"], [64, 256, 1, 1])
        self.assertEqual(self.n3["sequence"][4]["weight_shape"], [256, 64, 1, 1])
        self.assertEqual(self.n1["sequence"][0]["attributes"]["group"], 64)
        self.assertEqual(self.n3["sequence"][0]["attributes"]["group"], 128)
        self.assertEqual(self.n1["sequence"][0]["weight_shape"], [128, 1, 7, 7])

    def test_four_frozen_profiles_have_exact_jobs_slots_and_strides(self):
        profiles = self.pack["profiles"]
        self.assertEqual(list(profiles), ["p3", "p4", "p5", "p6"])
        expected = {
            "p3": ("N1", [1, 64, 64, 64], [1, 128, 32, 32], 16384, 22433, ["DW7", "GELU"]),
            "p4": ("N1", [1, 128, 32, 32], [1, 128, 32, 32], 16384, 22433, ["PW1", "GELU"]),
            "p5": ("N3", [1, 128, 32, 32], [1, 256, 16, 16], 8192, 61057, ["DW7"]),
            "p6": ("N3", [1, 256, 16, 16], [1, 256, 16, 16], 8192, 61057, ["PW1", "GELU"]),
        }
        for name, values in expected.items():
            record = profiles[name]
            self.assertEqual((record["source_transition"], record["input_shape"], record["output_shape"],
                              record["slot_words"], record["block_stride_words"], record["operators"]), values)
            self.assertEqual(record["block_count"], 1)
            self.assertEqual(record["slot_index"], 1)
            if "DW7" in record["operators"]:
                self.assertEqual(record["dw_line_buffer_pixels"], 4096)
            self.assertEqual(record["activation_dtype"], "little_endian_signed_int16_HCW")
            self.assertEqual(record["weight_dtype"], "little_endian_signed_int16")
            self.assertEqual(record["accumulator_bits"], 48)
            self.assertEqual(len(record["parameter_bytes"]), record["block_stride_words"] * 16)
            self.assertEqual(record["parameter_sha256"], hashlib.sha256(record["parameter_bytes"]).hexdigest())
        expected_blobs = {
            "p3": "profile-3-network1-dw7-gelu-params-w16.bin",
            "p4": "profile-4-network1-pw1-gelu-params-w16.bin",
            "p5": "profile-5-network3-dw7-params-w16.bin",
            "p6": "profile-6-network3-pw1-gelu-params-w16.bin",
        }
        for profile, filename in expected_blobs.items():
            self.assertEqual(self.pack["profiles"][profile]["parameter_blob"], filename)
            self.assertEqual(self.pack["manifest"]["profiles"][profile]["parameter_blob"], filename)
            self.assertEqual(len(profiles[profile]["parameter_bytes"]) % 16, 0)

    def test_unused_sections_are_zero_and_real_n1_weights_are_quantized(self):
        p3 = self.pack["profiles"]["p3"]
        p4 = self.pack["profiles"]["p4"]
        p5 = self.pack["profiles"]["p5"]
        p6 = self.pack["profiles"]["p6"]
        for record in (p3, p4, p5, p6):
            self.assertEqual(record["unused_sections_zero"], ["dw3", "unused_coefficients", "pw2"])
            self.assertEqual(record["parameter_layout"]["pw1_active_outputs"], record["channels"] if "PW1" in record["operators"] else 0)
        self.assertGreater(int(np.max(np.abs(p3["arrays"]["dw7_weights_i16"]))), 0)
        self.assertGreater(int(np.max(np.abs(p4["arrays"]["pw1_tiles_i16"]))), 0)
        for record in (p3, p4, p5, p6):
            self.assertEqual(np.unique(record["weight_scales"]).size, 1)
        expected_dw, unused = quantize_weight_w16(
            self.n1["parameters"][self.n1["sequence"][0]["weight_name"]], per_channel=False)
        np.testing.assert_array_equal(p3["arrays"]["dw7_weights_i16"], expected_dw.reshape((128, 49)))
        expected_pw, unused = quantize_weight_w16(
            self.n1["parameters"][self.n1["sequence"][2]["weight_name"]][:, :, 0, 0], per_channel=False)
        np.testing.assert_array_equal(p4["arrays"]["pw1_tiles_i16"][:128], expected_pw)
        self.assertEqual(int(np.count_nonzero(p5["arrays"]["gelu_lut_i16"])), 0)
        self.assertEqual(int(np.count_nonzero(p3["arrays"]["pw2_tiles_i16"])), 0)
        self.assertNotIn("ps_se_parameters", self.pack["manifest"])
        self.assertEqual(self.pack["experimental_integer_se"]["fc1"]["weight_i16"].shape, (64, 256))
        self.assertEqual(self.pack["experimental_integer_se"]["fc2"]["weight_i16"].shape, (256, 64))

    def test_ddr_intermediate_contract_keeps_n1_on_pl_and_n3_se_on_ps(self):
        transfers = self.pack["intermediate_ddr"]
        self.assertEqual(transfers["n1_p3_to_p4"]["shape"], [1, 128, 32, 32])
        self.assertEqual(transfers["n1_p3_to_p4"]["dtype"], "int16")
        self.assertFalse(transfers["n1_p3_to_p4"]["ps_roundtrip"])
        self.assertEqual(transfers["n1_p3_to_p4"]["consumer"], "p4")
        self.assertEqual(transfers["n3_p5_to_ps_se"]["shape"], [1, 256, 16, 16])
        self.assertEqual(transfers["n3_ps_se_to_p6"]["shape"], [1, 256, 16, 16])
        self.assertEqual(transfers["n3_path"], ["p5:DW7", "PS:SE+GELU", "p6:PW1+GELU"])
        self.assertIn("original N3 ONNX FP32 SE+GELU callback output",
                      transfers["n3_ps_se_to_p6"]["provenance"])

    def test_manifest_deterministic_sha_bound_and_requires_three_case_scale_input(self):
        self.assertEqual(self.pack["status"], "candidate_not_accuracy_claim")
        self.assertEqual(self.pack["quantization"]["weight_dtype"], "int16")
        self.assertEqual(self.pack["quantization"]["activation_dtype"], "int16")
        self.assertEqual(self.pack["quantization"]["accumulator_bits"], 48)
        self.assertEqual(self.pack["quantization"]["q31_rounding"], "ties_to_even")
        self.assertEqual(self.pack["calibration"]["case_count"], 3)
        self.assertEqual(self.pack["v5_manifest_sha256"], sha256(V5_MANIFEST))
        self.assertEqual(self.pack["scale_manifest_sha256"], sha256(SCALE_MANIFEST))
        self.assertEqual(self.pack["manifest_sha256"], self.pack["manifest_sha256_recomputed"])
        payload = json.dumps(self.pack["manifest"], sort_keys=True, separators=(",", ":"),
                             ensure_ascii=True).encode("utf-8")
        self.assertEqual(self.pack["manifest_sha256"], hashlib.sha256(payload).hexdigest())
        self.assertEqual(self.pack["manifest_sha256"], build_stage6_pack(
            self.n1, self.n3, self.boundaries, self.calibration)["manifest_sha256"])
        manifest = self.pack["manifest"]
        self.assertEqual(manifest["parameter_container"], {
            "header": "none", "word_bits": 128, "word_byte_order": "little_endian"})
        self.assertEqual(manifest["canonical_profile_aliases"]["0"]["parameter_blob"],
                         "profile-0-network2-params-w16.bin")
        self.assertEqual(manifest["canonical_profile_aliases"]["1"]["parameter_blob"],
                         "profile-1-network4-params-w16.bin")
        self.assertEqual(manifest["canonical_profile_aliases"]["2"]["parameter_blob"],
                         "profile-2-network0-params-w16.bin")
        self.assertEqual(manifest["canonical_profile_aliases"]["0"]["included_in_this_pack"], False)
        expected_aliases = {"0": "params-profile0.bin", "1": "params-profile1.bin",
                            "2": "params-profile2.bin"}
        for profile_id, canonical_name in expected_aliases.items():
            alias = manifest["canonical_profile_aliases"][profile_id]
            canonical_path = os.path.join(BUNDLE_DIR, canonical_name)
            self.assertEqual(alias["canonical_path"], canonical_name)
            self.assertEqual(alias["sha256"], sha256(canonical_path))
            self.assertEqual(alias["bytes"], os.path.getsize(canonical_path))
        self.assertEqual(manifest["profiles"]["p3"]["block_stride_words"], 22433)
        self.assertEqual(manifest["profiles"]["p5"]["block_stride_words"], 61057)
        self.assertEqual(manifest["profiles"]["p3"]["parameter_bytes"], 22433 * 16)
        self.assertEqual(manifest["profiles"]["p5"]["parameter_bytes"], 61057 * 16)
        self.assertEqual(manifest["quantization"]["weight_scale_mode"],
                         "per_tensor_symmetric_maxabs")
        self.assertEqual(manifest["deployment_graph"]["n3_ps_boundary"],
                         "PS_ONNX_RUNTIME_FP32_SE_GELU_CALLBACK_REQUIRED")
        self.assertEqual(manifest["deployment_graph"]["ps_boundary_provenance"],
                         "original_N3_ONNX_full_SE_order_not_integer_SE_candidate")
        self.assertEqual(manifest["intermediate_ddr"]["n1_p3_to_p4"]["buffer_layout"], "HCW")
        self.assertEqual(manifest["intermediate_ddr"]["n3_p5_to_ps_se"]["buffer_layout"], "HCW")
        checkpoints = manifest["activation_checkpoints"]
        expected_checkpoints = {
            "stem-p2-input": ([64, 64, 64], 64 * 64 * 64 * 2),
            "p5-output": ([256, 16, 16], 256 * 16 * 16 * 2),
            "se-gelu-p6-input": ([256, 16, 16], 256 * 16 * 16 * 2),
            "p1-output": ([256, 16, 16], 256 * 16 * 16 * 2),
        }
        for checkpoint, (shape, byte_count) in expected_checkpoints.items():
            record = checkpoints[checkpoint]
            self.assertEqual(record["shape_hcw"], shape)
            self.assertEqual(record["bytes"], byte_count)
            self.assertEqual(record["dtype"], "little_endian_signed_int16")
            self.assertEqual(record["header_bytes"], 0)
            self.assertTrue(record["fixture_data_pending"])
        bad = dict(self.calibration, case_count=2)
        with self.assertRaises(ValueError):
            build_stage6_pack(self.n1, self.n3, self.boundaries, bad)
        bad_sha = dict(self.calibration, source_manifest_sha256="0" * 64)
        with self.assertRaises(ValueError):
            build_stage6_pack(self.n1, self.n3, self.boundaries, bad_sha)

    def test_w16_quantizer_and_signed48_guard(self):
        values = np.array([[0.5, 1.5, 40000.0], [-0.5, -1.5, -40000.0]])
        q, scales = quantize_weight_w16(values, axis=0, scale=np.array([1.0, 1.0]))
        self.assertEqual(q.dtype, np.dtype("<i2"))
        np.testing.assert_array_equal(q[:, :2], np.array([[0, 2], [0, -2]], dtype="<i2"))
        self.assertLessEqual(int(np.max(np.abs(q.astype(np.int32)))), 32767)
        self.assertEqual(scales.shape, (2,))
        self.assertEqual(checked_accumulator(2 ** 47 - 1), 2 ** 47 - 1)
        self.assertEqual(checked_accumulator(-(2 ** 47)), -(2 ** 47))
        with self.assertRaises(OverflowError):
            checked_accumulator(2 ** 47)

    def test_real_weight_integer_oracle_obeys_n1_and_n3_ps_pl_flow(self):
        n1_input = np.zeros(self.n1["input"]["shape"], dtype="<i2")
        n1 = integer_oracle("N1", n1_input, self.n1, self.n3, self.pack)
        self.assertEqual(n1["output"].shape, tuple(self.n1["output"]["shape"]))
        self.assertEqual(n1["output"].dtype, np.dtype("<i2"))
        self.assertFalse(n1["ps_roundtrip_between_jobs"])
        n3_input = np.zeros(self.n3["input"]["shape"], dtype="<i2")
        with self.assertRaisesRegex(ValueError, "FP32 PS SE/GELU callback"):
            integer_oracle("N3", n3_input, self.n1, self.n3, self.pack)
        n3 = integer_oracle("N3", n3_input, self.n1, self.n3, self.pack,
                            n3_ps_se_gelu_callback=lambda value: np.zeros_like(value, dtype=np.float32))
        self.assertEqual(n3["output"].shape, tuple(self.n3["output"]["shape"]))
        self.assertEqual(n3["output"].dtype, np.dtype("<i2"))
        self.assertTrue(n3["ps_roundtrip_between_jobs"])
        self.assertEqual(n3["ps_se_gelu_input_i16"].shape, (1, 256, 16, 16))
        experimental = integer_oracle_n3_integer_se_experimental(
            n3_input, self.n3, self.pack)
        self.assertEqual(experimental["output"].shape, tuple(self.n3["output"]["shape"]))
        self.assertEqual(experimental["status"], "experimental_not_frozen_target")

    def test_same_board_three_case_fp32_ranges_are_sha_bound_and_deterministic(self):
        n1_path = os.path.join(MODELS, "network1-bridge.onnx")
        n3_path = os.path.join(MODELS, "network3-bridge.onnx")
        paths = []
        calibrations = []
        try:
            for unused in range(2):
                handle, path = tempfile.mkstemp(prefix="stage6-real-calibration-", suffix=".json")
                os.close(handle)
                paths.append(path)
                calibrations.append(prepare_stage6_calibration(
                    n1_path, n3_path, GOLDEN_DIR, self.boundaries, path))
            with open(paths[0], "rb") as stream:
                first_bytes = stream.read()
            with open(paths[1], "rb") as stream:
                self.assertEqual(stream.read(), first_bytes)
            manifest = calibrations[0]["manifest"]
            self.assertEqual(manifest["status"], "host_calibrated_candidate_accuracy_unverified")
            self.assertEqual(manifest["provenance"]["golden_manifest_sha256"],
                             sha256(os.path.join(GOLDEN_DIR, "manifest.json")))
            self.assertFalse(manifest["provenance"]["synthetic"])
            self.assertEqual(len(manifest["cases"]), 3)
            for index, case in enumerate(manifest["cases"]):
                case_id = "image-%02d" % index
                self.assertEqual(case["case_id"], case_id)
                for stage in ("N1", "N3"):
                    record = case["inputs"][stage]
                    actual_path = os.path.join(GOLDEN_DIR, *record["path"].split("/"))
                    self.assertEqual(record["sha256"], sha256(actual_path))
                    self.assertEqual(record["bytes"], os.path.getsize(actual_path))
                    receipt_path = os.path.join(GOLDEN_DIR, *record["receipt_path"].split("/"))
                    self.assertEqual(record["receipt_sha256"], sha256(receipt_path))
                    self.assertEqual(record["receipt_ort_version"], "1.16.3")
                    self.assertTrue(record["board_capture"])
                    self.assertFalse(record["pl_execution"])
                for key in ("p3_dw_output", "p3_gelu_output", "p4_pw_output", "p5_output",
                            "ps_se_fc1_output", "ps_se_fc2_output", "ps_se_gate",
                            "ps_se_gelu_output", "p6_pw_output"):
                    self.assertTrue(np.isfinite(case["internal_scales"][key]))
                    self.assertGreater(case["internal_scales"][key], 0.0)
                    measured = case["internal_ranges"][key]["abs_max"] / 32767.0
                    self.assertEqual(case["internal_scales"][key], measured)
            self.assertEqual(calibrations[0]["scales"], calibrations[1]["scales"])
            for key in ("p3_dw_output", "p3_gelu_output", "p4_pw_output", "p5_output",
                        "ps_se_fc1_output", "ps_se_fc2_output", "ps_se_gate",
                        "ps_se_gelu_output", "p6_pw_output"):
                maximum = max(case["internal_ranges"][key]["abs_max"]
                              for case in manifest["cases"])
                self.assertEqual(calibrations[0]["scales"][key], maximum / 32767.0)
            packed = build_stage6_pack(self.n1, self.n3, self.boundaries, calibrations[0])
            self.assertEqual(packed["manifest"]["calibration"]["status"],
                             "host_calibrated_candidate_accuracy_unverified")
            self.assertEqual(packed["manifest"]["calibration"]["golden_manifest_sha256"],
                             manifest["provenance"]["golden_manifest_sha256"])
            for key in ("p3_input", "p4_output", "p5_input", "p6_output"):
                self.assertEqual(calibrations[0]["scales"][key], self.pack["calibration"]["scales"][key])
        finally:
            for path in paths:
                if os.path.isfile(path):
                    os.remove(path)

    def test_n3_ps_se_gelu_subgraph_preserves_original_onnx_order(self):
        model = extract_n3_ps_se_gelu_subgraph(os.path.join(MODELS, "network3-bridge.onnx"))
        names = [node.name for node in model.graph.node]
        expected = ["/image_encoder/model/network.3/proj/proj.0/se/ReduceMean",
                    "/image_encoder/model/network.3/proj/proj.0/se/fc1/Conv",
                    "/image_encoder/model/network.3/proj/proj.0/se/act/Relu",
                    "/image_encoder/model/network.3/proj/proj.0/se/fc2/Conv",
                    "/image_encoder/model/network.3/proj/proj.0/se/gate/Sigmoid",
                    "/image_encoder/model/network.3/proj/proj.0/se/Mul",
                    "/image_encoder/model/network.3/proj/proj.0/activation/Constant",
                    "/image_encoder/model/network.3/proj/proj.0/activation/Div",
                    "/image_encoder/model/network.3/proj/proj.0/activation/Erf",
                    "/image_encoder/model/network.3/proj/proj.0/activation/Constant_1",
                    "/image_encoder/model/network.3/proj/proj.0/activation/Add",
                    "/image_encoder/model/network.3/proj/proj.0/activation/Mul",
                    "/image_encoder/model/network.3/proj/proj.0/activation/Constant_2",
                    "/image_encoder/model/network.3/proj/proj.0/activation/Mul_1"]
        self.assertEqual(names, expected)
        self.assertEqual(len(model.graph.input), 1)
        self.assertEqual(len(model.graph.output), 1)
        self.assertEqual(model.graph.input[0].type.tensor_type.shape.dim[1].dim_value, 256)
        import onnx
        from onnx.reference import ReferenceEvaluator
        n3_path = os.path.join(MODELS, "network3-bridge.onnx")
        case_input = os.path.join(GOLDEN_DIR, "image-00", "board", "network3-bridge-input.f32")
        n3_input = np.fromfile(case_input, dtype="<f4").reshape((1, 128, 32, 32))
        names = [self.n3["sequence"][0]["outputs"][0], self.n3["sequence"][7]["outputs"][0]]
        full_outputs = ReferenceEvaluator(onnx.load(n3_path)).run(
            names, {self.n3["input"]["name"]: n3_input})
        subgraph_output = ReferenceEvaluator(model).run(
            [model.graph.output[0].name], {model.graph.input[0].name: full_outputs[0]})[0]
        np.testing.assert_array_equal(subgraph_output, full_outputs[1])

    def test_default_cli_output_has_profile_blobs_and_fp32_ps_subgraph_only(self):
        output_dir = tempfile.mkdtemp(prefix="stage6-cli-output-")
        try:
            stage6_main([
                os.path.join(MODELS, "network1-bridge.onnx"),
                os.path.join(MODELS, "network3-bridge.onnx"),
                "--v5-manifest", V5_MANIFEST,
                "--bundle-manifest", BUNDLE_MANIFEST,
                "--scale-manifest", SCALE_MANIFEST,
                "--calibration", self.calibration_path,
                "--output-dir", output_dir,
            ])
            manifest_path = os.path.join(output_dir, "manifest.json")
            with open(manifest_path, "r") as stream:
                manifest = json.load(stream)
            for profile in ("p3", "p4", "p5", "p6"):
                record = manifest["profiles"][profile]
                blob = os.path.join(output_dir, record["parameter_blob"])
                self.assertTrue(os.path.isfile(blob))
                self.assertEqual(sha256(blob), record["parameter_sha256"])
            subgraph = os.path.join(output_dir, "network3-ps-se-gelu.onnx")
            self.assertTrue(os.path.isfile(subgraph))
            self.assertEqual(sha256(subgraph), manifest["deployment_graph"]["ps_subgraph_sha256"])
            self.assertFalse(any(name.startswith("ps-se-") for name in os.listdir(output_dir)))
        finally:
            import shutil
            shutil.rmtree(output_dir)

    def test_cli_resolves_relative_calibration_path_without_duplicate_parent(self):
        import shutil
        work_dir = tempfile.mkdtemp(prefix="stage6-relative-cli-", dir=ROOT)
        output_dir = os.path.join(work_dir, "output")
        relative_calibration = os.path.relpath(
            os.path.join(work_dir, "calibration.json"), ROOT)
        try:
            shutil.copyfile(self.calibration_path,
                            os.path.join(work_dir, "calibration.json"))
            stage6_main([
                os.path.join(MODELS, "network1-bridge.onnx"),
                os.path.join(MODELS, "network3-bridge.onnx"),
                "--v5-manifest", V5_MANIFEST,
                "--bundle-manifest", BUNDLE_MANIFEST,
                "--scale-manifest", SCALE_MANIFEST,
                "--calibration", relative_calibration,
                "--output-dir", output_dir,
            ])
            self.assertTrue(os.path.isfile(os.path.join(output_dir, "manifest.json")))
        finally:
            shutil.rmtree(work_dir)


if __name__ == "__main__":
    unittest.main()
