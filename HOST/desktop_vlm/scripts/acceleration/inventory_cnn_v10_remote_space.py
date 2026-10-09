#!/usr/bin/env python3
"""Read-only disk and project-staging inventory on the FZ3B target."""
from __future__ import print_function

import datetime
import hashlib
import json
import sys
from pathlib import Path


REPO = Path(r"E:\AIProject\FPGAVibecoding")
OUT = REPO / "artifacts/board-debug-20261007/acceleration/network/network10-v10.2-remote-space-inventory-001"
BOOT = "fd395d2a-974c-4a1a-827d-568452cd8488"
sys.path.insert(0, str(REPO / "artifacts/board-debug-20261004/acceleration/network"))
import dma_driver_rebuild as helper


def run(client, name, command, report, timeout=180):
    result = helper.run(client, name, command, timeout)
    report["commands"].append(result)
    if result["exit_code"]:
        raise RuntimeError("%s failed: %s\n%s" %
                           (name, result["stdout"], result["stderr"]))
    return result


def main():
    if OUT.exists():
        raise RuntimeError("refusing to overwrite remote-space inventory")
    OUT.mkdir(parents=True)
    report = {
        "schema": "fz3b-v10.2-project-space-inventory-v1",
        "status": "RUNNING",
        "boot_id": BOOT,
        "mode": "read_only_no_delete_no_module_no_pl_change",
        "commands": [],
        "started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    client = helper.connect()
    try:
        run(client, "state-and-filesystems",
            "set -eu; test \"$(cat /proc/sys/kernel/random/boot_id)\" = {boot}; "
            "test -d /sys/module/fpgadrv; test -c /dev/fpgadrv0; "
            "test \"$(cat /sys/module/fpgadrv/refcnt)\" = 0; "
            "echo DF_H_BEGIN; df -hT; echo DF_H_END; "
            "echo DF_I_BEGIN; df -i; echo DF_I_END; "
            "echo FINDMNT_BEGIN; findmnt -rno TARGET,SOURCE,FSTYPE,SIZE,AVAIL,USE%; echo FINDMNT_END".format(
                boot=BOOT), report)
        run(client, "project-root-directories",
            "set -eu; echo PROJECT_DU_KIB_BEGIN; "
            "find /root -mindepth 1 -maxdepth 1 -type d "
            "'(' -name 'network10-*' -o -name 'cnn-v10-*' -o -name 'board-debug-kernel-*' ')' "
            "-print0 | sort -z | xargs -0 -r du -sk; "
            "echo PROJECT_DU_KIB_END; echo ROOT_TOP_KIB_BEGIN; "
            "du -sk /root/* 2>/dev/null | sort -n; echo ROOT_TOP_KIB_END", report, 600)
        run(client, "protected-path-identities",
            "set -eu; "
            "test -d /root/network10-v10.2-p3-window-preupload-001; "
            "test -d /root/network10-v10.2-p3-compile-003; "
            "sha256sum /root/network10-v10.2-p3-window-preupload-001/expected-sha256.txt "
            "/root/network10-v10.2-p3-window-preupload-001/driver/cnn_ddr_v10_p3_candidate.ko "
            "/root/network10-v10.2-p3-window-preupload-001/chain-parameters/manifest.json "
            "/root/network10-v10.2-p3-compile-003/driver/cnn_ddr_v10_p3_candidate.ko "
            "/root/workspace/driver/fpgadrv.ko; "
            "echo PROTECTED_IDENTITIES_PASS", report)
        report["status"] = "PASS_READ_ONLY_PROJECT_SPACE_INVENTORY"
    finally:
        client.close()
        report["finished_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
        raw = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode("utf-8")
        (OUT / "receipt.json").write_bytes(raw)
        print(json.dumps({"status": report.get("status", "FAILED"),
                          "receipt_sha256": hashlib.sha256(raw).hexdigest()}, sort_keys=True))


if __name__ == "__main__":
    main()
