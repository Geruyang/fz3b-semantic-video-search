#!/usr/bin/env python3
"""Resume the P3 preupload after the Windows CRLF checksum-list failure.

The first staging attempt uploaded all payload files before sha256sum rejected
the CRLF list.  This script uploads only a canonical LF list and performs the
remaining read-only target checks.  It never changes module or PL state.
"""
from __future__ import print_function

import datetime
import hashlib
import json
import sys
from pathlib import Path


REPO = Path(r"E:\AIProject\FPGAVibecoding")
SOURCE = REPO / "artifacts/board-debug-20261007/acceleration/network/network10-v10.2-p3-window-preupload-001/receipt.json"
OUT = REPO / "artifacts/board-debug-20261007/acceleration/network/network10-v10.2-p3-window-preupload-resume-002"
REMOTE = "/root/network10-v10.2-p3-window-preupload-001"
INCOMPLETE_RETRY = "/root/network10-v10.2-p3-window-preupload-002"
BOOT = "fd395d2a-974c-4a1a-827d-568452cd8488"
FACTORY_DRIVER_SHA = "a482b11d47a117e60f98efd43631b45a3a33ba98e81ff610204d2f301dbb0b6f"
RUNNER_SHA = "0a8a94e2d553508baa958a741ea8d0e5c9f68d1f2a589d75d64860c825fc4f96"
COMBINED_SHA = "c62b9f49b1118916168a2ca7a4a63c56d51bba66a0921523af35d46495bbab99"
KO_SHA = "b166879d3773f915d361c2579aeac15bd7126ed99243879f5eb063f2c758c5ca"

sys.path.insert(0, str(REPO / "artifacts/board-debug-20261004/acceleration/network"))
import dma_driver_rebuild as helper


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(client, name, command, report, timeout=180):
    result = helper.run(client, name, command, timeout)
    report["commands"].append(result)
    if result["exit_code"]:
        raise RuntimeError("%s failed: %s\n%s" %
                           (name, result["stdout"], result["stderr"]))
    return result


def main():
    if OUT.exists():
        raise RuntimeError("refusing to overwrite resumed P3 preupload evidence")
    OUT.mkdir(parents=True)
    source_raw = SOURCE.read_bytes()
    source = json.loads(source_raw.decode("utf-8"))
    files = source.get("files")
    if (source.get("schema") != "fz3b-v10.2-p3-software-window-preupload-v1" or
            source.get("remote_root") != REMOTE or not isinstance(files, list) or
            len(files) != 67):
        raise ValueError("first preupload receipt is not the expected complete upload inventory")
    lines = []
    for item in files:
        remote = item.get("remote_path")
        digest = item.get("sha256")
        if (not isinstance(remote, str) or not remote.startswith(REMOTE + "/") or
                not isinstance(digest, str) or len(digest) != 64):
            raise ValueError("unsafe source upload inventory")
        lines.append("%s  %s" % (digest, remote))
    checksum_path = OUT / "expected-sha256.lf.txt"
    checksum_path.write_bytes(("\n".join(lines) + "\n").encode("ascii"))
    report = {
        "schema": "fz3b-v10.2-p3-software-window-preupload-resume-v1",
        "status": "RUNNING",
        "boot_id": BOOT,
        "remote_root": REMOTE,
        "resumed_from": {"path": SOURCE.relative_to(REPO).as_posix(),
                         "sha256": hashlib.sha256(source_raw).hexdigest()},
        "resume_reason": "payload upload complete; GNU sha256sum rejected CRLF path suffixes",
        "payload_file_count": len(files),
        "checksum_manifest_sha256": sha(checksum_path),
        "commands": [],
        "ready_for_programming": False,
        "missing_final_hardware_gates": source["missing_final_hardware_gates"],
        "started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    client = helper.connect()
    try:
        run(client, "resume-factory-preflight",
            "set -eu; test \"$(cat /proc/sys/kernel/random/boot_id)\" = {boot}; "
            "test -d /sys/module/fpgadrv; test -c /dev/fpgadrv0; "
            "test \"$(cat /sys/module/fpgadrv/refcnt)\" = 0; "
            "test -z \"$(fuser /dev/fpgadrv0 2>/dev/null || true)\"; "
            "test \"$(sha256sum /root/workspace/driver/fpgadrv.ko|cut -d' ' -f1)\" = {factory}; "
            "test ! -e /sys/module/cnn_ddr_v10_p3_candidate; test ! -e /dev/network10_v10_p3; "
            "test -d {remote}; df -Pk /root".format(
                boot=BOOT, factory=FACTORY_DRIVER_SHA, remote=REMOTE), report)
        run(client, "remove-owned-incomplete-retry",
            "set -eu; test -d {retry}; du -sk {retry}; "
            "rm -rf -- {retry}; test ! -e {retry}; df -Pk /root".format(
                retry=INCOMPLETE_RETRY), report)
        sftp = client.open_sftp()
        try:
            temporary = REMOTE + "/expected-sha256.txt.lf.part"
            sftp.put(str(checksum_path), temporary, confirm=True)
            sftp.posix_rename(temporary, REMOTE + "/expected-sha256.txt")
        finally:
            sftp.close()
        run(client, "resumed-uploaded-sha256",
            "set -eu; cd /; sha256sum -c %s/expected-sha256.txt" % REMOTE,
            report, 600)
        run(client, "python36-syntax-import-and-assets",
            "set -eu; cd {remote}/runtime; "
            "PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python3 -B -c \"import glob; [compile(open(p,'rb').read(),p,'exec') for p in glob.glob('*.py')]; print('P3_RUNTIME_PY36_SYNTAX_PASS')\"; "
            "PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python3 -B -c \"import benchmark_cnn_pipeline_v10_live as b; import cnn_pipeline_v10_suffix_capture as c; import evaluate_cnn_v10_p3_suffix_domain as e; import cnn_pipeline_v10_p3_runtime as p; import cnn_ddr_v10_p3_runtime as d; assert d.CORE_ABI==0x000A0002; print('P3_RUNTIME_IMPORT_PASS')\"; "
            "test ! -e __pycache__; "
            "test \"$(sha256sum /root/network10-v10.1-ps-software-ab6-20261007/bin/ort_partition_runner_v3|cut -d' ' -f1)\" = {runner}; "
            "test \"$(sha256sum {remote}/driver/cnn_ddr_v10_p3_candidate.ko|cut -d' ' -f1)\" = {ko}; "
            "test \"$(sha256sum {remote}/chain-parameters/manifest.json|cut -d' ' -f1)\" = {combined}; "
            "echo P3_PREUPLOAD_ASSETS_PASS".format(
                remote=REMOTE, runner=RUNNER_SHA, ko=KO_SHA, combined=COMBINED_SHA), report)
        run(client, "resume-factory-postflight",
            "set -eu; test \"$(cat /proc/sys/kernel/random/boot_id)\" = {boot}; "
            "test -d /sys/module/fpgadrv; test -c /dev/fpgadrv0; "
            "test \"$(cat /sys/module/fpgadrv/refcnt)\" = 0; "
            "test -z \"$(fuser /dev/fpgadrv0 2>/dev/null || true)\"; "
            "test ! -e /sys/module/cnn_ddr_v10_p3_candidate; test ! -e /dev/network10_v10_p3; "
            "echo FACTORY_UNCHANGED_P3_PREUPLOAD_ONLY".format(boot=BOOT), report)
        report["status"] = "PASS_P3_SOFTWARE_PREUPLOAD_FACTORY_UNCHANGED_NOT_READY_FOR_PROGRAMMING"
    finally:
        client.close()
        report["finished_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
        raw = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode("utf-8")
        (OUT / "receipt.json").write_bytes(raw)
        print(json.dumps({"status": report.get("status", "FAILED"),
                          "receipt_sha256": hashlib.sha256(raw).hexdigest()}, sort_keys=True))


if __name__ == "__main__":
    main()
