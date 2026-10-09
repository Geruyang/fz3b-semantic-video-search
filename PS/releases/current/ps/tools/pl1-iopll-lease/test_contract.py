import pathlib
import re
import unittest


HERE = pathlib.Path(__file__).resolve().parent
SRC = (HERE / "fz3b_pl1_iopll_lease.c").read_text(encoding="utf-8")
UAPI = (HERE / "fz3b_pl1_iopll_lease_uapi.h").read_text(encoding="utf-8")


class ContractTests(unittest.TestCase):
    def test_all_four_pl_branches_are_guarded(self):
        for index, offset in enumerate(("0xC0U", "0xC4U", "0xC8U", "0xCCU")):
            self.assertIn(f"#define CRL_APB_PL{index}_REF_CTRL {offset}", SRC)
            self.assertIn(f"status.pl{index}_ref_ctrl", SRC)
            self.assertRegex(SRC, rf"pl\[{index}\] == baseline_pl\[{index}\]")
        self.assertIn("canonical_entry_state(baseline_pl)", SRC)
        self.assertIn("FZ3B_PL0_BASELINE 0x01010802U", SRC)
        self.assertIn("FZ3B_UNUSED_PL_BASELINE 0x00052000U", SRC)
        self.assertIn("status == baseline_pll_status", SRC)

    def test_release_is_fail_closed_until_exact_restore(self):
        release = SRC[SRC.index("static int lease_release"):SRC.index("static long lease_ioctl")]
        self.assertIn("transaction_active || !hardware_release_safe()", release)
        self.assertLess(release.index("hardware_release_safe"), release.index("clk_disable_unprepare"))
        self.assertIn("__module_get(THIS_MODULE)", release)
        finalize = SRC[SRC.index("case FZ3B_PL1_IOC_FINALIZE"):
                       SRC.index("case FZ3B_PL1_IOC_STATUS")]
        self.assertIn("if (!hardware_release_safe())", finalize)
        self.assertIn("transaction_active = false", finalize)

    def test_iopll_lease_has_no_clock_writes(self):
        self.assertIn("clk_prepare_enable(iopll)", SRC)
        self.assertIn("clk_disable_unprepare(iopll)", SRC)
        for forbidden in ("clk_set_rate", "clk_set_parent", "writel(", "regmap_write"):
            self.assertNotIn(forbidden, SRC)
        self.assertIn("FZ3B_IOPLL_EXPECTED_HZ 1499999985UL", SRC)

    def test_uapi_layout_contract(self):
        self.assertIn("FZ3B_PL1_IOPLL_LEASE_VERSION 2U", UAPI)
        self.assertIn("struct fz3b_pl1_iopll_lease_status", UAPI)
        self.assertIn("sizeof(struct fz3b_pl1_iopll_lease_status) != 64U", SRC)
        self.assertIn("iopll_rate_hz) != 48U", SRC)
        self.assertIn("_IOC_SIZE(FZ3B_PL1_IOC_STATUS) != 64U", SRC)

    def test_entry_requires_known_a0004_rollback_state(self):
        body = SRC[SRC.index("static bool canonical_entry_state"):
                   SRC.index("static bool hardware_release_safe")]
        self.assertEqual(len(re.findall(r"pl\[[0-3]\] ==", body)), 4)
        self.assertIn("pl[0] == FZ3B_PL0_BASELINE", body)
        for index in (1, 2, 3):
            self.assertIn(f"pl[{index}] == FZ3B_UNUSED_PL_BASELINE", body)


if __name__ == "__main__":
    unittest.main()
