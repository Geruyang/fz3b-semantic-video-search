"""Contract tests for the fail-closed Network2 twelve-block PS runtime.

The injected clients/backend are test doubles for call-count and lifecycle
checks only; these tests do not measure board execution or model accuracy.
"""

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import partition_network2_cascade_s1 as runtime_module
from partition_network2_cascade_s1 import (
    HOST_CASCADE_ORACLE_MANIFEST_SHA256,
    NotReady,
    Network2CascadeRuntime,
    ProtocolError,
)


REPO = Path(__file__).resolve().parents[3]
SPLIT_DIR = REPO / "artifacts/board-debug-20261005/acceleration/host/network2-trace-split-002"
HOST_ORACLE_DIR = REPO / "artifacts/board-debug-20261005/acceleration/host/network2-int-oracle-board-ps-001"
FIXTURE_DIR = REPO / "artifacts/board-debug-20261005/acceleration/host/network2-cascade-fixture-001"


def contract_activation(index=0):
    packet = (FIXTURE_DIR / ("image-%02d.input.bin" % index)).read_bytes()
    offset = (runtime_module.CASCADE_FRAME_HEADER_BYTES +
              runtime_module.CASCADE_BLOCK_HEADER_BYTES +
              runtime_module.CASCADE_PARAMETER_BYTES)
    qactivation = np.frombuffer(packet[offset:offset + 262144], dtype="<i2")
    oracle = __import__("json").loads((HOST_ORACLE_DIR / "manifest.json").read_text())
    scale = oracle["results"][index]["qinput_scale"]
    return (qactivation.astype(np.float64) * scale).astype("<f4").reshape((1, 128, 32, 32))


class FakeOrtClient(object):
    def __init__(self, name, output, calls):
        self.name = name
        self.output = output
        self.calls = calls
        self.closed = 0

    def infer(self, inputs):
        self.calls.append((self.name, inputs))
        if self.name == "prefix":
            return {runtime_module.BLOCK0_INPUT_TENSOR: self.output}, 0.0
        return {"features": self.output}, 0.0

    def close(self):
        self.closed += 1


class FakeCascadeBackend(object):
    def __init__(self, output_i16=None, pl_execution=False, invalid_receipt=None):
        self.execution_identity = {"pl_execution": pl_execution,
                                   "contract_test_only": not pl_execution}
        self.output_i16 = (np.full((1, 128, 32, 32), 3, dtype="<i2")
                           if output_i16 is None else output_i16)
        self.invalid_receipt = invalid_receipt or {}
        self.calls = []
        self.closed = 0

    def run_cascade_frame(self, logical_frame_id, packet):
        self.calls.append((logical_frame_id, packet))
        receipt = {
            "logical_frame_id": logical_frame_id,
            "hardware_frame_id": logical_frame_id + 100,
            "request_id": logical_frame_id + 200,
            "completed_frames_before": logical_frame_id,
            "completed_frames_after": logical_frame_id + 1,
            "mode": runtime_module.CASCADE_MODE,
            "input_bytes": len(packet),
            "output_bytes": runtime_module.CASCADE_OUTPUT_BYTES,
            "physical_transfer_count": 1,
            "tlast_count": 1,
            "parameter_manifest_sha256": runtime_module.HOST_CASCADE_PARAMETER_MANIFEST_SHA256,
            "output_i16": self.output_i16.tobytes(order="C"),
        }
        receipt.update(self.invalid_receipt)
        return receipt

    def close(self):
        self.closed += 1


def make_runtime(monkeypatch, backend=None, ort_factory=None):
    calls = []
    prefix_output = contract_activation()
    suffix_output = np.full((1, 512), 1.25, dtype="<f4")

    def factory(name, model_path, contract, threads):
        if ort_factory is not None:
            return ort_factory(name, model_path, contract, threads)
        output = prefix_output if name == "prefix" else suffix_output
        return FakeOrtClient(name, output, calls)

    if backend is None:
        backend = FakeCascadeBackend()
    session = Network2CascadeRuntime(
        split_dir=SPLIT_DIR,
        parameter_manifest_dir=HOST_ORACLE_DIR,
        runner_path="unused-in-contract-test",
        backend=backend,
        ort_client_factory=factory,
        allow_host_contract_test=True,
        contract_fixture_dir=FIXTURE_DIR,
    )
    return session, backend, calls


def test_frozen_trace_split_proves_only_block0_input_and_block11_add_boundaries():
    backend = FakeCascadeBackend()
    seen = []
    session = Network2CascadeRuntime(
        split_dir=SPLIT_DIR, parameter_manifest_dir=HOST_ORACLE_DIR,
        runner_path="unused", backend=backend,
        ort_client_factory=lambda name, path, contract, threads: (
            seen.append((name, contract, threads)) or
            FakeOrtClient(name, np.zeros((1, 128, 32, 32), dtype="<f4"), [])),
        allow_host_contract_test=True, contract_fixture_dir=FIXTURE_DIR)
    try:
        assert session.split_manifest_sha256 == runtime_module.TRACE_SPLIT_MANIFEST_SHA256
        assert session.prefix_contract["outputs"][0]["name"] == runtime_module.BLOCK0_INPUT_TENSOR
        assert session.suffix_contract["inputs"] == [{
            "name": runtime_module.BLOCK11_ADD_TENSOR,
            "shape": (1, 128, 32, 32), "bytes": 524288, "dtype": "<f4"}]
        assert seen[0][0] == "prefix" and seen[1][0] == "suffix"
    finally:
        session.close()


def test_one_quantization_one_mode4_transfer_one_dequantization_and_suffix_run(monkeypatch):
    quantize_calls = []
    dequantize_calls = []
    original_quantize = runtime_module.quantize_block0_input
    original_dequantize = runtime_module.dequantize_block11_add

    def quantize_spy(value, scale):
        quantize_calls.append(scale)
        return original_quantize(value, scale)

    def dequantize_spy(value, scale):
        dequantize_calls.append(scale)
        return original_dequantize(value, scale)

    monkeypatch.setattr(runtime_module, "quantize_block0_input", quantize_spy)
    monkeypatch.setattr(runtime_module, "dequantize_block11_add", dequantize_spy)
    session, backend, ort_calls = make_runtime(monkeypatch)
    try:
        result = session.infer_tensor(np.zeros((1, 3, 256, 256), dtype="<f4"), 5)
        assert len(quantize_calls) == 1
        assert len(dequantize_calls) == 1
        assert [name for name, unused in ort_calls] == ["prefix", "suffix"]
        assert len(backend.calls) == 1
        frame_id, packet = backend.calls[0]
        assert frame_id == 5
        assert isinstance(packet, bytes)
        assert len(packet) == runtime_module.CASCADE_INPUT_BYTES == 3245600
        fixture_row = json.loads((FIXTURE_DIR / "fixture-manifest.json").read_text())["images"][0]
        assert hashlib.sha256(packet).hexdigest() == fixture_row["input_sha256"]
        assert result["packet_sha256"] == fixture_row["input_sha256"]
        assert result["frame_mapping"]["logical_frame_id"] == 5
        assert result["pl_execution"] is False
        assert result["performance_eligible"] is False
        assert "timing_ms" not in result
        assert result["features"].shape == (1, 512)
        assert result["features"].dtype == np.dtype("<f4")
    finally:
        session.close()


def test_actual_v3_backend_is_not_ready_while_deployment_gate_is_unfrozen():
    backend = FakeCascadeBackend(pl_execution=True)
    with pytest.raises(NotReady, match="deployment gate is not frozen"):
        Network2CascadeRuntime(
            split_dir=SPLIT_DIR, parameter_manifest_dir=HOST_ORACLE_DIR,
            runner_path="unused", backend=backend,
            ort_client_factory=lambda *args: pytest.fail("ORT client must not start"),
            allow_host_contract_test=True, contract_fixture_dir=FIXTURE_DIR)


def test_missing_backend_is_not_ready_and_host_backend_requires_explicit_test_flag():
    with pytest.raises(NotReady, match="FZC1 cascade backend is not injected"):
        Network2CascadeRuntime(SPLIT_DIR, HOST_ORACLE_DIR, "unused", None)
    with pytest.raises(NotReady, match="host-only backend requires explicit contract-test opt-in"):
        Network2CascadeRuntime(
            SPLIT_DIR, HOST_ORACLE_DIR, "unused", FakeCascadeBackend(),
            ort_client_factory=lambda *args: pytest.fail("ORT client must not start"),
            contract_fixture_dir=FIXTURE_DIR)


def test_manifest_identity_mismatch_fails_before_creating_persistent_clients(tmp_path):
    bad_split = tmp_path / "split"
    bad_split.mkdir()
    original = (SPLIT_DIR / "manifest.json").read_bytes()
    (bad_split / "manifest.json").write_bytes(original + b" ")
    backend = FakeCascadeBackend()
    with pytest.raises(ValueError, match="trace split manifest SHA256 mismatch"):
        Network2CascadeRuntime(
            bad_split, HOST_ORACLE_DIR, "unused", backend,
            ort_client_factory=lambda *args: pytest.fail("ORT client must not start"),
            allow_host_contract_test=True, contract_fixture_dir=FIXTURE_DIR)


def test_tampered_fixture_manifest_fails_closed_and_unknown_packet_can_still_run(tmp_path):
    bad_fixture = tmp_path / "fixture"
    bad_fixture.mkdir()
    fixture_manifest = (FIXTURE_DIR / "fixture-manifest.json").read_bytes()
    (bad_fixture / "fixture-manifest.json").write_bytes(fixture_manifest + b" ")
    backend = FakeCascadeBackend()
    with pytest.raises(ValueError, match="fixture manifest SHA256 mismatch"):
        Network2CascadeRuntime(
            SPLIT_DIR, HOST_ORACLE_DIR, "unused", backend,
            ort_client_factory=lambda *args: pytest.fail("ORT client must not start"),
            allow_host_contract_test=True, contract_fixture_dir=bad_fixture)
    assert backend.closed == 1

    backend = FakeCascadeBackend()
    session, unused_backend, unused_calls = make_runtime(None, backend=backend)
    clients = list(session.clients)
    client = clients[0]
    client.output = np.zeros((1, 128, 32, 32), dtype="<f4")
    result = session.infer_tensor(np.zeros((1, 3, 256, 256), dtype="<f4"), 0)
    assert backend.calls and len(backend.calls[0][1]) == runtime_module.CASCADE_INPUT_BYTES
    assert result["sample_id"] is None
    assert result["expected_output_sha256"] is None


def test_three_fixture_samples_are_mapped_by_actual_packet_and_output_sha_not_frame_id():
    session, backend, unused_calls = make_runtime(None)
    try:
        for offset, sample_index in enumerate((2, 0, 1)):
            session.clients[0].output = contract_activation(sample_index)
            backend.output_i16 = np.fromfile(
                str(FIXTURE_DIR / ("image-%02d.output.bin" % sample_index)), dtype="<i2").reshape(
                    (1, 128, 32, 32))
            result = session.infer_tensor(
                np.zeros((1, 3, 256, 256), dtype="<f4"), 40 + offset)
            row = session.fixture_manifest["images"][sample_index]
            assert result["sample_id"] == row["image"]
            assert result["packet_sha256"] == row["input_sha256"]
            assert result["output_i16_sha256"] == row["output_sha256"]
            assert result["expected_output_sha256"] == row["output_sha256"]
    finally:
        session.close()


def test_backend_transfer_error_closes_both_ort_clients_and_poison_session():
    backend = FakeCascadeBackend(invalid_receipt={"physical_transfer_count": 2})
    clients = []

    def factory(name, path, contract, threads):
        client = FakeOrtClient(name, contract_activation(), [])
        clients.append(client)
        return client

    session = Network2CascadeRuntime(
        SPLIT_DIR, HOST_ORACLE_DIR, "unused", backend,
        ort_client_factory=factory, allow_host_contract_test=True, contract_fixture_dir=FIXTURE_DIR)
    with pytest.raises(ProtocolError, match="one physical transfer"):
        session.infer_tensor(np.zeros((1, 3, 256, 256), dtype="<f4"), 0)
    assert session.failed
    assert [client.closed for client in clients] == [1, 1]
    with pytest.raises(RuntimeError, match="failed; close/recovery is required"):
        session.infer_tensor(np.zeros((1, 3, 256, 256), dtype="<f4"), 1)
    session.close()
    assert [client.closed for client in clients] == [1, 1]


def test_pl_runtime_error_preserves_backend_for_verified_quiesce(monkeypatch):
    monkeypatch.setattr(runtime_module, "FZC1_PL_DEPLOYMENT_GATE_FROZEN", True)
    backend = FakeCascadeBackend(pl_execution=True, invalid_receipt={"physical_transfer_count": 2})
    backend.execution_identity.update({
        "deployment_gate_frozen": True,
        "driver_abi": "network2-dma-abi-v3",
        "core_identity": "FZC1",
        "quantization_manifest_sha256": runtime_module.HOST_CASCADE_PARAMETER_MANIFEST_SHA256,
        "bitstream_sha256": "a" * 64,
        "driver_module_sha256": "b" * 64,
        "pl_clock_evidence_sha256": "c" * 64,
        "pl_clock_hz": 100000000,
    })
    quiesce_calls = []
    backend.quiesce = lambda: quiesce_calls.append("called") or {"quiesced": True, "poisoned": False}
    clients = []

    def factory(name, path, contract, threads):
        client = FakeOrtClient(name, contract_activation(), [])
        clients.append(client)
        return client

    session = Network2CascadeRuntime(
        SPLIT_DIR, HOST_ORACLE_DIR, "unused", backend,
        ort_client_factory=factory, contract_fixture_dir=FIXTURE_DIR)
    with pytest.raises(ProtocolError, match="one physical transfer"):
        session.infer_tensor(np.zeros((1, 3, 256, 256), dtype="<f4"), 0)
    assert session.failed
    assert [client.closed for client in clients] == [1, 1]
    assert backend.closed == 0
    session.close()
    assert backend.closed == 0
    assert backend.quiesce()["quiesced"] is True
    assert quiesce_calls == ["called"]


def test_suffix_factory_failure_closes_prefix_and_backend():
    backend = FakeCascadeBackend()
    prefix = FakeOrtClient("prefix", np.zeros((1, 128, 32, 32), dtype="<f4"), [])

    def factory(name, path, contract, threads):
        if name == "suffix":
            raise OSError("suffix startup failed")
        return prefix

    with pytest.raises(OSError, match="suffix startup failed"):
        Network2CascadeRuntime(
            SPLIT_DIR, HOST_ORACLE_DIR, "unused", backend,
            ort_client_factory=factory, allow_host_contract_test=True, contract_fixture_dir=FIXTURE_DIR)
    assert prefix.closed == 1
    assert backend.closed == 1


def test_frame_mapping_requires_one_contiguous_completion_and_exact_packet_contract():
    bad_receipts = [
        {"mode": 3},
        {"input_bytes": runtime_module.CASCADE_INPUT_BYTES - 1},
        {"output_bytes": runtime_module.CASCADE_OUTPUT_BYTES - 2},
        {"tlast_count": 2},
        {"completed_frames_after": 9},
    ]
    for invalid in bad_receipts:
        backend = FakeCascadeBackend(invalid_receipt=invalid)
        session, unused_backend, unused_calls = make_runtime(None, backend=backend)
        with pytest.raises(ProtocolError):
            session.infer_tensor(np.zeros((1, 3, 256, 256), dtype="<f4"), 7)
        assert session.failed
        session.close()


def test_output_length_and_dtype_errors_fail_closed_and_release_clients():
    backend = FakeCascadeBackend()
    backend.output_i16 = np.zeros((1, 128, 32, 32), dtype="<i4")
    clients = []

    def factory(name, path, contract, threads):
        client = FakeOrtClient(name, contract_activation(), [])
        clients.append(client)
        return client

    session = Network2CascadeRuntime(
        SPLIT_DIR, HOST_ORACLE_DIR, "unused", backend,
        ort_client_factory=factory, allow_host_contract_test=True, contract_fixture_dir=FIXTURE_DIR)
    with pytest.raises(ProtocolError, match="output bytes must be exactly"):
        session.infer_tensor(np.zeros((1, 3, 256, 256), dtype="<f4"), 0)
    assert [client.closed for client in clients] == [1, 1]


def test_close_aggregates_failures_after_attempting_every_resource():
    backend = FakeCascadeBackend()
    clients = []

    class BadCloseClient(FakeOrtClient):
        def close(self):
            self.closed += 1
            raise OSError("client close failed")

    def factory(name, path, contract, threads):
        client = BadCloseClient(name, np.zeros((1, 128, 32, 32), dtype="<f4"), [])
        clients.append(client)
        return client

    session = Network2CascadeRuntime(
        SPLIT_DIR, HOST_ORACLE_DIR, "unused", backend,
        ort_client_factory=factory, allow_host_contract_test=True, contract_fixture_dir=FIXTURE_DIR)
    with pytest.raises(RuntimeError, match="resource close failed"):
        session.close()
    assert [client.closed for client in clients] == [1, 1]
    assert backend.closed == 1

