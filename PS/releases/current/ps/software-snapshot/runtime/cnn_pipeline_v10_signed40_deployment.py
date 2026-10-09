"""Strict offline loader for the A0005 signed40 dual-clock deployment.

The loader validates immutable local bytes only.  It never opens the device,
loads a module, applies an overlay, changes PL clocks, or programs a bitstream.
"""
from __future__ import print_function

import json
import pathlib

from cnn_pipeline_v10_deployment import KERNEL_RELEASE, _checked_sha, _record, _sha
from cnn_pipeline_v10_signed40_parameters import CHAIN_CONTRACT


SCHEMA = "cnn-pipeline-v10.5-signed40-deployment-v1"
FINAL_PLATFORM_SCHEMA = "cnn-v10.5-signed40-full-platform-v1"
IDENTITY = {"core_id": "0x465A5641", "core_abi": "0x000A0005",
            "guard_caps": "0x00000FFF", "software_uapi": 10}
TARGET = {"kernel_release": KERNEL_RELEASE,
          "device": "/dev/network10_v10_signed40",
          "module": "cnn_ddr_v10_signed40_candidate"}
COMBINED_SHA256 = \
    "4a32c9373e783ac572a5d3374b316181a4d52ae9a92ec45f8b13d763ef028690"
ADMISSION_SHA256 = \
    "cfa5f1a3a29aa04f11a83a7e3b23637be063e22e5627ca66b4c20c62745443dd"
PROOF_SHA256 = \
    "9f3de6ffb18a9d1de54addbcc471f95f18c47acf86f31e051794d59e528b2676"
SOURCE_MANIFEST_SHA256 = \
    "f8714065c490506f5e08b1738c8fe121270db2c66da9eb42d9674907102e0593"
CANDIDATE_CONTRACT_SHA256 = \
    "a65bdd2c50a5f1b5329350e22a67d9fb9ff4731c3517454ae524f667c5dc3f4d"
DRIVER_SHA256 = \
    "7a273d19ccc20c6d19c7f64bd6c07fc0067ad600dedf70c6bd111441b85e57f5"
DRIVER_COMPILE_RECEIPT_SHA256 = \
    "1e85e3d07b50a5116c4b8deef77317cdf6bd84144c55c039b25645fa5c3a2770"

DEBUG_PROFILE = {
    "mode": "release-no-ila", "guard_ila_count": 0,
    "pipeline_ila_count": 0, "debug_hub_count": 0,
    "trace_pack_present": False, "hls_ap_none_trace_port_count": 12,
    "platform_trace_mmio_register_count": 0,
    "trace_outputs_connected": False, "trace_output_transport": "ap_none",
    "mmio_trace_count": 0, "ltx_required": False,
}
CLOCK_CONTRACT = {
    "master": {"name": "clk_pl_1", "nominal_hz": 100000000,
               "implemented_exact_hz": 99999999,
               "runtime_hz": 99999999, "period_ns": 10.0},
    "domains": {
        "driver_job": {
            "generated_clock": "half2x_clock_tree_driver_job_clk_200",
            "nominal_hz": 200000000,
            "implemented_exact_hz": 199999998,
            "runtime_hz": 199999998,
            "period_ns": 5.0},
        "pw_local": {"generated_clock": "clock_wiz_clk_out1",
                     "nominal_hz": 400000000,
                     "implemented_exact_hz": 399999996,
                     "runtime_hz": 399999996, "period_ns": 2.5},
    },
    "relationship": {"same_mmcm": True, "integer_ratio": 2,
                     "phase_aligned": True},
    "topology": {
        "kind": "mmcm_fast_plus_bufgce_div_v1",
        "mmcm": {"divclk_divide": 1, "clkfbout_mult_f": 12.0,
                 "clkout_fast_divide_f": 3.0},
        "bufgce_div": {"driver_job_divide": 2, "pw_local_divide": 1},
    },
}
PATH_GROUPS = ("slow_to_slow", "fast_to_fast", "slow_to_fast", "fast_to_slow")
REQUIRED_FILES = {
    "bitstream", "configuration_bin", "dtbo", "full_platform_receipt",
    "address_map_receipt", "timing_receipt", "guard_validation_receipt",
    "driver_module", "driver_compile_receipt", "module_symvers",
    "factory_bitstream", "factory_driver", "chain_parameter_manifest",
    "signed40_admission", "signed40_range_proof",
    "candidate_source_manifest", "candidate_contract",
}
REQUIRED_GATES = {
    "all_rtl_profiles_pass", "rtl_stress_pass", "full_platform_route_pass",
    "all_clock_domains_setup_met", "all_clock_domains_hold_met",
    "pulse_width_met", "cdc_pass", "guard_six_master_pass",
    "target_module_compile_pass", "restore_assets_verified",
    "pw2_signed40_range_proof_pass", "pw2_signed40_runtime_admission_pass",
    "whole_top_native_exact_pass", "dual_clock_rtl_exact_pass",
}
KNOWN_FILE_SHA = {
    "chain_parameter_manifest": COMBINED_SHA256,
    "signed40_admission": ADMISSION_SHA256,
    "signed40_range_proof": PROOF_SHA256,
    "candidate_source_manifest": SOURCE_MANIFEST_SHA256,
    "candidate_contract": CANDIDATE_CONTRACT_SHA256,
    "driver_module": DRIVER_SHA256,
    "driver_compile_receipt": DRIVER_COMPILE_RECEIPT_SHA256,
}


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      allow_nan=False)


def _nonnegative_number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        raise ValueError("A0005 %s did not pass" % label)


def _validate_timing(timing):
    if not isinstance(timing, dict):
        raise ValueError("A0005 timing evidence is missing")
    for name in ("setup_wns_ns", "hold_whs_ns",
                 "pulse_width_min_slack_ns"):
        _nonnegative_number(timing.get(name), name)
    for name in ("route_errors", "drc_violations",
                 "check_timing_violations", "cdc_violations"):
        value = timing.get(name)
        if isinstance(value, bool) or not isinstance(value, int) or value != 0:
            raise ValueError("A0005 timing %s is nonzero" % name)
    groups = timing.get("path_groups")
    if not isinstance(groups, dict) or set(groups) != set(PATH_GROUPS):
        raise ValueError("A0005 cross-domain path group evidence is incomplete")
    for name in PATH_GROUPS:
        value = groups[name]
        if not isinstance(value, dict):
            raise ValueError("A0005 path group %s is invalid" % name)
        _nonnegative_number(value.get("setup_wns_ns"), name + " setup")
        _nonnegative_number(value.get("hold_whs_ns"), name + " hold")
    return timing


def _read_json(path, label):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise ValueError("A0005 %s is not valid JSON" % label)
    if not isinstance(value, dict):
        raise ValueError("A0005 %s is not a JSON object" % label)
    return value


def _validate_platform(receipt, manifest):
    if (receipt.get("schema") != FINAL_PLATFORM_SCHEMA or
            receipt.get("pass") is not True or receipt.get("status") != "PASS"):
        raise ValueError("A0005 final platform receipt is not PASS")
    if receipt.get("identity") != dict(
            IDENTITY,
            combined_parameter_manifest_sha256=COMBINED_SHA256,
            candidate_source_manifest_sha256=SOURCE_MANIFEST_SHA256,
            candidate_contract_sha256=CANDIDATE_CONTRACT_SHA256):
        raise ValueError("A0005 final platform identity mismatch")
    if _canonical(receipt.get("clock")) != _canonical(CLOCK_CONTRACT):
        raise ValueError("A0005 final platform clock contract mismatch")
    if _canonical(receipt.get("debug_profile")) != _canonical(DEBUG_PROFILE):
        raise ValueError("A0005 final platform debug profile mismatch")
    address = receipt.get("address_map")
    if (not isinstance(address, dict) or
            address.get("hls_control") !=
            {"base": "0xa4000000", "size": "0x00010000"} or
            address.get("guard_identity") !=
            {"base": "0xa4010000", "size": "0x00010000"}):
        raise ValueError("A0005 final platform address map mismatch")
    _validate_timing(receipt.get("timing"))
    artifacts = receipt.get("artifacts")
    if not isinstance(artifacts, dict) or set(artifacts) != {
            "bitstream", "bin", "final_dcp"}:
        raise ValueError("A0005 no-ILA artifact inventory mismatch")
    if (manifest["files"]["bitstream"]["sha256"] !=
            artifacts["bitstream"].get("sha256") or
            manifest["files"]["configuration_bin"]["sha256"] !=
            artifacts["bin"].get("sha256")):
        raise ValueError("A0005 bitstream is not from the final platform")


def load_v10_signed40_deployment(manifest_path, expected_manifest_sha256,
                                 expected_release_manifest_sha256,
                                 expected_combined_manifest_sha256):
    expected_release = _checked_sha(expected_release_manifest_sha256,
                                    "base release manifest")
    if (_checked_sha(expected_combined_manifest_sha256,
                         "combined parameter manifest") != COMBINED_SHA256):
        raise ValueError("A0005 trusted parameter identity mismatch")
    path = pathlib.Path(manifest_path).resolve()
    raw = path.read_bytes()
    if _sha(raw) != _checked_sha(expected_manifest_sha256,
                                 "deployment manifest"):
        raise ValueError("A0005 deployment manifest SHA mismatch")
    manifest = json.loads(raw.decode("utf-8"))
    if (manifest.get("schema") != SCHEMA or
            manifest.get("status") != "READY_FOR_BOARD_VALIDATION" or
            manifest.get("identity") != IDENTITY or
            manifest.get("target") != TARGET or
            manifest.get("base_release_manifest_sha256") != expected_release or
            manifest.get("chain_contract") != CHAIN_CONTRACT or
            manifest.get("combined_parameter_manifest_sha256") != COMBINED_SHA256 or
            manifest.get("candidate_source_manifest_sha256") !=
            SOURCE_MANIFEST_SHA256 or
            manifest.get("candidate_contract_sha256") !=
            CANDIDATE_CONTRACT_SHA256 or
            _canonical(manifest.get("clock")) != _canonical(CLOCK_CONTRACT) or
            _canonical(manifest.get("debug_profile")) !=
            _canonical(DEBUG_PROFILE)):
        raise ValueError("A0005 deployment identity or contract mismatch")
    gates = manifest.get("gates")
    if (not isinstance(gates, dict) or set(gates) != REQUIRED_GATES or
            any(gates[name] is not True for name in REQUIRED_GATES)):
        raise ValueError("A0005 deployment gates are incomplete")
    files = manifest.get("files")
    if not isinstance(files, dict) or set(files) != REQUIRED_FILES:
        raise ValueError("A0005 deployment artifact set is incomplete")
    root = path.parent
    resolved = {name: _record(root, files[name], name)
                for name in sorted(REQUIRED_FILES)}
    for name, expected in KNOWN_FILE_SHA.items():
        if files[name]["sha256"] != expected:
            raise ValueError("A0005 %s identity mismatch" % name)
    if (resolved["bitstream"].suffix.lower() != ".bit" or
            resolved["configuration_bin"].suffix.lower() != ".bin" or
            resolved["dtbo"].suffix.lower() != ".dtbo" or
            resolved["driver_module"].suffix.lower() != ".ko" or
            "ltx" in files):
        raise ValueError("A0005 deployment artifact extension mismatch")
    platform = _read_json(resolved["full_platform_receipt"],
                          "full-platform receipt")
    _validate_platform(platform, manifest)
    admission = _read_json(resolved["signed40_admission"], "admission")
    if (admission.get("pass") is not True or
            admission.get("contract", {}).get(
                "required_combined_manifest_sha256") != COMBINED_SHA256 or
            admission.get("contract", {}).get("required_core_abi") != 0x000A0005 or
            admission.get("contract", {}).get("required_guard_caps") != 0xFFF):
        raise ValueError("A0005 signed40 admission mismatch")
    return {"manifest": manifest, "manifest_sha256": _sha(raw),
            "clock_hz": CLOCK_CONTRACT["domains"]["driver_job"]["runtime_hz"],
            "pw_local_clock_hz":
                CLOCK_CONTRACT["domains"]["pw_local"]["runtime_hz"],
            "chain_manifest_sha256": COMBINED_SHA256,
            "chain_contract": CHAIN_CONTRACT, "debug_profile": DEBUG_PROFILE,
            "native_ila_capture_applicable": False, "files": resolved}


__all__ = ["CLOCK_CONTRACT", "COMBINED_SHA256", "DEBUG_PROFILE", "IDENTITY",
           "SCHEMA", "TARGET", "load_v10_signed40_deployment"]
