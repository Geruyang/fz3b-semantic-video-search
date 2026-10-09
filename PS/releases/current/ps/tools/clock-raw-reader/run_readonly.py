from __future__ import print_function

import datetime
import hashlib
import importlib.util
import json
import pathlib
import shlex

HERE = pathlib.Path(__file__).resolve().parent
REPO = pathlib.Path("E:/AIProject/FPGAVibecoding")
HELPER_PATH = REPO / (
    "artifacts/board-debug-20261008/acceleration/network/"
    "network10-v10.4-a0004-board-exact-003/run_exact.py"
)
REMOTE = "/root/workspace/network10-v10.4-clock-raw-baseline-001"

spec = importlib.util.spec_from_file_location("board_exact", str(HELPER_PATH))
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)


def q(value):
    return shlex.quote(str(value))


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    source = HERE / "read_fz3b_clock_registers.c"
    result = {
        "schema": "fz3b-clock-raw-baseline-v1",
        "status": "STARTED",
        "pass": False,
        "hardware_writes": False,
        "source": {"path": str(source), "bytes": source.stat().st_size, "sha256": sha256(source)},
        "commands": [],
        "started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    channel = helper.connect()
    try:
        sftp = channel.open_sftp()
        helper.run(channel, result["commands"], "prepare", "set -eu; mkdir -p " + q(REMOTE))
        sftp.put(str(source), REMOTE + "/read_fz3b_clock_registers.c")
        sftp.close()
        helper.run(
            channel,
            result["commands"],
            "compile",
            "set -eu; cd " + q(REMOTE) + "; "
            "sha256sum read_fz3b_clock_registers.c; "
            "gcc -std=c11 -O2 -Wall -Wextra -Werror read_fz3b_clock_registers.c -o read_fz3b_clock_registers; "
            "test -x read_fz3b_clock_registers; "
            "sha256sum read_fz3b_clock_registers; "
            "objdump -d read_fz3b_clock_registers | grep -E 'ldr[[:space:]]+w' | head -20",
        )
        helper.run(
            channel,
            result["commands"],
            "raw-clock-registers",
            "set -eu; " + q(REMOTE + "/read_fz3b_clock_registers") + "; "
            "echo RAW_CLOCK_REGISTER_READ_PASS",
        )
        helper.run(
            channel,
            result["commands"],
            "clock-and-policy-state",
            "set -eu; p=/sys/devices/system/cpu/cpufreq/policy0; "
            "echo BOOT_ID=$(cat /proc/sys/kernel/random/boot_id); "
            "for f in scaling_cur_freq cpuinfo_cur_freq scaling_setspeed scaling_governor scaling_min_freq scaling_max_freq scaling_available_frequencies; do "
            "printf '%s=' $f; cat $p/$f; done; "
            "echo CLOCKS_BEGIN; "
            "grep -E '(^|[[:space:]])(acpu|acpu_half|apll|dpll|ddr_ref|iopll|rpll|pl0_ref)(_|[[:space:]])' /sys/kernel/debug/clk/clk_summary; "
            "echo CLOCKS_END; "
            "test \"$(cat $p/scaling_cur_freq)\" = 1066666; "
            "test -d /sys/module/fpgadrv; test \"$(cat /sys/module/fpgadrv/refcnt)\" = 0; "
            "echo CLOCK_POLICY_BASELINE_PASS",
        )
        result["status"] = "PASS"
        result["pass"] = True
    except Exception as exc:
        result["status"] = "FAIL"
        result["error"] = repr(exc)
        raise
    finally:
        channel.close()
        result["finished_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        raw = (json.dumps(result, indent=2, sort_keys=True) + "\n").encode("utf-8")
        path = HERE / "receipt.json"
        path.write_bytes(raw)
        print(json.dumps({
            "status": result["status"],
            "path": str(path),
            "receipt_sha256": hashlib.sha256(raw).hexdigest(),
        }, sort_keys=True))


if __name__ == "__main__":
    main()
