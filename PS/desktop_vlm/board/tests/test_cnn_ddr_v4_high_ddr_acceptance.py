from pathlib import Path

from desktop_vlm.board.cnn_ddr_v4_high_ddr_acceptance import (
    GRANULE_BYTES,
    execute_acceptance,
    load_block1_fixture,
)
from desktop_vlm.board.cnn_ddr_v4_runtime import LinuxIoctlV4Transport


ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "artifacts/board-debug-20261005/acceleration/host/network2-v4-fixtures-002"
MANIFEST_SHA = "e0b441a3f08fc4088b54d947991a58437c3b20e84e3fae810b997a86c588f1f5"


class TailFake(object):
    ALLOC_LOW_ONLY = LinuxIoctlV4Transport.ALLOC_LOW_ONLY
    ALLOC_HIGH_ONLY = LinuxIoctlV4Transport.ALLOC_HIGH_ONLY
    LOW_ARENA_BYTES = LinuxIoctlV4Transport.LOW_ARENA_BYTES
    HIGH_ARENA_BYTES = LinuxIoctlV4Transport.HIGH_ARENA_BYTES

    def __init__(self, expected):
        self.identity = {"arena_count": 2}
        self.allocations = {}
        self.next_handle = 1
        self.used = [0, 0]
        self.payloads = {}
        self.expected = expected
        self.completed = 0

    def alloc(self, size_bytes, alignment, flags=0):
        arena = 0 if flags == self.ALLOC_LOW_ONLY else 1
        handle = self.next_handle
        self.next_handle += 1
        footprint = ((size_bytes + GRANULE_BYTES - 1) // GRANULE_BYTES) * GRANULE_BYTES
        limit = self.LOW_ARENA_BYTES if arena == 0 else self.HIGH_ARENA_BYTES
        assert self.used[arena] + footprint <= limit
        self.allocations[handle] = {"bytes": size_bytes, "arena_index": arena,
                                    "flags": flags, "offset": self.used[arena],
                                    "footprint": footprint}
        self.used[arena] += footprint
        return handle

    def upload(self, handle, offset, payload):
        assert offset + len(payload) <= self.allocations[handle]["bytes"]
        self.payloads[(handle, offset)] = bytes(payload)

    def download(self, handle, offset, size_bytes):
        value = self.payloads[(handle, offset)]
        assert len(value) == size_bytes
        return value

    def get_status(self):
        return {"completed_frames": self.completed, "protocol_error": 0,
                "guard_error_flags": 0, "job_cycles": 123}

    def submit(self, profile, block_count, params_handle, activation_handle):
        assert (profile, block_count) == (0, 1)
        assert self.used[0] == self.LOW_ARENA_BYTES
        assert self.used[1] == self.HIGH_ARENA_BYTES
        assert self.allocations[params_handle]["arena_index"] != \
            self.allocations[activation_handle]["arena_index"]
        self.payloads[(activation_handle, 262144)] = self.expected
        self.completed += 1

    def wait_complete(self, profile, timeout_s):
        assert profile == 0 and timeout_s == 30.0
        return {"completed_frames": self.completed, "protocol_error": 0,
                "guard_error_flags": 0, "job_cycles": 123}

    def free(self, handle):
        arena = self.allocations[handle]["arena_index"]
        del self.allocations[handle]
        for key in [key for key in self.payloads if key[0] == handle]:
            del self.payloads[key]
        if not any(item["arena_index"] == arena for item in self.allocations.values()):
            self.used[arena] = 0


def test_block1_dual_orientation_plan_fills_each_arena_without_bulk_filler_io():
    fixture = load_block1_fixture(str(FIXTURE), MANIFEST_SHA)
    transport = TailFake(fixture["expected"])
    report = execute_acceptance(transport, fixture)
    assert report["status"] == "V4_REAL_KERNEL_LOW_HIGH_DDR_ACCEPTANCE_PASS"
    assert [(item["params_arena_index"], item["activation_arena_index"])
            for item in report["runs"]] == [(1, 0), (0, 1)]
    assert all(item["metadata_only_filler"] for item in report["runs"])
    assert all(item["output_sha256"] == fixture["expected_sha256"]
               for item in report["runs"])
    assert transport.allocations == {}
    assert transport.used == [0, 0]
