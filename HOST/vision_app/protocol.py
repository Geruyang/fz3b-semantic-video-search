"""Bounded, resynchronising wire protocol, shared with Python 3.6 board."""
import json
import struct
import time
import zlib

MAGIC = b'FZVA'
HEADER = struct.Struct('<4sBBHII')
MAX_PAYLOAD = 4 * 1024 * 1024
JSON, PREVIEW, RESULT_IMAGE, IMAGE_CHUNK = 1, 2, 3, 4
INPUT_FRAME = 5
CHUNK_HEADER = struct.Struct('<QII')


def json_bytes(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')


def encode_message(kind, payload, crc=None):
    if kind not in (JSON, PREVIEW, RESULT_IMAGE, IMAGE_CHUNK, INPUT_FRAME):
        raise ValueError('unknown message kind')
    payload = json_bytes(payload) if isinstance(payload, dict) else bytes(payload)
    if len(payload) > MAX_PAYLOAD:
        raise ValueError('payload too large')
    checksum = zlib.crc32(payload) if crc is None else crc(payload)
    return HEADER.pack(MAGIC, 1, kind, 0, len(payload), checksum & 0xffffffff) + payload


class Decoder:
    def __init__(self, reset_validator=None):
        self.buffer = bytearray()
        self.errors = 0
        self.reset_validator = reset_validator
        self.hello_tail = b''

    def reconnect(self, data):
        # Only an authenticated, CRC-valid short HELLO can interrupt a partial
        # UART request. Scan new bytes plus a bounded tail, not the large query.
        scan = self.hello_tail + bytes(data)
        old_end = len(self.hello_tail)
        self.hello_tail = scan[-(2048 + HEADER.size):]
        position = scan.find(MAGIC)
        while position >= 0:
            if len(scan) - position >= HEADER.size:
                magic, version, kind, flags, size, checksum = HEADER.unpack_from(scan, position)
                end = position + HEADER.size + size
                if version == 1 and kind == JSON and flags == 0 and size <= 2048 and old_end < end <= len(scan):
                    payload = scan[position + HEADER.size:end]
                    if zlib.crc32(payload) & 0xffffffff == checksum:
                        try:
                            value = json.loads(payload.decode('utf-8'))
                            if isinstance(value, dict) and value.get('op') == 'hello' and self.reset_validator(value):
                                self.buffer = bytearray(scan[position:])
                                return True
                        except (ValueError, TypeError):
                            pass
            position = scan.find(MAGIC, position + 4)
        return False

    def feed(self, data):
        if self.reset_validator is None or not self.reconnect(data):
            self.buffer.extend(data)
        output = []
        while True:
            position = self.buffer.find(MAGIC)
            if position < 0:
                if len(self.buffer) > 3:
                    del self.buffer[:-3]
                break
            if position:
                del self.buffer[:position]
            if len(self.buffer) < HEADER.size:
                break
            magic, version, kind, flags, size, checksum = HEADER.unpack_from(self.buffer)
            if version != 1 or flags != 0 or kind not in (JSON, PREVIEW, RESULT_IMAGE, IMAGE_CHUNK, INPUT_FRAME) or size > MAX_PAYLOAD:
                self.errors += 1
                del self.buffer[:4]
                continue
            if len(self.buffer) < HEADER.size + size:
                break
            payload = bytes(self.buffer[HEADER.size:HEADER.size + size])
            del self.buffer[:HEADER.size + size]
            if zlib.crc32(payload) & 0xffffffff != checksum:
                self.errors += 1
                continue
            output.append((kind, payload))
        return output


def pack_image(metadata, jpeg):
    meta = json_bytes(metadata)
    if len(meta) > 65536 or len(jpeg) + len(meta) + 4 > MAX_PAYLOAD:
        raise ValueError('image metadata/payload exceeds limit')
    return struct.pack('<I', len(meta)) + meta + bytes(jpeg)


def unpack_image(payload):
    if len(payload) < 4:
        raise ValueError('short image')
    n = struct.unpack_from('<I', payload)[0]
    if n > 65536 or n + 4 >= len(payload):
        raise ValueError('invalid image metadata length')
    meta = json.loads(payload[4:4 + n].decode('utf-8'))
    if not isinstance(meta, dict) or type(meta.get('frame_id')) is not int or meta['frame_id'] < 0:
        raise ValueError('image frame ID missing')
    return meta, payload[4 + n:]


def fragment_image(payload, frame_id, size=1024):
    if not 64 <= size <= 8192 or len(payload) > MAX_PAYLOAD:
        raise ValueError('invalid fragment size')
    for offset in range(0, len(payload), size):
        yield CHUNK_HEADER.pack(frame_id, len(payload), offset) + payload[offset:offset + size]


class ImageAssembler:
    def __init__(self):
        self.frame_id = None
        self.buffer = bytearray()
        self.total = 0
        self.updated = 0

    def feed(self, part):
        if len(part) < CHUNK_HEADER.size:
            raise ValueError('short fragment')
        frame, total, offset = CHUNK_HEADER.unpack_from(part)
        data = part[CHUNK_HEADER.size:]
        if not 0 < total <= MAX_PAYLOAD or not data or offset + len(data) > total:
            raise ValueError('invalid fragment extent')
        if offset == 0:
            self.frame_id, self.total, self.buffer = frame, total, bytearray()
        if frame != self.frame_id or total != self.total or offset != len(self.buffer) or (offset and time.monotonic() - self.updated > 10):
            self.buffer.clear()
            self.frame_id = None
            raise ValueError('fragment order/identity/timeout mismatch')
        self.buffer.extend(data)
        self.updated = time.monotonic()
        if len(self.buffer) == total:
            result = bytes(self.buffer)
            self.buffer.clear()
            self.frame_id = None
            return result
        return None
