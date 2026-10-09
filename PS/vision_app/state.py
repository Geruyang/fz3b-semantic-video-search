"""Bounded live state and atomic semantic query snapshots (Python 3.6)."""
import threading
import queue
import time
import numpy as np


class LatestSlot:
    def __init__(self):
        self.condition = threading.Condition()
        self.version = 0
        self.value = None
        self.subscribers={}
    def subscribe(self,capacity=128):
        delivery=queue.Queue(capacity);overflow=threading.Event()
        with self.condition:self.subscribers[delivery]=overflow
        return delivery,overflow
    def unsubscribe(self,delivery):
        with self.condition:self.subscribers.pop(delivery,None)

    def publish(self, value):
        with self.condition:
            self.version += 1
            self.value = value
            for delivery,overflow in self.subscribers.items():
                try:delivery.put_nowait(value)
                except queue.Full:overflow.set()
            self.condition.notify_all()

    def get_after(self, version, timeout=1):
        with self.condition:
            if self.version <= version:
                self.condition.wait_for(lambda: self.version > version, timeout)
            return (self.version, self.value) if self.version > version else None


def normalized(features):
    data = np.asarray(features, dtype=np.float64)
    if data.ndim != 2 or data.shape[1] != 512 or not 0 < len(data) <= 256 or not np.isfinite(data).all():
        raise ValueError('expected finite features [1..256,512]')
    scale = np.max(np.abs(data), axis=1, keepdims=True)
    if np.any(scale == 0):
        raise ValueError('zero feature vector')
    data = data / scale
    return np.asarray(data / np.sqrt(np.sum(data * data, axis=1, keepdims=True)), dtype=np.float32)


class Candidates:
    def __init__(self):
        self.lock = threading.Lock()
        self.snapshot = None

    def replace(self, items, features, revision, identity):
        if type(revision) is not int or revision < 1 or not isinstance(identity, dict) or not identity.get('contract_id'):
            raise ValueError('query revision/identity missing')
        if not isinstance(items, list) or not 0 < len(items) <= 256:
            raise ValueError('expected 1..256 query items')
        ids = set()
        for item in items:
            if not isinstance(item, dict) or any(not isinstance(item.get(k), str) or not item[k].strip() or len(item[k]) > 1000 for k in ('id', 'label', 'text')) or item['id'] in ids:
                raise ValueError('invalid/duplicate query item')
            ids.add(item['id'])
        values = normalized(features)
        if len(values) != len(items):
            raise ValueError('item/feature count differs')
        with self.lock:
            if self.snapshot and revision <= self.snapshot[2]:
                raise ValueError('query revision must increase')
            self.snapshot = ([dict(i) for i in items], values.copy(), revision, dict(identity))

    def get(self):
        with self.lock:
            return self.snapshot

    def match(self, feature, threshold=.2, snapshot=None):
        snapshot = self.get() if snapshot is None else snapshot
        if snapshot is None:
            return {'query_revision': 0, 'ranking': [], 'best': None, 'unknown': True}
        if not isinstance(threshold, (int, float)) or not np.isfinite(threshold) or not -1 <= threshold <= 1:
            raise ValueError('threshold must be finite in [-1,1]')
        query = normalized(np.asarray(feature).reshape(1, -1))[0]
        items, values, revision, identity = snapshot
        scores = np.clip(values.dot(query), -1, 1)
        order = np.argsort(-scores, kind='mergesort')
        ranking = [dict(items[int(i)], score=float(scores[i])) for i in order[:8]]
        return {'query_revision': revision, 'ranking': ranking, 'best': ranking[0], 'unknown': ranking[0]['score'] < threshold, 'threshold': threshold, 'identity': identity}
