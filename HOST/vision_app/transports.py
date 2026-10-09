"""Host network/serial readers. Preview storage is a single replaceable slot."""
import json
import base64
import numpy as np
import queue
import socket
import threading
import time
from .protocol import Decoder, ImageAssembler, JSON, PREVIEW, RESULT_IMAGE, IMAGE_CHUNK, encode_message, unpack_image


class ReceiverState:
    def __init__(self):
        self.preview = None
        self.preview_count = 0
        self.last_result = None
        self.result_image = None
        self.assembler = ImageAssembler()

    def accept(self, kind, payload):
        if kind == JSON:
            value = json.loads(payload.decode('utf-8'), parse_constant=lambda x: (_ for _ in ()).throw(ValueError('nonfinite JSON')))
            if not isinstance(value, dict):
                raise ValueError('JSON object required')
            if value.get('type') == 'result':
                self.last_result = value
            return value
        if kind == IMAGE_CHUNK:
            data = self.assembler.feed(payload)
            if data is None:
                return None
            kind, payload = PREVIEW, data
        if kind in (PREVIEW, RESULT_IMAGE):
            meta, jpeg = unpack_image(payload)
            if kind == PREVIEW:
                self.preview = (meta, jpeg, time.monotonic())
                self.preview_count += 1
            else:
                self.result_image = (meta, jpeg, time.monotonic())
            return None
        raise ValueError('unexpected message kind')


class Link:
    def __init__(self, on_message, on_error, on_frame=None, on_result_image=None):
        self.state = ReceiverState()
        self.on_message, self.on_error = on_message, on_error
        self.on_frame,self.on_result_image=on_frame,on_result_image
        self.stop = threading.Event()
        self.outgoing = queue.Queue(32)
        self.endpoints, self.threads = [], []
        self.token = None
        self.preview_enabled=threading.Event();self.preview_enabled.set()
    def set_preview_enabled(self,enabled):
        if enabled:self.preview_enabled.set()
        else:self.preview_enabled.clear()

    def send(self, value):
        if value.get('op') == 'queries' and 'features' in value:
            value = dict(value)
            data = np.asarray(value.pop('features'), dtype='<f4')
            value['features_f32_b64'] = base64.b64encode(data.tobytes()).decode('ascii')
        self.outgoing.put_nowait(encode_message(JSON, value))

    def _thread(self, fn, args):
        t = threading.Thread(target=fn, args=args, daemon=True)
        self.threads.append(t)
        t.start()

    def connect_tcp(self, host, token, control_port=8765, video_port=8766):
        self.token = token
        self._thread(self._tcp, (host, control_port, False))
        self._thread(self._tcp, (host, video_port, True))

    def _tcp(self, host, port, video):
        sock = None
        try:
            sock = socket.create_connection((host, port), timeout=5)
            sock.settimeout(.03)
            self.endpoints.append(sock)
            sock.sendall(encode_message(JSON, {'op': 'hello', 'token': self.token}))
            decoder, deadline, authenticated = Decoder(), time.monotonic() + 5, False
            preview_mode=None
            while not self.stop.is_set():
                if video and authenticated and preview_mode!=self.preview_enabled.is_set():
                    preview_mode=self.preview_enabled.is_set();sock.sendall(encode_message(JSON,dict(op='preview',enabled=preview_mode)))
                if not video:
                    try:
                        sock.sendall(self.outgoing.get_nowait())
                    except queue.Empty:
                        pass
                try:
                    data = sock.recv(131072)
                    if not data:
                        raise ConnectionError('板端关闭连接')
                    for kind, payload in decoder.feed(data):
                        message = self.state.accept(kind, payload)
                        if kind==PREVIEW and self.on_frame:self.on_frame(*self.state.preview[:2])
                        if kind==RESULT_IMAGE and self.on_result_image:self.on_result_image(*self.state.result_image[:2])
                        if message:
                            if message.get('type') == 'hello':
                                authenticated = True
                            if not video:
                                self.on_message(message)
                except socket.timeout:
                    pass
                if not authenticated and time.monotonic() > deadline:
                    raise TimeoutError('应用握手超时，请核对连接令牌')
        except Exception as exc:
            if not self.stop.is_set():
                self.on_error(('视频：' if video else '控制：') + str(exc))
        finally:
            if sock:
                sock.close()

    def connect_serial(self, port, token, baudrate=115200):
        self.token = token
        self._thread(self._serial, (port, baudrate))

    def _serial(self, port, baudrate):
        endpoint = None
        try:
            import serial
            endpoint = serial.Serial(port=None, baudrate=baudrate, timeout=.02, write_timeout=1)
            endpoint.dtr = endpoint.rts = False
            endpoint.port = port
            endpoint.open()
            self.endpoints.append(endpoint)
            endpoint.write(encode_message(JSON, {'op': 'hello', 'token': self.token}))
            decoder, deadline, authenticated = Decoder(), time.monotonic() + 12, False
            pending, last_hello, last_ping = bytearray(), time.monotonic(), 0
            while not self.stop.is_set():
                now = time.monotonic()
                if not authenticated and now - last_hello > 1:
                    endpoint.write(encode_message(JSON, {'op': 'hello', 'token': self.token}))
                    last_hello = now
                if not pending:
                    try:
                        pending.extend(self.outgoing.get_nowait())
                    except queue.Empty:
                        if authenticated and now - last_ping > 2:
                            pending.extend(encode_message(JSON, {'op': 'status', 'request_id': 'serial-ping'}))
                            last_ping = now
                if pending:
                    sent = endpoint.write(pending[:512])
                    del pending[:sent]
                for kind, payload in decoder.feed(endpoint.read(max(1, min(endpoint.in_waiting, 65536)))):
                    message = self.state.accept(kind, payload)
                    if message:
                        authenticated |= message.get('type') == 'hello'
                        if message.get('request_id') != 'serial-ping':
                            self.on_message(message)
                if not authenticated and time.monotonic() > deadline:
                    raise TimeoutError('串口未收到应用握手；请确认板端应用已接管 UART')
        except Exception as exc:
            if not self.stop.is_set():
                self.on_error('串口：' + str(exc))
        finally:
            if endpoint:
                endpoint.close()

    def close(self):
        self.stop.set()
        for endpoint in self.endpoints:
            try:
                endpoint.close()
            except OSError:
                pass
        for thread in self.threads:
            thread.join(.5)
