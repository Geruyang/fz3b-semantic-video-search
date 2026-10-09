import pathlib
import struct
import sys
import unittest


BOARD = pathlib.Path(__file__).resolve().parents[1]
if str(BOARD) not in sys.path:
    sys.path.insert(0, str(BOARD))

import cnn_ddr_v10_runtime as v10
from run_cnn_pipeline_v10_board_window import run_paired_exact_case


class V10ContractTests(unittest.TestCase):
    def allocations(self, profile=2, blocks=4, extra=0):
        c = v10.profile_contract(profile, blocks)
        return c, {
            1: {"bytes": c["params_bytes"]},
            2: {"bytes": c["arena_bytes"] + extra},
            3: {"bytes": c["arena_bytes"] + extra},
        }

    def test_profiles_match_frozen_hls_contract(self):
        self.assertEqual(v10.CORE_ID, 0x465A5641)
        self.assertEqual(v10.CORE_ABI, 0x000A0001)
        self.assertEqual(v10.SOFTWARE_ABI, 10)
        self.assertEqual(v10.GUARD_CAPS, 0x7ff)
        self.assertEqual(v10.PROFILE_STRIDE_WORDS[:3], (21081, 59705, 10985))
        self.assertEqual(v10.PROFILE_SLOT_WORDS, (16384, 8192, 32768))
        self.assertEqual(v10.PROFILE_ARENA_WORDS, (36864, 20480, 69632))
        for profile, blocks in enumerate((12, 20, 4)):
            c = v10.profile_contract(profile, blocks)
            self.assertEqual(c["arena_words"], 2 * c["slot_words"] + 4096)

    def test_submit_accepts_larger_objects_with_independent_aligned_bases(self):
        c, allocations = self.allocations(extra=64)
        d = v10.validate_submission(allocations, 2, 4, 1, 2, 3, 16, 32)
        self.assertEqual(d["params_words"], 4 * 10985)
        self.assertEqual(d["input_a_offset_bytes"], 16)
        self.assertEqual(d["input_b_offset_bytes"], 32)
        self.assertEqual(d["output_a_offset_bytes"], 16)
        self.assertEqual(d["output_b_offset_bytes"], 32)
        self.assertEqual(d["arena_bytes"], c["arena_bytes"])

    def test_submit_rejects_alias_size_alignment_and_reserved(self):
        c, allocations = self.allocations()
        bad = dict(allocations)
        bad[1] = {"bytes": c["params_bytes"] + 16}
        with self.assertRaisesRegex(ValueError, "parameter allocation"):
            v10.validate_submission(bad, 2, 4, 1, 2, 3)
        with self.assertRaisesRegex(ValueError, "must be distinct"):
            v10.validate_submission(allocations, 2, 4, 1, 2, 2)
        with self.assertRaisesRegex(ValueError, "aligned"):
            v10.validate_submission(allocations, 2, 4, 1, 2, 3, 1, 0)
        with self.assertRaisesRegex(ValueError, "reserved"):
            v10.validate_submission(allocations, 2, 4, 1, 2, 3, reserved=1)
        too_small = dict(allocations)
        too_small[3] = {"bytes": c["arena_bytes"] - 16}
        with self.assertRaisesRegex(ValueError, "arena extent"):
            v10.validate_submission(too_small, 2, 4, 1, 2, 3)

    def _identity_ioctl(self, core_id=v10.CORE_ID, core_abi=v10.CORE_ABI,
                        guard_caps=v10.GUARD_CAPS):
        manifest = tuple(range(8))
        values = (
            core_id, core_abi, guard_caps, v10.SOFTWARE_ABI,
            5, 40, 128, 1, 3,
            *v10.PROFILE_MAX_BLOCKS, *v10.PROFILE_CHANNELS,
            *v10.PROFILE_WIDTHS, *v10.PROFILE_STRIDE_WORDS,
            0, 0x3ff00000, 0, *manifest)
        identity = struct.pack("<38I2Q8I", *values)
        status = struct.pack("<15I", *([0] * 15))

        def ioctl(_fd, request, raw=None, _mutate=True):
            if raw is None:
                return 0
            payload = identity if len(raw) == len(identity) else status
            raw[:] = payload
            return 0
        return ioctl, manifest

    def test_transport_rejects_v8_identity_and_accepts_exact_fzva(self):
        ioctl, manifest = self._identity_ioctl()
        transport = v10.LinuxIoctlV10Transport(
            fd=123, ioctl_callable=ioctl,
            expected_parameter_manifest_words=manifest)
        self.assertEqual(transport.identity["guard_caps"], 0x7ff)
        transport.close_device()
        old_ioctl, manifest = self._identity_ioctl(
            core_id=0x465A5638, core_abi=0x00080000, guard_caps=0x1ff)
        with self.assertRaisesRegex(RuntimeError, "identity"):
            v10.LinuxIoctlV10Transport(
                fd=123, ioctl_callable=old_ioctl,
                expected_parameter_manifest_words=manifest)


class FakeTransport:
    def __init__(self, expected_a, expected_b):
        self.allocations = {}
        self.memory = {}
        self.next_handle = 1
        self.expected_a = expected_a
        self.expected_b = expected_b
        self.uploads = []
        self.submits = []

    def alloc(self, size):
        handle = self.next_handle
        self.next_handle += 1
        self.allocations[handle] = {"bytes": size}
        self.memory[handle] = bytearray(size)
        return handle

    def upload(self, handle, offset, payload):
        self.uploads.append((handle, offset, len(payload)))
        self.memory[handle][offset:offset + len(payload)] = payload

    def get_status(self):
        return {"completed_frames": len(self.submits)}

    def submit(self, profile, blocks, params, arena_a, arena_b,
               a_base=0, b_base=0, reserved=0):
        d = v10.validate_submission(self.allocations, profile, blocks, params,
                                    arena_a, arena_b, a_base, b_base, reserved)
        self.submits.append((params, arena_a, arena_b, d))
        at = d["output_offset_bytes"]
        self.memory[arena_a][at:at + len(self.expected_a)] = self.expected_a
        self.memory[arena_b][at:at + len(self.expected_b)] = self.expected_b
        return d

    def wait_complete(self, profile, timeout_s):
        return {"profile": profile, "timeout_s": timeout_s, "completed_pairs": 1}

    def download(self, handle, offset, size):
        return bytes(self.memory[handle][offset:offset + size])


class V10BoardRunnerTests(unittest.TestCase):
    def test_runner_uses_one_params_and_two_exact_arenas(self):
        c = v10.profile_contract(2, 3)
        params = bytes([7]) * c["params_bytes"]
        input_a = bytes([11]) * c["slot_bytes"]
        input_b = bytes([13]) * c["slot_bytes"]
        expected_a = bytes([17]) * c["slot_bytes"]
        expected_b = bytes([19]) * c["slot_bytes"]
        transport = FakeTransport(expected_a, expected_b)
        result = run_paired_exact_case(
            transport, 2, 3, params, input_a, expected_a,
            input_b, expected_b, timeout_s=5.0)
        self.assertTrue(result["byte_exact_a"] and result["byte_exact_b"])
        self.assertEqual(len(set(transport.allocations)), 3)
        sizes = [value["bytes"] for value in transport.allocations.values()]
        self.assertEqual(sizes, [c["params_bytes"], c["arena_bytes"], c["arena_bytes"]])
        self.assertEqual(transport.uploads, [
            (1, 0, c["params_bytes"]),
            (2, 0, c["slot_bytes"]),
            (3, 0, c["slot_bytes"]),
        ])
        self.assertEqual(result["descriptor"]["output_offset_bytes"], c["slot_bytes"])

    def test_runner_rejects_same_image_before_allocating(self):
        c = v10.profile_contract(2, 4)
        image = bytes([3]) * c["slot_bytes"]
        expected = bytes([5]) * c["slot_bytes"]
        transport = FakeTransport(expected, expected)
        with self.assertRaisesRegex(ValueError, "distinct"):
            run_paired_exact_case(
                transport, 2, 4, bytes(c["params_bytes"]),
                image, expected, image, expected)
        self.assertFalse(transport.allocations)


if __name__ == "__main__":
    unittest.main()
