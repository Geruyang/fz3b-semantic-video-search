#!/usr/bin/env python3
"""Archive the inactive target-kernel build tree to USB, then reclaim rootfs."""
from __future__ import print_function

import datetime
import hashlib
import json
import sys
from pathlib import Path


REPO = Path(r"E:\AIProject\FPGAVibecoding")
OUT = REPO / "artifacts/board-debug-20261007/acceleration/network/network10-v10.2-kernel-tree-usb-migration-002"
BOOT = "fd395d2a-974c-4a1a-827d-568452cd8488"
SOURCE = "/root/board-debug-kernel-20261004"
USB_ROOT = "/media/root/ESD-USB3/codex-fpga-backups"
INCOMPLETE_ARCHIVE = USB_ROOT + "/board-debug-kernel-20261004.tar"
ARCHIVE = USB_ROOT + "/board-debug-kernel-20261004.tar.gz"
FACTORY_SHA = "a482b11d47a117e60f98efd43631b45a3a33ba98e81ff610204d2f301dbb0b6f"
P3_KO_SHA = "b166879d3773f915d361c2579aeac15bd7126ed99243879f5eb063f2c758c5ca"
COMBINED_SHA = "c62b9f49b1118916168a2ca7a4a63c56d51bba66a0921523af35d46495bbab99"

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
        raise RuntimeError("refusing to overwrite kernel-tree migration evidence")
    OUT.mkdir(parents=True)
    report = {
        "schema": "fz3b-v10.2-target-kernel-tree-usb-migration-v1",
        "status": "RUNNING",
        "boot_id": BOOT,
        "source": SOURCE,
        "archive": ARCHIVE,
        "scope": "inactive build tree only; compile003 KO/Symvers and all runtime assets remain on rootfs",
        "supersedes_incomplete_archive": INCOMPLETE_ARCHIVE,
        "commands": [],
        "started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    client = helper.connect()
    try:
        run(client, "stop-and-remove-owned-incomplete-archive",
            "set -eu; pattern='^tar -cpf {old} -C /root board-debug-kernel-20261004$'; "
            "pid=$(pgrep -f \"$pattern\"); test -n \"$pid\"; "
            "test \"$(tr '\\000' ' ' </proc/$pid/cmdline | sed 's/ $//')\" = "
            "'tar -cpf {old} -C /root board-debug-kernel-20261004'; "
            "kill -TERM \"$pid\"; i=0; while kill -0 \"$pid\" 2>/dev/null; do "
            "i=$((i+1)); test $i -le 50; sleep 0.1; done; "
            "test -d {source}; test -f {old}; du -k {old}; "
            "rm -f -- {old}; test ! -e {old}; sync; "
            "echo OWNED_INCOMPLETE_ARCHIVE_REMOVED".format(
                old=INCOMPLETE_ARCHIVE, source=SOURCE), report, 60)
        run(client, "migration-preflight",
            "set -eu; test \"$(cat /proc/sys/kernel/random/boot_id)\" = {boot}; "
            "test -d /sys/module/fpgadrv; test -c /dev/fpgadrv0; "
            "test \"$(cat /sys/module/fpgadrv/refcnt)\" = 0; "
            "test -z \"$(fuser /dev/fpgadrv0 2>/dev/null || true)\"; "
            "test -d {source}; test ! -L {source}; "
            "test \"$(realpath {source})\" = {source}; "
            "test \"$(findmnt -n -o FSTYPE /media/root/ESD-USB3)\" = vfat; "
            "! pgrep -x make >/dev/null; ! pgrep -x gcc >/dev/null; "
            "! pgrep -x cc1 >/dev/null; ! pgrep -x ld >/dev/null; "
            "test ! -e {archive}; mkdir -p {usb}; "
            "du -sk {source}; find {source} -xdev | wc -l; df -Pk /root /media/root/ESD-USB3".format(
                boot=BOOT, source=SOURCE, archive=ARCHIVE, usb=USB_ROOT), report)
        run(client, "create-and-verify-kernel-archive",
            "set -eu; tar -czpf {archive} -C /root board-debug-kernel-20261004; "
            "test -s {archive}; tar -tzf {archive} >/dev/null; "
            "tar -dzf {archive} -C /root; "
            "echo ARCHIVE_BYTES=$(stat -c %s {archive}); "
            "echo ARCHIVE_ENTRIES=$(tar -tzf {archive} | wc -l); "
            "sha256sum {archive}; sync; df -Pk /media/root/ESD-USB3; "
            "echo KERNEL_TREE_ARCHIVE_VERIFIED".format(archive=ARCHIVE), report, 1800)
        archive_line = [line for line in report["commands"][-1]["stdout"].splitlines()
                        if line.endswith("  " + ARCHIVE)]
        if len(archive_line) != 1:
            raise RuntimeError("verified archive SHA line is missing")
        report["archive_sha256"] = archive_line[0].split()[0]
        run(client, "remove-migrated-kernel-tree",
            "set -eu; test -s {archive}; tar -tzf {archive} >/dev/null; "
            "rm -rf -- {source}; test ! -e {source}; sync; df -Pk /root".format(
                archive=ARCHIVE, source=SOURCE), report, 600)
        run(client, "migration-postflight",
            "set -eu; test \"$(cat /proc/sys/kernel/random/boot_id)\" = {boot}; "
            "test -d /sys/module/fpgadrv; test -c /dev/fpgadrv0; "
            "test \"$(cat /sys/module/fpgadrv/refcnt)\" = 0; "
            "test \"$(sha256sum /root/workspace/driver/fpgadrv.ko|cut -d' ' -f1)\" = {factory}; "
            "test \"$(sha256sum /root/network10-v10.2-p3-compile-003/driver/cnn_ddr_v10_p3_candidate.ko|cut -d' ' -f1)\" = {ko}; "
            "test \"$(sha256sum /root/network10-v10.2-p3-window-preupload-001/chain-parameters/manifest.json|cut -d' ' -f1)\" = {combined}; "
            "test -d /root/network10-v10.2-p3-window-preupload-001; "
            "test -d /root/network10-v10.2-p3-compile-003; "
            "test -d /root/network10-v10.1-board-window; "
            "test -d /root/network10-v10.1-ps-opt-20261007; "
            "test -d /root/network10-v10.1-ps-software-ab6-20261007; "
            "test -s {archive}; test \"$(sha256sum {archive}|cut -d' ' -f1)\" = {archive_sha}; "
            "df -hT /root /media/root/ESD-USB3; df -i /root; "
            "echo KERNEL_TREE_MIGRATED_FACTORY_AND_P3_ASSETS_PASS".format(
                boot=BOOT, factory=FACTORY_SHA, ko=P3_KO_SHA, combined=COMBINED_SHA,
                archive=ARCHIVE, archive_sha=report["archive_sha256"]), report)
        report["status"] = "PASS_KERNEL_TREE_ARCHIVED_TO_USB_ROOTFS_RECLAIMED"
    finally:
        client.close()
        report["finished_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
        raw = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode("utf-8")
        (OUT / "receipt.json").write_bytes(raw)
        print(json.dumps({"status": report.get("status", "FAILED"),
                          "receipt_sha256": hashlib.sha256(raw).hexdigest()}, sort_keys=True))


if __name__ == "__main__":
    main()
