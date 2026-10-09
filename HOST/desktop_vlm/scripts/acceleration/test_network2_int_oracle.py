"""Unit tests for the generic network.2 INT16/INT8 host oracle."""
import importlib.util
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np


HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))


def load_module(filename, name):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


builder = load_module("build_network2_int_oracle.py", "network2_int_oracle_builder")
checker = load_module("check_network2_int_oracle.py", "network2_int_oracle_checker")


class IntegerOraclePrimitiveTests(unittest.TestCase):
    def test_checker_has_independent_rounding_and_accumulation_primitives(self):
        np.testing.assert_array_equal(
            checker._round_shift_even_independent(np.array([-3, -1, 1, 3], dtype=np.int64), 1),
            np.array([-2, 0, 0, 2], dtype=np.int64))
        x = np.array([[[2, 4]], [[-1, 3]]], dtype=np.int16)
        w = np.array([[2, 1], [-1, 2]], dtype=np.int8)
        np.testing.assert_array_equal(checker._pointwise_independent(x, w),
                                      np.array([[[3, 11]], [[-4, 2]]], dtype=np.int64))
        with self.assertRaises(OverflowError):
            checker._checked_bias_independent(np.array([[[2**31]]], dtype=np.int64),
                                              np.array([0], dtype=np.int32))

    def test_checker_rank_flags_use_positive_full_rank_match_semantics(self):
        same = ["bottle", "pliers", "cup"]
        checker._validate_rank_flags(same, same, {
            "quantized_ranking": same, "reference_ranking": same,
            "quantized_top1": "bottle", "reference_top1": "bottle",
            "full_rank_matches": True, "top1_changed": False})
        with self.assertRaises(ValueError):
            checker._validate_rank_flags(same, same, {
                "quantized_ranking": same, "reference_ranking": same,
                "quantized_top1": "bottle", "reference_top1": "bottle",
                "full_rank_matches": False, "top1_changed": False})

    def test_symmetric_int16_quantization_uses_ties_even_and_symmetric_clip(self):
        q = builder.quantize_symmetric(np.array([-4.5, -3.5, -0.5, 0.5, 3.5, 4.5]), 1.0, 16)
        np.testing.assert_array_equal(q, np.array([-4, -4, 0, 0, 4, 4], dtype=np.int16))
        self.assertEqual(int(builder.quantize_symmetric(np.array([40000.0]), 1.0, 16)[0]), 32767)

    def test_bias_quantization_checks_int32_and_ties_even(self):
        np.testing.assert_array_equal(builder.quantize_bias_i32(np.array([0.5, 1.5, -1.5]), 1.0),
                                      np.array([0, 2, -2], dtype=np.int32))
        with self.assertRaises(OverflowError):
            builder.quantize_bias_i32(np.array([3.0e9]), 1.0)

    def test_accumulator_is_int64_oracle_and_bias_included_output_is_checked_i32(self):
        raw = np.array([[[32767 * 127, -32767 * 127]]], dtype=np.int64)
        result = builder.checked_accumulator_with_bias(raw, np.array([1], dtype=np.int32))
        self.assertEqual(result.dtype, np.int32)
        np.testing.assert_array_equal(result, np.array([[[4161410, -4161408]]], dtype=np.int32))
        with self.assertRaises(OverflowError):
            builder.checked_accumulator_with_bias(np.array([[[2**31]]], dtype=np.int64),
                                                  np.array([0], dtype=np.int32))

    def test_q31_rounding_is_signed_ties_even_and_saturates(self):
        q = builder.requantize_q31(np.array([[[1, 3, -1, -3, 80000]]], dtype=np.int32),
                                   np.array([1 << 30], dtype=np.int32),
                                   np.array([31], dtype=np.int32), clip=(-32767, 32767))
        np.testing.assert_array_equal(q, np.array([[[0, 2, 0, -2, 32767]]], dtype=np.int16))

    def test_depthwise_and_pointwise_accumulate_match_small_exact_examples(self):
        x = np.arange(9, dtype=np.int16).reshape(1, 3, 3)
        w = np.ones((1, 1, 3, 3), dtype=np.int8)
        dw = builder.depthwise_accumulate(x, w)
        self.assertEqual(dw.dtype, np.int64)
        self.assertEqual(int(dw[0, 1, 1]), 36)
        px = np.array([[[1, 2]], [[3, 4]]], dtype=np.int16)
        pw = np.array([[2, -1], [1, 1]], dtype=np.int8)
        raw = builder.pointwise_accumulate(px, pw)
        np.testing.assert_array_equal(raw, np.array([[[ -1, 0]], [[4, 6]]], dtype=np.int64))


    def test_serializer_parameter_shapes_and_scale_targets_are_frozen(self):
        layers = {
            "dw3": {"weight_i8": np.ones((128, 1, 3, 3), dtype=np.int8), "weight_f32": np.ones((128, 1, 3, 3)), "weight_scales": np.ones(128), "bias_f32": np.zeros(128)},
            "dw7": {"weight_i8": np.ones((128, 1, 7, 7), dtype=np.int8), "weight_f32": np.ones((128, 1, 7, 7)), "weight_scales": np.ones(128), "bias_f32": np.zeros(128)},
            "pw1": {"weight_i8": np.ones((384, 128), dtype=np.int8), "weight_f32": np.ones((384, 128)), "weight_scales": np.ones(384), "bias_f32": np.zeros(384)},
            "pw2": {"weight_i8": np.ones((128, 384), dtype=np.int8), "weight_f32": np.ones((128, 384)), "weight_scales": np.ones(128), "bias_f32": np.zeros(128)},
            "residual_scale": np.full(128, 2.0, dtype=np.float32),
        }
        scales = {label: 1.0 for label in builder.TRACE_LABELS}
        scales.update({"pw2": 4.0, "add": 2.0, "scale": 100.0})
        arrays, specs = builder.make_block_parameter_arrays(layers, scales)
        for key, shape in (("dw3_weights", (128, 9)), ("dw7_weights", (128, 49)),
                           ("pw1_weights", (384, 128)), ("pw2_weights", (128, 384)),
                           ("bias_i32", (768,)), ("multiplier_i32", (768,)),
                           ("gelu_lut", (65536,)), ("scale_multiplier_i32", (128,)),
                           ("residual_multiplier_i32", (1,))):
            self.assertEqual(arrays[key].shape, shape)
        expected, unused = builder.q31_parameters(np.array([4.0]), signed=True)
        self.assertEqual(int(arrays["scale_multiplier_i32"][0]), int(expected[0]))
        self.assertTrue(all(item["worst_case_fits_int32"] for item in specs.values()))

    def test_block_parameter_submanifest_is_written_with_verified_hashes(self):
        import tempfile
        layers = {
            "dw3": {"weight_i8": np.ones((128, 1, 3, 3), dtype=np.int8), "weight_f32": np.ones((128, 1, 3, 3)), "weight_scales": np.ones(128), "bias_f32": np.zeros(128)},
            "dw7": {"weight_i8": np.ones((128, 1, 7, 7), dtype=np.int8), "weight_f32": np.ones((128, 1, 7, 7)), "weight_scales": np.ones(128), "bias_f32": np.zeros(128)},
            "pw1": {"weight_i8": np.ones((384, 128), dtype=np.int8), "weight_f32": np.ones((384, 128)), "weight_scales": np.ones(384), "bias_f32": np.zeros(384)},
            "pw2": {"weight_i8": np.ones((128, 384), dtype=np.int8), "weight_f32": np.ones((128, 384)), "weight_scales": np.ones(128), "bias_f32": np.zeros(128)},
            "residual_scale": np.ones(128, dtype=np.float32),
        }
        scales = {label: 1.0 for label in builder.TRACE_LABELS}
        trace_names = {label: {"tensor_name": "boundary/" + label}
                       for label in builder.TRACE_LABELS if label != "input"}
        with tempfile.TemporaryDirectory() as temp:
            record = builder.write_block_parameter_artifact(temp, 0, layers, scales, trace_names)
            submanifest = Path(temp) / record["path"]
            self.assertEqual(builder.sha256_file(submanifest), record["parameter_manifest_sha256"])
            parsed = json.loads(submanifest.read_text(encoding="utf-8"))
            self.assertEqual(parsed["parameters"]["dw3_weights"]["shape"], [128, 9])
            for item in parsed["parameters"].values():
                path = Path(temp) / item["path"]
                self.assertTrue(path.is_file())
                self.assertEqual(path.stat().st_size, item["bytes"])
                self.assertEqual(builder.sha256_file(path), item["sha256"])


class TraceAndArtifactContractTests(unittest.TestCase):
    def test_pinned_host_trace_manifest_identity_and_schema(self):
        root = Path(__file__).resolve().parents[3]
        path = root / "artifacts/board-debug-20261005/acceleration/host/network2-trace-split-002/manifest.json"
        if not path.is_file():
            self.skipTest("frozen network2 split trace is not present")
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),
                         "9f7a16199470b7846437475113d91bf9e8a2cdb183ee3dc1806befb89105d1bf")
        trace = json.loads(path.read_text(encoding="utf-8"))
        info = builder.validate_trace_manifest(trace)
        self.assertEqual(info["provenance"], "HOST_ONLY")
        self.assertEqual(info["sample_count"], 3)
        self.assertEqual(info["block_count"], 12)

    def test_host_trace_is_explicitly_not_board_ps_and_requires_all_12_blocks(self):
        labels = ["input", "dw3", "dw7", "pw1", "gelu", "pw2", "scale", "add"]
        blocks = [{"index": i, "input": "input.0" if i == 0 else "out.%d" % (i - 1),
                   "outputs": {label: "out-%s-%d" % (label, i) for label in labels if label != "input"}}
                  for i in range(12)]
        for i in range(1, 12):
            blocks[i]["input"] = blocks[i - 1]["outputs"]["add"]
        samples = []
        for sample_index in range(3):
            sample = {"sample_id": "image-%02d" % sample_index,
                      "input_sha256": ("a" if sample_index == 0 else "b" if sample_index == 1 else "c") * 64,
                      "files": []}
            for block in range(12):
                for label in labels:
                    shape = [1, 384, 32, 32] if label in ("pw1", "gelu") else [1, 128, 32, 32]
                    sample["files"].append({"block": block, "label": label,
                        "provenance": "HOST_ORT_REFERENCE_ONLY_NOT_BOARD_PS_CAPTURE",
                        "shape": shape, "dtype": "<f4", "bytes": int(np.prod(shape)) * 4,
                        "tensor_name": blocks[block]["input"] if label == "input" else
                                       blocks[block]["outputs"][label]})
            samples.append(sample)
        manifest = {"status": "HOST_NETWORK2_TRACE_SPLIT_VALIDATED_NOT_BOARD_PS_CAPTURE",
                    "blocks": blocks,
                    "host_reference": {"samples": samples}}
        info = builder.validate_trace_manifest(manifest)
        self.assertEqual(info["provenance"], "HOST_ONLY")
        self.assertEqual(info["sample_count"], 3)
        manifest["host_reference"]["samples"][0]["files"].pop()
        with self.assertRaises(ValueError):
            builder.validate_trace_manifest(manifest)

    def test_checker_rejects_host_artifact_when_board_provenance_is_required(self):
        manifest = {"status": "NETWORK2_INT_ORACLE_HOST_ONLY_NOT_BOARD_PS_OR_PL",
                    "provenance": {"mode": "HOST_ONLY"}, "files": {}}
        with self.assertRaises(ValueError):
            checker.validate_manifest_data(manifest, require_board=True)

    def test_checker_verifies_independent_submanifest_and_parameter_file_hashes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "block-00").mkdir()
            payload = b"fixed parameter bytes"
            parameter = root / "block-00/weights.bin"
            parameter.write_bytes(payload)
            parameter_meta = {"path": "block-00/weights.bin", "bytes": len(payload),
                              "sha256": hashlib.sha256(payload).hexdigest()}
            subdata = json.dumps({"block_index": 0}, sort_keys=True).encode("utf-8")
            subpath = root / "block-00/manifest.json"
            subpath.write_bytes(subdata)
            subsha = hashlib.sha256(subdata).hexdigest()
            blocks = []
            for index in range(12):
                blocks.append({"index": index,
                    "parameter_manifest_sha256": subsha if index == 0 else "0" * 64,
                    "verified_parameter_manifest_sha256": subsha if index == 0 else "0" * 64,
                    "parameter_manifest": ({"path": "block-00/manifest.json", "bytes": len(subdata),
                                            "sha256": subsha} if index == 0 else None),
                    "files": ({"weights": parameter_meta} if index == 0 else {})})
            report = {"status": "NETWORK2_INT_ORACLE_HOST_ONLY_NOT_BOARD_PS_OR_PL",
                      "provenance": {"mode": "HOST_ONLY"}, "block_count": 12,
                      "dependencies": [{"sha256": "a" * 64}], "blocks": blocks, "files": {}}
            (root / "manifest.json").write_text(json.dumps(report), encoding="utf-8")
            result = checker.validate_oracle_directory(root)
            self.assertTrue(result["valid"])
            self.assertEqual(result["verified_file_count"], 2)
            parameter.write_bytes(b"tampered")
            with self.assertRaises(ValueError):
                checker.validate_oracle_directory(root)

    def test_boundary_chain_requires_exact_tensor_name_identity(self):
        blocks = []
        for index in range(12):
            blocks.append({"index": index, "outputs": {"add": "tensor-%d" % index},
                           "input": "root" if index == 0 else "tensor-%d" % (index - 1)})
        self.assertTrue(builder.validate_block_chain(blocks))
        blocks[1]["input"] = "renamed"
        with self.assertRaises(ValueError):
            builder.validate_block_chain(blocks)

    def test_stage3_004_bridge_reproduces_frozen_block0_post_dw7_arrays(self):
        root = Path(__file__).resolve().parents[3]
        artifact = root / "artifacts/board-debug-20261004/acceleration/host/stage3-network20-int16-004"
        manifest_path = artifact / "manifest.json"
        if not manifest_path.is_file():
            self.skipTest("frozen Stage3-004 evidence is not present in this checkout")
        self.assertEqual(hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
                         "164fdff3ab1a09e0b6282f4281ed09e7846cb44ace36ddbdca86ab57237e94c7")
        report = json.loads(manifest_path.read_text(encoding="utf-8"))
        stage2 = root / "artifacts/board-debug-20261004/acceleration/host/stage2-dw3-dw7-int16act-007"
        stage2_manifest = stage2 / "manifest.json"
        self.assertEqual(hashlib.sha256(stage2_manifest.read_bytes()).hexdigest(),
                         "68e2a29131ca0965783b00eea54049c313de669e1c758b738f4c530bb78cd282")
        stage2_report = json.loads(stage2_manifest.read_text(encoding="utf-8"))

        def array(record):
            data = np.fromfile(str(artifact / record["path"]), dtype=record["dtype"])
            self.assertEqual(data.size, int(np.prod(record["shape"])))
            return data.reshape(record["shape"])

        files = report["files"]
        case_files = next(item["files"] for item in report["results"]
                          if item["sample_id"] == "image-00")
        params = report["parameter_files"]
        stage2_files = stage2_report["results"][0]["files"]

        def stage2_array(record):
            data = np.fromfile(str(stage2 / record["path"]), dtype=record["dtype"])
            self.assertEqual(data.size, int(np.prod(record["shape"])))
            return data.reshape(record["shape"])

        qinput = stage2_array(stage2_files["dw7_stage3_i16"]).astype(np.int16)
        fc1 = params["pw128-to-384"]
        w1 = array(fc1["weights-kn.i8"])
        b1 = array(fc1["bias.i32"]).reshape(-1)
        raw1 = checker._pointwise_independent(qinput, w1)
        total1 = checker._checked_bias_independent(raw1, b1)
        np.testing.assert_array_equal(total1, array(case_files["fc1_with_bias_i32"])[0])
        q1 = checker._q31_independent(total1,
            array(fc1["requant-multiplier.i32"]).reshape(-1),
            array(fc1["requant-shift.i32"]).reshape(-1), (-32767, 32767))
        np.testing.assert_array_equal(q1, array(case_files["fc1_output_i16"])[0])

        lut = array(params["scale_add_gelu"]["gelu-int16-lut.i16le"])
        qgelu = lut[q1.astype(np.int32) + 32768]
        np.testing.assert_array_equal(qgelu, array(case_files["gelu_output_i16"])[0])
        fc2 = params["pw384-to-128"]
        w2 = array(fc2["weights-kn.i8"])
        b2 = array(fc2["bias.i32"]).reshape(-1)
        total2 = checker._checked_bias_independent(checker._pointwise_independent(qgelu, w2), b2)
        np.testing.assert_array_equal(total2, array(case_files["fc2_with_bias_i32"])[0])
        q2 = checker._q31_independent(total2,
            array(fc2["requant-multiplier.i32"]).reshape(-1),
            array(fc2["requant-shift.i32"]).reshape(-1), (-32767, 32767))
        np.testing.assert_array_equal(q2, array(case_files["fc2_output_i16"])[0])

        scale_add = params["scale_add_gelu"]
        scaled = checker._q31_independent(q2,
            array(scale_add["scale-add-multiplier.i32"]).reshape(-1),
            array(scale_add["scale-add-shift.i32"]).reshape(-1), None)
        residual = checker._q31_independent(
            stage2_array(stage2_files["dw3_residual_i16"]).astype(np.int16),
            array(scale_add["residual-multiplier.i32"]).reshape(-1),
            array(scale_add["residual-shift.i32"]).reshape(-1), None)
        np.testing.assert_array_equal(scaled, array(case_files["scale_branch_i32"])[0])
        np.testing.assert_array_equal(residual, array(case_files["residual_branch_i32"])[0])
        output = np.clip(scaled + residual, -32767, 32767).astype(np.int16)
        np.testing.assert_array_equal(output, array(case_files["block_add_output_i16"])[0])


if __name__ == "__main__":
    unittest.main()
