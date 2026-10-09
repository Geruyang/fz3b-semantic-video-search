import errno
import threading
import unittest

from desktop_vlm.board.cnn_pipeline_v6_driver_concurrency import (
    run_n4_transfer_concurrency_probe,
)


class BlockingTransport(object):
    FLAG_RUNNING = 8

    def __init__(self):
        self.identity = {"core_id": 0x465A5636, "core_abi": 0x00060000,
                         "abi_version": 6, "profile_count": 7}
        self.memory = {1: bytearray(61057 * 16 * 20),
                       2: bytearray(2 * 8192 * 16),
                       3: bytearray(16 * 1024)}
        self.active = {1, 2}
        self.started = threading.Event()
        self.release = threading.Event()
        self.completed = 10
        self.generation = 4
        self.running = False
        self.pending = False
        self.transfer_done = False
        self.next_handle = 4

    def alloc(self, size, alignment=16, flags=0):
        handle = self.next_handle
        self.next_handle += 1
        self.memory[handle] = bytearray(size)
        return handle

    def get_status(self):
        moving = 100 if self.running else 110
        status = {"completed_frames": self.completed, "protocol_error": 0,
                "flags": self.FLAG_RUNNING if self.running else 0,
                "profile": 1, "guard_status": 0x0c10,
                "guard_acks": 0, "ar_total": moving,
                "rlast_total": moving, "aw_total": moving,
                "wlast_total": moving, "b_total": moving,
                "reset_generation": self.generation,
                "guard_error_flags": 0, "job_cycles": 25}
        if self.running and self.transfer_done:
            self.transfer_done = False
            self.release.set()
        return status

    def submit(self, profile, blocks, params, activation,
               activation_base_offset_bytes=0, input_offset_bytes=0):
        self.running = True
        self.pending = True
        self.started.set()
        self.release.wait(1.0)
        self.running = False
        self.completed += 1

    def wait_complete(self, profile, timeout_s):
        if not self.pending:
            raise RuntimeError("no pending job")
        self.pending = False
        after = self.get_status()
        before = dict(after, completed_frames=after["completed_frames"] - 1)
        return dict(after, status_before=before, status_after=after)

    def upload(self, handle, offset, payload):
        if self.running and handle in self.active:
            raise OSError(errno.EBUSY, "active handle")
        self.memory[handle][offset:offset + len(payload)] = payload

    def download(self, handle, offset, size):
        if self.running and handle in self.active:
            raise OSError(errno.EBUSY, "active handle")
        result = bytes(self.memory[handle][offset:offset + size])
        # Keep the PL job alive until both unrelated transfers and both active
        # rejection probes have completed.
        if self.running and handle not in self.active:
            self.transfer_done = True
        return result


class DriverConcurrencyProbeTests(unittest.TestCase):
    def test_unrelated_transfer_overlaps_one_full_n4_and_active_handles_are_busy(self):
        transport = BlockingTransport()
        receipt = run_n4_transfer_concurrency_probe(
            transport, params_handle=1, activation_handle=2,
            transfer_handle=3, transfer_bytes=16 * 1024, timeout_s=1.0)
        self.assertEqual(receipt["status"], "FZV6_N4_UNRELATED_TRANSFER_CONCURRENCY_PASS")
        self.assertEqual(receipt["profile"], 1)
        self.assertEqual(receipt["block_count"], 20)
        self.assertEqual(receipt["generation"], 4)
        self.assertEqual(receipt["completed_frames_delta"], 1)
        self.assertTrue(receipt["status_before_transfer"]["flags"] & 8)
        self.assertTrue(receipt["status_after_transfer"]["flags"] & 8)
        self.assertEqual(receipt["payload_sha256"], receipt["download_sha256"])
        self.assertEqual(receipt["active_transfer_rejections"], {
            "params_upload_errno": errno.EBUSY,
            "activation_download_errno": errno.EBUSY,
        })
        self.assertGreaterEqual(receipt["transfer_elapsed_ms"], 0.0)


if __name__ == "__main__":
    unittest.main()
