import pathlib
import sys
import unittest


BOARD = pathlib.Path(__file__).resolve().parents[1]
if str(BOARD) not in sys.path:
    sys.path.insert(0, str(BOARD))

from run_cnn_pipeline_v8_board_window import _promote_report


class V8RunnerTests(unittest.TestCase):
    def test_promoted_report_keeps_physical_identity_and_never_claims_v6(self):
        internal = {"status": "BOARD_V6_BENCHMARK_COMPLETED",
                    "execution": "board_linux_ioctl_fzv6",
                    "pl_clock": {"hz": 1}}
        identity = {"core_id": 0x465A5638, "core_abi": 0x00080000,
                    "abi_version": 8, "profile_count": 3}
        clock = {"hz": 123.5, "fclk0_hz_measured": 101}
        result = _promote_report(internal, identity, clock)
        self.assertEqual(result["status"], "BOARD_V8_BENCHMARK_COMPLETED")
        self.assertEqual(result["execution"],
                         "board_linux_ioctl_fzv8_abi6_normal")
        self.assertEqual(result["physical_identity"], identity)
        self.assertFalse(result["compatibility_base"]["bridge_profiles_present"])
        self.assertEqual(result["pl_clock"], clock)

    def test_promote_rejects_an_unvalidated_internal_report(self):
        with self.assertRaisesRegex(ValueError, "incomplete"):
            _promote_report({"status": "FAILED"}, {}, {})


if __name__ == "__main__":
    unittest.main()
