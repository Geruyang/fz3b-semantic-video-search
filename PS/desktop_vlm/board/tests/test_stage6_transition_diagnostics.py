import unittest

import numpy as np

from desktop_vlm.board.stage6_transition_diagnostics import (
    _decode_hcw_tensor,
    _error_metrics,
    _saturation_counts,
    _run_fp32_semantic_segment,
    _validate_transition_order,
)


class Stage6TransitionDiagnosticTests(unittest.TestCase):
    def test_hcw_decode_round_trip_preserves_logical_chw(self):
        logical = np.arange(2 * 3 * 4, dtype="<i2").reshape((2, 3, 4))
        physical = np.ascontiguousarray(logical.transpose((1, 0, 2))).tobytes()
        decoded = _decode_hcw_tensor(physical, [3, 2, 4], [2, 3, 4])
        np.testing.assert_array_equal(decoded, logical)
        with self.assertRaisesRegex(ValueError, "HCW shape"):
            _decode_hcw_tensor(physical, [2, 3, 4], [2, 3, 4])

    def test_frozen_n1_n3_operator_order_is_checked(self):
        n1_kinds = ["depthwise_conv", "gelu", "pointwise_conv", "gelu"]
        n3_kinds = ["depthwise_conv", "se_reduce_mean", "se_fc1", "relu",
                    "se_fc2", "sigmoid", "se_gate_mul", "gelu",
                    "pointwise_conv", "gelu"]
        _validate_transition_order(
            {"sequence": [{"kind": kind} for kind in n1_kinds]},
            {"sequence": [{"kind": kind} for kind in n3_kinds]})
        with self.assertRaisesRegex(ValueError, "N3 ONNX sequence"):
            _validate_transition_order(
                {"sequence": [{"kind": kind} for kind in n1_kinds]},
                {"sequence": [{"kind": kind} for kind in reversed(n3_kinds)]})

    def test_error_metrics_and_endpoint_saturation_counts_are_explicit(self):
        reference = np.asarray([1.0, -2.0, 4.0], dtype=np.float32)
        actual = np.asarray([1.5, -2.0, 3.0], dtype=np.float32)
        metrics = _error_metrics(actual, reference)
        self.assertEqual(metrics["max_abs"], 1.0)
        self.assertTrue(0.0 < metrics["cosine"] <= 1.0)
        saturation = _saturation_counts(
            np.asarray([-32767, 0, 32767], dtype=np.int16),
            reference_output=np.asarray([-4.0, 0.0, 4.0], dtype=np.float32),
            output_scale=0.0001,
            weights=np.asarray([-32767, 0, 32767], dtype=np.int16))
        self.assertEqual(saturation["input_endpoint_code_count"], 2)
        self.assertEqual(saturation["reference_output_clip_count"], 2)
        self.assertEqual(saturation["weight_endpoint_code_count"], 2)

    def test_fp32_semantic_slice_runs_only_declared_nodes(self):
        import onnx
        from onnx import TensorProto, helper, numpy_helper

        x_info = helper.make_tensor_value_info("x", TensorProto.FLOAT, [1, 1, 2, 2])
        y_info = helper.make_tensor_value_info("y", TensorProto.FLOAT, [1, 1, 2, 2])
        weight = numpy_helper.from_array(np.asarray([[[[2.0]]]], dtype=np.float32), "w")
        bias = numpy_helper.from_array(np.asarray([-0.5], dtype=np.float32), "b")
        conv = helper.make_node("Conv", ["x", "w", "b"], ["conv_out"], name="conv")
        relu = helper.make_node("Relu", ["conv_out"], ["y"], name="relu")
        model = helper.make_model(
            helper.make_graph([conv, relu], "tiny", [x_info], [y_info], [weight, bias]),
            opset_imports=[helper.make_opsetid("", 13)])
        entry = {"start_index": 0, "end_index": 1,
                 "inputs": ["x", "w", "b"], "outputs": ["y"]}
        source = np.asarray([[[[-1.0, 0.0], [1.0, 2.0]]]], dtype=np.float32)
        actual = _run_fp32_semantic_segment(model, [entry], source)
        np.testing.assert_allclose(actual, np.asarray([[[[0.0, 0.0], [1.5, 3.5]]]], dtype=np.float32))


if __name__ == "__main__":
    unittest.main()
