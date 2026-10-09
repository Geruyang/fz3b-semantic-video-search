from __future__ import print_function

import argparse
import fcntl
import json
import os
import struct


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


def get_status(fd):
    payload = bytearray(STATUS.size)
    fcntl.ioctl(fd, IOC_STATUS, payload, True)
    return dict(zip(FIELDS, STATUS.unpack(bytes(payload))))


def check(status, flags, begin_count):
    assert status["version"] == 2
    assert status["flags"] == flags
    assert status["pl0_ref_ctrl"] == 0x01010802
    assert status["pl1_ref_ctrl"] == 0x00052000
    assert status["pl2_ref_ctrl"] == 0x00052000
    assert status["pl3_ref_ctrl"] == 0x00052000
    assert status["iopll_ctrl"] == 0x00015A00
    assert status["rpll_ctrl"] == 0x00013000
    assert status["ddr_ctrl"] == 0x01000200
    assert status["pll_status"] == 0x0000001B
    assert status["last_error"] == 0
    assert status["begin_count"] == begin_count
    assert status["iopll_rate_hz"] == 1499999985


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", default="/dev/fz3b_pl1_iopll_lease")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = {"schema": "fz3b-pl1-iopll-no-write-gate-v1", "pass": False}
    fd = os.open(args.device, os.O_RDWR | os.O_CLOEXEC)
    begun = False
    try:
        result["opened"] = get_status(fd)
        check(result["opened"], 0x23, 0)
        fcntl.ioctl(fd, IOC_BEGIN)
        begun = True
        result["begun"] = get_status(fd)
        check(result["begun"], 0x27, 1)
        fcntl.ioctl(fd, IOC_FINALIZE)
        begun = False
        result["finalized"] = get_status(fd)
        check(result["finalized"], 0x23, 1)
        result["pass"] = True
    finally:
        if begun:
            try:
                fcntl.ioctl(fd, IOC_FINALIZE)
                result["finally_finalized"] = get_status(fd)
            except Exception as error:
                result["finally_finalize_error"] = repr(error)
        os.close(fd)
        temporary = args.output + ".tmp"
        with open(temporary, "w") as handle:
            json.dump(result, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.rename(temporary, args.output)


if __name__ == "__main__":
    main()
