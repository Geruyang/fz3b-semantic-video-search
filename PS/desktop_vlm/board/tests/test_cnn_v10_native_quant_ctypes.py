import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

import numpy as np


BOARD = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BOARD))

from activation_buffers import ActivationBufferWorkspace
from cnn_v10_native_quant import V10NativeQuantWorkspace
from cnn_v10_native_quant_ctypes import CtypesV10Quantizer


C_SOURCE = BOARD / "cnn_v10_native_quant_neon.c"


class FakeCFunction(object):
    def __init__(self, status=0):
        self.argtypes = None
        self.restype = None
        self.status = status
        self.calls = 0

    def __call__(self, source_ptr, channels, width, scale, target_ptr,
                 clamp_min, clamp_max):
        self.calls += 1
        count = channels * width * width
        src = np.ctypeslib.as_array(source_ptr, shape=(count,))
        dst = np.ctypeslib.as_array(target_ptr, shape=(count,))
        if self.status:
            return self.status
        chw = src.reshape(channels, width, width).astype(np.float64)
        np.divide(chw, scale, out=chw)
        np.rint(chw, out=chw)
        np.clip(chw, clamp_min, clamp_max, out=chw)
        dst_view = dst.reshape(width, channels, width)
        np.copyto(dst_view, chw.transpose(1, 0, 2), casting="unsafe")
        return 0


class FakeLibrary(object):
    def __init__(self, function=None):
        self.cnn_v10_quantize_chw_to_hcw = function or FakeCFunction()


class CtypesQuantizerTests(unittest.TestCase):
    def test_workspace_selects_native_library_and_reuses_hcw_output(self):
        channels, width = 64, 64
        function = FakeCFunction()
        workspace = V10NativeQuantWorkspace(
            2, channels, width, native_lib=FakeLibrary(function))
        source = np.random.RandomState(20261007).normal(
            size=(1, channels, width, width)).astype(np.float32)
        expected = ActivationBufferWorkspace(2, channels, width).quantize_chw_to_hcw(
            source, 0.00016495765799892816, "reference")
        result = workspace.quantize_chw_to_hcw(source, 0.00016495765799892816)
        address = result.__array_interface__["data"][0]
        np.testing.assert_array_equal(result, expected)
        self.assertEqual(function.calls, 1)
        result_again = workspace.quantize_chw_to_hcw(source, 0.00016495765799892816)
        self.assertIs(result_again, result)
        self.assertEqual(result_again.__array_interface__["data"][0], address)
        self.assertEqual(function.calls, 2)

    def test_wrapper_rejects_missing_symbol_and_propagates_native_errors(self):
        with self.assertRaisesRegex(ValueError, "missing"):
            CtypesV10Quantizer(object())
        channels, width = 64, 64
        workspace = V10NativeQuantWorkspace(
            2, channels, width, native_lib=FakeLibrary(FakeCFunction(-2)))
        with self.assertRaisesRegex(ValueError, "non-finite"):
            workspace.quantize_chw_to_hcw(
                np.zeros((1, channels, width, width), dtype=np.float32), 1.0)
        failed = V10NativeQuantWorkspace(
            2, channels, width, native_lib=FakeLibrary(FakeCFunction(7)))
        with self.assertRaisesRegex(RuntimeError, "status 7"):
            failed.quantize_chw_to_hcw(
                np.zeros((1, channels, width, width), dtype=np.float32), 1.0)

    def test_native_source_contract_keeps_double_division_and_exact_rounding(self):
        text = C_SOURCE.read_text(encoding="utf-8")
        self.assertIn("const double quotient = (double)src[w] / scale;", text)
        self.assertIn("round_ties_even(quotient)", text)
        self.assertIn("fmod(fabs(lower), 2.0)", text)
        self.assertIn("HCW traversal makes destination writes contiguous", text)
        self.assertIn("vdivq_f64", text)
        self.assertIn("vrndnq_f64", text)
        self.assertIn("cnn_v10_quantize_chw_to_hcw_scalar", text)
        self.assertNotIn("vrecpeq", text)
        self.assertNotIn("vrecpsq", text)
        self.assertNotIn("1.0f / scale", text)
        self.assertIn("-fno-fast-math", text)

    def test_host_compiled_scalar_and_fallback_exports_match_numpy(self):
        compiler = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
        if compiler is None:
            self.skipTest("no host C compiler available; scalar C compile is optional")
        with tempfile.TemporaryDirectory(prefix="v10-quant-c-") as temp:
            library_path = pathlib.Path(temp) / "libcnn_v10_native_quant.so"
            command = [compiler, "-std=c99", "-O2", "-fPIC", "-shared",
                       "-fno-fast-math", str(C_SOURCE), "-o", str(library_path), "-lm"]
            try:
                subprocess.run(command, check=True, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
            except (OSError, subprocess.CalledProcessError) as error:
                self.skipTest("host compiler cannot build shared library: %s" % error)

            rng = np.random.RandomState(61007)
            channels, width = 7, 5
            shape = (1, channels, width, width)
            count = channels * width * width
            scale = 0.00016495765799892816
            ties = (np.array([-3.5, -2.5, -1.5, -0.5, -0.0,
                              0.0, 0.5, 1.5, 2.5, 3.5]) * scale).astype(np.float32)
            near_zero = np.array([
                np.nextafter(np.float32(0.0), np.float32(-np.inf)),
                np.nextafter(np.float32(0.0), np.float32(np.inf)),
                np.nextafter(np.float32(0.5 * scale), np.float32(-np.inf)),
                np.float32(0.5 * scale),
                np.nextafter(np.float32(0.5 * scale), np.float32(np.inf)),
                np.nextafter(np.float32(-0.5 * scale), np.float32(-np.inf)),
                np.float32(-0.5 * scale),
                np.nextafter(np.float32(-0.5 * scale), np.float32(np.inf)),
            ], dtype=np.float32)
            saturation = (np.array([-32770.0, -32768.5, -32768.0, -32767.5,
                                    32766.5, 32767.0, 32767.5, 32770.0]) *
                          scale).astype(np.float32)
            random = (rng.uniform(-40000.0, 40000.0, 4 * count) * scale).astype(
                np.float32)
            cases = np.concatenate((random, np.tile(ties, 20),
                                    np.tile(near_zero, 20), np.tile(saturation, 20)))
            for clamp in ((-32768, 32767), (-32767, 32767)):
                for offset in range(0, cases.size, count):
                    source = np.zeros(shape, dtype=np.float32)
                    chunk = cases[offset:offset + count]
                    source.reshape(-1)[:chunk.size] = chunk
                    chw = source[0].astype(np.float64) / scale
                    expected = np.clip(np.rint(chw), *clamp).transpose(1, 0, 2).astype("<i2")
                    for symbol in ("cnn_v10_quantize_chw_to_hcw_scalar",
                                   "cnn_v10_quantize_chw_to_hcw"):
                        source.fill(0)
                        source.reshape(-1)[:chunk.size] = chunk
                        quantizer = CtypesV10Quantizer(library_path, symbol=symbol)
                        workspace = V10NativeQuantWorkspace(
                            2, channels, width, clamp=clamp, native_lib=quantizer)
                        actual = workspace.quantize_chw_to_hcw(source, scale)
                        np.testing.assert_array_equal(actual, expected)

                        nonfinite = source.copy()
                        nonfinite.reshape(-1)[0] = np.float32(np.nan)
                        before = workspace._output_i16.copy()
                        with self.assertRaisesRegex(ValueError, "finite"):
                            workspace.quantize_chw_to_hcw(nonfinite, scale)
                        np.testing.assert_array_equal(workspace._output_i16, before)


if __name__ == "__main__":
    unittest.main()
