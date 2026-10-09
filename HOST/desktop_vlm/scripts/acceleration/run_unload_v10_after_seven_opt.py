#!/usr/bin/env python3
"""Normally unload the quiesced V10 module and remove its exact overlay."""
from __future__ import print_function

import datetime
import hashlib
import json
import sys
from pathlib import Path


REPO = Path(r"E:\AIProject\FPGAVibecoding")
OUT = (REPO / "artifacts/board-debug-20261007/acceleration/network/"
       "network10-v10.1-seven-opt-unload-handoff-001")
BOOT = "fd395d2a-974c-4a1a-827d-568452cd8488"
REMOTE_TOOLS = "/root/network10-v10.1-board-window/tools"
OVERLAY = "/sys/kernel/config/device-tree/overlays/network10-v10-trace18"

sys.path.insert(0, str(REPO / "artifacts/board-debug-20261004/acceleration/network"))
import dma_driver_rebuild as helper


def run(client, name, command, report, timeout=60):
    record = helper.run(client, name, command, timeout)
    report["commands"].append(record)
    if record["exit_code"]:
        raise RuntimeError("%s failed: %s %s" %
                           (name, record["stdout"], record["stderr"]))
    return record


def main():
    if OUT.exists():
        raise RuntimeError("handoff evidence already exists")
    OUT.mkdir(parents=True)
    report = {
        "schema": "fz3b-v10.1-normal-unload-factory-pl-handoff-v1",
        "boot_id": BOOT,
        "normal_module_unload": True,
        "force_unload_used": False,
        "reboot_performed": False,
        "pl_programming_performed": False,
        "commands": [],
        "started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    client = helper.connect()
    failure = None
    try:
        rdissue = run(
            client, "fresh-safe-preflight",
            "set -eu; test \"$(cat /proc/sys/kernel/random/boot_id)\" = %s; "
            "grep -qx applied %s/status; "
            "test -d /sys/module/cnn_ddr_v10_candidate; test -c /dev/network10_v10; "
            "test \"$(cat /sys/module/cnn_ddr_v10_candidate/refcnt)\" = 0; "
            "test -z \"$(fuser /dev/network10_v10 2>/dev/null || true)\"; "
            "test ! -e /sys/module/fpgadrv; test ! -e /dev/fpgadrv0; "
            "%s/rmw_ps_afifm2_rdissue read; echo V10_UNLOAD_PREFLIGHT_PASS" %
            (BOOT, OVERLAY, REMOTE_TOOLS), report)
        if "old=0x00000007 new=0x00000007 readback=0x00000007" not in rdissue["stdout"]:
            raise RuntimeError("RDISSUE original word was not restored before unload")
        run(client, "normal-rmmod-v10",
            "set -eu; /sbin/rmmod cnn_ddr_v10_candidate; "
            "test ! -e /sys/module/cnn_ddr_v10_candidate; "
            "test ! -e /dev/network10_v10; echo V10_MODULE_NORMALLY_UNLOADED",
            report)
        run(client, "remove-exact-v10-overlay",
            "set -eu; test -d %s; rmdir %s; test ! -e %s; "
            "echo V10_EXACT_OVERLAY_REMOVED" % (OVERLAY, OVERLAY, OVERLAY), report)
        run(client, "fresh-factory-pl-handoff-state",
            "set -eu; test \"$(cat /proc/sys/kernel/random/boot_id)\" = %s; "
            "test ! -e /sys/module/cnn_ddr_v10_candidate; "
            "test ! -e /dev/network10_v10; test ! -e %s; "
            "test ! -e /sys/module/fpgadrv; test ! -e /dev/fpgadrv0; "
            "test -z \"$(pgrep -f '[r]un_cnn_pipeline_v10|[o]rt_partition_runner' || true)\"; "
            "cat /sys/class/fpga_manager/fpga0/state; ip -brief address show eth0; "
            "echo V10_ABSENT_READY_FOR_JTAG_FACTORY_PL_RESTORE" % (BOOT, OVERLAY), report)
        report["status"] = "V10_MODULE_OVERLAY_ABSENT_READY_FOR_FACTORY_PL_RESTORE"
    except Exception as error:
        failure = error
        report["status"] = "FAILED"
        report["error"] = "%s: %s" % (type(error).__name__, error)
        raise
    finally:
        client.close()
        report["finished_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
        raw = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode("utf-8")
        (OUT / "receipt.json").write_bytes(raw)
        print(json.dumps({"status": report["status"], "path": str(OUT / "receipt.json"),
                          "sha256": hashlib.sha256(raw).hexdigest()}, sort_keys=True))
    return 1 if failure else 0


if __name__ == "__main__":
    raise SystemExit(main())

