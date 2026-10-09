import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from axi_dot_client import (AxiDotBusError, AxiDotBusyError, AxiDotClient,
                            AxiDotIdentityError, AxiDotJobError,
                            AxiDotProtocolError, AxiDotTimeoutError)


class FakeClock(object):
    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class FakeTransport(object):
    ID = 0x00
    CONTROL = 0x04
    STATUS = 0x08
    LENGTH = 0x0C
    RESULT = 0x10
    ACCEPTED = 0x14
    JOB_ID = 0x18
    BUFFER = 0x1000

    def __init__(self, behavior="normal", old_job_id=7):
        self.behavior = behavior
        self.regs = {self.ID: 0x465A4331, self.STATUS: 0,
                     self.LENGTH: 1, self.RESULT: 0, self.ACCEPTED: 0,
                     self.JOB_ID: old_job_id}
        if behavior == "stale_done":
            self.regs[self.STATUS] = 0x2
        elif behavior == "busy":
            self.regs[self.STATUS] = 0x1
        elif behavior == "status_reserved":
            self.regs[self.STATUS] = 0x8
        elif behavior == "old_job_error":
            self.regs[self.STATUS] = 0x4
        self.buffer = {}
        self.reads = []
        self.writes = []
        self.polls = 0
        self.started = False
        self.job_id_reads = 0
        self.read_error_offset = None
        self.write_error_offset = None

    @staticmethod
    def _signed8(value):
        value &= 0xff
        return value - 256 if value & 0x80 else value

    def _finish(self):
        length = self.regs[self.LENGTH]
        total = 0
        for i in range(length):
            word = self.buffer.get(i, 0)
            total += self._signed8(word) * self._signed8(word >> 8)
        self.regs[self.RESULT] = total & 0xffffffff
        self.regs[self.ACCEPTED] = length
        if self.behavior == "accepted_mismatch":
            self.regs[self.ACCEPTED] -= 1
        self.regs[self.STATUS] = 0x2

    def read32(self, offset):
        self.reads.append(offset)
        if offset == self.read_error_offset:
            raise IOError("SLVERR read")
        if offset >= self.BUFFER:
            index = (offset - self.BUFFER) // 4
            return self.buffer.get(index, 0)
        if offset == self.JOB_ID:
            self.job_id_reads += 1
            if self.behavior == "identity_before_start" and self.job_id_reads == 2:
                self.regs[self.JOB_ID] = (self.regs[self.JOB_ID] + 1) & 0xffffffff
        if offset == self.STATUS and self.started and self.regs[self.STATUS] & 0x1:
            self.polls += 1
            if self.behavior == "job_error":
                self.regs[self.STATUS] = 0x4
            elif self.behavior == "identity_change" and self.polls == 1:
                self.regs[self.JOB_ID] = (self.regs[self.JOB_ID] + 1) & 0xffffffff
            elif self.behavior == "identity_reset_during_poll" and self.polls == 1:
                self.regs[self.JOB_ID] = 0
                self.regs[self.STATUS] = 0
            elif self.behavior != "timeout":
                self._finish()
        return self.regs.get(offset, 0)

    def write32(self, offset, value, wstrb):
        self.writes.append((offset, value & 0xffffffff, wstrb))
        if offset == self.write_error_offset:
            raise IOError("SLVERR write")
        if offset == self.LENGTH:
            if self.regs[self.STATUS] & 1:
                raise IOError("SLVERR LENGTH busy")
            self.regs[self.LENGTH] = value & 0xffffffff
        elif offset >= self.BUFFER:
            if self.regs[self.STATUS] & 1:
                raise IOError("SLVERR buffer busy")
            index = (offset - self.BUFFER) // 4
            prior = self.buffer.get(index, 0)
            merged = prior
            for byte in range(4):
                if wstrb & (1 << byte):
                    mask = 0xff << (byte * 8)
                    merged = (merged & ~mask) | (value & mask)
            self.buffer[index] = merged
        elif offset == self.CONTROL:
            if self.behavior == "stale_done":
                return
            if self.regs[self.STATUS] & 1:
                raise IOError("SLVERR command busy")
            self.regs[self.JOB_ID] = (self.regs[self.JOB_ID] + 1) & 0xffffffff
            self.regs[self.RESULT] = 0
            self.regs[self.ACCEPTED] = 0
            self.regs[self.STATUS] = 1
            self.started = True
            if self.behavior == "identity_reset":
                self.regs[self.JOB_ID] = 0
                self.regs[self.STATUS] = 0


def make_client(transport, clock=None):
    return AxiDotClient(transport.read32, transport.write32,
                        clock=clock.monotonic if clock else None,
                        sleep=clock.sleep if clock else None)


def test_normal_and_negative_sum_use_signed8_and_expected_wstrb():
    transport = FakeTransport()
    result = make_client(transport).run([(3, 4), (-128, 127), (-1, -1)])
    assert result["result"] == 12 - 16256 + 1
    assert result["accepted"] == 3
    assert result["job_id"] == 8
    assert all(wstrb == 3 for offset, value, wstrb in transport.writes if offset >= transport.BUFFER)
    assert [wstrb for offset, value, wstrb in transport.writes if offset == transport.CONTROL] == [1]
    assert [wstrb for offset, value, wstrb in transport.writes if offset == transport.LENGTH] == [0xf]


@pytest.mark.parametrize("pairs,old_job_id,expected_job_id", [
    ([(127, 127)], 0, 1),
    ([(127, 127)] * 512, 0xffffffff, 0),
])
def test_length_boundaries_and_job_id_wrap(pairs, old_job_id, expected_job_id):
    transport = FakeTransport(old_job_id=old_job_id)
    result = make_client(transport).run(pairs)
    assert result["accepted"] == len(pairs)
    assert result["result"] == len(pairs) * 127 * 127
    assert result["job_id"] == expected_job_id


def test_busy_refuses_without_writes_or_clear():
    transport = FakeTransport("busy")
    with pytest.raises(AxiDotBusyError):
        make_client(transport).run([(1, 2)])
    assert transport.writes == []


def test_reserved_status_bits_are_rejected():
    transport = FakeTransport("status_reserved")
    with pytest.raises(AxiDotProtocolError, match="reserved bits"):
        make_client(transport).run([(1, 2)])
    assert transport.writes == []


def test_stale_done_is_not_accepted_as_completion():
    transport = FakeTransport("stale_done")
    with pytest.raises(AxiDotIdentityError):
        make_client(transport).run([(1, 2)])


def test_changed_job_id_before_start_does_not_submit_job():
    transport = FakeTransport("identity_before_start")
    with pytest.raises(AxiDotIdentityError):
        make_client(transport).run([(1, 2)])
    assert not any(offset == transport.CONTROL for offset, value, wstrb in transport.writes)


def test_timeout_does_not_clear_or_restart_active_job():
    transport = FakeTransport("timeout")
    clock = FakeClock()
    with pytest.raises(AxiDotTimeoutError):
        make_client(transport, clock).run([(1, 2)], timeout_s=0.01, poll_interval_s=0.004)
    assert transport.regs[transport.STATUS] & 1
    assert len([item for item in transport.writes if item[0] == transport.CONTROL]) == 1


def test_job_error_is_reported():
    transport = FakeTransport("job_error")
    with pytest.raises(AxiDotJobError):
        make_client(transport).run([(1, 2)])


def test_new_start_clears_previous_idle_job_error_atomically():
    transport = FakeTransport("old_job_error")
    result = make_client(transport).run([(2, 3)])
    assert result["result"] == 6
    assert [item for item in transport.writes if item[0] == transport.CONTROL] == [
        (transport.CONTROL, 3, 1)]


@pytest.mark.parametrize("behavior", ["identity_reset", "identity_change"])
def test_job_identity_reset_or_change_is_reported(behavior):
    with pytest.raises(AxiDotIdentityError):
        make_client(FakeTransport(behavior)).run([(1, 2)])


def test_reset_after_wrapped_job_id_is_not_misread_as_active_job():
    with pytest.raises(AxiDotIdentityError, match="idle without DONE"):
        make_client(FakeTransport("identity_reset_during_poll", old_job_id=0xffffffff)).run([(1, 2)])


def test_accepted_count_must_match_length():
    with pytest.raises(AxiDotJobError, match="ACCEPTED"):
        make_client(FakeTransport("accepted_mismatch")).run([(1, 2), (3, 4)])


@pytest.mark.parametrize("where", ["read", "write"])
def test_bus_slverr_is_reported(where):
    transport = FakeTransport()
    if where == "read":
        transport.read_error_offset = transport.ID
    else:
        transport.write_error_offset = transport.LENGTH
    with pytest.raises(AxiDotBusError, match="SLVERR"):
        make_client(transport).run([(1, 2)])


def test_device_id_mismatch_refuses_without_writes():
    transport = FakeTransport()
    transport.regs[transport.ID] ^= 1
    with pytest.raises(AxiDotProtocolError, match="device ID mismatch"):
        make_client(transport).run([(1, 2)])
    assert transport.writes == []


@pytest.mark.parametrize("pairs", [[], [(0, 0)] * 513, [(128, 0)], [(-129, 0)], [(0, 128)], [(0, -129)]])
def test_invalid_length_and_signed8_parameters_are_rejected_before_bus_writes(pairs):
    transport = FakeTransport()
    with pytest.raises(ValueError):
        make_client(transport).run(pairs)
    assert transport.reads == []
    assert transport.writes == []


@pytest.mark.parametrize("pairs", [[(1,)], [(1, 2, 3)], [(True, 1)], [(1, False)], [(1.0, 2)], [(1, 2.0)]])
def test_malformed_pair_and_noninteger_values_are_rejected_before_bus_access(pairs):
    transport = FakeTransport()
    with pytest.raises(ValueError):
        make_client(transport).run(pairs)
    assert transport.reads == []
    assert transport.writes == []


def test_abi_raw_byte_change_is_rejected_before_bus_access(tmp_path):
    source = Path(__file__).resolve().parents[2] / "hardware" / "acceleration" / "axi_dot_abi.json"
    original = source.read_bytes()
    changed = tmp_path / "changed-abi.json"
    changed.write_bytes(original + b" ")
    transport = FakeTransport()
    with pytest.raises(ValueError, match="SHA256 mismatch"):
        AxiDotClient(transport.read32, transport.write32, abi_path=str(changed))
    assert transport.reads == []
    assert transport.writes == []
