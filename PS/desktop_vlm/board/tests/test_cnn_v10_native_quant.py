import pathlib
import sys
import time
import unittest

import numpy as np


BOARD = pathlib.Path(__file__).resolve().parents[1]
ROOT = BOARD.parents[1]
sys.path.insert(0, str(BOARD))

from activation_buffers import ActivationBufferWorkspace
from cnn_v10_native_quant import INT16_CLAMP, V10NativeQuantWorkspace
from cnn_pipeline_v10_bundle import load_v10_release_bundle


BUNDLE = (ROOT / "artifacts/board-debug-20261006/acceleration/host/"
          "network10-v10.1-release-bundle-001")
BUNDLE_SHA256 = "679dc768f3525f55c05134e4d66869ea8dacb5d9fee9b1bef4d88f83b5daa268"
PROFILE_SHAPES = {0: (128, 64), 1: (256, 32), 2: (64, 64)}


class V10NativeQuantTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = load_v10_release_bundle(BUNDLE, BUNDLE_SHA256)["parameter_contract"]

    def _check_equal(self, profile, source, scale, clamp=INT16_CLAMP):
        channels, width = PROFILE_SHAPES[profile]
        actual = V10NativeQuantWorkspace(
            profile, channels, width, clamp=clamp).quantize_chw_to_hcw(source, scale)
        reference_chw_f64 = np.asarray(source, dtype=np.float32)[0].astype(np.float64)
        reference_chw_f64 /= float(scale)
        np.rint(reference_chw_f64, out=reference_chw_f64)
        np.clip(reference_chw_f64, clamp[0], clamp[1], out=reference_chw_f64)
        reference = reference_chw_f64.transpose(1, 0, 2).astype("<i2")
        np.testing.assert_array_equal(actual, reference)
        self.assertEqual(actual.dtype, np.dtype("<i2"))
        self.assertEqual(actual.shape, (width, channels, width))
        self.assertEqual(actual.tobytes(), reference.tobytes())

    def test_random_inputs_match_existing_v10_profiles_and_release_scales(self):
        rng = np.random.RandomState(20261007)
        for profile, (channels, width) in PROFILE_SHAPES.items():
            source = rng.normal(0.0, 0.75,
                                (1, channels, width, width)).astype(np.float32)
            scales = (self.contract["profiles"][profile]["input_scale"],
                      0.125, 1.0)
            for scale in scales:
                with self.subTest(profile=profile, scale=scale):
                    self._check_equal(profile, source, scale)

    def test_ties_boundaries_and_clamps_are_byte_exact_for_each_profile(self):
        rng = np.random.RandomState(4107)
        for profile, (channels, width) in PROFILE_SHAPES.items():
            scale = self.contract["profiles"][profile]["input_scale"]
            source = np.zeros((1, channels, width, width), dtype=np.float32)
            quotients = np.concatenate((
                np.arange(-32770.5, 32769.5, dtype=np.float64),
                rng.uniform(-32772.0, 32772.0, 8192)))
            raw = (quotients * np.float64(scale)).astype(np.float32)
            around = np.concatenate((
                np.nextafter(raw, np.float32(-np.inf)), raw,
                np.nextafter(raw, np.float32(np.inf))))
            count = min(source.size, around.size)
            source.reshape(-1)[:count] = around[:count]
            source.reshape(-1)[count:count + 8] = np.array(
                [0.5, 1.5, 2.5, -0.5, -1.5, -2.5, 50000.0, -50000.0],
                dtype=np.float32) * np.float32(scale)
            with self.subTest(profile=profile):
                self._check_equal(profile, source, scale)
                self._check_equal(profile, source, scale, clamp=(-32767, 32767))

    def test_noncontiguous_source_and_output_reuse(self):
        channels, width = PROFILE_SHAPES[0]
        base = np.arange(channels * width * width * 2, dtype=np.float32).reshape(
            (1, channels, width, width * 2))
        source = base[..., ::2]
        workspace = V10NativeQuantWorkspace(0, channels, width)
        first = workspace.quantize_chw_to_hcw(source, 17.0)
        address = first.__array_interface__["data"][0]
        expected = ActivationBufferWorkspace(0, channels, width).quantize_chw_to_hcw(
            source, 17.0, "reference")
        np.testing.assert_array_equal(first, expected)
        source.fill(0)
        second = workspace.quantize_chw_to_hcw(source, 17.0)
        self.assertIs(first, second)
        self.assertEqual(second.__array_interface__["data"][0], address)
        self.assertTrue(np.all(second == 0))

    def test_profile_specific_clamp_is_explicit_and_validated(self):
        channels, width = PROFILE_SHAPES[2]
        source = np.zeros((1, channels, width, width), dtype=np.float32)
        source.reshape(-1)[:2] = [40000.0, -40000.0]
        actual = V10NativeQuantWorkspace(
            2, channels, width, clamp=(-32767, 32767)).quantize_chw_to_hcw(source, 1.0)
        self.assertEqual(actual.reshape(-1)[:2].tolist(), [32767, -32767])
        for bad in ((32768, 32769), (1, -1), (-32769, 32767), (0.0, 1)):
            with self.subTest(clamp=bad), self.assertRaises(ValueError):
                V10NativeQuantWorkspace(2, channels, width, clamp=bad)

    def test_benchmark_boundary_reports_conversion_only(self):
        """Manual smoke measurement; no performance threshold is asserted."""
        rng = np.random.RandomState(17)
        for profile, (channels, width) in PROFILE_SHAPES.items():
            source = rng.normal(size=(1, channels, width, width)).astype(np.float32)
            scale = self.contract["profiles"][profile]["input_scale"]
            native = V10NativeQuantWorkspace(profile, channels, width)
            reference = ActivationBufferWorkspace(profile, channels, width)
            for _ in range(3):
                native.quantize_chw_to_hcw(source, scale)
                reference.quantize_chw_to_hcw(source, scale, "reference")
            samples = []
            for workspace in (reference, native):
                start = time.perf_counter()
                for _ in range(30):
                    if workspace is reference:
                        workspace.quantize_chw_to_hcw(source, scale, "reference")
                    else:
                        workspace.quantize_chw_to_hcw(source, scale)
                samples.append((time.perf_counter() - start) * 1000.0 / 30.0)
            print("profile%d conversion only: reference=%.3f ms, fused-order=%.3f ms" %
                  (profile, samples[0], samples[1]))


if __name__ == "__main__":
    unittest.main()
