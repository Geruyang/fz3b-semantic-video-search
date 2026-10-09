"""Two semantic video workflows in the existing native workstation."""
import datetime
import json
from pathlib import Path
import threading
import time
from PySide6.QtCore import Qt,QThread,Signal,QUrl,QTimer,QStandardPaths
from PySide6.QtGui import QDesktopServices,QImage,QPixmap
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QLineEdit,QTextEdit,QDoubleSpinBox,QFileDialog,QProgressBar,QTableWidget,QTableWidgetItem,QHeaderView,QTabWidget,QStackedWidget
from PySide6.QtMultimedia import QMediaPlayer,QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget
from .client import Window
from .text_encoder import TextEncoder,parse_prompts,PRESETS
from .translation import same_intent
from .semantic_media import SemanticArchive,export_segments
from .video_analysis import analyze_video,video_info

def clock(seconds):
    ms=round(seconds*1000);return '%02d:%02d:%02d.%03d'%(ms//3600000,(ms//60000)%60,(ms//1000)%60,ms%1000)
def new_folder(root,prefix):return Path(root)/(prefix+'-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f'))

class AnalysisWorker(QThread):
    progress=Signal(object);preview=Signal(bytes);ready=Signal(object);failed=Signal(str)
    def __init__(self,owner,path,text,directory,threshold):
        super().__init__(owner);self.owner=owner;self.path=path;self.text=text;self.directory=directory;self.threshold=threshold;self.cancel=threading.Event()
        self.host=owner.address.text().strip();self.token=owner.token.text().strip()
    def run(self):
        try:
            self.progress.emit(dict(stage='正在主机编码描述…'))
            items=self.owner.translator.items(parse_prompts(self.text,allow_chinese=True))
            if self.owner.encoder is None:self.owner.encoder=TextEncoder(self.owner.contract,str(self.owner.model_root))
            features,identity=self.owner.encoder.encode(items)
            report=analyze_video(self.path,self.host,self.token,items,features,identity,self.directory,self.threshold,self.progress.emit,self.preview.emit,self.cancel)
            self.ready.emit(report)
        except BaseException as exc:self.failed.emit(str(exc))

class ExportWorker(QThread):
    ready=Signal(object);failed=Signal(str);progress=Signal(str)
    def __init__(self,owner,source,segments,destination):
        super().__init__(owner);self.source=source;self.segments=segments;self.destination=destination;self.cancel=threading.Event()
    def run(self):
        try:self.ready.emit(export_segments(self.source,self.segments,self.destination,lambda i,n:self.progress.emit('正在导出 %d / %d 个片段'%(i,n)),self.cancel))
        except BaseException as exc:self.failed.emit(str(exc))

class ArchiveSignals(QWidget):
    updated=Signal(object);missing=Signal(int)

class SemanticWindow(Window):
    def __init__(self):
        self.archive=None;self.want_recording=False;self.end_recording=False;self.analysis_worker=None;self.export_worker=None
        self.session_report=None;self.clips={};self.playing=False
        super().__init__()
        self.setWindowTitle('FZ3B · 语义视频工作台')
        self.archive_events=ArchiveSignals(self);self.archive_events.hide()
        self.archive_events.updated.connect(self.archive_updated);self.archive_events.missing.connect(lambda fid:self.request(dict(op='frame_get',frame_id=fid)))
    def build_ui(self):
        super().build_ui()
        self.overlay.hide();self.video.setMinimumSize(480,240)
        self.tabs=self.findChild(QTabWidget);self.tabs.setTabText(0,'实时文字找场景');self.tabs.removeTab(1)
        self.prompts.setPlainText('桌面上的杯子\n有人在房间里')
        self.start_button.setText('开始录像与检索');self.encode_button.setText('更新描述')
        self.threshold.setValue(.2)
        for label in self.tabs.widget(0).findChildren(QLabel):
            if label.text().startswith('每行一条'):label.setText('每行一个描述，中文在本机离线翻译。\n保存完整视频、命中原图及出现时间段。')
            if label.text()=='当前候选 · 余弦相似度':label.setText('最近分析帧 · 相似度（不是概率）')
        for button in self.tabs.widget(0).findChildren(QPushButton):
            if button.text()=='停止推理':button.setText('结束录像')
            if button.text()=='物品与场景预设':self.preset_button=button
        page=self.tabs.widget(0);layout=page.layout()
        output=QHBoxLayout();self.output_root=QLineEdit(str(Path(QStandardPaths.writableLocation(QStandardPaths.MoviesLocation))/'FZ3B语义检索'))
        choose=QPushButton('选择目录');choose.clicked.connect(self.choose_output)
        output.addWidget(self.output_root,1);output.addWidget(choose)
        layout.insertWidget(2,QLabel('保存位置'));layout.insertLayout(3,output)
        level=QHBoxLayout();level.addWidget(QLabel('命中相似度阈值'));self.live_threshold=QDoubleSpinBox();self.live_threshold.setRange(-1,1);self.live_threshold.setSingleStep(.01);self.live_threshold.setValue(self.threshold.value());level.addWidget(self.live_threshold);level.addStretch();layout.insertLayout(4,level)
        self.live_threshold.valueChanged.connect(self.threshold.setValue);self.threshold.valueChanged.connect(self.live_threshold.setValue)
        self.live_threshold.setToolTip('余弦相似度，不是概率。降低阈值增加命中，也可能增加误报。')
        self.prompts.setMaximumHeight(125)
        self.live_summary=QLabel('尚未开始录像');self.live_summary.setWordWrap(True);layout.addWidget(self.live_summary)
        offline=QWidget();v=QVBoxLayout(offline)
        title=QLabel('检索视频中的物品与场景');title.setObjectName('title');v.addWidget(title)
        self.file_label=QLabel('选择本机视频，逐帧发送板卡分析');self.file_label.setWordWrap(True);v.addWidget(self.file_label)
        self.choose_video_button=QPushButton('选择视频…');self.choose_video_button.clicked.connect(self.choose_video);v.addWidget(self.choose_video_button)
        self.offline_prompts=QTextEdit();self.offline_prompts.setPlainText('桌面上的杯子\n有人在房间里');self.offline_prompts.setMaximumHeight(155);v.addWidget(QLabel('要寻找的描述 · 每行一条'));v.addWidget(self.offline_prompts)
        level=QHBoxLayout();level.addWidget(QLabel('命中相似度阈值'));self.offline_threshold=QDoubleSpinBox();self.offline_threshold.setRange(-1,1);self.offline_threshold.setSingleStep(.01);self.offline_threshold.setValue(self.threshold.value());level.addWidget(self.offline_threshold);level.addStretch();v.addLayout(level)
        self.offline_threshold.valueChanged.connect(self.threshold.setValue);self.threshold.valueChanged.connect(self.offline_threshold.setValue)
        self.file_details=QLabel('完整分析每一帧，耗时随视频帧数增加。');self.file_details.setWordWrap(True);v.addWidget(self.file_details)
        row=QHBoxLayout();self.analyze_button=QPushButton('开始逐帧分析');self.analyze_button.clicked.connect(self.start_analysis)
        self.cancel_analysis_button=QPushButton('取消');self.cancel_analysis_button.clicked.connect(self.cancel_analysis);self.cancel_analysis_button.setEnabled(False)
        row.addWidget(self.analyze_button);row.addWidget(self.cancel_analysis_button);v.addLayout(row)
        self.analysis_progress=QProgressBar();self.analysis_progress.setRange(0,1000);v.addWidget(self.analysis_progress)
        self.analysis_notice=QLabel('分析完成后，选择下方时间段播放或导出。');self.analysis_notice.setWordWrap(True);v.addWidget(self.analysis_notice);v.addStretch()
        self.tabs.insertTab(1,offline,'视频语义检索');self.tabs.currentChanged.connect(self.page_changed)
        video_parent=self.video.parentWidget();video_layout=video_parent.layout()
        self.preview_stack=QStackedWidget();self.preview_stack.addWidget(self.video)
        self.playback=QVideoWidget();self.preview_stack.addWidget(self.playback);video_layout.insertWidget(0,self.preview_stack,1)
        self.player=QMediaPlayer(self);self.audio=QAudioOutput(self);self.player.setAudioOutput(self.audio);self.player.setVideoOutput(self.playback)
        self.player.mediaStatusChanged.connect(self.media_loaded)
        self.player.positionChanged.connect(self.playback_position)
        self.player.errorOccurred.connect(lambda *args:self.error('播放失败：'+self.player.errorString()))
        tools=QHBoxLayout();tools.addWidget(QLabel('命中时间段'))
        back=QPushButton('返回画面');back.clicked.connect(self.back_to_preview);tools.addWidget(back)
        self.play_button=QPushButton('播放所选');self.play_button.clicked.connect(self.play_segment);tools.addWidget(self.play_button)
        self.export_button=QPushButton('导出片段');self.export_button.clicked.connect(self.export_clips);tools.addWidget(self.export_button)
        folder=QPushButton('打开输出');folder.clicked.connect(self.open_output);tools.addWidget(folder);video_layout.addLayout(tools)
        self.segments_table=QTableWidget(0,4);self.segments_table.setHorizontalHeaderLabels(['描述','开始时间','结束时间','命中帧 / 最佳相似度'])
        self.segments_table.setSelectionBehavior(QTableWidget.SelectRows);self.segments_table.setSelectionMode(QTableWidget.SingleSelection);self.segments_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.segments_table.horizontalHeader().setSectionResizeMode(0,QHeaderView.Stretch);self.segments_table.horizontalHeader().setSectionResizeMode(3,QHeaderView.Stretch)
        self.segments_table.setMaximumHeight(190);self.segments_table.setMinimumHeight(140);self.segments_table.doubleClicked.connect(self.play_segment);video_layout.addWidget(self.segments_table)
        self.notice.setText('实时视频与检索结果分开展示；时间段依据捕获时间。')
        self.setStyleSheet(self.styleSheet()+'''QTableWidget {background:#142033;border:1px solid #30425B;alternate-background-color:#1B2A40;selection-background-color:#245D9E;} QHeaderView::section {background:#203049;color:#DCE8F8;padding:7px;border:0;} QProgressBar {border:1px solid #41526A;border-radius:5px;text-align:center;min-height:24px;} QProgressBar::chunk {background:#2B87B9;}''')
    def page_changed(self,index):
        self.playing=False;self.player.stop();self.preview_stack.setCurrentIndex(0)
        if index==1 and getattr(self,'offline_report',None):self.show_segments(self.offline_report)
        elif index==0 and self.archive:self.show_segments(dict(path=str(self.archive.path),segments=self.archive.segments,source='camera'))
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
        if self.mode.currentIndex():self.error('完整录像检索请使用以太网，串口仍支持状态与控制');return
        if self.archive and not self.archive.closed.is_set():self.error('正在录像，请先结束当前任务');return
        if self.analysis_worker and self.analysis_worker.isRunning():self.error('板卡正在逐帧分析视频');return
        if self.status_data.get('inference',{}).get('state')!='STOPPED':self.error('请等待板端推理正常停止');return
        self.want_recording=True;self.end_recording=False;self.pending_start=True
        try:items=parse_prompts(self.prompts.toPlainText(),allow_chinese=True)
        except ValueError as exc:self.error(str(exc));return
        if not hasattr(self,'last_encoded') or not same_intent(items,self.last_encoded['items']) or self.accepted_revision!=self.last_encoded['revision']:self.encode()
        else:self.resume_pending_start()
    def resume_pending_start(self):
        if not self.want_recording:return super().resume_pending_start()
        if not self.pending_start or self.accepted_revision!=self.last_encoded['revision']:return
        current=parse_prompts(self.prompts.toPlainText(),allow_chinese=True)
        if not same_intent(current,self.last_encoded['items']):self.encode();return
        try:
            root=Path(self.output_root.text());root.mkdir(parents=True,exist_ok=True)
            self.archive=SemanticArchive(new_folder(root,'live'),self.last_encoded['items'],self.accepted_revision,self.threshold.value(),self.archive_events.updated.emit,self.archive_events.missing.emit)
            self.prompts.setReadOnly(True);self.start_button.setEnabled(False);self.encode_button.setEnabled(False)
            self.preset_button.setEnabled(False)
            self.set_threshold_enabled(False)
            self.request(dict(op='settings',threshold=self.threshold.value()))
            self.live_summary.setText('正在录像 · 模型准备中，视频连续保存')
            self.pending_start=False;self.want_recording=False;self.request(dict(op='start'))
        except Exception as exc:self.pending_start=False;self.want_recording=False;self.error(str(exc))
    def stop_inference(self):
        self.want_recording=False;self.end_recording=True;super().stop_inference()
        if self.archive:self.live_summary.setText('正在停止推理并整理末尾结果…')
    def message(self,message):
        if message.get('_connection_epoch',self.connection_epoch)!=self.connection_epoch:return
        if message.get('type')=='result' and self.archive:self.archive.feed_result(message)
        super().message(message)
        if message.get('type') in ('hello','status') and self.archive and not self.archive.closed.is_set():
            if self.end_recording and message.get('inference',{}).get('state')=='STOPPED':self.archive.finish_at(message.get('camera',{}).get('frames',0)-1)
            if message.get('inference',{}).get('state')=='FAILED':self.archive.error=message['inference']['error'];self.archive.stop()
    def archive_updated(self,value):
        if value.get('done'):
            self.prompts.setReadOnly(False);self.start_button.setEnabled(True);self.encode_button.setEnabled(True)
            self.preset_button.setEnabled(True)
            self.set_threshold_enabled(True)
            self.live_summary.setText(('录像已保存' if value['ok'] else '录像中断：'+str(value['error']))+'\n'+value['path'])
        else:self.live_summary.setText('录像中 · %d 帧 · %d 张命中原图 · %d 个时间段'%(value['frames'],value['hits'],len(value['segments'])))
        if self.tabs.currentIndex()==0:self.show_segments(dict(value,source='camera'))
    def choose_video(self):
        path,_=QFileDialog.getOpenFileName(self,'选择要检索的视频','','视频 (*.mp4 *.mkv *.mov *.avi *.webm);;全部文件 (*)')
        if not path:return
        try:
            info=video_info(path);self.video_path=path;self.file_label.setText(Path(path).name);self.file_label.setToolTip(path)
            frames=info['frames'] or round(info['duration_s']*info['fps'])
            self.file_details.setText('%d × %d · %.2f FPS · %s\n预计 %d 帧，按4 FPS分析约 %.1f 分钟。'%(info['width'],info['height'],info['fps'],clock(info['duration_s']),frames,frames/240))
        except Exception as exc:self.error('视频无法读取：'+str(exc))
    def preset_classify(self):
        if self.archive and not self.archive.closed.is_set():self.error('请先结束录像再修改描述');return
        self.prompts.setPlainText('\n'.join(label+' | '+text for label,text in PRESETS))
        self.query_status.setText('预设已填入，点击“开始录像与检索”开始任务')
    def start_analysis(self):
        if not self.link or self.mode.currentIndex():self.error('请连接板卡以太网');return
        if not getattr(self,'video_path',None):self.error('请先选择视频');return
        if self.archive and not self.archive.closed.is_set():self.error('请先结束实时录像');return
        if self.worker.isRunning() or self.status_data.get('inference',{}).get('state')!='STOPPED':self.error('请等待板卡停止及描述编码完成');return
        if self.analysis_worker and self.analysis_worker.isRunning():return
        root=Path(self.output_root.text());root.mkdir(parents=True,exist_ok=True)
        self.analysis_worker=AnalysisWorker(self,self.video_path,self.offline_prompts.toPlainText(),new_folder(root,'video'),self.threshold.value())
        self.analysis_worker.progress.connect(self.analysis_update);self.analysis_worker.preview.connect(self.analysis_frame);self.analysis_worker.ready.connect(self.analysis_done);self.analysis_worker.failed.connect(self.analysis_failed)
        self.analyze_button.setEnabled(False);self.choose_video_button.setEnabled(False);self.cancel_analysis_button.setEnabled(True);self.offline_prompts.setReadOnly(True)
        self.start_button.setEnabled(False);self.encode_button.setEnabled(False);self.preset_button.setEnabled(False)
        self.set_threshold_enabled(False)
        self.analysis_progress.setValue(0);self.analysis_worker.start()
        self.link.set_preview_enabled(False)
    def cancel_analysis(self):
        if self.analysis_worker:self.analysis_worker.cancel.set();self.analysis_notice.setText('正在取消并等待板端排空…')
    def analysis_update(self,value):
        if 'stage' in value:self.analysis_notice.setText(value['stage']);return
        ratio=min(1,value['source_time_s']/max(value['duration_s'],.001));self.analysis_progress.setValue(round(ratio*1000))
        remaining=max(0,value['duration_s']-value['source_time_s'])*value.get('source_fps',25)/max(value['fps'],.01)
        eta=clock(remaining) if value['fps'] else '正在测量'
        self.analysis_notice.setText('已分析 %d 帧 / 已发送 %d 帧\n视频位置 %s · %.2f FPS · 预计剩余 %s'%(value['completed'],value['sent'],clock(value['source_time_s']),value['fps'],eta))
        if self.tabs.currentIndex()==1:
            self.metrics.setText('本地视频 · 已分析 %d 帧 · 位置 %s'%(value['completed'],clock(value['source_time_s'])))
            self.notice.setText('逐帧检索完成后自动导出命中片段')
    def analysis_frame(self,jpeg):
        if self.tabs.currentIndex()==1 and not self.playing:
            image=QImage.fromData(jpeg);self.video.setPixmap(QPixmap.fromImage(image).scaled(self.video.size(),Qt.KeepAspectRatio,Qt.SmoothTransformation))
    def reset_analysis_buttons(self):
        self.analyze_button.setEnabled(True);self.choose_video_button.setEnabled(True);self.cancel_analysis_button.setEnabled(False);self.offline_prompts.setReadOnly(False);self.accepted_revision=0
        self.set_threshold_enabled(True)
        if self.link:self.link.set_preview_enabled(True)
        self.start_button.setEnabled(True);self.encode_button.setEnabled(True);self.preset_button.setEnabled(True);self.current_result=None
    def set_threshold_enabled(self,enabled):
        for widget in (self.threshold,self.live_threshold,self.offline_threshold):widget.setEnabled(enabled)
    def encoded(self,message):
        self.prompts.setToolTip('\n'.join(x['label']+' → '+x.get('translated_text',x['text']) for x in message['items']))
        super().encoded(message)
    def analysis_done(self,report):
        self.offline_report=report;self.reset_analysis_buttons();self.analysis_progress.setValue(1000)
        self.analysis_notice.setText('全部 %d 帧分析完成 · %d 个命中时间段\n%s'%(report['completed'],len(report['segments']),report['path']));self.show_segments(report)
        if self.tabs.currentIndex()==1:self.metrics.setText('全部 %d 帧分析完成 · %d 个命中时间段'%(report['completed'],len(report['segments'])))
        if report['segments']:self.export_clips()
    def analysis_failed(self,text):self.reset_analysis_buttons();self.analysis_notice.setText(text);self.error(text)
    def show_segments(self,report):
        self.session_report=report;items=report.get('segments',[]);self.segments_table.setRowCount(len(items))
        for row,item in enumerate(items):
            for col,text in enumerate((item['label'],clock(item['start_s']),clock(item['end_s']),'%d 帧 · %.3f'%(len(item['frame_ids']),item['best_score']))):self.segments_table.setItem(row,col,QTableWidgetItem(text))
    def source_path(self):
        if not self.session_report:return None
        return str(Path(self.session_report['path'])/'video.mkv') if self.session_report.get('source')=='camera' else self.session_report['source']
    def play_segment(self,*args):
        row=self.segments_table.currentRow()
        if row<0 or not self.session_report:return
        item=self.session_report['segments'][row];self.playing=True;self.play_range=(round(item['start_s']*1000),round(item['end_s']*1000));self.preview_stack.setCurrentIndex(1)
        url=QUrl.fromLocalFile(self.source_path())
        if self.player.source()==url and self.player.mediaStatus() in (QMediaPlayer.LoadedMedia,QMediaPlayer.BufferedMedia,QMediaPlayer.EndOfMedia):self.player.setPosition(self.play_range[0]);self.player.play()
        else:self.player.setSource(url)
    def media_loaded(self,status):
        if self.playing and status==QMediaPlayer.LoadedMedia:self.player.setPosition(self.play_range[0]);self.player.play()
    def playback_position(self,position):
        if self.playing and position>=self.play_range[1]:self.player.pause()
    def back_to_preview(self):self.playing=False;self.player.stop();self.preview_stack.setCurrentIndex(0)
    def export_clips(self):
        if not self.session_report or not self.session_report.get('segments'):self.error('当前没有命中时间段');return
        if self.archive and not self.archive.closed.is_set() and self.session_report.get('source')=='camera':self.error('请先结束录像再导出片段');return
        if self.export_worker and self.export_worker.isRunning():return
        self.export_worker=ExportWorker(self,self.source_path(),self.session_report['segments'],new_folder(Path(self.session_report['path']),'clips'))
        self.export_worker.ready.connect(lambda items:self.export_finished(items));self.export_worker.failed.connect(lambda text:self.export_failed(text));self.export_worker.progress.connect(self.error)
        self.export_button.setEnabled(False);self.export_worker.start()
    def export_finished(self,items):self.export_button.setEnabled(True);self.error('已导出 %d 个片段，保留原视频音轨'%len(items))
    def export_failed(self,text):self.export_button.setEnabled(True);self.error(text)
    def open_output(self):
        path=self.session_report['path'] if self.session_report else self.output_root.text();QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(path).resolve())))
    def tick(self):
        if not self.playing and self.tabs.currentIndex()!=1:super().tick()
        if self.archive and self.archive.error and not getattr(self.archive,'fault_stop_sent',False):
            self.archive.fault_stop_sent=True;self.stop_inference();self.archive.stop()
    def error(self,text):
        super().error(text)
        if text.startswith(('视频：','控制：')) and self.archive and not self.archive.closed.is_set():self.archive.error=text;self.archive.stop();self.request(dict(op='stop'))
    def closeEvent(self,event):
        if self.archive and not self.archive.closed.is_set():self.stop_inference();self.error('录像正在整理，完成后再关闭');event.ignore();return
        if self.analysis_worker and self.analysis_worker.isRunning():self.cancel_analysis();self.error('视频分析正在取消，完成后再关闭');event.ignore();return
        if self.export_worker and self.export_worker.isRunning():self.export_worker.cancel.set();self.error('片段导出正在取消，完成后再关闭');event.ignore();return
        self.player.stop();super().closeEvent(event)
