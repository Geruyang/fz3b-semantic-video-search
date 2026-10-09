import sys
import textwrap
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import benchmark_dw_memory_protocol as bench


def _fake_helper_script():
    return textwrap.dedent(r'''
        import json, struct, sys
        sys.stdout.write(json.dumps({"protocol":"DWJ2-MEMORY-SIM-V1", "status":"SIMULATED_NOT_PL", "outputs_are_zero":True}) + "\n")
        sys.stdout.flush()
        expected = 1
        job = 0
        while True:
            header = sys.stdin.buffer.read(12)
            if not header:
                break
            if len(header) != 12:
                sys.exit(20)
            magic, request_id, length = struct.unpack("<4sII", header)
            if magic != b"DWJ2" or request_id != expected or length != 1073:
                sys.exit(21)
            payload = sys.stdin.buffer.read(length)
            if len(payload) != length:
                sys.exit(22)
            job += 1
            response = {"request_id": request_id, "job_id": job,
                        "weight_count": 49, "pixel_count": 1024,
                        "output_count": 1024, "cycles": 0}
            sys.stdout.write(json.dumps(response, separators=(",", ":")) + "\n")
            sys.stdout.flush()
            sys.stdout.buffer.write(b"\0" * 4096)
            sys.stdout.buffer.flush()
            expected = (expected + 1) & 0xffffffff
    ''')


def _helper_command():
    return [sys.executable, "-u", "-c", _fake_helper_script()]


def test_memory_client_runs_128_contiguous_wire_jobs_and_marks_simulation():
    weights = [[(i % 255) - 128 for i in range(49)] for _ in range(128)]
    pixels = [[(i % 255) - 128 for i in range(1024)] for _ in range(128)]
    client = bench.MemoryProtocolClient(_helper_command(), timeout_s=2.0)
    try:
        assert client.metadata["status"] == "SIMULATED_NOT_PL"
        for index in range(128):
            result = client.run(weights[index], pixels[index])
            assert result["request_id"] == index + 1
            assert result["job_id"] == index + 1
            assert result["outputs"] == b"\0" * 4096
        assert client.next_request_id == 129
    finally:
        client.close()


def test_client_rejects_malformed_or_skipped_request_metadata():
    bad_script = textwrap.dedent(r'''
        import json, sys
        sys.stdout.write(json.dumps({"protocol":"DWJ2-MEMORY-SIM-V1", "status":"SIMULATED_NOT_PL", "outputs_are_zero":True}) + "\n")
        sys.stdout.flush()
        sys.stdin.buffer.read(12 + 1073)
        sys.stdout.write(json.dumps({"request_id":2, "job_id":1, "weight_count":49,
          "pixel_count":1024, "output_count":1024, "cycles":0}) + "\n")
        sys.stdout.flush()
    ''')
    client = bench.MemoryProtocolClient([sys.executable, "-u", "-c", bad_script], timeout_s=1.0)
    try:
        with pytest.raises(bench.ProtocolError, match="request_id"):
            client.run([0] * 49, [0] * 1024)
        with pytest.raises(bench.ProtocolError):
            client.run([0] * 49, [0] * 1024)
    finally:
        client.close()


def test_benchmark_reports_validation_and_protocol_as_simulated(monkeypatch):
    weights = [[0] * 49 for _ in range(128)]
    pixels = [[0] * 1024 for _ in range(128)]
    report = bench.benchmark_batches(weights, pixels, _helper_command(),
                                     warmup=1, iterations=2, timeout_s=2.0)
    assert report["classification"] == "SIMULATED_NOT_PL"
    assert report["validation_only"]["batches"] == 128
    assert report["ipc_only"]["jobs_per_run"] == 128
    assert report["protocol_roundtrip"]["jobs_per_run"] == 128
    assert report["protocol_roundtrip"]["iterations"] == 2
    assert report["protocol_roundtrip"]["jobs_total"] == 256
    assert report["protocol_roundtrip"]["p50_ms"] >= 0
    assert report["protocol_roundtrip"]["p95_ms"] >= 0


def test_validate_only_uses_production_int8_validator():
    calls = []
    original = bench.AxiDwUioAccessor._validate_int8_vector

    def observe(values, count, label, rows=None, columns=None):
        calls.append((count, label))
        return original(values, count, label, rows, columns)

    bench.AxiDwUioAccessor._validate_int8_vector = staticmethod(observe)
    try:
        report = bench.validation_only([[0] * 49 for _ in range(128)],
                                       [[0] * 1024 for _ in range(128)])
    finally:
        bench.AxiDwUioAccessor._validate_int8_vector = staticmethod(original)
    assert report["batches"] == 128
    assert len(calls) == 128 * 2 * 8


def test_shutdown_is_bounded_and_reaps_child():
    client = bench.MemoryProtocolClient(_helper_command(), timeout_s=2.0)
    process = client.process
    client.close()
    assert process.poll() is not None


def test_loader_keeps_the_pinned_ps_quant_arrays_native():
    repo = Path(__file__).resolve().parents[3]
    host = repo / "artifacts" / "board-debug-20261004" / "acceleration" / "host"
    weights, pixels, identity = bench.load_ps_fixture(
        str(host / "dw-int8-002"), str(host / "dw-ps-prefix-oracle-002"), 0)
    assert weights.shape == (128, 7, 7)
    assert pixels.shape == (128, 32, 32)
    assert str(weights.dtype) == "int8"
    assert str(pixels.dtype) == "int8"
    assert identity["classification"] == "SIMULATED_NOT_PL"
    assert identity["quantized_input_sha256"] == (
        "471ebe691f54f390edba493f6cded8a81222ce46c1de2238cd7dedad586eb6cc")

