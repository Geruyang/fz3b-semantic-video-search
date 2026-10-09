import pathlib
import struct
import sys
import unittest


BOARD = pathlib.Path(__file__).resolve().parents[1]
if str(BOARD) not in sys.path:
    sys.path.insert(0, str(BOARD))

import cnn_ddr_v10_p3_runtime as p3
import cnn_ddr_v6_runtime as v6


def make_ioctl(manifest, core_abi=p3.CORE_ABI):
    values = (
        p3.CORE_ID, core_abi, p3.GUARD_CAPS, p3.SOFTWARE_ABI,
        5, 40, 128, 1, p3.PROFILE_COUNT,
        *p3.PROFILE_MAX_BLOCKS, *p3.PROFILE_CHANNELS, *p3.PROFILE_WIDTHS,
        *p3.PROFILE_STRIDE_WORDS, 0, 0x3ff00000, 0, *manifest,
    )
    identity = struct.pack("<38I2Q8I", *values)
    status = struct.pack("<15I", *([0] * 15))
    submitted = []

    def ioctl(_fd, request, raw=None, _mutate=True):
        if raw is None:
            return 0
        if len(raw) == len(identity):
            raw[:] = identity
        elif len(raw) == len(status):
            raw[:] = status
        elif len(raw) == 32:
            submitted.append(struct.unpack("<8I", raw))
        else:
            raw[:] = bytes(len(raw))
        return 0

    return ioctl, tuple(manifest), submitted


class P3RuntimeTests(unittest.TestCase):
    def test_p3_identity_tables_and_wire_size(self):
        self.assertEqual(p3.DEVICE_PATH, "/dev/network10_v10_p3")
        self.assertEqual(p3.DRIVER_NAME, "cnn_ddr_v10_p3_candidate")
        self.assertEqual(p3.COMPATIBLE, "fz3b,cnn-ddr-v10-p3-candidate")
        self.assertEqual((p3.CORE_ID, p3.CORE_ABI, p3.SOFTWARE_ABI,
                          p3.GUARD_CAPS, p3.PROFILE_COUNT),
                         (0x465A5641, 0x000A0002, 10, 0x7ff, 4))
        self.assertEqual(p3.PROFILE_MAX_BLOCKS, (12, 20, 4, 1, 0, 0, 0))
        self.assertEqual(p3.PROFILE_CHANNELS, (128, 256, 64, 64, 0, 0, 0))
        self.assertEqual(p3.PROFILE_WIDTHS, (32, 16, 64, 64, 0, 0, 0))
        self.assertEqual(p3.PROFILE_STRIDE_WORDS, (21081, 59705, 10985, 11280, 0, 0, 0))
        self.assertEqual(struct.calcsize("<38I2Q8I"), 200)
        self.assertEqual(p3.profile_contract(3, 1), {
            "profile": 3, "block_count": 1, "params_words": 11280,
            "params_bytes": 11280 * 16, "slot_words": 32768,
            "slot_bytes": 32768 * 16, "arena_words": 69632,
            "arena_bytes": 69632 * 16, "scratch_words": 4096,
            "input_words": 32768, "input_bytes": 32768 * 16,
            "output_words": 16384, "output_bytes": 16384 * 16,
            "output_offset_bytes": 0,
        })

    def test_old_v10_abi_and_wrong_device_path_are_rejected(self):
        ioctl, manifest, _ = make_ioctl(tuple(range(8)), core_abi=0x000A0001)
        with self.assertRaisesRegex(RuntimeError, "identity core_abi mismatch"):
            p3.LinuxIoctlV10P3Transport(
                fd=11, ioctl_callable=ioctl,
                expected_parameter_manifest_words=manifest)
        with self.assertRaisesRegex(ValueError, "device must be"):
            p3.LinuxIoctlV10P3Transport(
                "/dev/network10_v10", fd=11, ioctl_callable=ioctl,
                expected_parameter_manifest_words=manifest)

    def test_exact_manifest_and_profile_metadata_gate_identity(self):
        manifest = tuple(range(8))
        ioctl, _, _ = make_ioctl(manifest)
        transport = p3.LinuxIoctlV10P3Transport(
            fd=12, ioctl_callable=ioctl,
            expected_parameter_manifest_words=manifest)
        self.assertEqual(transport.identity["profile_count"], 4)
        self.assertEqual(transport.identity["block_stride_words"],
                         p3.PROFILE_STRIDE_WORDS)
        transport.close_device()

        bad_ioctl, _, _ = make_ioctl((8, 7, 6, 5, 4, 3, 2, 1))
        with self.assertRaisesRegex(RuntimeError, "manifest_words mismatch"):
            p3.LinuxIoctlV10P3Transport(
                fd=13, ioctl_callable=bad_ioctl,
                expected_parameter_manifest_words=manifest)

    def test_p2_p3_p0_can_reuse_one_pair_of_larger_arena_handles(self):
        arena_bytes = p3.PROFILE_ARENA_WORDS[3] * p3.WORD_BYTES
        allocations = {
            1: {"bytes": 10985 * 4 * 16},
            2: {"bytes": arena_bytes},
            3: {"bytes": arena_bytes},
            4: {"bytes": 11280 * 16},
            5: {"bytes": 21081 * 12 * 16},
        }
        expected = ((2, 4, 1), (3, 1, 4), (0, 12, 5))
        descriptors = [p3.validate_submission(
            allocations, profile, blocks, params, 2, 3)
            for profile, blocks, params in expected]
        self.assertEqual([d["output_offset_bytes"] for d in descriptors],
                         [0, 0, 0])
        self.assertTrue(all(d["activation_a_handle"] == 2 and
                            d["activation_b_handle"] == 3 for d in descriptors))

    def test_p3_submit_sends_abi10_32_byte_descriptor(self):
        manifest = tuple(range(8))
        ioctl, _, submitted = make_ioctl(manifest)
        transport = p3.LinuxIoctlV10P3Transport(
            fd=14, ioctl_callable=ioctl,
            expected_parameter_manifest_words=manifest)
        transport.allocations = {
            1: {"bytes": 11280 * 16},
            2: {"bytes": 69632 * 16},
            3: {"bytes": 69632 * 16},
        }
        descriptor = transport.submit(3, 1, 1, 2, 3)
        self.assertEqual(descriptor["output_bytes"], 16384 * 16)
        self.assertEqual(submitted, [(3, 1, 1, 2, 3, 0, 0, 0)])
        transport.close_device()


if __name__ == "__main__":
    unittest.main()



