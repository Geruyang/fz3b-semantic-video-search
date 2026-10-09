import datetime
import hashlib
import json
import os
import pathlib
import re
import subprocess


HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[4]
KNOWN = ROOT / "artifacts/board-debug-20261004/serial/board-known_hosts"
ASKPASS = HERE.parent / "network10-v10.4-pl-branch-readonly-audit-001/ssh_askpass.cmd"
DOC = ROOT / "docs/hardware/FZ3B/TF-LINUX-INSTALL.md"
HOST = "192.168.1.254"
REMOTE = "/root/workspace/network10-v10.4-pl1-iopll-lease-candidate-001"
KERNEL = "/root/board-debug-kernel-20261004/linux-xlnx-xilinx-v2018.3"
BOOT = "3d766e07-9adf-4515-93c3-a9214190f12d"
SOURCES = ["fz3b_pl1_iopll_lease.c", "fz3b_pl1_iopll_lease_uapi.h", "Makefile"]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


account = re.findall(
    r"默认账户\s+`([^`]+)`\s*/\s*`([^`]+)`", DOC.read_text(encoding="utf-8")
)[0]
env = os.environ.copy()
env.update({
    "FZ3B_SSH_PASSWORD": account[1],
    "SSH_ASKPASS": str(ASKPASS),
    "SSH_ASKPASS_REQUIRE": "force",
    "DISPLAY": "codex-target-compile",
})
target = "%s@%s" % (account[0], HOST)
common = [
    "-o", "BatchMode=no", "-o", "ConnectTimeout=10",
    "-o", "StrictHostKeyChecking=yes", "-o", "UserKnownHostsFile=%s" % KNOWN,
]
commands = []


def run(name, argv, timeout=180):
    result = subprocess.run(argv, cwd=str(ROOT), env=env, text=True,
                            capture_output=True, timeout=timeout)
    commands.append({"name": name, "argv": argv, "exit_code": result.returncode,
                     "stdout": result.stdout, "stderr": result.stderr})
    if result.returncode:
        raise RuntimeError("%s failed: %d" % (name, result.returncode))
    return result.stdout


started = datetime.datetime.now(datetime.timezone.utc).isoformat()
passed = False
ko_sha = None
try:
    preflight = (
        "set -eu; test \"$(cat /proc/sys/kernel/random/boot_id)\" = '%s'; "
        "test ! -e /sys/module/cnn_ddr_v10_p3_dma_candidate; "
        "test ! -e /dev/network10_v10_p3_dma; "
        "test ! -e /sys/module/fz3b_pl1_iopll_lease; "
        "test ! -e /dev/fz3b_pl1_iopll_lease; "
        "test -z \"$(pgrep -f '[o]rt_partition_runner|[b]enchmark_cnn_pipeline_v10|[r]un_cnn_pipeline_v10' || true)\"; "
        "mkdir -p '%s'" % (BOOT, REMOTE)
    )
    run("compile-preflight", ["ssh", "-T"] + common + [target, preflight])
    for name in SOURCES:
        run("upload-%s" % name, ["scp", "-q"] + common +
            [str(HERE / name), "%s:%s/%s" % (target, REMOTE, name)])
    build = (
        "set -eu; cd '%s'; "
        "make -C '%s' M='%s' ARCH=arm64 clean; "
        "make -C '%s' M='%s' ARCH=arm64 KBUILD_MODPOST_WARN=1 modules; "
        "sha256sum fz3b_pl1_iopll_lease.ko; "
        "nm -u fz3b_pl1_iopll_lease.ko; "
        "modinfo fz3b_pl1_iopll_lease.ko | grep -E '^(description|license|vermagic):'; "
        "test ! -e /sys/module/fz3b_pl1_iopll_lease; "
        "test ! -e /dev/fz3b_pl1_iopll_lease" % (REMOTE, KERNEL, REMOTE, KERNEL, REMOTE)
    )
    output = run("target-compile-only", ["ssh", "-T"] + common + [target, build])
    match = re.search(r"(?m)^([0-9a-f]{64})  fz3b_pl1_iopll_lease\.ko$", output)
    if not match:
        raise RuntimeError("KO hash missing")
    ko_sha = match.group(1)
    passed = True
finally:
    env["FZ3B_SSH_PASSWORD"] = ""
    receipt = {
        "schema": "fz3b-v10.4-pl1-iopll-lease-target-compile-v1",
        "pass": passed,
        "hardware_execution": False,
        "module_loaded": False,
        "clock_write_performed": False,
        "boot_id": BOOT,
        "remote_directory": REMOTE,
        "source_files": [
            {"path": name, "bytes": (HERE / name).stat().st_size,
             "sha256": sha(HERE / name)} for name in SOURCES
        ],
        "target_ko_sha256": ko_sha,
        "commands": commands,
        "started_utc": started,
        "finished_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    out = HERE / "target-compile-receipt.json"
    out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(out)
    print(sha(out))
if not passed:
    raise SystemExit(1)
