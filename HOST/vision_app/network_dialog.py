"""Native host Ethernet settings; UAC applies only to the small helper."""
import ipaddress
import os
from pathlib import Path
from PySide6.QtCore import QThread, QTimer, Signal
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QComboBox, QLineEdit, QPushButton, QMessageBox
from . import host_network


class NetworkWorker(QThread):
    ready = Signal(object)
    failed = Signal(str)

    def __init__(self, parent, request=None, history=None):
        super().__init__(parent)
        self.request, self.history = request, history

    def run(self):
        try:
            if self.request is None:
                self.ready.emit({'inventory': host_network.inventory()})
            else:
                path = host_network.create_job(self.request, self.history)
                self.ready.emit(host_network.elevate(path))
        except Exception as exc:
            self.failed.emit(str(exc))


class NetworkDialog(QDialog):
    configured = Signal(str)

    def __init__(self, parent, board_ip='', history=None):
        super().__init__(parent)
        self.setWindowTitle('主机网口 · 板卡直连')
        self.resize(730, 660)
        self.setMinimumSize(660, 620)
        self.nics, self.worker, self.busy, self.history = [], None, False, history
        layout = QVBoxLayout(self)
        title = QLabel('配置 Windows 主机网口')
        title.setObjectName('title')
        layout.addWidget(title)
        description = QLabel('选择连接板卡的物理有线网口。设置仅在本次 Windows 会话生效；重启后使用系统原配置。')
        description.setWordWrap(True)
        layout.addWidget(description)
        adapter_row = QHBoxLayout()
        self.adapters = QComboBox()
        self.adapters.setAccessibleName('主机物理有线网口')
        self.adapters.currentIndexChanged.connect(self.selection_changed)
        self.refresh_button = QPushButton('刷新网口')
        self.refresh_button.clicked.connect(self.refresh)
        adapter_row.addWidget(self.adapters, 1)
        adapter_row.addWidget(self.refresh_button)
        layout.addLayout(adapter_row)
        self.current = QLabel('正在读取主机网口…')
        self.current.setWordWrap(True)
        layout.addWidget(self.current)
        form = QFormLayout()
        self.preset = QComboBox()
        self.preset.addItems(['常用直连 · 主机 192.168.1.10 / 板卡 192.168.1.254',
                             '当前备用直连 · 主机 169.254.220.34 / 板卡 169.254.220.254', '自定义地址'])
        self.ip = QLineEdit('192.168.1.10')
        self.mask = QLineEdit('255.255.255.0')
        self.board = QLineEdit(board_ip or '192.168.1.254')
        self.board.setToolTip('设置成功后把这个地址填回客户端连接栏')
        for label, widget in [('直连预设', self.preset), ('主机 IPv4', self.ip), ('子网掩码 / 前缀', self.mask), ('板卡 IPv4', self.board)]:
            form.addRow(label, widget)
        layout.addLayout(form)
        self.preset.currentIndexChanged.connect(self.use_preset)
        for field in (self.ip, self.mask, self.board):
            field.textChanged.connect(self.validate)
            field.textEdited.connect(lambda _: self.preset.setCurrentIndex(2))
        if board_ip.startswith('169.254.'):
            self.preset.setCurrentIndex(1)
        else:
            self.use_preset(0)
        self.validation = QLabel('')
        self.validation.setWordWrap(True)
        layout.addWidget(self.validation)
        row = QHBoxLayout()
        self.apply_button = QPushButton('一键配置直连网口')
        self.dhcp_button = QPushButton('自动获取 IPv4（DHCP）…')
        self.restore_button = QPushButton('恢复上次配置…')
        self.apply_button.clicked.connect(lambda: self.apply('static'))
        self.dhcp_button.clicked.connect(lambda: self.apply('dhcp'))
        self.restore_button.clicked.connect(lambda: self.apply('restore'))
        for button in (self.apply_button, self.dhcp_button, self.restore_button):
            row.addWidget(button)
        layout.addLayout(row)
        note = QLabel('确认上方网口和地址后，点击“一键配置直连网口”，Windows会弹出管理员授权。静态地址保留原有静态IPv4；不会主动设置网关或DNS。DHCP可能自动下发网络设置。无线、虚拟网卡和已有默认网关的网口不用于此直连配置。')
        note.setWordWrap(True)
        layout.addWidget(note)
        self.feedback = QLabel('')
        self.feedback.setWordWrap(True)
        layout.addWidget(self.feedback)
        layout.addStretch()
        close = QPushButton('完成')
        close.clicked.connect(self.close)
        layout.addWidget(close)
        QTimer.singleShot(0, self.refresh)

    def nic(self):
        index = self.adapters.currentIndex()
        return self.nics[index] if 0 <= index < len(self.nics) else None

    def use_preset(self, index):
        if index in (0, 1):
            host, mask, peer = [('192.168.1.10', '255.255.255.0', '192.168.1.254'),
                                ('169.254.220.34', '255.255.0.0', '169.254.220.254')][index]
            self.ip.setText(host)
            self.mask.setText(mask)
            self.board.setText(peer)

    def set_busy(self, value):
        self.busy = value
        for widget in (self.adapters, self.refresh_button, self.preset, self.ip, self.mask, self.board):
            widget.setEnabled(not value)
        self.validate()

    def refresh(self):
        if self.worker and self.worker.isRunning():
            return
        self.feedback.setText('正在读取网口状态…')
        self.set_busy(True)
        self.worker = NetworkWorker(self)
        self.worker.ready.connect(self.received)
        self.worker.failed.connect(self.failed)
        self.worker.start()

    def selection_changed(self, *_):
        nic = self.nic()
        if nic:
            addresses = '，'.join('%s/%d' % (ip['ip'], ip['prefix']) for ip in nic['addresses']) or '尚无 IPv4 地址'
            self.current.setText('%s · %s\nMAC %s · 接口 #%d\n当前 IPv4：%s\nDHCP：%s' %
                                 (nic['description'], nic['status'], nic['mac'], nic['index'], addresses, '自动获取' if nic['dhcp'] == 'Enabled' else '关闭'))
        else:
            self.current.setText('未找到物理有线网口；请连接或在 Windows 中启用网卡')
        self.validate()

    def validate(self, *_):
        if not hasattr(self, 'apply_button'):
            return
        nic, valid, allowed = self.nic(), False, False
        text = ''
        if nic and not self.busy:
            try:
                host_network.check_nic(nic)
                allowed = True
                host_network.make_request(nic, 'static', self.ip.text().strip(), self.mask.text().strip(), self.board.text().strip())
                valid = True
                prefix = ipaddress.IPv4Network('0.0.0.0/' + self.mask.text().strip()).prefixlen
                text = '直连子网 /%d · 修改前配置会自动保存，可恢复' % prefix
            except (ValueError, KeyError) as exc:
                text = str(exc)
        self.apply_button.setEnabled(valid and not self.busy)
        self.dhcp_button.setEnabled(allowed and not self.busy)
        backup = host_network.last_backup(nic['guid'], self.history) if nic else None
        self.restore_button.setEnabled(allowed and backup is not None and not self.busy)
        self.validation.setText(text)

    def apply(self, action):
        if self.busy or not self.nic():
            return
        try:
            nic = self.nic()
            backup = host_network.last_backup(nic['guid'], self.history) if action == 'restore' else None
            request = host_network.make_request(nic, action, self.ip.text().strip(), self.mask.text().strip(),
                                                self.board.text().strip() if action == 'static' else '', backup)
            operation = {'static': '添加 %s/%s 并关闭该网口 DHCP（保留原有静态地址）' % (request.get('address', ''), request.get('prefix', '')),
                         'dhcp': '移除该网口的当前静态 IPv4，并启用 DHCP',
                         'restore': '恢复该网口上次修改前的 DHCP 模式与静态 IPv4'}[action]
            preview = '网口：%s\nMAC：%s\n操作：%s\n\n作用：本次 Windows 会话。网络连接可能短暂中断。\n确认后将弹出 Windows 管理员授权。' % (nic['name'], nic['mac'], operation)
            if action != 'static' and QMessageBox.question(self, '确认网口配置', preview, QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
                return
            self.pending_board_ip = request['board_ip']
            self.set_busy(True)
            self.feedback.setText('等待 Windows 管理员授权并应用设置…')
            self.worker = NetworkWorker(self, request, self.history)
            self.worker.ready.connect(self.received)
            self.worker.failed.connect(self.failed)
            self.worker.start()
        except (ValueError, KeyError) as exc:
            self.feedback.setText(str(exc))

    def received(self, result):
        self.set_busy(False)
        if 'inventory' in result:
            selected = self.nic()['guid'] if self.nic() else None
            self.nics = result['inventory']
            self.adapters.blockSignals(True)
            self.adapters.clear()
            for nic in self.nics:
                self.adapters.addItem('%s · %s' % (nic['name'], nic['status']))
            chosen = next((i for i, n in enumerate(self.nics) if n['guid'] == selected), 0)
            self.adapters.setCurrentIndex(chosen if self.nics else -1)
            self.adapters.blockSignals(False)
            self.selection_changed()
            self.feedback.setText(getattr(self, 'last_outcome', '读取完成；应用设置时才会请求管理员权限'))
        else:
            if result.get('ok'):
                self.feedback.setText('设置已应用并读回。可返回主界面连接板卡；DHCP 地址可能需要等待。')
                self.configured.emit(self.pending_board_ip)
            else:
                text = result.get('error', '设置失败')
                if result.get('rollback'):
                    text += '\n恢复结果：' + result['rollback']
                self.feedback.setText(text)
            # Update the inventory without replacing the action outcome text.
            outcome = self.feedback.text()
            QTimer.singleShot(150, lambda: self.refresh_with_outcome(outcome))

    def refresh_with_outcome(self, text):
        self.last_outcome = text
        self.refresh()

    def failed(self, text):
        self.set_busy(False)
        self.feedback.setText(text)

    def closeEvent(self, event):
        if self.busy or (self.worker and self.worker.isRunning()):
            self.feedback.setText('操作正在进行，请等待结果后关闭')
            event.ignore()
        else:
            super().closeEvent(event)

    def done(self, result):
        # Esc/reject/accept bypass QWidget.closeEvent in a modal QDialog.
        if self.busy or (self.worker and self.worker.isRunning()):
            self.feedback.setText('操作正在进行，请等待结果后关闭')
            return
        super().done(result)

    def reject(self):
        self.done(QDialog.Rejected)

    def accept(self):
        self.done(QDialog.Accepted)
