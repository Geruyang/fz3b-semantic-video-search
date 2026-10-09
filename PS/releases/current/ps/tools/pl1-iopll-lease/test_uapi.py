import ctypes
import pathlib
import unittest


HERE = pathlib.Path(__file__).resolve().parent
HEADER = (HERE / "fz3b_pl1_iopll_lease_uapi.h").read_text(encoding="utf-8")


class LeaseStatus(ctypes.LittleEndianStructure):
    _fields_ = [
        ("version", ctypes.c_uint32),
        ("flags", ctypes.c_uint32),
        ("pl0_ref_ctrl", ctypes.c_uint32),
        ("pl1_ref_ctrl", ctypes.c_uint32),
        ("pl2_ref_ctrl", ctypes.c_uint32),
        ("pl3_ref_ctrl", ctypes.c_uint32),
        ("iopll_ctrl", ctypes.c_uint32),
        ("pll_status", ctypes.c_uint32),
        ("rpll_ctrl", ctypes.c_uint32),
        ("ddr_ctrl", ctypes.c_uint32),
        ("last_error", ctypes.c_int32),
        ("begin_count", ctypes.c_uint32),
        ("iopll_rate_hz", ctypes.c_uint64),
        ("reserved", ctypes.c_uint32 * 2),
    ]


class LeaseUapiTests(unittest.TestCase):
    def test_status_layout(self):
        self.assertEqual(ctypes.sizeof(LeaseStatus), 64)
        expected = {
            "version": 0, "flags": 4, "pl0_ref_ctrl": 8,
            "pl1_ref_ctrl": 12, "pl2_ref_ctrl": 16,
            "pl3_ref_ctrl": 20, "iopll_ctrl": 24,
            "pll_status": 28, "rpll_ctrl": 32, "ddr_ctrl": 36,
            "last_error": 40, "begin_count": 44,
            "iopll_rate_hz": 48, "reserved": 56,
        }
        for name, offset in expected.items():
            self.assertEqual(getattr(LeaseStatus, name).offset, offset)

    def test_no_clock_write_ioctl(self):
        self.assertIn("FZ3B_PL1_IOC_BEGIN", HEADER)
        self.assertIn("FZ3B_PL1_IOC_FINALIZE", HEADER)
        self.assertIn("FZ3B_PL1_IOC_STATUS", HEADER)
        self.assertNotIn("SET_RATE", HEADER)
        self.assertNotIn("SET_PARENT", HEADER)


if __name__ == "__main__":
    unittest.main()
