#!/usr/bin/env python3
"""Read-only detailed inventory for exact V10 task-owned cleanup candidates."""
from __future__ import print_function

import datetime
import hashlib
import json
import shlex
import sys
from pathlib import Path


REPO = Path(r"E:\AIProject\FPGAVibecoding")
OUT = REPO / "artifacts/board-debug-20261007/acceleration/network/network10-v10.2-remote-cleanup-candidates-001"
BOOT = "fd395d2a-974c-4a1a-827d-568452cd8488"
CANDIDATES = [
    "/root/network10-v10.1-suffix11-selection-20261007",
    "/root/network10-v10.1-suffix6-selection-20261007",
    "/root/network10-v10.1-suffix-candidate-profile-20261007",
    "/root/network10-v10.1-suffix-candidate2-20261007",
    "/root/network10-v10.1-mixed-builder-suffix-20261007",
    "/root/network10-v10.1-ps-mixed2-20261007",
    "/root/network10-v10.1-seven-opt-20261007",
    "/root/network10-v10.2-p3-compile-001",
    "/root/network10-v10.2-p3-compile-002",
    "/root/network10-v10.1-driver-wc-compile-001",
    "/root/network10-v10.1-driver-wc-compile-002",
    "/root/network10-v10.1-n1-native-test-20261007",
    "/root/network10-v10.1-n1-native5-20261007",
    "/root/network10-v10.1-n1-native6-20261007",
]
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
        raise RuntimeError("refusing to overwrite cleanup-candidate audit")
    OUT.mkdir(parents=True)
    report = {
        "schema": "fz3b-v10.2-task-owned-cleanup-candidate-audit-v1",
        "status": "RUNNING",
        "boot_id": BOOT,
        "mode": "read_only_no_delete_no_module_no_pl_change",
        "candidate_paths": CANDIDATES,
        "commands": [],
        "started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    client = helper.connect()
    try:
        run(client, "candidate-state-and-extents",
            "set -eu; test \"$(cat /proc/sys/kernel/random/boot_id)\" = {boot}; "
            "test -d /sys/module/fpgadrv; test -c /dev/fpgadrv0; "
            "test \"$(cat /sys/module/fpgadrv/refcnt)\" = 0; "
            "for p in {paths}; do test -d \"$p\"; du -sk \"$p\"; done; "
            "echo CANDIDATE_EXTENTS_PASS".format(
                boot=BOOT, paths=" ".join(shlex.quote(p) for p in CANDIDATES)), report)
        for index, path in enumerate(CANDIDATES):
            run(client, "candidate-files-%02d" % index,
                "set -eu; p={path}; echo PATH=$p; "
                "find \"$p\" -type f -printf '%s %P\\n' | sort -k2; "
                "echo FILE_COUNT=$(find \"$p\" -type f | wc -l)".format(
                    path=shlex.quote(path)), report, 300)
        report["status"] = "PASS_READ_ONLY_CLEANUP_CANDIDATE_AUDIT"
    finally:
        client.close()
        report["finished_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
        raw = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode("utf-8")
        (OUT / "receipt.json").write_bytes(raw)
        print(json.dumps({"status": report.get("status", "FAILED"),
                          "receipt_sha256": hashlib.sha256(raw).hexdigest()}, sort_keys=True))


if __name__ == "__main__":
    main()
