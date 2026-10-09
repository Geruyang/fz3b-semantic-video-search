#!/usr/bin/env python3
"""Run the controlled ABI10 WC-driver live qualification and write receipts.

The CLI opens only the caller-selected device. It never loads/unloads modules,
applies an overlay, or programs PL. Run only inside an already authorized
controlled board window after the offline and reserved-memory gates pass.
"""

import argparse
import errno
import hashlib
import json
import os
import pathlib
import re
import time

try:
    import cnn_ddr_v10_runtime as runtime
    from cnn_pipeline_v10_bundle import load_v10_release_bundle
    from cnn_pipeline_v10_wc_deployment import (
        LIVE_RECEIPT_SCHEMA, LIVE_RECEIPT_STATUS, LIVE_TRANSFER_GATES, TARGET,
        _current_boot_id)
except ImportError:
    from . import cnn_ddr_v10_runtime as runtime
    from .cnn_pipeline_v10_bundle import load_v10_release_bundle
    from .cnn_pipeline_v10_wc_deployment import (
        LIVE_RECEIPT_SCHEMA, LIVE_RECEIPT_STATUS, LIVE_TRANSFER_GATES, TARGET,
        _current_boot_id)


FIXTURE_SCHEMA = "cnn-v10.1-paired-fixtures-v1"
FIXTURE_STATUS = "HOST_ABI10_1_PAIRED_GOLDEN_NOT_PL"
FIXTURE_RECEIPT_SCHEMA = "cnn-v10.1-paired-fixture-build-receipt-v1"
FIXTURE_MANIFEST_SHA256 = "83df8803b7a8eb08795c6c19d89538637f850df9044c407b90814d725f0079c4"
PROFILE_ORDER = (2, 0, 1)
PROFILE_BLOCKS = {2: 4, 0: 12, 1: 20}
IMAGE_NAMES = ("image-00", "image-01")
CANARY_BYTES = 64 * 1024
CANARY_A = b"\xa5"
CANARY_B = b"\x5a"
FAILURE_STATUS = "FAIL_WC_LIVE_TRANSFER_AND_FUNCTIONAL_GATES"
DETAILS_SCHEMA = "cnn-pipeline-v10.1-wc-live-test-details-v1"


def _sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def _checked_sha(value, label):
    if (not isinstance(value, str) or len(value) != 64 or
            any(ch not in "0123456789abcdef" for ch in value)):
        raise ValueError("%s must be a lowercase SHA256" % label)
    return value


def _record_path(root, record, label, asset_root=None):
    if not isinstance(record, dict) or set(record) != {"path", "bytes", "sha256"}:
        raise ValueError("%s fixture record is malformed" % label)
    raw_path = record.get("path")
    if not isinstance(raw_path, str) or not raw_path:
        raise ValueError("%s fixture path is missing" % label)
    normalized = raw_path.replace("\\", "/")
    path = pathlib.Path(normalized)
    candidates = [path]
    if not path.is_absolute() and not re.match(r"^[A-Za-z]:/", normalized):
        if any(part in ("", ".", "..") for part in normalized.split("/")):
            raise ValueError("%s fixture path is unsafe" % label)
        candidates = [root / pathlib.PurePosixPath(normalized)]
    elif not path.exists():
        parts = normalized.split("/")
        if "artifacts" in parts:
            marker = parts.index("artifacts")
            base = (pathlib.Path(asset_root).resolve() if asset_root is not None else
                    pathlib.Path(__file__).resolve().parents[2])
            candidates.append(base.joinpath(*parts[marker:]))
    resolved = None
    for candidate in candidates:
        try:
            if candidate.is_file():
                resolved = candidate.resolve()
                break
        except OSError:
            continue
    if resolved is None:
        raise ValueError("%s fixture file is unavailable" % label)
    raw = resolved.read_bytes()
    if (isinstance(record.get("bytes"), bool) or record.get("bytes") != len(raw) or
            _checked_sha(record.get("sha256"), label + " SHA256") != _sha256(raw)):
        raise ValueError("%s fixture size/SHA mismatch" % label)
    return raw, resolved


def load_frozen_fixtures(fixture_root, expected_manifest_sha256, release,
                         asset_root=None):
    """Load the fixed paired fixture set and cross-check it against the bundle."""
    root = pathlib.Path(fixture_root).resolve()
    expected = _checked_sha(expected_manifest_sha256, "fixture manifest")
    if expected != FIXTURE_MANIFEST_SHA256:
        raise ValueError("fixture manifest is not the frozen V10.1 paired set")
    manifest_path = root / "manifest.json"
    raw = manifest_path.read_bytes()
    if _sha256(raw) != expected:
        raise ValueError("fixture manifest SHA mismatch")
    manifest = json.loads(raw.decode("utf-8"))
    if (manifest.get("schema") != FIXTURE_SCHEMA or
            manifest.get("status") != FIXTURE_STATUS or
            manifest.get("board_operations") is not False or
            manifest.get("identity") != {"core": "0x465A5641",
                                          "abi": "0x000A0001",
                                          "software": "sw10.1"}):
        raise ValueError("fixture manifest identity/status mismatch")

    receipt_path = root / "receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if (set(receipt) != {"schema", "pass", "manifest", "v9_sources_unchanged",
                         "profiles", "paired_images"} or
            receipt.get("schema") != FIXTURE_RECEIPT_SCHEMA or
            receipt.get("pass") is not True or
            receipt.get("v9_sources_unchanged") is not True or
            receipt.get("profiles") != list(PROFILE_ORDER) or
            receipt.get("paired_images") != list(IMAGE_NAMES)):
        raise ValueError("fixture build receipt is incomplete")
    receipt_manifest = receipt.get("manifest")
    if (not isinstance(receipt_manifest, dict) or
            receipt_manifest.get("bytes") != len(raw) or
            receipt_manifest.get("sha256") != expected):
        raise ValueError("fixture build receipt does not bind manifest")

    cases = manifest.get("cases")
    if not isinstance(cases, list) or len(cases) != len(PROFILE_ORDER):
        raise ValueError("paired fixture cases are incomplete")
    if tuple(item.get("profile") for item in cases) != PROFILE_ORDER:
        raise ValueError("paired fixture profile order changed")
    profiles = release.get("parameter_contract", {}).get("profiles", {})
    loaded_cases = []
    for case in cases:
        profile = case.get("profile")
        blocks = PROFILE_BLOCKS[profile]
        contract = runtime.profile_contract(profile, blocks)
        if (case.get("blocks") != blocks or case.get("flags") != 0 or
                case.get("params_words") != contract["params_bytes"] // 16 or
                case.get("slot_words") != contract["slot_bytes"] // 16 or
                case.get("arena_words") != contract["arena_bytes"] // 16):
            raise ValueError("profile %d frozen fixture contract mismatch" % profile)
        params, unused_path = _record_path(
            root, case.get("params"), "profile %d params" % profile, asset_root)
        release_profile = profiles.get(profile)
        if (not isinstance(release_profile, dict) or
                release_profile.get("params") != params or
                release_profile.get("params_sha256") != _sha256(params) or
                len(params) != contract["params_bytes"]):
            raise ValueError("profile %d params differ from V10 release bundle" % profile)
        images = case.get("images")
        if not isinstance(images, list) or len(images) != 2:
            raise ValueError("profile %d paired images are incomplete" % profile)
        loaded_images = []
        for index, image in enumerate(images):
            if image.get("sample") != IMAGE_NAMES[index]:
                raise ValueError("profile %d paired image order changed" % profile)
            input_bytes, unused_path = _record_path(
                root, image.get("input"), "profile %d input %d" % (profile, index),
                asset_root)
            expected_bytes, unused_path = _record_path(
                root, image.get("expected"), "profile %d expected %d" % (profile, index),
                asset_root)
            if (len(input_bytes) != contract["slot_bytes"] or
                    len(expected_bytes) != contract["slot_bytes"]):
                raise ValueError("profile %d fixture slot extent mismatch" % profile)
            loaded_images.append({"sample": IMAGE_NAMES[index],
                                  "input": input_bytes,
                                  "input_sha256": _sha256(input_bytes),
                                  "expected": expected_bytes,
                                  "expected_sha256": _sha256(expected_bytes)})
        if loaded_images[0]["input"] == loaded_images[1]["input"]:
            raise ValueError("profile %d fixture images must be distinct" % profile)
        loaded_cases.append({"profile": profile, "block_count": blocks,
                             "params": params, "params_sha256": _sha256(params),
                             "images": loaded_images})
    return {"manifest_sha256": _sha256(raw), "manifest": manifest,
            "cases": loaded_cases}


def _errno_from(error):
    return getattr(error, "errno", None)


def _bad_pointer_upload(transport, handle, offset, size):
    raw = bytearray(runtime.v6._TRANSFER_STRUCT.pack(
        handle, 0, offset, size, 1))
    transport._ioctl(runtime.v6.IOCTL_REQUESTS["UPLOAD"], raw)


def _run_case(transport, case, timeout_s):
    profile = case["profile"]
    block_count = case["block_count"]
    contract = runtime.profile_contract(profile, block_count)
    base = CANARY_BYTES
    allocation_bytes = contract["arena_bytes"] + 2 * CANARY_BYTES
    params_handle = transport.alloc(contract["params_bytes"])
    handle_a = transport.alloc(allocation_bytes, flags=transport.ALLOC_LOW_ONLY)
    handle_b = transport.alloc(allocation_bytes, flags=transport.ALLOC_HIGH_ONLY)
    if (transport.allocations[handle_a]["arena_index"] != 0 or
            transport.allocations[handle_b]["arena_index"] != 1):
        raise RuntimeError("driver did not honor low/high allocation placement")

    params = case["params"]
    transport.upload(params_handle, 0, params)
    params_readback = transport.download(params_handle, 0, len(params))
    params_exact = params_readback == params

    canary_a = CANARY_A * allocation_bytes
    canary_b = CANARY_B * allocation_bytes
    transport.upload(handle_a, 0, canary_a)
    transport.upload(handle_b, 0, canary_b)
    canaries_before = {
        "a_prefix": transport.download(handle_a, 0, base) == canary_a[:base],
        "a_suffix": transport.download(handle_a, base + contract["arena_bytes"],
                                         CANARY_BYTES) == canary_a[-CANARY_BYTES:],
        "b_prefix": transport.download(handle_b, 0, base) == canary_b[:base],
        "b_suffix": transport.download(handle_b, base + contract["arena_bytes"],
                                         CANARY_BYTES) == canary_b[-CANARY_BYTES:],
    }
    if not all(canaries_before.values()):
        raise RuntimeError("activation canary initialization mismatch")

    image_a, image_b = case["images"]
    error_probe = {"upload_errno": None, "download_errno": None,
                   "transfer_refs_zero_after_error": False,
                   "retry_exact": False}
    try:
        _bad_pointer_upload(transport, handle_a, base, contract["slot_bytes"])
    except OSError as error:
        error_probe["upload_errno"] = _errno_from(error)
        if error_probe["upload_errno"] != errno.EFAULT:
            raise RuntimeError("bad user_ptr returned errno %r, expected EFAULT" %
                               error_probe["upload_errno"])
    else:
        raise RuntimeError("bad user_ptr upload unexpectedly succeeded")
    try:
        transport.download(handle_a, base, contract["slot_bytes"])
    except OSError as error:
        error_probe["download_errno"] = _errno_from(error)
        if error_probe["download_errno"] != getattr(errno, "ENODATA", 61):
            raise RuntimeError("download after failed upload returned errno %r" %
                               error_probe["download_errno"])
        # ENODATA means the download entered the object transfer path and saw
        # the invalidated range; EBUSY from a leaked transfer ref would fail here.
        error_probe["transfer_refs_zero_after_error"] = True
    else:
        raise RuntimeError("failed upload range remained downloadable")

    transport.upload(handle_a, base, image_a["input"])
    transport.upload(handle_b, base, image_b["input"])
    retry = transport.download(handle_a, base, contract["slot_bytes"])
    error_probe["retry_exact"] = retry == image_a["input"]
    if not error_probe["retry_exact"]:
        raise RuntimeError("full upload retry did not restore exact input bytes")

    descriptor = transport.submit(
        profile, block_count, params_handle, handle_a, handle_b, base, base)
    completion = transport.wait_complete(profile, timeout_s)
    output_offset = base + contract["output_offset_bytes"]
    actual_a = transport.download(handle_a, output_offset, contract["slot_bytes"])
    actual_b = transport.download(handle_b, output_offset, contract["slot_bytes"])
    exact_a = actual_a == image_a["expected"]
    exact_b = actual_b == image_b["expected"]
    if not exact_a or not exact_b:
        raise RuntimeError("profile %d output differs from frozen paired fixtures" % profile)
    canaries_after = {
        "a_prefix": transport.download(handle_a, 0, base) == canary_a[:base],
        "a_suffix": transport.download(handle_a, base + contract["arena_bytes"],
                                         CANARY_BYTES) == canary_a[-CANARY_BYTES:],
        "b_prefix": transport.download(handle_b, 0, base) == canary_b[:base],
        "b_suffix": transport.download(handle_b, base + contract["arena_bytes"],
                                         CANARY_BYTES) == canary_b[-CANARY_BYTES:],
    }
    if not all(canaries_after.values()):
        raise RuntimeError("profile %d activation canary changed" % profile)
    return {
        "profile": profile, "block_count": block_count,
        "params_bytes": len(params), "params_sha256": _sha256(params),
        "params_readback_exact": params_exact,
        "activation_allocation_bytes": allocation_bytes,
        "activation_arena_bytes": contract["arena_bytes"],
        "activation_base_offset_bytes": base,
        "activation_a_arena_index": 0, "activation_b_arena_index": 1,
        "input_a_sha256": image_a["input_sha256"],
        "input_b_sha256": image_b["input_sha256"],
        "expected_a_sha256": image_a["expected_sha256"],
        "expected_b_sha256": image_b["expected_sha256"],
        "actual_a_sha256": _sha256(actual_a),
        "actual_b_sha256": _sha256(actual_b),
        "output_a_exact": exact_a, "output_b_exact": exact_b,
        "canaries_before": canaries_before,
        "canaries_after": canaries_after,
        "bad_user_pointer": error_probe,
        "submit_descriptor": descriptor,
        "completion": completion,
        "scratch_inspected": False,
    }


def run_qualification(transport, release, fixtures, timeout_s=300.0):
    """Execute all frozen paired cases and derive gate evidence from results."""
    if not isinstance(timeout_s, (int, float)) or timeout_s <= 0:
        raise ValueError("timeout_s must be positive")
    if [case["profile"] for case in fixtures["cases"]] != list(PROFILE_ORDER):
        raise ValueError("qualification cases must be ordered profile2/profile0/profile1")
    results = []
    for case in fixtures["cases"]:
        try:
            results.append(_run_case(transport, case, timeout_s))
        except Exception as error:
            error.qualification_case_results = results
            error.qualification_failed_profile = case.get("profile")
            raise
    all_exact = all(item["output_a_exact"] and item["output_b_exact"]
                    for item in results)
    canaries_exact = all(all(item["canaries_before"].values()) and
                         all(item["canaries_after"].values()) for item in results)
    copy_recovery = all(item["bad_user_pointer"]["upload_errno"] == errno.EFAULT and
                        item["bad_user_pointer"]["download_errno"] ==
                        getattr(errno, "ENODATA", 61) and
                        item["bad_user_pointer"]["transfer_refs_zero_after_error"] and
                        item["bad_user_pointer"]["retry_exact"] for item in results)
    params_exact = all(item["params_readback_exact"] for item in results)
    low_high = all(item["activation_a_arena_index"] == 0 and
                   item["activation_b_arena_index"] == 1 and
                   item["input_a_sha256"] != item["input_b_sha256"] and
                   item["output_a_exact"] and item["output_b_exact"]
                   for item in results)
    evidence = {
        LIVE_TRANSFER_GATES[0]: bool(low_high and canaries_exact),
        LIVE_TRANSFER_GATES[1]: bool(all_exact and canaries_exact),
        LIVE_TRANSFER_GATES[2]: bool(copy_recovery),
        LIVE_TRANSFER_GATES[3]: bool(params_exact and all_exact and
                                     [item["profile"] for item in results] ==
                                     list(PROFILE_ORDER)),
    }
    return {"case_results": results, "gate_evidence": evidence}


def _hash_file(path, expected, label):
    raw = pathlib.Path(path).read_bytes()
    actual = _sha256(raw)
    if actual != _checked_sha(expected, label + " expected SHA256"):
        raise ValueError("%s SHA mismatch" % label)
    return actual


def write_receipts(receipt_path, boot_id, module_sha, dtbo_sha,
                   evidence, details, error=None):
    """Write helper-compatible fixed receipt plus its detailed sidecar."""
    all_gates = dict((name, evidence.get(name) is True)
                     for name in LIVE_TRANSFER_GATES)
    if details.get("boot_id_end") != boot_id or details.get("transport_close_ok") is not True:
        all_gates[LIVE_TRANSFER_GATES[2]] = False
    passed = error is None and all(all_gates.values())
    receipt = {
        "schema": LIVE_RECEIPT_SCHEMA,
        "status": LIVE_RECEIPT_STATUS if passed else FAILURE_STATUS,
        "target": dict(TARGET), "boot_id": boot_id,
        "driver_module_sha256": module_sha, "dtbo_sha256": dtbo_sha,
        "completed_live_gates": all_gates,
    }
    details_record = {"schema": DETAILS_SCHEMA,
                      "status": "PASS" if passed else "FAIL",
                      "target": dict(TARGET), "boot_id_start": boot_id,
                      "completed_live_gates": dict(all_gates)}
    details_record.update(details)
    if error is not None:
        details_record["error"] = "%s: %s" % (type(error).__name__, error)
    output = pathlib.Path(receipt_path)
    detail_output = output.with_suffix(".details.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    for path, value in ((output, receipt), (detail_output, details_record)):
        with path.open("x", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2, sort_keys=True)
            stream.write("\n")
    return receipt, detail_output


def main(argv=None):
    parser = argparse.ArgumentParser(description="Qualify the isolated V10 WC driver")
    parser.add_argument("--bundle-root", required=True)
    parser.add_argument("--expected-bundle-sha256", required=True)
    parser.add_argument("--fixture-root", required=True)
    parser.add_argument("--expected-fixture-manifest-sha256", required=True)
    parser.add_argument("--asset-root")
    parser.add_argument("--driver-module", required=True)
    parser.add_argument("--expected-driver-module-sha256", required=True)
    parser.add_argument("--dtbo", required=True)
    parser.add_argument("--expected-dtbo-sha256", required=True)
    parser.add_argument("--device", default=TARGET["device"])
    parser.add_argument("--timeout-s", type=float, default=300.0)
    parser.add_argument("--output-receipt", required=True)
    args = parser.parse_args(argv)
    if args.device != TARGET["device"]:
        parser.error("--device must match the WC candidate target")
    if args.timeout_s <= 0:
        parser.error("--timeout-s must be positive")

    module_sha = _hash_file(args.driver_module,
                            args.expected_driver_module_sha256, "driver module")
    dtbo_sha = _hash_file(args.dtbo, args.expected_dtbo_sha256, "DTBO")
    release = load_v10_release_bundle(
        args.bundle_root, args.expected_bundle_sha256)
    if release["manifest"].get("schema") != "cnn-pipeline-v10.1-release-bundle-v2":
        raise ValueError("WC qualification requires release bundle schema v2")
    fixtures = load_frozen_fixtures(
        args.fixture_root, args.expected_fixture_manifest_sha256,
        release, args.asset_root)
    boot_id_start = _current_boot_id()
    transport = None
    close_result = None
    run_result = None
    failure = None
    try:
        transport = runtime.LinuxIoctlV10Transport(
            args.device,
            expected_parameter_manifest_words=release["parameter_manifest_words"])
        run_result = run_qualification(transport, release, fixtures, args.timeout_s)
    except Exception as error:
        failure = error
        run_result = {
            "case_results": getattr(error, "qualification_case_results", []),
            "gate_evidence": getattr(error, "qualification_gate_evidence", {}),
            "failed_profile": getattr(error, "qualification_failed_profile", None),
        }
    finally:
        if transport is not None:
            try:
                close_result = transport.close()
            except Exception as error:
                if failure is None:
                    failure = error
    boot_id_end = _current_boot_id()
    if boot_id_end != boot_id_start and failure is None:
        failure = RuntimeError("kernel boot_id changed during qualification")
    evidence = {} if run_result is None else run_result["gate_evidence"]
    close_ok = (isinstance(close_result, dict) and
                close_result.get("quiesce_confirmed") is True and
                close_result.get("all_handles_freed") is True and
                close_result.get("transport_closed") is True)
    details = {
        "boot_id_end": boot_id_end,
        "release_manifest_sha256": release["manifest_sha256"],
        "fixture_manifest_sha256": fixtures["manifest_sha256"],
        "driver_module_sha256": module_sha, "dtbo_sha256": dtbo_sha,
        "case_results": [] if run_result is None else run_result["case_results"],
        "failed_profile": None if run_result is None else run_result.get("failed_profile"),
        "transport_close": close_result,
        "transport_close_ok": close_ok,
        "rmmod_refcount_check": "external_control_window_required",
    }
    if not close_ok:
        if failure is None:
            failure = RuntimeError("transport close did not confirm quiesce/free/close")
    receipt, detail_path = write_receipts(
        args.output_receipt, boot_id_start, module_sha, dtbo_sha,
        evidence, details, failure)
    print(json.dumps({"status": receipt["status"],
                      "receipt": str(pathlib.Path(args.output_receipt).resolve()),
                      "details": str(detail_path.resolve()),
                      "completed_live_gates": receipt["completed_live_gates"]},
                     sort_keys=True))
    return 0 if receipt["status"] == LIVE_RECEIPT_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["load_frozen_fixtures", "run_qualification", "write_receipts", "main"]
