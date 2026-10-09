"""Fail-closed host model for the optional A0003 P3 DMA/WC transport.

This module contains no hardware access.  It mirrors the additive candidate
UAPI so range, ownership and backend-selection behavior can be tested before
the target Linux 4.14 module is compiled or loaded.
"""

CAP_WC_MMAP = 1 << 0
CAP_CPU_WC_COPY = 1 << 1
CAP_DMAENGINE_COPY = 1 << 2
CAP_CACHED_DMA_UPLOAD = 1 << 3
KNOWN_CAPS_V1 = CAP_WC_MMAP | CAP_CPU_WC_COPY | CAP_DMAENGINE_COPY
KNOWN_CAPS = KNOWN_CAPS_V1 | CAP_CACHED_DMA_UPLOAD

ACCESS_READ = 1
ACCESS_WRITE = 2
BACKEND_NONE = 0
BACKEND_CPU_WC = 1
BACKEND_DMAENGINE = 2
BACKEND_CACHED_DMA_UPLOAD = 3
COPY_ALLOW_CPU_FALLBACK = 1 << 0
COPY_REQUIRE_DMAENGINE = 1 << 1

ALIGNMENT = 16
PAGE_SIZE = 4096
MAX_COPY_BYTES = 32 * 1024 * 1024
MAX_TIMEOUT_MS = 30000


def validate_cached_dma_upload(extent, offset, size, timeout_ms, caps,
                               transfer_version):
    """Validate the explicit cacheable-user-memory to reserved-DDR path."""
    validate_span(extent, offset, size)
    timeout_ms = _plain_int(timeout_ms, "timeout_ms")
    caps = _plain_int(caps, "caps")
    transfer_version = _plain_int(transfer_version, "transfer_version")
    if size > MAX_COPY_BYTES:
        raise TransferContractError("cached DMA upload exceeds the bounded request size")
    if timeout_ms <= 0 or timeout_ms > MAX_TIMEOUT_MS:
        raise TransferContractError("cached DMA timeout is outside the bounded range")
    if transfer_version != 2 or not (caps & CAP_CACHED_DMA_UPLOAD):
        raise TransferContractError("cached DMA upload requires transfer ABI v2 and cap bit 3")
    if caps & ~KNOWN_CAPS:
        raise TransferContractError("unknown transfer capabilities")
    return {"offset": offset, "bytes": size, "timeout_ms": timeout_ms}


class TransferContractError(ValueError):
    pass


def _plain_int(value, name):
    if isinstance(value, bool) or not isinstance(value, int):
        raise TransferContractError("%s must be an integer" % name)
    return value


def validate_span(extent, offset, size, alignment=ALIGNMENT):
    extent = _plain_int(extent, "extent")
    offset = _plain_int(offset, "offset")
    size = _plain_int(size, "size")
    if extent <= 0 or offset < 0 or size <= 0:
        raise TransferContractError("span values must be positive and in range")
    if offset > extent or size > extent - offset:
        raise TransferContractError("span exceeds allocation extent")
    if offset % alignment or size % alignment:
        raise TransferContractError("span is not aligned")
    return offset, size


def validate_mapping(extent, offset, size, access, page_size=PAGE_SIZE):
    validate_span(extent, offset, size)
    access = _plain_int(access, "access")
    if access not in (ACCESS_READ, ACCESS_WRITE):
        raise TransferContractError("mapping access must be exactly read or write")
    if offset % page_size or size % page_size:
        raise TransferContractError("direct mappings must be page aligned")
    return {"offset": offset, "bytes": size, "access": access}


def choose_copy_backend(caps, flags, dma_map_source=True, dma_map_destination=True):
    caps = _plain_int(caps, "caps")
    flags = _plain_int(flags, "flags")
    if caps & ~KNOWN_CAPS:
        raise TransferContractError("unknown transfer capabilities")
    if flags & ~(COPY_ALLOW_CPU_FALLBACK | COPY_REQUIRE_DMAENGINE):
        raise TransferContractError("unknown copy flags")
    if flags & COPY_ALLOW_CPU_FALLBACK and flags & COPY_REQUIRE_DMAENGINE:
        raise TransferContractError("copy fallback and require-DMA are exclusive")
    dma_ready = bool(caps & CAP_DMAENGINE_COPY and
                     dma_map_source and dma_map_destination)
    if dma_ready:
        return BACKEND_DMAENGINE
    if flags & COPY_REQUIRE_DMAENGINE:
        raise TransferContractError("DMAengine is unavailable or cannot map the resource")
    if flags & COPY_ALLOW_CPU_FALLBACK and caps & CAP_CPU_WC_COPY:
        return BACKEND_CPU_WC
    raise TransferContractError("no permitted copy backend")


def _validate_copy_flags(flags):
    flags = _plain_int(flags, "flags")
    if flags & ~(COPY_ALLOW_CPU_FALLBACK | COPY_REQUIRE_DMAENGINE):
        raise TransferContractError("unknown copy flags")
    if flags & COPY_ALLOW_CPU_FALLBACK and flags & COPY_REQUIRE_DMAENGINE:
        raise TransferContractError("copy fallback and require-DMA are exclusive")
    return flags


def validate_copy(source_extent, destination_extent, source_offset,
                  destination_offset, size, flags, timeout_ms,
                  same_object=False):
    validate_span(source_extent, source_offset, size)
    validate_span(destination_extent, destination_offset, size)
    flags = _validate_copy_flags(flags)
    timeout_ms = _plain_int(timeout_ms, "timeout_ms")
    if size > MAX_COPY_BYTES:
        raise TransferContractError("copy exceeds the bounded request size")
    if timeout_ms <= 0 or timeout_ms > MAX_TIMEOUT_MS:
        raise TransferContractError("copy timeout is outside the bounded range")
    if same_object:
        source_end = source_offset + size
        destination_end = destination_offset + size
        if source_offset < destination_end and destination_offset < source_end:
            raise TransferContractError("overlapping DDR copies are forbidden")
    _validate_copy_flags(flags)


class ObjectState(object):
    """Small reference model for map/copy/job ownership."""

    def __init__(self, extent):
        self.extent = _plain_int(extent, "extent")
        if self.extent <= 0:
            raise TransferContractError("extent must be positive")
        self.job_refs = 0
        self.transfer_refs = 0
        self.map_refs = 0
        self.initialized = []

    def can_pin_job(self):
        return not (self.job_refs or self.transfer_refs or self.map_refs)

    def begin_map(self, offset, size, access):
        validate_mapping(self.extent, offset, size, access)
        if self.job_refs or self.transfer_refs or self.map_refs:
            raise TransferContractError("object already has an owner")
        if access == ACCESS_READ and not self.covers(offset, size):
            raise TransferContractError("read mapping requires initialized data")
        if access == ACCESS_WRITE:
            end = offset + size
            kept = []
            for start, stop in self.initialized:
                if stop <= offset or start >= end:
                    kept.append((start, stop))
                else:
                    if start < offset:
                        kept.append((start, offset))
                    if stop > end:
                        kept.append((end, stop))
            self.initialized = kept
        self.map_refs = 1

    def end_map(self):
        if self.map_refs != 1:
            raise TransferContractError("mapping reference imbalance")
        self.map_refs = 0

    def commit_write(self, offset, size):
        validate_span(self.extent, offset, size)
        if self.map_refs != 1:
            raise TransferContractError("write commit requires a live mapping")
        self.initialized.append((offset, offset + size))
        self.initialized.sort()

    def covers(self, offset, size):
        end = offset + size
        return any(start <= offset and end <= stop
                   for start, stop in self.initialized)


__all__ = [name for name in globals() if name.isupper()] + [
    "TransferContractError", "validate_span", "validate_mapping",
    "validate_copy", "validate_cached_dma_upload", "choose_copy_backend",
    "ObjectState"]
