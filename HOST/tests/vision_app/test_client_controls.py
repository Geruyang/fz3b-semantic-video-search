"""Native controls with mocked transport/elevation; never changes networking."""
import unittest
from unittest.mock import patch,MagicMock
from PySide6.QtWidgets import QApplication
APP=QApplication.instance() or QApplication([])

class ClientControls(unittest.TestCase):
    def test_device_page_distinguishes_input_range_from_board_capability(self):
        from vision_app.client import Window
        window=Window()
        try:
            window.message({'type':'status','cpu':{'current_khz':1199999,'supported_khz':[600000,800000,1000000,1200000],'transition':True}})
            self.assertIn('600/800/1000/1200MHz四档',window.cpu_hint.text())
            self.assertIn('等待硬件核验',window.device_summary.text())
            window.message({'type':'status','cpu':{'current_khz':1199999,'fine_control_available':True}})
            self.assertNotIn('暂不可用',window.cpu_hint.text())
        finally:window.close()
    def test_cpu_range_step_and_mhz_to_khz_request(self):
        from vision_app.client import Window
        window=Window()
        try:
            self.assertEqual([window.cpu.itemData(i) for i in range(window.cpu.count())],[600,800,1000,1200])
            self.assertEqual(window.cpu.currentData(),1200)
            window.cpu.setCurrentIndex(1)
            with patch.object(window,'request',return_value=True) as request:
                window.cpu_apply.click()
            request.assert_called_once_with({'op':'cpu_frequency','khz':800000})
            self.assertFalse(window.cpu_apply.isEnabled())
            window.request_ids={'clock':'cpu_frequency'}
            window.message({'type':'ack','request_id':'clock','op':'cpu_frequency','ok':True,'result':{'inference_resumed':True}})
            self.assertTrue(window.cpu_apply.isEnabled())
        finally:window.close()

    def test_one_click_static_goes_to_elevation_worker_without_extra_confirm(self):
        from vision_app.network_dialog import NetworkDialog
        from vision_app.tests.test_host_network import HostNetworkContract
        nic=dict(HostNetworkContract().nic(),description='Test physical NIC',status='Up')
        with patch('vision_app.network_dialog.QTimer.singleShot'),patch('vision_app.network_dialog.host_network.last_backup',return_value=None),patch('vision_app.network_dialog.NetworkWorker') as worker,patch('vision_app.network_dialog.QMessageBox.question') as confirm:
            dialog=NetworkDialog(None,'192.168.1.254')
            try:
                dialog.nics=[nic];dialog.adapters.addItem('Test')
                self.assertTrue(dialog.apply_button.isEnabled())
                dialog.apply_button.click()
                confirm.assert_not_called()
                args=worker.call_args.args
                self.assertEqual(args[1]['action'],'static')
                self.assertEqual(args[1]['address'],'192.168.1.10')
                worker.return_value.start.assert_called_once()
            finally:
                dialog.worker=None;dialog.busy=False;dialog.close()
