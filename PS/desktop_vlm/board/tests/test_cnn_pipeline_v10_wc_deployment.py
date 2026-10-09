import hashlib
import json
import re
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path

import cnn_pipeline_v10_wc_deployment as wc

@contextmanager
def _raises(exception_type, match):
    try:
        yield
    except exception_type as exc:
        if not re.search(match, str(exc)):
            raise AssertionError("exception did not match %r: %s" % (match, exc))
    else:
        raise AssertionError("expected %s" % exception_type.__name__)


class _MonkeyPatch:
    def setattr(self, obj, name, value):
        setattr(obj, name, value)


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _write_json(path, value):
    raw = (json.dumps(value, sort_keys=True) + "\n").encode("utf-8")
    path.write_bytes(raw)
    return raw


def _file_record(path):
    raw = path.read_bytes()
    return {"path": path.name, "bytes": len(raw), "sha256": _sha(raw)}


def test_wc_manifest_binds_base_and_rejects_target_tamper(tmp_path, monkeypatch):
    release = "1" * 64
    base_sha = "2" * 64
    base_value = {"manifest_sha256": base_sha,
                  "release_manifest_sha256": release, "clock_hz": 196415985}
    monkeypatch.setattr(wc, "load_v10_platform_deployment",
                        lambda path, expected, rel: dict(base_value))
    files = {}
    for name, suffix in (("driver_module", ".ko"), ("module_symvers", ".txt"),
                         ("driver_compile_receipt", ".json"),
                         ("overlay_source", ".dts"), ("overlay_dtbo", ".dtbo"),
                         ("overlay_roundtrip_source", ".dts")):
        path = tmp_path / (name + suffix)
        path.write_bytes(name.encode("ascii"))
        files[name] = {"path": path.name, "bytes": path.stat().st_size,
                       "sha256": _sha(path.read_bytes())}
    manifest = {"schema": wc.SCHEMA, "status": wc.STATUS,
                "target": wc.TARGET,
                "base_deployment": dict(base_value, clock_hz=196415985),
                "offline_gates": dict((name, True) for name in wc.REQUIRED_OFFLINE_GATES),
                "required_live_gates": list(wc.REQUIRED_LIVE_GATES),
                "live_gates_completed": False, "files": files}
    raw = (json.dumps(manifest, sort_keys=True) + "\n").encode("utf-8")
    path = tmp_path / "manifest.json"
    path.write_bytes(raw)
    loaded = wc.load_v10_wc_deployment(path, _sha(raw), "base.json", base_sha, release)
    assert loaded["live_gates_completed"] is False
    manifest["target"] = dict(wc.TARGET, device="/dev/network10_v10")
    bad = (json.dumps(manifest, sort_keys=True) + "\n").encode("utf-8")
    path.write_bytes(bad)
    with _raises(ValueError, "schema/status/target"):
        wc.load_v10_wc_deployment(path, _sha(bad), "base.json", base_sha, release)


def _qualification_fixture(tmp_path, monkeypatch, boot_id="fd395d2a-974c-4a1a-827d-568452cd8488"):
    module = tmp_path / "driver.ko"
    overlay = tmp_path / "candidate.dtbo"
    live = tmp_path / "live.json"
    reserved = tmp_path / "reserved.json"
    offline_manifest = tmp_path / "offline.json"
    for path in (module, overlay):
        path.write_bytes(path.name.encode("ascii"))
    records = {"driver_module": _file_record(module),
               "overlay_dtbo": _file_record(overlay)}
    fake_offline = {"manifest": {"files": {
        "driver_module": {"sha256": records["driver_module"]["sha256"]},
        "overlay_dtbo": {"sha256": records["overlay_dtbo"]["sha256"]}}},
        "base_deployment": {"clock_hz": 196415985}}
    monkeypatch.setattr(wc, "load_v10_wc_deployment",
                        lambda *args, **kwargs: fake_offline)
    reserved_receipt = {
        "schema": wc.RESERVED_RECEIPT_SCHEMA,
        "status": wc.RESERVED_RECEIPT_STATUS,
        "target": wc.TARGET,
        "boot_id": boot_id,
        "completed_gate": wc.RESERVED_MEMORY_GATE,
        "reserved_ranges": {
            "low": {"reg": [0x40000000, 0x40000000], "no_map": True},
            "high": {"reg": [0x800000000, 0x40000000], "no_map": True}},
        "system_ram_ranges": [
            {"start": 0, "size": 0x40000000},
            {"start": 0x840000000, "size": 0x40000000}]}
    _write_json(reserved, reserved_receipt)
    live_receipt = {
        "schema": wc.LIVE_RECEIPT_SCHEMA,
        "status": wc.LIVE_RECEIPT_STATUS,
        "target": wc.TARGET,
        "boot_id": boot_id,
        "driver_module_sha256": records["driver_module"]["sha256"],
        "dtbo_sha256": records["overlay_dtbo"]["sha256"],
        "completed_live_gates": dict((name, True)
                                      for name in wc.LIVE_TRANSFER_GATES)}
    _write_json(live, live_receipt)
    records.update(live_test_receipt=_file_record(live),
                   reserved_memory_receipt=_file_record(reserved))
    offline_manifest.write_bytes(b"offline manifest receipt")
    monkeypatch.setattr(wc, "_current_boot_id", lambda: boot_id)
    record = {"schema": wc.QUALIFICATION_SCHEMA,
              "status": wc.QUALIFICATION_STATUS, "target": wc.TARGET,
              "boot_id": boot_id,
              "offline_manifest": _file_record(offline_manifest),
              "files": records}
    path = tmp_path / "qualification.json"
    raw = _write_json(path, record)
    return {"path": path, "record": record, "module": module,
            "overlay": overlay, "live": live, "reserved": reserved,
            "raw": raw}


def _rewrite_qualification(fixture):
    return _write_json(fixture["path"], fixture["record"])


def test_wc_qualification_derives_live_gates_from_same_boot_receipts(tmp_path, monkeypatch):
    fixture = _qualification_fixture(tmp_path, monkeypatch)
    raw = fixture["raw"]
    loaded = wc.load_v10_wc_qualification(
        fixture["path"], _sha(raw), "base.json", "2" * 64, "1" * 64)
    assert loaded["target"]["device"] == "/dev/network10_v10_wc_candidate"
    assert loaded["live_gates_completed"] is True
    assert loaded["completed_live_gates"] == dict((name, True)
                                                   for name in wc.REQUIRED_LIVE_GATES)
    fixture["record"]["completed_live_gates"] = dict(
        (name, True) for name in wc.REQUIRED_LIVE_GATES)
    bad = _rewrite_qualification(fixture)
    with _raises(ValueError, "live gates"):
        wc.load_v10_wc_qualification(
            fixture["path"], _sha(bad), "base.json", "2" * 64, "1" * 64)


def test_wc_qualification_rejects_receipts_from_an_older_boot(tmp_path, monkeypatch):
    fixture = _qualification_fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(wc, "_current_boot_id",
                        lambda: "774b9485-2465-4f16-b60e-a4081467f468")
    with _raises(ValueError, "stale"):
        wc.load_v10_wc_qualification(
            fixture["path"], _sha(fixture["raw"]),
            "base.json", "2" * 64, "1" * 64)


def test_wc_qualification_rejects_fake_reserved_receipt(tmp_path, monkeypatch):
    fixture = _qualification_fixture(tmp_path, monkeypatch)
    receipt = json.loads(fixture["reserved"].read_text(encoding="utf-8"))
    receipt["reserved_ranges"]["low"]["no_map"] = False
    _write_json(fixture["reserved"], receipt)
    fixture["record"]["files"]["reserved_memory_receipt"] = _file_record(
        fixture["reserved"])
    raw = _rewrite_qualification(fixture)
    with _raises(ValueError, "reg/no-map"):
        wc.load_v10_wc_qualification(
            fixture["path"], _sha(raw), "base.json", "2" * 64, "1" * 64)


def test_wc_qualification_rejects_live_receipt_with_wrong_artifact_identity(tmp_path, monkeypatch):
    fixture = _qualification_fixture(tmp_path, monkeypatch)
    receipt = json.loads(fixture["live"].read_text(encoding="utf-8"))
    receipt["dtbo_sha256"] = "0" * 64
    _write_json(fixture["live"], receipt)
    fixture["record"]["files"]["live_test_receipt"] = _file_record(fixture["live"])
    raw = _rewrite_qualification(fixture)
    with _raises(ValueError, "module/DTBO identity"):
        wc.load_v10_wc_qualification(
            fixture["path"], _sha(raw), "base.json", "2" * 64, "1" * 64)


class V10WCDeploymentUnitTests(unittest.TestCase):
    def _run_with_tempdir(self, function):
        with tempfile.TemporaryDirectory() as directory:
            function(Path(directory), _MonkeyPatch())

    def test_manifest_binds_base_and_rejects_target_tamper(self):
        self._run_with_tempdir(test_wc_manifest_binds_base_and_rejects_target_tamper)

    def test_qualification_derives_live_gates_from_receipts(self):
        self._run_with_tempdir(test_wc_qualification_derives_live_gates_from_same_boot_receipts)

    def test_qualification_rejects_old_boot(self):
        self._run_with_tempdir(test_wc_qualification_rejects_receipts_from_an_older_boot)

    def test_qualification_rejects_fake_reserved_receipt(self):
        self._run_with_tempdir(test_wc_qualification_rejects_fake_reserved_receipt)

    def test_qualification_rejects_wrong_live_artifact_identity(self):
        self._run_with_tempdir(
            test_wc_qualification_rejects_live_receipt_with_wrong_artifact_identity)
