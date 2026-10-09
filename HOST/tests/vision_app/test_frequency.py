import unittest


class FineFrequency(unittest.TestCase):
    def test_four_targets_stay_in_cpu_and_vco_bounds(self):
        from vision_app.frequency import pll_plan, validate_khz
        for mhz in (600,800,1000,1200):
            self.assertEqual(validate_khz(mhz*1000),mhz*1000)
            plan=pll_plan(mhz*1000)
            self.assertLessEqual(abs(plan['actual_hz']-mhz*1000000),300)
            if plan['parent']==3:
                self.assertGreaterEqual(plan['vco_hz'],1500000000)
                self.assertLessEqual(plan['vco_hz'],3000000000)
                self.assertEqual(plan['frac'],0)
                self.assertEqual(plan['generic_mode'],1)

    def test_rejects_fractional_mhz_and_out_of_range(self):
        from vision_app.frequency import validate_khz
        for value in (True,600001,601000,799000,1199000,599000,1201000,'600000',0):
            with self.assertRaises(ValueError):validate_khz(value)

    def test_fractional_cfg_differs_from_integer_baseline(self):
        from vision_app.frequency import pll_plan
        plan=pll_plan(1000000)
        self.assertEqual(plan['params'][8],3)
        self.assertEqual(plan['params'][9],2)
        self.assertEqual(plan['params'][6],625)

    def test_legacy_600_and_1200_aliases(self):
        from vision_app.frequency import validate_khz
        self.assertEqual(validate_khz(599999),600000)
        self.assertEqual(validate_khz(1199999),1200000)
