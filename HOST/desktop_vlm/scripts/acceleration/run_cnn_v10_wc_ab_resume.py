#!/usr/bin/env python3
"""Resume the WC qualification after the completed live gate was archived.

The preceding attempt completed the destructive/live portion and unloaded the
WC module, but failed while creating a local receipt directory.  This script
binds that immutable attempt and continues with packaging and performance only.
"""
from __future__ import print_function

import datetime
import hashlib
import json
import shutil
from pathlib import Path

import run_cnn_v10_wc_live_and_ab as common


OUT = common.REPO / (
    "artifacts/board-debug-20261007/acceleration/network/"
    "network10-v10.1-wc-live-ab-003")
PREVIOUS = common.REPO / (
    "artifacts/board-debug-20261007/acceleration/network/"
    "network10-v10.1-wc-live-ab-002")


def _load_previous():
    receipt_path = PREVIOUS / "receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    names = [item.get("name") for item in receipt.get("commands", [])
             if item.get("exit_code") == 0]
    required = {"wc-live-qualification", "wc-post-live-rmmod-proof"}
    if receipt.get("status") != "FAILED" or not required.issubset(set(names)):
        raise RuntimeError("previous attempt is not the expected completed-live checkpoint")
    live_path = PREVIOUS / "live-test-receipt.json"
    details_path = PREVIOUS / "live-test-receipt.details.json"
    live = json.loads(live_path.read_text(encoding="utf-8"))
    if live.get("status") != "PASS_WC_LIVE_TRANSFER_AND_FUNCTIONAL_GATES":
        raise RuntimeError("previous live qualification did not pass")
    return receipt_path, live_path, details_path, live


def main():
    if OUT.exists():
        raise RuntimeError("refusing overwrite")
    receipt_path, live_path, details_path, live = _load_previous()
    OUT.mkdir(parents=True)
    result = {
        "schema": "fz3b-v10.1-wc-live-ab-resume-v1",
        "status": "FAILED",
        "boot_id": common.BOOT,
        "started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
        "commands": [],
        "prior_attempt": common.record(receipt_path, common.REPO),
        "results": {},
    }
    shutil.copy2(live_path, OUT / "live-test-receipt.json")
    shutil.copy2(details_path, OUT / "live-test-receipt.details.json")
    common.write_json(OUT / "reserved-memory-receipt.json", common.reserved_receipt())
    qualification = OUT / "qualification"
    shutil.copytree(common.OFFLINE, qualification / "offline")
    (qualification / "receipts").mkdir(parents=True)
    shutil.copy2(OUT / "live-test-receipt.json",
                 qualification / "receipts/live-test-receipt.json")
    shutil.copy2(OUT / "reserved-memory-receipt.json",
                 qualification / "receipts/reserved-memory-receipt.json")
    manifest = {
        "schema": "cnn-pipeline-v10.1-wc-driver-qualification-v1",
        "status": "PASS_BOARD_QUALIFIED",
        "target": live["target"],
        "boot_id": common.BOOT,
        "offline_manifest": common.record(qualification / "offline/manifest.json", qualification),
        "files": {
            "driver_module": common.record(
                qualification / "offline/driver/cnn_ddr_v10_wc_candidate.ko", qualification),
            "overlay_dtbo": common.record(
                qualification / "offline/platform/network10_v10_overlay_wc_experiment.dtbo", qualification),
            "live_test_receipt": common.record(
                qualification / "receipts/live-test-receipt.json", qualification),
            "reserved_memory_receipt": common.record(
                qualification / "receipts/reserved-memory-receipt.json", qualification),
        },
    }
    common.write_json(qualification / "qualification.json", manifest)
    qualification_sha = common.sha(qualification / "qualification.json")
    client = common.helper.connect()
    try:
        common.run(client, "resume-same-boot-wc-unloaded",
                   "set -eu; test \"$(cat /proc/sys/kernel/random/boot_id)\" = %s; "
                   "grep -qx applied %s/status; "
                   "test ! -d /sys/module/cnn_ddr_v10_wc_candidate; "
                   "test ! -d /sys/module/cnn_ddr_v10_candidate; "
                   "test ! -e /dev/network10_v10_wc_candidate; test ! -e /dev/network10_v10" %
                   (common.BOOT, common.WC_OVERLAY), result)
        sftp = client.open_sftp()
        try:
            for path in qualification.rglob("*"):
                if path.is_file():
                    common.upload(sftp, path, common.REMOTE + "/wc-qualification/" +
                                  path.relative_to(qualification).as_posix())
        finally:
            sftp.close()
        remote_qualification = common.REMOTE + "/wc-qualification/qualification.json"
        common.run(client, "target-qualification-loader",
                   "set -eu; cd %s/runtime; PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. "
                   "python3 -B -c \"from cnn_pipeline_v10_wc_deployment import "
                   "load_v10_wc_qualification as l;q=l('%s','%s','%s/platform/manifest.json',"
                   "'%s','%s');assert q['live_gates_completed'] and "
                   "q['target']['device']=='/dev/network10_v10_wc_candidate';"
                   "print('WC_QUALIFICATION_PASS',q['manifest_sha256'])\"" %
                   (common.REMOTE, remote_qualification, qualification_sha,
                    common.BASE, common.DEPLOY, common.RELEASE), result)
        common.run(client, "reload-wc-for-performance",
                   "set -eu; /sbin/insmod %s/wc-package/driver/"
                   "cnn_ddr_v10_wc_candidate.ko; test -c /dev/network10_v10_wc_candidate" %
                   common.REMOTE, result)
        common.run(client, "run-wc-suffix30",
                   common.benchmark("wc-suffix-w8a8-30-v2",
                                    "/dev/network10_v10_wc_candidate",
                                    (remote_qualification, qualification_sha), False),
                   result, 3600)
        sftp = client.open_sftp()
        try:
            sftp.get(common.REMOTE + "/results/wc-suffix-w8a8-30-v2/result.json",
                     str(OUT / "wc-suffix-w8a8-30-result.json"))
        finally:
            sftp.close()
        wc = json.loads((OUT / "wc-suffix-w8a8-30-result.json").read_text(encoding="utf-8"))
        wc_fps = wc["measured"]["fps_including_fill_and_drain"]
        if wc.get("status") != "ENGINEERING_FEATURE_REGRESSION_PROTOCOL_CLEAN":
            raise RuntimeError("WC suffix30 gate failed")
        base_fps = 2.7647195438974035
        selected = "wc" if wc_fps > base_fps else "base"
        if selected == "wc":
            common.run(client, "reload-selected-wc",
                       "set -eu; /sbin/rmmod cnn_ddr_v10_wc_candidate; "
                       "/sbin/insmod %s/wc-package/driver/cnn_ddr_v10_wc_candidate.ko" %
                       common.REMOTE, result)
            device = "/dev/network10_v10_wc_candidate"
            qualification_args = (remote_qualification, qualification_sha)
        else:
            common.run(client, "switch-wc-to-base",
                       "set -eu; /sbin/rmmod cnn_ddr_v10_wc_candidate; rmdir %s; "
                       "mkdir %s; cat %s/platform/platform/network10_v10_trace18.dtbo > %s/dtbo; "
                       "grep -qx applied %s/status; /sbin/insmod %s/driver/cnn_ddr_v10_candidate.ko" %
                       (common.WC_OVERLAY, common.BASE_OVERLAY, common.BASE,
                        common.BASE_OVERLAY, common.BASE_OVERLAY, common.BASE), result)
            device = "/dev/network10_v10"
            qualification_args = None
        label = "selected-%s-suffix-w8a8-jsonl-30-v2" % selected
        common.run(client, "run-selected-jsonl30",
                   common.benchmark(label, device, qualification_args, True), result, 3600)
        sftp = client.open_sftp()
        try:
            sftp.get(common.REMOTE + "/results/" + label + "/result.json",
                     str(OUT / (label + "-result.json")))
            sftp.get(common.REMOTE + "/results/" + label + "/measured-live.jsonl",
                     str(OUT / (label + "-measured-live.jsonl")))
        finally:
            sftp.close()
        delivery_path = OUT / (label + "-result.json")
        delivery = json.loads(delivery_path.read_text(encoding="utf-8"))
        if delivery.get("status") != "ENGINEERING_FEATURE_REGRESSION_PROTOCOL_CLEAN":
            raise RuntimeError("selected JSONL gate failed")
        result["qualification"] = {
            "path": "qualification/qualification.json",
            "sha256": qualification_sha,
            "live_receipt_sha256": common.sha(OUT / "live-test-receipt.json"),
            "details_sha256": common.sha(OUT / "live-test-receipt.details.json"),
        }
        result["results"] = {
            "base_suffix_no_sink_fps": base_fps,
            "wc_suffix_no_sink": {"sha256": common.sha(OUT / "wc-suffix-w8a8-30-result.json"),
                                   "fps": wc_fps, "status": wc["status"]},
            "selected": selected,
            "selected_jsonl": {
                "sha256": common.sha(delivery_path),
                "jsonl_sha256": common.sha(OUT / (label + "-measured-live.jsonl")),
                "fps": delivery["measured"]["fps_including_fill_and_drain"],
                "status": delivery["status"],
            },
        }
        result["status"] = "PASS_WC_QUALIFIED_AB_AND_SELECTED_DELIVERY"
    finally:
        client.close()
        result["finished_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
        raw = (json.dumps(result, indent=2, sort_keys=True) + "\n").encode("utf-8")
        (OUT / "receipt.json").write_bytes(raw)
        print(json.dumps({"status": result["status"],
                          "sha256": hashlib.sha256(raw).hexdigest()}))


if __name__ == "__main__":
    main()
