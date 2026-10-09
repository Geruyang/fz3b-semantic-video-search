import os
import hashlib
import json
import tempfile
from pathlib import Path

import numpy as np

from desktop_vlm.board.cnn_ddr_v4_runtime import (
    FakeV4Transport,
    IOCTL_REQUESTS,
    LinuxIoctlV4Transport,
    _ALLOC_STRUCT,
    _FREE_STRUCT,
    _IDENTITY_STRUCT,
    _STATUS_STRUCT,
    _SUBMIT_STRUCT,
    _TRANSFER_STRUCT,
    _ioc,
    _V4_SPLIT_MANIFEST_SHA256,
    V4FullRuntime,
    V4NetworkAdapter,
    _FIXTURES,
    _read_fixture,
    load_v4_split_contracts,
    quantize_chw,
)
import ctypes
import struct
from unittest import mock


ROOT = Path(__file__).resolve().parents[3]
FIXTURE_ROOT = ROOT / "artifacts" / "board-debug-20261005" / "acceleration" / "host"
TEST_SCALES = {
    "network2_input": 9.687628574169352e-05,
    "network2_output": 8.010273432023655e-06,
    "network4_input": 7.726196825520674e-05,
    "network4_output": 2.462270113096634e-05,
}


def _bind_test_fixture_scales(adapter):
    adapter.contracts[0]["input_scale"] = TEST_SCALES["network2_input"]
    adapter.contracts[0]["output_scale"] = TEST_SCALES["network2_output"]


class RecordingTransport(FakeV4Transport):
    def __init__(self):
        super(RecordingTransport, self).__init__()
        self.uploads = []

    def upload(self, handle, offset, payload):
        self.uploads.append((handle, offset, bytes(payload)))
        super(RecordingTransport, self).upload(handle, offset, payload)


def test_v4_fixture_packages_are_manifest_and_sha_pinned():
    profile0 = _read_fixture(0, str(FIXTURE_ROOT))
    profile1 = _read_fixture(1, str(FIXTURE_ROOT))
    assert profile0["manifest_sha256"] == _FIXTURES[0]["manifest_sha256"]
    assert profile1["manifest_sha256"] == _FIXTURES[1]["manifest_sha256"]
    assert (profile0["manifest"]["channel_count"], profile0["manifest"]["block_count"]) == (128, 12)
    assert (profile1["manifest"]["channel_count"], profile1["manifest"]["block_count"]) == (256, 20)
    assert profile0["manifest"]["checks"]["pl_execution"] is False
    assert profile1["manifest"]["checks"]["pl_execution"] is False


def test_final_feature_outputs_are_2048_bytes_sha_pinned_and_sorted_by_frame_id():
    from types import SimpleNamespace
    from desktop_vlm.board.cnn_ddr_v4_run import _write_feature_outputs
    with tempfile.TemporaryDirectory() as output_dir:
        results = [SimpleNamespace(frame_id=8, value={"features": np.full(512, 8, dtype="<f4")}),
                   SimpleNamespace(frame_id=2, value={"features": np.full(512, 2, dtype="<f4")})]
        records = _write_feature_outputs(output_dir, results)
        assert [record["frame_id"] for record in records] == [2, 8]
        assert [record["pipeline_order"] for record in records] == [1, 0]
        for record in records:
            path = Path(output_dir) / record["relative_path"]
            assert record["bytes"] == 2048
            assert path.stat().st_size == 2048
            assert hashlib.sha256(path.read_bytes()).hexdigest() == record["sha256"]


def test_cleanup_failure_writes_no_success_receipt_and_marks_raw_outputs_incomplete():
    from types import SimpleNamespace
    from desktop_vlm.board.cnn_ddr_v4_run import _finalize_report_after_cleanup

    class FailingRuntime(object):
        def __init__(self):
            self.adapter = SimpleNamespace(
                handles={0: (11, 12)},
                transport=SimpleNamespace(quiesced=False, closed=True, allocations={}))

        def close(self):
            raise RuntimeError("QUIESCE failed")

    with tempfile.TemporaryDirectory() as output_dir:
        outputs = [{"frame_id": 1, "relative_path": "feature-frame-1.f32",
                    "bytes": 2048, "sha256": "a" * 64}]
        try:
            _finalize_report_after_cleanup(output_dir, {"status": "would-be-success"},
                                           FailingRuntime(), outputs)
        except RuntimeError:
            pass
        else:
            raise AssertionError("cleanup failure unexpectedly finalized a success report")
        assert not (Path(output_dir) / "result.json").exists()
        incomplete = json.loads((Path(output_dir) / "incomplete.json").read_text())
        assert incomplete["status"] == "INCOMPLETE_NO_FINAL_RECEIPT"
        assert incomplete["feature_outputs_without_final_receipt"] == outputs


def test_success_report_is_written_only_with_complete_cleanup_receipt():
    from types import SimpleNamespace
    from desktop_vlm.board.cnn_ddr_v4_run import _finalize_report_after_cleanup

    class SuccessfulRuntime(object):
        def __init__(self):
            self.adapter = SimpleNamespace(
                handles={}, transport=SimpleNamespace(quiesced=False, closed=False,
                                                       allocations={}))

        def close(self):
            self.adapter.transport.quiesced = True
            self.adapter.transport.closed = True

    with tempfile.TemporaryDirectory() as output_dir:
        report = {"status": "RUNTIME_EXECUTED_HOST_DEVELOPMENT_PREFLIGHT"}
        _finalize_report_after_cleanup(output_dir, report, SuccessfulRuntime(), [])
        written = json.loads((Path(output_dir) / "result.json").read_text())
        assert written["cleanup_receipt"] == {
            "quiesce_confirmed": True, "all_handles_freed": True,
            "transport_closed": True}


def test_host_joint_preflight_manifest_cannot_be_promoted_to_board_gate():
    from desktop_vlm.board.cnn_ddr_v4_run import _read_reference_manifest
    manifest = FIXTURE_ROOT / "v4-joint-feature-preflight-001" / "manifest.json"
    digest = hashlib.sha256(manifest.read_bytes()).hexdigest()
    record = {"path": os.path.relpath(str(manifest), str(FIXTURE_ROOT)), "sha256": digest}
    evidence = _read_reference_manifest(str(FIXTURE_ROOT), record, digest,
                                        "host_development_preflight", "joint INT")
    assert evidence["board_capture"] is False
    assert evidence["pl_execution"] is False
    assert evidence["gate_approved"] is False
    try:
        _read_reference_manifest(str(FIXTURE_ROOT), record, digest,
                                 "board_acceptance", "joint INT")
    except ValueError:
        pass
    else:
        raise AssertionError("host preflight manifest was accepted as board gate")


def test_board_joint_reference_role_requires_structured_capture_oracle_and_boot_evidence():
    from desktop_vlm.board.cnn_ddr_v4_run import _read_reference_manifest
    with tempfile.TemporaryDirectory() as root:
        evidence = {"role": "joint_int_reference_board_acceptance",
                    "board_capture": True, "independent_int_oracle": True,
                    "same_board_c_ort_bridge_suffix": True, "pl_execution": False,
                    "gate_approved": True,
                    "source_boot_id": "123e4567-e89b-12d3-a456-426614174000"}
        manifest = {"status": "BOARD_CAPTURED_JOINT_INT_REFERENCE",
                    "execution_provenance": {"board_capture": True,
                                             "pl_execution": False},
                    "board_acceptance_evidence": evidence}
        path = Path(root) / "joint-reference.json"
        path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        record = {"path": path.name, "sha256": digest}
        parsed = _read_reference_manifest(root, record, digest,
                                          "board_acceptance", "joint INT")
        assert parsed["board_capture"] is True
        assert parsed["pl_execution"] is False
        assert parsed["independent_int_oracle"] is True
        assert parsed["same_board_c_ort_bridge_suffix"] is True
        assert parsed["gate_approved"] is True
        manifest["board_acceptance_evidence"]["source_boot_id"] = "not-a-boot-id"
        path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
        changed_sha = hashlib.sha256(path.read_bytes()).hexdigest()
        try:
            _read_reference_manifest(root, {"path": path.name, "sha256": changed_sha},
                                     changed_sha, "board_acceptance", "joint INT")
        except ValueError:
            pass
        else:
            raise AssertionError("invalid source boot_id unexpectedly accepted")


def test_runtime_fails_closed_when_fixture_scale_contract_is_missing_or_mismatched():
    adapter = V4NetworkAdapter(FakeV4Transport(), str(FIXTURE_ROOT))
    adapter.contracts[0]["input_scale"] = None
    try:
        try:
            V4FullRuntime(
                adapter, lambda _fid, value: value, lambda _fid, value: value,
                lambda _fid, value: value,
                network2_input_scale=TEST_SCALES["network2_input"],
                network2_output_scale=TEST_SCALES["network2_output"],
                network4_input_scale=TEST_SCALES["network4_input"],
                network4_output_scale=TEST_SCALES["network4_output"],
                joint_int_reference_features={1: np.zeros((512,), dtype="<f4")},
                joint_int_reference_manifest_sha256="a" * 64,
                joint_int_reference_source="host preflight test",
                pure_ps_reference_features={1: np.zeros((512,), dtype="<f4")},
                pure_ps_reference_manifest_sha256="b" * 64,
                pure_ps_reference_source="pure PS test")
        except ValueError as error:
            assert "all four runtime scales" in str(error)
        else:
            raise AssertionError("missing fixture scale was accepted")
    finally:
        adapter.close()


def test_runtime_rejects_scale_values_that_differ_from_fixture_contract():
    adapter = V4NetworkAdapter(FakeV4Transport(), str(FIXTURE_ROOT))
    _bind_test_fixture_scales(adapter)
    try:
        try:
            V4FullRuntime(
                adapter, lambda _fid, value: value, lambda _fid, value: value,
                lambda _fid, value: value,
                network2_input_scale=TEST_SCALES["network2_input"] * 2,
                network2_output_scale=TEST_SCALES["network2_output"],
                network4_input_scale=TEST_SCALES["network4_input"],
                network4_output_scale=TEST_SCALES["network4_output"],
                joint_int_reference_features={1: np.zeros((512,), dtype="<f4")},
                joint_int_reference_manifest_sha256="a" * 64,
                joint_int_reference_source="host preflight test",
                pure_ps_reference_features={1: np.zeros((512,), dtype="<f4")},
                pure_ps_reference_manifest_sha256="b" * 64,
                pure_ps_reference_source="pure PS test")
        except ValueError as error:
            assert "differ from SHA-pinned parameter manifests" in str(error)
        else:
            raise AssertionError("unbound runtime scale unexpectedly accepted")
    finally:
        adapter.close()


def test_runtime_controls_cover_serial4_matched_and_candidate_pipeline_options():
    from desktop_vlm.board.cnn_ddr_v4_run import _runtime_controls
    preset, budget, pipeline = _runtime_controls({
        "thread_preset": "serial4", "pipeline_options": {"max_in_flight": 1}})
    assert preset == "serial4"
    assert budget == {"prefix": 4, "network2_network4_bridge_worker": 4, "suffix": 4}
    assert pipeline["max_in_flight"] == 1
    preset, budget, pipeline = _runtime_controls({
        "thread_preset": "matched1_3", "pipeline_options": {"queue_capacity": 3}})
    assert budget == {"prefix": 1, "network2_network4_bridge_worker": 1, "suffix": 3}
    assert pipeline["queue_capacity"] == 3
    preset, budget, pipeline = _runtime_controls({
        "thread_preset": "candidate_prefix2_bridge1_suffix1",
        "pipeline_options": {"run_timeout_s": 120, "cleanup_timeout_s": 2,
                              "max_in_flight": 2}})
    assert budget == {"prefix": 2, "network2_network4_bridge_worker": 1, "suffix": 1}
    assert pipeline["run_timeout_s"] == 120.0 and pipeline["cleanup_timeout_s"] == 2.0
    try:
        _runtime_controls({"thread_preset": "serial4"})
    except ValueError:
        pass
    else:
        raise AssertionError("serial4 accepted cross-frame max_in_flight")


def test_quiesce_failure_never_frees_handles_but_closes_transport_file():
    class FailingQuiesceTransport(FakeV4Transport):
        def __init__(self):
            super(FailingQuiesceTransport, self).__init__()
            self.close_device_count = 0

        def quiesce(self):
            self.quiesce_count += 1
            raise RuntimeError("simulated poisoned device")

        def close_device(self):
            self.close_device_count += 1

    transport = FailingQuiesceTransport()
    adapter = V4NetworkAdapter(transport, str(FIXTURE_ROOT))
    try:
        adapter.close()
    except RuntimeError as error:
        assert "poisoned device" in str(error)
    else:
        raise AssertionError("failed QUIESCE did not propagate")
    assert transport.free_calls == []
    assert transport.close_device_count == 1
    assert adapter.closed is True
    assert len(adapter._owned_handles) == 4


def test_fake_pipeline_uses_live_network3_output_and_frozen_submit_shape():
    transport = RecordingTransport()
    adapter = V4NetworkAdapter(transport, str(FIXTURE_ROOT))
    _bind_test_fixture_scales(adapter)
    # Exactly two setup uploads: one complete parameter package for each profile.
    assert transport.upload_count == 2
    params_handles = {adapter.handles[p][0] for p in (0, 1)}
    n4_activation_handle = adapter.handles[1][1]
    seen_bridge = []

    def prefix(frame_id, image):
        return np.full((1, 128, 32, 32), frame_id + 1, dtype="<f4")

    def network3(frame_id, tensor):
        seen_bridge.append((frame_id, tensor.copy()))
        # A live runtime value that is distinct from the stored host fixture input.
        return np.full((1, 256, 16, 16), 0.004 * (frame_id + 1), dtype="<f4")

    def suffix(frame_id, tensor):
        return np.full((512,), float(tensor.mean()), dtype="<f4")

    expected_features = {}
    for frame_id in (1, 2):
        live_n3 = 0.004 * (frame_id + 1)
        live_int = np.rint(live_n3 / TEST_SCALES["network4_input"])
        live_output = live_int * TEST_SCALES["network4_output"]
        expected_features[frame_id] = np.full((512,), live_output, dtype="<f4")

    runtime = V4FullRuntime(
        adapter, prefix, network3, suffix,
        network2_input_scale=TEST_SCALES["network2_input"],
        network2_output_scale=TEST_SCALES["network2_output"],
        network4_input_scale=TEST_SCALES["network4_input"],
        network4_output_scale=TEST_SCALES["network4_output"],
        joint_int_reference_features=expected_features,
        joint_int_reference_manifest_sha256="b" * 64,
        joint_int_reference_role="board_acceptance",
        joint_int_reference_source="unit-test frozen capture",
        joint_int_reference_board_capture=True,
        joint_int_reference_pl_execution=False,
        joint_int_reference_gate_approved=True,
        joint_int_reference_independent_int_oracle=True,
        joint_int_reference_same_board_c_ort_bridge_suffix=True,
        joint_int_reference_source_boot_id="123e4567-e89b-12d3-a456-426614174000",
        pure_ps_reference_features={1: expected_features[1] + np.float32(0.001),
                                    2: expected_features[2] + np.float32(0.001)},
        pure_ps_reference_manifest_sha256="c" * 64,
        pure_ps_reference_source="pure-PS unit-test reference",
        thread_budget={"prefix": 2, "network2_network4_bridge_worker": 1, "suffix": 1})
    try:
        results = runtime.run([(1, "input-a"), (2, "input-b")], [1, 2])
        assert [result.frame_id for result in results] == [1, 2]
        assert len(seen_bridge) == 2
        assert [call[:2] for call in transport.submit_calls] == [(0, 12), (1, 20), (0, 12), (1, 20)]
        assert all(len(call) == 4 for call in transport.submit_calls)
        assert all(call[2] in params_handles for call in transport.submit_calls)
        assert all(call[3] == adapter.handles[call[0]][1] for call in transport.submit_calls)
        assert all(transport.download_calls[i][1:] == (0, 128 * 32 * 32 * 2)
                   for i in (0, 2))
        assert all(transport.download_calls[i][1:] == (0, 256 * 16 * 16 * 2)
                   for i in (1, 3))
        runtime_n4_uploads = [payload for handle, offset, payload in transport.uploads
                              if handle == n4_activation_handle]
        assert len(runtime_n4_uploads) == 2
        first_live = np.full((1, 256, 16, 16), 0.008, dtype="<f4")
        expected = quantize_chw(first_live, TEST_SCALES["network4_input"],
                                (1, 256, 16, 16), "expected")
        expected_hcw = np.ascontiguousarray(expected[0].transpose(1, 0, 2), dtype="<i2")
        assert runtime_n4_uploads[0] == expected_hcw.tobytes(order="C")
        assert len(transport._buffers[n4_activation_handle]) == 2 * 256 * 16 * 16 * 2
        assert n4_activation_handle not in params_handles
        component_names = results[0].components_ms
        assert set(component_names) == {"prefix", "backend", "suffix"}
        assert results[0].correct is True
        detail = results[0].value["timing_ms"]
        assert {"network3_bridge", "network4_live_quantize",
                "network2_live_quantize", "network4_output_dequantize"} <= set(detail)
        validation = results[0].value["validation"]
        assert validation["joint_quantized_int_reference"]["passed"] is True
        assert validation["joint_quantized_int_reference"]["thresholds"]["max_abs_lte"] == 1.0e-6
        assert validation["pure_ps_fp32_reference"]["metrics"]["max_abs"] > 1.0e-6
        assert validation["pure_ps_fp32_reference"]["gate_applied"] is False
    finally:
        runtime.close()
    assert transport.quiesce_count == 1
    assert len(transport.free_calls) == 4


def test_adapter_profile_shape_and_timing_items_are_explicit():
    transport = RecordingTransport()
    adapter = V4NetworkAdapter(transport, str(FIXTURE_ROOT))
    try:
        activation = np.zeros((1, 128, 32, 32), dtype="<i2")
        result = adapter.infer(0, activation)
        assert result["activation"].shape == activation.shape
        assert set(result["timing_ms"]) == {
            "layout_chw_to_hcw", "layout_hcw_to_chw", "activation_upload",
            "device_submit_wait", "activation_download"}
        assert set(adapter.setup_timings_ms) == {"parameter_upload_once"}
    finally:
        adapter.close()


def test_v4_split_bundle_is_pinned_and_has_real_n3_bridge_and_suffix_cut():
    model_dir = ROOT / "artifacts" / "board-debug-20261005" / "acceleration" / "host" / "v4-runtime-models-001"
    bundle = load_v4_split_contracts(str(model_dir))
    assert bundle["manifest_sha256"] == _V4_SPLIT_MANIFEST_SHA256
    assert set(bundle["models"]) == {"prefix", "network3-bridge", "suffix"}
    assert len(bundle["models"]["network3-bridge"]["contract"]["outputs"][0]["shape"]) == 4
    assert bundle["manifest"]["boundaries"]["network3_bridge"]["dw7_conv_stride"] == [2, 2]
    assert bundle["manifest"]["checks"]["network3_full_se_gate_chain_present"] is True
    assert bundle["manifest"]["checks"]["suffix_excludes_network4"] is True
    for case in bundle["manifest"]["cases"]:
        assert set(case["boundary_checks"]) == {
            "prefix_to_network2", "network3_bridge", "network4_output_to_suffix"}
        assert all(check["allclose_rtol_1e-6_atol_1e-6"] and check["max_abs"] == 0.0
                   for check in case["boundary_checks"].values())


class MockV4Ioctl(object):
    def __init__(self, identity_override=None, status_flags=0):
        self.identity_override = identity_override
        self.status_flags = status_flags
        self.completed = 0
        self.profile = 0
        self.next_handle = 100
        self.buffers = {}
        self.calls = []

    def __call__(self, fd, request, argument=None, mutate=False):
        self.calls.append((request, argument))
        if request == IOCTL_REQUESTS["GET_IDENTITY"]:
            words = [0x465A5634, 0x40000, 0x1ff, 4, 0x7, 40, 128,
                     2, 2, 12, 20, 128, 256, 32, 16, 15537, 35073]
            words += [0x3ff00000, 0x40000000]
            words += list(self.identity_override or (0,) * 8)
            argument[:] = _IDENTITY_STRUCT.pack(*words)
        elif request == IOCTL_REQUESTS["GET_STATUS"]:
            values = [self.completed, 0, self.status_flags, self.profile,
                      0, 0, 0, 0, 0, 0, 0, 1, 0, 0x89abcdef, 0x01234567]
            argument[:] = _STATUS_STRUCT.pack(*values)
        elif request == IOCTL_REQUESTS["ALLOC"]:
            size, alignment, flags, _, _, _ = _ALLOC_STRUCT.unpack(argument)
            handle = self.next_handle
            self.next_handle += 1
            self.buffers[handle] = bytearray(size)
            arena_index = 1 if flags == LinuxIoctlV4Transport.ALLOC_HIGH_ONLY else 0
            argument[:] = _ALLOC_STRUCT.pack(size, alignment, flags, handle, arena_index, 0)
        elif request in (IOCTL_REQUESTS["UPLOAD"], IOCTL_REQUESTS["DOWNLOAD"]):
            handle, reserved, offset, size, pointer = _TRANSFER_STRUCT.unpack(argument)
            assert reserved == 0
            if request == IOCTL_REQUESTS["UPLOAD"]:
                self.buffers[handle][offset:offset + size] = ctypes.string_at(pointer, size)
            else:
                ctypes.memmove(pointer, bytes(self.buffers[handle][offset:offset + size]), size)
        elif request == IOCTL_REQUESTS["SUBMIT"]:
            profile, blocks, params, activation = _SUBMIT_STRUCT.unpack(argument)
            assert profile in (0, 1) and blocks > 0 and params != activation
            self.profile = profile
            self.completed += 1
        elif request == IOCTL_REQUESTS["QUIESCE"]:
            self.status_flags = LinuxIoctlV4Transport.FLAG_QUIESCED
        elif request == IOCTL_REQUESTS["FREE"]:
            handle, reserved = _FREE_STRUCT.unpack(argument)
            assert reserved == 0
            del self.buffers[handle]
        else:
            raise AssertionError("unexpected ioctl request 0x%x" % request)
        return 0


def test_linux_ioctl_transport_encodes_opaque_offset_io_and_quiesce_free_order():
    assert (_IDENTITY_STRUCT.size, _ALLOC_STRUCT.size, _FREE_STRUCT.size,
            _TRANSFER_STRUCT.size, _SUBMIT_STRUCT.size, _STATUS_STRUCT.size) == (120, 32, 8, 32, 16, 60)
    assert IOCTL_REQUESTS == {
        "GET_IDENTITY": 0x80785840, "ALLOC": 0xc0205841,
        "FREE": 0x40085842, "UPLOAD": 0x40205843,
        "DOWNLOAD": 0x40205844, "SUBMIT": 0x40105845,
        "GET_STATUS": 0x803c5846, "QUIESCE": 0x00005847}
    assert IOCTL_REQUESTS["GET_IDENTITY"] == _ioc(2, "X", 0x40, 120)
    ioctl = MockV4Ioctl()
    transport = LinuxIoctlV4Transport(fd=9, ioctl_callable=ioctl)
    params = transport.alloc(35073 * 20 * 16, 64)
    activation = transport.alloc(2 * 8192 * 16, 64)
    payload = b"offset-payload!!"
    assert len(payload) == 16
    transport.upload(activation, 16, payload)
    assert transport.download(activation, 16, 16) == payload
    try:
        transport.upload(activation, 17, payload)
    except ValueError:
        pass
    else:
        raise AssertionError("unaligned transfer offset unexpectedly accepted")
    try:
        transport.download(activation, 16, 15)
    except ValueError:
        pass
    else:
        raise AssertionError("unaligned transfer size unexpectedly accepted")
    transport.submit(1, 20, params, activation)
    status = transport.wait_complete(1, 0.02)
    assert status["job_cycles"] == 0x0123456789abcdef
    assert _SUBMIT_STRUCT.unpack(next(arg for req, arg in reversed(ioctl.calls)
                                       if req == IOCTL_REQUESTS["SUBMIT"])) == (1, 20, params, activation)
    transport.quiesce()
    transport.free(params)
    transport.free(activation)
    assert len(transport.allocations) == 0
    quiesce_at = next(index for index, (request, _) in enumerate(ioctl.calls)
                      if request == IOCTL_REQUESTS["QUIESCE"])
    assert [request for request, _ in ioctl.calls[quiesce_at:]] == [
        IOCTL_REQUESTS["QUIESCE"], IOCTL_REQUESTS["GET_STATUS"],
        IOCTL_REQUESTS["FREE"], IOCTL_REQUESTS["FREE"]]
    transport.close_device()


def test_linux_ioctl_transport_fails_closed_on_identity_or_guard_status_mismatch():
    bad_identity = MockV4Ioctl(identity_override=(1,) * 8)
    try:
        LinuxIoctlV4Transport(fd=9, ioctl_callable=bad_identity)
    except Exception:
        pass
    else:
        raise AssertionError("mismatched identity unexpectedly accepted")
    bad_status = MockV4Ioctl(status_flags=LinuxIoctlV4Transport.FLAG_RUNNING)
    try:
        LinuxIoctlV4Transport(fd=9, ioctl_callable=bad_status)
    except Exception:
        pass
    else:
        raise AssertionError("running status unexpectedly accepted during open")


def test_linux_ioctl_transport_supports_explicit_high_arena_opaque_allocations():
    ioctl = MockV4Ioctl()
    transport = LinuxIoctlV4Transport(fd=9, ioctl_callable=ioctl)
    high_handle = transport.alloc(64, 64, flags=LinuxIoctlV4Transport.ALLOC_HIGH_ONLY)
    assert transport.allocations[high_handle]["arena_index"] == 1
    assert transport.allocations[high_handle]["flags"] == LinuxIoctlV4Transport.ALLOC_HIGH_ONLY
    transport.quiesce()
    transport.free(high_handle)
    transport.close_device()


def test_linux_ioctl_transport_allows_both_mixed_arena_submit_orientations():
    ioctl = MockV4Ioctl()
    transport = LinuxIoctlV4Transport(fd=9, ioctl_callable=ioctl)
    n4_params_high = transport.alloc(35073 * 20 * 16, 64,
                                    flags=LinuxIoctlV4Transport.ALLOC_HIGH_ONLY)
    n4_activation_low = transport.alloc(2 * 8192 * 16, 64)
    transport.submit(1, 20, n4_params_high, n4_activation_low)
    transport.wait_complete(1, 0.02)
    n2_params_low = transport.alloc(15537 * 12 * 16, 64)
    n2_activation_high = transport.alloc(2 * 16384 * 16, 64,
                                         flags=LinuxIoctlV4Transport.ALLOC_HIGH_ONLY)
    transport.submit(0, 12, n2_params_low, n2_activation_high)
    transport.wait_complete(0, 0.02)
    assert transport.allocations[n4_params_high]["arena_index"] == 1
    assert transport.allocations[n4_activation_low]["arena_index"] == 0
    assert transport.allocations[n2_params_low]["arena_index"] == 0
    assert transport.allocations[n2_activation_high]["arena_index"] == 1
    transport.quiesce()
    for handle in (n4_params_high, n4_activation_low, n2_params_low, n2_activation_high):
        transport.free(handle)
    transport.close_device()


def test_c_ort_partition_client_adapter_wires_prefix_live_bridge_suffix_and_fake_pl():
    from desktop_vlm.board import partition_s1
    from desktop_vlm.board import cnn_ddr_v4_runtime as runtime_module

    calls = []

    class MockOrtClient(object):
        def __init__(self, command, contract, threads=1, expected_version=None):
            self.command = command
            self.contract = contract
            self.threads = threads
            self.header = {"load_ms": 0.25}

        def infer(self, inputs):
            name = os.path.basename(self.command[2]).replace(".onnx", "")
            calls.append((name, np.asarray(inputs[0]).copy()))
            output_spec = self.contract["outputs"][0]
            output = np.zeros(output_spec["shape"], dtype="<f4")
            return {output_spec["name"]: output}, 0.1

        def close(self):
            calls.append(("close", self.threads))

    model_dir = ROOT / "artifacts" / "board-debug-20261005" / "acceleration" / "host" / "v4-runtime-models-001"
    real_adapter = runtime_module.V4NetworkAdapter

    def mock_adapter(*args, **kwargs):
        adapter = real_adapter(*args, **kwargs)
        _bind_test_fixture_scales(adapter)
        return adapter

    with mock.patch.object(partition_s1, "OrtPartitionClient", MockOrtClient), \
            mock.patch.object(runtime_module, "V4NetworkAdapter", mock_adapter):
        runtime = __import__("desktop_vlm.board.cnn_ddr_v4_runtime",
                             fromlist=["CnnDdrV4OrtRuntime"]).CnnDdrV4OrtRuntime(
            "ort_partition_runner", str(model_dir), str(FIXTURE_ROOT),
            transport=FakeV4Transport(), expected_ort_version="test-ort",
            thread_budget={"prefix": 2, "network2_network4_bridge_worker": 1,
                           "suffix": 1},
            runtime_options={
                "network2_input_scale": TEST_SCALES["network2_input"],
                "network2_output_scale": TEST_SCALES["network2_output"],
                "network4_input_scale": TEST_SCALES["network4_input"],
                "network4_output_scale": TEST_SCALES["network4_output"],
                "joint_int_reference_features": {7: np.zeros((512,), dtype="<f4")},
                "joint_int_reference_manifest_sha256": "b" * 64,
                "joint_int_reference_role": "host_development_preflight",
                "joint_int_reference_source": "test host preflight manifest",
                "pure_ps_reference_features": {7: np.zeros((512,), dtype="<f4")},
                "pure_ps_reference_manifest_sha256": "c" * 64,
                "pure_ps_reference_source": "test pure PS manifest",
                "queue_capacity": 1, "max_in_flight": 1,
                "run_timeout_s": 10, "cleanup_timeout_s": 1})
        try:
            image = np.zeros((1, 3, 256, 256), dtype="<f4")
            result = runtime.run([(7, image)], [7])[0]
            assert result.correct is True
            assert [name for name, _ in calls if name != "close"] == [
                "prefix", "network3-bridge", "suffix"]
            assert runtime.setup_identity["parameter_upload_receipts"][0]["upload_completed"]
            assert runtime.setup_timings_ms["parameter_upload_once"] >= 0
            assert runtime.thread_budget == {"prefix": 2,
                                             "network2_network4_bridge_worker": 1,
                                             "suffix": 1}
            assert runtime.runtime.pipeline.max_in_flight == 1
            assert runtime.runtime.pipeline.queue_capacity == 1
            assert runtime.setup_identity["activation_scale_bindings"][
                "network4_input"]["fixture_manifest_sha256"] == _FIXTURES[1]["manifest_sha256"]
        finally:
            runtime.close()
    assert len([item for item in calls if item[0] == "close"]) == 3
