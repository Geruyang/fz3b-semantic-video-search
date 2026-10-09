from __future__ import print_function

import argparse
import fcntl
import json
import os
import struct
import time


IOC_BEGIN = 0x00004D01
IOC_FINALIZE = 0x00004D02
IOC_STATUS = 0x80404D03
STATUS = struct.Struct("<IIIIIIIIIIiIQII")
FIELDS = (
    "version", "flags", "pl0_ref_ctrl", "pl1_ref_ctrl",
    "pl2_ref_ctrl", "pl3_ref_ctrl", "iopll_ctrl", "pll_status",
    "rpll_ctrl", "ddr_ctrl", "last_error", "begin_count",
    "iopll_rate_hz", "reserved0", "reserved1",
)

ENTRY = {
    "pl0_ref_ctrl": 0x01010802,
    "pl1_ref_ctrl": 0x00052000,
    "pl2_ref_ctrl": 0x00052000,
    "pl3_ref_ctrl": 0x00052000,
    "iopll_ctrl": 0x00015A00,
    "rpll_ctrl": 0x00013000,
    "ddr_ctrl": 0x01000200,
    "pll_status": 0x0000001B,
}


def get_status(fd):
    payload = bytearray(STATUS.size)
    fcntl.ioctl(fd, IOC_STATUS, payload, True)
    return dict(zip(FIELDS, STATUS.unpack(bytes(payload))))


def validate_status(status, expected_flags, expected_begin_count):
    if status["version"] != 2:
        raise RuntimeError("unexpected lease ABI version")
    if status["flags"] != expected_flags:
        raise RuntimeError("unexpected lease flags: 0x%08x" % status["flags"])
    for field, expected in ENTRY.items():
        if status[field] != expected:
            raise RuntimeError(
                "%s mismatch: 0x%08x != 0x%08x" %
                (field, status[field], expected))
    if status["last_error"] != 0:
        raise RuntimeError("lease reports last_error=%d" % status["last_error"])
    if status["begin_count"] != expected_begin_count:
        raise RuntimeError("unexpected begin_count")
    if status["iopll_rate_hz"] != 1499999985:
        raise RuntimeError("unexpected IOPLL rate")


def atomic_json(path, value):
    temporary = path + ".tmp"
    with open(temporary, "w") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.rename(temporary, path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", default="/dev/fz3b_pl1_iopll_lease")
    parser.add_argument("--ready", required=True)
    parser.add_argument("--command", required=True)
    parser.add_argument("--result", required=True)
    parser.add_argument("--timeout", type=float, default=600.0)
    args = parser.parse_args()

    result = {
        "schema": "fz3b-pl1-iopll-jtag-hold-v1",
        "status": "STARTED",
        "pass": False,
        "finalize_requested": False,
        "target_pl1_ref_ctrl": "0x01010f00",
    }
    fd = os.open(args.device, os.O_RDWR | os.O_CLOEXEC)
    begun = False
    try:
        result["opened"] = get_status(fd)
        validate_status(result["opened"], 0x23, 0)
        fcntl.ioctl(fd, IOC_BEGIN)
        begun = True
        result["begun"] = get_status(fd)
        validate_status(result["begun"], 0x27, 1)
        result["status"] = "READY_FOR_PL1_JTAG_TRANSACTION"
        atomic_json(args.ready, result)

        deadline = time.monotonic() + args.timeout
        while True:
            if os.path.exists(args.command):
                with open(args.command, "r") as handle:
                    command = handle.read().strip()
                if command != "FINALIZE":
                    raise RuntimeError("unexpected command: " + command)
                result["finalize_requested"] = True
                break
            if time.monotonic() >= deadline:
                raise RuntimeError("JTAG transaction command timeout")
            time.sleep(0.01)

        # The external orchestrator may request FINALIZE only after the JTAG
        # receipt proves PL1 and every protected raw register are restored.
        fcntl.ioctl(fd, IOC_FINALIZE)
        begun = False
        result["finalized"] = get_status(fd)
        validate_status(result["finalized"], 0x23, 1)
        result["status"] = "PASS_FINALIZED"
        result["pass"] = True
    except Exception as error:
        result["error"] = repr(error)
        result["status"] = "FAIL_CLOSED_WITHOUT_FINALIZE"
        raise
    finally:
        # Do not auto-finalize an active transaction. If JTAG state is unknown,
        # close makes the kernel retain the IOPLL reference and quarantine.
        os.close(fd)
        atomic_json(args.result, result)


if __name__ == "__main__":
    main()
