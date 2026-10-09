import os
import sys

import pytest


BOARD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BOARD_DIR not in sys.path:
    sys.path.insert(0, BOARD_DIR)

from fzd1_mode0_sanity import (_check, _payload, CORE_STATUS_CORE_DONE,
                               CORE_STATUS_DONE, DMA_SR_IOC,
                               STATUS_POISONED)


def valid_status():
    return {"mode": 0, "frame_id": 18, "completed_frames": 34,
            "input_bytes_seen": 4097, "output_bytes_seen": 4097,
            "s2mm_actual_bytes": 4097, "dma_mm2s_status": DMA_SR_IOC,
            "dma_s2mm_status": DMA_SR_IOC,
            "core_status": CORE_STATUS_DONE | CORE_STATUS_CORE_DONE,
            "core_error": 0, "cycles": 100, "flags": 0}


def test_deterministic_payload_changes_with_seed_and_length():
    assert _payload(4097, 0x5a17c3e1) == _payload(4097, 0x5a17c3e1)
    assert _payload(4097, 0x5a17c3e1) != _payload(4097, 0x5a17c3e2)
    assert len(_payload(1, 0)) == 1


def test_status_contract_accepts_one_complete_wrapping_transaction():
    before = valid_status()
    before.update({"frame_id": 0xffffffff, "completed_frames": 0xffffffff,
                   "input_bytes_seen": 0, "output_bytes_seen": 0,
                   "s2mm_actual_bytes": 0})
    after = valid_status()
    after.update({"frame_id": 0, "completed_frames": 0})
    _check(before, after, 4097)


def test_status_contract_rejects_poison_or_stale_completion():
    before = valid_status()
    before.update({"frame_id": 17, "completed_frames": 33,
                   "input_bytes_seen": 0, "output_bytes_seen": 0,
                   "s2mm_actual_bytes": 0})
    poisoned = valid_status()
    poisoned["flags"] = STATUS_POISONED
    with pytest.raises(RuntimeError, match="unusable"):
        _check(before, poisoned, 4097)
    stale = valid_status()
    stale["completed_frames"] = before["completed_frames"]
    with pytest.raises(RuntimeError, match="completed counter"):
        _check(before, stale, 4097)
