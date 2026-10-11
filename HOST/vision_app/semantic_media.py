"""Host video archive, frame identity and semantic intervals; no board codecs."""
import collections
from fractions import Fraction
import json
from pathlib import Path
import queue
import subprocess
import threading
import time
import tempfile
from .temporal_segments import SegmentTracker,segment_report

def build_segments(rows,threshold=.25,gap_s=1,padding_s=.5,duration=None,continuity=True):
    return segment_report(rows,threshold,gap_s,padding_s,duration,continuity)['segments']

def export_segments(source,segments,destination,on_progress=None,cancel=None,group_by_query=False):
    import imageio_ffmpeg
    destination=Path(destination);destination.mkdir(parents=True,exist_ok=True);outputs=[]
    if group_by_query:
        groups=collections.OrderedDict()
        for item in segments:groups.setdefault((item['query_id'],item['label']),[]).append(item)
        with tempfile.TemporaryDirectory(prefix='.parts-',dir=destination) as temporary:
            for index,((qid,label),members) in enumerate(groups.items()):
                if cancel and cancel.is_set():raise InterruptedError('片段导出已取消')
                # Union overlapping playback padding so one source frame is not duplicated.
                cuts=[]
                for member in sorted(members,key=lambda x:x['start_s']):
                    if cuts and member['start_s']<=cuts[-1]['end_s']:
                        cuts[-1]['end_s']=max(cuts[-1]['end_s'],member['end_s'])
                    else:cuts.append(dict(member))
                part_root=Path(temporary)/('query-%04d'%index)
                parts=export_segments(source,cuts,part_root,cancel=cancel)
                listing=Path(temporary)/('query-%04d.txt'%index)
                listing.write_text(''.join("file '%s'\n"%Path(p['path']).resolve().as_posix().replace("'","'\\''") for p in parts),encoding='utf-8')
                target=destination/('query-%04d.mp4'%index)
                _export_command([imageio_ffmpeg.get_ffmpeg_exe(),'-hide_banner','-loglevel','error','-y','-f','concat','-safe','0','-i',str(listing),'-c','copy','-movflags','+faststart',str(target)],cancel)
                import av
                mapping=[];offset=0.
                for cut,part in zip(cuts,parts):
                    with av.open(part['path']) as container:length=float(container.duration or 0)/1e6
                    mapping.append(dict(source_start_s=cut['start_s'],source_end_s=cut['end_s'],output_start_s=offset,output_end_s=offset+length))
                    offset+=length
                outputs.append(dict(query_id=qid,label=label,path=str(target),source_intervals=mapping,segments=members,duration_s=offset))
                if on_progress:on_progress(index+1,len(groups))
        (destination/'clips.json').write_text(json.dumps(outputs,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        return outputs
    for i,item in enumerate(segments):
        if cancel and cancel.is_set():raise InterruptedError('片段导出已取消')
        target=destination/('clip-%04d.mp4'%i)
        args=[imageio_ffmpeg.get_ffmpeg_exe(),'-hide_banner','-loglevel','error','-y','-ss',str(item['start_s']),'-i',str(source),'-t',str(max(.04,item['end_s']-item['start_s'])),'-map','0:v:0','-map','0:a?','-c:v','libx264','-preset','veryfast','-crf','20','-fps_mode','vfr','-c:a','aac','-movflags','+faststart',str(target)]
        _export_command(args,cancel)
        outputs.append(dict(item,path=str(target)))
        if on_progress:on_progress(i+1,len(segments))
    (destination/'clips.json').write_text(json.dumps(outputs,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return outputs

def _export_command(args,cancel):
        proc=subprocess.Popen(args,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        while proc.poll() is None:
            if cancel and cancel.wait(.1):proc.terminate();proc.wait();raise InterruptedError('片段导出已取消')
            if not cancel:time.sleep(.1)
        error=proc.stderr.read().decode('utf-8','replace');proc.stderr.close()
        if proc.returncode:raise RuntimeError('视频片段导出失败：'+error[-1000:])

class SemanticArchive:
    """Mux received camera JPEG once; retain only a bounded look-back cache."""
    def __init__(self,directory,items,revision,threshold=.25,on_update=None,on_missing=None,continuity=True):
        self.path=Path(directory);self.path.mkdir(parents=True,exist_ok=False)
        (self.path/'matches').mkdir()
        self.items=items;self.revision=revision;self.threshold=threshold
        self.segment_tracker=SegmentTracker(threshold,continuity);self.candidates=[]
        self.on_update=on_update or (lambda x:None);self.on_missing=on_missing or (lambda x:None)
        self.queue=queue.Queue(256);self.closed=threading.Event();self.closing=False
        self.error=None;self.frames=0;self.gaps=0;self.rows=[];self.origin=None;self.last_time=0
        self.cache=collections.OrderedDict();self.pending={};self.saved=set();self.segments=[]
        self.end_frame_id=None;self.end_requested_at=None;self.last_saved_id=None
        self.thread=threading.Thread(target=self._run,daemon=True);self.thread.start()
    def enqueue(self,kind,value):
        if self.closing or self.closed.is_set():return
        try:self.queue.put_nowait((kind,value))
        except queue.Full:
            self.error='主机录像队列满，录像已中断，未丢帧后冒充完整录像';self.closing=True
    def feed_frame(self,meta,jpeg):self.enqueue('frame',(dict(meta),bytes(jpeg)))
    def feed_result(self,result):
        if result.get('source','camera')=='camera' and result.get('query_revision')==self.revision:self.enqueue('result',dict(result))
    def feed_missing(self,meta,jpeg):self.enqueue('missing',(meta,jpeg))
    def stop(self):self.closing=True
    def finish_at(self,frame_id):
        if self.end_frame_id is None:
            self.end_frame_id=max(frame_id,self.last_saved_id if self.last_saved_id is not None else frame_id)
            self.end_requested_at=time.monotonic()
    def _save_matches(self,result,jpeg):
        for hit in result.get('ranking',[]):
            if hit['score']>=self.threshold:
                name='%010d-q%s.jpg'%(result['frame_id'],hit['id'])
                if name not in self.saved:(self.path/'matches'/name).write_bytes(jpeg);self.saved.add(name)
    def _run(self):
        import av
        container=stream=None;last_id=None
        try:
            with (self.path/'frames.jsonl').open('w',encoding='utf-8') as frame_log,(self.path/'results.jsonl').open('w',encoding='utf-8') as result_log:
                while not self.closing or not self.queue.empty():
                    if self.end_frame_id is not None and self.last_saved_id is not None and self.last_saved_id>=self.end_frame_id:self.closing=True
                    if self.end_requested_at and time.monotonic()-self.end_requested_at>10 and (self.last_saved_id is None or self.last_saved_id<self.end_frame_id):raise TimeoutError('录像尾帧未到达，已标记不完整')
                    try:kind,value=self.queue.get(timeout=.1)
                    except queue.Empty:continue
                    if kind in ('frame','missing'):
                        meta,jpeg=value;fid=meta['frame_id']
                        if kind=='frame':
                            if self.end_frame_id is not None and fid>self.end_frame_id:continue
                            stamp=meta['capture_monotonic']
                            if self.origin is None:
                                self.origin=stamp;container=av.open(str(self.path/'video.mkv'),'w')
                                stream=container.add_stream('mjpeg',rate=25);stream.width=meta['width'];stream.height=meta['height'];stream.pix_fmt='yuvj422p';stream.time_base=Fraction(1,1000000)
                            at=stamp-self.origin
                            if at<self.last_time:raise ValueError('摄像头时间倒退，录像已停止')
                            if last_id is not None:self.gaps+=max(0,fid-last_id-1)
                            packet=av.Packet(jpeg);packet.pts=packet.dts=round(at*1000000);packet.time_base=Fraction(1,1000000);packet.duration=40000;packet.stream=stream;container.mux(packet)
                            frame_log.write(json.dumps(dict(frame_id=fid,time_s=at,source_time=stamp))+'\n')
                            self.frames+=1;self.last_time=at;last_id=fid
                            self.last_saved_id=fid
                        self.cache[fid]=jpeg
                        if fid in self.pending:self._save_matches(self.pending.pop(fid),jpeg)
                        while len(self.cache)>512:self.cache.popitem(last=False)
                    elif kind=='result':
                        if self.origin is None:continue
                        at=value['capture_monotonic']-self.origin
                        if at<0:continue
                        row=dict(frame_id=value['frame_id'],time_s=at,ranking=value.get('ranking',[]),query_revision=value['query_revision'],source='camera')
                        self.rows.append(row);result_log.write(json.dumps(row,ensure_ascii=False)+'\n');result_log.flush()
                        if any(h['score']>=self.threshold for h in row['ranking']):
                            jpeg=self.cache.get(row['frame_id'])
                            if jpeg:self._save_matches(row,jpeg)
                            else:
                                self.pending[row['frame_id']]=row;self.on_missing(row['frame_id'])
                        self.segment_tracker.add(row)
                        intervals=self.segment_tracker.report(duration=self.last_time+.04)
                        self.segments=intervals['segments'];self.candidates=intervals['candidates']
                        self.on_update(dict(path=str(self.path),frames=self.frames,hits=len(self.saved),**intervals))
        except BaseException as exc:self.error=type(exc).__name__+': '+str(exc)
        finally:
            if container:
                try:container.close()
                except Exception as exc:self.error=str(exc)
            if self.pending and not self.error:self.error='有%d个命中帧未收到，索引保留但截图不完整'%len(self.pending)
            if self.gaps and not self.error:self.error='摄像头流缺少%d帧，录像已标记不完整'%self.gaps
            intervals=self.segment_tracker.report(duration=self.last_time+.04)
            self.segments=intervals['segments'];self.candidates=intervals['candidates']
            report=dict(ok=self.error is None and self.frames>0,error=self.error,frames=self.frames,received_frame_gaps=self.gaps,missing_hit_frames=sorted(self.pending),expected_end_frame_id=self.end_frame_id,last_saved_frame_id=self.last_saved_id,duration_s=self.last_time+.04 if self.frames else 0,items=self.items,threshold=self.threshold,source='camera',video='video.mkv',**intervals)
            try:
                (self.path/'session.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
                (self.path/'segments.json').write_text(json.dumps(self.segments,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
                (self.path/'candidates.json').write_text(json.dumps(self.candidates,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            except BaseException as exc:
                self.error='录像收尾写入失败：'+str(exc);report.update(ok=False,error=self.error)
            finally:
                self.closed.set();self.on_update(dict(report,path=str(self.path),done=True,hits=len(self.saved)))
