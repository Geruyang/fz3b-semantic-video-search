"""At most two prepared frames; decode only on demand, not at camera FPS."""
import queue
import threading


class BoundedPrefetch:
    def __init__(self, source, capacity=2):
        self.source = iter(source)
        self.queue = queue.Queue(capacity)
        self.slots = threading.BoundedSemaphore(capacity)
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self.produce, daemon=True)

    def produce(self):
        try:
            while not self.stop.is_set():
                if not self.slots.acquire(timeout=.1):
                    continue
                try:
                    value = next(self.source)
                except StopIteration:
                    self.queue.put_nowait(('end', None))
                    return
                except BaseException as exc:
                    self.queue.put_nowait(('error', exc))
                    return
                self.queue.put_nowait(('item', value))
        finally:
            close = getattr(self.source, 'close', None)
            if close:
                close()

    def __enter__(self):
        self.thread.start()
        return self

    def __iter__(self):
        return self

    def __next__(self):
        while not self.stop.is_set():
            try:
                kind, value = self.queue.get(timeout=.1)
            except queue.Empty:
                if not self.thread.is_alive():
                    raise StopIteration
                continue
            self.slots.release()
            if kind == 'end':
                raise StopIteration
            if kind == 'error':
                raise value
            return value
        raise StopIteration

    def __exit__(self, *unused):
        self.stop.set()
        self.thread.join(10)
        if self.thread.is_alive():
            raise RuntimeError('preprocessing worker did not stop')
