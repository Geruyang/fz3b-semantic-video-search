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
REMOTE = "/root/workspace/network10-v10.4-pl1-iopll-lease-candidate-001"
BOOT = "3d766e07-9adf-4515-93c3-a9214190f12d"
EXPECTED_KO = "3e3643b8cb334b610095311f563cd9019b1acc886fd2c133efec063bf2a6f272"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


account = re.findall(
    r"默认账户\s+`([^`]+)`\s*/\s*`([^`]+)`", DOC.read_text(encoding="utf-8")
)[0]
env = os.environ.copy()
env.update({"FZ3B_SSH_PASSWORD": account[1], "SSH_ASKPASS": str(ASKPASS),
            "SSH_ASKPASS_REQUIRE": "force", "DISPLAY": "codex-symbol-audit"})
target = "%s@192.168.1.254" % account[0]
common = ["-o", "BatchMode=no", "-o", "ConnectTimeout=10", "-o",
          "StrictHostKeyChecking=yes", "-o", "UserKnownHostsFile=%s" % KNOWN]
command = (
    "set -eu; test \"$(cat /proc/sys/kernel/random/boot_id)\" = '%s'; "
    "cd '%s'; test \"$(sha256sum fz3b_pl1_iopll_lease.ko | cut -d' ' -f1)\" = '%s'; "
    "test ! -e /sys/module/fz3b_pl1_iopll_lease; "
    "nm -u fz3b_pl1_iopll_lease.ko | awk '{print $2}' | sort -u > required-symbols.txt; "
    ": > resolved-symbols.txt; while read sym; do grep -q -w \"$sym\" /proc/kallsyms; "
    "printf '%%s\\n' \"$sym\" >> resolved-symbols.txt; done < required-symbols.txt; "
    "cmp required-symbols.txt resolved-symbols.txt; "
    "echo REQUIRED_COUNT=$(wc -l < required-symbols.txt); cat required-symbols.txt; "
    "test ! -e /sys/module/fz3b_pl1_iopll_lease; test ! -e /dev/fz3b_pl1_iopll_lease"
    % (BOOT, REMOTE, EXPECTED_KO)
)
started = datetime.datetime.now(datetime.timezone.utc).isoformat()
result = subprocess.run(["ssh", "-T"] + common + [target, command], cwd=str(ROOT),
                        env=env, text=True, capture_output=True, timeout=60)
env["FZ3B_SSH_PASSWORD"] = ""
symbols = []
if result.returncode == 0:
    symbols = [line for line in result.stdout.splitlines()
               if line and not line.startswith("REQUIRED_COUNT=")]
receipt = {
    "schema": "fz3b-v10.4-pl1-iopll-running-kernel-symbol-audit-v1",
    "pass": result.returncode == 0,
    "hardware_execution": False,
    "module_loaded": False,
    "clock_write_performed": False,
    "boot_id": BOOT,
    "target_ko_sha256": EXPECTED_KO,
    "required_symbols": symbols,
    "command": command,
    "exit_code": result.returncode,
    "stdout": result.stdout,
    "stderr": result.stderr,
    "started_utc": started,
    "finished_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
}
out = HERE / "running-kernel-symbol-audit.json"
out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(out)
print(sha(out))
raise SystemExit(0 if receipt["pass"] else 1)
