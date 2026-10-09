#!/usr/bin/env python3
"""Build an immutable A0004 deployment package from final approved inputs.

The pending template is deliberately rejected.  This script copies and hashes
local artifacts only; it performs no SSH, JTAG, overlay, module, or device
operation.  Debug instrumentation is taken from, and must exactly match, the
final full-platform receipt instead of being hard-coded by this builder.
"""
from __future__ import print_function

import argparse
import datetime
import json
import pathlib
import shutil
import sys
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


REPO = pathlib.Path(__file__).resolve().parents[3]
BOARD = REPO / "desktop_vlm" / "board"
sys.path.insert(0, str(BOARD))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from cnn_pipeline_v10_deployment import (  # noqa: E402
    CLOCK_IDENTITY_BASIS, REQUIRED_FILES)
from cnn_pipeline_v10_p3_dma_deployment import (  # noqa: E402
    CHAIN_CONTRACT, CHAIN_MANIFEST_SHA256, EXTRA_FILES, EXTRA_GATES,
    IDENTITY, SCHEMA, TARGET, _validated_debug_profile,
    load_v10_p3_dma_deployment)
from build_cnn_v10_p3_deployment import (  # noqa: E402
    _canonical, _checked_sha, _copy_record, _repo_source, _sha)


INPUT_SCHEMA = "cnn-pipeline-v10.4-p3-dma-deployment-builder-input-v1"
INPUT_READY = "FINAL_INPUTS_APPROVED"
RELEASE_SHA = "3f52238b2a35d23f6f07c4cc9263ff8d4330c5aa27a6ed91640c4a45a8d45a2d"
KNOWN_FILE_SHA = {
    "chain_parameter_manifest": CHAIN_MANIFEST_SHA256,
    "driver_module": "03f2e2d6cc691e9f9cf438c932d650ba4334ff0ba63f098e66d79477c4f1a6bf",
    "driver_compile_receipt": "10ff675dcbddd2d906bd40c2fad4cbb6b04bc623f0c10f35ba0d462c23b3a563",
    "module_symvers": "ed188d47135d6224f954bd018aff9b7da988650c8a08c61abed3235cc3168326",
    "dma_provider_compatibility_receipt":
        "6258c0b48cb26cc88527feb1ef735f8a2b60281c5dc4eec13ae9d63833753220",
    "factory_bitstream": "59e1a6176194eccc05603738ba3c2e71ea25c3c09cdf9dce47ed1ad1ddf5fc2e",
    "factory_driver": "a482b11d47a117e60f98efd43631b45a3a33ba98e81ff610204d2f301dbb0b6f",
}
REQUIRED_GATES = {
    "all_rtl_profiles_pass", "rtl_stress_pass", "full_platform_route_pass",
    "internal_setup_met", "internal_hold_met", "guard_six_master_pass",
    "target_module_compile_pass", "restore_assets_verified",
} | set(EXTRA_GATES)
REQUIRED_PACKAGE_FILES_WITH_ILA = set(REQUIRED_FILES) | set(EXTRA_FILES)
FULL_PLATFORM_SCHEMA = "cnn-v10.4-full-platform-v1-metadata-corrected"
ADDRESS_RECEIPT_SCHEMA = "cnn-v10.4-a0004-address-map-v1"
TIMING_RECEIPT_SCHEMA = "cnn-v10.4-a0004-timing-v1"
EXPECTED_ADDRESS_MAP = {
    "hls_control": {"base": "0xa4000000", "size": "0x00010000"},
    "guard_identity": {"base": "0xa4010000", "size": "0x00010000"},
}
EXPECTED_PLATFORM_IDENTITY = {
    "core_id": "0x465A5641",
    "core_abi": "0x000A0004",
    "guard_caps": "0x000007FF",
    "combined_parameter_manifest_sha256": CHAIN_MANIFEST_SHA256,
}


def _read_json_record(record, label):
    expected = _checked_sha(record.get("sha256"), label + " SHA")
    source = _repo_source(record.get("source_path"), label)
    raw = source.read_bytes()
    if _sha(raw) != expected:
        raise ValueError("%s source SHA mismatch" % label)
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise ValueError("%s is not valid JSON" % label)
    if not isinstance(value, dict):
        raise ValueError("%s is not a JSON object" % label)
    return value


def _artifact_sha(record, label):
    if (not isinstance(record, dict) or
            isinstance(record.get("bytes"), bool) or
            not isinstance(record.get("bytes"), int) or
            record.get("bytes") <= 0 or
            not isinstance(record.get("path"), str) or
            not record.get("path")):
        raise ValueError("final platform %s artifact is incomplete" % label)
    return _checked_sha(record.get("sha256"), "final platform %s" % label)


def _validate_final_platform_receipt(record):
    receipt = _read_json_record(record, "full-platform receipt")
    if (receipt.get("schema") != FULL_PLATFORM_SCHEMA or
            receipt.get("pass") is not True or receipt.get("status") != "PASS"):
        raise ValueError("final full-platform receipt is not PASS")
    if _canonical(receipt.get("identity")) != _canonical(EXPECTED_PLATFORM_IDENTITY):
        raise ValueError("final full-platform identity mismatch")
    address = receipt.get("address_map")
    if not isinstance(address, dict):
        raise ValueError("final full-platform address map is missing")
    for name, expected in EXPECTED_ADDRESS_MAP.items():
        if address.get(name) != expected:
            raise ValueError("final full-platform %s window mismatch" % name)
    for name in ("report_sha256", "interface_widths_sha256",
                 "abi_wiring_sha256", "exact_bd_tcl_sha256"):
        _checked_sha(address.get(name), "final address %s" % name)
    clock = receipt.get("clock")
    if not isinstance(clock, dict):
        raise ValueError("final full-platform clock is missing")
    try:
        exact_hz = Decimal(str(clock.get("kernel_hz")))
        declared_exact_hz = Decimal(clock.get("implemented_exact_hz"))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("final full-platform exact clock is invalid")
    if (not exact_hz.is_finite() or exact_hz <= 0 or
            exact_hz != declared_exact_hz):
        raise ValueError("final full-platform exact clock mismatch")
    mmcm = clock.get("mmcm")
    if (not isinstance(mmcm, dict) or
            set(mmcm) != {"divclk_divide", "clkfbout_mult_f",
                          "clkout0_divide_f"} or
            not isinstance(clock.get("master_clock"), str) or
            not clock.get("master_clock") or
            not isinstance(clock.get("generated_clock"), str) or
            not clock.get("generated_clock")):
        raise ValueError("final full-platform clock identity is incomplete")
    timing = receipt.get("timing")
    if not isinstance(timing, dict):
        raise ValueError("final full-platform timing is missing")
    for name in ("setup_wns_ns", "hold_whs_ns", "pulse_width_min_slack_ns"):
        value = timing.get(name)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
            raise ValueError("final timing %s did not pass" % name)
    for name in ("route_errors", "drc_violations", "check_timing_violations"):
        value = timing.get(name)
        if isinstance(value, bool) or not isinstance(value, int) or value != 0:
            raise ValueError("final timing %s is nonzero" % name)
    profile = _validated_debug_profile(receipt.get("debug_profile"))
    artifacts = receipt.get("artifacts")
    if not isinstance(artifacts, dict):
        raise ValueError("final full-platform artifacts are missing")
    expected_artifacts = {"bitstream", "bin", "final_dcp"}
    if profile["ltx_required"]:
        expected_artifacts.add("ltx")
    if set(artifacts) != expected_artifacts:
        raise ValueError("final full-platform debug artifact inventory mismatch")
    for name in sorted(expected_artifacts):
        _artifact_sha(artifacts.get(name), name)
    return receipt


def _validate_derived_receipts(sources, full_record, full_receipt):
    full_sha = _checked_sha(full_record.get("sha256"), "full-platform receipt SHA")
    address = _read_json_record(sources["address_map_receipt"],
                                "address-map receipt")
    if (address.get("schema") != ADDRESS_RECEIPT_SCHEMA or
            address.get("pass") is not True or
            address.get("full_platform_receipt_sha256") != full_sha or
            _canonical(address.get("address_map")) !=
            _canonical(full_receipt["address_map"])):
        raise ValueError("derived address-map receipt mismatch")
    timing = _read_json_record(sources["timing_receipt"], "timing receipt")
    if (timing.get("schema") != TIMING_RECEIPT_SCHEMA or
            timing.get("pass") is not True or
            timing.get("full_platform_receipt_sha256") != full_sha or
            _canonical(timing.get("timing")) !=
            _canonical(full_receipt["timing"]) or
            _canonical(timing.get("clock")) !=
            _canonical(full_receipt["clock"])):
        raise ValueError("derived timing receipt mismatch")


def _validate_debug_profile_binding(spec_profile, full_platform_record):
    expected = _validated_debug_profile(spec_profile)
    receipt = _validate_final_platform_receipt(full_platform_record)
    actual = receipt.get("debug_profile")
    if _canonical(actual) != _canonical(expected):
        raise ValueError("final build receipt debug profile mismatch")
    return expected


def _validate_final_artifact_binding(sources, full_receipt, debug_profile):
    profile = _validated_debug_profile(debug_profile)
    if (sources["bitstream"].get("sha256") !=
            full_receipt["artifacts"]["bitstream"]["sha256"]):
        raise ValueError("deployment bitstream is not from final build")
    if profile["ltx_required"]:
        if ("ltx" not in sources or "ltx" not in full_receipt["artifacts"] or
                sources["ltx"].get("sha256") !=
                full_receipt["artifacts"]["ltx"]["sha256"]):
            raise ValueError("deployment LTX is not from final build")
    elif "ltx" in sources or "ltx" in full_receipt["artifacts"]:
        raise ValueError("no-ILA deployment must not contain LTX")


def build(spec_path, output_path):
    spec_path = pathlib.Path(spec_path).resolve()
    output = pathlib.Path(output_path).resolve()
    spec_raw = spec_path.read_bytes()
    spec = json.loads(spec_raw.decode("utf-8"))
    if spec.get("schema") != INPUT_SCHEMA or spec.get("status") != INPUT_READY:
        raise ValueError("deployment input spec is pending or has the wrong schema")
    if (spec.get("release_manifest_sha256") != RELEASE_SHA or
            spec.get("identity") != IDENTITY or spec.get("target") != TARGET or
            _canonical(spec.get("chain_contract")) != _canonical(CHAIN_CONTRACT)):
        raise ValueError("A0004 deployment identity or chain contract mismatch")
    gates = spec.get("gates")
    if (not isinstance(gates, dict) or set(gates) != REQUIRED_GATES or
            any(gates[name] is not True for name in REQUIRED_GATES)):
        raise ValueError("deployment gates are incomplete")
    debug_profile = _validated_debug_profile(spec.get("debug_profile"))
    required_package_files = set(REQUIRED_PACKAGE_FILES_WITH_ILA)
    if not debug_profile["ltx_required"]:
        required_package_files.remove("ltx")
    sources = spec.get("files")
    if not isinstance(sources, dict) or set(sources) != required_package_files:
        raise ValueError("deployment file inputs are incomplete")
    for name, expected in KNOWN_FILE_SHA.items():
        if sources[name].get("sha256") != expected:
            raise ValueError("%s is not the frozen artifact" % name)
    full_receipt = _validate_final_platform_receipt(
        sources["full_platform_receipt"])
    _validate_debug_profile_binding(debug_profile,
                                    sources["full_platform_receipt"])
    _validate_derived_receipts(sources, sources["full_platform_receipt"],
                               full_receipt)
    _validate_final_artifact_binding(sources, full_receipt, debug_profile)
    clock = spec.get("clock")
    if (not isinstance(clock, dict) or
            clock.get("domain") != "single-domain kernel/AXI" or
            isinstance(clock.get("kernel_hz"), bool) or
            not isinstance(clock.get("kernel_hz"), int) or
            clock.get("kernel_hz") <= 0 or
            not isinstance(clock.get("identity"), dict) or
            clock["identity"].get("basis") != CLOCK_IDENTITY_BASIS):
        raise ValueError("final clock identity is incomplete")
    try:
        spec_exact_hz = Decimal(clock.get("implemented_exact_hz"))
        receipt_exact_hz = Decimal(str(full_receipt["clock"]["kernel_hz"]))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("deployment exact clock identity is invalid")
    rounded_hz = int(receipt_exact_hz.to_integral_value(rounding=ROUND_HALF_UP))
    identity = clock["identity"]
    full_clock = full_receipt["clock"]
    if (spec_exact_hz != receipt_exact_hz or clock["kernel_hz"] != rounded_hz or
            identity.get("implemented_mmcm_m") !=
            full_clock["mmcm"]["clkfbout_mult_f"] or
            identity.get("implemented_mmcm_d") !=
            full_clock["mmcm"]["divclk_divide"] or
            identity.get("implemented_mmcm_o0") !=
            full_clock["mmcm"]["clkout0_divide_f"] or
            identity.get("master_clock") != full_clock["master_clock"] or
            identity.get("generated_clock") != full_clock["generated_clock"]):
        raise ValueError("deployment clock does not match final routed clock")
    provenance_inputs = spec.get("provenance")
    if not isinstance(provenance_inputs, dict) or not provenance_inputs:
        raise ValueError("final evidence provenance is missing")
    if output.exists():
        raise ValueError("refusing to overwrite deployment package")
    output.mkdir(parents=True)
    try:
        files = {name: _copy_record(output, sources[name], name)
                 for name in sorted(required_package_files)}
        provenance = {
            name: _copy_record(output, record, "provenance.%s" % name)
            for name, record in sorted(provenance_inputs.items())}
        identity = clock["identity"]
        if (identity.get("full_platform_receipt_sha256") !=
                files["full_platform_receipt"]["sha256"] or
                identity.get("timing_receipt_sha256") !=
                files["timing_receipt"]["sha256"]):
            raise ValueError("clock identity is not bound to final receipts")
        manifest = {
            "schema": SCHEMA, "status": "READY_FOR_BOARD_VALIDATION",
            "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "identity": IDENTITY, "release_manifest_sha256": RELEASE_SHA,
            "target": TARGET, "clock": clock, "gates": gates,
            "files": files, "chain_contract": CHAIN_CONTRACT,
            "debug_profile": debug_profile,
            "chain_parameter_manifest_sha256": CHAIN_MANIFEST_SHA256,
            "provenance": provenance,
            "transfer_backends": {
                "selected_for_main_validation": "direct_wc",
                "cached_dma_cap_expected": False,
                "cached_dma_blocker": "target provider lacks device_synchronize",
            },
            "scope": "READY authorizes staged A0004 validation; it is not a board result.",
        }
        raw = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
        manifest_path = output / "manifest.json"
        manifest_path.write_bytes(raw)
        digest = _sha(raw)
        loaded = load_v10_p3_dma_deployment(
            manifest_path, digest, RELEASE_SHA, CHAIN_MANIFEST_SHA256)
        if loaded["clock_hz"] != clock["kernel_hz"]:
            raise ValueError("post-build clock verification mismatch")
        receipt = {
            "schema": "cnn-pipeline-v10.4-p3-dma-deployment-package-receipt-v1",
            "pass": True,
            "input_spec": {"path": spec_path.relative_to(REPO).as_posix(),
                           "sha256": _sha(spec_raw)},
            "manifest": {"path": "manifest.json", "bytes": len(raw),
                         "sha256": digest},
            "required_file_count": len(files),
            "provenance_file_count": len(provenance),
            "debug_profile": debug_profile,
            "native_ila_capture_applicable": debug_profile["ltx_required"],
            "copy_policy": "independent copies; no hardlinks to mutable sources",
            "board_operations": False,
        }
        receipt_raw = (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode("utf-8")
        (output / "receipt.json").write_bytes(receipt_raw)
        return digest, _sha(receipt_raw)
    except Exception:
        shutil.rmtree(str(output))
        raise


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-spec", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)
    manifest_sha, receipt_sha = build(args.input_spec, args.output_dir)
    print(json.dumps({"manifest_sha256": manifest_sha,
                      "receipt_sha256": receipt_sha}, sort_keys=True))


if __name__ == "__main__":
    main()
