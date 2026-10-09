import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from desktop_vlm.board import run_cnn_pipeline_v6_board_window as window


REPO = Path(__file__).resolve().parents[3]
ROUTE = (REPO / "artifacts/board-debug-20261005/acceleration/host/"
         "network-v6-route-fixtures-candidate-002/manifest.json")
PLAN = (REPO / "artifacts/board-debug-20261005/acceleration/network/"
        "network6-v6-board-window-plan-001/board-window-parameters.json")
HOST = (REPO / "artifacts/board-debug-20261005/acceleration/network/"
        "stage_network6_v6_window_001.py")


def _load_host():
    spec = importlib.util.spec_from_file_location("stage_network6_v6_window_001", HOST)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_exact_fixture_mapping_uses_real_p2_input_and_all_seven_outputs():
    manifest = json.loads(ROUTE.read_text(encoding="utf-8"))
    image = manifest["images"][0]
    paths = {}
    for profile in (2, 3, 4, 0, 5, 6, 1):
        source, expected = window._fixture_record(image, profile)
        paths[profile] = (source["path"], expected["path"])
    assert paths[2][0].endswith("stem-p2-input-hcw-i16le.bin")
    assert paths[2][1].endswith("stem-p2-output-hcw-i16le.bin")
    assert paths[3][0] == paths[2][1]
    assert paths[4][0] == paths[3][1]
    assert paths[0][0] == paths[4][1]
    assert paths[5][0] == paths[0][1]
    assert paths[6][0].endswith("se-gelu-p6-input-hcw-i16le.bin")
    assert paths[1][0] == paths[6][1]


def test_activation_extents_and_output_offsets_cover_frozen_descriptor_ranges():
    assert window._activation_extent(2, 4) == 1024 * 1024
    assert window._activation_extent(3, 1) == 1048576
    assert window._activation_extent(4, 1) == 786432
    assert window._activation_extent(5, 1) == 524288
    assert window._activation_extent(6, 1) == 262144
    assert window._output_offset(3, 1) == 32768 * 16
    assert window._output_offset(4, 1) == 16384 * 16
    assert window._output_offset(5, 1) == 16384 * 16
    assert window._output_offset(6, 1) == 8192 * 16


def test_plan_has_non_circular_offline_and_online_release_layers():
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    gates = plan["hardware_release_gates"]
    assert "all_must_be_present_before_any_board_transition" not in gates
    offline = gates["gate_layers"]["offline_pre_board_transition"]
    online = gates["gate_layers"]["online_pre_driver_bind_and_compute"]
    assert "jtag_deployment_receipt" not in offline["required"]
    assert "pl_clock_hz" not in offline["required"]
    assert "jtag_deployment_receipt" in online["required"]
    assert "pl_clock_hz" in online["required"]
    assert offline["complete"] is False and online["complete"] is False


def test_host_stage_fails_closed_until_offline_gate_is_complete():
    host = _load_host()
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    try:
        host.require_offline_gate(plan)
    except RuntimeError as error:
        assert "offline pre-board release gate is incomplete" in str(error)
    else:
        raise AssertionError("incomplete offline release gate was accepted")


def test_group_commands_bind_terminal_group_inputs_without_contacting_board():
    host = _load_host()
    exact = host._remote_group_command("exact", "/tmp/exact")
    concurrency = host._remote_group_command(
        "concurrency", "/tmp/concurrency", "NETWORK6_V6_ILA_ARMED")
    benchmark = host._remote_group_command(
        "serial4", "/tmp/serial", deployment_sha="a" * 64,
        design_sha="b" * 64)
    assert "seven-profile-exact" in exact
    assert "normal-fallback" not in exact
    assert "driver-concurrency" in concurrency
    assert "NETWORK6_V6_ILA_ARMED" in concurrency
    assert "benchmark --device" in benchmark
    assert "--benchmark-mode serial4" in benchmark
    assert "--expected-deployment-receipt-sha256 " + "a" * 64 in benchmark
    assert "--expected-design-sha256 " + "b" * 64 in benchmark


def test_frozen_manifest_hash_constants_are_real_file_hashes():
    assert hashlib.sha256(ROUTE.read_bytes()).hexdigest() == window.ROUTE_MANIFEST_SHA256
    golden = (REPO / "artifacts/board-debug-20261005/acceleration/host/"
              "network-w16-same-board-golden-001/manifest.json")
    assert hashlib.sha256(golden.read_bytes()).hexdigest() == window.SAME_BOARD_GOLDEN_MANIFEST_SHA256


def test_physical_onnx_output_is_mapped_to_scheduler_boundary_name():
    class Client(object):
        header = {"threads": 1}

        def infer(self, unused):
            return {"onnx/full/output/name": "tensor"}, 1.25

        def close(self):
            return "closed"

    wrapped = window._LogicalOutputClient(
        Client(), "onnx/full/output/name", "n0_input")
    outputs, elapsed = wrapped.infer(["input"])
    assert outputs == {"n0_input": "tensor"}
    assert elapsed == 1.25
    assert wrapped.close() == "closed"


def test_deployment_gate_binds_release_design_and_same_boot_clock_evidence():
    host = _load_host()
    value = {
        "abi": "FZV6", "pl_execution": True,
        "boot_id": host.BOOT_ID, "pl_clock_hz": 101375992,
        "pl_clock_source": "same-boot preserved PS FCLK0 pl0_ref",
        "design_sha256": "b" * 64,
        "programmed_payload": {"format": "bit", "path": "release/final.bit",
                               "bytes": 123456, "sha256": "b" * 64},
        "program_command_no_ps_reset": True,
        "program_receipt_sha256": "d" * 64,
        "release_receipt_sha256": "e" * 64,
        "clock_evidence": {"same_boot_preserved": True, "sha256": "c" * 64},
    }
    raw = (json.dumps(value) + "\n").encode("utf-8")
    with tempfile.TemporaryDirectory() as temporary:
        path = Path(temporary) / "deployment.json"
        path.write_bytes(raw)
        unused, parsed = host.deployment(path, hashlib.sha256(raw).hexdigest(), "b" * 64)
        assert parsed["design_sha256"] == "b" * 64
        try:
            host.deployment(path, hashlib.sha256(raw).hexdigest(), "d" * 64)
        except ValueError as error:
            assert "identity/clock" in str(error)
        else:
            raise AssertionError("mismatched programmed design SHA was accepted")


def test_failure_receipt_keeps_commands_and_usb_source_is_uuid_resolved():
    host = _load_host()
    with tempfile.TemporaryDirectory() as temporary:
        out = Path(temporary) / "failure"
        receipt = {"commands": [{"name": "preflight", "exit_code": 1}]}
        host.retain_failure(out, receipt, RuntimeError("intentional test failure"))
        saved = json.loads((out / "failure-receipt.json").read_text(encoding="utf-8"))
        assert saved["commands"][0]["name"] == "preflight"
        assert saved["result"] == "FAILED_PRESERVE_STATE"
        host.write_host_receipt(out, {"result": "RETRY_SUCCEEDED"})
        success = json.loads((out / "receipt.json").read_text(encoding="utf-8"))
        assert success["result"] == "RETRY_SUCCEEDED"
    source = HOST.read_text(encoding="utf-8")
    assert "/dev/sda1" not in source
    assert "readlink -f /dev/disk/by-uuid/3021-253C" in source
    assert '"prepare-pl"' in source


def test_local_restore_validation_failure_is_retained_without_opening_ssh():
    host = _load_host()
    with tempfile.TemporaryDirectory() as temporary:
        temporary = Path(temporary)
        host.BASE = temporary
        bad = temporary / "bad-jtag-receipt.json"
        bad.write_text("{}\n", encoding="utf-8")
        args = type("Args", (), {
            "jtag_factory_receipt": str(bad),
            "expected_jtag_factory_receipt_sha256": hashlib.sha256(bad.read_bytes()).hexdigest(),
        })()
        try:
            host.action_restore_factory(args)
        except ValueError as error:
            assert "exact factory PL restoration" in str(error)
        else:
            raise AssertionError("invalid JTAG factory receipt was accepted")
        failure = temporary / "factory-software-restored-001/failure-receipt.json"
        saved = json.loads(failure.read_text(encoding="utf-8"))
        assert saved["result"] == "FAILED_PRESERVE_STATE"
        assert saved["commands"] == []


def test_remote_group_failure_downloads_incomplete_result_and_keeps_commands():
    host = _load_host()

    class FailedSession(object):
        def __init__(self):
            self.commands = []

        def run(self, name, unused_command, timeout=None):
            self.commands.append({"name": name, "exit_code": 0 if name.endswith("preflight") else 17})
            if name.endswith("execute"):
                raise RuntimeError("simulated remote runner failure")
            return {"stdout": "", "stderr": "", "exit_code": 0}

        def download_tree_if_exists(self, unused_remote, local):
            local.mkdir(parents=True, exist_ok=True)
            (local / "incomplete.json").write_text(
                '{"status":"SIMULATED_INCOMPLETE"}\n', encoding="utf-8")
            return True

        def close(self):
            pass

    with tempfile.TemporaryDirectory() as temporary:
        temporary = Path(temporary)
        host.BASE = temporary
        host.Session = FailedSession
        args = type("Args", (), {
            "group": "exact", "jtag_armed_token": None,
            "attempt": 1,
            "expected_deployment_receipt_sha256": None,
        })()
        try:
            host.action_run(args)
        except RuntimeError as error:
            assert "simulated remote runner failure" in str(error)
        else:
            raise AssertionError("simulated remote failure was accepted")
        out = temporary / "exact-001"
        assert json.loads((out / "incomplete.json").read_text(encoding="utf-8"))["status"] == "SIMULATED_INCOMPLETE"
        failure = json.loads((out / "failure-receipt.json").read_text(encoding="utf-8"))
        assert failure["remote_failure_result_downloaded"] is True
        assert [item["name"] for item in failure["commands"]] == [
            "v6-exact-preflight", "v6-exact-execute"]


def test_attempt_is_positive_and_names_immutable_evidence_directory():
    host = _load_host()
    assert host.positive_attempt("2") == 2
    for invalid in ("0", "-1", "not-an-integer"):
        try:
            host.positive_attempt(invalid)
        except Exception as error:
            assert "positive integer" in str(error)
        else:
            raise AssertionError("invalid attempt was accepted: " + invalid)
    source = HOST.read_text(encoding="utf-8")
    assert 'suffix = "%s-%03d" % (group, attempt)' in source
    assert 'test ! -e " + remote_output' in source
