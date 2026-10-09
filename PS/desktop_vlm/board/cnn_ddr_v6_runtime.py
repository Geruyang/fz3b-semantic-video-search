"""Linux ioctl transport for the frozen CNN DDR ABI-v6 UAPI.

This module deliberately contains only the transport layer: applications own
model manifests and tensor/layout policy. Device memory is referenced only by
opaque handles and byte offsets.
"""

import ctypes
import os
import struct
import threading
import time


class V6NotReady(RuntimeError):
    """The device identity, status, or lifecycle is not safe for the request."""


_UINT32_MAX = 0xffffffff
_IDENTITY_STRUCT = struct.Struct("<38I2Q8I")
_ALLOC_STRUCT = struct.Struct("<QQIIII")
_FREE_STRUCT = struct.Struct("<II")
_TRANSFER_STRUCT = struct.Struct("<IIQQQ")
_SUBMIT_STRUCT = struct.Struct("<6I")
_STATUS_STRUCT = struct.Struct("<15I")


def _ioc(direction, type_char, number, size=0):
    return ((direction << 30) | (size << 16) | (ord(type_char) << 8) | number)


def _ior(number, size):
    return _ioc(2, "X", number, size)


def _iow(number, size):
    return _ioc(1, "X", number, size)


def _iowr(number, size):
    return _ioc(3, "X", number, size)


IOCTL_REQUESTS = {
    "GET_IDENTITY": _ior(0x40, _IDENTITY_STRUCT.size),
    "ALLOC": _iowr(0x41, _ALLOC_STRUCT.size),
    "FREE": _iow(0x42, _FREE_STRUCT.size),
    "UPLOAD": _iow(0x43, _TRANSFER_STRUCT.size),
    "DOWNLOAD": _iow(0x44, _TRANSFER_STRUCT.size),
    "SUBMIT": _iow(0x45, _SUBMIT_STRUCT.size),
    "GET_STATUS": _ior(0x46, _STATUS_STRUCT.size),
    "QUIESCE": _ioc(0, "X", 0x47),
}


# These records mirror network6_v6_uapi.h profile indices 0..6 exactly.
# CHANNELS/WIDTHS describe each descriptor's input tensor.  In particular,
# p3 is 64x64x64 and p5 is 128x32x32 even though their HLS output-channel
# count is 128 and 256.  Parameter strides and output extents are independent
# frozen tables below; callers must not derive them from the identity shape.
PROFILE_MAX_BLOCKS = (12, 20, 4, 1, 1, 1, 1)
PROFILE_CHANNELS = (128, 256, 64, 64, 128, 128, 256)
PROFILE_WIDTHS = (32, 16, 64, 64, 32, 32, 16)
PROFILE_STRIDE_WORDS = (22433, 61057, 12193, 22433, 22433, 61057, 61057)
PROFILE_SLOT_WORDS = (16384, 8192, 32768, 32768, 16384, 16384, 8192)
PROFILE_INPUT_WORDS = (16384, 8192, 32768, 32768, 16384, 16384, 8192)
PROFILE_OUTPUT_WORDS = (16384, 8192, 32768, 16384, 16384, 8192, 8192)
PROFILE_INPUT_OFFSET_WORDS = (0, 0, 0, 0, 32768, 0, 0)
PROFILE_OUTPUT_OFFSET_WORDS = (0, 0, 0, 32768, 16384, 16384, 8192)
PROFILE_NAMES = ("network2", "network4", "network0", "n1_dw", "n1_pw",
                 "n3_dw", "n3_pw")


def _identity_dict(values):
    if len(values) != 48:
        raise ValueError("FZV6 identity must contain exactly 200 bytes")
    return {
        "core_id": values[0], "core_abi": values[1], "guard_caps": values[2],
        "abi_version": values[3], "caps": values[4], "address_bits": values[5],
        "data_bits": values[6], "arena_count": values[7], "profile_count": values[8],
        "max_blocks": tuple(values[9:16]), "channels": tuple(values[16:23]),
        "widths": tuple(values[23:30]), "block_stride_words": tuple(values[30:37]),
        "reserved0": values[37], "arena_bytes": tuple(values[38:40]),
        "parameter_manifest_words": tuple(values[40:48]),
    }


class LinuxIoctlV6Transport(object):
    """Real Linux ioctl transport for ``network6_v6_uapi.h``."""

    CORE_ID = 0x465A5636
    CORE_ABI = 0x00060000
    GUARD_CAPS = 0x000001ff
    ABI_VERSION = 6
    CAP_LOW_ARENA = 1 << 0
    CAP_HIGH_ARENA = 1 << 1
    CAP_FOUR_M_AXI = 1 << 2
    ALLOC_LOW_ONLY = 1
    ALLOC_HIGH_ONLY = 2
    FLAG_POISONED = 1
    FLAG_QUIESCED = 2
    FLAG_REMOVING = 4
    FLAG_RUNNING = 8
    LOW_ARENA_BYTES = 0x3ff00000
    HIGH_ARENA_BYTES = 0x40000000
    GUARD_ERROR_MASK = (1 << 7) | (1 << 8) | (1 << 9)

    def __init__(self, device_path="/dev/network6_v6",
                 expected_parameter_manifest_words=(0,) * 8,
                 fd=None, ioctl_callable=None):
        self.device_path = device_path
        self._owns_fd = fd is None
        self.fd = os.open(device_path, os.O_RDWR | getattr(os, "O_CLOEXEC", 0)) \
            if fd is None else fd
        self._ioctl_fn = ioctl_callable
        if self._ioctl_fn is None:
            try:
                import fcntl
                self._ioctl_fn = fcntl.ioctl
            except ImportError:
                self.close_device()
                raise RuntimeError("Linux ioctl is unavailable on this platform")
        words = tuple(expected_parameter_manifest_words)
        if (len(words) != 8 or any(isinstance(word, bool) or not isinstance(word, int) or
                                   not 0 <= word <= _UINT32_MAX for word in words)):
            self.close_device()
            raise ValueError("expected manifest identity requires eight uint32 words")
        self.expected_parameter_manifest_words = words
        self.allocations = {}
        self.closed = False
        self.quiesced = False
        self._pending_completion = None
        self._generation_lock = threading.Lock()
        self._inflight_generation = None
        try:
            self.identity = self._read_identity()
            self._validate_identity()
            initial_status = self._validate_status(
                self.get_status(), expected_flags=0)
            self._generation_token = initial_status["reset_generation"]
            self._accepted_reset_generation = initial_status["reset_generation"]
        except Exception:
            self.close_device()
            raise

    def _ioctl(self, request, raw=None):
        if raw is None:
            return self._ioctl_fn(self.fd, request)
        return self._ioctl_fn(self.fd, request, raw, True)

    def _read_identity(self):
        raw = bytearray(_IDENTITY_STRUCT.size)
        self._ioctl(IOCTL_REQUESTS["GET_IDENTITY"], raw)
        return _identity_dict(_IDENTITY_STRUCT.unpack(raw))

    def _validate_identity(self):
        identity = self.identity
        expected = {
            "core_id": self.CORE_ID, "core_abi": self.CORE_ABI,
            "guard_caps": self.GUARD_CAPS, "abi_version": self.ABI_VERSION,
            "address_bits": 40, "data_bits": 128, "profile_count": 7,
            "max_blocks": PROFILE_MAX_BLOCKS, "channels": PROFILE_CHANNELS,
            "widths": PROFILE_WIDTHS, "block_stride_words": PROFILE_STRIDE_WORDS,
            "reserved0": 0,
            "parameter_manifest_words": self.expected_parameter_manifest_words,
        }
        for key, wanted in expected.items():
            if identity[key] != wanted:
                raise V6NotReady("driver identity %s mismatch: %r != %r" %
                                 (key, identity[key], wanted))
        known_caps = self.CAP_LOW_ARENA | self.CAP_HIGH_ARENA | self.CAP_FOUR_M_AXI
        if (identity["caps"] & ~known_caps or
                identity["caps"] & (self.CAP_LOW_ARENA | self.CAP_FOUR_M_AXI) !=
                (self.CAP_LOW_ARENA | self.CAP_FOUR_M_AXI)):
            raise V6NotReady("driver arena/M_AXI capabilities mismatch")
        high = bool(identity["caps"] & self.CAP_HIGH_ARENA)
        if (identity["arena_count"] != (2 if high else 1) or
                identity["arena_bytes"] != (self.LOW_ARENA_BYTES,
                    self.HIGH_ARENA_BYTES if high else 0)):
            raise V6NotReady("driver arena identity mismatch")

    def get_status(self):
        raw = bytearray(_STATUS_STRUCT.size)
        self._ioctl(IOCTL_REQUESTS["GET_STATUS"], raw)
        v = _STATUS_STRUCT.unpack(raw)
        return {"completed_frames": v[0], "protocol_error": v[1], "flags": v[2],
                "profile": v[3], "guard_status": v[4], "guard_acks": v[5],
                "ar_total": v[6], "rlast_total": v[7], "aw_total": v[8],
                "wlast_total": v[9], "b_total": v[10], "reset_generation": v[11],
                "guard_error_flags": v[12], "job_cycles": v[13] | (v[14] << 32)}

    def _validate_status(self, status, expected_flags=None, profile=None):
        if expected_flags is not None and status["flags"] != expected_flags:
            raise V6NotReady("driver status flags are not clean")
        if (status["protocol_error"] or status["guard_error_flags"] or
                status["guard_status"] & self.GUARD_ERROR_MASK):
            raise V6NotReady("driver or guard reports an error")
        if profile is not None and status["profile"] != profile:
            raise V6NotReady("driver completed another profile")
        return status

    def current_generation_token(self):
        """Stable scheduler token with strict hardware-reset tracking.

        A driver-authorized profile switch advances the hardware guard reset
        generation, but it does not invalidate frame leases.  Any generation
        change that was not accepted by ``wait_complete`` remains terminal to
        the runtime and is never folded into this token.
        """
        with self._generation_lock:
            # Keep the hardware snapshot and its accepted/planned-generation
            # decision atomic with wait_complete() publishing a newly accepted
            # generation.  GET_STATUS is short; the blocking SUBMIT remains
            # outside this lock so PS work can continue while PL runs.
            status = self._validate_status(self.get_status())
            if status["flags"] & ~self.FLAG_RUNNING:
                raise V6NotReady("driver lifecycle changed during generation check")
            allowed = {self._accepted_reset_generation}
            if self._inflight_generation is not None:
                allowed.add(self._inflight_generation[1])
            accepted = status["reset_generation"] in allowed
            if not accepted:
                raise V6NotReady("unexpected v6 reset generation change")
            return self._generation_token

    def _abort_pending_generation(self):
        with self._generation_lock:
            self._inflight_generation = None
        self._pending_completion = None

    def alloc(self, size_bytes, alignment=16, flags=0):
        if self.closed or self.quiesced:
            raise V6NotReady("transport is closed or quiesced")
        if (isinstance(size_bytes, bool) or not isinstance(size_bytes, int) or size_bytes <= 0 or
                size_bytes & 15 or isinstance(alignment, bool) or not isinstance(alignment, int) or
                alignment < 16 or alignment & (alignment - 1) or isinstance(flags, bool) or
                flags not in (0, self.ALLOC_LOW_ONLY, self.ALLOC_HIGH_ONLY)):
            raise ValueError("invalid v6 allocation size, alignment, or placement flags")
        if flags == self.ALLOC_HIGH_ONLY and not (self.identity["caps"] & self.CAP_HIGH_ARENA):
            raise V6NotReady("high DDR is not available")
        raw = bytearray(_ALLOC_STRUCT.pack(size_bytes, alignment, flags, 0, 0, 0))
        self._ioctl(IOCTL_REQUESTS["ALLOC"], raw)
        _, _, returned_flags, handle, arena, reserved = _ALLOC_STRUCT.unpack(raw)
        if (not handle or returned_flags != flags or reserved or arena not in (0, 1) or
                (arena == 1 and self.identity["arena_count"] != 2) or
                (flags == self.ALLOC_LOW_ONLY and arena != 0) or
                (flags == self.ALLOC_HIGH_ONLY and arena != 1) or
                handle in self.allocations):
            raise V6NotReady("driver returned invalid opaque allocation metadata")
        self.allocations[handle] = {"bytes": size_bytes, "arena_index": arena}
        return handle

    def _check_range(self, handle, offset, size):
        if (self.closed or isinstance(handle, bool) or not isinstance(handle, int) or
                handle not in self.allocations):
            raise V6NotReady("unknown opaque allocation handle")
        extent = self.allocations[handle]["bytes"]
        if (isinstance(offset, bool) or not isinstance(offset, int) or offset < 0 or
                isinstance(size, bool) or not isinstance(size, int) or size <= 0 or
                offset > extent or size > extent - offset):
            raise ValueError("transfer range exceeds allocation extent")
        if offset & 15 or size & 15:
            raise ValueError("v6 arena transfer offset and size must be 16-byte aligned")

    def _transfer(self, command, handle, offset, size, pointer):
        raw = bytearray(_TRANSFER_STRUCT.pack(handle, 0, offset, size, pointer))
        self._ioctl(IOCTL_REQUESTS[command], raw)

    def upload(self, handle, offset, payload):
        payload = bytes(payload)
        self._check_range(handle, offset, len(payload))
        if self.quiesced:
            raise V6NotReady("transport is quiesced")
        buf = ctypes.create_string_buffer(payload)
        self._transfer("UPLOAD", handle, offset, len(payload), ctypes.addressof(buf))

    def download(self, handle, offset, size):
        self._check_range(handle, offset, size)
        if self.quiesced:
            raise V6NotReady("transport is quiesced")
        buf = ctypes.create_string_buffer(size)
        self._transfer("DOWNLOAD", handle, offset, size, ctypes.addressof(buf))
        return buf.raw[:size]

    def upload_array(self, handle, offset, array):
        """Upload a C-contiguous NumPy array directly from its backing storage."""
        import numpy as np
        if not isinstance(array, np.ndarray) or not array.flags.c_contiguous:
            raise ValueError("upload_array requires a C-contiguous NumPy array")
        size = int(array.nbytes)
        self._check_range(handle, offset, size)
        if self.quiesced:
            raise V6NotReady("transport is quiesced")
        self._transfer("UPLOAD", handle, offset, size, int(array.ctypes.data))

    def download_into(self, handle, offset, array):
        """Download directly into a writable C-contiguous NumPy array."""
        import numpy as np
        if (not isinstance(array, np.ndarray) or not array.flags.c_contiguous or
                not array.flags.writeable):
            raise ValueError("download_into requires a writable C-contiguous NumPy array")
        size = int(array.nbytes)
        self._check_range(handle, offset, size)
        if self.quiesced:
            raise V6NotReady("transport is quiesced")
        self._transfer("DOWNLOAD", handle, offset, size, int(array.ctypes.data))

    def submit(self, profile, block_count, params_handle, activation_handle,
               activation_base_offset_bytes=0, input_offset_bytes=0):
        if isinstance(profile, bool) or not isinstance(profile, int) or profile not in range(7):
            raise ValueError("unsupported v6 profile")
        if params_handle == activation_handle:
            raise ValueError("parameter and activation handles must be distinct")
        if (params_handle not in self.allocations or activation_handle not in self.allocations or
                isinstance(block_count, bool) or not isinstance(block_count, int) or
                not 1 <= block_count <= PROFILE_MAX_BLOCKS[profile]):
            raise ValueError("invalid v6 submit handles or block count")
        if (isinstance(activation_base_offset_bytes, bool) or
                not isinstance(activation_base_offset_bytes, int) or
                activation_base_offset_bytes < 0 or activation_base_offset_bytes & 15 or
                isinstance(input_offset_bytes, bool) or not isinstance(input_offset_bytes, int) or
                input_offset_bytes < 0 or input_offset_bytes & 15):
            raise ValueError("v6 activation offsets must be non-negative and 16-byte aligned")
        param_bytes = PROFILE_STRIDE_WORDS[profile] * block_count * 16
        if self.allocations[params_handle]["bytes"] != param_bytes:
            raise ValueError("parameter allocation does not match the exact profile extent")

        activation_bytes = self.allocations[activation_handle]["bytes"]
        input_bytes = PROFILE_INPUT_WORDS[profile] * 16
        output_bytes = PROFILE_OUTPUT_WORDS[profile] * 16
        if profile <= 2:
            if input_offset_bytes != 0:
                raise ValueError("profiles 0..2 require input_offset_bytes == 0")
            slot_bytes = PROFILE_SLOT_WORDS[profile] * 16
            if activation_base_offset_bytes > activation_bytes or \
                    2 * slot_bytes > activation_bytes - activation_base_offset_bytes:
                raise ValueError("activation allocation lacks both ping-pong slots")
            output_offset = (block_count & 1) * slot_bytes
            input_start = activation_base_offset_bytes
            output_start = activation_base_offset_bytes + output_offset
            input_bytes = slot_bytes
            output_bytes = slot_bytes
        else:
            if block_count != 1:
                raise ValueError("bridge profiles execute exactly one block")
            expected_input_offset = PROFILE_INPUT_OFFSET_WORDS[profile] * 16
            if input_offset_bytes != expected_input_offset:
                raise ValueError("bridge input offset does not match the frozen profile")
            output_offset = PROFILE_OUTPUT_OFFSET_WORDS[profile] * 16
            if activation_base_offset_bytes > activation_bytes:
                raise ValueError("activation base exceeds allocation extent")
            available = activation_bytes - activation_base_offset_bytes
            if (input_offset_bytes > available or input_bytes > available - input_offset_bytes or
                    output_offset > available or output_bytes > available - output_offset):
                raise ValueError("bridge activation ranges exceed allocation extent")
            input_start = activation_base_offset_bytes + input_offset_bytes
            output_start = activation_base_offset_bytes + output_offset
            if input_start < output_start + output_bytes and output_start < input_start + input_bytes:
                raise ValueError("bridge input and output extents overlap")

        if self.quiesced:
            raise V6NotReady("SUBMIT is unavailable after QUIESCE")
        before = self._validate_status(self.get_status(), expected_flags=0)
        mode_switch = bool(before["completed_frames"] and
                           before["profile"] != profile)
        expected_generation = ((before["reset_generation"] +
                                (1 if mode_switch else 0)) & _UINT32_MAX)
        with self._generation_lock:
            if (self._inflight_generation is not None or
                    self._pending_completion is not None or
                    before["reset_generation"] != self._accepted_reset_generation):
                raise V6NotReady("unexpected v6 reset generation before submit")
            self._inflight_generation = (
                before["reset_generation"], expected_generation, profile)
        raw = bytearray(_SUBMIT_STRUCT.pack(profile, block_count, params_handle,
                                            activation_handle,
                                            activation_base_offset_bytes,
                                            input_offset_bytes))
        try:
            self._ioctl(IOCTL_REQUESTS["SUBMIT"], raw)
        except Exception:
            with self._generation_lock:
                self._inflight_generation = None
            raise
        self._pending_completion = (
            before, profile, mode_switch, expected_generation)

    def wait_complete(self, profile, timeout_s):
        if self._pending_completion is None:
            raise V6NotReady("there is no submitted v6 job")
        before, expected_profile, mode_switch, expected_generation = \
            self._pending_completion
        if expected_profile != profile:
            self._abort_pending_generation()
            raise V6NotReady("completion wait profile mismatch")
        deadline = time.monotonic() + timeout_s
        while True:
            try:
                status = self.get_status()
                self._validate_status(status, expected_flags=0, profile=profile)
            except Exception:
                self._abort_pending_generation()
                raise
            if status["completed_frames"] != before["completed_frames"]:
                if status["completed_frames"] != ((before["completed_frames"] + 1) & _UINT32_MAX):
                    self._abort_pending_generation()
                    raise V6NotReady("driver completed an unexpected number of jobs")
                complete_mask = (1 << 4) | (1 << 10) | (1 << 11)
                active_mask = (1 << 13) | (1 << 15)
                if ((status["guard_status"] & complete_mask) != complete_mask or
                        status["guard_status"] & active_mask or status["job_cycles"] <= 0):
                    self._abort_pending_generation()
                    raise V6NotReady("v6 job lacks clean completion and timer evidence")
                for field in ("ar_total", "rlast_total", "aw_total", "wlast_total", "b_total"):
                    if ((status[field] - before[field]) & _UINT32_MAX) <= 0:
                        self._abort_pending_generation()
                        raise V6NotReady("v6 guard counter %s did not advance" % field)
                if status["reset_generation"] != expected_generation:
                    self._abort_pending_generation()
                    raise V6NotReady("v6 reset generation does not match profile switch")
                with self._generation_lock:
                    if self._inflight_generation != (
                            before["reset_generation"], expected_generation, profile):
                        self._inflight_generation = None
                        self._pending_completion = None
                        raise V6NotReady("v6 in-flight generation plan changed")
                    self._accepted_reset_generation = status["reset_generation"]
                    self._inflight_generation = None
                self._pending_completion = None
                after = dict(status)
                completion = dict(after)
                completion["status_before"] = dict(before)
                completion["status_after"] = after
                completion["reset_generation_before"] = before["reset_generation"]
                completion["mode_switch_reset"] = mode_switch
                completion["generation_token"] = self._generation_token
                completion["hardware_reset_generation"] = status["reset_generation"]
                return completion
            if time.monotonic() >= deadline:
                self._abort_pending_generation()
                raise TimeoutError("v6 PL job timed out")
            time.sleep(0.001)

    def quiesce(self):
        if not self.closed and not self.quiesced:
            self._ioctl(IOCTL_REQUESTS["QUIESCE"])
            self.quiesced = True

    def free(self, handle):
        if handle not in self.allocations:
            raise V6NotReady("unknown opaque allocation handle")
        if not self.quiesced:
            raise V6NotReady("FREE is permitted only after QUIESCE")
        self._ioctl(IOCTL_REQUESTS["FREE"], bytearray(_FREE_STRUCT.pack(handle, 0)))
        del self.allocations[handle]

    def close_device(self):
        if self.closed:
            return
        self.closed = True
        if self._owns_fd:
            os.close(self.fd)

    def close(self):
        """Quiesce, free owned opaque handles, and close the device descriptor."""
        if self.closed:
            return {"quiesce_confirmed": self.quiesced,
                    "all_handles_freed": not self.allocations, "transport_closed": True}
        failure = None
        try:
            self.quiesce()
            for handle in list(self.allocations.keys()):
                try:
                    self.free(handle)
                except Exception as error:
                    if failure is None:
                        failure = error
        except Exception as error:
            if failure is None:
                failure = error
        finally:
            self.close_device()
        if failure is not None:
            raise failure
        return {"quiesce_confirmed": self.quiesced,
                "all_handles_freed": not self.allocations, "transport_closed": self.closed}


__all__ = ["LinuxIoctlV6Transport", "V6NotReady", "IOCTL_REQUESTS",
           "PROFILE_MAX_BLOCKS", "PROFILE_CHANNELS", "PROFILE_WIDTHS",
           "PROFILE_STRIDE_WORDS", "PROFILE_SLOT_WORDS", "PROFILE_NAMES"]
