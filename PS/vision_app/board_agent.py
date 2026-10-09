"""FZ3B application service. Linux retains physical GEM/UVC/UART ownership."""
import argparse
import base64
import collections
import hmac
import io
import json
import math
import os
import queue
import select
import signal
import socket
import subprocess
import threading
import time
import traceback
import zlib
import numpy as np
from PIL import Image

from .camera import Camera, preprocess_jpeg
from .contract import load_contract
from .protocol import Decoder, JSON, PREVIEW, RESULT_IMAGE, IMAGE_CHUNK, INPUT_FRAME, encode_message, fragment_image, pack_image,unpack_image
from .state import Candidates, LatestSlot

DEFAULT_CPU_KHZ = 1199999


def read(path, default=None):
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return default


class CpuPolicy:
    def __init__(self, root='/sys/devices/system/cpu/cpufreq/policy0', control_socket=None):
        self.root = root
        self.control_socket = control_socket

    def status(self):
        value = lambda n: read(self.root + '/' + n, '')
        state = {'current_khz': int(value('scaling_cur_freq') or 0),
                'available_khz': [int(i) for i in value('scaling_available_frequencies').split()],
                'governor': value('scaling_governor'), 'affected_cpus': value('affected_cpus'),
                'min_khz': int(value('scaling_min_freq') or 0), 'max_khz': int(value('scaling_max_freq') or 0), 'verified': False}
        state['cached_sysfs_khz'] = state['current_khz']
        if self.control_socket:
            from .cpu_clock_service import request, TARGETS
            actual = request(path=self.control_socket)
            state.update(actual, current_khz=actual['actual_hz']//1000,
                         available_khz=list(TARGETS), governor='verified_cpu_clock',
                         min_khz=min(TARGETS), max_khz=max(TARGETS))
        return state

    def set_frequency(self, khz):
        if self.control_socket:
            from .cpu_clock_service import request, validate_target
            actual = request('set', validate_target(khz), path=self.control_socket)
            if not actual.get('verified') or abs(actual['actual_hz']//1000 - khz) > 1:
                raise RuntimeError('CPU hardware frequency not verified')
            return self.status()
        state = self.status()
        if type(khz) is not int or khz not in state['available_khz']:
            raise ValueError('frequency must be an enumerated policy value')
        if state['governor'] != 'userspace' or not state['min_khz'] <= khz <= state['max_khz']:
            raise ValueError('current governor/policy limits do not permit this frequency')
        raise RuntimeError('verified CPU clock service required; sysfs cache cannot prove frequency')


class Agent:
    def __init__(self, config):
        self.config = config
        self.contract = load_contract(config['contract'])
        self.token = read(config['token_file'])
        if not self.token or len(self.token) < 24:
            raise ValueError('application token missing')
        self.stop = threading.Event()
        self.frames, self.results = LatestSlot(), LatestSlot()
        self.input_source='camera';self.upload_job=None;self.result_frames=collections.OrderedDict()
        self.queries, self.cpu = Candidates(), CpuPolicy(control_socket=config.get('cpu_control_socket'))
        self.camera = Camera(self.frames, self.stop, config['camera_helper'], config['camera_device'], config.get('width', 1280), config.get('height', 720), config.get('fps', 30))
        self.inference_enabled = False
        self.inference_thread = None
        self.frequency_changing,self.resume_after_frequency = False,False
        self.last_cpu_state=None
        self.inference_state, self.inference_error = 'STOPPED', None
        self.inference_count, self.inference_started = 0, None
        self.threshold = .2
        self.max_in_flight = 4
        self.threads, self.listeners = set(), []
        self.lock = threading.RLock()
        self.result_queues = []
        self.result_queue_owners={}
        self.delivery_drops = 0
        self.performance = {}
        self.first_result_at = self.last_result_at = None
        self.client_limit = threading.BoundedSemaphore(8)
        self.serial_metrics = {'rx_bytes': 0, 'tx_bytes': 0, 'authenticated': False, 'decoder_errors': 0}
        self.r5, self.r5_error, self.telemetry_at = None, None, 0
        if config.get('r5_enabled'):
            try:
                if config.get('r5_require_ready'):
                    from .r5_start import qualified_boot
                    if not qualified_boot():
                        raise RuntimeError('R5 startup qualification absent in this boot')
                from .r5_bridge import R5Bridge
                self.r5 = R5Bridge()
            except Exception as exc:
                self.r5_error = str(exc)

    def wire(self, kind, payload):
        def crc(data):
            # Keep full-frame video in efficient Linux networking; small control
            # messages and serial fragments are actually computed on R5-1.
            return self.r5.crc(data) if self.r5 is not None and len(data) <= 8192 else zlib.crc32(data)
        return encode_message(kind, payload, crc=crc)

    def spawn(self, target, args=()):
        def invoke():
            try:
                target(*args)
            finally:
                with self.lock:
                    self.threads.discard(thread)
        thread = threading.Thread(target=invoke, daemon=True)
        with self.lock:
            self.threads.add(thread)
        thread.start()
        return thread

    def status(self):
        remote = '/sys/class/remoteproc'
        r5 = []
        for name in os.listdir(remote) if os.path.isdir(remote) else []:
            r5.append({'name': read(remote + '/' + name + '/name'), 'state': read(remote + '/' + name + '/state')})
        mem = {}
        for line in (read('/proc/meminfo', '') or '').splitlines():
            key, value = line.split(':', 1)
            if key in ('MemTotal', 'MemAvailable'):
                mem[key] = int(value.strip().split()[0])
        elapsed = time.monotonic() - self.camera.started
        snapshot = self.queries.get()
        with self.lock:
            changing=getattr(self,'frequency_changing',False)
            if changing:
                cpu=dict(getattr(self,'last_cpu_state',None) or
                         {'current_khz':0,'actual_hz':0,'verified':False})
                cpu.update(verified=False,transition=True)
            else:
                # Serialize this short read with the change flag. Once set,
                # receiver status must never wait behind a clock SET RPC.
                cpu=self.cpu.status()
                self.last_cpu_state=dict(cpu)
        if self.r5 and not changing and time.monotonic() - self.telemetry_at > 1:
            with self.lock:
                self.r5.telemetry(cpu['current_khz'], mem.get('MemAvailable', 0), self.camera.frames / max(elapsed, .001), self.camera.frames)
                self.telemetry_at = time.monotonic()
        r5_state = self.r5.status() if self.r5 else {'mode': 'Linux compatibility', 'cores': r5, 'offload_verified': False, 'error': self.r5_error}
        with self.lock:
            performance = {key: dict(value, mean_ms=value['sum_ms']/max(value['count'],1)) for key,value in self.performance.items()}
            first_result_at, last_result_at = self.first_result_at, self.last_result_at
            inference_count, inference_started = self.inference_count, self.inference_started
        interval_fps = ((inference_count-1)/(last_result_at-first_result_at)
                        if first_result_at is not None and last_result_at is not None
                        and last_result_at > first_result_at else 0)
        return {'type': 'status', 'protocol': 1, 'platform': 'A0005', 'boot_id': read('/proc/sys/kernel/random/boot_id'),
                'contract_id': self.contract['contract_id'], 'cpu': cpu, 'cpu_frequency_changing':changing,'memory_kb': mem,
                'loadavg': (read('/proc/loadavg', '') or '').split()[:3], 'camera': {'frames': self.camera.frames, 'fps': self.camera.frames / max(elapsed, .001), 'sequence_gaps': self.camera.gaps, 'error': self.camera.error, 'width': self.camera.width, 'height': self.camera.height, 'requested_fps': self.camera.fps},
                'inference': {'state': self.inference_state, 'error': self.inference_error, 'frames': inference_count, 'fps': inference_count / max(time.monotonic() - inference_started, .001) if inference_started else 0, 'max_in_flight': self.max_in_flight,
                              'result_interval_fps': interval_fps,
                              'preprocess_async': self.config.get('preprocess_async', False), 'performance': performance},
                'query_revision': snapshot[2] if snapshot else 0, 'threshold': self.threshold, 'result_delivery_drops': self.delivery_drops,
                'input_source':getattr(self,'input_source','camera'),'upload':self.upload_job.status() if getattr(self,'upload_job',None) else None,
                'r5': r5_state, 'serial': dict(self.serial_metrics)}

    def handle(self, request):
        if not isinstance(request, dict):
            raise ValueError('object request required')
        op = request.get('op')
        if op == 'status':
            return self.status()
        if op=='upload_begin':
            from .upload_source import UploadSource
            job_id=request.get('job_id')
            if not isinstance(job_id,str) or not 1<=len(job_id)<=64 or not all(c.isalnum() or c in '-_' for c in job_id):raise ValueError('invalid upload job ID')
            with self.lock:
                if self.inference_thread and self.inference_thread.is_alive():raise ValueError('stop and drain current inference before video upload')
                if self.inference_error or getattr(self,'frequency_changing',False):raise ValueError('inference cleanup/frequency state is not ready')
                if self.queries.get() is None:raise ValueError('upload descriptions first')
                job=UploadSource(job_id);job.owner=request.get('_owner');job.snapshot=self.queries.get();job.threshold=self.threshold
                if self.r5:self.r5.request(0,12,0)
                self.upload_job=job;self.input_source='upload';self.inference_enabled=True
                self.inference_thread=self.spawn(self.infer)
            return dict(job_id=job_id,credits=16,state='STARTING')
        if op=='upload_finish':
            job=self.upload_job
            if not job or job.job_id!=request.get('job_id') or job.owner is not request.get('_owner'):raise ValueError('upload owner/job mismatch')
            job.finish(request.get('frame_count'))
            if self.r5:self.r5.request(0,14,job.received)
            return job.status()
        if op=='upload_cancel':
            job=self.upload_job
            if not job or job.job_id!=request.get('job_id') or job.owner is not request.get('_owner'):raise ValueError('upload owner/job mismatch')
            job.cancel();self.inference_enabled=False;self.resume_after_frequency=False
            return job.status()
        if op == 'queries':
            identity = request.get('identity', {})
            if identity.get('contract_id') != self.contract['contract_id'] or identity.get('weight_sha256') != self.contract['weight_sha256'] or identity.get('normalization') != self.contract['normalization'] or identity.get('bpe_sha256') != self.contract['bpe_sha256']:
                raise ValueError('text/image semantic identity mismatch')
            if 'features_f32_b64' in request:
                count = len(request['items'])
                encoded = request['features_f32_b64']
                if not isinstance(encoded, str) or len(encoded) > 700000 or not 1 <= count <= 256:
                    raise ValueError('encoded feature extent invalid')
                data = base64.b64decode(encoded, validate=True)
                if len(data) != count * 512 * 4:
                    raise ValueError('encoded feature size mismatch')
                features = np.frombuffer(data, dtype='<f4').reshape(count, 512).copy()
            else:
                features = request['features']
            self.queries.replace(request['items'], features, request['revision'], identity)
            return {'query_revision': request['revision'], 'count': len(request['items'])}
        if op == 'start':
            with self.lock:
                if getattr(self,'frequency_changing',False):
                    raise ValueError('CPU frequency change in progress; wait for completion')
                if self.inference_thread and self.inference_thread.is_alive():
                    if not self.inference_enabled:
                        raise ValueError('inference is draining; wait for STOPPED before starting again')
                    return {'state': self.inference_state}
                if self.queries.get() is None:
                    raise ValueError('upload descriptions before starting inference')
                self.input_source='camera'
                self.inference_enabled, self.inference_error = True, None
                self.inference_thread = self.spawn(self.infer)
            return {'state': 'STARTING'}
        if op == 'stop':
            with self.lock:
                self.inference_enabled = False
                self.resume_after_frequency = False
            return {'state': 'DRAINING' if self.inference_thread and self.inference_thread.is_alive() else self.inference_state}
        if op == 'settings':
            with self.lock:
                threshold = request.get('threshold', self.threshold)
                in_flight = request.get('max_in_flight', self.max_in_flight)
                if not isinstance(threshold, (float, int)) or not math.isfinite(threshold) or not -1 <= threshold <= 1:
                    raise ValueError('threshold must be finite in [-1,1]')
                if type(in_flight) is not int or not 1 <= in_flight <= 4:
                    raise ValueError('max_in_flight must be 1..4')
                if in_flight != self.max_in_flight and self.inference_thread and self.inference_thread.is_alive():
                    raise ValueError('stop and drain inference before changing in-flight count')
                self.threshold, self.max_in_flight = float(threshold), in_flight
            return {'threshold': self.threshold, 'max_in_flight': self.max_in_flight}
        if op == 'cpu_frequency':
            return self.change_frequency(request.get('khz'))
        raise ValueError('unsupported operation')

    def change_frequency(self,khz):
        from .frequency import validate_khz
        khz=validate_khz(khz)
        with self.lock:
            if getattr(self,'frequency_changing',False):
                raise ValueError('CPU frequency change already in progress')
            self.frequency_changing=True
            task=self.inference_thread
            self.resume_after_frequency=bool(self.inference_enabled and task and task.is_alive())
            self.inference_enabled=False
        try:
            # infer() needs self.lock to finish. Never hold it across join.
            if task and task.is_alive():
                task.join(timeout=310)
                if task.is_alive():
                    raise RuntimeError('inference drain timed out; CPU frequency unchanged')
            if task and (self.inference_state!='STOPPED' or self.inference_error):
                raise RuntimeError('inference cleanup failed; CPU frequency unchanged')
            if self.r5:
                self.r5.request(0,10,khz)
            state=self.cpu.set_frequency(khz)
            with self.lock:
                resume=self.resume_after_frequency and not self.stop.is_set()
                if resume:
                    self.inference_enabled,self.inference_error=True,None
                    self.inference_thread=self.spawn(self.infer)
                return dict(state,inference_resumed=bool(resume))
        finally:
            with self.lock:
                self.frequency_changing,self.resume_after_frequency=False,False

    def infer(self):
        runtime = prepared = None
        retained = {}
        job=self.upload_job if getattr(self,'input_source','camera')=='upload' else None
        self.inference_state, self.inference_error = 'STARTING', None
        try:
            from .board_runtime import create_runtime
            runtime = create_runtime(self.contract)
            with self.lock:
                self.inference_count, self.inference_started = 0, time.monotonic()
                self.performance = {}
                self.first_result_at = self.last_result_at = None
            self.inference_state = 'RUNNING'
            def raw_inputs():
                version = 0
                while self.inference_enabled and not self.stop.is_set():
                    wait_at = time.perf_counter()
                    frame=job.take(.2) if job else None
                    if job:
                        if frame is None:
                            if job.exhausted or job.cancelled:break
                            continue
                        got=(version+1,frame)
                    else:got = self.frames.get_after(version, .5)
                    if got is None:
                        if self.camera.error:
                            raise RuntimeError(self.camera.error)
                        continue
                    version, frame = got
                    snapshot = job.snapshot if job else self.queries.get()
                    timings = {'input_wait_ms': (time.perf_counter()-wait_at)*1000}
                    tensor = preprocess_jpeg(frame['jpeg'], timings)
                    for key, value in timings.items():
                        self.record_performance(key, value)
                    yield frame, snapshot, tensor
                self.inference_state = 'DRAINING'
            source = raw_inputs()
            if not job and self.config.get('preprocess_async', False):
                from .prefetch import BoundedPrefetch
                prepared = BoundedPrefetch(source, capacity=2)
                source = prepared.__enter__()
            def inputs():
                for frame, snapshot, tensor in source:
                    if not self.inference_enabled or self.stop.is_set():
                        if job:job.push_back(frame)
                        self.inference_state = 'DRAINING'
                        return
                    retained[frame['frame_id']] = (frame, snapshot)
                    if len(retained) > self.max_in_flight * 2 + 4:
                        raise RuntimeError('runtime admission exceeded bounded frame retention')
                    yield frame['frame_id'], tensor
            with runtime.iter_results(inputs(), max_in_flight=self.max_in_flight, record_history=False) as stream:
                for output in stream:
                    consumed = time.perf_counter()
                    frame, snapshot = retained.pop(output['frame_id'])
                    feature = np.asarray(output['features'], dtype=np.float32)
                    threshold=job.threshold if job else self.threshold
                    if self.r5 and hasattr(self.r5,'match'):
                        result=self.r5.match(feature,threshold,snapshot)
                    else:result = self.queries.match(feature, threshold, snapshot)
                    result.update(type='result', frame_id=frame['frame_id'], capture_monotonic=frame['capture_monotonic'], completed_monotonic=time.monotonic(), source_width=frame['width'], source_height=frame['height'],source='upload' if job else 'camera')
                    if job:
                        result.update(job_id=job.job_id,video_time_s=frame['video_time_s'])
                        with job.condition:job.completed+=1
                    else:
                        with self.lock:
                            self.result_frames[frame['frame_id']]=dict(frame,query_revision=result['query_revision'])
                            while len(self.result_frames)>64:self.result_frames.popitem(last=False)
                    now = time.monotonic()
                    with self.lock:
                        self.inference_count += 1
                        if self.first_result_at is None:
                            self.first_result_at = now
                        self.last_result_at = now
                    events = output['pair_timing']['ps_events'] if output['frame_id'] == output['pair_timing']['frame_ids'][0] else []
                    for event in events:
                        self.record_performance(event['partition']+'_call_ms', event['call_wall_ms'])
                        self.record_performance(event['partition']+'_ort_ms', event['ort_run_ms'])
                    self.results.publish((result, frame['jpeg']))
                    with self.lock:
                        for delivery in self.result_queues:
                            if job and self.result_queue_owners.get(delivery) is not job.owner:continue
                            try:
                                delivery.put_nowait((result, frame['jpeg']))
                            except queue.Full:
                                if job:raise RuntimeError('upload result queue full; incomplete job is not successful')
                                delivery.get_nowait()
                                delivery.put_nowait((result, frame['jpeg']))
                                self.delivery_drops += 1
                    self.record_performance('result_postprocess_ms', (time.perf_counter()-consumed)*1000)
        except BaseException as exc:
            self.inference_error = '%s: %s' % (type(exc).__name__, str(exc))
            traceback.print_exc()
        finally:
            self.inference_enabled = False
            if prepared is not None:
                try:
                    prepared.__exit__(None, None, None)
                except BaseException as exc:
                    self.inference_error = 'preprocessing cleanup: ' + str(exc)
            if runtime is not None:
                try:
                    runtime.close()
                except BaseException as exc:
                    self.inference_error = 'runtime cleanup: ' + str(exc)
            retained.clear()
            self.inference_state = 'FAILED' if self.inference_error else 'STOPPED'
            if job:job.error=self.inference_error

    def record_performance(self, key, value):
        with self.lock:
            entry = self.performance.setdefault(key, {'count': 0, 'sum_ms': 0., 'max_ms': 0.})
            entry['count'] += 1
            entry['sum_ms'] += value
            entry['max_ms'] = max(entry['max_ms'], value)

    def authenticate(self, request):
        return isinstance(request, dict) and request.get('op') == 'hello' and isinstance(request.get('token'), str) and hmac.compare_digest(request['token'], self.token)

    def reply(self, request):
        identity = {'type': 'ack', 'request_id': request.get('request_id'), 'op': request.get('op')}
        try:
            return dict(identity, ok=True, result=self.handle(request))
        except Exception as exc:
            return dict(identity, ok=False, error=str(exc))

    def queued_reply(self,request,replies,epoch=None):
        answer=self.reply(request)
        try:
            replies.put_nowait((epoch,answer))
        except queue.Full:
            pass

    def tcp_client(self, connection, video):
        connection.settimeout(.2)
        decoder, authenticated, deadline = Decoder(), False, time.monotonic() + 5
        version, last_status = 0, 0
        delivery = None
        replies=queue.Queue(8)
        owner=object();owned_job=None
        video_paused=False
        frame_delivery=None;frame_overflow=None
        try:
            while not self.stop.is_set():
                try:
                    data = connection.recv(65536)
                    if not data:
                        return
                    for kind, payload in decoder.feed(data):
                        if kind==INPUT_FRAME and authenticated and not video:
                            meta,jpeg=unpack_image(payload);job=self.upload_job
                            if job is None or job.owner is not owner or meta.get('job_id')!=job.job_id:raise ValueError('upload frame owner/job mismatch')
                            if self.r5:self.r5.request(0,13,meta['frame_id'])
                            job.put(meta,jpeg)
                            continue
                        if kind != JSON:
                            raise ValueError('JSON request required')
                        req = json.loads(payload.decode('utf-8'))
                        if not authenticated:
                            if not self.authenticate(req):
                                return
                            authenticated = True
                            if video:frame_delivery,frame_overflow=self.frames.subscribe()
                            if not video:
                                delivery = queue.Queue(16)
                                with self.lock:
                                    self.result_queues.append(delivery)
                                    self.result_queue_owners[delivery]=owner
                            connection.sendall(self.wire(JSON, dict(self.status(), type='hello', ok=True)))
                            continue
                        if video:
                            if req.get('op')=='preview':
                                paused=req.get('enabled') is False
                                if paused and frame_delivery is not None:self.frames.unsubscribe(frame_delivery);frame_delivery=None
                                elif not paused and frame_delivery is None:frame_delivery,frame_overflow=self.frames.subscribe()
                                video_paused=paused
                            continue
                        if req.get('op')=='frame_get':
                            with self.lock:frame=self.result_frames.get(req.get('frame_id'))
                            if frame:
                                meta={k:v for k,v in frame.items() if k!='jpeg'}
                                connection.sendall(self.wire(RESULT_IMAGE,pack_image(meta,frame['jpeg'])))
                            connection.sendall(self.wire(JSON,dict(type='ack',op='frame_get',request_id=req.get('request_id'),ok=bool(frame),result={'frame_id':req.get('frame_id')})))
                            continue
                        req['_owner']=owner
                        if req.get('op')=='cpu_frequency':
                            # Keep this receiver responsive to a stop command
                            # while the separate job drains inference and sets CPU.
                            self.spawn(self.queued_reply,(req,replies))
                        else:
                            connection.sendall(self.wire(JSON, self.reply(req)))
                            if req.get('op')=='upload_begin' and self.upload_job and self.upload_job.owner is owner:owned_job=self.upload_job
                except socket.timeout:
                    pass
                if not authenticated:
                    if time.monotonic() > deadline:
                        return
                    continue
                try:
                    unused,answer=replies.get_nowait()
                    connection.sendall(self.wire(JSON,answer))
                except queue.Empty:
                    pass
                if video:
                    got=None
                    if not video_paused and frame_delivery is not None:
                        if frame_overflow.is_set():raise ValueError('lossless camera delivery overflow; incomplete recording')
                        try:got=(version+1,frame_delivery.get_nowait())
                        except queue.Empty:pass
                else:
                    try:
                        got = (version + 1, delivery.get_nowait())
                    except queue.Empty:
                        got = None
                if got:
                    version, value = got
                    connection.settimeout(2)
                    if video:
                        meta = {k: v for k, v in value.items() if k != 'jpeg'}
                        connection.sendall(self.wire(PREVIEW, pack_image(meta, value['jpeg'])))
                    else:
                        result, jpeg = value
                        wire = dict(result, result_age_ms=(time.monotonic() - result['capture_monotonic']) * 1000)
                        connection.sendall(self.wire(JSON, wire))
                    connection.settimeout(.002 if video else .05)
                if not video and delivery.empty() and time.monotonic() - last_status >= 1:
                    last_status = time.monotonic()
                    connection.sendall(self.wire(JSON, self.status()))
        except (OSError, ValueError, TypeError):
            pass
        finally:
            if frame_delivery is not None:self.frames.unsubscribe(frame_delivery)
            if owned_job and self.upload_job is owned_job and (not owned_job.finished or owned_job.completed<owned_job.received):
                owned_job.cancel();self.inference_enabled=False
            if delivery is not None:
                with self.lock:
                    self.result_queues.remove(delivery)
                    self.result_queue_owners.pop(delivery,None)
                    if not self.result_queues and self.input_source=='camera':self.inference_enabled=False
            connection.close()
            self.client_limit.release()

    def listen(self, port, video):
        listener = socket.socket()
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind((self.config.get('bind', '0.0.0.0'), port))
        listener.listen(4)
        listener.settimeout(.5)
        self.listeners.append(listener)
        try:
            while not self.stop.is_set():
                try:
                    c, addr = listener.accept()
                    if self.client_limit.acquire(False):
                        self.spawn(self.tcp_client, (c, video))
                    else:
                        c.close()
                except socket.timeout:
                    continue
        finally:
            listener.close()

    def serial_loop(self, device):
        import termios
        fd = os.open(device, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
        previous = termios.tcgetattr(fd)
        raw = list(previous)
        raw[0], raw[1], raw[2], raw[3] = 0, 0, termios.CS8 | termios.CREAD | termios.CLOCAL, 0
        raw[4] = raw[5] = termios.B115200
        raw[6] = list(previous[6])
        raw[6][termios.VMIN], raw[6][termios.VTIME] = 0, 0
        termios.tcsetattr(fd, termios.TCSANOW, raw)
        decoder, authenticated = Decoder(reset_validator=self.authenticate), False
        version, last_status, last_image = 0, 0, 0
        fragments, outgoing = iter(()), bytearray()
        last_rx = time.monotonic()
        replies,epoch=queue.Queue(8),0
        try:
            while not self.stop.is_set():
                ready, writable, unused = select.select([fd], [fd] if outgoing else [], [], .01)
                if ready:
                    data = os.read(fd, 65536)
                    last_rx = time.monotonic()
                    self.serial_metrics['rx_bytes'] += len(data)
                    messages = decoder.feed(data)
                    self.serial_metrics['decoder_errors'] = decoder.errors
                    for kind, payload in messages:
                        if kind != JSON:
                            continue
                        try:
                            req = json.loads(payload.decode('utf-8'))
                            if not authenticated or req.get('op') == 'hello':
                                authenticated = self.authenticate(req)
                                self.serial_metrics['authenticated'] = authenticated
                                if authenticated:
                                    epoch+=1
                                    fragments = iter(())
                                    outgoing.extend(self.wire(JSON, dict(self.status(), type='hello', ok=True)))
                                continue
                            if req.get('op')=='cpu_frequency':
                                self.spawn(self.queued_reply,(req,replies,epoch))
                            else:
                                outgoing.extend(self.wire(JSON, self.reply(req)))
                        except Exception as exc:
                            outgoing.extend(self.wire(JSON, {'type': 'ack', 'ok': False, 'error': str(exc)}))
                if writable and outgoing:
                    n = os.write(fd, outgoing[:512])
                    self.serial_metrics['tx_bytes'] += n
                    del outgoing[:n]
                try:
                    generation,answer=replies.get_nowait()
                    if authenticated and generation==epoch:
                        outgoing.extend(self.wire(JSON,answer))
                except queue.Empty:
                    pass
                if not authenticated or outgoing:
                    continue
                now = time.monotonic()
                if now - last_rx > 8:
                    authenticated = False
                    decoder = Decoder(reset_validator=self.authenticate)
                    self.serial_metrics['authenticated'] = False
                    fragments = iter(())
                    continue
                if now - last_status > 2:
                    last_status = now
                    outgoing.extend(self.wire(JSON, self.status()))
                    continue
                got = self.results.get_after(version, .001)
                if got:
                    version, pair = got
                    result, jpeg = pair
                    if result.get('source')=='upload':continue
                    wire = {k: v for k, v in result.items() if k != 'features'}
                    wire['result_age_ms'] = (now - result['capture_monotonic']) * 1000
                    outgoing.extend(self.wire(JSON, wire))
                try:
                    part = next(fragments)
                    outgoing.extend(self.wire(IMAGE_CHUNK, part))
                except StopIteration:
                    if now - last_image > 3:
                        frame = self.frames.get_after(0, .001)
                        if frame:
                            value = frame[1]
                            with Image.open(io.BytesIO(value['jpeg'])) as image:
                                image.thumbnail((320, 240))
                                stream = io.BytesIO()
                                image.save(stream, 'JPEG', quality=40)
                            data = pack_image({k: v for k, v in value.items() if k != 'jpeg'}, stream.getvalue())
                            fragments = fragment_image(data, value['frame_id'], 512)
                            last_image = now
        finally:
            termios.tcsetattr(fd, termios.TCSANOW, previous)
            os.close(fd)

    def run(self):
        signal.signal(signal.SIGTERM, lambda *unused: self.stop.set())
        signal.signal(signal.SIGINT, lambda *unused: self.stop.set())
        self.apply_boot_defaults()
        self.spawn(self.camera.run)
        self.spawn(self.listen, (self.config.get('control_port', 8765), False))
        self.spawn(self.listen, (self.config.get('video_port', 8766), True))
        serial_device = self.config.get('serial_device')
        restore_getty = False
        if serial_device:
            getty_active = subprocess.call(['systemctl', 'is-active', '--quiet', 'serial-getty@' + os.path.basename(serial_device) + '.service']) == 0
            restore_getty = getty_active or self.config.get('serial_restore_getty', False)
            if getty_active:
                subprocess.check_call(['systemctl', 'stop', 'serial-getty@' + os.path.basename(serial_device) + '.service'])
            self.spawn(self.serial_loop, (serial_device,))
        try:
            while not self.stop.wait(1):
                pass
        finally:
            self.inference_enabled = False
            if self.inference_thread:
                self.inference_thread.join(310)
                if self.inference_thread.is_alive():
                    raise RuntimeError('inference owner still draining; refusing forced teardown')
            for thread in list(self.threads):
                if thread is not self.inference_thread:
                    thread.join(8)
            if restore_getty:
                # With boot ordering, getty start must wait until our stop job
                # finishes; waiting synchronously here would deadlock that job.
                subprocess.call(['systemctl', '--no-block', 'start', 'serial-getty@' + os.path.basename(serial_device) + '.service'])
            if self.r5 is not None:
                self.r5.close()

    def apply_boot_defaults(self):
        target = self.config.get('default_cpu_khz', DEFAULT_CPU_KHZ)
        if self.r5 is not None:
            self.r5.request(0, 10, target)
        return self.cpu.set_frequency(target)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True)
    args = parser.parse_args()
    with open(args.config) as f:
        Agent(json.load(f)).run()


if __name__ == '__main__':
    main()
