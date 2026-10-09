import os
import struct
import sys
from pathlib import Path

import numpy as np
import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dma_batch_backend import (CORE_STATUS_CORE_DONE, CORE_STATUS_DONE,
                               DMA_BATCH_IOC_GET_STATUS,
                               DMA_BATCH_IOC_QUIESCE,
                               DMA_BATCH_IOC_SET_CONFIG, DMA_BATCH_MODE_DW128,
                               DMA_BATCH_STATUS_QUIESCED, DMA_SR_IOC,
                               DmaBatchBackend, _CONFIG, _STATUS)
from dma_batch_protocol import DW128_INPUT_BYTES, DW128_OUTPUT_BYTES


class FakeDmaDevice(object):
    def __init__(self):
        self.fd = 37
        self.opened = False
        self.closed = False
        self.config = None
        self.quiesced = False
        self.status = {
            "mode": 0,
            "frame_id": 41,
            "dma_mm2s_status": 0,
            "dma_s2mm_status": 0,
            "core_status": 0,
            "core_error": 0,
            "input_bytes_seen": 0,
            "output_bytes_seen": 0,
            "s2mm_actual_bytes": 0,
            "completed_frames": 100,
            "cycles": 0,
            "flags": 0,
        }
        self.output = np.arange(128 * 32 * 32, dtype="<i4").tobytes()
        self.writes = []

    def open(self, path, flags):
        assert path == os.path.abspath("/dev/dma_batch0")
        assert flags & os.O_RDWR
        assert not self.opened
        self.opened = True
        return self.fd

    def close(self, fd):
        assert fd == self.fd
        self.closed = True

    def ioctl(self, fd, command, argument=0, mutate_flag=True):
        assert fd == self.fd
        if command == DMA_BATCH_IOC_GET_STATUS:
            keys = ("mode", "frame_id", "dma_mm2s_status",
                    "dma_s2mm_status", "core_status", "core_error",
                    "input_bytes_seen", "output_bytes_seen",
                    "s2mm_actual_bytes", "completed_frames", "cycles",
                    "flags")
            argument[:] = _STATUS.pack(*(self.status[key] for key in keys))
            return 0
        if command == DMA_BATCH_IOC_SET_CONFIG:
            self.config = _CONFIG.unpack(argument)
            return 0
        if command == DMA_BATCH_IOC_QUIESCE:
            self.quiesced = True
            self.status["flags"] |= DMA_BATCH_STATUS_QUIESCED
            return 0
        raise AssertionError("unexpected ioctl")

    def write(self, fd, payload):
        assert fd == self.fd
        assert self.config == (DMA_BATCH_MODE_DW128,
                               DW128_INPUT_BYTES, DW128_OUTPUT_BYTES)
        assert len(payload) == DW128_INPUT_BYTES
        self.writes.append(payload)
        self.status.update({
            "mode": DMA_BATCH_MODE_DW128,
            "frame_id": (self.status["frame_id"] + 1) & 0xffffffff,
            "dma_mm2s_status": DMA_SR_IOC,
            "dma_s2mm_status": DMA_SR_IOC,
            "core_status": CORE_STATUS_DONE | CORE_STATUS_CORE_DONE,
            "input_bytes_seen": DW128_INPUT_BYTES,
            "output_bytes_seen": DW128_OUTPUT_BYTES,
            "s2mm_actual_bytes": DW128_OUTPUT_BYTES,
            "completed_frames": (self.status["completed_frames"] + 1) & 0xffffffff,
            "cycles": 1234,
        })
        return len(payload)

    def read(self, fd, length):
        assert fd == self.fd
        assert length == DW128_OUTPUT_BYTES
        return self.output


def _make_backend(device):
    ticks = iter([0.000, 0.001, 0.002, 0.003, 0.004,
                  0.010, 0.011, 0.012, 0.013, 0.014])
    return DmaBatchBackend(open_fn=device.open, close_fn=device.close,
                           write_fn=device.write, read_fn=device.read,
                           ioctl_fn=device.ioctl, clock_fn=lambda: next(ticks))


def test_persistent_backend_maps_logical_frames_to_monotonic_hardware_frames():
    device = FakeDmaDevice()
    weights = np.zeros((128, 7, 7), dtype=np.int8)
    pixels = np.zeros((128, 32, 32), dtype=np.int8)
    backend = _make_backend(device)
    try:
        first = backend.run_layer(weights, pixels, logical_frame_id=7)
        second = backend.run_layer(weights, pixels, logical_frame_id=19)

        assert first["logical_frame_id"] == 7
        assert first["frame_id"] == 42
        assert first["completed_frames_before"] == 100
        assert first["completed_frames_after"] == 101
        assert second["logical_frame_id"] == 19
        assert second["frame_id"] == 43
        assert second["completed_frames_before"] == 101
        assert second["completed_frames_after"] == 102
        assert first["outputs"] == device.output
        assert first["cycles"] == 1234
        assert len(device.writes) == 2
        assert backend.last_mapping == {
            "logical_frame_id": 19, "hardware_frame_id": 43,
            "request_id": 2}
    finally:
        backend.close()
    assert device.closed


def test_rebind_uses_persistent_core_completion_and_fresh_request_frame_lifetimes():
    device = FakeDmaDevice()
    # A new driver owner starts request frame ids from zero.  The PL core's
    # completion counter is cumulative and may retain four earlier frames.
    device.status["frame_id"] = 0
    device.status["completed_frames"] = 4
    backend = _make_backend(device)
    try:
        receipt = backend.run_layer(
            np.zeros((128, 7, 7), dtype=np.int8),
            np.zeros((128, 32, 32), dtype=np.int8),
            logical_frame_id=0)
        assert receipt["frame_id"] == 1
        assert receipt["completed_frames_before"] == 4
        assert receipt["completed_frames_after"] == 5
    finally:
        backend.close()


def test_missing_dma_ioc_fails_reuse_but_allows_verified_quiesce():
    device = FakeDmaDevice()
    original_write = device.write

    def write_without_s2mm_ioc(fd, payload):
        count = original_write(fd, payload)
        device.status["dma_s2mm_status"] = 0
        return count

    device.write = write_without_s2mm_ioc
    backend = _make_backend(device)
    weights = np.zeros((128, 7, 7), dtype=np.int8)
    pixels = np.zeros((128, 32, 32), dtype=np.int8)
    with pytest.raises(RuntimeError, match="IOC"):
        backend.run_layer(weights, pixels, logical_frame_id=0)
    with pytest.raises(RuntimeError, match="failed"):
        backend.run_layer(weights, pixels, logical_frame_id=1)
    status = backend.quiesce()
    assert status["flags"] & DMA_BATCH_STATUS_QUIESCED
    assert device.quiesced
    backend.close()


def test_kernel_poison_flag_blocks_quiesce_ioctl():
    device = FakeDmaDevice()
    backend = _make_backend(device)
    device.status["flags"] = 1
    with pytest.raises(RuntimeError, match="poisoned/removing"):
        backend.quiesce()
    assert not device.quiesced
    backend.close()


def test_external_counter_change_is_rejected_before_submission():
    device = FakeDmaDevice()
    backend = _make_backend(device)
    device.status["completed_frames"] += 1
    with pytest.raises(RuntimeError, match="outside"):
        backend.run_layer(np.zeros((128, 7, 7), dtype=np.int8),
                          np.zeros((128, 32, 32), dtype=np.int8),
                          logical_frame_id=3)
    assert not device.writes
    backend.close()


def test_quiesce_is_verified_and_prevents_more_submissions():
    device = FakeDmaDevice()
    backend = _make_backend(device)
    status = backend.quiesce()
    assert status["flags"] & DMA_BATCH_STATUS_QUIESCED
    assert device.quiesced
    with pytest.raises(RuntimeError, match="quiesced"):
        backend.run_layer(np.zeros((128, 7, 7), dtype=np.int8),
                          np.zeros((128, 32, 32), dtype=np.int8))
    backend.close()
