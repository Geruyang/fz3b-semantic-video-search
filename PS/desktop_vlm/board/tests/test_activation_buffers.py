"""Tests for per-frame, reusable v5 activation conversion workspaces."""

import unittest

import numpy as np

from desktop_vlm.board import cnn_ddr_v5_runtime as runtime
from desktop_vlm.board.activation_buffers import ActivationBufferWorkspace


ROOT = runtime.os.path.abspath(runtime.os.path.join(
    runtime.os.path.dirname(__file__), "..", "..", ".."))
FIXTURE_ROOT = runtime.os.path.join(
    ROOT, "artifacts", "board-debug-20261005", "acceleration", "host")


class ActivationBufferWorkspaceTests(unittest.TestCase):
    def _workspace(self, profile):
        spec = runtime.PROFILE_SPECS[profile]
        return ActivationBufferWorkspace(profile, spec.channels, spec.width)

    def _legacy_quantize_hcw(self, value, scale, profile):
        chw = runtime.quantize_chw(value, scale, profile, "test")
        return runtime._chw_to_hcw(chw, profile)

    def _legacy_dequantize_chw(self, value, scale, profile):
        chw = runtime._hcw_to_chw(value, profile)
        return runtime.dequantize_chw(chw, scale, profile, "test")

    def test_quantize_fused_result_matches_legacy_for_each_profile(self):
        for profile in runtime.PROFILE_SPECS:
            spec = runtime.PROFILE_SPECS[profile]
            scale = 0.125
            source = np.linspace(-7.75, 7.75, spec.activation_bytes // 2,
                                 dtype=np.float32).reshape(
                                     (1, spec.channels, spec.width, spec.width))
            workspace = self._workspace(profile)
            actual = workspace.quantize_chw_to_hcw(source, scale, "test")
            expected = self._legacy_quantize_hcw(source, scale, profile)
            np.testing.assert_array_equal(actual, expected)
            self.assertEqual(actual.dtype, np.dtype("<i2"))
            self.assertEqual(actual.shape,
                             (spec.width, spec.channels, spec.width))
            self.assertEqual(actual.tobytes(), expected.tobytes())

    def test_quantize_exact_bytes_match_real_v5_manifest_scales(self):
        contracts = runtime._read_v5_bundle(FIXTURE_ROOT)["contracts"]
        rng = np.random.RandomState(20261005)
        for profile in runtime.PROFILE_SPECS:
            spec = runtime.PROFILE_SPECS[profile]
            source = rng.uniform(-1.0, 1.0,
                                 size=(1, spec.channels, spec.width, spec.width))
            source = source.astype(np.float32)
            scale = contracts[profile]["input_scale"]
            actual = self._workspace(profile).quantize_chw_to_hcw(
                source, scale, "manifest input")
            expected = self._legacy_quantize_hcw(source, scale, profile)
            self.assertEqual(actual.tobytes(), expected.tobytes(),
                             "profile %d differs at manifest scale %.17g" %
                             (profile, scale))

    def test_quantize_uses_ties_to_even_and_saturates(self):
        workspace = self._workspace(2)
        spec = runtime.PROFILE_SPECS[2]
        source = np.zeros((1, spec.channels, spec.width, spec.width),
                          dtype=np.float32)
        source.flat[:8] = [0.5, 1.5, 2.5, -0.5, -1.5, -2.5, 50000.0, -50000.0]
        actual = workspace.quantize_chw_to_hcw(source, 1.0, "test")
        expected = self._legacy_quantize_hcw(source, 1.0, 2)
        np.testing.assert_array_equal(actual, expected)
        self.assertEqual(actual[0, 0, :8].tolist(),
                         [0, 2, 2, 0, -2, -2, 32767, -32768])

    def test_quantize_accepts_noncontiguous_chw_input(self):
        spec = runtime.PROFILE_SPECS[0]
        base = np.arange(1 * spec.channels * spec.width * spec.width * 2,
                         dtype=np.float32).reshape(
                             (1, spec.channels, spec.width, spec.width * 2))
        source = base[..., ::2]
        self.assertFalse(source.flags.c_contiguous)
        workspace = self._workspace(0)
        actual = workspace.quantize_chw_to_hcw(source, 17.0, "test")
        expected = self._legacy_quantize_hcw(source, 17.0, 0)
        np.testing.assert_array_equal(actual, expected)

    def test_quantize_rejects_bad_shape_and_nonfinite_values(self):
        workspace = self._workspace(1)
        spec = runtime.PROFILE_SPECS[1]
        expected_shape = (1, spec.channels, spec.width, spec.width)
        with self.assertRaises(ValueError):
            workspace.quantize_chw_to_hcw(np.zeros(expected_shape[1:],
                                                   dtype=np.float32), 1.0, "test")
        source = np.zeros(expected_shape, dtype=np.float32)
        source[0, 0, 0, 0] = np.inf
        with self.assertRaises(ValueError):
            workspace.quantize_chw_to_hcw(source, 1.0, "test")

    def test_dequantize_fused_result_matches_legacy_for_each_profile(self):
        for profile in runtime.PROFILE_SPECS:
            spec = runtime.PROFILE_SPECS[profile]
            source = np.arange(spec.activation_bytes // 2, dtype=np.int32)
            source = ((source % 65536) - 32768).astype("<i2").reshape(
                (spec.width, spec.channels, spec.width))
            workspace = self._workspace(profile)
            actual = workspace.dequantize_hcw_to_chw(source, 0.03125, "test")
            expected = self._legacy_dequantize_chw(source, 0.03125, profile)
            np.testing.assert_array_equal(actual, expected)
            self.assertEqual(actual.dtype, np.dtype(np.float32))
            self.assertEqual(actual.shape,
                             (1, spec.channels, spec.width, spec.width))

    def test_dequantize_rejects_bad_dtype_shape_and_scale(self):
        workspace = self._workspace(0)
        spec = runtime.PROFILE_SPECS[0]
        shape = (spec.width, spec.channels, spec.width)
        with self.assertRaises(ValueError):
            workspace.dequantize_hcw_to_chw(np.zeros(shape, dtype=np.int32), 1.0, "test")
        with self.assertRaises(ValueError):
            workspace.dequantize_hcw_to_chw(np.zeros(shape[1:], dtype="<i2"), 1.0, "test")
        with self.assertRaises(ValueError):
            workspace.dequantize_hcw_to_chw(np.zeros(shape, dtype="<i2"), 0.0, "test")

    def test_repeated_calls_reuse_workspace_output_objects_and_addresses(self):
        workspace = self._workspace(2)
        spec = runtime.PROFILE_SPECS[2]
        source = np.zeros((1, spec.channels, spec.width, spec.width), dtype=np.float32)
        quantized = workspace.quantize_chw_to_hcw(source, 0.5, "first")
        quantized_id = id(quantized)
        quantized_address = quantized.__array_interface__["data"][0]
        source.fill(1.0)
        quantized_again = workspace.quantize_chw_to_hcw(source, 0.5, "second")
        self.assertIs(quantized_again, quantized)
        self.assertEqual(quantized_again.__array_interface__["data"][0], quantized_address)
        self.assertEqual(id(quantized_again), quantized_id)
        self.assertTrue(np.all(quantized_again == 2))

        output = workspace.dequantize_hcw_to_chw(quantized_again, 0.25, "first")
        output_id = id(output)
        output_address = output.__array_interface__["data"][0]
        quantized_again.fill(4)
        output_again = workspace.dequantize_hcw_to_chw(quantized_again, 0.25, "second")
        self.assertIs(output_again, output)
        self.assertEqual(output_again.__array_interface__["data"][0], output_address)
        self.assertEqual(id(output_again), output_id)
        self.assertTrue(np.all(output_again == 1.0))


if __name__ == "__main__":
    unittest.main()
