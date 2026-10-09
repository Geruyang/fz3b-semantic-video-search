import copy
import unittest


class HostNetworkContract(unittest.TestCase):
    def nic(self):
        return {'guid': '9566f5c3-ae17-4e8a-b58f-ae308d0e57aa', 'index': 14, 'mac': 'D8-43-AE-BD-40-FE',
                'name': '以太网', 'media': '802.3', 'dhcp': 'Disabled', 'default_route': False,
                'addresses': [{'ip': '169.254.220.34', 'prefix': 16, 'origin': 'Manual', 'skip': False}]}

    def test_static_plan_validates_host_address_and_mask(self):
        from vision_app.host_network import make_request
        request = make_request(self.nic(), 'static', '192.168.1.10', '255.255.255.0', '192.168.1.254')
        self.assertEqual(request['prefix'], 24)
        self.assertEqual(request['address'], '192.168.1.10')
        self.assertEqual(request['store'], 'ActiveStore')
        for ip, mask, board in [('192.168.1.254','255.255.255.0','192.168.1.254'), ('192.168.1.0','24',''), ('192.168.1.255','24',''), ('127.0.0.1','24',''), ('224.0.0.1','24',''), ('192.168.1.10','255.0.255.0',''), ('1; Remove-Item','24','')]:
            with self.assertRaises(ValueError):
                make_request(self.nic(), 'static', ip, mask, board)

    def test_only_matching_physical_ethernet_without_default_route(self):
        from vision_app.host_network import make_request, validate_request
        request = make_request(self.nic(), 'dhcp')
        self.assertEqual(validate_request(request, [self.nic()])['index'], 14)
        for field, value in [('media','Native 802.11'), ('default_route',True), ('mac','00-00-00-00-00-00'), ('index',8)]:
            nic = dict(self.nic(), **{field:value})
            with self.assertRaises(ValueError):
                validate_request(request, [nic])

    def test_network_changed_during_uac_is_rejected(self):
        from vision_app.host_network import make_request, validate_request
        request = make_request(self.nic(), 'static', '192.168.1.10', '24')
        nic = copy.deepcopy(self.nic())
        nic['addresses'][0]['ip'] = '192.168.2.10'
        with self.assertRaisesRegex(ValueError, '刷新'):
            validate_request(request, [nic])

    def test_restore_validates_backup_identity_and_addresses(self):
        from vision_app.host_network import make_request
        request = make_request(self.nic(), 'restore', backup=self.nic())
        self.assertEqual(request['restore']['dhcp'], 'Disabled')
        for backup in (dict(self.nic(), guid='63f9419a-3e17-4f85-b93d-c18cec92aa8b'),
                       dict(self.nic(), addresses=[{'ip':'224.0.0.1','prefix':24,'origin':'Manual','skip':False}])):
            with self.assertRaises(ValueError):
                make_request(self.nic(), 'restore', backup=backup)

    def test_invalid_actions_and_interface_indices_rejected(self):
        from vision_app.host_network import make_request
        with self.assertRaises(ValueError):
            make_request(self.nic(), 'run-command')
        for index in (True, -1, '14'):
            with self.assertRaises(ValueError):
                make_request(dict(self.nic(), index=index), 'dhcp')

    def test_escape_cannot_close_an_active_network_operation(self):
        from types import SimpleNamespace
        from PySide6.QtWidgets import QApplication
        from vision_app.network_dialog import NetworkDialog
        app = QApplication.instance() or QApplication([])
        dialog = NetworkDialog(None, '192.168.1.254')
        dialog.worker = SimpleNamespace(isRunning=lambda: True)
        dialog.busy = True
        dialog.show()
        dialog.reject()
        self.assertTrue(dialog.isVisible())
        dialog.worker = None
        dialog.busy = False
        dialog.close()


if __name__ == '__main__':
    unittest.main()
