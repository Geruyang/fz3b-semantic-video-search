"""TCM-only R5 mailbox: native aligned MMIO, never Python mmap memcpy."""
import ctypes
import glob
import os
import struct
import threading
import time

def acquire_owner():
    import fcntl
    owner = open('/run/fz3b-vision-r5-owner.lock', 'a')
    try:
        fcntl.flock(owner.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        owner.close()
        raise RuntimeError('R5 mailboxes already have an application owner')
    return owner


class R5Bridge:
    def __init__(self, library=None):
        self.owner = acquire_owner()
        self.native = None
        self.locks = [threading.Lock(), threading.Lock()]
        try:
            self.open(library)
        except BaseException:
            if self.native is not None:
                self.native.r5_close()
            self.owner.close()
            raise

    def open(self, library):
        # Never touch TCM until Linux confirms both of our known firmware
        # instances are powered and running in this boot.
        for core in range(2):
            instances = [p for p in glob.glob('/sys/class/remoteproc/remoteproc*') if 'app-r5%d' % core in os.path.realpath(p)]
            if len(instances) != 1:
                raise RuntimeError('R5-%d instance is not qualified in this boot' % core)
            with open(instances[0] + '/state') as f:
                state = f.read().strip()
            with open(instances[0] + '/firmware') as f:
                firmware = f.read().strip()
            if state != 'running' or firmware != 'fz3b-app-r5%d.elf' % core:
                raise RuntimeError('R5-%d firmware is not running' % core)
        self.native = ctypes.CDLL(library or os.path.join(os.path.dirname(__file__), 'libr5_tcm_io.so'))
        self.native.r5_read.argtypes = [ctypes.c_uint, ctypes.c_uint]
        self.native.r5_read.restype = ctypes.c_uint32
        self.native.r5_read_score.argtypes=[ctypes.c_uint,ctypes.c_uint]
        self.native.r5_read_score.restype=ctypes.c_uint32
        self.query_key=None;self.semantic_matches=0;self.exact_fallbacks=0
        self.native.r5_request.argtypes = [ctypes.c_uint, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32)]
        rc = self.native.r5_open()
        if rc:
            raise RuntimeError('R5 mailbox open failed (%d)' % rc)
        before = [self.heartbeat(i) for i in range(2)]
        time.sleep(.03)
        if any(self.heartbeat(i) == before[i] for i in range(2)):
            raise RuntimeError('R5 heartbeat not advancing')

    def heartbeat(self, core):
        return int(self.native.r5_read(core, 3))

    def request(self, core, opcode, argument=0, data=b'', timeout=.5):
        if not 0 <= core < 2 or len(data) > 8192:
            raise ValueError('R5 mailbox extent invalid')
        buffer = ctypes.create_string_buffer(data)
        answer = ctypes.c_uint32()
        with self.locks[core]:
            rc = self.native.r5_request(core, opcode, argument, buffer, len(data), ctypes.byref(answer))
        if rc:
            raise ValueError('R5 request failed (%d)' % rc)
        return answer.value

    def crc(self, data):
        seed = 0
        for offset in range(0, len(data), 8192):
            seed = self.request(1, 20, seed, data[offset:offset+8192])
        return seed

    def telemetry(self, khz, available_kb, camera_fps, sequence):
        return self.request(0, 11, data=struct.pack('<4I', khz, available_kb, int(camera_fps * 1000), sequence))

    def match(self,feature,threshold,snapshot):
        import numpy as np
        from .state import normalized
        items,values,revision,identity=snapshot
        query=normalized(np.asarray(feature).reshape(1,-1))[0]
        packed=np.rint(query*32767).astype('<i2').tobytes();scores=[]
        def send(op,arg,data=b''):
            buffer=ctypes.create_string_buffer(data);answer=ctypes.c_uint32()
            rc=self.native.r5_request(0,op,arg&0xffffffff,buffer,len(data),ctypes.byref(answer))
            if rc:raise ValueError('R5 semantic request failed (%d)'%rc)
            return answer.value
        with self.locks[0]:
            for start in range(0,len(items),16):
                block=values[start:start+16];key=(revision,start,len(block))
                if self.query_key!=key:
                    send(30,len(block))
                    for i,row in enumerate(block):send(31,i,np.rint(row*32767).astype('<i2').tobytes())
                    self.query_key=key
                send(32,int(round(threshold*32767*32767)),packed)
                for i in range(len(block)):
                    raw=self.native.r5_read_score(0,i)
                    if raw>=0x80000000:raw-=0x100000000
                    scores.append(raw/(32767.0*32767.0))
            self.semantic_matches+=1
        scores=np.asarray(scores)
        near=np.abs(scores-threshold)<.0015
        if near.any():
            scores[near]=values[near].dot(query);self.exact_fallbacks+=int(near.sum())
        scores=np.clip(scores,-1,1);order=np.argsort(-scores,kind='mergesort')
        ranking=[dict(items[int(i)],score=float(scores[i])) for i in order]
        return dict(query_revision=revision,ranking=ranking,best=ranking[0],unknown=ranking[0]['score']<threshold,threshold=threshold,identity=identity,score_engine='R5-Q15 / boundary-exact',hits=[r['id'] for r in ranking if r['score']>=threshold])

    def status(self):
        return {'mode': 'dual R5 split / TCM', 'offload_verified': True,
                'semantic_matches':self.semantic_matches,'exact_threshold_fallbacks':self.exact_fallbacks,
                'cores': [{'core': i, 'heartbeat': self.heartbeat(i), 'requests': int(self.native.r5_read(i, 5)), 'role': 'semantic scores / hits / frame sequence / telemetry' if i == 0 else 'transport CRC / framing'} for i in range(2)]}

    def close(self):
        self.native.r5_close()
        self.owner.close()
