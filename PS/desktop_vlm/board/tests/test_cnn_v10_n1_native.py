from __future__ import annotations

import ctypes
import hashlib
import math
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import types

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[3]
C_SOURCE = ROOT / "desktop_vlm" / "board" / "cnn_v10_n1_native.c"
HEADER_BYTES = 40


def _compile_native(output):
    compiler = Path("D:/Vivado/2026.1/Vitis/win64/tools/clang-16/bin/clang.exe")
    sysroot = Path("D:/Vivado/2026.1/Vitis/tps/mingw/10.0.0/win64.o/nt")
    if not compiler.is_file() or not sysroot.is_dir():
        compiler_name = shutil.which("clang")
        if compiler_name is None:
            pytest.fail("required host C compiler is unavailable")
        command = [compiler_name, "-std=c99", "-O2", "-shared", "-fPIC",
                   "-fno-fast-math", "-ffp-contract=off", "-pthread", str(C_SOURCE),
                   "-o", str(output), "-lm"]
    else:
        vitis = Path("D:/Vivado/2026.1/Vitis")
        runtime = [str(sysroot / "bin"), str(vitis / "bin"), str(vitis / "tps/win64"),
                   str(vitis / "lib/win64.o"),
                   str(vitis / "tps/mingw/6.2.0/win64.o/nt/bin"),
                   str(vitis / "win64/tools/clang-16/bin")]
        command = [str(compiler), "--target=x86_64-w64-windows-gnu",
                   "--sysroot=" + str(sysroot), "-std=c99", "-O2", "-shared",
                   "-fPIC", "-fno-fast-math", "-ffp-contract=off", "-pthread",
                   str(C_SOURCE), "-o", str(output), "-lm"]
        env = os.environ.copy()
        env["PATH"] = os.pathsep.join(runtime + [env.get("PATH", "")])
    if "env" not in locals():
        env = None
    subprocess.run(command, check=True, capture_output=True, text=True, env=env)


def _qweights(weights):
    rows = weights.reshape(weights.shape[0], -1).astype(np.float64)
    scales = (np.max(np.abs(rows), axis=1) / 127.0).astype(np.float32)
    scales[scales == 0] = 1.0
    q = np.clip(np.rint(rows / scales[:, None]), -127, 127).astype(np.int8)
    return q.reshape(weights.shape), scales


def _pack(rng):
    dw = rng.normal(0, 0.15, (128, 1, 7, 7)).astype(np.float32)
    pw = rng.normal(0, 0.07, (128, 128, 1, 1)).astype(np.float32)
    dwq, dws = _qweights(dw)
    pwq, pws = _qweights(pw)
    dwb = rng.normal(0, 0.03, 128).astype(np.float32)
    pwb = rng.normal(0, 0.03, 128).astype(np.float32)
    dmask = np.zeros(128, dtype=np.uint8)
    pmask = np.zeros(128, dtype=np.uint8)
    dmask[[3, 51]] = 1
    pmask[[9, 100]] = 1
    scales = (np.float32(0.0125), np.float32(0.0075), np.float32(0.004))
    blob = bytearray(b"N1W8A16\0" + np.asarray([1, 128, 128, 128, 0], dtype="<u4").tobytes()
                     + np.asarray(scales, dtype="<f4").tobytes())
    for value, dtype in ((dwq, "i1"), (dws, "<f4"), (dwb, "<f4"),
                         (dw, "<f4"), (dmask, "u1"), (pwq, "i1"),
                         (pws, "<f4"), (pwb, "<f4"), (pw, "<f4"),
                         (pmask, "u1")):
        blob.extend(np.asarray(value, dtype=dtype).tobytes())
    return bytes(blob), (dw, dwq, dws, dwb, dmask, pw, pwq, pws, pwb, pmask, scales)


def _gelu(x):
    x = np.asarray(x, dtype=np.float32)
    erf = np.frompyfunc(math.erf, 1, 1)(x.astype(np.float64) / math.sqrt(2)).astype(np.float32)
    return (np.float32(0.5) * x * (np.float32(1.0) + erf)).astype(np.float32)


def _oracle(source, params):
    dw, dwq, dws, dwb, dmask, pw, pwq, pws, pwb, pmask, scales = params
    input_scale, pw_scale, output_scale = map(np.float32, scales)
    hcw_input = source.reshape(64, 64, 64)
    padded = np.pad(hcw_input, ((3, 3), (0, 0), (3, 3)))
    dw_gelu = np.empty((32, 128, 32), dtype=np.float32)
    mid = np.empty((32, 128, 32), dtype=np.int16)
    for oc in range(128):
        ic = oc // 2
        if dmask[oc]:
            facc = np.zeros((32, 32), dtype=np.float32)
            for ky in range(7):
                for kx in range(7):
                    aq = padded[ky:ky + 64:2, ic, kx:kx + 64:2].astype(np.float32)
                    term = np.asarray(np.float32(aq * input_scale) * dw[oc, 0, ky, kx], dtype=np.float32)
                    facc = np.asarray(facc + term, dtype=np.float32)
            y = np.asarray(facc + dwb[oc], dtype=np.float32)
        else:
            acc = np.zeros((32, 32), dtype=np.int64)
            for ky in range(7):
                for kx in range(7):
                    aq = padded[ky:ky + 64:2, ic, kx:kx + 64:2].astype(np.int64)
                    acc += aq * int(dwq[oc, 0, ky, kx])
            y = np.asarray(acc.astype(np.float32) * np.float32(input_scale * dws[oc]) + dwb[oc], dtype=np.float32)
        g = _gelu(y)
        dw_gelu[:, oc, :] = g
        mid[:, oc, :] = np.clip(np.rint(g.astype(np.float64) / np.float64(pw_scale)), -32767, 32767).astype(np.int16)
    result = np.empty((32, 128, 32), dtype=np.int16)
    for oc in range(128):
        if pmask[oc]:
            facc = np.zeros((32, 32), dtype=np.float32)
            for ic in range(128):
                a = np.asarray(mid[:, ic, :].astype(np.float32) * pw_scale, dtype=np.float32)
                term = np.asarray(a * pw[oc, ic, 0, 0], dtype=np.float32)
                facc = np.asarray(facc + term, dtype=np.float32)
            y = np.asarray(facc + pwb[oc], dtype=np.float32)
        else:
            acc = np.zeros((32, 32), dtype=np.int64)
            for ic in range(128):
                acc += mid[:, ic, :].astype(np.int64) * int(pwq[oc, ic, 0, 0])
            y = np.asarray(acc.astype(np.float32) * np.float32(pw_scale * pws[oc]) + pwb[oc], dtype=np.float32)
        g = _gelu(y)
        result[:, oc, :] = np.clip(np.rint(g.astype(np.float64) / np.float64(output_scale)), -32767, 32767).astype(np.int16)
    return result


@pytest.fixture(scope="module")
def compiled_native():
    with tempfile.TemporaryDirectory(prefix="cnn-v10-n1-native-") as temp:
        path = Path(temp) / "cnn_v10_n1_native.dll"
        _compile_native(path)
        pthread_runtime = None
        runtime_dir = Path("D:/Vivado/2026.1/Vitis/tps/mingw/10.0.0/win64.o/nt/bin")
        if runtime_dir.is_dir() and hasattr(os, "add_dll_directory"):
            pthread_runtime = os.add_dll_directory(str(runtime_dir))
        lib = ctypes.CDLL(os.fspath(path))
        function = lib.cnn_v10_n1_infer_int16_hcw
        scalar = lib.cnn_v10_n1_infer_int16_hcw_scalar
        profile = lib.cnn_v10_n1_infer_int16_hcw_profile
        for export in (function, scalar):
            export.argtypes = [ctypes.POINTER(ctypes.c_uint8), ctypes.c_size_t,
                               ctypes.POINTER(ctypes.c_int16), ctypes.POINTER(ctypes.c_int16)]
            export.restype = ctypes.c_int
        profile.argtypes = [ctypes.POINTER(ctypes.c_uint8), ctypes.c_size_t,
                            ctypes.POINTER(ctypes.c_int16), ctypes.POINTER(ctypes.c_int16),
                            ctypes.POINTER(ctypes.c_double), ctypes.POINTER(ctypes.c_double)]
        profile.restype = ctypes.c_int
        function.profile = profile
        yield function, scalar
        import _ctypes
        function.profile = None
        function = None
        scalar = None
        profile = None
        _ctypes.FreeLibrary(lib._handle)
        lib._handle = 0
        if pthread_runtime is not None:
            pthread_runtime.close()


@pytest.mark.parametrize("seed,sparse", [(1007, True), (1008, False)])
def test_native_full_shape_matches_python_oracle(compiled_native, seed, sparse):
    neon_export, scalar_export = compiled_native
    rng = np.random.RandomState(seed)
    blob, params = _pack(rng)
    source = rng.randint(-200, 201, size=(64, 64, 64), dtype=np.int16)
    if sparse:
        source.fill(0)
        source[31, 17, 29] = 137
        source[0, 0, 0] = -91
    expected = _oracle(source, params)
    output = np.empty((32, 128, 32), dtype=np.int16)
    p = ctypes.create_string_buffer(blob)
    input_ptr = source.ctypes.data_as(ctypes.POINTER(ctypes.c_int16))
    output_ptr = output.ctypes.data_as(ctypes.POINTER(ctypes.c_int16))
    for export in (neon_export, scalar_export):
        status = export(ctypes.cast(p, ctypes.POINTER(ctypes.c_uint8)), len(blob),
                        input_ptr, output_ptr)
        assert status == 0
        np.testing.assert_array_equal(output, expected)


def test_signed32_storage_domain_proofs_cover_both_reductions():
    # Conservative full storage domains include the INT16/INT8 sign endpoints.
    dw_abs = 49 * 32768 * 128
    pw_abs = 128 * 32768 * 128
    assert dw_abs == 205_520_896
    assert pw_abs == 536_870_912
    assert dw_abs < (1 << 31)
    assert pw_abs < (1 << 31)


def test_three_worker_channel_splits_are_pair_aligned_and_cover_128_once():
    # DW emits multiplier-2 channel pairs.  The former 2*(128*i/3) split
    # produced boundary 85 for worker 2 and let the NEON oc+1 store overrun.
    source = C_SOURCE.read_text(encoding="utf-8")
    assert "args[i].oc_begin = 2 * ((64 * i) / 3);" in source
    assert "args[i].oc_end = 2 * ((64 * (i + 1)) / 3);" in source
    starts = [2 * ((64 * i) // 3) for i in range(3)]
    ends = [2 * ((64 * (i + 1)) // 3) for i in range(3)]
    assert starts == [0, 42, 84]
    assert ends == [42, 84, 128]
    assert all(value % 2 == 0 for value in starts + ends)
    assert [channel for start, end in zip(starts, ends)
            for channel in range(start, end)] == list(range(128))


@pytest.mark.parametrize("blob_size", [1, 27, 39])
def test_native_rejects_truncated_parameter_blob_before_header_reads(compiled_native, blob_size):
    neon_export, scalar_export = compiled_native
    blob = ctypes.create_string_buffer(b"N1W8A16\0"[:blob_size])
    source = np.zeros((64, 64, 64), dtype=np.int16)
    output = np.empty((32, 128, 32), dtype=np.int16)
    for export in (neon_export, scalar_export):
        status = export(ctypes.cast(blob, ctypes.POINTER(ctypes.c_uint8)), blob_size,
                        source.ctypes.data_as(ctypes.POINTER(ctypes.c_int16)),
                        output.ctypes.data_as(ctypes.POINTER(ctypes.c_int16)))
        assert status == -1


def test_native_profile_export_reports_dw_and_pw_wall_time(compiled_native):
    neon_export, _ = compiled_native
    profile_export = neon_export.profile
    rng = np.random.RandomState(1010)
    blob, _ = _pack(rng)
    source = np.zeros((64, 64, 64), dtype=np.int16)
    output = np.empty((32, 128, 32), dtype=np.int16)
    params = ctypes.create_string_buffer(blob)
    dw_ms, pw_ms = ctypes.c_double(), ctypes.c_double()
    status = profile_export(
        ctypes.cast(params, ctypes.POINTER(ctypes.c_uint8)), len(blob),
        source.ctypes.data_as(ctypes.POINTER(ctypes.c_int16)),
        output.ctypes.data_as(ctypes.POINTER(ctypes.c_int16)),
        ctypes.byref(dw_ms), ctypes.byref(pw_ms))
    assert status == 0
    assert dw_ms.value > 0 and pw_ms.value > 0


def test_packer_rejects_old_oracle_fallback_semantics(tmp_path, monkeypatch):
    import importlib.util
    oracle_stub = types.ModuleType("cnn_v10_mixed_int")
    oracle_stub.INT32_MAX = (1 << 31) - 1
    oracle_stub.load_n1_contract = lambda *args, **kwargs: None
    oracle_stub.quantize_w8_per_output = lambda *args, **kwargs: None
    oracle_stub.accumulator_bound = lambda *args, **kwargs: None
    monkeypatch.setitem(__import__("sys").modules, "cnn_v10_mixed_int", oracle_stub)
    script = ROOT / "desktop_vlm" / "scripts" / "acceleration" / "cnn_v10_n1_native_pack.py"
    spec = importlib.util.spec_from_file_location("n1_native_pack", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    report = tmp_path / "old-oracle.json"
    report.write_text('{"schema_version":2,"contract":{"model_sha256":"abc"},"status":"MIXED_PASS"}', encoding="utf-8")
    with pytest.raises(ValueError, match="native A16-dequantized"):
        module._read_native_oracle(report, "abc")


def test_packer_consumes_schema_v2_mixed_report(tmp_path, monkeypatch):
    import importlib.util
    oracle_stub = types.ModuleType("cnn_v10_mixed_int")
    oracle_stub.INT32_MAX = (1 << 31) - 1
    oracle_stub.load_n1_contract = lambda *args, **kwargs: None
    oracle_stub.quantize_w8_per_output = lambda *args, **kwargs: None
    oracle_stub.accumulator_bound = lambda *args, **kwargs: None
    monkeypatch.setitem(__import__("sys").modules, "cnn_v10_mixed_int", oracle_stub)
    script = ROOT / "desktop_vlm" / "scripts" / "acceleration" / "cnn_v10_n1_native_pack.py"
    spec = importlib.util.spec_from_file_location("n1_native_pack_v2", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    bounds = []
    for terms in (49, 128):
        bounds.append({"bound": {"reduction_terms": terms, "activation_abs_max": 32768,
                                 "weight_abs_max": 128, "worst_case_abs": terms * 32768 * 128,
                                 "signed32_max": (1 << 31) - 1, "fits_signed32": True},
                       "observed_accumulator_min": -200,
                       "observed_accumulator_max": 300})
    case_metrics = {"cosine": 0.9993, "relative_l2": 0.02}
    selection = {"status": "PASS", "metrics": {"cosine": 0.9995, "relative_l2": 0.01},
                 "dw_fp32_channels": [2], "pw_fp32_channels": [3, 7],
                 "per_case_gate": [{"pass": True, "metrics": case_metrics} for _ in range(3)]}
    record = {"schema_version": 2, "status": "MIXED_PASS",
              "contract": {"model_sha256": "a" * 64},
              "mixed_execution_contract": {"status": "PASS",
                  "fallback_semantics": "native_a16_dequant_input_fp32_weights_accum; listed channels use A16"},
              "layer_error_attribution": {"mixed_candidate_search": selection},
              "overflow_proofs": bounds}
    path = tmp_path / "oracle-v2.json"
    path.write_text(__import__("json").dumps(record), encoding="utf-8")
    _, _, dw_channels, pw_channels, proofs = module._read_native_oracle(path, "a" * 64)
    assert dw_channels == [2] and pw_channels == [3, 7]
    assert [row["reduction_terms"] for row in proofs] == [49, 128]
