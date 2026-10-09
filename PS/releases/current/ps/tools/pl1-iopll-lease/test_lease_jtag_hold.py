from __future__ import print_function

import importlib.util
import pathlib
import sys
import types
import unittest


HERE = pathlib.Path(__file__).resolve().parent
if "fcntl" not in sys.modules:
    sys.modules["fcntl"] = types.SimpleNamespace(ioctl=None)
SPEC = importlib.util.spec_from_file_location(
    "lease_jtag_hold", str(HERE / "lease_jtag_hold.py"))
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class LeaseJtagHoldTests(unittest.TestCase):
    def status(self, flags, count):
        value = dict(MODULE.ENTRY)
        value.update({
            "version": 2,
            "flags": flags,
            "last_error": 0,
            "begin_count": count,
            "iopll_rate_hz": 1499999985,
            "reserved0": 0,
            "reserved1": 0,
        })
        return value

    def test_opened_and_begun_contracts(self):
        MODULE.validate_status(self.status(0x23, 0), 0x23, 0)
        MODULE.validate_status(self.status(0x27, 1), 0x27, 1)

    def test_rejects_target_or_unrestored_pl1(self):
        value = self.status(0x27, 1)
        value["pl1_ref_ctrl"] = 0x01010F00
        with self.assertRaises(RuntimeError):
            MODULE.validate_status(value, 0x27, 1)

    def test_uapi_layout(self):
        self.assertEqual(MODULE.STATUS.size, 64)
        self.assertEqual(MODULE.IOC_STATUS, 0x80404D03)


if __name__ == "__main__":
    unittest.main()
