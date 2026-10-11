from pathlib import Path
import tempfile
import unittest
import importlib.util


class HardwareMonitorTests(unittest.TestCase):
    def monitor_type(self):
        source=Path(__file__).resolve().parents[2]/'PS/vision_app/hardware_monitor.py'
        spec=importlib.util.spec_from_file_location('hardware_monitor_fixture',source)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        return module.HardwareMonitor

    def test_raw_offset_scale_are_converted_to_celsius_and_volts(self):
        monitor_type=self.monitor_type()
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);device=root/'iio-device0';device.mkdir();(device/'name').write_text('ams')
            for stem,values in [('in_temp1_remote_temp',{'raw':42522,'offset':-36058,'scale':7.771514892}),('in_voltage8_vccpsintfp',{'raw':20000,'scale':.05})]:
                for suffix,value in values.items():(device/(stem+'_'+suffix)).write_text(str(value))
            monitor=monitor_type(str(root),pl_ready=lambda:True)
            monitor.sample();report=monitor.status()
            self.assertAlmostEqual(report['values']['cpu_fpd_c'],50.234,places=2)
            self.assertAlmostEqual(report['values']['ps_fpd_v'],1.,places=4)
            self.assertNotIn('pl_c',report['values'])

    def test_initializing_pl_does_not_read_any_ams_measurements(self):
        monitor=self.monitor_type()('/not-used',pl_ready=lambda:False)
        monitor.sample();report=monitor.status()
        self.assertEqual(report['values'],{})
        self.assertFalse(report['available'])

    def test_new_sample_does_not_retain_a_failed_old_reading(self):
        monitor_type=self.monitor_type()
        with tempfile.TemporaryDirectory() as d:
            device=Path(d)/'iio-device0';device.mkdir();(device/'name').write_text('ams')
            (device/'in_temp2_pl_temp_raw').write_text('42018');(device/'in_temp2_pl_temp_offset').write_text('-36058');(device/'in_temp2_pl_temp_scale').write_text('7.771514892')
            monitor=monitor_type(d,pl_ready=lambda:True);monitor.sample()
            self.assertIn('pl_c',monitor.status()['values'])
            (device/'in_temp2_pl_temp_raw').write_text('unavailable');monitor.sample()
            self.assertNotIn('pl_c',monitor.status()['values'])
