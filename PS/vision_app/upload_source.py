"""Bounded lossless uploaded-frame source, compatible with board Python 3.6."""
import collections
import math
import threading
import time

class UploadSource:
    def __init__(self,job_id,capacity=16):
        self.job_id=job_id;self.capacity=capacity
        self.frames=collections.deque();self.condition=threading.Condition()
        self.received=0;self.completed=0;self.last_time=-1.0
        self.finished=False;self.cancelled=False;self.error=None
    def put(self,meta,jpeg):
        fid=meta.get('frame_id');stamp=meta.get('video_time_s')
        with self.condition:
            if self.cancelled or self.finished:raise ValueError('upload job is closed')
            if type(fid) is not int or fid!=self.received:raise ValueError('uploaded frames must be consecutive from zero')
            if not isinstance(stamp,(int,float)) or not math.isfinite(stamp) or stamp<0 or stamp<self.last_time:raise ValueError('invalid source video timestamp')
            if not jpeg or len(jpeg)>4*1024*1024:raise ValueError('invalid uploaded JPEG extent')
            if len(self.frames)>=self.capacity:raise ValueError('upload queue full; wait for result credits')
            frame=dict(meta,jpeg=jpeg,capture_monotonic=time.monotonic(),source='upload',job_id=self.job_id)
            self.frames.append(frame);self.received+=1;self.last_time=stamp;self.condition.notify_all()
    def take(self,timeout=.2):
        with self.condition:
            if not self.frames and not self.finished and not self.cancelled:self.condition.wait(timeout)
            return self.frames.popleft() if self.frames and not self.cancelled else None
    def push_back(self,frame):
        with self.condition:
            if not self.cancelled:self.frames.appendleft(frame);self.condition.notify_all()
    def finish(self,count):
        with self.condition:
            if type(count) is not int or count!=self.received:raise ValueError('upload final frame count mismatch')
            self.finished=True;self.condition.notify_all()
    def cancel(self):
        with self.condition:self.cancelled=True;self.frames.clear();self.condition.notify_all()
    @property
    def exhausted(self):
        with self.condition:return self.finished and not self.frames
    def status(self):
        with self.condition:return dict(job_id=self.job_id,received=self.received,completed=self.completed,queued=len(self.frames),finished=self.finished,cancelled=self.cancelled,error=self.error)
