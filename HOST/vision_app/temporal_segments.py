"""Incremental, source-time semantic intervals; raw scores remain untouched."""
import collections
import copy
import math


class SegmentTracker:
    def __init__(self, threshold, enabled=True, gap_s=1., padding_s=.5):
        if not math.isfinite(threshold) or not -1 <= threshold <= 1:
            raise ValueError('threshold must be finite in [-1,1]')
        self.threshold=threshold;self.enabled=enabled;self.gap_s=gap_s;self.padding_s=padding_s
        self.lower=max(-1.,threshold-.02)
        self.active={};self.finished=[];self.last_time=None;self.revision=None

    @property
    def settings(self):
        return dict(version=1,enabled=self.enabled,threshold=self.threshold,
                    continuation_offset=.02,entry_s=.4,entry_fraction=.7,
                    interruption_s=.75,weak_limit_s=2.,observation_gap_s=self.gap_s)

    def _close(self,key,cut=None):
        state=self.active.pop(key)
        item=state['item']
        item['last_support_s']=min(item['last_support_s'],cut) if cut is not None else item['last_support_s']
        item['confirmed']=state['confirmed']
        self.finished.append(item)

    def add(self,row):
        stamp=float(row['time_s'])
        if not math.isfinite(stamp) or stamp<0 or (self.last_time is not None and stamp<self.last_time):
            raise ValueError('semantic source time is invalid or decreasing')
        revision=row.get('query_revision')
        if self.last_time is not None and (stamp-self.last_time>self.gap_s or
                (revision is not None and self.revision is not None and revision!=self.revision)):
            for key in list(self.active):self._close(key)
        self.last_time=stamp;self.revision=revision
        present=set()
        for hit in row.get('ranking',[]):
            key=(hit['id'],hit['label']);score=float(hit['score'])
            if not math.isfinite(score):continue
            present.add(key)
            state=self.active.get(key)
            if state is not None:
                if not self.enabled and score<self.threshold:
                    self._close(key);state=None
                elif self.enabled:
                    low_since=state['low_since']
                    if (low_since is not None and stamp-low_since>.75+1e-9):
                        self._close(key);state=None
                    elif stamp-state['item']['last_hit_s']>=2.-1e-9:
                        self._close(key,cut=state['item']['last_hit_s']);state=None
            if state is None:
                if score<self.threshold:continue
                item=dict(query_id=key[0],label=key[1],first_hit_s=stamp,last_hit_s=stamp,
                          last_support_s=stamp,frame_ids=[],best_score=score)
                state=dict(item=item,confirmed=not self.enabled,history=collections.deque(),low_since=None)
                self.active[key]=state
            item=state['item'];high=score>=self.threshold
            if high:
                item['frame_ids'].append(row['frame_id']);item['last_hit_s']=stamp
                item['best_score']=max(item['best_score'],score)
            if score>=self.lower if self.enabled else high:
                item['last_support_s']=stamp;state['low_since']=None
            elif state['low_since'] is None:state['low_since']=stamp
            history=state['history'];history.append((stamp,high))
            left=stamp-.4
            while len(history)>1 and history[1][0]<=left:history.popleft()
            if not state['confirmed'] and stamp-item['first_hit_s']>=.4-1e-9:
                # Each result describes [its source PTS, the next result PTS).
                # Integrate time, not sample count: VFR and 4-FPS camera agree.
                support=sum(max(0.,b[0]-max(a[0],left)) for a,b in zip(history,list(history)[1:]) if a[1])
                observations=sum(high for at,high in history if at>=left-1e-9)
                if support/.4>=.7-1e-9 and observations>=2:state['confirmed']=True
        # Missing descriptions are unknown observations, never evidence to bridge.
        for key in list(self.active):
            if key not in present:self._close(key)

    def report(self,duration=None):
        items=self.finished+[dict(s['item'],confirmed=s['confirmed']) for s in self.active.values()]
        segments=[];candidates=[]
        for item in sorted(items,key=lambda x:(x['first_hit_s'],str(x['query_id']))):
            entry=copy.deepcopy(item)
            entry['start_s']=max(0.,entry['first_hit_s']-self.padding_s)
            entry['end_s']=entry['last_support_s']+self.padding_s
            if duration is not None:entry['end_s']=min(duration,entry['end_s'])
            entry['segment_id']=len(segments) if entry['confirmed'] else 'candidate-%d'%len(candidates)
            (segments if entry['confirmed'] else candidates).append(entry)
        return dict(segments=segments,candidates=candidates,continuity=self.settings)


def segment_report(rows,threshold=.25,gap_s=1.,padding_s=.5,duration=None,continuity=True):
    tracker=SegmentTracker(threshold,continuity,gap_s,padding_s)
    for row in sorted(rows,key=lambda x:(x['time_s'],x['frame_id'])):tracker.add(row)
    return tracker.report(duration)
