"""Every-frame Ethernet analysis with source PTS and bounded result credits."""
import base64
import io
import json
from pathlib import Path
import socket
import time
import uuid
import numpy as np
from .protocol import Decoder,JSON,INPUT_FRAME,encode_message,pack_image
from .semantic_media import build_segments,export_segments
from .temporal_segments import segment_report
from .recent_fps import RecentFps

def video_info(path):
    import av
    with av.open(str(path)) as container:
        stream=container.streams.video[0]
        duration=float(stream.duration*stream.time_base) if stream.duration else float(container.duration or 0)/1000000
        return dict(width=stream.width,height=stream.height,frames=stream.frames,duration_s=duration,fps=float(stream.average_rate or 25))

def analyze_video(path,host,items,features,identity,directory,threshold=.25,on_progress=None,on_frame=None,cancel=None,continuity=True):
    import av
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=False);(directory/'matches').mkdir()
    job_id=uuid.uuid4().hex;decoder=Decoder();pending={};rows=[];sent=received=0
    ended=False;begun=False;report={'ok':False,'source':str(Path(path).resolve()),'job_id':job_id,'items':items,'threshold':threshold}
    started=time.monotonic();last_event=started;origin=None;recent_fps=RecentFps()
    with socket.create_connection((host,8765),timeout=10) as sock,av.open(str(path)) as container,(directory/'results.jsonl').open('w',encoding='utf-8') as log:
        sock.settimeout(.1)
        def send(value):sock.sendall(encode_message(JSON,value))
        def messages():
            try:data=sock.recv(131072)
            except socket.timeout:return []
            if not data:raise ConnectionError('板端关闭视频分析连接')
            return [json.loads(p.decode()) for kind,p in decoder.feed(data) if kind==JSON]
        def command(op,**kw):
            key=uuid.uuid4().hex;send(dict(op=op,request_id=key,**kw));end=time.monotonic()+30
            while time.monotonic()<end:
                for value in messages():
                    if value.get('request_id')==key:
                        if not value.get('ok'):raise RuntimeError(value.get('error','板端拒绝任务'))
                        return value['result']
            raise TimeoutError('板端任务确认超时')
        try:
            send(dict(op='hello'));hello=None;end=time.monotonic()+10
            while hello is None and time.monotonic()<end:
                for value in messages():
                    if value.get('type')=='hello':hello=value
            if hello is None:raise TimeoutError('视频分析握手失败')
            if hello['inference']['state']!='STOPPED':raise RuntimeError('请先结束实时录像，等待板端停止')
            command('settings',threshold=threshold)
            encoded=base64.b64encode(np.asarray(features,dtype='<f4').tobytes()).decode('ascii')
            command('queries',items=items,features_f32_b64=encoded,identity=identity,revision=hello['query_revision']+1)
            command('upload_begin',job_id=job_id);begun=True
            frames=iter(container.decode(video=0));stream=container.streams.video[0]
            info=video_info(path);duration=info['duration_s']
            while not ended or pending:
                if cancel and cancel.is_set():raise InterruptedError('视频逐帧分析已取消')
                while not ended and len(pending)<16:
                    try:frame=next(frames)
                    except StopIteration:
                        ended=True;send(dict(op='upload_finish',job_id=job_id,frame_count=sent,request_id='upload-eof'));break
                    source_time=float(frame.pts*frame.time_base) if frame.pts is not None else sent/float(stream.average_rate or 25)
                    if origin is None:origin=source_time
                    stamp=source_time-origin
                    image=frame.to_image();out=io.BytesIO();image.save(out,format='JPEG',quality=95)
                    jpeg=out.getvalue();meta=dict(frame_id=sent,video_time_s=stamp,job_id=job_id,width=frame.width,height=frame.height)
                    pending[sent]=(stamp,jpeg)
                    sock.settimeout(10);sock.sendall(encode_message(INPUT_FRAME,pack_image(meta,jpeg)));sock.settimeout(.1)
                    sent+=1
                for value in messages():
                    if value.get('type')=='ack' and value.get('request_id')=='upload-eof' and not value.get('ok'):raise RuntimeError(value.get('error','帧数不一致'))
                    if value.get('type')=='status' and value.get('inference',{}).get('state')=='FAILED':raise RuntimeError(value['inference']['error'])
                    if value.get('type')!='result' or value.get('job_id')!=job_id:continue
                    fid=value['frame_id']
                    if fid!=received or fid not in pending:raise RuntimeError('视频结果重复、缺失或乱序')
                    stamp,jpeg=pending.pop(fid);received+=1;last_event=time.monotonic()
                    recent_fps.add(value['completed_monotonic'])
                    if abs(value['video_time_s']-stamp)>1e-6:raise RuntimeError('视频帧时间身份不一致')
                    row=dict(frame_id=fid,time_s=stamp,ranking=value['ranking'],score_engine=value.get('score_engine'))
                    rows.append(row);log.write(json.dumps(row,ensure_ascii=False)+'\n');log.flush()
                    for hit in row['ranking']:
                        if hit['score']>=threshold:(directory/'matches'/('%010d-q%s.jpg'%(fid,hit['id']))).write_bytes(jpeg)
                    if on_frame:on_frame(jpeg)
                    if on_progress:on_progress(dict(sent=sent,completed=received,source_time_s=stamp,duration_s=duration,source_fps=info['fps'],fps=recent_fps.value(),fps_window=10,fps_samples=recent_fps.samples,ended=ended))
                if time.monotonic()-last_event>180:raise TimeoutError('板端180秒未返回视频结果')
            # All frames acknowledged, then wait for normal hardware cleanup.
            end=time.monotonic()+40;stopped=False
            while time.monotonic()<end:
                for value in messages():
                    if value.get('type')=='status':
                        state=value['inference']['state']
                        if state=='FAILED':raise RuntimeError(value['inference']['error'])
                        if state=='STOPPED':stopped=True;break
                if stopped:break
            if not stopped:raise TimeoutError('板端模型正常排空未确认')
            intervals=segment_report(rows,threshold,duration=max(duration,rows[-1]['time_s']+.04) if rows else duration,continuity=continuity)
            if not sent or received!=sent:raise RuntimeError('视频未完整处理')
            report.update(ok=True,frames=sent,completed=received,elapsed_s=time.monotonic()-started,**intervals)
        except BaseException as exc:
            report.update(error=type(exc).__name__+': '+str(exc),frames=sent,completed=received,**segment_report(rows,threshold,continuity=continuity))
            if begun:
                try:send(dict(op='upload_cancel',job_id=job_id,request_id='cancel'))
                except OSError:pass
            raise
        finally:
            (directory/'session.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            (directory/'segments.json').write_text(json.dumps(report.get('segments',[]),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            (directory/'candidates.json').write_text(json.dumps(report.get('candidates',[]),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return dict(report,path=str(directory))
