"""Host video archive, frame identity and semantic intervals; no board codecs."""
import collections
from fractions import Fraction
import json
from pathlib import Path
import queue
import subprocess
import threading
import time

def build_segments(rows,threshold=.25,gap_s=1,padding_s=.5,duration=None):
    active={};segments=[]
    for row in sorted(rows,key=lambda r:(r['time_s'],r['frame_id'])):
        stamp=row['time_s'];present=set()
        for hit in row.get('ranking',[]):
            key=(hit['id'],hit['label']);present.add(key)
            if hit['score']<threshold:
                if key in active:segments.append(active.pop(key))
                continue
            if key in active and stamp-active[key]['last_hit_s']>gap_s:segments.append(active.pop(key))
            if key not in active:active[key]=dict(query_id=key[0],label=key[1],first_hit_s=stamp,last_hit_s=stamp,frame_ids=[],best_score=hit['score'])
            item=active[key];item['last_hit_s']=stamp;item['frame_ids'].append(row['frame_id']);item['best_score']=max(item['best_score'],hit['score'])
        for key in list(active):
            if key not in present:segments.append(active.pop(key))
    segments.extend(active.values())
    for i,item in enumerate(sorted(segments,key=lambda r:(r['first_hit_s'],r['query_id']))):
        item.update(segment_id=i,start_s=max(0,item['first_hit_s']-padding_s),end_s=item['last_hit_s']+padding_s)
        if duration is not None:item['end_s']=min(duration,item['end_s'])
    return sorted(segments,key=lambda r:(r['start_s'],r['query_id']))

def export_segments(source,segments,destination,on_progress=None,cancel=None):
    import imageio_ffmpeg
    destination=Path(destination);destination.mkdir(parents=True,exist_ok=True);outputs=[]
    for i,item in enumerate(segments):
        if cancel and cancel.is_set():raise InterruptedError('片段导出已取消')
        target=destination/('clip-%04d.mp4'%i)
        args=[imageio_ffmpeg.get_ffmpeg_exe(),'-hide_banner','-loglevel','error','-y','-ss',str(item['start_s']),'-i',str(source),'-t',str(max(.04,item['end_s']-item['start_s'])),'-map','0:v:0','-map','0:a?','-c:v','libx264','-preset','veryfast','-crf','20','-fps_mode','vfr','-c:a','aac','-movflags','+faststart',str(target)]
        proc=subprocess.Popen(args,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        while proc.poll() is None:
            if cancel and cancel.wait(.1):proc.terminate();proc.wait();raise InterruptedError('片段导出已取消')
            if not cancel:time.sleep(.1)
        error=proc.stderr.read().decode('utf-8','replace');proc.stderr.close()
        if proc.returncode:raise RuntimeError('视频片段导出失败：'+error[-1000:])
        outputs.append(dict(item,path=str(target)))
        if on_progress:on_progress(i+1,len(segments))
    (destination/'clips.json').write_text(json.dumps(outputs,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return outputs

class SemanticArchive:
    """Mux received camera JPEG once; retain only a bounded look-back cache."""
    def __init__(self,directory,items,revision,threshold=.25,on_update=None,on_missing=None):
        self.path=Path(directory);self.path.mkdir(parents=True,exist_ok=False)
        (self.path/'matches').mkdir()
        self.items=items;self.revision=revision;self.threshold=threshold
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
                        self.segments=build_segments(self.rows,self.threshold,duration=self.last_time+.04)
                        self.on_update(dict(path=str(self.path),frames=self.frames,hits=len(self.saved),segments=self.segments))
        except BaseException as exc:self.error=type(exc).__name__+': '+str(exc)
        finally:
            if container:
                try:container.close()
                except Exception as exc:self.error=str(exc)
            if self.pending and not self.error:self.error='有%d个命中帧未收到，索引保留但截图不完整'%len(self.pending)
            if self.gaps and not self.error:self.error='摄像头流缺少%d帧，录像已标记不完整'%self.gaps
            report=dict(ok=self.error is None and self.frames>0,error=self.error,frames=self.frames,received_frame_gaps=self.gaps,missing_hit_frames=sorted(self.pending),expected_end_frame_id=self.end_frame_id,last_saved_frame_id=self.last_saved_id,duration_s=self.last_time+.04 if self.frames else 0,items=self.items,threshold=self.threshold,source='camera',video='video.mkv',segments=self.segments)
            try:
                (self.path/'session.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
                (self.path/'segments.json').write_text(json.dumps(self.segments,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            except BaseException as exc:
                self.error='录像收尾写入失败：'+str(exc);report.update(ok=False,error=self.error)
            finally:
                self.closed.set();self.on_update(dict(report,path=str(self.path),done=True,hits=len(self.saved)))
