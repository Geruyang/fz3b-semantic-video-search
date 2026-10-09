"""Forward compressed MJPEG; decode only inference-selected frames."""
import io
import os
import select
import struct
import subprocess
import time
import numpy as np
from PIL import Image

CAM_HEADER = struct.Struct('<IIIIQ')


def preprocess_jpeg(jpeg, timings=None):
    started = time.perf_counter()
    with Image.open(io.BytesIO(jpeg)) as opened:
        opened.load()
        image = opened if opened.mode=='RGB' else opened.convert('RGB')
        decoded = time.perf_counter()
        w, h = image.size
        long = int(256 * max(w, h) / min(w, h))
        resized = image.resize((256, long) if w <= h else (long, 256), Image.BILINEAR)
        scaled = time.perf_counter()
        left, top = int(round((resized.size[0] - 256) / 2.0)), int(round((resized.size[1] - 256) / 2.0))
        array = np.asarray(resized.crop((left, top, left + 256, top + 256)), dtype=np.uint8).astype(np.float32)
        array /= np.float32(255)
        tensor = np.ascontiguousarray(array.transpose(2, 0, 1)[None])
        ended = time.perf_counter()
        if timings is not None:
            timings.update(jpeg_decode_ms=(decoded-started)*1000,
                           resize_ms=(scaled-decoded)*1000,
                           tensor_ms=(ended-scaled)*1000,
                           preprocess_ms=(ended-started)*1000)
        return tensor


class Camera:
    def __init__(self, slot, stop, helper, device, width=1280, height=720, fps=30):
        self.slot, self.stop, self.helper, self.device = slot, stop, helper, device
        self.width, self.height, self.fps = width, height, fps
        self.frames, self.gaps, self.started, self.error = 0, 0, time.monotonic(), None
        self.proc = None

    def _exact(self, size):
        buf = bytearray()
        end = time.monotonic() + 8
        while len(buf) < size:
            if self.stop.is_set():
                raise InterruptedError('camera stopped')
            if time.monotonic() > end:
                raise TimeoutError('camera read timed out')
            ready, _, _ = select.select([self.proc.stdout], [], [], .2)
            if ready:
                data = os.read(self.proc.stdout.fileno(), size - len(buf))
                if not data:
                    raise EOFError('camera helper exited')
                buf.extend(data)
        return bytes(buf)

    def run(self):
        previous = None
        try:
            while not self.stop.is_set():
                self.proc = subprocess.Popen([self.helper, self.device, str(self.width), str(self.height), str(self.fps), '100000'], stdout=subprocess.PIPE, bufsize=0)
                try:
                    for unused in range(100000):
                        magic, size, sequence, flags, timestamp_us = CAM_HEADER.unpack(self._exact(CAM_HEADER.size))
                        if magic != 0x43414d31 or not 0 < size <= 4 * 1024 * 1024:
                            raise ValueError('invalid camera frame header')
                        jpeg = self._exact(size)
                        if previous is not None and sequence > previous:
                            self.gaps += max(0, sequence - previous - 1)
                        previous = sequence
                        frame = {'frame_id': self.frames, 'sequence': sequence, 'capture_monotonic': time.monotonic(), 'v4l2_timestamp_us': timestamp_us, 'width': self.width, 'height': self.height, 'jpeg': jpeg}
                        self.frames += 1
                        self.slot.publish(frame)
                finally:
                    if self.proc.poll() is None:
                        self.proc.terminate()
                    try:
                        self.proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        self.proc.kill()
                        self.proc.wait()
                    self.proc.stdout.close()
        except InterruptedError:
            pass
        except Exception as exc:
            self.error = str(exc)
