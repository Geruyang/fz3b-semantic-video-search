import json
from pathlib import Path
import tempfile
import unittest


class BootContract(unittest.TestCase):
    def nodes(self, state='running'):
        return [{'path': '/sys/class/remoteproc/remoteproc%d' % i,
                 'realpath': '/platform/ff9a0%d00.app-r5%d/remoteproc/remoteproc%d' % (i+1, i, i),
                 'state': state, 'firmware': 'fz3b-app-r5%d.elf' % i} for i in range(2)]

    def test_startup_rejects_unknown_and_partial_r5_owners(self):
        from vision_app.r5_start import startup_decision
        self.assertEqual(startup_decision([]), 'start')
        self.assertEqual(startup_decision(self.nodes('offline')), 'start')
        self.assertEqual(startup_decision(self.nodes()), 'verify')
        for nodes in (self.nodes()[:1], self.nodes() + self.nodes()[:1]):
            with self.assertRaises(ValueError):
                startup_decision(nodes)
        nodes = self.nodes()
        nodes[0]['firmware'] = 'other-owner.elf'
        with self.assertRaises(ValueError):
            startup_decision(nodes)
        nodes = self.nodes()
        nodes[0]['state'] = 'offline'
        with self.assertRaises(ValueError):
            startup_decision(nodes)

    def test_boot_marker_must_belong_to_this_boot(self):
        from vision_app.r5_start import qualified_boot
        with tempfile.TemporaryDirectory() as folder:
            marker = Path(folder, 'ready.json')
            self.assertFalse(qualified_boot(str(marker), 'current'))
            marker.write_text(json.dumps({'boot_id': 'old', 'ok': True}))
            self.assertFalse(qualified_boot(str(marker), 'current'))
            marker.write_text(json.dumps({'boot_id': 'current', 'ok': False}))
            self.assertFalse(qualified_boot(str(marker), 'current'))
            marker.write_text(json.dumps({'boot_id': 'current', 'ok': True}))
            self.assertTrue(qualified_boot(str(marker), 'current'))

    def test_service_orders_r5_and_application_shutdown(self):
        from vision_app.boot_units import r5_unit, application_unit
        r5 = r5_unit('/root/test')
        app = application_unit('/root/test', boot=True)
        self.assertIn('Requires=fz3b-pl-loader.service', r5)
        self.assertIn('After=fz3b-pl-loader.service', r5)
        self.assertIn('RemainAfterExit=yes', r5)
        self.assertIn('ExecStop=', r5)
        self.assertIn('fz3b-app-r5.service', app.split('Requires=')[1].splitlines()[0])
        self.assertIn('TimeoutStopSec=360', app)
        self.assertIn('SendSIGKILL=no', app)
        self.assertIn('vision_app.link_setup', app)

    def test_cpu_waits_for_platform_and_notifies_before_application(self):
        from vision_app.boot_units import cpu_unit, application_unit
        clock = cpu_unit('/root/test')
        app = application_unit('/root/test', boot=True, cpu_clock=True)
        self.assertIn('fz3b-app-r5.service', clock.split('After=')[1].splitlines()[0])
        self.assertIn('Type=notify', clock)
        self.assertIn('TimeoutStartSec=60', clock)
        self.assertIn('fz3b-app-cpu-clock.service', app.split('After=')[1].splitlines()[0])

    def test_bridge_locks_before_inspecting_power_state(self):
        from unittest.mock import patch, MagicMock
        from vision_app.r5_bridge import R5Bridge
        events = []
        owner = MagicMock()
        owner.close.side_effect = lambda: events.append('close')
        def lock():
            events.append('lock')
            return owner
        def inspect(*args):
            events.append('inspect')
            return []
        with patch('vision_app.r5_bridge.acquire_owner', side_effect=lock, create=True), patch('vision_app.r5_bridge.glob.glob', side_effect=inspect):
            with self.assertRaisesRegex(RuntimeError, 'not qualified'):
                R5Bridge()
        self.assertEqual(events, ['lock', 'inspect', 'close'])

    def test_loader_waits_for_rpc_and_ready_identity(self):
        from unittest.mock import patch
        import subprocess
        from vision_app.r5_start import wait_loader
        outputs = [subprocess.CalledProcessError(1, 'status'),
                   json.dumps({'result': {'ready': False, 'status': 'STARTING'}}).encode(),
                   json.dumps({'result': {'ready': True, 'status': 'READY_A0005'}}).encode()]
        with patch('vision_app.r5_start.subprocess.check_output', side_effect=outputs) as rpc, patch('vision_app.r5_start.time.sleep'):
            self.assertTrue(wait_loader()['result']['ready'])
            self.assertEqual(rpc.call_count, 3)

    def test_diagnostic_failure_cannot_skip_installation_rollback(self):
        from unittest.mock import patch
        from vision_app.tools.install_boot import recover_failure
        record, snapshot, client = {}, {'files': []}, object()
        with patch('vision_app.tools.install_boot.run', side_effect=RuntimeError('diagnostic unavailable')), patch('vision_app.tools.install_boot.restore_state', return_value={'ok': True}) as restore:
            recover_failure(client, snapshot, record)
            restore.assert_called_once_with(client, snapshot)
        self.assertTrue(record['rollback']['ok'])
        self.assertEqual(record['failure_log_error'], 'diagnostic unavailable')


if __name__ == '__main__':
    unittest.main()
