"""Fake-ioctl tests for the Linux ABI-v6 transport (no hardware access)."""

import ctypes
import os
import struct
import sys
import threading
import unittest
import importlib.util


BOARD = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BOARD not in sys.path:
    sys.path.insert(0, BOARD)

import cnn_ddr_v6_runtime as v6


def _identity(manifest=(0,) * 8, caps=0x5, profile_count=7):
    return v6._IDENTITY_STRUCT.pack(
        v6.LinuxIoctlV6Transport.CORE_ID,
        v6.LinuxIoctlV6Transport.CORE_ABI,
        v6.LinuxIoctlV6Transport.GUARD_CAPS,
        6, caps, 40, 128, 1, profile_count,
        *v6.PROFILE_MAX_BLOCKS, *v6.PROFILE_CHANNELS, *v6.PROFILE_WIDTHS,
        *v6.PROFILE_STRIDE_WORDS, 0, 0x3ff00000, 0, *manifest)


class FakeIoctl(object):
    def __init__(self, identity=None):
        self.identity = identity or _identity()
        self.status = [0, 0, 0, 0, 0x0c10, 0, 0, 0, 0, 0, 0, 1,
                       0, 0, 0]
        self.next_handle = 10
        self.allocations = {}
        self.calls = []
        self.forced_generation_delta = None
        self.submit_enter = None
        self.submit_release = None

    def __call__(self, fd, request, raw=None, mutate=False):
        self.calls.append((request, raw))
        if request == v6.IOCTL_REQUESTS["GET_IDENTITY"]:
            raw[:] = self.identity
        elif request == v6.IOCTL_REQUESTS["GET_STATUS"]:
            raw[:] = v6._STATUS_STRUCT.pack(*self.status)
        elif request == v6.IOCTL_REQUESTS["ALLOC"]:
            size, alignment, flags, _, _, _ = v6._ALLOC_STRUCT.unpack(raw)
            handle = self.next_handle
            self.next_handle += 1
            self.allocations[handle] = bytearray(size)
            arena = 0
            raw[:] = v6._ALLOC_STRUCT.pack(size, alignment, flags, handle, arena, 0)
        elif request == v6.IOCTL_REQUESTS["FREE"]:
            handle, _ = v6._FREE_STRUCT.unpack(raw)
            self.allocations.pop(handle)
        elif request in (v6.IOCTL_REQUESTS["UPLOAD"], v6.IOCTL_REQUESTS["DOWNLOAD"]):
            handle, reserved, offset, size, ptr = v6._TRANSFER_STRUCT.unpack(raw)
            if request == v6.IOCTL_REQUESTS["UPLOAD"]:
                self.allocations[handle][offset:offset + size] = ctypes.string_at(ptr, size)
            else:
                ctypes.memmove(ptr, bytes(self.allocations[handle][offset:offset + size]), size)
        elif request == v6.IOCTL_REQUESTS["SUBMIT"]:
            profile, blocks, _, _, _, _ = v6._SUBMIT_STRUCT.unpack(raw)
            switched = bool(self.status[0] and self.status[3] != profile)
            delta = (1 if switched else 0) if self.forced_generation_delta is None \
                else self.forced_generation_delta
            self.status[11] = (self.status[11] + delta) & 0xffffffff
            self.status[0] = (self.status[0] + 1) & 0xffffffff
            self.status[3] = profile
            self.status[5:11] = [x + 1 for x in self.status[5:11]]
            self.status[13] = 25
            self.status[14] = 0
            if self.submit_enter is not None:
                self.submit_enter.set()
                if not self.submit_release.wait(1.0):
                    raise RuntimeError("fake submit release timed out")
        return 0


class LinuxIoctlV6TransportTests(unittest.TestCase):
    def setUp(self):
        self.fake = FakeIoctl()
        self.transport = v6.LinuxIoctlV6Transport(fd=7, ioctl_callable=self.fake)

    def tearDown(self):
        self.transport.close_device()

    def test_frozen_uapi_sizes_and_ioctl_encodings(self):
        self.assertEqual(v6._IDENTITY_STRUCT.size, 200)
        self.assertEqual(v6._SUBMIT_STRUCT.size, 24)
        self.assertEqual(v6._STATUS_STRUCT.size, 60)
        self.assertEqual(v6.IOCTL_REQUESTS["GET_IDENTITY"] >> 16 & 0x3fff, 200)
        self.assertEqual(v6.IOCTL_REQUESTS["SUBMIT"] >> 16 & 0x3fff, 24)
        self.assertEqual(v6.IOCTL_REQUESTS["GET_STATUS"] >> 16 & 0x3fff, 60)

    def test_identity_is_pinned_to_fzv6_and_manifest(self):
        self.assertEqual(self.transport.identity["profile_count"], 7)
        self.assertEqual(self.transport.identity["core_id"], 0x465A5636)
        self.transport.close_device()
        bad = FakeIoctl(_identity(profile_count=3))
        with self.assertRaises(v6.V6NotReady):
            v6.LinuxIoctlV6Transport(fd=8, ioctl_callable=bad)
        bad = FakeIoctl(_identity(manifest=(1,) + (0,) * 7))
        with self.assertRaises(v6.V6NotReady):
            v6.LinuxIoctlV6Transport(fd=8, ioctl_callable=bad)

    def test_submit_profiles_offsets_and_subtract_first_extents(self):
        p = self.transport.alloc(v6.PROFILE_STRIDE_WORDS[3] * 16)
        a = self.transport.alloc(1 << 20)
        self.transport.submit(3, 1, p, a, 16, 0)
        fields = v6._SUBMIT_STRUCT.unpack(self.fake.calls[-1][1])
        self.assertEqual(fields, (3, 1, p, a, 16, 0))
        with self.assertRaises(ValueError):
            self.transport.submit(3, 1, p, a, 0, 16)
        with self.assertRaises(ValueError):
            self.transport.submit(3, 1, p, a, 1 << 20, 0)
        with self.assertRaises(ValueError):
            self.transport.submit(3, 1, p, a, 0xffff0, 0)

    def test_submit_completion_carries_status_before_after_and_counters(self):
        p = self.transport.alloc(v6.PROFILE_STRIDE_WORDS[0] * 16)
        a = self.transport.alloc(2 * v6.PROFILE_SLOT_WORDS[0] * 16)
        self.transport.submit(0, 1, p, a)
        result = self.transport.wait_complete(0, 0.2)
        self.assertEqual(result["completed_frames"], 1)
        self.assertEqual(result["status_before"]["completed_frames"], 0)
        self.assertEqual(result["status_after"]["completed_frames"], 1)
        self.assertEqual(result["reset_generation"], 1)
        self.assertEqual(result["ar_total"], 1)

    def test_profile_switch_accepts_exactly_one_core_reset_and_marks_it(self):
        p3 = self.transport.alloc(v6.PROFILE_STRIDE_WORDS[3] * 16)
        a3 = self.transport.alloc(1 << 20)
        self.transport.submit(3, 1, p3, a3)
        first = self.transport.wait_complete(3, 0.2)
        self.assertFalse(first["mode_switch_reset"])
        self.assertEqual(first["reset_generation_before"], 1)
        self.assertEqual(first["reset_generation"], 1)

        p0 = self.transport.alloc(v6.PROFILE_STRIDE_WORDS[0] * 16)
        a0 = self.transport.alloc(2 * v6.PROFILE_SLOT_WORDS[0] * 16)
        self.transport.submit(0, 1, p0, a0)
        switched = self.transport.wait_complete(0, 0.2)
        self.assertTrue(switched["mode_switch_reset"])
        self.assertEqual(switched["reset_generation_before"], 1)
        self.assertEqual(switched["reset_generation"], 2)

        p0_again = self.transport.alloc(v6.PROFILE_STRIDE_WORDS[0] * 16)
        a0_again = self.transport.alloc(2 * v6.PROFILE_SLOT_WORDS[0] * 16)
        self.transport.submit(0, 1, p0_again, a0_again)
        same = self.transport.wait_complete(0, 0.2)
        self.assertFalse(same["mode_switch_reset"])
        self.assertEqual(same["reset_generation_before"], 2)
        self.assertEqual(same["reset_generation"], 2)

    def test_profile_switch_rejects_wrong_reset_generation_delta(self):
        p3 = self.transport.alloc(v6.PROFILE_STRIDE_WORDS[3] * 16)
        a3 = self.transport.alloc(1 << 20)
        self.transport.submit(3, 1, p3, a3)
        self.transport.wait_complete(3, 0.2)
        self.fake.forced_generation_delta = 2
        p0 = self.transport.alloc(v6.PROFILE_STRIDE_WORDS[0] * 16)
        a0 = self.transport.alloc(2 * v6.PROFILE_SLOT_WORDS[0] * 16)
        self.transport.submit(0, 1, p0, a0)
        with self.assertRaisesRegex(v6.V6NotReady, "reset generation"):
            self.transport.wait_complete(0, 0.2)

    def test_generation_token_accepts_only_planned_switch_during_blocking_submit(self):
        p3 = self.transport.alloc(v6.PROFILE_STRIDE_WORDS[3] * 16)
        a3 = self.transport.alloc(1 << 20)
        self.transport.submit(3, 1, p3, a3)
        self.transport.wait_complete(3, 0.2)

        p0 = self.transport.alloc(v6.PROFILE_STRIDE_WORDS[0] * 16)
        a0 = self.transport.alloc(2 * v6.PROFILE_SLOT_WORDS[0] * 16)
        self.fake.submit_enter = threading.Event()
        self.fake.submit_release = threading.Event()
        errors = []

        def submit():
            try:
                self.transport.submit(0, 1, p0, a0)
            except Exception as error:
                errors.append(error)

        thread = threading.Thread(target=submit)
        thread.start()
        self.assertTrue(self.fake.submit_enter.wait(0.2))
        self.assertEqual(self.fake.status[11], 2)
        self.assertEqual(self.transport.current_generation_token(), 1)
        self.fake.submit_release.set()
        thread.join(0.2)
        self.assertFalse(thread.is_alive())
        self.assertEqual(errors, [])
        completion = self.transport.wait_complete(0, 0.2)
        self.assertTrue(completion["mode_switch_reset"])
        self.assertEqual(completion["hardware_reset_generation"], 2)
        self.assertEqual(self.transport.current_generation_token(), 1)

    def test_generation_token_snapshot_cannot_race_completion_acceptance(self):
        p3 = self.transport.alloc(v6.PROFILE_STRIDE_WORDS[3] * 16)
        a3 = self.transport.alloc(1 << 20)
        self.transport.submit(3, 1, p3, a3)
        self.transport.wait_complete(3, 0.2)

        p0 = self.transport.alloc(v6.PROFILE_STRIDE_WORDS[0] * 16)
        a0 = self.transport.alloc(2 * v6.PROFILE_SLOT_WORDS[0] * 16)
        self.transport.submit(0, 1, p0, a0)

        original_get_status = self.transport.get_status
        snapshot_captured = threading.Event()
        release_snapshot = threading.Event()
        snapshot_gate = threading.Lock()
        block_once = [True]

        def blocked_get_status():
            status = original_get_status()
            with snapshot_gate:
                should_block = block_once[0]
                block_once[0] = False
            if should_block:
                snapshot_captured.set()
                if not release_snapshot.wait(1.0):
                    raise RuntimeError("generation snapshot release timed out")
            return status

        self.transport.get_status = blocked_get_status
        token_results = []
        token_errors = []
        completion_results = []
        completion_errors = []
        completion_done = threading.Event()

        def read_token():
            try:
                token_results.append(self.transport.current_generation_token())
            except Exception as error:
                token_errors.append(error)

        def finish_job():
            try:
                completion_results.append(self.transport.wait_complete(0, 0.5))
            except Exception as error:
                completion_errors.append(error)
            finally:
                completion_done.set()

        token_thread = threading.Thread(target=read_token)
        token_thread.start()
        self.assertTrue(snapshot_captured.wait(0.2))
        completion_thread = threading.Thread(target=finish_job)
        completion_thread.start()
        completed_while_snapshot_blocked = completion_done.wait(0.05)
        release_snapshot.set()
        token_thread.join(0.5)
        completion_thread.join(0.5)

        self.assertFalse(token_thread.is_alive())
        self.assertFalse(completion_thread.is_alive())
        self.assertFalse(completed_while_snapshot_blocked)
        self.assertEqual(token_errors, [])
        self.assertEqual(completion_errors, [])
        self.assertEqual(token_results, [1])
        self.assertEqual(completion_results[0]["hardware_reset_generation"], 2)

    @unittest.skipUnless(importlib.util.find_spec("numpy"), "NumPy is unavailable")
    def test_numpy_upload_and_download_into_keep_zero_copy_api(self):
        import numpy as np
        handle = self.transport.alloc(64)
        source = np.arange(16, dtype=np.uint32)
        self.transport.upload_array(handle, 0, source)
        output = np.empty_like(source)
        self.transport.download_into(handle, 0, output)
        np.testing.assert_array_equal(source, output)

    def test_quiesce_free_and_close_lifecycle(self):
        handle = self.transport.alloc(64)
        with self.assertRaises(v6.V6NotReady):
            self.transport.free(handle)
        self.transport.quiesce()
        self.transport.free(handle)
        self.assertNotIn(handle, self.transport.allocations)
        self.transport.close_device()
        self.assertTrue(self.transport.closed)


if __name__ == "__main__":
    unittest.main()
