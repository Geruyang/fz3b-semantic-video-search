"""Fail-closed loader for the isolated V10.1 WC-driver A/B candidate.

This manifest extends, but never replaces, the frozen trace18 deployment.  It
performs only local identity/SHA checks.  Live reserved-memory and transfer
tests remain mandatory before the experimental device may be timed.
"""

import hashlib
import json
import os
import pathlib
import uuid

try:
    from cnn_pipeline_v10_deployment import load_v10_platform_deployment
except ImportError:
    from .cnn_pipeline_v10_deployment import load_v10_platform_deployment


SCHEMA = "cnn-pipeline-v10.1-wc-driver-experiment-v1"
STATUS = "READY_FOR_CONTROLLED_WC_DRIVER_AB"
QUALIFICATION_SCHEMA = "cnn-pipeline-v10.1-wc-driver-qualification-v1"
QUALIFICATION_STATUS = "PASS_BOARD_QUALIFIED"
RESERVED_RECEIPT_SCHEMA = "cnn-pipeline-v10.1-wc-reserved-memory-receipt-v1"
RESERVED_RECEIPT_STATUS = "PASS_RESERVED_MEMORY_LOW_HIGH_NO_MAP"
LIVE_RECEIPT_SCHEMA = "cnn-pipeline-v10.1-wc-live-test-receipt-v1"
LIVE_RECEIPT_STATUS = "PASS_WC_LIVE_TRANSFER_AND_FUNCTIONAL_GATES"
TARGET = {
    "kernel_release": "4.14.0-xilinx-v2018.3",
    "device": "/dev/network10_v10_wc_candidate",
    "module": "cnn_ddr_v10_wc_candidate",
    "compatible": "fz3b,cnn-ddr-v10-wc-candidate",
}
REQUIRED_FILES = {
    "driver_module", "module_symvers", "driver_compile_receipt",
    "overlay_source", "overlay_dtbo", "overlay_roundtrip_source",
}
REQUIRED_OFFLINE_GATES = {
    "base_trace18_deployment_valid", "target_compile_pass",
    "static_contract_pass", "dtc_roundtrip_pass", "distinct_identity_pass",
    "max_profile_payload_supported",
}
REQUIRED_LIVE_GATES = (
    "same_boot_reserved_memory_low_high_no_map_exact_ranges",
    "low_high_upload_pl_read_exact_with_canary",
    "pl_write_download_exact_with_canary",
    "failed_user_copy_zero_transfer_refs_then_full_retry",
    "full_parameter_upload_and_three_profile_functional_pass",
)
RESERVED_MEMORY_GATE = REQUIRED_LIVE_GATES[0]
LIVE_TRANSFER_GATES = REQUIRED_LIVE_GATES[1:]
RESERVED_RANGES = {
    "low": (0x40000000, 0x40000000),
    "high": (0x800000000, 0x40000000),
}


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _checked_sha(value, label):
    if (not isinstance(value, str) or len(value) != 64 or
            any(ch not in "0123456789abcdef" for ch in value)):
        raise ValueError("%s must be a lowercase SHA256" % label)
    return value


def _current_boot_id():
    """Read the running kernel boot ID; private so host tests can replace it."""
    value = pathlib.Path("/proc/sys/kernel/random/boot_id").read_text(
        encoding="ascii").strip()
    return _canonical_boot_id(value, "current kernel")


def _canonical_boot_id(value, label):
    if not isinstance(value, str):
        raise ValueError("%s boot_id is invalid" % label)
    try:
        canonical = str(uuid.UUID(value))
    except (ValueError, AttributeError):
        raise ValueError("%s boot_id is invalid" % label)
    if value != canonical:
        raise ValueError("%s boot_id is not canonical" % label)
    return canonical


def _read_receipt(path, schema, status, label, expected_fields):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("%s receipt is unreadable" % label) from exc
    if (not isinstance(value, dict) or set(value) != set(expected_fields) or
            value.get("schema") != schema or
            value.get("status") != status or value.get("target") != TARGET):
        raise ValueError("%s receipt schema/status/target mismatch" % label)
    return value


def _receipt_boot_matches(receipt, expected_boot_id, label):
    boot_id = _canonical_boot_id(receipt.get("boot_id"), label)
    if boot_id != expected_boot_id:
        raise ValueError("%s receipt boot_id mismatch" % label)


def _positive_int(value, label):
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError("%s must be a positive integer" % label)
    return value


def _validate_reserved_receipt(receipt, expected_boot_id):
    _receipt_boot_matches(receipt, expected_boot_id, "reserved-memory")
    if receipt.get("completed_gate") != RESERVED_MEMORY_GATE:
        raise ValueError("reserved-memory receipt gate mismatch")
    ranges = receipt.get("reserved_ranges")
    if not isinstance(ranges, dict) or set(ranges) != set(RESERVED_RANGES):
        raise ValueError("reserved-memory receipt ranges are incomplete")
    reserved = []
    for name, (expected_start, expected_size) in RESERVED_RANGES.items():
        item = ranges.get(name)
        if not isinstance(item, dict) or set(item) != {"reg", "no_map"}:
            raise ValueError("reserved-memory %s record is malformed" % name)
        reg = item.get("reg")
        if (not isinstance(reg, list) or len(reg) != 2 or
                any(isinstance(part, bool) or not isinstance(part, int)
                    for part in reg) or tuple(reg) != (expected_start, expected_size) or
                item.get("no_map") is not True):
            raise ValueError("reserved-memory %s reg/no-map mismatch" % name)
        reserved.append((expected_start, expected_start + expected_size))

    system_ram = receipt.get("system_ram_ranges")
    if not isinstance(system_ram, list) or not system_ram:
        raise ValueError("reserved-memory receipt lacks System RAM ranges")
    for index, item in enumerate(system_ram):
        if not isinstance(item, dict) or set(item) != {"start", "size"}:
            raise ValueError("System RAM range %d is malformed" % index)
        start = item.get("start")
        size = _positive_int(item.get("size"), "System RAM size")
        if isinstance(start, bool) or not isinstance(start, int) or start < 0:
            raise ValueError("System RAM start is invalid")
        end = start + size
        if end <= start:
            raise ValueError("System RAM range overflows")
        if any(start < reserved_end and reserved_start < end
               for reserved_start, reserved_end in reserved):
            raise ValueError("reserved-memory range overlaps System RAM")


def _validate_live_receipt(receipt, expected_boot_id, module_sha, dtbo_sha):
    _receipt_boot_matches(receipt, expected_boot_id, "live-test")
    if (receipt.get("driver_module_sha256") != module_sha or
            receipt.get("dtbo_sha256") != dtbo_sha):
        raise ValueError("live-test receipt module/DTBO identity mismatch")
    gates = receipt.get("completed_live_gates")
    if (not isinstance(gates, dict) or set(gates) != set(LIVE_TRANSFER_GATES) or
            any(gates[name] is not True for name in LIVE_TRANSFER_GATES)):
        raise ValueError("live-test receipt gates are incomplete")


def _record(root, record, label):
    if not isinstance(record, dict):
        raise ValueError("%s record is missing" % label)
    relative = record.get("path")
    if (not isinstance(relative, str) or not relative or
            relative.startswith(("/", "\\")) or
            ":" in relative.split("/")[0] or
            any(part in ("", ".", "..") for part in relative.replace("\\", "/").split("/"))):
        raise ValueError("%s path is unsafe" % label)
    path = (root / pathlib.PurePosixPath(relative.replace("\\", "/"))).resolve()
    if os.path.commonpath((str(root), str(path))) != str(root):
        raise ValueError("%s path escapes WC package" % label)
    raw = path.read_bytes()
    if (isinstance(record.get("bytes"), bool) or record.get("bytes") != len(raw) or
            _checked_sha(record.get("sha256"), label + " SHA") != _sha(raw)):
        raise ValueError("%s extent/SHA mismatch" % label)
    return path


def load_v10_wc_deployment(manifest_path, expected_manifest_sha256,
                           base_deployment_path,
                           expected_base_deployment_sha256,
                           expected_release_manifest_sha256):
    base = load_v10_platform_deployment(
        base_deployment_path, expected_base_deployment_sha256,
        expected_release_manifest_sha256)
    path = pathlib.Path(manifest_path).resolve()
    raw = path.read_bytes()
    if _sha(raw) != _checked_sha(expected_manifest_sha256, "WC manifest"):
        raise ValueError("WC deployment manifest SHA mismatch")
    manifest = json.loads(raw.decode("utf-8"))
    if (manifest.get("schema") != SCHEMA or manifest.get("status") != STATUS or
            manifest.get("target") != TARGET):
        raise ValueError("WC deployment schema/status/target mismatch")
    binding = manifest.get("base_deployment")
    if (not isinstance(binding, dict) or
            binding.get("manifest_sha256") != base["manifest_sha256"] or
            binding.get("release_manifest_sha256") != base["release_manifest_sha256"] or
            binding.get("clock_hz") != base["clock_hz"]):
        raise ValueError("WC base deployment binding mismatch")
    gates = manifest.get("offline_gates")
    if (not isinstance(gates, dict) or set(gates) != REQUIRED_OFFLINE_GATES or
            any(gates[name] is not True for name in REQUIRED_OFFLINE_GATES)):
        raise ValueError("WC offline gates are incomplete")
    if manifest.get("required_live_gates") != list(REQUIRED_LIVE_GATES):
        raise ValueError("WC live-gate contract is incomplete")
    if manifest.get("live_gates_completed") is not False:
        raise ValueError("WC candidate must not claim live gates in offline package")
    files = manifest.get("files")
    if not isinstance(files, dict) or set(files) != REQUIRED_FILES:
        raise ValueError("WC artifact set is incomplete")
    resolved = dict((name, _record(path.parent, files[name], name))
                    for name in sorted(REQUIRED_FILES))
    if resolved["driver_module"].suffix != ".ko" or resolved["overlay_dtbo"].suffix != ".dtbo":
        raise ValueError("WC module/overlay extension mismatch")
    return {"manifest": manifest, "manifest_sha256": _sha(raw),
            "base_deployment": base, "files": resolved,
            "live_gates_completed": False}


def load_v10_wc_qualification(path, expected_sha256, base_deployment_path,
                              base_sha256, release_sha256):
    """Validate the immutable live receipt that alone authorizes WC timing."""
    qualification_path = pathlib.Path(path).resolve()
    root = qualification_path.parent
    raw = qualification_path.read_bytes()
    if _sha(raw) != _checked_sha(expected_sha256, "WC qualification"):
        raise ValueError("WC qualification SHA mismatch")
    manifest = json.loads(raw.decode("utf-8"))
    if (manifest.get("schema") != QUALIFICATION_SCHEMA or
            manifest.get("status") != QUALIFICATION_STATUS or
            manifest.get("target") != TARGET):
        raise ValueError("WC qualification schema/status/target mismatch")
    if "completed_live_gates" in manifest:
        raise ValueError("WC qualification cannot self-assert completed live gates")
    boot_id = _canonical_boot_id(manifest.get("boot_id"), "qualification")
    current_boot_id = _current_boot_id()
    if boot_id != current_boot_id:
        raise ValueError("WC qualification boot_id is stale for this host")
    offline_path = _record(root, manifest.get("offline_manifest"),
                           "WC offline manifest")
    offline = load_v10_wc_deployment(
        offline_path, manifest["offline_manifest"]["sha256"],
        base_deployment_path, base_sha256, release_sha256)
    files = manifest.get("files")
    expected_files = {"driver_module", "overlay_dtbo", "live_test_receipt",
                      "reserved_memory_receipt"}
    if not isinstance(files, dict) or set(files) != expected_files:
        raise ValueError("WC qualification evidence set is incomplete")
    resolved = dict((name, _record(root, files[name], name))
                    for name in sorted(expected_files))
    for live_name, offline_name in (("driver_module", "driver_module"),
                                    ("overlay_dtbo", "overlay_dtbo")):
        if files[live_name]["sha256"] != offline["manifest"]["files"][offline_name]["sha256"]:
            raise ValueError("WC qualification changed %s identity" % live_name)
    reserved_receipt = _read_receipt(
        resolved["reserved_memory_receipt"], RESERVED_RECEIPT_SCHEMA,
        RESERVED_RECEIPT_STATUS, "reserved-memory",
        {"schema", "status", "target", "boot_id", "completed_gate",
         "reserved_ranges", "system_ram_ranges"})
    _validate_reserved_receipt(reserved_receipt, boot_id)
    live_receipt = _read_receipt(
        resolved["live_test_receipt"], LIVE_RECEIPT_SCHEMA,
        LIVE_RECEIPT_STATUS, "live-test",
        {"schema", "status", "target", "boot_id", "driver_module_sha256",
         "dtbo_sha256", "completed_live_gates"})
    _validate_live_receipt(
        live_receipt, boot_id, files["driver_module"]["sha256"],
        files["overlay_dtbo"]["sha256"])
    completed_gates = {RESERVED_MEMORY_GATE: True}
    completed_gates.update(live_receipt["completed_live_gates"])
    if set(completed_gates) != set(REQUIRED_LIVE_GATES):
        raise ValueError("WC qualification evidence does not close every live gate")
    return {"manifest": manifest, "manifest_sha256": _sha(raw),
            "base_deployment": offline["base_deployment"],
            "offline_deployment": offline, "files": resolved,
            "target": dict(TARGET), "boot_id": boot_id,
            "completed_live_gates": completed_gates,
            "live_gates_completed": all(completed_gates.values())}


__all__ = ["SCHEMA", "STATUS", "QUALIFICATION_SCHEMA",
           "QUALIFICATION_STATUS", "RESERVED_RECEIPT_SCHEMA",
           "RESERVED_RECEIPT_STATUS", "LIVE_RECEIPT_SCHEMA",
           "LIVE_RECEIPT_STATUS", "TARGET", "REQUIRED_FILES",
           "REQUIRED_LIVE_GATES", "load_v10_wc_deployment",
           "load_v10_wc_qualification"]
