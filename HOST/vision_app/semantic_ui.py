"""Two semantic video workflows in the existing native workstation."""
import datetime
import json
from pathlib import Path
import threading
import time
from PySide6.QtCore import Qt,QThread,Signal,QUrl,QTimer,QStandardPaths,QSize
from PySide6.QtGui import QDesktopServices,QImage,QPixmap
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QLineEdit,QTextEdit,QDoubleSpinBox,QFileDialog,QProgressBar,QTableWidget,QTableWidgetItem,QHeaderView,QTabWidget,QStackedWidget,QComboBox,QSlider,QCheckBox,QMessageBox,QToolButton
from PySide6.QtMultimedia import QMediaPlayer,QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget
from .client import Window
from .text_encoder import TextEncoder,parse_prompts,PRESETS
from .translation import same_intent
from .semantic_media import SemanticArchive,export_segments
from .video_analysis import analyze_video,video_info
from .ui_icons import action_icon
from .threshold_control import SimilarityStepper

def clock(seconds):
    ms=round(seconds*1000);return '%02d:%02d:%02d.%03d'%(ms//3600000,(ms//60000)%60,(ms//1000)%60,ms%1000)
def new_folder(root,prefix):return Path(root)/(prefix+'-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f'))

class AnalysisWorker(QThread):
    progress=Signal(object);preview=Signal(bytes);ready=Signal(object);failed=Signal(str)
    def __init__(self,owner,path,text,directory,threshold):
        super().__init__(owner);self.owner=owner;self.path=path;self.text=text;self.directory=directory;self.threshold=threshold;self.cancel=threading.Event()
        self.host=owner.address.text().strip();self.continuity=owner.live_continuity.isChecked()
    def run(self):
        try:
            self.progress.emit(dict(stage='正在主机编码描述…'))
            items=self.owner.translator.items(parse_prompts(self.text,allow_chinese=True))
            if self.owner.encoder is None:self.owner.encoder=TextEncoder(self.owner.contract,str(self.owner.model_root))
            features,identity=self.owner.encoder.encode(items)
            report=analyze_video(self.path,self.host,items,features,identity,self.directory,self.threshold,self.progress.emit,self.preview.emit,self.cancel,continuity=self.continuity)
            self.ready.emit(report)
        except BaseException as exc:self.failed.emit(str(exc))

class ExportWorker(QThread):
    ready=Signal(object);failed=Signal(str);progress=Signal(str)
    def __init__(self,owner,source,segments,destination):
        super().__init__(owner);self.source=source;self.segments=segments;self.destination=destination;self.cancel=threading.Event()
    def run(self):
        try:self.ready.emit(export_segments(self.source,self.segments,self.destination,lambda i,n:self.progress.emit('正在导出 %d / %d 个视频'%(i,n)),self.cancel,group_by_query=True))
        except BaseException as exc:self.failed.emit(str(exc))

class ArchiveSignals(QWidget):
    updated=Signal(object);missing=Signal(int)

class SemanticWindow(Window):
    def __init__(self):
        self.archive=None;self.want_recording=False;self.end_recording=False;self.analysis_worker=None;self.export_worker=None
        self.session_report=None;self.clips={};self.playing=False
        self.playback_kind=None;self.play_range=None;self.latest_analysis_jpeg=None;self.full_position=0
        self.pending_playback_start=False
        self.live_state='idle';self.manual_update=False;self.query_feedback_revision=None
        self.feedback_boxes=[];self.notified_archives=set()
        self.device_received_at=None;self.hardware_sample_id=None;self.hardware_updated_text=None
        super().__init__()
        self.setWindowTitle('FZ3B · 语义视频工作台')
        self.archive_events=ArchiveSignals(self);self.archive_events.hide()
        self.archive_events.updated.connect(self.archive_updated);self.archive_events.missing.connect(lambda fid:self.request(dict(op='frame_get',frame_id=fid)))
        self.worker.finished.connect(lambda:self.set_live_state(self.live_state))
    def build_ui(self):
        super().build_ui()
        self.overlay.hide();self.video.setMinimumSize(480,240)
        self.findChild(QLabel,'brand').setText('FZ3B · 视频检索')
        self.tabs=self.findChild(QTabWidget);self.tabs.setTabText(0,'实时文字找场景');self.tabs.removeTab(1)
        self.prompts.setPlainText('桌面上的杯子\n有人在房间里')
        self.start_button.setText('开始录像与检索');self.encode_button.setText('更新描述')
        self.threshold.setValue(.17)
        for label in self.tabs.widget(0).findChildren(QLabel):
            if label.text().startswith('每行一条'):label.setText('输入要找的物品或场景，每行一个。\n开始后自动录像，结束后保存视频和命中画面。')
            if label.text()=='当前候选 · 余弦相似度':label.setText('最近分析帧 · 相似度（不是概率）')
        for button in self.tabs.widget(0).findChildren(QPushButton):
            if button.text()=='停止推理':self.stop_button=button;button.setText('结束录像')
            if button.text()=='物品与场景预设':self.preset_button=button
        page=self.tabs.widget(0);layout=page.layout()
        output=QHBoxLayout();self.output_root=QLineEdit(str(Path(QStandardPaths.writableLocation(QStandardPaths.MoviesLocation))/'FZ3B语义检索'))
        choose=QPushButton('选择目录');choose.clicked.connect(self.choose_output)
        output.addWidget(self.output_root,1);output.addWidget(choose)
        layout.insertWidget(2,QLabel('保存位置'));layout.insertLayout(3,output)
        level=QHBoxLayout();level.addWidget(QLabel('命中相似度阈值'));self.live_threshold=SimilarityStepper();self.live_threshold.setRange(-1,1);self.live_threshold.setSingleStep(.01);self.live_threshold.setValue(self.threshold.value());level.addWidget(self.live_threshold);level.addStretch();layout.insertLayout(4,level)
        self.live_threshold.valueChanged.connect(self.threshold.setValue);self.threshold.valueChanged.connect(self.live_threshold.setValue)
        self.live_threshold.setToolTip('余弦相似度，不是概率。降低阈值增加命中，也可能增加误报。')
        self.live_continuity=QCheckBox('连续片段优化');self.live_continuity.setChecked(True)
        self.live_continuity.setToolTip('平滑短暂掉分，极短命中保留为候选。');self.live_continuity.hide()
        more=QToolButton();more.setText('更多设置');more.setCheckable(True)
        more.toggled.connect(self.live_continuity.setVisible);layout.insertWidget(5,more);layout.insertWidget(6,self.live_continuity)
        self.prompts.setMaximumHeight(125)
        self.live_summary=QLabel('尚未开始录像');self.live_summary.setWordWrap(True);layout.addWidget(self.live_summary)
        offline=QWidget();v=QVBoxLayout(offline)
        title=QLabel('检索视频中的物品与场景');title.setObjectName('title');v.addWidget(title)
        self.file_label=QLabel('选择本机视频，逐帧发送板卡分析');self.file_label.setWordWrap(True);v.addWidget(self.file_label)
        self.choose_video_button=QPushButton('选择视频…');self.choose_video_button.clicked.connect(self.choose_video);v.addWidget(self.choose_video_button)
        self.offline_prompts=QTextEdit();self.offline_prompts.setPlainText('桌面上的杯子\n有人在房间里');self.offline_prompts.setMaximumHeight(155);v.addWidget(QLabel('要寻找的描述 · 每行一条'));v.addWidget(self.offline_prompts)
        level=QHBoxLayout();level.addWidget(QLabel('命中相似度阈值'));self.offline_threshold=SimilarityStepper();self.offline_threshold.setRange(-1,1);self.offline_threshold.setSingleStep(.01);self.offline_threshold.setValue(self.threshold.value());level.addWidget(self.offline_threshold);level.addStretch();v.addLayout(level)
        self.offline_threshold.valueChanged.connect(self.threshold.setValue);self.threshold.valueChanged.connect(self.offline_threshold.setValue)
        self.offline_continuity=QCheckBox('连续片段优化');self.offline_continuity.setChecked(True);v.addWidget(self.offline_continuity)
        self.offline_continuity.hide();offline_more=QToolButton();offline_more.setText('更多设置');offline_more.setCheckable(True);offline_more.toggled.connect(self.offline_continuity.setVisible);v.insertWidget(v.count()-1,offline_more)
        self.offline_continuity.toggled.connect(self.live_continuity.setChecked);self.live_continuity.toggled.connect(self.offline_continuity.setChecked)
        self.file_details=QLabel('完整分析每一帧，耗时随视频帧数增加。');self.file_details.setWordWrap(True);v.addWidget(self.file_details)
        row=QHBoxLayout();self.analyze_button=QPushButton('开始逐帧分析');self.analyze_button.clicked.connect(self.start_analysis)
        self.cancel_analysis_button=QPushButton('取消');self.cancel_analysis_button.clicked.connect(self.cancel_analysis);self.cancel_analysis_button.setEnabled(False)
        row.addWidget(self.analyze_button);row.addWidget(self.cancel_analysis_button);v.addLayout(row)
        self.analysis_progress=QProgressBar();self.analysis_progress.setRange(0,1000);v.addWidget(self.analysis_progress)
        self.analysis_notice=QLabel('分析完成后，选择下方时间段播放或导出。');self.analysis_notice.setWordWrap(True);v.addWidget(self.analysis_notice);v.addStretch()
        self.tabs.insertTab(1,offline,'视频语义检索');self.tabs.currentChanged.connect(self.page_changed)
        device=self.tabs.widget(2)
        self.hardware_rows=[('cpu_fpd_c','CPU 区域温度（FPD）','°C'),('ps_lpd_c','PS 低功耗区温度','°C'),('pl_c','PL 温度','°C'),
            ('ps_fpd_v','CPU / FPD 供电','V'),('ps_lpd_v','PS 低功耗供电','V'),('ps_aux_v','PS 辅助供电','V'),('ps_ddr_v','PS DDR 供电','V'),
            ('pl_core_v','PL 核心供电','V'),('pl_aux_v','PL 辅助供电','V'),('pl_bram_v','PL BRAM 供电','V'),('ps_pll_v','PS PLL 供电','V')]
        self.hardware_table=QTableWidget(len(self.hardware_rows),2);self.hardware_table.setHorizontalHeaderLabels(['温度 / 电压','实时值'])
        self.hardware_table.verticalHeader().hide();self.hardware_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.hardware_table.setSelectionMode(QTableWidget.NoSelection);self.hardware_table.horizontalHeader().setSectionResizeMode(0,QHeaderView.Stretch)
        self.hardware_table.setMinimumHeight(180);self.hardware_table.setMaximumHeight(300)
        for row,(_,label,_) in enumerate(self.hardware_rows):self.hardware_table.setItem(row,0,QTableWidgetItem(label));self.hardware_table.setItem(row,1,QTableWidgetItem('—'))
        device.layout().insertWidget(3,self.hardware_table)
        self.device_updated=QLabel('温度、电压等待采集');self.device_updated.setWordWrap(True);device.layout().insertWidget(4,self.device_updated)
        for toggle in (more,offline_more):
            toggle.setArrowType(Qt.RightArrow);toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            toggle.toggled.connect(lambda checked,target=toggle:target.setArrowType(Qt.DownArrow if checked else Qt.RightArrow))
        video_parent=self.video.parentWidget();video_layout=video_parent.layout()
        self.display_tools=QWidget();display_row=QHBoxLayout(self.display_tools);display_row.setContentsMargins(0,0,0,0)
        display_row.addWidget(QLabel('检索画面'));self.display_mode=QComboBox();self.display_mode.addItems(['当前推理帧','整段视频']);display_row.addWidget(self.display_mode);display_row.addStretch()
        self.display_mode.setToolTip('显示方式不影响逐帧分析；整段视频按原速独立播放。')
        video_layout.insertWidget(0,self.display_tools);self.display_tools.hide()
        self.preview_stack=QStackedWidget();self.preview_stack.addWidget(self.video)
        self.playback=QVideoWidget();self.preview_stack.addWidget(self.playback);video_layout.insertWidget(1,self.preview_stack,1)
        self.player=QMediaPlayer(self);self.audio=QAudioOutput(self);self.player.setAudioOutput(self.audio);self.player.setVideoOutput(self.playback)
        self.player.mediaStatusChanged.connect(self.media_loaded)
        self.player.positionChanged.connect(self.playback_position)
        self.display_mode.currentIndexChanged.connect(self.apply_display_mode)
        self.playback_tools=QWidget();playback_row=QHBoxLayout(self.playback_tools);playback_row.setContentsMargins(0,0,0,0)
        self.pause_button=QPushButton('播放');self.pause_button.clicked.connect(self.playback_toggle);playback_row.addWidget(self.pause_button)
        self.seek=QSlider(Qt.Horizontal);self.seek.setRange(0,0);self.seek.sliderMoved.connect(self.player.setPosition);playback_row.addWidget(self.seek,1)
        self.playback_time=QLabel('00:00 / 00:00');playback_row.addWidget(self.playback_time);video_layout.addWidget(self.playback_tools);self.playback_tools.hide()
        self.player.durationChanged.connect(lambda duration:self.seek.setRange(0,int(duration)))
        self.player.playbackStateChanged.connect(lambda state:self.pause_button.setText('暂停' if state==QMediaPlayer.PlayingState else '播放'))
        self.player.errorOccurred.connect(lambda *args:self.error('播放失败：'+self.player.errorString()))
        tools=QHBoxLayout();tools.addWidget(QLabel('命中时间段'))
        back=QPushButton('返回画面');back.clicked.connect(self.back_to_preview);tools.addWidget(back)
        self.play_button=QPushButton('播放所选');self.play_button.clicked.connect(self.play_segment);tools.addWidget(self.play_button)
        self.export_button=QPushButton('导出片段');self.export_button.clicked.connect(self.export_clips);tools.addWidget(self.export_button)
        folder=QPushButton('打开输出');folder.clicked.connect(self.open_output);tools.addWidget(folder);video_layout.addLayout(tools)
        self.segments_table=QTableWidget(0,3);self.segments_table.setHorizontalHeaderLabels(['描述','开始时间','结束时间'])
        self.segments_table.setObjectName('semanticSegments')
        self.segments_table.setSelectionBehavior(QTableWidget.SelectRows);self.segments_table.setSelectionMode(QTableWidget.SingleSelection);self.segments_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.segments_table.horizontalHeader().setSectionResizeMode(0,QHeaderView.Stretch)
        self.segments_table.setMaximumHeight(190);self.segments_table.setMinimumHeight(140);self.segments_table.doubleClicked.connect(self.play_segment);video_layout.addWidget(self.segments_table)
        self.notice.setText('实时视频与检索结果分开展示；时间段依据捕获时间。')
        for button,name in ((self.preset_button,'preset'),(self.encode_button,'update'),(self.stop_button,'stop')):
            button.setIcon(action_icon(name));button.setIconSize(QSize(20,20))
        self.start_button.setIconSize(QSize(20,20));self.set_live_state('idle')
        self.setStyleSheet(self.styleSheet()+'''QTableWidget {background:#142033;border:1px solid #30425B;alternate-background-color:#1B2A40;selection-background-color:#236DB0;selection-color:#FFFFFF;}
            QTableWidget#semanticSegments::item:selected {background:#236DB0;color:#FFFFFF;border-top:1px solid #8BD3FF;border-bottom:1px solid #8BD3FF;}
            QHeaderView::section {background:#203049;color:#DCE8F8;padding:7px;border:0;} QProgressBar {border:1px solid #41526A;border-radius:5px;text-align:center;min-height:24px;} QProgressBar::chunk {background:#2B87B9;}''')
    def set_live_state(self,state):
        self.live_state=state
        style={
            'idle':('开始录像与检索','start','#245D9E','#FFFFFF','#4381BF'),
            'preparing':('等待推理…','wait','#FFD166','#362504','#FFD166'),
            'recording':('正在推理','record','#4A252D','#FFF4F5','#FF6676'),
            'stopping':('正在结束…','wait','#FFD166','#362504','#FFD166'),
        }
        text,icon,background,foreground,border=style[state]
        self.start_button.setText(text);self.start_button.setIcon(action_icon(icon,foreground))
        self.start_button.setProperty('recordState',state)
        self.start_button.setStyleSheet('QPushButton, QPushButton:disabled {background:%s;color:%s;border:2px solid %s;border-radius:5px;padding:9px;font-weight:600;}'%(background,foreground,border))
        offline=self.analysis_worker is not None and self.analysis_worker.isRunning()
        idle=state=='idle' and not self.manual_update and not offline and not self.worker.isRunning()
        self.start_button.setEnabled(idle);self.encode_button.setEnabled(idle);self.preset_button.setEnabled(idle)
        self.stop_button.setEnabled(state in ('preparing','recording'))
        self.stop_button.setText('正在结束…' if state=='stopping' else '结束录像')
        self.stop_button.setIcon(action_icon('wait' if state=='stopping' else 'stop'))
        self.prompts.setReadOnly(not idle);self.set_threshold_enabled(idle)
    def notify_success(self,title,text,path=None):
        box=QMessageBox(QMessageBox.Information,title,text,QMessageBox.Ok,self)
        box.setWindowModality(Qt.WindowModal);box.button(QMessageBox.Ok).setText('知道了')
        if path:
            button=box.addButton('打开保存位置',QMessageBox.ActionRole)
            button.clicked.connect(lambda:QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(path).resolve()))))
        box.setAttribute(Qt.WA_DeleteOnClose);self.feedback_boxes.append(box)
        box.finished.connect(lambda _:self.feedback_boxes.remove(box) if box in self.feedback_boxes else None)
        box.open()
    def finish_manual_update(self):
        self.manual_update=False;self.query_feedback_revision=None
        self.set_live_state(self.live_state)
    def encode(self):
        if self.worker.isRunning():return
        manual=not self.want_recording and not self.pending_start
        if manual and not self.link:self.error('请先连接板卡再更新描述');return
        if manual:
            self.manual_update=True;self.query_feedback_revision=self.revision+1
            self.set_live_state(self.live_state)
        super().encode()
        if not self.worker.isRunning() and self.worker.revision!=self.query_feedback_revision and manual:self.finish_manual_update()
    def encoding_error(self,text):
        super().encoding_error(text);self.want_recording=False;self.finish_manual_update();self.set_live_state('idle')
    def page_changed(self,index):
        self.remember_full_position();self.playing=False;self.playback_kind=None;self.pending_playback_start=False;self.player.stop();self.preview_stack.setCurrentIndex(0)
        self.display_tools.setVisible(index==1);self.playback_tools.hide()
        if index==1:self.apply_display_mode()
        if index==1 and getattr(self,'offline_report',None):self.show_segments(self.offline_report)
        elif index==0 and self.archive:self.show_segments(dict(path=str(self.archive.path),segments=self.archive.segments,candidates=self.archive.candidates,source='camera'))
    def choose_output(self):
        path=QFileDialog.getExistingDirectory(self,'选择录像及检索输出目录',self.output_root.text())
        if path:self.output_root.setText(path)
    def connect_board(self):
        if self.archive and not self.archive.closed.is_set():self.error('请先结束录像，等待整理完成再断开');return
        if self.analysis_worker and self.analysis_worker.isRunning():self.error('请先取消视频分析再断开');return
        super().connect_board()
        if self.link:self.link.on_frame=self.record_frame;self.link.on_result_image=self.record_missing
    def record_frame(self,meta,jpeg):
        archive=self.archive
        if archive and not archive.closed.is_set():archive.feed_frame(meta,jpeg)
    def record_missing(self,meta,jpeg):
        if self.archive:self.archive.feed_missing(meta,jpeg)
    def start_inference(self):
        if not self.link:self.error('请先连接板卡');return
        if self.mode.currentIndex():self.error('完整录像检索请使用以太网，串口仍支持状态与控制');return
        if self.archive and not self.archive.closed.is_set():self.error('正在录像，请先结束当前任务');return
        if self.analysis_worker and self.analysis_worker.isRunning():self.error('板卡正在逐帧分析视频');return
        if self.status_data.get('inference',{}).get('state')!='STOPPED':self.error('请等待板端推理正常停止');return
        try:items=parse_prompts(self.prompts.toPlainText(),allow_chinese=True)
        except ValueError as exc:self.error(str(exc));return
        self.want_recording=True;self.end_recording=False;self.pending_start=True
        self.set_live_state('preparing');self.live_summary.setText('正在准备，请稍候。')
        if not hasattr(self,'last_encoded') or not same_intent(items,self.last_encoded['items']) or self.accepted_revision!=self.last_encoded['revision']:self.encode()
        else:self.resume_pending_start()
    def resume_pending_start(self):
        if not self.want_recording:return super().resume_pending_start()
        if not self.pending_start or self.accepted_revision!=self.last_encoded['revision']:return
        current=parse_prompts(self.prompts.toPlainText(),allow_chinese=True)
        if not same_intent(current,self.last_encoded['items']):self.encode();return
        try:
            root=Path(self.output_root.text());root.mkdir(parents=True,exist_ok=True)
            self.archive=SemanticArchive(new_folder(root,'live'),self.last_encoded['items'],self.accepted_revision,self.threshold.value(),self.archive_events.updated.emit,self.archive_events.missing.emit,continuity=self.live_continuity.isChecked())
            self.prompts.setReadOnly(True);self.start_button.setEnabled(False);self.encode_button.setEnabled(False)
            self.preset_button.setEnabled(False)
            self.set_threshold_enabled(False)
            self.request(dict(op='settings',threshold=self.threshold.value()))
            self.live_summary.setText('正在准备推理，视频已开始保存。')
            self.pending_start=False;self.want_recording=False
            if not self.request(dict(op='start')):raise RuntimeError('开始请求未发送，请重新连接板卡')
        except Exception as exc:
            self.pending_start=False;self.want_recording=False;self.error(str(exc))
            if self.archive and not self.archive.closed.is_set():self.archive.error=str(exc);self.archive.stop()
            else:self.set_live_state('idle')
    def stop_inference(self):
        self.want_recording=False;self.end_recording=True;self.pending_start=False
        active=self.archive and not self.archive.closed.is_set()
        self.set_live_state('stopping');sent=self.request(dict(op='stop'))
        if active:
            self.live_summary.setText('正在结束并保存，请稍候。')
            if not sent:self.archive.error='结束请求未发送，录像未确认完整';self.archive.stop()
        else:self.set_live_state('idle');self.live_summary.setText('已取消准备，尚未开始录像。')
    def message(self,message):
        if message.get('_connection_epoch',self.connection_epoch)!=self.connection_epoch:return
        requested=self.request_ids.get(message.get('request_id'))
        if message.get('type')=='result' and self.archive:self.archive.feed_result(message)
        super().message(message)
        if message.get('type')=='ack' and requested:
            if requested=='queries' and self.manual_update:
                if message.get('ok') and message.get('result',{}).get('query_revision')==self.query_feedback_revision:
                    count=message['result']['count'];self.finish_manual_update()
                    self.query_status.setText('已更新 %d 个描述'%count);self.notify_success('描述更新成功','已更新 %d 个描述，可以开始录像与检索。'%count)
                elif not message.get('ok'):self.finish_manual_update()
            if requested=='queries' and not message.get('ok') and self.live_state=='preparing':
                self.want_recording=False;self.pending_start=False;self.set_live_state('idle')
            if not message.get('ok') and requested=='start' and self.archive:
                self.archive.error=message.get('error','开始失败');self.archive.stop()
            if not message.get('ok') and requested=='stop' and self.archive and not self.archive.closed.is_set():
                self.end_recording=False;self.set_live_state('recording')
            if message.get('ok'):
                label={'start':'开始请求已收到，正在准备。','stop':'正在结束并保存录像…','settings':'设置已应用','queries':'描述已更新'}.get(requested)
                if label:self.log_label.setText(label)
                if requested=='queries':self.query_status.setText('已准备 %d 个描述'%message['result']['count'])
        if message.get('type') in ('hello','status'):
            self.cpu_hint.setText('修改频率时会先暂停推理，完成后自动恢复。')
            summary=self.device_summary.text()
            for raw,plain in (('STOPPED','未开始'),('STARTING','准备中'),('RUNNING','推理中'),('DRAINING','结束中'),('FAILED','异常')):summary=summary.replace('推理：'+raw,'推理：'+plain)
            self.device_summary.setText(summary)
            self.update_device_parameters(message)
            if message.get('type')=='hello':self.connection_status.setText('已连接')
        if message.get('type')=='result' and self.current_result and self.current_result[0] is message:
            self.ranking.clear()
            for hit in message.get('ranking',[]):self.ranking.addItem('%s   ·   %.3f'%(hit['label'],hit['score']))
        if message.get('type') in ('hello','status') and self.archive and not self.archive.closed.is_set():
            state=message.get('inference',{}).get('state')
            if not self.end_recording and state in ('STARTING','RUNNING'):self.set_live_state('recording' if state=='RUNNING' else 'preparing')
            if self.end_recording and state=='STOPPED':self.archive.finish_at(message.get('camera',{}).get('frames',0)-1)
            if message.get('inference',{}).get('state')=='FAILED':self.archive.error=message['inference']['error'];self.archive.stop()
    def update_device_parameters(self,message):
        self.device_received_at=time.monotonic();hardware=message.get('hardware',{})
        values=hardware.get('values',{}) if not hardware.get('stale',True) else {}
        for row,(key,_,unit) in enumerate(self.hardware_rows):
            value=values.get(key);text=('%.1f °C'%value if unit=='°C' else '%.3f V'%value) if value is not None else '—'
            self.hardware_table.item(row,1).setText(text)
        sample_id=hardware.get('sample_id')
        if sample_id!=self.hardware_sample_id:
            self.hardware_sample_id=sample_id;self.hardware_updated_text=datetime.datetime.now().strftime('%H:%M:%S')
        self.device_updated.setText('每秒采集 · 更新于 '+str(self.hardware_updated_text) if values else '温度、电压暂未获取')
        cpu=message.get('cpu',{});memory=message.get('memory_kb',{});camera=message.get('camera',{});inference=message.get('inference',{})
        usage=hardware.get('cpu_usage_percent');load='%.0f%%'%usage if usage is not None and not hardware.get('stale',True) else '—'
        state={'STOPPED':'未开始','STARTING':'准备中','RUNNING':'进行中','DRAINING':'结束中','FAILED':'异常'}.get(inference.get('state'),'—')
        r5='正常' if message.get('r5',{}).get('offload_verified') else '未确认'
        self.device_summary.setText('CPU %.0f MHz · 使用率 %s\n可用内存 %.0f MB · 摄像头 %.1f FPS\n推理 %s · %s\nR5 状态：%s'%(cpu.get('current_khz',0)/1000,load,memory.get('MemAvailable',0)/1024,camera.get('fps',0),state,self.inference_fps_text(inference),r5))
    def archive_updated(self,value):
        if value.get('done'):
            self.set_live_state('idle')
            self.live_summary.setText(('录像已保存' if value['ok'] else '录像中断：'+str(value['error']))+'\n'+value['path'])
            if value['ok'] and self.end_recording and value['path'] not in self.notified_archives:
                self.notified_archives.add(value['path']);self.notify_success('录像已结束','完整视频和命中画面已保存。',value['path'])
        else:self.live_summary.setText(('正在准备 · ' if self.live_state=='preparing' else '录像中 · ')+'%d 张命中画面 · %d 个时间段'%(value['hits'],len(value['segments'])))
        if self.tabs.currentIndex()==0:self.show_segments(dict(value,source='camera'))
    def choose_video(self):
        path,_=QFileDialog.getOpenFileName(self,'选择要检索的视频','','视频 (*.mp4 *.mkv *.mov *.avi *.webm);;全部文件 (*)')
        if not path:return
        try:
            info=video_info(path);self.video_path=path;self.full_position=0;self.latest_analysis_jpeg=None;self.file_label.setText(Path(path).name);self.file_label.setToolTip(path)
            frames=info['frames'] or round(info['duration_s']*info['fps'])
            self.file_details.setText('%d × %d · %.2f FPS · %s\n预计 %d 帧，按4 FPS分析约 %.1f 分钟。'%(info['width'],info['height'],info['fps'],clock(info['duration_s']),frames,frames/240))
            self.apply_display_mode()
        except Exception as exc:self.error('视频无法读取：'+str(exc))
    def preset_classify(self):
        if self.archive and not self.archive.closed.is_set():self.error('请先结束录像再修改描述');return
        self.prompts.setPlainText('\n'.join(label for label,text in PRESETS))
        self.query_status.setText('预设已填入，点击“开始录像与检索”开始任务')
        self.notify_success('预设成功','已填入常用物品与场景。可以直接开始录像，也可以修改描述。')
    def start_analysis(self):
        if not self.link or self.mode.currentIndex():self.error('请连接板卡以太网');return
        if not getattr(self,'video_path',None):self.error('请先选择视频');return
        if self.archive and not self.archive.closed.is_set():self.error('请先结束实时录像');return
        if self.worker.isRunning() or self.status_data.get('inference',{}).get('state')!='STOPPED':self.error('请等待板卡停止及描述编码完成');return
        if self.analysis_worker and self.analysis_worker.isRunning():return
        root=Path(self.output_root.text());root.mkdir(parents=True,exist_ok=True)
        self.analysis_worker=AnalysisWorker(self,self.video_path,self.offline_prompts.toPlainText(),new_folder(root,'video'),self.threshold.value())
        self.analysis_worker.progress.connect(self.analysis_update);self.analysis_worker.preview.connect(self.analysis_frame);self.analysis_worker.ready.connect(self.analysis_done);self.analysis_worker.failed.connect(self.analysis_failed)
        self.analysis_worker.finished.connect(lambda:self.set_live_state(self.live_state))
        self.analyze_button.setEnabled(False);self.choose_video_button.setEnabled(False);self.cancel_analysis_button.setEnabled(True);self.offline_prompts.setReadOnly(True)
        self.start_button.setEnabled(False);self.encode_button.setEnabled(False);self.preset_button.setEnabled(False)
        self.set_threshold_enabled(False)
        self.analysis_progress.setValue(0);self.analysis_worker.start()
        self.latest_analysis_jpeg=None
        self.link.set_preview_enabled(False)
    def cancel_analysis(self):
        if self.analysis_worker:self.analysis_worker.cancel.set();self.analysis_notice.setText('正在取消并等待板端排空…')
    def analysis_update(self,value):
        if 'stage' in value:self.analysis_notice.setText(value['stage']);return
        ratio=min(1,value['source_time_s']/max(value['duration_s'],.001));self.analysis_progress.setValue(round(ratio*1000))
        remaining=max(0,value['duration_s']-value['source_time_s'])*value.get('source_fps',25)/max(value['fps'],.01)
        eta=clock(remaining) if value['fps'] else '正在测量'
        rate='%.2f FPS'%value['fps'] if value.get('fps_samples',10)>=10 else '采样中'
        self.analysis_notice.setText('已分析 %d 帧 / 已发送 %d 帧\n视频位置 %s · %s · 预计剩余 %s'%(value['completed'],value['sent'],clock(value['source_time_s']),rate,eta))
        if self.tabs.currentIndex()==1:
            self.metrics.setText('本地视频 · 已分析 %d 帧 · 位置 %s'%(value['completed'],clock(value['source_time_s'])))
            self.notice.setText('逐帧检索完成后自动导出命中片段')
    def analysis_frame(self,jpeg):
        self.latest_analysis_jpeg=jpeg
        if self.tabs.currentIndex()==1 and self.display_mode.currentIndex()==0 and not self.playing:
            image=QImage.fromData(jpeg);self.video.setPixmap(QPixmap.fromImage(image).scaled(self.video.size(),Qt.KeepAspectRatio,Qt.SmoothTransformation))
    def reset_analysis_buttons(self):
        self.analyze_button.setEnabled(True);self.choose_video_button.setEnabled(True);self.cancel_analysis_button.setEnabled(False);self.offline_prompts.setReadOnly(False);self.accepted_revision=0
        self.set_threshold_enabled(True)
        if self.link:self.link.set_preview_enabled(True)
        self.start_button.setEnabled(True);self.encode_button.setEnabled(True);self.preset_button.setEnabled(True);self.current_result=None
    def set_threshold_enabled(self,enabled):
        for widget in (self.threshold,self.live_threshold,self.offline_threshold):widget.setEnabled(enabled)
        for widget in (self.live_continuity,self.offline_continuity):widget.setEnabled(enabled)
    def encoded(self,message):
        self.prompts.setToolTip('\n'.join(x['label']+' → '+x.get('translated_text',x['text']) for x in message['items']))
        submitted=super().encoded(message)
        if not submitted:
            self.want_recording=False;self.finish_manual_update();self.set_live_state('idle');return
        if self.want_recording and not self.pending_start:
            self.want_recording=False;self.set_live_state('idle')
        else:self.set_live_state(self.live_state)
    def analysis_done(self,report):
        self.offline_report=report;self.reset_analysis_buttons();self.analysis_progress.setValue(1000)
        self.analysis_notice.setText('全部 %d 帧分析完成 · %d 个命中时间段\n%s'%(report['completed'],len(report['segments']),report['path']));self.show_segments(report)
        if self.tabs.currentIndex()==1:self.metrics.setText('全部 %d 帧分析完成 · %d 个命中时间段'%(report['completed'],len(report['segments'])))
        if report['segments']:self.export_clips(automatic=True)
    def analysis_failed(self,text):self.reset_analysis_buttons();self.analysis_notice.setText(text);self.error(text)
    def show_segments(self,report):
        table=self.segments_table;selected=None
        old=self.session_report;row=table.currentRow()
        if old and (old.get('path'),old.get('source'))==(report.get('path'),report.get('source')) and table.selectedItems() and 0<=row<len(self.shown_segments):
            item=self.shown_segments[row];selected=(item['query_id'],item.get('first_hit_s',item['start_s']))
        self.session_report=report;items=list(report.get('segments',[]))
        self.shown_segments=sorted(items,key=lambda item:(item['start_s'],str(item['query_id'])))
        table.setUpdatesEnabled(False)
        try:
            table.clearSelection();table.setCurrentCell(-1,-1);table.setRowCount(len(items))
            for row,item in enumerate(self.shown_segments):
                for col,text in enumerate((item['label'],clock(item['start_s']),clock(item['end_s']))):table.setItem(row,col,QTableWidgetItem(text))
                if (item['query_id'],item.get('first_hit_s',item['start_s']))==selected:table.selectRow(row)
        finally:table.setUpdatesEnabled(True)
    def source_path(self):
        if not self.session_report:return None
        return str(Path(self.session_report['path'])/'video.mkv') if self.session_report.get('source')=='camera' else self.session_report['source']
    def play_segment(self,*args):
        row=self.segments_table.currentRow()
        if row<0 or not self.session_report:return
        self.remember_full_position()
        item=self.shown_segments[row];self.playing=True;self.playback_kind='segment';self.play_range=(round(item['start_s']*1000),round(item['end_s']*1000));self.preview_stack.setCurrentIndex(1);self.playback_tools.show()
        url=QUrl.fromLocalFile(self.source_path())
        if self.player.source()==url and self.player.mediaStatus() in (QMediaPlayer.LoadedMedia,QMediaPlayer.BufferedMedia,QMediaPlayer.EndOfMedia):self.player.setPosition(self.play_range[0]);self.player.play()
        else:self.pending_playback_start=True;self.player.setSource(url)
    def media_loaded(self,status):
        if self.playing and self.pending_playback_start and status==QMediaPlayer.LoadedMedia:
            self.pending_playback_start=False
            self.player.setPosition(self.play_range[0] if self.play_range else self.full_position);self.player.play()
    def playback_position(self,position):
        if not self.seek.isSliderDown():self.seek.setValue(position)
        self.playback_time.setText('%s / %s'%(clock(position/1000)[:-4],clock(self.player.duration()/1000)[:-4]))
        if self.playing and self.play_range and position>=self.play_range[1]:self.player.pause()
    def remember_full_position(self):
        if self.playback_kind=='full':self.full_position=self.player.position()
    def apply_display_mode(self,*args):
        self.remember_full_position();self.playing=False;self.playback_kind=None;self.pending_playback_start=False
        self.player.stop();self.play_range=None
        whole=self.tabs.currentIndex()==1 and self.display_mode.currentIndex()==1
        self.playing=whole;self.playback_kind='full' if whole else None
        self.preview_stack.setCurrentIndex(1 if whole else 0);self.playback_tools.setVisible(whole)
        if whole and getattr(self,'video_path',None):
            url=QUrl.fromLocalFile(self.video_path)
            if self.player.source()==url and self.player.mediaStatus() in (QMediaPlayer.LoadedMedia,QMediaPlayer.BufferedMedia,QMediaPlayer.EndOfMedia):
                self.player.setPosition(self.full_position);self.player.play()
            else:self.pending_playback_start=True;self.player.setSource(url)
        elif not whole and self.latest_analysis_jpeg:self.analysis_frame(self.latest_analysis_jpeg)
    def playback_toggle(self):
        if self.player.playbackState()==QMediaPlayer.PlayingState:self.player.pause()
        elif not self.player.source().isEmpty():
            if self.play_range and self.player.position()>=self.play_range[1]:self.player.setPosition(self.play_range[0])
            self.player.play()
    def back_to_preview(self):self.apply_display_mode()
    def export_clips(self,checked=False,automatic=False):
        items=list(self.session_report.get('segments',[])) if self.session_report else []
        if not items:self.error('当前没有命中时间段');return
        if self.archive and not self.archive.closed.is_set() and self.session_report.get('source')=='camera':self.error('请先结束录像再导出片段');return
        if self.export_worker and self.export_worker.isRunning():return
        self.export_worker=ExportWorker(self,self.source_path(),items,new_folder(Path(self.session_report['path']),'clips'))
        self.export_worker.ready.connect(lambda items:self.export_finished(items));self.export_worker.failed.connect(lambda text:self.export_failed(text));self.export_worker.progress.connect(self.error)
        self.export_button.setEnabled(False);self.export_worker.start()
    def export_finished(self,items):self.export_button.setEnabled(True);self.error('已导出 %d 个片段，保留原视频音轨'%len(items))
    def export_failed(self,text):self.export_button.setEnabled(True);self.error(text)
    def open_output(self):
        path=self.session_report['path'] if self.session_report else self.output_root.text();QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(path).resolve())))
    def tick(self):
        if not self.playing and self.tabs.currentIndex()!=1:super().tick()
        if self.tabs.currentIndex()==0 and not self.playing and self.link:
            fps=self.status_data.get('camera',{}).get('fps',0)
            phase={'idle':'未开始','preparing':'准备中','stopping':'正在保存'}.get(self.live_state)
            inference=phase or self.inference_fps_text(self.status_data.get('inference',{}))
            self.metrics.setText('视频 %.1f FPS · 推理 %s'%(fps,inference))
            preview=self.link.state.preview
            if preview and time.monotonic()-preview[2]<=2:self.notice.setText('结束录像后会保存完整视频和命中画面。')
        if self.archive and self.archive.error and not getattr(self.archive,'fault_stop_sent',False):
            self.archive.fault_stop_sent=True;self.stop_inference();self.archive.stop()
        if self.device_received_at and (not self.link or time.monotonic()-self.device_received_at>3):
            self.device_updated.setText('状态暂未更新')
            self.device_summary.setText('等待设备实时状态。')
            for row in range(self.hardware_table.rowCount()):self.hardware_table.item(row,1).setText('—')
    def error(self,text):
        super().error(text)
        if text.startswith(('视频：','控制：','串口：')):
            self.want_recording=False;self.pending_start=False;self.manual_update=False;self.query_feedback_revision=None
            if self.archive and not self.archive.closed.is_set():self.archive.error=text;self.archive.stop()
            else:self.set_live_state('idle')
    def closeEvent(self,event):
        if self.archive and not self.archive.closed.is_set():self.stop_inference();self.error('录像正在整理，完成后再关闭');event.ignore();return
        if self.analysis_worker and self.analysis_worker.isRunning():self.cancel_analysis();self.error('视频分析正在取消，完成后再关闭');event.ignore();return
        if self.export_worker and self.export_worker.isRunning():self.export_worker.cancel.set();self.error('片段导出正在取消，完成后再关闭');event.ignore();return
        self.player.stop();super().closeEvent(event)
