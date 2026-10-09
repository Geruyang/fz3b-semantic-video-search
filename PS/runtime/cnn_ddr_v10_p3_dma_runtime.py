"""Optional zero-copy/DMA extension for the isolated ABI A0004 P3 transport.

The extension is additive.  A driver without QUERY_TRANSFER_CAPS keeps the
proven ioctl upload/download path.  Once a direct-map ticket is issued, errors
are fail-closed and are never replayed through another backend.
"""

import errno
import mmap
import os
import struct

import cnn_ddr_v6_runtime as v6
import cnn_ddr_v10_runtime as v10
import cnn_ddr_v10_p3_dma_contract as contract


TRANSFER_ABI_VERSION = 2
LEGACY_TRANSFER_ABI_VERSION = 1
_CAPS = struct.Struct("<8I2Q")
_MAP = struct.Struct("<IIQQQ")
_SYNC = struct.Struct("<IIQQ")
_COPY = struct.Struct("<IIQQQIIII")
_CACHED_UPLOAD = struct.Struct("<IIQQQIIIIQQ")

IOCTL_QUERY_TRANSFER_CAPS = v6._ior(0x48, _CAPS.size)
IOCTL_MAP_PREP = v6._iowr(0x49, _MAP.size)
IOCTL_MAP_CANCEL = v6._ioc(0, "X", 0x4a)
IOCTL_SYNC_RANGE = v6._iow(0x4b, _SYNC.size)
IOCTL_ARENA_COPY = v6._iowr(0x4c, _COPY.size)
IOCTL_CACHED_DMA_UPLOAD = v6._iowr(0x4d, _CACHED_UPLOAD.size)

SYNC_COMMIT_HOST_WRITE = 1
SYNC_PREPARE_CPU_READ = 2

DEVICE_PATH = "/dev/network10_v10_p3_dma"
CORE_ID = 0x465A5641
CORE_ABI = 0x000A0004
GUARD_CAPS = 0x000007ff
PROFILE_MAX_BLOCKS = (12, 20, 4, 1, 0, 0, 0)
PROFILE_CHANNELS = (128, 256, 64, 64, 0, 0, 0)
PROFILE_WIDTHS = (32, 16, 64, 64, 0, 0, 0)
PROFILE_STRIDE_WORDS = (21081, 59705, 10985, 11280, 0, 0, 0)
PROFILE_SLOT_WORDS = (16384, 8192, 32768, 32768)
PROFILE_ARENA_WORDS = (36864, 20480, 69632, 69632)
PROFILE_OUTPUT_WORDS = (16384, 8192, 32768, 16384)
SCRATCH_WORDS = 4096
WORD_BYTES = 16
_SUBMIT = struct.Struct("<8I")
_QUARANTINED_CACHED_DMA_SOURCES = []


def _retain_cached_dma_source(array):
    if not any(item is array for item in _QUARANTINED_CACHED_DMA_SOURCES):
        _QUARANTINED_CACHED_DMA_SOURCES.append(array)


def profile_contract(profile, block_count):
    if (isinstance(profile, bool) or not isinstance(profile, int) or
            not 0 <= profile < 4):
        raise ValueError("DMA candidate supports only profiles 0..3")
    if (isinstance(block_count, bool) or not isinstance(block_count, int) or
            not 1 <= block_count <= PROFILE_MAX_BLOCKS[profile]):
        raise ValueError("invalid DMA candidate block count")
    slot = PROFILE_SLOT_WORDS[profile]
    arena = PROFILE_ARENA_WORDS[profile]
    if arena != 2 * slot + SCRATCH_WORDS:
        raise AssertionError("A0004 internal-FIFO arena contract is inconsistent")
    output_offset_words = 0 if profile == 3 else (block_count & 1) * slot
    return {
        "profile": profile, "block_count": block_count,
        "params_words": PROFILE_STRIDE_WORDS[profile] * block_count,
        "params_bytes": PROFILE_STRIDE_WORDS[profile] * block_count * WORD_BYTES,
        "slot_words": slot, "slot_bytes": slot * WORD_BYTES,
        "arena_words": arena, "arena_bytes": arena * WORD_BYTES,
        "input_words": slot, "input_bytes": slot * WORD_BYTES,
        "output_words": PROFILE_OUTPUT_WORDS[profile],
        "output_bytes": PROFILE_OUTPUT_WORDS[profile] * WORD_BYTES,
        "output_offset_bytes": output_offset_words * WORD_BYTES,
        "residual_offset_words": 2 * slot,
        "external_stage_ring_words": 0,
    }


def validate_submission(allocations, profile, block_count, params_handle,
                        activation_a_handle, activation_b_handle,
                        activation_a_base_offset_bytes=0,
                        activation_b_base_offset_bytes=0, reserved=0):
    result = profile_contract(profile, block_count)
    handles = (params_handle, activation_a_handle, activation_b_handle)
    if any(isinstance(handle, bool) or not isinstance(handle, int) or
           handle not in allocations or handle == 0 for handle in handles):
        raise ValueError("unknown A0004 allocation handle")
    if len(set(handles)) != 3 or reserved != 0:
        raise ValueError("A0004 handles must be distinct and reserved must be zero")
    if allocations[params_handle]["bytes"] != result["params_bytes"]:
        raise ValueError("parameter allocation does not match exact A0004 extent")
    for label, handle, base in (("A", activation_a_handle,
                                 activation_a_base_offset_bytes),
                                ("B", activation_b_handle,
                                 activation_b_base_offset_bytes)):
        if (isinstance(base, bool) or not isinstance(base, int) or
                base < 0 or base & 15):
            raise ValueError("activation %s base is invalid" % label)
        extent = allocations[handle]["bytes"]
        if base > extent or result["arena_bytes"] > extent - base:
            raise ValueError("activation %s lacks the A0004 arena extent" % label)
    result.update({
        "params_handle": params_handle,
        "activation_a_handle": activation_a_handle,
        "activation_b_handle": activation_b_handle,
        "activation_a_base_offset_bytes": activation_a_base_offset_bytes,
        "activation_b_base_offset_bytes": activation_b_base_offset_bytes,
        "input_a_offset_bytes": activation_a_base_offset_bytes,
        "input_b_offset_bytes": activation_b_base_offset_bytes,
        "output_a_offset_bytes": (activation_a_base_offset_bytes +
                                  result["output_offset_bytes"]),
        "output_b_offset_bytes": (activation_b_base_offset_bytes +
                                  result["output_offset_bytes"]),
    })
    return result


class LinuxIoctlV10P3A0004Transport(v10.LinuxIoctlV10Transport):
    DEVICE_PATH = DEVICE_PATH
    CORE_ID = CORE_ID
    CORE_ABI = CORE_ABI
    ABI_VERSION = 10

    def __init__(self, device_path=DEVICE_PATH, *,
                 expected_parameter_manifest_words=None, fd=None,
                 ioctl_callable=None):
        if device_path != self.DEVICE_PATH:
            raise ValueError("DMA candidate device must be %s" %
                             self.DEVICE_PATH)
        if expected_parameter_manifest_words is None:
            raise ValueError("A0004 combined parameter identity is required")
        v6.LinuxIoctlV6Transport.__init__(
            self, device_path=device_path,
            expected_parameter_manifest_words=expected_parameter_manifest_words,
            fd=fd, ioctl_callable=ioctl_callable)

    def _validate_identity(self):
        expected = {
            "core_id": CORE_ID, "core_abi": CORE_ABI,
            "guard_caps": GUARD_CAPS, "abi_version": 10,
            "address_bits": 40, "data_bits": 128, "profile_count": 4,
            "max_blocks": PROFILE_MAX_BLOCKS, "channels": PROFILE_CHANNELS,
            "widths": PROFILE_WIDTHS,
            "block_stride_words": PROFILE_STRIDE_WORDS,
            "reserved0": 0,
            "parameter_manifest_words": self.expected_parameter_manifest_words,
        }
        for name, wanted in expected.items():
            if self.identity.get(name) != wanted:
                raise v6.V6NotReady("A0004 driver identity %s mismatch" % name)
        known = self.CAP_LOW_ARENA | self.CAP_HIGH_ARENA | self.CAP_SIX_M_AXI
        required = self.CAP_LOW_ARENA | self.CAP_SIX_M_AXI
        if self.identity["caps"] & ~known or \
                self.identity["caps"] & required != required:
            raise v6.V6NotReady("A0004 arena/six-master capabilities mismatch")
        high = bool(self.identity["caps"] & self.CAP_HIGH_ARENA)
        if (self.identity["arena_count"] != (2 if high else 1) or
                self.identity["arena_bytes"] !=
                (self.LOW_ARENA_BYTES,
                 self.HIGH_ARENA_BYTES if high else 0)):
            raise v6.V6NotReady("A0004 arena identity mismatch")

    def submit(self, profile, block_count, params_handle,
               activation_a_handle, activation_b_handle,
               activation_a_base_offset_bytes=0,
               activation_b_base_offset_bytes=0, reserved=0):
        descriptor = validate_submission(
            self.allocations, profile, block_count, params_handle,
            activation_a_handle, activation_b_handle,
            activation_a_base_offset_bytes,
            activation_b_base_offset_bytes, reserved)
        if self.quiesced:
            raise v6.V6NotReady("SUBMIT is unavailable after QUIESCE")
        before = self._validate_status(self.get_status(), expected_flags=0)
        mode_switch = bool(before["completed_frames"] and
                           before["profile"] != profile)
        expected_generation = ((before["reset_generation"] +
                                (1 if mode_switch else 0)) & 0xffffffff)
        with self._generation_lock:
            if (self._inflight_generation is not None or
                    self._pending_completion is not None or
                    before["reset_generation"] != self._accepted_reset_generation):
                raise v6.V6NotReady("unexpected A0004 reset generation")
            self._inflight_generation = (
                before["reset_generation"], expected_generation, profile)
        raw = bytearray(_SUBMIT.pack(
            profile, block_count, params_handle, activation_a_handle,
            activation_b_handle, activation_a_base_offset_bytes,
            activation_b_base_offset_bytes, reserved))
        try:
            self._ioctl(v6._iow(0x45, _SUBMIT.size), raw)
        except Exception:
            with self._generation_lock:
                self._inflight_generation = None
            raise
        self._pending_completion = (
            before, profile, mode_switch, expected_generation)
        return descriptor


class DirectArenaMap(object):
    def __init__(self, transport, handle, offset, size, access, ticket,
                 mapping):
        self.transport = transport
        self.handle = handle
        self.offset = offset
        self.size = size
        self.access = access
        self.ticket = ticket
        self.mapping = mapping
        self.published = False
        self.closed = False

    def publish_host_write(self):
        if self.closed or self.access != contract.ACCESS_WRITE:
            raise v6.V6NotReady("only a live writable mapping can be published")
        raw = bytearray(_SYNC.pack(
            self.handle, SYNC_COMMIT_HOST_WRITE, self.offset, self.size))
        self.transport._ioctl(IOCTL_SYNC_RANGE, raw)
        self.published = True

    def close(self):
        if not self.closed:
            self.mapping.close()
            self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()


class LinuxIoctlV10P3DmaTransport(LinuxIoctlV10P3A0004Transport):
    """P3 transport with capability-gated WC maps and DDR-copy support."""

    def __init__(self, *args, **kwargs):
        self._mmap_factory = kwargs.pop("mmap_factory", mmap.mmap)
        self._cached_dma_poisoned = False
        super().__init__(*args, **kwargs)
        self.transfer_caps = self._query_transfer_caps_or_fallback()

    def _query_transfer_caps_or_fallback(self):
        raw = bytearray(_CAPS.size)
        try:
            self._ioctl(IOCTL_QUERY_TRANSFER_CAPS, raw)
        except OSError as error:
            if error.errno not in (errno.ENOTTY, errno.EOPNOTSUPP, errno.ENOSYS):
                raise
            return {
                "version": 0, "caps": 0, "alignment": 16,
                "page_size": mmap.PAGESIZE, "max_timeout_ms": 0,
                "max_map_bytes": 0, "max_copy_bytes": 0,
                "legacy_ioctl_fallback": True,
            }
        values = _CAPS.unpack(raw)
        result = {
            "version": values[0], "caps": values[1],
            "alignment": values[2], "page_size": values[3],
            "max_timeout_ms": values[4], "reserved": tuple(values[5:8]),
            "max_map_bytes": values[8], "max_copy_bytes": values[9],
            "legacy_ioctl_fallback": False,
        }
        if (result["version"] not in (LEGACY_TRANSFER_ABI_VERSION,
                                      TRANSFER_ABI_VERSION) or
                result["caps"] & ~(contract.KNOWN_CAPS if
                                    result["version"] == TRANSFER_ABI_VERSION
                                    else contract.KNOWN_CAPS_V1) or
                (result["version"] == LEGACY_TRANSFER_ABI_VERSION and
                 result["caps"] & contract.CAP_CACHED_DMA_UPLOAD) or
                result["alignment"] != contract.ALIGNMENT or
                result["page_size"] != mmap.PAGESIZE or
                any(result["reserved"]) or
                result["max_map_bytes"] <= 0 or
                result["max_copy_bytes"] <= 0 or
                result["max_timeout_ms"] <= 0):
            raise v6.V6NotReady("invalid P3 DMA/WC transfer capability record")
        return result

    def _cached_dma_capable(self):
        return bool(self.transfer_caps["version"] == TRANSFER_ABI_VERSION and
                    self.transfer_caps["caps"] &
                    contract.CAP_CACHED_DMA_UPLOAD)

    def _direct_capable(self):
        return bool(self.transfer_caps["caps"] & contract.CAP_WC_MMAP)

    def map_arena(self, handle, offset, size, access):
        if not self._direct_capable():
            raise v6.V6NotReady("direct arena mapping is unavailable")
        self._check_range(handle, offset, size)
        contract.validate_mapping(
            self.allocations[handle]["bytes"], offset, size, access,
            self.transfer_caps["page_size"])
        if size > self.transfer_caps["max_map_bytes"]:
            raise ValueError("direct mapping exceeds driver capability")
        raw = bytearray(_MAP.pack(handle, access, offset, size, 0))
        self._ioctl(IOCTL_MAP_PREP, raw)
        returned_handle, returned_access, returned_offset, returned_size, ticket = \
            _MAP.unpack(raw)
        if ((returned_handle, returned_access, returned_offset, returned_size) !=
                (handle, access, offset, size) or ticket == 0):
            raise v6.V6NotReady("driver returned an invalid one-shot map ticket")
        prot = getattr(mmap, "PROT_READ", 1)
        if access == contract.ACCESS_WRITE:
            prot |= getattr(mmap, "PROT_WRITE", 2)
        try:
            mapped = self._mmap_factory(
                self.fd, size, flags=getattr(mmap, "MAP_SHARED", 1), prot=prot,
                offset=ticket * self.transfer_caps["page_size"])
        except Exception:
            # MAP_PREP has not touched object ownership.  Cancel the one-shot
            # ticket, then fail closed; do not replay a possibly ambiguous map.
            try:
                self._ioctl(IOCTL_MAP_CANCEL)
            finally:
                raise
        return DirectArenaMap(
            self, handle, offset, size, access, ticket, mapped)

    def upload_array(self, handle, offset, array):
        import numpy as np
        if not isinstance(array, np.ndarray) or not array.flags.c_contiguous:
            raise ValueError("upload_array requires a C-contiguous NumPy array")
        size = int(array.nbytes)
        page = self.transfer_caps["page_size"]
        # This fallback is decided before MAP_PREP and therefore has no
        # ownership side effect.  It avoids exposing padding outside a logical
        # allocation through a page-granular VMA.
        if (not self._direct_capable() or offset % page or size % page):
            return super().upload_array(handle, offset, array)
        with self.map_arena(handle, offset, size, contract.ACCESS_WRITE) as direct:
            view = memoryview(direct.mapping)
            try:
                view[:size] = memoryview(array).cast("B")
            finally:
                view.release()
            direct.publish_host_write()

    def quantize_upload_into(self, handle, offset, value, scale, workspace,
                             label="V10 activation"):
        """Quantize/layout-convert directly into a mapped DDR activation.

        ``workspace`` must provide the exact
        ``V10NativeQuantWorkspace.quantize_chw_to_hcw_into`` contract.  A
        writable NumPy view is backed by the WC mapping, all views are dropped
        before commit/close, and a failed conversion is never published.  If
        direct mapping is unavailable, backend selection occurs before
        MAP_PREP and falls back to the proven ioctl upload.
        """
        import numpy as np

        quantize_into = getattr(workspace, "quantize_chw_to_hcw_into", None)
        shape = getattr(workspace, "hcw_shape", None)
        if not callable(quantize_into) or not isinstance(shape, tuple):
            raise TypeError("workspace lacks direct-target quantization support")
        import time

        size = int(np.prod(shape)) * np.dtype("<i2").itemsize
        page = self.transfer_caps["page_size"]
        if (not self._direct_capable() or offset % page or size % page):
            total_started = time.perf_counter()
            conversion_started = time.perf_counter()
            quantized = workspace.quantize_chw_to_hcw(value, scale, label)
            conversion_ms = (time.perf_counter() - conversion_started) * 1000.0
            transfer_started = time.perf_counter()
            super().upload_array(handle, offset, quantized)
            transfer_ms = (time.perf_counter() - transfer_started) * 1000.0
            return {"backend": "legacy_ioctl", "bytes": size,
                    "direct_target": False, "conversion_ms": conversion_ms,
                    "transfer_ms": transfer_ms,
                    "total_ms": (time.perf_counter() - total_started) * 1000.0}
        total_started = time.perf_counter()
        conversion_ms = None
        with self.map_arena(handle, offset, size, contract.ACCESS_WRITE) as direct:
            target = np.ndarray(shape=shape, dtype="<i2", buffer=direct.mapping)
            try:
                conversion_started = time.perf_counter()
                quantize_into(value, scale, target, label)
                conversion_ms = (time.perf_counter() - conversion_started) * 1000.0
            finally:
                # Drop the exported buffer before mmap.close(); publishing is
                # intentionally after this point and is skipped on exception.
                del target
            direct.publish_host_write()
        total_ms = (time.perf_counter() - total_started) * 1000.0
        return {"backend": "wc_mmap_direct_quantize", "bytes": size,
                "direct_target": True, "conversion_ms": conversion_ms,
                "transfer_ms": max(0.0, total_ms - conversion_ms),
                "total_ms": total_ms}

    def cached_dma_upload(self, handle, offset, array, timeout_ms=2000):
        """Synchronously DMA a cacheable, C-contiguous ndarray to an arena.

        There is deliberately no fallback.  Once the ioctl is entered, GUP or
        DMA may have acquired ownership, so an error cannot be replayed safely
        through WC or the legacy upload path.
        """
        import numpy as np
        import time

        if not self._cached_dma_capable():
            raise v6.V6NotReady(
                "cached DMA upload requires transfer ABI v2 and cap bit 3")
        if self._cached_dma_poisoned:
            raise v6.V6NotReady("cached DMA transport is poisoned")
        if (not isinstance(array, np.ndarray) or
                not array.flags.c_contiguous or array.flags.writeable):
            raise ValueError("cached DMA source must be read-only C-contiguous ndarray")
        size = int(array.nbytes)
        self._check_range(handle, offset, size)
        contract.validate_cached_dma_upload(
            self.allocations[handle]["bytes"], offset, size, timeout_ms,
            self.transfer_caps["caps"], self.transfer_caps["version"])
        pointer = int(array.__array_interface__["data"][0])
        if pointer <= 0 or pointer > 0xffffffffffffffff:
            raise ValueError("cached DMA source pointer is outside the UAPI range")
        raw = bytearray(_CACHED_UPLOAD.pack(
            handle, 0, offset, size, pointer, timeout_ms,
            contract.BACKEND_NONE, 0, 0, 0, 0))
        started = time.perf_counter()
        entered_ioctl = False
        try:
            entered_ioctl = True
            self._ioctl(IOCTL_CACHED_DMA_UPLOAD, raw)
            wall_ms = (time.perf_counter() - started) * 1000.0
            values = _CACHED_UPLOAD.unpack(raw)
            if values[:6] != (handle, 0, offset, size, pointer, timeout_ms):
                raise v6.V6NotReady("driver mutated cached DMA upload inputs")
            if (values[6] != contract.BACKEND_CACHED_DMA_UPLOAD or
                    values[7] <= 0 or values[8] != 0 or values[10] != 0):
                raise v6.V6NotReady("driver returned invalid cached DMA evidence")
        except BaseException:
            if entered_ioctl:
                # errno cannot distinguish a pre-submit provider failure from
                # a terminate failure with a live bus master.  Retain the
                # malloc owner and reject all future cached-DMA submissions.
                _retain_cached_dma_source(array)
                self._cached_dma_poisoned = True
            raise
        return {
            "backend": "cached_dma", "backend_id": values[6],
            "bytes": size, "segment_count": values[7],
            "driver_dma_ns": values[9], "dma_ioctl_wall_ms": wall_ms,
            "timeout_ms": timeout_ms, "direct_target": False,
        }

    def quantize_upload_cached_dma(self, handle, offset, value, scale,
                                   workspace, label="V10 activation",
                                   timeout_ms=2000):
        """Quantize/layout-convert in cacheable RAM, then synchronously DMA."""
        import time

        locked = getattr(workspace, "locked_quantized_hcw", None)
        if not callable(locked):
            raise TypeError("workspace lacks locked cached-DMA quantization")
        total_started = time.perf_counter()
        conversion_started = time.perf_counter()
        with locked(value, scale, label) as quantized:
            conversion_ms = (time.perf_counter() - conversion_started) * 1000.0
            result = self.cached_dma_upload(
                handle, offset, quantized, timeout_ms=timeout_ms)
        result.update({
            "conversion_ms": conversion_ms,
            "total_ms": (time.perf_counter() - total_started) * 1000.0,
        })
        return result

    def download_into(self, handle, offset, array):
        import numpy as np
        if (not isinstance(array, np.ndarray) or not array.flags.c_contiguous or
                not array.flags.writeable):
            raise ValueError("download_into requires a writable C-contiguous NumPy array")
        size = int(array.nbytes)
        page = self.transfer_caps["page_size"]
        if (not self._direct_capable() or offset % page or size % page):
            return super().download_into(handle, offset, array)
        with self.map_arena(handle, offset, size, contract.ACCESS_READ) as direct:
            raw = bytearray(_SYNC.pack(
                handle, SYNC_PREPARE_CPU_READ, offset, size))
            self._ioctl(IOCTL_SYNC_RANGE, raw)
            view = memoryview(direct.mapping)
            try:
                memoryview(array).cast("B")[:] = view[:size]
            finally:
                view.release()

    def copy_arena(self, source_handle, source_offset, destination_handle,
                   destination_offset, size, timeout_ms=2000,
                   require_dmaengine=False, allow_cpu_fallback=True):
        if require_dmaengine and allow_cpu_fallback:
            raise ValueError("require_dmaengine and allow_cpu_fallback are exclusive")
        self._check_range(source_handle, source_offset, size)
        self._check_range(destination_handle, destination_offset, size)
        flags = ((contract.COPY_REQUIRE_DMAENGINE if require_dmaengine else 0) |
                 (contract.COPY_ALLOW_CPU_FALLBACK if allow_cpu_fallback else 0))
        contract.validate_copy(
            self.allocations[source_handle]["bytes"],
            self.allocations[destination_handle]["bytes"],
            source_offset, destination_offset, size, flags, timeout_ms,
            source_handle == destination_handle)
        raw = bytearray(_COPY.pack(
            source_handle, destination_handle, source_offset,
            destination_offset, size, flags, timeout_ms,
            contract.BACKEND_NONE, 0))
        self._ioctl(IOCTL_ARENA_COPY, raw)
        values = _COPY.unpack(raw)
        if values[:7] != (source_handle, destination_handle, source_offset,
                          destination_offset, size, flags, timeout_ms):
            raise v6.V6NotReady("driver mutated the DDR copy request")
        if values[7] not in (contract.BACKEND_CPU_WC,
                             contract.BACKEND_DMAENGINE) or values[8] != 0:
            raise v6.V6NotReady("driver returned an invalid DDR copy backend")
        if require_dmaengine and values[7] != contract.BACKEND_DMAENGINE:
            raise v6.V6NotReady("required DMAengine copy was not used")
        return {"backend": values[7], "bytes": size, "timeout_ms": timeout_ms}


__all__ = ["LinuxIoctlV10P3DmaTransport", "LinuxIoctlV10P3A0004Transport",
           "DirectArenaMap", "profile_contract", "validate_submission",
           "TRANSFER_ABI_VERSION", "SYNC_COMMIT_HOST_WRITE",
           "LEGACY_TRANSFER_ABI_VERSION", "SYNC_PREPARE_CPU_READ",
           "IOCTL_CACHED_DMA_UPLOAD"]
