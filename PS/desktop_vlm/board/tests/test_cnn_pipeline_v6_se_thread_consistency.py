"""Tests for the offline ORT thread-consistency measurement helper."""

import hashlib
import json
import os
import tempfile

import numpy as np
import pytest

from desktop_vlm.board.cnn_pipeline_v6_se_thread_consistency import (
    pairwise_metrics, run_thread_consistency,
)


class FakeClient(object):
    created = []

    def __init__(self, command, contract, threads=1, expected_version=None):
        self.threads = threads
        self.contract = contract
        self.expected_version = expected_version
        self.closed = False
        self.header = {
            "kind": "ready", "api_version": 16, "ort_version": "1.16.3",
            "threads": threads, "load_ms": 12.5,
            "inputs": [{"name": contract["inputs"][0]["name"],
                        "shape": [1, 256, 16, 16], "dtype": "float32",
                        "bytes": 262144}],
            "outputs": [{"name": contract["outputs"][0]["name"],
                         "shape": [1, 256, 16, 16], "dtype": "float32",
                         "bytes": 262144}],
            "input_bytes": 262144, "output_bytes": 262144,
        }
        self.seen_input = None
        FakeClient.created.append(self)

    def infer(self, tensors):
        self.seen_input = tensors[0].copy()
        output = np.full((1, 256, 16, 16), self.threads,
                         dtype=np.float32)
        return {self.contract["outputs"][0]["name"]: output}, self.threads * 1.25

    def close(self):
        self.closed = True


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _fixture(tmp_path):
    model = tmp_path / "network3-ps-se-gelu.onnx"
    model.write_bytes(b"fixture model bytes")
    hcw = np.arange(16 * 256 * 16, dtype=np.int32).reshape(16, 256, 16)
    hcw = ((hcw % 65536) - 32768).astype("<i2")
    fixture = tmp_path / "p5-output.hcw.i16le"
    fixture.write_bytes(hcw.tobytes())
    return model, fixture, hcw


def _run(tmp_path, outputs=None):
    model, fixture, hcw = _fixture(tmp_path)
    FakeClient.created = []
    result = run_thread_consistency(
        str(model), str(fixture), 0.125,
        runner_path="fake-ort-runner",
        expected_model_sha256=_sha(model.read_bytes()),
        expected_input_sha256=_sha(fixture.read_bytes()),
        input_name="network3_dw_output",
        output_name="network3_se_gelu_output",
        output_dir=str(tmp_path / "results"),
        client_factory=FakeClient)
    return result, hcw


def test_runs_fresh_one_two_four_thread_clients_and_reports_pairwise_exactness(tmp_path):
    result, hcw = _run(tmp_path)
    assert [item["threads"] for item in result["runs"]] == [1, 2, 4]
    assert all(client.closed for client in FakeClient.created)
    expected = hcw.transpose(1, 0, 2).astype(np.float32) * np.float32(0.125)
    for client in FakeClient.created:
        np.testing.assert_array_equal(client.seen_input, expected.reshape(1, 256, 16, 16))
    assert all(run["ort_version"] == "1.16.3" for run in result["runs"])
    assert all(run["header"]["kind"] == "ready" for run in result["runs"])
    assert [run["run_ms"] for run in result["runs"]] == [1.25, 2.5, 5.0]
    assert len(result["pairwise"]) == 3
    assert result["pairwise"][0]["byte_exact"] is False
    assert result["pairwise"][0]["max_abs"] == 1.0
    assert result["pairwise"][0]["cosine_similarity"] == pytest.approx(1.0)
    assert all(os.path.isfile(run["output_path"]) for run in result["runs"])
    saved = np.load(result["runs"][0]["output_path"])
    assert saved.shape == (1, 256, 16, 16)
    assert saved.dtype == np.float32
    assert result["pl_execution"] is False
    assert result["accuracy_claim"] is False


def test_input_sha_mismatch_fails_before_starting_any_ort_client(tmp_path):
    model, fixture, unused_hcw = _fixture(tmp_path)
    FakeClient.created = []
    with pytest.raises(ValueError, match="input fixture SHA256"):
        run_thread_consistency(
            str(model), str(fixture), 0.125, "fake-ort-runner",
            _sha(model.read_bytes()), "0" * 64,
            "network3_dw_output", "network3_se_gelu_output",
            str(tmp_path / "results"), client_factory=FakeClient)
    assert FakeClient.created == []


def test_rejects_wrong_fixture_extent_and_nonpositive_scale(tmp_path):
    model, fixture, unused_hcw = _fixture(tmp_path)
    fixture.write_bytes(b"short")
    with pytest.raises(ValueError, match="exactly 131072 bytes"):
        run_thread_consistency(
            str(model), str(fixture), 0.125, "fake-ort-runner",
            _sha(model.read_bytes()), _sha(fixture.read_bytes()),
            "network3_dw_output", "network3_se_gelu_output",
            str(tmp_path / "results"), client_factory=FakeClient)
    fixture.write_bytes(bytes(16 * 256 * 16 * 2))
    with pytest.raises(ValueError, match="positive finite"):
        run_thread_consistency(
            str(model), str(fixture), 0.0, "fake-ort-runner",
            _sha(model.read_bytes()), _sha(fixture.read_bytes()),
            "network3_dw_output", "network3_se_gelu_output",
            str(tmp_path / "results"), client_factory=FakeClient)


def test_rejects_nonfinite_output_and_still_closes_client(tmp_path):
    model, fixture, unused_hcw = _fixture(tmp_path)

    class NonfiniteClient(FakeClient):
        def infer(self, tensors):
            output = np.zeros((1, 256, 16, 16), dtype=np.float32)
            output.reshape(-1)[0] = np.nan
            return {self.contract["outputs"][0]["name"]: output}, 1.0

    FakeClient.created = []
    with pytest.raises(ValueError, match="non-finite"):
        run_thread_consistency(
            str(model), str(fixture), 0.125, "fake-ort-runner",
            _sha(model.read_bytes()), _sha(fixture.read_bytes()),
            "network3_dw_output", "network3_se_gelu_output",
            str(tmp_path / "results"), client_factory=NonfiniteClient)
    assert FakeClient.created[0].closed


def test_pairwise_metrics_define_zero_vector_cosine(tmp_path):
    zero = np.zeros((1, 256, 16, 16), dtype=np.float32)
    ones = np.ones((1, 256, 16, 16), dtype=np.float32)
    both_zero = pairwise_metrics(zero, zero.copy(), 1, 2)
    one_zero = pairwise_metrics(zero, ones, 1, 4)
    assert both_zero["byte_exact"] is True
    assert both_zero["cosine_similarity"] == 1.0
    assert one_zero["byte_exact"] is False
    assert one_zero["cosine_similarity"] == 0.0
    result, unused_hcw = _run(tmp_path)
    report_path = tmp_path / "results" / "thread-consistency.json"
    with open(str(report_path), "r") as stream:
        on_disk = json.load(stream)
    assert on_disk["report_type"] == "FZV6_N3_PS_SE_GELU_THREAD_CONSISTENCY"
    assert on_disk["model_sha256"] == result["model_sha256"]

