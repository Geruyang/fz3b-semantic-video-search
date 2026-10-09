#!/usr/bin/env python3
"""Finish refined-N1 short gates after mask16 narrowly missed the model gate."""
from __future__ import print_function

import datetime
import hashlib
import json
from pathlib import Path

import run_cnn_v10_n1_masks_target_short as common_masks
import run_cnn_v10_wc_live_and_ab as common


OUT = common.REPO / (
    "artifacts/board-debug-20261007/acceleration/network/"
    "network10-v10.1-n1-refined-short-004")
PREVIOUS = common.REPO / (
    "artifacts/board-debug-20261007/acceleration/network/"
    "network10-v10.1-n1-refined-short-002")
RUNS = (("mask32", False), ("mask32", True))


def main():
    if OUT.exists():
        raise RuntimeError("refusing overwrite")
    OUT.mkdir(parents=True)
    previous_raw = (PREVIOUS / "receipt.json").read_bytes()
    previous = json.loads(previous_raw.decode("utf-8"))
    if (previous.get("status") != "FAILED" or
            previous.get("masks", {}).get("mask16", {}).get("runs", {}).get(
                "n1-only", {}).get("result_sha256") is None):
        raise RuntimeError("previous checkpoint is not the expected mask16 result")
    receipt = {
        "schema": "fz3b-v10.1-n1-refined-short-resume-v1",
        "status": "FAILED", "boot_id": common.BOOT,
        "started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
        "previous_receipt_sha256": hashlib.sha256(previous_raw).hexdigest(),
        "commands": [], "runs": {},
    }
    client = common.helper.connect()
    try:
        common.run(client, "reload-base-for-remaining-short-gates",
                   "set -eu; test \"$(cat /proc/sys/kernel/random/boot_id)\" = %s; "
                   "grep -qx applied %s/status; test -d /sys/module/cnn_ddr_v10_candidate; "
                   "test \"$(cat /sys/module/cnn_ddr_v10_candidate/refcnt)\" = 0; "
                   "test -z \"$(fuser /dev/network10_v10 2>/dev/null || true)\"; "
                   "/sbin/rmmod cnn_ddr_v10_candidate; "
                   "/sbin/insmod %s/driver/cnn_ddr_v10_candidate.ko" %
                   (common.BOOT, common.BASE_OVERLAY, common.BASE), receipt)
        for run_index, (mask, suffix) in enumerate(RUNS):
            if run_index:
                common.run(client, "reload-base-before-%s-%s" %
                           (mask, "combined" if suffix else "n1"),
                           "set -eu; test \"$(cat /sys/module/cnn_ddr_v10_candidate/refcnt)\" = 0; "
                           "test -z \"$(fuser /dev/network10_v10 2>/dev/null || true)\"; "
                           "/sbin/rmmod cnn_ddr_v10_candidate; "
                           "/sbin/insmod %s/driver/cnn_ddr_v10_candidate.ko" % common.BASE,
                           receipt)
            variant = "combined-suffix" if suffix else "n1-only"
            label = "n1-%s-%s-short10-v3" % (mask, variant)
            selection = (common.REMOTE + "/n1-refined2/" + mask +
                         "/validated/selection.json")
            command = common_masks._benchmark(label, selection, suffix)
            outcome = common.run(client, "run-" + label, command, receipt,
                                 1800, allow=True)
            local_dir = OUT / mask
            local_dir.mkdir(parents=True, exist_ok=True)
            local_result = local_dir / (variant + "-result.json")
            sftp = client.open_sftp()
            try:
                sftp.get(common.REMOTE + "/results/" + label + "/result.json",
                         str(local_result))
            finally:
                sftp.close()
            value = json.loads(local_result.read_text(encoding="utf-8"))
            measured = value.get("measured", {})
            features = measured.get("features", [])
            receipt["runs"][mask + ":" + variant] = {
                "command_exit_code": outcome["exit_code"],
                "status": value.get("status"),
                "result_sha256": hashlib.sha256(local_result.read_bytes()).hexdigest(),
                "fps": measured.get("fps_including_fill_and_drain"),
                "feature_protocol_pass": measured.get("feature_protocol_pass"),
                "min_cosine": min((item.get("cosine", 1.0) for item in features),
                                  default=None),
                "max_relative_l2": max((item.get("relative_l2", 0.0)
                                         for item in features), default=None),
            }
        receipt["status"] = "PASS_REFINED_N1_SHORT_GATES_RECORDED"
    finally:
        client.close()
        receipt["finished_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
        raw = (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode("utf-8")
        (OUT / "receipt.json").write_bytes(raw)
        print(json.dumps({"status": receipt["status"],
                          "sha256": hashlib.sha256(raw).hexdigest()}))


if __name__ == "__main__":
    main()
