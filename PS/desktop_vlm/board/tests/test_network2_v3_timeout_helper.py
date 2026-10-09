import errno
import re
import sys
import unittest
from pathlib import Path
import struct

BOARD_DIR = Path(__file__).resolve().parents[1]
if str(BOARD_DIR) not in sys.path:
    sys.path.insert(0, str(BOARD_DIR))

from network2_v3_mode0_timeout_test import (
    ACCEPTED_MODES, CORE_ABI_V3, CORE_CAPS_FZC1, CORE_CORE_DONE, CORE_DONE,
    CORE_ID_FZC1, CORE_INPUT_DONE, CORE_OUTPUT_DONE, DMA_IOC, FLAG_POISONED,
    FLAG_QUIESCED, FLAG_TEST_CONSUMED, TEST_BYTES, _verify_identity,
    run_production_fresh_check, run_recovery_cycle, STATUS_FIELDS)


TEST_MANIFEST = "0123456789abcdef" * 4


def valid_identity():
    return {"core_id": CORE_ID_FZC1, "abi_version": CORE_ABI_V3,
            "caps": CORE_CAPS_FZC1, "accepted_modes": ACCEPTED_MODES,
            "address_bits": 40, "length_bits": 23, "window_base": 0,
            "window_bytes": 1 << 30,
            "manifest_words": tuple(int(TEST_MANIFEST[i:i + 8], 16)
                                    for i in range(0, 64, 8))}


class FakeTransport(object):
    """In-process behavioral model of this helper's ioctl/read/write gates."""
    def __init__(self, first_errno=errno.ETIMEDOUT, reset_delta=1,
                 poison_after_fault=False, corrupt_retry=False, flags=0):
        self.current_identity = valid_identity()
        self.first_errno = first_errno
        self.reset_delta = reset_delta
        self.poison_after_fault = poison_after_fault
        self.corrupt_retry = corrupt_retry
        self.write_count = 0
        self.config = None
        self.pending = b""
        self.closed = False
        self.state = self._status(flags=flags)

    def _status(self, flags=0):
        return {"mode": 0, "frame_id": 0, "mm2s_status": 1, "s2mm_status": 1,
                "core_status": 0, "core_error": 0, "input_bytes_seen": 0,
                "output_bytes_seen": 0, "s2mm_actual_bytes": 0,
                "completed_frames": 27, "cycles": 0, "flags": flags,
                "reset_generation": 10}

    def identity(self):
        return self.current_identity

    def status(self):
        return dict(self.state)

    def configure(self, mode, input_bytes, output_bytes):
        if mode != 0 or input_bytes != TEST_BYTES or output_bytes != TEST_BYTES:
            raise ValueError("unexpected config")
        self.config = (mode, input_bytes, output_bytes)

    def write(self, payload):
        self.write_count += 1
        if self.write_count == 1:
            self.state["frame_id"] = 1
            self.state["reset_generation"] += self.reset_delta
            self.state["flags"] = FLAG_TEST_CONSUMED
            if self.poison_after_fault:
                self.state["flags"] |= FLAG_POISONED
            if self.first_errno is not None:
                raise OSError(self.first_errno, "simulated first-write result")
            return len(payload)
        self.state.update({"frame_id": 2, "mm2s_status": DMA_IOC,
                           "s2mm_status": DMA_IOC,
                           "core_status": CORE_DONE | CORE_CORE_DONE |
                                          CORE_INPUT_DONE | CORE_OUTPUT_DONE,
                           "core_error": 0, "input_bytes_seen": TEST_BYTES,
                           "output_bytes_seen": TEST_BYTES,
                           "s2mm_actual_bytes": TEST_BYTES,
                           "completed_frames": 28, "flags": FLAG_TEST_CONSUMED})
        self.pending = (bytes(bytearray((byte ^ 1 for byte in payload)))
                        if self.corrupt_retry else payload)
        return len(payload)

    def read_exact(self, count):
        result, self.pending = self.pending, b""
        return result if len(result) == count else result[:count]

    def quiesce(self):
        self.state["reset_generation"] += 1
        self.state["flags"] |= FLAG_QUIESCED

    def close(self):
        self.closed = True


class Network2V3TimeoutHelperTests(unittest.TestCase):
    def test_uapi_layout_and_disabled_test_overlay_are_guarded(self):
        self.assertEqual(struct.calcsize("=13I"), 52)
        self.assertEqual(struct.calcsize("=18I"), 72)
        self.assertEqual(STATUS_FIELDS[-1], "reset_generation")
        board = BOARD_DIR
        overlay = (board / "network2_v3_timeout_test_overlay.dts").read_text(encoding="utf-8")
        self.assertEqual(re.findall(r'compatible\s*=\s*"([^"]+)"', overlay),
                         ["fz3b,axi-dma-batch-v3"])
        self.assertIn('status = "disabled";', overlay)
        self.assertIn('fz3b,allow-mode0-mm2s-skip-test;', overlay)
        self.assertIn("0x00000000 0x0 0x00010000", overlay)

    def test_recovery_cycle_checks_timeout_reset_health_retry_and_quiesce(self):
        transport = FakeTransport()
        report = run_recovery_cycle(transport, TEST_MANIFEST)
        self.assertEqual(report["result"], "recovery-retry-byte-exact-quiesced")
        self.assertEqual(report["status_before"]["flags"], 0)
        self.assertEqual(report["status_after_fault"]["reset_generation"], 11)
        self.assertTrue(report["status_after_fault"]["flags"] & FLAG_TEST_CONSUMED)
        self.assertFalse(report["status_after_fault"]["flags"] & FLAG_POISONED)
        self.assertEqual(report["status_after_retry"]["completed_frames"], 28)
        self.assertTrue(report["status_after_quiesce"]["flags"] & FLAG_QUIESCED)
        self.assertEqual(report["retry_input_sha256"], report["retry_output_sha256"])

    def test_wrong_timeout_errno_stops_before_retry_or_quiesce(self):
        transport = FakeTransport(first_errno=errno.EIO)
        with self.assertRaisesRegex(RuntimeError, "expected ETIMEDOUT"):
            run_recovery_cycle(transport, TEST_MANIFEST)
        self.assertEqual(transport.write_count, 1)

    def test_no_reset_poison_or_bad_retry_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "reset-generation"):
            run_recovery_cycle(FakeTransport(reset_delta=0), TEST_MANIFEST)
        with self.assertRaisesRegex(RuntimeError, "poisoned"):
            run_recovery_cycle(FakeTransport(poison_after_fault=True), TEST_MANIFEST)
        with self.assertRaisesRegex(RuntimeError, "byte-exact"):
            run_recovery_cycle(FakeTransport(corrupt_retry=True), TEST_MANIFEST)

    def test_manifest_identity_and_fresh_production_status_are_fail_closed(self):
        _verify_identity(valid_identity(), TEST_MANIFEST)
        with self.assertRaisesRegex(RuntimeError, "GET_IDENTITY"):
            _verify_identity(valid_identity(), "f" * 64)
        report = run_production_fresh_check(FakeTransport(), TEST_MANIFEST)
        self.assertEqual(report["result"], "production-fresh-flags-zero")
        with self.assertRaisesRegex(RuntimeError, "flags=0"):
            run_production_fresh_check(FakeTransport(flags=FLAG_TEST_CONSUMED), TEST_MANIFEST)


if __name__ == "__main__":
    unittest.main()
