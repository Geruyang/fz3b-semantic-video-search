"""Native Windows client; display and inference are independent clocks."""
import argparse
import json
import os
from pathlib import Path
import sys
import time
import traceback
import uuid
import numpy as np
from PySide6.QtCore import Qt, QThread, Signal, QObject, QTimer
from PySide6.QtGui import QImage, QPixmap, QFont
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton, QLineEdit, QComboBox, QTextEdit, QDoubleSpinBox, QSpinBox, QSplitter, QTabWidget, QListWidget, QListWidgetItem, QGroupBox, QFileDialog, QMessageBox
from .contract import load_contract
from .text_encoder import TextEncoder, PRESETS, parse_prompts
from .transports import Link
from .state import normalized
from .translation import PromptTranslator,same_intent


def resource_root():
    return Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent


class Events(QObject):
    message = Signal(object)
    error = Signal(str)


class EncoderWorker(QThread):
    ready = Signal(object)
    failed = Signal(str)

    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self.items, self.revision = None, 0

    def run(self):
        try:
            if self.owner.encoder is None:
                self.owner.encoder = TextEncoder(self.owner.contract, str(self.owner.model_root))
            items=self.owner.translator.items(self.items)
            values, identity = self.owner.encoder.encode(items)
            self.ready.emit({'op': 'queries', 'items': items, 'features': values.tolist(), 'identity': identity, 'revision': self.revision})
        except Exception as exc:
            self.failed.emit(str(exc))


class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('FZ3B Vision Console · 实时语义工作台')
        self.resize(1360, 850)
        self.setMinimumSize(1000, 670)
        self.root = resource_root()
        config_file = self.root / 'client-config.json'
        self.config = json.loads(config_file.read_text(encoding='utf-8')) if config_file.exists() else {}
        self.contract = load_contract(str(self.root / 'semantic-contract.json'))
        self.model_root = Path(self.config.get('model_root', str(self.root / 'models')))
        if not self.model_root.is_absolute():
            self.model_root = self.root / self.model_root
        self.encoder, self.link, self.status_data = None, None, {}
        self.translator=PromptTranslator()
        self.events = Events()
        self.events.message.connect(self.message)
        self.events.error.connect(self.error)
        self.worker = EncoderWorker(self)
        self.worker.ready.connect(self.encoded)
        self.worker.failed.connect(self.encoding_error)
        self.revision, self.accepted_revision, self.current_result = 0, 0, None
        self.request_ids = {}
        self.pending_start = False
        self.connection_epoch = 0
        self.preview_stamp = None
        self.pixmap = None
        self.gallery, self.gallery_ids = [], set()
        self.gallery_image_version = None
        self.fps_at, self.fps_count, self.displayed = time.monotonic(), 0, 0
        self.build_ui()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(16)

    def build_ui(self):
        central = QWidget()
        outer = QVBoxLayout(central)
        top = QHBoxLayout()
        brand = QLabel('FZ3B  /  VISION CONSOLE')
        brand.setObjectName('brand')
        top.addWidget(brand)
        top.addStretch()
        self.connection_status = QLabel('尚未连接')
        top.addWidget(self.connection_status)
        outer.addLayout(top)
        connection = QHBoxLayout()
        self.mode = QComboBox()
        self.mode.addItems(['以太网', 'USB 串口'])
        self.address = QLineEdit(self.config.get('host', '192.168.1.254'))
        self.address.setPlaceholderText('板卡 IP / COM6')
        self.mode.currentIndexChanged.connect(lambda i: self.address.setText('COM6' if i else self.config.get('host', '192.168.1.254')))
        self.token = QLineEdit(self.config.get('token', ''))
        self.token.setEchoMode(QLineEdit.Password)
        self.token.setPlaceholderText('连接令牌')
        self.connect_button = QPushButton('连接板卡')
        self.connect_button.clicked.connect(self.connect_board)
        for label, widget in [('连接', self.mode), ('地址', self.address), ('令牌', self.token)]:
            connection.addWidget(QLabel(label))
            connection.addWidget(widget)
        connection.addWidget(self.connect_button)
        network_button = QPushButton('主机网口')
        network_button.setEnabled(os.name == 'nt')
        network_button.clicked.connect(self.open_host_network)
        connection.addWidget(network_button)
        outer.addLayout(connection)
        split = QSplitter(Qt.Horizontal)
        video_area = QWidget()
        v = QVBoxLayout(video_area)
        v.setContentsMargins(0, 0, 0, 0)
        self.video = QLabel('连接板卡后显示实时视频')
        self.video.setAlignment(Qt.AlignCenter)
        self.video.setMinimumSize(540, 380)
        self.video.setObjectName('video')
        self.video.setScaledContents(False)
        self.overlay = QLabel('等待推理结果')
        self.overlay.setObjectName('overlay')
        self.overlay.setWordWrap(True)
        self.overlay.setParent(self.video)
        self.overlay.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.overlay.move(14, 14)
        self.overlay.resize(490, 60)
        v.addWidget(self.video, 1)
        bar = QHBoxLayout()
        self.metrics = QLabel('预览 — FPS   /   推理 — FPS   /   结果年龄 —')
        bar.addWidget(self.metrics)
        bar.addStretch()
        save = QPushButton('保存当前画面')
        save.clicked.connect(self.save_frame)
        bar.addWidget(save)
        v.addLayout(bar)
        self.notice = QLabel('以太网传输摄像头压缩流；推理抽帧异步运行')
        self.notice.setWordWrap(True)
        v.addWidget(self.notice)
        split.addWidget(video_area)
        tabs = QTabWidget()
        search = QWidget()
        s = QVBoxLayout(search)
        title = QLabel('用描述寻找物品与场景')
        title.setObjectName('title')
        s.addWidget(title)
        help_label = QLabel('每行一条。支持英文，或“中文标签 | English description”。\n常见中文物品名自动映射；这是整帧语义匹配。')
        help_label.setWordWrap(True)
        s.addWidget(help_label)
        self.prompts = QTextEdit()
        self.prompts.setPlainText('\n'.join(label + ' | ' + text for label, text in PRESETS))
        self.prompts.setMaximumHeight(180)
        s.addWidget(self.prompts)
        row = QHBoxLayout()
        preset = QPushButton('物品与场景预设')
        preset.clicked.connect(self.preset_classify)
        self.encode_button = QPushButton('更新描述')
        self.encode_button.clicked.connect(self.encode)
        row.addWidget(preset)
        row.addWidget(self.encode_button)
        s.addLayout(row)
        actions = QHBoxLayout()
        self.start_button = QPushButton('开始推理')
        self.start_button.clicked.connect(self.start_inference)
        stop = QPushButton('停止推理')
        stop.clicked.connect(self.stop_inference)
        actions.addWidget(self.start_button)
        actions.addWidget(stop)
        s.addLayout(actions)
        self.ranking = QListWidget()
        s.addWidget(QLabel('当前候选 · 余弦相似度'))
        s.addWidget(self.ranking, 1)
        self.query_status = QLabel('描述尚未发送')
        self.query_status.setWordWrap(True)
        s.addWidget(self.query_status)
        tabs.addTab(search, '实时识别')
        history = QWidget()
        g = QVBoxLayout(history)
        g.addWidget(QLabel('最近推理帧 · 最多保留 60 张'))
        self.gallery_query = QComboBox()
        g.addWidget(self.gallery_query)
        gallery_search = QPushButton('按所选描述检索已接收图像')
        gallery_search.clicked.connect(self.search_gallery)
        g.addWidget(gallery_search)
        self.gallery_list = QListWidget()
        self.gallery_list.itemClicked.connect(self.show_gallery)
        g.addWidget(self.gallery_list, 1)
        self.gallery_preview = QLabel('选择历史帧查看对应图像')
        self.gallery_preview.setAlignment(Qt.AlignCenter)
        self.gallery_preview.setMinimumHeight(180)
        g.addWidget(self.gallery_preview)
        tabs.addTab(history, '图文检索')
        device = QWidget()
        d = QVBoxLayout(device)
        self.device_summary = QLabel('等待设备状态')
        self.device_summary.setWordWrap(True)
        d.addWidget(self.device_summary)
        controls = QGridLayout()
        self.cpu = QComboBox()
        for mhz in (600,800,1000,1200):
            self.cpu.addItem('%d MHz'%mhz,mhz)
        self.cpu.setCurrentIndex(3)
        self.cpu.setAccessibleName('A53目标频率，600、800、1000、1200MHz四档')
        cpu_apply = QPushButton('设置频率')
        self.cpu_apply=cpu_apply
        cpu_apply.clicked.connect(self.apply_frequency)
        controls.addWidget(QLabel('A53 共享频率'), 0, 0)
        controls.addWidget(self.cpu, 0, 1)
        controls.addWidget(cpu_apply, 0, 2)
        self.threshold = QDoubleSpinBox()
        self.threshold.setRange(-1, 1)
        self.threshold.setSingleStep(.01)
        self.threshold.setValue(.2)
        controls.addWidget(QLabel('匹配阈值'), 1, 0)
        controls.addWidget(self.threshold, 1, 1)
        self.inflight = QSpinBox()
        self.inflight.setRange(1, 4)
        self.inflight.setValue(4)
        controls.addWidget(QLabel('推理在途对数'), 2, 0)
        controls.addWidget(self.inflight, 2, 1)
        apply = QPushButton('应用参数')
        apply.clicked.connect(lambda: self.request({'op': 'settings', 'threshold': self.threshold.value(), 'max_in_flight': self.inflight.value()}))
        controls.addWidget(apply, 2, 2)
        d.addLayout(controls)
        info = QLabel('调频自动暂停/排空，核验后恢复；改变在途数需先停止。\n600/800/1000/1200MHz四档，四个A53共享频率。\n阈值为工程设置，尚未做自然样本准确率校准。')
        self.cpu_hint=info
        info.setWordWrap(True)
        d.addWidget(info)
        d.addStretch()
        tabs.addTab(device, '设备参数')
        split.addWidget(tabs)
        split.setSizes([880, 410])
        outer.addWidget(split, 1)
        self.log_label = QLabel('就绪')
        self.log_label.setWordWrap(True)
        outer.addWidget(self.log_label)
        self.setCentralWidget(central)
        self.setStyleSheet('''QWidget {background:#101827;color:#E7EDF5;font-family:"Microsoft YaHei UI";font-size:13px;}
            QLineEdit,QTextEdit,QListWidget,QComboBox,QSpinBox,QDoubleSpinBox {background:#1B283C;border:1px solid #41526A;border-radius:5px;padding:7px;selection-background-color:#235EAD;}
            QPushButton {background:#245D9E;color:white;border:1px solid #3A78BE;border-radius:5px;padding:9px 14px;}
            QPushButton:hover {background:#3276BF;} QPushButton:disabled {background:#303B4D;color:#8995A8;} QPushButton:focus {border:2px solid #8BD2FF;}
            QTabBar::tab {background:#1B283C;padding:10px 16px;} QTabBar::tab:selected {background:#245D9E;}
            QLabel#video {background:#060B12;border:1px solid #41526A;} QLabel#overlay {background:rgba(8,16,28,210);color:#F2F7FF;padding:9px;border-radius:4px;}
            QLabel#brand {font-size:18px;font-weight:700;padding:9px 0;} QLabel#title {font-size:18px;font-weight:600;}
            QSplitter::handle {background:#263549;width:8px;}''')

    def connect_board(self):
        self.connection_epoch += 1
        self.pending_start = False
        self.accepted_revision = 0
        self.request_ids.clear()
        self.cpu_apply.setEnabled(True)
        if self.link:
            self.link.close()
            self.link = None
            self.connect_button.setText('连接板卡')
            self.connection_status.setText('已断开')
            self.video.setText('连接已断开')
            self.overlay.setText('连接已断开 · 推理结果停止更新')
            self.current_result = None
            self.metrics.setText('预览 — FPS   /   推理 — FPS   /   结果年龄 —')
            return
        if len(self.token.text().strip()) < 24:
            self.error('请填入部署时生成的连接令牌')
            return
        self.current_result = None
        self.preview_stamp = None
        self.gallery, self.gallery_ids = [], set()
        epoch = self.connection_epoch
        self.link = Link(lambda m: self.events.message.emit(dict(m, _connection_epoch=epoch)), self.events.error.emit)
        if self.mode.currentIndex():
            self.notice.setText('USB-UART：图像为限速缩略图；推理/状态独立回传')
            self.link.connect_serial(self.address.text().strip(), self.token.text().strip())
        else:
            self.link.connect_tcp(self.address.text().strip(), self.token.text().strip())
        self.connection_status.setText('正在连接…')
        self.connect_button.setText('断开连接')

    def open_host_network(self):
        from .network_dialog import NetworkDialog
        peer = self.address.text().strip() if not self.mode.currentIndex() else self.config.get('host', '')
        dialog = NetworkDialog(self, peer)
        dialog.configured.connect(self.host_network_configured)
        self.network_dialog = dialog
        try:
            dialog.exec()
        finally:
            self.network_dialog = None

    def host_network_configured(self, board_ip):
        if self.link:
            self.connect_board()
        if board_ip:
            self.mode.setCurrentIndex(0)
            self.address.setText(board_ip)
        self.log_label.setText('主机网口已配置，请重新连接板卡')

    def request(self, message):
        if not self.link:
            self.error('请先连接板卡')
            return False
        message = dict(message, request_id=uuid.uuid4().hex)
        try:
            self.link.send(message)
            self.request_ids[message['request_id']] = message['op']
            return True
        except Exception as exc:
            self.error(str(exc))
            return False

    def apply_frequency(self):
        if self.request({'op': 'cpu_frequency', 'khz': self.cpu.currentData() * 1000}):
            self.cpu_apply.setEnabled(False)
            self.log_label.setText('正在停止推理、调整频率并核验…')

    def encode(self):
        if self.worker.isRunning():
            return
        try:
            self.worker.items = parse_prompts(self.prompts.toPlainText(),allow_chinese=True)
        except ValueError as exc:
            self.error(str(exc))
            return
        self.revision += 1
        self.worker.revision = self.revision
        self.current_result = None
        self.encode_button.setEnabled(False)
        self.query_status.setText('正在主机编码描述…')
        self.worker.start()

    def preset_classify(self):
        self.prompts.setPlainText('\n'.join(label + ' | ' + text for label, text in PRESETS))
        if self.link:
            self.pending_start = True
            self.encode()

    def start_inference(self):
        if not self.link:
            self.error('请先连接板卡')
            return
        try:
            items = parse_prompts(self.prompts.toPlainText(),allow_chinese=True)
        except ValueError as exc:
            self.error(str(exc))
            return
        if not hasattr(self, 'last_encoded') or not same_intent(items,self.last_encoded['items']) or self.accepted_revision != self.last_encoded['revision'] or not self.accepted_revision:
            self.pending_start = True
            self.encode()
        else:
            self.request({'op': 'start'})

    def stop_inference(self):
        self.pending_start = False
        self.request({'op': 'stop'})

    def resume_pending_start(self):
        if not self.pending_start or self.accepted_revision != self.last_encoded['revision']:
            return
        # Editing while the asynchronous encoder is working changes the intent.
        # Re-encode that intent before starting, even if the prior ACK is valid.
        try:
            current_items = parse_prompts(self.prompts.toPlainText(),allow_chinese=True)
        except ValueError as exc:
            self.pending_start = False
            self.error(str(exc))
            return
        if not same_intent(current_items,self.last_encoded['items']):
            self.encode()
            return
        self.pending_start = False
        self.request({'op': 'start'})

    def encoded(self, message):
        self.encode_button.setEnabled(True)
        self.last_encoded = message
        self.gallery_query.clear()
        for item in message['items']:
            self.gallery_query.addItem(item['label'], item['id'])
        if self.request(message):
            self.query_status.setText('描述已编码，等待板端确认…')
        else:
            self.pending_start = False
            self.query_status.setText('描述已在本地编码，尚未上传到板卡')

    def encoding_error(self, text):
        self.pending_start = False
        self.encode_button.setEnabled(True)
        self.query_status.setText('文本编码失败')
        self.error(text)

    def error(self, text):
        self.log_label.setText(text)

    def message(self, message):
        if message.get('_connection_epoch', self.connection_epoch) != self.connection_epoch:
            return
        kind = message.get('type')
        if kind == 'hello':
            if message.get('contract_id') != self.contract['contract_id']:
                self.error('模型/平台合同不一致，已断开')
                self.connect_board()
                return
            self.connection_status.setText('已连接 · A0005')
            self.revision = max(self.revision, message.get('query_revision', 0))
        if kind in ('hello', 'status'):
            self.revision=max(self.revision,message.get('query_revision',0))
            self.status_data = message
            cpu = message.get('cpu', {})
            inference = message.get('inference', {})
            self.device_summary.setText('A53 当前 %.1f MHz · 四核共享\n推理：%s\n内存可用：%.0f MB\n摄像头：%s × %s，采集 %.2f FPS\nR5F：%s' % (cpu.get('current_khz', 0) / 1000, inference.get('state', '—'), message.get('memory_kb', {}).get('MemAvailable', 0) / 1024, message.get('camera', {}).get('width', '—'), message.get('camera', {}).get('height', '—'), message.get('camera', {}).get('fps', 0), message.get('r5', {}).get('mode', 'unavailable')))
            summary = self.device_summary.text() + '\nCPU 负载：' + ' / '.join(message.get('loadavg', []))
            for core in message.get('r5', {}).get('cores', []):
                summary += '\nR5-%s · 心跳 %s · 处理消息 %s' % (core.get('core'), core.get('heartbeat'), core.get('requests'))
            self.device_summary.setText(summary)
            base='调频自动暂停/排空，核验后恢复；改变在途数需先停止。\n600/800/1000/1200MHz四档，四个A53共享频率。'
            self.cpu_hint.setText(base+'\n阈值为工程设置，尚未做自然样本准确率校准。')
            if cpu.get('transition'):
                self.device_summary.setText('正在调整频率，等待硬件核验…\n'+self.device_summary.text())
            if inference.get('error'):
                self.error(inference['error'])
        elif kind == 'ack':
            requested = self.request_ids.pop(message.get('request_id'), None)
            if requested is None:
                return
            if requested=='cpu_frequency':
                self.cpu_apply.setEnabled(True)
            if not message.get('ok'):
                if message.get('op') == 'queries':
                    self.pending_start = False
                    self.query_status.setText('板端未接受描述，请更新后重试')
                self.error(message.get('error', '请求失败'))
                return
            self.log_label.setText('已执行：' + str(message.get('op')))
            if message.get('op') == 'queries':
                self.accepted_revision = message['result']['query_revision']
                self.query_status.setText('板端已接受 %d 条描述 · 版本 %d' % (message['result']['count'], self.accepted_revision))
                self.resume_pending_start()
        elif kind == 'result':
            if message.get('query_revision') != self.accepted_revision or self.worker.isRunning() or self.revision > self.accepted_revision:
                return
            self.current_result = (message, time.monotonic())
            self.ranking.clear()
            for item in message.get('ranking', []):
                self.ranking.addItem('%s   %.3f\n%s' % (item['label'], item['score'], item['text']))

    def tick(self):
        if not self.link:
            return
        state = self.link.state
        preview = state.preview
        if preview and preview[0]['frame_id'] != self.preview_stamp:
            self.preview_stamp = preview[0]['frame_id']
            image = QImage.fromData(preview[1], 'JPEG')
            if not image.isNull():
                self.pixmap = QPixmap.fromImage(image)
                self.video.setPixmap(self.pixmap.scaled(self.video.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
                self.displayed += 1
        result_image = state.result_image
        if result_image and result_image[0]['frame_id'] not in self.gallery_ids:
            result = state.last_result
            if result and result['frame_id'] == result_image[0]['frame_id'] and 'features' in result:
                entry = {'frame_id': result['frame_id'], 'jpeg': result_image[1], 'features': result['features'], 'label': (result.get('best') or {}).get('label', '未知')}
                self.gallery.append(entry)
                self.gallery_ids.add(entry['frame_id'])
                if len(self.gallery) > 60:
                    self.gallery_ids.discard(self.gallery.pop(0)['frame_id'])
        now = time.monotonic()
        if preview and now - preview[2] > 2:
            self.notice.setText('视频暂未更新 · 当前显示最后收到的一帧')
        elif preview:
            self.notice.setText('USB-UART：限速缩略图，推理结果独立回传' if self.mode.currentIndex() else '以太网传输摄像头压缩流；推理抽帧异步运行')
        age = None
        if self.current_result:
            result, received = self.current_result
            age = result.get('result_age_ms', 0) / 1000 + now - received
            best = result.get('best')
            label = '未匹配' if result.get('unknown') else (best or {}).get('label', '未知')
            self.overlay.setText('%s%s  ·  %s\n帧 #%s  /  结果来自 %.1f 秒前' % ('已过期 · ' if age > 3 else '', label, '%.3f' % best['score'] if best else '—', result['frame_id'], age))
        else:
            self.overlay.setText('等待当前描述的推理结果')
        if now - self.fps_at >= 1:
            fps = (self.displayed - self.fps_count) / (now - self.fps_at)
            self.fps_count, self.fps_at = self.displayed, now
            infer = self.status_data.get('inference', {})
            self.metrics.setText('预览 %.1f FPS   /   推理 %.2f FPS   /   结果年龄 %s' % (fps, infer.get('fps', 0), '%.1f s' % age if age is not None else '—'))

    def save_frame(self):
        if not self.link or not self.link.state.preview:
            self.error('当前没有画面')
            return
        filename, unused = QFileDialog.getSaveFileName(self, '保存当前画面', 'frame.jpg', 'JPEG (*.jpg)')
        if filename:
            Path(filename).write_bytes(self.link.state.preview[1])

    def search_gallery(self):
        if not self.gallery or not hasattr(self, 'last_encoded'):
            self.error('先编码描述并接收推理帧')
            return
        index = self.gallery_query.currentIndex()
        query = np.asarray(self.last_encoded['features'][index])
        features = normalized([item['features'] for item in self.gallery])
        scores = features.dot(query)
        self.gallery_list.clear()
        for i in np.argsort(-scores, kind='stable'):
            entry = self.gallery[int(i)]
            item = QListWidgetItem('%.3f  ·  帧 #%d  ·  %s' % (scores[i], entry['frame_id'], entry['label']))
            item.setData(Qt.UserRole, entry)
            self.gallery_list.addItem(item)

    def show_gallery(self, item):
        image = QImage.fromData(item.data(Qt.UserRole)['jpeg'], 'JPEG')
        self.gallery_preview.setPixmap(QPixmap.fromImage(image).scaled(self.gallery_preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def closeEvent(self, event):
        network = getattr(self, 'network_dialog', None)
        if network and network.worker and network.worker.isRunning():
            self.error('主机网口操作正在进行，请等待结果后关闭')
            event.ignore()
            return
        if self.worker.isRunning():
            self.error('文本模型正在加载/编码，请完成后关闭')
            event.ignore()
            return
        if self.link:
            self.link.close()
        event.accept()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--smoke', help='capture screenshot and exit after 1 second')
    parser.add_argument('--self-test', help='validate packaged text encoder and write JSON receipt')
    parser.add_argument('--live-smoke', help='connect, query, run 55 seconds, capture live screenshot and exit')
    parser.add_argument('--network-smoke', help='read-only network dialog acceptance screenshot')
    parser.add_argument('--semantic-self-test',help='verify packaged Chinese encoder, video archive and clip exporter')
    args = parser.parse_args()
    app = QApplication(sys.argv[:1])
    app.setFont(QFont('Microsoft YaHei UI', 10))
    from .semantic_ui import SemanticWindow
    window = SemanticWindow()
    if args.semantic_self_test:
        import io
        from PIL import Image
        import av
        from .semantic_media import SemanticArchive,export_segments
        target=Path(args.semantic_self_test);directory=target.parent/('packaged-media-'+uuid.uuid4().hex)
        try:
            items=window.translator.items(parse_prompts('桌面上的杯子\n有人在房间里\n一个穿红色衣服的人',allow_chinese=True))
            encoder=TextEncoder(window.contract,str(window.model_root));features,identity=encoder.encode(items)
            archive=SemanticArchive(directory,items,1,threshold=-1)
            data=io.BytesIO();Image.new('RGB',(64,64),'red').save(data,'JPEG');jpeg=data.getvalue()
            for i in range(3):archive.feed_frame(dict(frame_id=i,capture_monotonic=100+i*.1,width=64,height=64),jpeg)
            archive.feed_result(dict(frame_id=1,capture_monotonic=100.1,query_revision=1,ranking=[dict(id='0',label='red',score=.5)]))
            archive.finish_at(2)
            if not archive.closed.wait(10):raise TimeoutError('packaged archive did not close')
            report=json.loads((directory/'session.json').read_text(encoding='utf-8'));assert report['ok'],report
            clips=export_segments(directory/'video.mkv',report['segments'],directory/'clips')
            with av.open(clips[0]['path']) as c:assert sum(1 for unused in c.decode(video=0))>0
            target.write_text(json.dumps(dict(ok=True,shape=list(features.shape),items=items,identity=identity,frames=report['frames'],clips=len(clips)),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        except BaseException as exc:
            target.write_text(json.dumps(dict(ok=False,error=str(exc)),ensure_ascii=False)+'\n',encoding='utf-8');raise
        return 0
    if args.self_test:
        try:
            encoder = TextEncoder(window.contract, str(window.model_root))
            items = parse_prompts('杯子\n瓶子')
            features, identity = encoder.encode(items)
            Path(args.self_test).write_text(json.dumps({'ok': True, 'shape': list(features.shape), 'identity': identity}, ensure_ascii=False, indent=2), encoding='utf-8')
        except Exception as exc:
            Path(args.self_test).write_text(json.dumps({'ok': False, 'error': str(exc)}), encoding='utf-8')
            raise
        return 0
    window.show()
    if args.network_smoke:
        from .network_dialog import NetworkDialog
        dialog = NetworkDialog(window, window.address.text())
        dialog.show()
        begun = time.monotonic()
        def capture_network():
            if not dialog.busy and dialog.nics:
                dialog.grab().save(args.network_smoke)
                Path(args.network_smoke).with_suffix('.json').write_text(json.dumps({'ok': True, 'read_only': True, 'nics': dialog.nics, 'static_action_enabled': dialog.apply_button.isEnabled(), 'dhcp_action_enabled': dialog.dhcp_button.isEnabled()}, ensure_ascii=False, indent=2), encoding='utf-8')
                dialog.close()
                app.quit()
            elif time.monotonic() - begun < 25:
                QTimer.singleShot(100, capture_network)
            else:
                dialog.grab().save(args.network_smoke)
                app.quit()
        QTimer.singleShot(200, capture_network)
    if args.smoke:
        def save():
            window.grab().save(args.smoke)
            app.quit()
        QTimer.singleShot(1200, save)
    if args.live_smoke:
        QTimer.singleShot(100, window.connect_board)
        QTimer.singleShot(1500, window.encode)
        def start():
            if window.accepted_revision == window.revision and window.accepted_revision:
                window.request({'op': 'start'})
            else:
                QTimer.singleShot(200, start)
        QTimer.singleShot(3000, start)
        def capture():
            window.grab().save(args.live_smoke)
            window.request({'op': 'stop'})
            QTimer.singleShot(3500, window.close)
        QTimer.singleShot(55000, capture)
    return app.exec()


if __name__ == '__main__':
    sys.exit(main())
