import unittest
from unittest.mock import patch
from vision_app.board_agent import CpuPolicy


class VerifiedClock(unittest.TestCase):
    def test_sysfs_cache_is_separate_from_hardware(self):
        with patch('vision_app.cpu_clock_service.request', return_value={
                'actual_hz': 1199999988, 'ccf_hz': 1199999988,
                'parent': 2, 'divider': 1, 'held': True, 'verified': True}):
            policy = CpuPolicy('/absent', control_socket='/test')
            state = policy.status()
            self.assertEqual(state['current_khz'], 1199999)
            self.assertTrue(state['verified'])
            self.assertEqual(state['cached_sysfs_khz'], 0)

    def test_control_requires_hardware_verification(self):
        with patch('vision_app.cpu_clock_service.request', return_value={
                'actual_hz': 1066666656, 'verified': False}):
            with self.assertRaisesRegex(RuntimeError, 'verified'):
                CpuPolicy('/absent', control_socket='/test').set_frequency(1199999)

    def test_abi_and_invalid_frequency(self):
        from vision_app.cpu_clock_service import STATE, validate_target
        self.assertEqual(STATE.size, 40)
        self.assertEqual(validate_target(1200000),1200000)
        self.assertEqual(validate_target(800000),800000)
        self.assertEqual(validate_target(1199999),1200000)
        for value in (True, 599000,601000, 600001,1201000, '1199999', 0):
            with self.assertRaises(ValueError):
                validate_target(value)

    def test_close_checks_raw_even_when_os_close_succeeds(self):
        from vision_app.cpu_clock_service import Lease
        lease = Lease.__new__(Lease)
        lease.fd, lease.initial_raw = 123, 'original clock registers'
        with patch('vision_app.cpu_clock_service.os.close') as close, patch.object(Lease, 'read_raw', return_value='not restored', create=True):
            with self.assertRaisesRegex(RuntimeError, 'restor'):
                lease.close()
            close.assert_called_once_with(123)

    def test_fractional_status_requires_requested_frequency_and_clean_state(self):
        import struct
        from vision_app.cpu_clock_service import Lease
        lease=Lease.__new__(Lease)
        lease.fd=123
        class Fake:
            def ioctl(self,fd,op,buffer,mutate):
                buffer[:]=struct.pack('<2Q6I',799999992,1066666656,0x03000103,3,1,0,1,800000)
        lease.fcntl=Fake()
        state=lease.status()
        self.assertTrue(state['verified'])
        self.assertEqual(state['requested_khz'],800000)

    def test_permission_denial_restores_verified_default_and_reports_failure(self):
        import struct
        from vision_app.cpu_clock_service import Lease
        lease=Lease.__new__(Lease);lease.fd=123;calls=[]
        class Fake:
            def ioctl(self,fd,op,buffer,mutate=None):
                if op==0x40044301:
                    khz=struct.unpack('<I',buffer)[0];calls.append(khz)
                    if khz==800000:raise PermissionError(13,'PMU denied')
                else:
                    buffer[:]=struct.pack('<2Q6I',1199999988,1066666656,0x03000102,2,1,0,1,1200000)
        lease.fcntl=Fake()
        with self.assertRaisesRegex(RuntimeError,'1200MHz'):
            lease.set(800000)
        self.assertEqual(calls,[800000,1200000])
