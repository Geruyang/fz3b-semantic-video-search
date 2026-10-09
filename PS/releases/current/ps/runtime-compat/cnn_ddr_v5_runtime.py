"""Opaque-handle v5 accelerator adapter and live PS/PL/PS execution path.

The board-side module uses only Python stdlib plus NumPy.  ONNX and ONNX
Runtime are host build dependencies; deployed partitions run through the
existing C ORT runner.  No physical DDR address crosses this API.
"""

import ctypes
import hashlib
import json
import math
import os
import struct
import time

import numpy as np

try:
    from bounded_pipeline import BoundedPipeline
except ImportError:
    try:
        from .bounded_pipeline import BoundedPipeline
    except ImportError:
        BoundedPipeline = None


class V5NotReady(RuntimeError):
    pass


class ProfileSpec(object):
    def __init__(self, profile, stage, channels, width, max_blocks,
                 block_stride_words, slot_words):
        self.profile = profile
        self.stage = stage
        self.channels = channels
        self.width = width
        self.max_blocks = max_blocks
        self.block_stride_words = block_stride_words
        self.slot_words = slot_words
        self.activation_bytes = channels * width * width * 2
        self.parameter_bytes = block_stride_words * 16 * max_blocks


PROFILE_SPECS = {
    0: ProfileSpec(0, "N2", 128, 32, 12, 22433, 16384),
    1: ProfileSpec(1, "N4", 256, 16, 20, 61057, 8192),
    2: ProfileSpec(2, "N0", 64, 64, 4, 12193, 32768),
}
PROFILE_ORDER = (2, 0, 1)
PROFILE_IDENTITY_ORDER = (0, 1, 2)
V5_BUNDLE_DIRECTORY = "network-w16-runtime-bundles-001"
V5_BUNDLE_MANIFEST_SHA256 = "400ecf86365f5e387ce62d350b6e4f24ab34b1dd5d903142c7a139515e19f18a"
V5_SCALE_MANIFEST_SHA256 = "59c4dde6427a95d7256800f861c76ba14a558029ac6eaec479afae31dc83db29"
THREAD_BUDGET_PRESETS = {
    "serial4": {"stem_prefix": 4, "network1_bridge": 4,
                "network3_bridge": 4, "suffix": 4},
    "matched1_3": {"stem_prefix": 1, "network1_bridge": 1,
                    "network3_bridge": 1, "suffix": 3},
    "candidate_prefix2_bridge1_suffix1": {
        "stem_prefix": 2, "network1_bridge": 1,
        "network3_bridge": 1, "suffix": 1},
}
_UINT32_MAX = 0xffffffff

_IDENTITY_STRUCT = struct.Struct("<22I2Q8I")
_ALLOC_STRUCT = struct.Struct("<QQIIII")
_FREE_STRUCT = struct.Struct("<II")
_TRANSFER_STRUCT = struct.Struct("<IIQQQ")
_SUBMIT_STRUCT = struct.Struct("<IIII")
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


def _sha256_bytes(value):
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _identity_dict(values):
    if len(values) != 32:
        raise ValueError("FZV5 identity must contain exactly 136 bytes")
    return {
        "core_id": values[0], "core_abi": values[1], "guard_caps": values[2],
        "abi_version": values[3], "caps": values[4], "address_bits": values[5],
        "data_bits": values[6], "arena_count": values[7], "profile_count": values[8],
        "max_blocks": tuple(values[9:12]), "channels": tuple(values[12:15]),
        "widths": tuple(values[15:18]), "block_stride_words": tuple(values[18:21]),
        "reserved0": values[21], "arena_bytes": tuple(values[22:24]),
        "parameter_manifest_words": tuple(values[24:32]),
    }


def _checked_scale(value, label):
    result = float(value)
    if not math.isfinite(result) or result <= 0:
        raise ValueError("%s must be finite and positive" % label)
    return result


def quantize_chw(value, scale, profile, label):
    spec = PROFILE_SPECS[profile]
    expected = (1, spec.channels, spec.width, spec.width)
    source = np.asarray(value, dtype=np.float32)
    if source.shape != expected or not np.all(np.isfinite(source)):
        raise ValueError("%s must be finite FP32 CHW %s" % (label, expected))
    quantized = np.rint(source.astype(np.float64) / scale)
    return np.ascontiguousarray(np.clip(quantized, -32768, 32767), dtype="<i2").reshape(expected)


def dequantize_chw(value, scale, profile, label):
    spec = PROFILE_SPECS[profile]
    expected = (1, spec.channels, spec.width, spec.width)
    source = np.asarray(value)
    if source.shape != expected or source.dtype != np.dtype("<i2"):
        raise ValueError("%s must be INT16 CHW %s" % (label, expected))
    return np.asarray(source, dtype=np.float32) * np.float32(scale)


def _chw_to_hcw(value, profile):
    spec = PROFILE_SPECS[profile]
    array = np.asarray(value)
    expected = (1, spec.channels, spec.width, spec.width)
    if array.shape != expected or array.dtype != np.dtype("<i2"):
        raise ValueError("profile %d activation must be INT16 CHW %s" % (profile, expected))
    return np.ascontiguousarray(array[0].transpose(1, 0, 2), dtype="<i2")


def _hcw_to_chw(value, profile):
    spec = PROFILE_SPECS[profile]
    array = np.asarray(value)
    expected = (spec.width, spec.channels, spec.width)
    if array.shape != expected or array.dtype != np.dtype("<i2"):
        raise ValueError("profile %d output must be INT16 HCW %s" % (profile, expected))
    return np.ascontiguousarray(array.transpose(1, 0, 2)[None, ...], dtype="<i2")


class LinuxIoctlV5Transport(object):
    """Linux UAPI v5 transport; only opaque handles and offsets are exposed."""

    CORE_ID = 0x465A5635
    CORE_ABI = 0x00050000
    GUARD_CAPS = 0x000001ff
    ABI_VERSION = 5
    CAPS = 0x00000007
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

    def __init__(self, device_path="/dev/network5_v5",
                 expected_parameter_manifest_words=(0,) * 8,
                 fd=None, ioctl_callable=None):
        self.device_path = device_path
        self._owns_fd = fd is None
        self.fd = os.open(device_path, os.O_RDWR | getattr(os, "O_CLOEXEC", 0)) if fd is None else fd
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
        try:
            self.identity = self._read_identity()
            self._validate_identity()
            self._validate_status(self.get_status(), expected_flags=0)
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
            "address_bits": 40, "data_bits": 128,
            "profile_count": 3,
            "max_blocks": (12, 20, 4), "channels": (128, 256, 64),
            "widths": (32, 16, 64), "block_stride_words": (22433, 61057, 12193),
            "reserved0": 0,
            "parameter_manifest_words": self.expected_parameter_manifest_words,
        }
        for key, wanted in expected.items():
            if identity[key] != wanted:
                raise V5NotReady("driver identity %s mismatch: %r != %r" %
                                 (key, identity[key], wanted))
        known_caps = self.CAP_LOW_ARENA | self.CAP_HIGH_ARENA | self.CAP_FOUR_M_AXI
        if (identity["caps"] & ~known_caps or
                identity["caps"] & (self.CAP_LOW_ARENA | self.CAP_FOUR_M_AXI) !=
                (self.CAP_LOW_ARENA | self.CAP_FOUR_M_AXI)):
            raise V5NotReady("driver arena/M_AXI capabilities mismatch")
        high = bool(identity["caps"] & self.CAP_HIGH_ARENA)
        if (identity["arena_count"] != (2 if high else 1) or
                identity["arena_bytes"] != (self.LOW_ARENA_BYTES,
                    self.HIGH_ARENA_BYTES if high else 0)):
            raise V5NotReady("driver arena identity mismatch")

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
            raise V5NotReady("driver status flags are not clean")
        if (status["protocol_error"] or status["guard_error_flags"] or
                status["guard_status"] & self.GUARD_ERROR_MASK):
            raise V5NotReady("driver or guard reports an error")
        if profile is not None and status["profile"] != profile:
            raise V5NotReady("driver completed another profile")
        return status

    def alloc(self, size_bytes, alignment=16, flags=0):
        if self.closed or self.quiesced:
            raise V5NotReady("transport is closed or quiesced")
        if (isinstance(size_bytes, bool) or not isinstance(size_bytes, int) or size_bytes <= 0 or
                size_bytes & 15 or isinstance(alignment, bool) or not isinstance(alignment, int) or
                alignment < 16 or alignment & (alignment - 1) or isinstance(flags, bool) or
                flags not in (0, 1, 2)):
            raise ValueError("invalid v5 allocation size, alignment, or placement flags")
        if flags == 2 and not (self.identity["caps"] & self.CAP_HIGH_ARENA):
            raise V5NotReady("high DDR is not available")
        raw = bytearray(_ALLOC_STRUCT.pack(size_bytes, alignment, flags, 0, 0, 0))
        self._ioctl(IOCTL_REQUESTS["ALLOC"], raw)
        _, _, returned_flags, handle, arena, reserved = _ALLOC_STRUCT.unpack(raw)
        if (not handle or returned_flags != flags or reserved or arena not in (0, 1) or
                (arena == 1 and self.identity["arena_count"] != 2) or
                (flags == 1 and arena != 0) or (flags == 2 and arena != 1) or
                handle in self.allocations):
            raise V5NotReady("driver returned invalid opaque allocation metadata")
        self.allocations[handle] = {"bytes": size_bytes, "arena_index": arena}
        return handle

    def _check_range(self, handle, offset, size):
        if (self.closed or isinstance(handle, bool) or not isinstance(handle, int) or
                handle not in self.allocations):
            raise V5NotReady("unknown opaque allocation handle")
        extent = self.allocations[handle]["bytes"]
        if (isinstance(offset, bool) or not isinstance(offset, int) or offset < 0 or
                isinstance(size, bool) or not isinstance(size, int) or size <= 0 or
                offset > extent or size > extent - offset):
            raise ValueError("transfer range exceeds allocation extent")
        if offset & 15 or size & 15:
            raise ValueError("v5 arena transfer offset and size must be 16-byte aligned")

    def _transfer(self, command, handle, offset, size, buffer):
        raw = bytearray(_TRANSFER_STRUCT.pack(handle, 0, offset, size, ctypes.addressof(buffer)))
        self._ioctl(IOCTL_REQUESTS[command], raw)

    def upload(self, handle, offset, payload):
        payload = bytes(payload)
        self._check_range(handle, offset, len(payload))
        if self.quiesced:
            raise V5NotReady("transport is quiesced")
        buf = ctypes.create_string_buffer(payload)
        self._transfer("UPLOAD", handle, offset, len(payload), buf)

    def download(self, handle, offset, size):
        self._check_range(handle, offset, size)
        if self.quiesced:
            raise V5NotReady("transport is quiesced")
        buf = ctypes.create_string_buffer(size)
        self._transfer("DOWNLOAD", handle, offset, size, buf)
        return buf.raw[:size]

    def submit(self, profile, block_count, params_handle, activation_handle):
        if profile not in PROFILE_SPECS or params_handle == activation_handle:
            raise ValueError("invalid v5 profile or aliased handles")
        if (params_handle not in self.allocations or activation_handle not in self.allocations or
                isinstance(block_count, bool) or not isinstance(block_count, int) or
                not 1 <= block_count <= PROFILE_SPECS[profile].max_blocks or
                self.allocations[params_handle]["bytes"] !=
                    PROFILE_SPECS[profile].block_stride_words * 16 * block_count or
                self.allocations[activation_handle]["bytes"] < 2 * PROFILE_SPECS[profile].activation_bytes):
            raise ValueError("submit handles do not cover the profile extents")
        if self.quiesced:
            raise ValueError("v5 SUBMIT is unavailable after QUIESCE")
        before_status = self._validate_status(self.get_status(), expected_flags=0)
        before = before_status["completed_frames"]
        raw = bytearray(_SUBMIT_STRUCT.pack(profile, block_count, params_handle, activation_handle))
        self._ioctl(IOCTL_REQUESTS["SUBMIT"], raw)
        self._pending_completion = (before, profile, before_status)

    def wait_complete(self, profile, timeout_s):
        if not self._pending_completion:
            raise V5NotReady("there is no submitted v5 job")
        before, expected_profile, before_status = self._pending_completion
        if expected_profile != profile:
            raise V5NotReady("completion wait profile mismatch")
        deadline = time.monotonic() + timeout_s
        while True:
            status = self.get_status()
            self._validate_status(status, expected_flags=0, profile=profile)
            if status["completed_frames"] != before:
                if status["completed_frames"] != ((before + 1) & _UINT32_MAX):
                    raise V5NotReady("driver completed an unexpected number of jobs")
                complete_mask = (1 << 4) | (1 << 10) | (1 << 11)
                active_mask = (1 << 13) | (1 << 15)
                if (status["guard_status"] & complete_mask) != complete_mask or \
                        status["guard_status"] & active_mask or status["job_cycles"] <= 0:
                    raise V5NotReady("v5 job lacks clean done/idle/counter/timer evidence")
                for field in ("ar_total", "rlast_total", "aw_total", "wlast_total", "b_total"):
                    delta = (status[field] - before_status[field]) & _UINT32_MAX
                    if delta <= 0:
                        raise V5NotReady("v5 guard counter %s did not advance" % field)
                self._pending_completion = None
                after_status = dict(status)
                completion = dict(status)
                completion["status_before"] = before_status
                completion["status_after"] = after_status
                return completion
            if time.monotonic() >= deadline:
                raise TimeoutError("v5 PL job timed out")
            time.sleep(0.001)

    def quiesce(self):
        if not self.closed and not self.quiesced:
            self._ioctl(IOCTL_REQUESTS["QUIESCE"])
            self.quiesced = True

    def free(self, handle):
        if handle not in self.allocations:
            raise V5NotReady("unknown opaque allocation handle")
        if not self.quiesced:
            raise V5NotReady("FREE is permitted only after QUIESCE")
        self._ioctl(IOCTL_REQUESTS["FREE"], bytearray(_FREE_STRUCT.pack(handle, 0)))
        del self.allocations[handle]

    def close_device(self):
        if self.closed:
            return
        self.closed = True
        if self._owns_fd:
            os.close(self.fd)


class FakeV5Transport(object):
    """In-memory fake. It mirrors the two-slot ABI but never claims PL work."""

    def __init__(self, transform=None, quiesce_error=None, caps=0x7):
        self.transform = transform or (lambda profile, payload: payload)
        self.quiesce_error = quiesce_error
        self.identity = {"caps": caps}
        self.next_handle = 1
        self.memory = {}
        self.alloc_calls = []
        self.calls = []
        self.allocations = {}
        self.completed_frames = 0
        self.pending = None
        self.quiesced = False
        self.closed = False

    def alloc(self, size_bytes, alignment=16, flags=0):
        handle = self.next_handle
        self.next_handle += 1
        self.alloc_calls.append((size_bytes, alignment, flags))
        arena_index = 1 if flags == 2 else 0
        self.allocations[handle] = {"bytes": size_bytes, "arena_index": arena_index,
                                    "flags": flags}
        self.arena_indices = getattr(self, "arena_indices", {})
        self.arena_indices[handle] = arena_index
        self.memory[handle] = bytearray(size_bytes)
        self.calls.append(("alloc", handle, size_bytes, flags))
        return handle

    def upload(self, handle, offset, payload):
        payload = bytes(payload)
        if (self.quiesced or offset < 0 or
                offset + len(payload) > self.allocations[handle]["bytes"]):
            raise ValueError("fake upload outside active allocation")
        self.memory[handle][offset:offset + len(payload)] = payload
        self.calls.append(("upload", handle, offset, len(payload)))

    def download(self, handle, offset, size):
        self.calls.append(("download", handle, offset, size))
        return bytes(self.memory[handle][offset:offset + size])

    def submit(self, profile, block_count, params_handle, activation_handle):
        if params_handle == activation_handle or self.quiesced:
            raise ValueError("invalid fake submit handles or state")
        spec = PROFILE_SPECS[profile]
        if (not 1 <= block_count <= spec.max_blocks or
                self.allocations[params_handle]["bytes"] != spec.block_stride_words * 16 * block_count or
                self.allocations[activation_handle]["bytes"] < 2 * spec.activation_bytes):
            raise ValueError("fake submit allocation extents mismatch")
        payload = bytes(self.memory[activation_handle][:spec.activation_bytes])
        output = bytes(self.transform(profile, payload))
        if len(output) != spec.activation_bytes:
            raise ValueError("fake transform returned wrong activation extent")
        out_offset = (block_count & 1) * spec.activation_bytes
        self.memory[activation_handle][out_offset:out_offset + len(output)] = output
        self.pending = (profile, block_count)
        self.completed_frames += 1
        self.calls.append(("submit", profile, block_count, params_handle, activation_handle))

    def wait_complete(self, profile, timeout_s):
        if self.pending is None or self.pending[0] != profile:
            raise V5NotReady("fake completion profile mismatch")
        self.pending = None
        return {"profile": profile, "completed_frames": self.completed_frames,
                "job_cycles": 0, "protocol_error": 0, "guard_error_flags": 0}

    def quiesce(self):
        self.calls.append(("quiesce",))
        if self.quiesce_error is not None:
            raise self.quiesce_error
        self.quiesced = True

    def free(self, handle):
        if not self.quiesced:
            raise V5NotReady("fake FREE requires QUIESCE")
        self.calls.append(("free", handle))
        self.allocations.pop(handle)
        self.memory.pop(handle)

    def close_device(self):
        self.calls.append(("close_device",))
        self.closed = True


def _read_v5_bundle(fixture_root):
    """Verify the canonical frozen parameter bundle and its independent scales."""
    root = os.path.abspath(os.path.join(str(fixture_root), V5_BUNDLE_DIRECTORY))
    manifest_path = os.path.join(root, "manifest.json")
    with open(manifest_path, "rb") as stream:
        raw_bundle = stream.read()
    if _sha256_bytes(raw_bundle) != V5_BUNDLE_MANIFEST_SHA256:
        raise ValueError("canonical v5 parameter bundle manifest SHA256 mismatch")
    manifest = json.loads(raw_bundle.decode("utf-8"))
    if (manifest.get("schema_version") != 1 or
            manifest.get("abi") != {"magic": "FZV5", "version": 327680, "flags": 0} or
            manifest.get("status") != "HOST_FZV5_W16_RUNTIME_PARAM_BUNDLE_NOT_PL" or
            manifest.get("checks", {}).get("board_or_pl_execution") is not False or
            manifest.get("checks", {}).get("parameter_files_have_no_headers") is not True or
            manifest.get("checks", {}).get("profiles") != ["0", "1", "2"] or
            set(manifest.get("profiles", {})) != {"0", "1", "2"}):
        raise ValueError("canonical v5 parameter bundle contract mismatch")
    scale_decl = manifest.get("scale_manifest", {})
    if (scale_decl.get("path") != "scale-manifest.json" or
            scale_decl.get("sha256") != V5_SCALE_MANIFEST_SHA256):
        raise ValueError("canonical v5 scale manifest declaration mismatch")
    scale_path = os.path.join(root, "scale-manifest.json")
    with open(scale_path, "rb") as stream:
        raw_scales = stream.read()
    if (_sha256_bytes(raw_scales) != V5_SCALE_MANIFEST_SHA256 or
            len(raw_scales) != scale_decl.get("bytes")):
        raise ValueError("canonical v5 scale manifest SHA256/size mismatch")
    scale_manifest = json.loads(raw_scales.decode("utf-8"))
    if (scale_manifest.get("schema_version") != 1 or
            scale_manifest.get("abi") != manifest.get("abi") or
            set(scale_manifest.get("profiles", {})) != {"0", "1", "2"}):
        raise ValueError("canonical v5 scale manifest ABI/profile contract mismatch")

    contracts = {}
    expected_profile_names = {0: "network2", 1: "network4", 2: "network0"}
    for profile, spec in PROFILE_SPECS.items():
        key = str(profile)
        record = manifest["profiles"][key]
        if (record.get("profile") != profile or record.get("network") != expected_profile_names[profile] or
                record.get("channels") != spec.channels or record.get("width") != spec.width or
                record.get("block_count") != spec.max_blocks or
                record.get("parameter_words_per_block") != spec.block_stride_words or
                record.get("block_stride_bytes") != spec.block_stride_words * 16 or
                record.get("slot_bytes") != spec.activation_bytes):
            raise ValueError("profile %d bundle topology mismatch" % profile)
        parameter = record.get("parameter_file", {})
        file_decl = manifest.get("files", {}).get(parameter.get("path"), {})
        parameter_path = os.path.abspath(os.path.join(root, parameter.get("path", "")))
        if os.path.commonpath((root, parameter_path)) != root:
            raise ValueError("profile %d parameter path escapes bundle" % profile)
        with open(parameter_path, "rb") as stream:
            payload = stream.read()
        if (parameter.get("bytes") != spec.parameter_bytes or
                file_decl.get("bytes") != spec.parameter_bytes or
                len(payload) != spec.parameter_bytes or
                parameter.get("sha256") != file_decl.get("sha256") or
                _sha256_bytes(payload) != parameter.get("sha256")):
            raise ValueError("profile %d parameter file SHA/size mismatch" % profile)
        sources = record.get("block_parameter_sources", [])
        scale_blocks = scale_manifest["profiles"][key].get("per_block", [])
        stride = spec.block_stride_words * 16
        if len(sources) != spec.max_blocks or len(scale_blocks) != spec.max_blocks:
            raise ValueError("profile %d block/scale manifest incomplete" % profile)
        input_scale = None
        previous_add = None
        for index, (source, scale_block) in enumerate(zip(sources, scale_blocks)):
            start = index * stride
            block_sha = _sha256_bytes(payload[start:start + stride])
            if (source.get("index") != index or source.get("bytes") != stride or
                    source.get("sha256") != block_sha or
                    scale_block.get("block_index") != index or
                    scale_block.get("parameter_block_sha256") != block_sha):
                raise ValueError("profile %d block %d parameter/scale SHA binding mismatch" %
                                 (profile, index))
            scales = scale_block.get("scales", {})
            current_input = _checked_scale(scales.get("input"),
                                           "profile %d block %d input scale" % (profile, index))
            current_add = _checked_scale(scales.get("add"),
                                         "profile %d block %d add scale" % (profile, index))
            if previous_add is not None and current_input != previous_add:
                raise ValueError("profile %d adjacent block scale discontinuity at %d" %
                                 (profile, index))
            if index == 0:
                input_scale = current_input
            previous_add = current_add
        contracts[profile] = {
            "manifest": manifest, "manifest_sha256": V5_BUNDLE_MANIFEST_SHA256,
            "scale_manifest_sha256": V5_SCALE_MANIFEST_SHA256,
            "parameter_sha256": parameter["sha256"], "params": payload,
            "input_scale": input_scale, "output_scale": previous_add,
            "parameter_path": parameter_path,
        }
    return {"manifest": manifest, "manifest_sha256": V5_BUNDLE_MANIFEST_SHA256,
            "scale_manifest": scale_manifest,
            "scale_manifest_sha256": V5_SCALE_MANIFEST_SHA256,
            "contracts": contracts}


class V5ProfileAdapter(object):
    """Loads three SHA-pinned v5 packages and owns opaque DMA leases."""

    def __init__(self, transport, fixture_root, timeout_s=30.0):
        self.transport = transport
        self.fixture_root = fixture_root
        self.timeout_s = float(timeout_s)
        if not math.isfinite(self.timeout_s) or self.timeout_s <= 0:
            raise ValueError("timeout_s must be finite and positive")
        self.fixture_bundle = _read_v5_bundle(fixture_root)
        self.contracts = self.fixture_bundle["contracts"]
        self.parameter_handles = {}
        self.activation_handles = {}
        self.handles = []
        self.closed = False
        self._busy = False
        self.setup_timings_ms = {"parameter_upload_once": 0.0}
        self.parameter_upload_receipts = []
        self.setup_identity = {
            "parameter_bundle_manifest_sha256": self.fixture_bundle["manifest_sha256"],
            "scale_manifest_sha256": self.fixture_bundle["scale_manifest_sha256"],
            "scale_bindings": {
                profile: {"input": self.contracts[profile]["input_scale"],
                          "output": self.contracts[profile]["output_scale"],
                          "parameter_sha256": self.contracts[profile]["parameter_sha256"],
                          "parameter_bundle_manifest_sha256": self.fixture_bundle["manifest_sha256"],
                          "scale_manifest_sha256": self.fixture_bundle["scale_manifest_sha256"]}
                for profile in PROFILE_ORDER}}
        try:
            for profile in PROFILE_ORDER:
                spec = PROFILE_SPECS[profile]
                if spec.slot_words * 16 != spec.activation_bytes:
                    raise ValueError("v5 slot word count does not match logical activation size")
                contract = self.contracts[profile]
                identity = getattr(transport, "identity", {})
                dual_arena = bool(identity.get("caps", 0) &
                                  getattr(LinuxIoctlV5Transport, "CAP_HIGH_ARENA", 2))
                param_flags = (LinuxIoctlV5Transport.ALLOC_HIGH_ONLY if dual_arena
                               else LinuxIoctlV5Transport.ALLOC_LOW_ONLY)
                params = transport.alloc(spec.parameter_bytes, 16, flags=param_flags)
                self.handles.append(params)
                activation = transport.alloc(2 * spec.activation_bytes, 16,
                                             flags=LinuxIoctlV5Transport.ALLOC_LOW_ONLY)
                self.handles.append(activation)
                if params == activation:
                    raise V5NotReady("driver reused one handle for params and activations")
                self.parameter_handles[profile] = params
                self.activation_handles[profile] = activation
                started = time.perf_counter()
                transport.upload(params, 0, contract["params"])
                self.setup_timings_ms["parameter_upload_once"] += (time.perf_counter() - started) * 1000.0
                self.parameter_upload_receipts.append({
                    "profile": profile, "manifest_sha256": contract["manifest_sha256"],
                    "scale_manifest_sha256": contract["scale_manifest_sha256"],
                    "parameter_sha256": contract["parameter_sha256"],
                    "parameter_bytes": len(contract["params"]), "upload_offset": 0,
                    "parameter_arena_index": transport.allocations.get(params, {}).get("arena_index"),
                    "activation_arena_index": transport.allocations.get(activation, {}).get("arena_index"),
                    "uploaded_once": True})
        except Exception:
            self.close()
            raise

    def run(self, profile, activation_chw, block_count=None):
        if self.closed or self._busy:
            raise V5NotReady("adapter is closed or already running")
        if profile not in PROFILE_SPECS:
            raise ValueError("unsupported v5 profile")
        spec = PROFILE_SPECS[profile]
        block_count = spec.max_blocks if block_count is None else block_count
        if block_count != spec.max_blocks:
            raise ValueError("runtime adapter uses the complete pinned parameter profile")
        self._busy = True
        try:
            timers = {}
            started = time.perf_counter()
            hcw = _chw_to_hcw(activation_chw, profile)
            timers["layout_chw_to_hcw"] = (time.perf_counter() - started) * 1000.0
            slot_bytes = spec.activation_bytes
            started = time.perf_counter()
            handle = self.activation_handles[profile]
            self.transport.upload(handle, 0, hcw.tobytes(order="C"))
            timers["activation_upload"] = (time.perf_counter() - started) * 1000.0
            started = time.perf_counter()
            self.transport.submit(profile, block_count,
                                  self.parameter_handles[profile], handle)
            completion = self.transport.wait_complete(profile, self.timeout_s)
            timers["device_submit_wait"] = (time.perf_counter() - started) * 1000.0
            started = time.perf_counter()
            out_offset = (block_count & 1) * slot_bytes
            raw = self.transport.download(handle, out_offset, slot_bytes)
            timers["activation_download"] = (time.perf_counter() - started) * 1000.0
            if len(raw) != slot_bytes:
                raise V5NotReady("v5 driver returned an incomplete activation")
            started = time.perf_counter()
            output = _hcw_to_chw(np.frombuffer(raw, dtype="<i2").reshape(
                (spec.width, spec.channels, spec.width)), profile)
            timers["layout_hcw_to_chw"] = (time.perf_counter() - started) * 1000.0
            return {"activation": output, "completion": completion, "timing_ms": timers}
        finally:
            self._busy = False

    def close(self):
        if self.closed:
            return {"quiesce_confirmed": True, "all_handles_freed": not self.handles,
                    "transport_closed": bool(getattr(self.transport, "closed", False))}
        first_error = None
        quiesced = False
        try:
            self.transport.quiesce()
            quiesced = True
        except Exception as error:
            first_error = error
        try:
            if quiesced:
                for handle in list(reversed(self.handles)):
                    try:
                        self.transport.free(handle)
                        self.handles.remove(handle)
                    except Exception as error:
                        if first_error is None:
                            first_error = error
            close_device = getattr(self.transport, "close_device", None)
            if callable(close_device):
                try:
                    close_device()
                except Exception as error:
                    if first_error is None:
                        first_error = error
        finally:
            self.closed = True
        if first_error is not None:
            raise first_error
        return {"quiesce_confirmed": True, "all_handles_freed": not self.handles,
                "transport_closed": bool(getattr(self.transport, "closed", True))}


class V5FullRuntime(object):
    """Runs the actual PS-prefix/N0/bridge1/N2/bridge3/N4/suffix order."""

    def __init__(self, adapter, stem_prefix, network1_bridge, network3_bridge, suffix):
        self.adapter = adapter
        self.stem_prefix = stem_prefix
        self.network1_bridge = network1_bridge
        self.network3_bridge = network3_bridge
        self.suffix = suffix
        self.pipeline = None

    def run_frame(self, image):
        timings = {}
        started = time.perf_counter()
        n0_input = self.stem_prefix(image)
        timings["stem_prefix"] = (time.perf_counter() - started) * 1000.0

        started = time.perf_counter()
        n0_q = quantize_chw(n0_input, self.adapter.contracts[2]["input_scale"], 2, "N0 input")
        timings["n0_input_quantize"] = (time.perf_counter() - started) * 1000.0
        n0_result = self.adapter.run(2, n0_q)
        timings.update({"n0_" + k: v for k, v in n0_result["timing_ms"].items()})
        started = time.perf_counter()
        n0_out = dequantize_chw(n0_result["activation"],
                                self.adapter.contracts[2]["output_scale"], 2, "N0 output")
        timings["n0_output_dequantize"] = (time.perf_counter() - started) * 1000.0

        started = time.perf_counter()
        n2_input = self.network1_bridge(n0_out)
        timings["network1_bridge"] = (time.perf_counter() - started) * 1000.0
        started = time.perf_counter()
        n2_q = quantize_chw(n2_input, self.adapter.contracts[0]["input_scale"], 0, "N2 input")
        timings["n2_input_quantize"] = (time.perf_counter() - started) * 1000.0
        n2_result = self.adapter.run(0, n2_q)
        timings.update({"n2_" + k: v for k, v in n2_result["timing_ms"].items()})
        started = time.perf_counter()
        n2_out = dequantize_chw(n2_result["activation"],
                                self.adapter.contracts[0]["output_scale"], 0, "N2 output")
        timings["n2_output_dequantize"] = (time.perf_counter() - started) * 1000.0

        started = time.perf_counter()
        n4_input = self.network3_bridge(n2_out)
        timings["network3_se_bridge"] = (time.perf_counter() - started) * 1000.0
        started = time.perf_counter()
        n4_q = quantize_chw(n4_input, self.adapter.contracts[1]["input_scale"], 1, "N4 input")
        timings["n4_input_quantize"] = (time.perf_counter() - started) * 1000.0
        n4_result = self.adapter.run(1, n4_q)
        timings.update({"n4_" + k: v for k, v in n4_result["timing_ms"].items()})
        started = time.perf_counter()
        n4_out = dequantize_chw(n4_result["activation"],
                                self.adapter.contracts[1]["output_scale"], 1, "N4 output")
        timings["n4_output_dequantize"] = (time.perf_counter() - started) * 1000.0

        started = time.perf_counter()
        features = np.asarray(self.suffix(n4_out), dtype=np.float32)
        timings["suffix"] = (time.perf_counter() - started) * 1000.0
        if features.shape != (1, 512) or not np.all(np.isfinite(features)):
            raise ValueError("v5 suffix must return finite [1,512] FP32 features")
        timings["end_to_end_callback"] = sum(timings.values())
        return {"features": features, "timing_ms": timings,
                "driver_completions": [n0_result["completion"], n2_result["completion"],
                                       n4_result["completion"]]}

    def _prefix_stage(self, frame_id, image):
        return self.stem_prefix(image)

    def _backend_stage(self, frame_id, n0_input):
        timings = {}
        started = time.perf_counter()
        n0_q = quantize_chw(n0_input, self.adapter.contracts[2]["input_scale"], 2, "N0 input")
        timings["n0_input_quantize"] = (time.perf_counter() - started) * 1000.0
        n0 = self.adapter.run(2, n0_q)
        timings.update({"n0_" + key: value for key, value in n0["timing_ms"].items()})
        started = time.perf_counter()
        n0_float = dequantize_chw(n0["activation"],
                                  self.adapter.contracts[2]["output_scale"], 2, "N0 output")
        timings["n0_output_dequantize"] = (time.perf_counter() - started) * 1000.0
        started = time.perf_counter()
        n2_input = self.network1_bridge(n0_float)
        timings["network1_bridge"] = (time.perf_counter() - started) * 1000.0
        started = time.perf_counter()
        n2_q = quantize_chw(n2_input, self.adapter.contracts[0]["input_scale"], 0, "N2 input")
        timings["n2_input_quantize"] = (time.perf_counter() - started) * 1000.0
        n2 = self.adapter.run(0, n2_q)
        timings.update({"n2_" + key: value for key, value in n2["timing_ms"].items()})
        started = time.perf_counter()
        n2_float = dequantize_chw(n2["activation"],
                                  self.adapter.contracts[0]["output_scale"], 0, "N2 output")
        timings["n2_output_dequantize"] = (time.perf_counter() - started) * 1000.0
        started = time.perf_counter()
        n4_input = self.network3_bridge(n2_float)
        timings["network3_se_bridge"] = (time.perf_counter() - started) * 1000.0
        started = time.perf_counter()
        n4_q = quantize_chw(n4_input, self.adapter.contracts[1]["input_scale"], 1, "N4 input")
        timings["n4_input_quantize"] = (time.perf_counter() - started) * 1000.0
        n4 = self.adapter.run(1, n4_q)
        timings.update({"n4_" + key: value for key, value in n4["timing_ms"].items()})
        started = time.perf_counter()
        n4_float = dequantize_chw(n4["activation"],
                                  self.adapter.contracts[1]["output_scale"], 1, "N4 output")
        timings["n4_output_dequantize"] = (time.perf_counter() - started) * 1000.0
        return {"activation": n4_float, "timing_ms": timings,
                "driver_completions": [n0["completion"], n2["completion"], n4["completion"]]}

    def _suffix_stage(self, frame_id, backend_value):
        started = time.perf_counter()
        features = np.asarray(self.suffix(backend_value["activation"]), dtype="<f4")
        suffix_ms = (time.perf_counter() - started) * 1000.0
        if features.shape != (1, 512) or not np.isfinite(features).all():
            raise ValueError("v5 suffix must return finite [1,512] FP32 features")
        return {"features": features.reshape(512).copy(),
                "timing_ms": dict(backend_value["timing_ms"], suffix=suffix_ms),
                "driver_completions": list(backend_value["driver_completions"])}

    def run(self, items, expected_frame_ids, **pipeline_options):
        if BoundedPipeline is None:
            raise RuntimeError("bounded_pipeline module is unavailable")
        if self.pipeline is None:
            allowed = {"queue_capacity", "run_timeout_s", "cleanup_timeout_s", "max_in_flight"}
            if set(pipeline_options) - allowed:
                raise ValueError("unknown pipeline option")
            self.pipeline = BoundedPipeline(
                self._prefix_stage, self._backend_stage, self._suffix_stage,
                thread_name="cnn-ddr-v5-runtime", **pipeline_options)
        elif pipeline_options:
            raise ValueError("pipeline options are frozen after the first run")
        return self.pipeline.run(items, expected_frame_ids)


def load_v5_split_contracts(model_dir, expected_manifest_sha256):
    """Verify a generated v5 split bundle before opening ORT runners/device."""
    root = os.path.abspath(str(model_dir))
    manifest_path = os.path.join(root, "manifest.json")
    if _sha256_file(manifest_path) != expected_manifest_sha256:
        raise ValueError("v5 split manifest SHA256 mismatch")
    with open(manifest_path, "r", encoding="utf-8") as stream:
        manifest = json.load(stream)
    names = ("stem-prefix", "network1-bridge", "network3-bridge", "suffix")
    if (manifest.get("status") != "V5_FOUR_PS_SPLITS_ORIGINAL_ONNX_VALIDATED_NOT_PL" or
            manifest.get("pl_execution") is not False or
            not manifest.get("checks", {}).get("split_boundaries_max_abs_zero") or
            not manifest.get("checks", {}).get("network3_full_se_gate_chain_present") or
            set(manifest.get("models", {})) != set(names)):
        raise ValueError("v5 split bundle does not match the four-stage source contract")
    required_model_contracts = {
        "stem-prefix": ([('image', [1, 3, 256, 256])],
                        [(BOUNDARY_NAMES["n0_input"], [1, 64, 64, 64])]),
        "network1-bridge": ([("/image_encoder/model/network.0/network.0.3/Add_output_0",
                              [1, 64, 64, 64])],
                            [(BOUNDARY_NAMES["n2_input"], [1, 128, 32, 32])]),
        "network3-bridge": ([("/image_encoder/model/network.2/network.2.11/Add_output_0",
                              [1, 128, 32, 32])],
                            [(BOUNDARY_NAMES["n4_input"], [1, 256, 16, 16])]),
        "suffix": ([("/image_encoder/model/network.4/network.4.19/Add_output_0",
                     [1, 256, 16, 16])], [("features", [1, 512])]),
    }
    cases = manifest.get("cases", [])
    if not cases or any(any(check.get("max_abs") != 0.0 or check.get("exact") is not True
                            for check in case.get("boundary_checks", {}).values())
                        for case in cases):
        raise ValueError("v5 model manifest lacks exact original-boundary validation cases")
    models = {}
    for name in names:
        item = manifest["models"][name]
        path = os.path.abspath(os.path.join(root, item["path"]))
        if os.path.commonpath((root, path)) != root:
            raise ValueError("v5 split model path escapes bundle")
        if os.path.getsize(path) != item["bytes"] or _sha256_file(path) != item["sha256"]:
            raise ValueError("v5 split model %s identity mismatch" % name)
        wanted_inputs, wanted_outputs = required_model_contracts[name]
        actual_inputs = [(t.get("name"), t.get("shape")) for t in item.get("inputs", [])]
        actual_outputs = [(t.get("name"), t.get("shape")) for t in item.get("outputs", [])]
        if (actual_inputs != wanted_inputs or actual_outputs != wanted_outputs or
                any(t.get("dtype") != "<f4" for t in item.get("inputs", []) + item.get("outputs", []))):
            raise ValueError("v5 split %s tensor boundary contract mismatch" % name)
        contract = {
            direction: [dict(tensor, shape=tuple(tensor["shape"]))
                        for tensor in item[direction]]
            for direction in ("inputs", "outputs")
        }
        models[name] = {"path": path, "contract": contract, "sha256": item["sha256"]}
    return {"root": root, "manifest": manifest,
            "manifest_sha256": expected_manifest_sha256, "models": models}


class CnnDdrV5OrtRuntime(object):
    """Production wiring: four persistent C ORT clients plus the v5 transport."""

    def __init__(self, runner_path, model_dir, expected_model_manifest_sha256,
                 fixture_root, transport=None, expected_ort_version="1.16.3",
                 thread_budget=None, device_path="/dev/network5_v5",
                 expected_parameter_manifest_words=(0,) * 8, timeout_s=30.0):
        try:
            from partition_s1 import OrtPartitionClient
        except ImportError:
            from .partition_s1 import OrtPartitionClient
        self.bundle = load_v5_split_contracts(model_dir, expected_model_manifest_sha256)
        budget = dict(thread_budget or THREAD_BUDGET_PRESETS[
            "candidate_prefix2_bridge1_suffix1"])
        if (set(budget) != {"stem_prefix", "network1_bridge", "network3_bridge", "suffix"} or
                any(isinstance(value, bool) or not isinstance(value, int) or
                    not 1 <= value <= 8 for value in budget.values())):
            raise ValueError("v5 thread budget must give four counts in [1,8]")
        self.thread_budget = budget
        self.clients = {}
        self.adapter = None
        self.runtime = None
        self.cleanup_receipt = None
        try:
            for name, record in self.bundle["models"].items():
                threads = budget[name.replace("-", "_")]
                self.clients[name] = OrtPartitionClient(
                    [runner_path, "--stream", record["path"], str(threads)],
                    record["contract"], threads=threads,
                    expected_version=expected_ort_version)
            self.adapter = V5ProfileAdapter(
                transport or LinuxIoctlV5Transport(
                    device_path=device_path,
                    expected_parameter_manifest_words=expected_parameter_manifest_words),
                fixture_root, timeout_s=timeout_s)
            self.runtime = V5FullRuntime(
                self.adapter,
                lambda image: self.clients["stem-prefix"].infer([image])[0][
                    BOUNDARY_NAMES["n0_input"]],
                lambda value: self.clients["network1-bridge"].infer([value])[0][
                    BOUNDARY_NAMES["n2_input"]],
                lambda value: self.clients["network3-bridge"].infer([value])[0][
                    BOUNDARY_NAMES["n4_input"]],
                lambda value: self.clients["suffix"].infer([value])[0]["features"])
            self.setup_timings_ms = {
                "ort_runner_load": sum(float(client.header["load_ms"])
                                        for client in self.clients.values()),
                "parameter_upload_once": self.adapter.setup_timings_ms["parameter_upload_once"]}
        except Exception:
            self.close()
            raise

    def run(self, items, expected_frame_ids, **pipeline_options):
        return self.runtime.run(items, expected_frame_ids, **pipeline_options)

    def close(self):
        failure = None
        receipt = None
        if self.adapter is not None:
            try:
                receipt = self.adapter.close()
                self.cleanup_receipt = receipt
            except Exception as error:
                failure = error
            self.adapter = None
        for client in reversed(list(self.clients.values())):
            try:
                client.close()
            except Exception as error:
                if failure is None:
                    failure = error
        self.clients.clear()
        if failure is not None:
            raise failure
        return receipt


BOUNDARY_NAMES = {
    "n0_input": "/image_encoder/model/patch_embed/patch_embed.2/activation/Mul_1_output_0",
    "n2_input": "/image_encoder/model/network.1/proj/proj.1/activation/Mul_1_output_0",
    "n4_input": "/image_encoder/model/network.3/proj/proj.1/activation/Mul_1_output_0",
}


__all__ = ["PROFILE_SPECS", "PROFILE_ORDER", "LinuxIoctlV5Transport",
           "FakeV5Transport", "V5ProfileAdapter", "V5FullRuntime", "V5NotReady",
           "quantize_chw", "dequantize_chw", "IOCTL_REQUESTS", "_IDENTITY_STRUCT",
           "_identity_dict", "THREAD_BUDGET_PRESETS", "load_v5_split_contracts",
           "CnnDdrV5OrtRuntime"]
