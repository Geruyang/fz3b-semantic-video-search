"""Linux ioctl backend for the replicated FZV7 user-space runner."""

from __future__ import print_function

import ctypes
import os
import struct


IDENTITY = struct.Struct("<28I2Q8I")
ALLOC = struct.Struct("<QQIIII")
FREE = struct.Struct("<II")
TRANSFER = struct.Struct("<IIQQQ")
SUBMIT = struct.Struct("<4IQ12I")
STATUS = struct.Struct("<16I")

CORE_ID = 0x465A5637
CORE_ABI = 0x00070000
GUARD_CAPS = 0x000001FF
ABI_VERSION = 7
PROFILE_COUNT = 3
MAX_CORES = 4


def _ioc(direction, number, size):
    return ((direction << 30) | (size << 16) | (ord("Z") << 8) | number)


IOC_GET_IDENTITY = _ioc(2, 0x40, IDENTITY.size)
IOC_ALLOC = _ioc(3, 0x41, ALLOC.size)
IOC_FREE = _ioc(1, 0x42, FREE.size)
IOC_UPLOAD = _ioc(1, 0x43, TRANSFER.size)
IOC_DOWNLOAD = _ioc(1, 0x44, TRANSFER.size)
IOC_SUBMIT = _ioc(1, 0x45, SUBMIT.size)
IOC_GET_STATUS = _ioc(3, 0x46, STATUS.size)
IOC_QUIESCE = _ioc(0, 0x47, 0)

STATUS_NAMES = (
    "core_id", "completed_jobs", "protocol_error", "flags", "profile",
    "guard_status", "guard_acks", "ar_total", "rlast_total", "aw_total",
    "wlast_total", "b_total", "reset_generation", "guard_error_flags",
    "job_cycles_lo", "job_cycles_hi",
)


def decode_identity(payload):
    values = IDENTITY.unpack(payload)
    result = {
        "core_id": values[0], "core_abi": values[1],
        "guard_caps": values[2], "abi_version": values[3],
        "caps": values[4], "address_bits": values[5],
        "data_bits": values[6], "arena_count": values[7],
        "profile_count": values[8],
        "blocks": list(values[9:12]),
        "channels": list(values[12:15]),
        "widths": list(values[15:18]),
        "block_stride_words": list(values[18:21]),
        "tensor_words": list(values[21:24]),
        "row_words": list(values[24:27]),
        "core_count": values[27],
        "arena_bytes": list(values[28:30]),
        "software_parameter_manifest_words": list(values[30:38]),
    }
    if (result["core_id"], result["core_abi"], result["guard_caps"],
            result["abi_version"], result["profile_count"]) != (
            CORE_ID, CORE_ABI, GUARD_CAPS, ABI_VERSION, PROFILE_COUNT):
        raise RuntimeError("FZV7 replicated-core identity mismatch")
    if result["core_count"] < 1 or result["core_count"] > MAX_CORES:
        raise RuntimeError("FZV7 routed core count is outside 1..4")
    return result


def decode_status(payload, requested_core):
    result = dict(zip(STATUS_NAMES, STATUS.unpack(payload)))
    if int(result["core_id"]) != int(requested_core):
        raise RuntimeError("driver returned status for a different core")
    result["job_cycles"] = ((int(result["job_cycles_hi"]) << 32) |
                            int(result["job_cycles_lo"]))
    return result


class MulticoreLinuxDevice(object):
    def __init__(self, path):
        self._fcntl = __import__("fcntl")
        self.fd = os.open(path, os.O_RDWR | getattr(os, "O_CLOEXEC", 0))

    def close(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None

    def _mutable_ioctl(self, command, packed):
        data = bytearray(packed)
        self._fcntl.ioctl(self.fd, command, data, True)
        return bytes(data)

    def identity(self):
        return decode_identity(self._mutable_ioctl(
            IOC_GET_IDENTITY, bytes(IDENTITY.size)))

    def status(self, core_id):
        core_id = int(core_id)
        if core_id < 0 or core_id >= MAX_CORES:
            raise ValueError("core_id must be in 0..3")
        request = STATUS.pack(core_id, *([0] * 15))
        return decode_status(self._mutable_ioctl(IOC_GET_STATUS, request),
                             core_id)

    def alloc(self, size, alignment=65536, flags=1):
        values = ALLOC.unpack(self._mutable_ioctl(
            IOC_ALLOC, ALLOC.pack(int(size), int(alignment), int(flags),
                                  0, 0, 0)))
        return {"bytes": values[0], "alignment": values[1],
                "flags": values[2], "handle": values[3],
                "arena_index": values[4]}

    def free(self, handle):
        self._fcntl.ioctl(self.fd, IOC_FREE, FREE.pack(int(handle), 0))

    def upload(self, handle, offset, payload):
        buffer_ = ctypes.create_string_buffer(payload)
        request = TRANSFER.pack(int(handle), 0, int(offset), len(payload),
                                ctypes.addressof(buffer_))
        self._fcntl.ioctl(self.fd, IOC_UPLOAD, request)

    def download(self, handle, offset, size):
        buffer_ = ctypes.create_string_buffer(int(size))
        request = TRANSFER.pack(int(handle), 0, int(offset), int(size),
                                ctypes.addressof(buffer_))
        self._fcntl.ioctl(self.fd, IOC_DOWNLOAD, request)
        return buffer_.raw

    def submit(self, descriptor, params_handle, memory_handle):
        values = [int(descriptor[name]) for name in (
            "core_id", "profile", "block_index")]
        values.append(0)
        frame_tag = int(descriptor["frame_tag"])
        tail = [int(descriptor[name]) for name in (
            "param_base_words", "params_words", "memory_words",
            "src_words", "dst_words", "scratch_words", "start_row",
            "row_count")]
        tail.extend((int(params_handle), int(memory_handle), 0, 0))
        self._fcntl.ioctl(self.fd, IOC_SUBMIT,
                          SUBMIT.pack(*(values + [frame_tag] + tail)))

    def quiesce(self):
        self._fcntl.ioctl(self.fd, IOC_QUIESCE, 0)


def create():
    return MulticoreLinuxDevice(os.environ.get(
        "CNN_SHARED_V7_MULTICORE_DEVICE", "/dev/network7_v7_multicore"))
