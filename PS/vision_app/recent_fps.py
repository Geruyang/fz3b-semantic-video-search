"""Throughput over the latest ten completed images, excluding startup time."""
from collections import deque


class RecentFps:
    def __init__(self):
        self.times=deque(maxlen=11)

    @property
    def samples(self):return max(0,len(self.times)-1)

    def clear(self):self.times.clear()

    def add(self,completed_at):self.times.append(completed_at)

    def value(self):
        if len(self.times)<11:return 0.
        elapsed=self.times[-1]-self.times[0]
        return (len(self.times)-1)/elapsed if elapsed>0 else 0.
