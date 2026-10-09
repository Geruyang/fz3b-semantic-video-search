"""Actual two-workflow UI, board inference, saved video and clip decoding."""
import json
import time
from pathlib import Path
import av
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from vision_app.semantic_ui import SemanticWindow
from vision_app.tools.board_link import ROOT

def main():
    output=ROOT/'artifacts/semantic-video-20261009';app=QApplication([]);w=SemanticWindow();w.show();w.output_root.setText(str(output/'gui-output'));w.threshold.setValue(-1)
    begun=time.monotonic();stage=0;record={'ok':False};ending=False
    def check():
        nonlocal stage,ending
        if ending:return
        try:
            if time.monotonic()-begun>130:raise TimeoutError('semantic UI acceptance stage %d: %s'%(stage,w.log_label.text()))
            if stage==0 and w.status_data.get('inference',{}).get('state')=='STOPPED':
                assert not w.overlay.isVisible();w.start_inference();stage=1
            elif stage==1 and w.archive and len(w.archive.rows)>=8:
                w.grab().save(str(output/'gui-live-recording.png'));w.stop_inference();stage=2
            elif stage==2 and w.archive.closed.is_set():
                report=json.loads((w.archive.path/'session.json').read_text(encoding='utf-8'));assert report['ok'],report
                with av.open(str(w.archive.path/'video.mkv')) as c:decoded=sum(1 for unused in c.decode(video=0))
                assert decoded==report['frames'] and len(list((w.archive.path/'matches').glob('*.jpg')))>=8
                record['live']=dict(report,path=str(w.archive.path),decoded_frames=decoded)
                w.tabs.setCurrentIndex(1);w.video_path=str(output/'media-smoke-2/video.mkv');w.file_label.setText('实际全帧测试：3帧 VFR 视频');w.start_analysis();stage=3
            elif stage==3 and getattr(w,'offline_report',None) and w.export_worker and not w.export_worker.isRunning():
                assert w.offline_report['ok'] and w.offline_report['completed']==3,'offline frame count'
                clips=json.loads((w.export_worker.destination/'clips.json').read_text(encoding='utf-8'));assert len(clips)==2,'each line must remain a separate description'
                for clip in clips:
                    with av.open(clip['path']) as c:assert sum(1 for unused in c.decode(video=0))>=1
                w.grab().save(str(output/'gui-offline-results.png'));record['offline']=w.offline_report;record['clips']=clips
                w.resize(1000,670);w.grab().save(str(output/'gui-minimum.png'))
                record['previous_live_path']=str(w.archive.path);w.tabs.setCurrentIndex(0);w.start_inference();stage=4
            elif stage==4 and w.archive and str(w.archive.path)!=record['previous_live_path'] and len(w.archive.rows)>=2:
                w.stop_inference();stage=5
            elif stage==5 and w.archive.closed.is_set():
                assert not w.archive.error,'live restart after offline query revision must work'
                record.update(ok=True,live_restart_after_offline=True,elapsed_s=time.monotonic()-begun);ending=True;w.close();app.quit()
        except BaseException as exc:
            import traceback
            record['error']=type(exc).__name__+': '+str(exc);record['traceback']=traceback.format_exc();ending=True
            if w.archive:w.archive.stop()
            if w.analysis_worker:w.analysis_worker.cancel.set();w.analysis_worker.wait(10000)
            if w.worker.isRunning():w.worker.wait(10000)
            w.close();app.quit()
    timer=QTimer();timer.timeout.connect(check);timer.start(100);QTimer.singleShot(100,w.connect_board);app.exec()
    (output/'gui-acceptance.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(ok=record['ok'],elapsed_s=record.get('elapsed_s'),error=record.get('error'))))
    if not record['ok']:raise RuntimeError(record.get('error'))

if __name__=='__main__':main()
