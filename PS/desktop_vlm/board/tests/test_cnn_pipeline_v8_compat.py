import pathlib
import sys
import unittest


BOARD = pathlib.Path(__file__).resolve().parents[1]
if str(BOARD) not in sys.path:
    sys.path.insert(0, str(BOARD))

import cnn_ddr_v6_runtime as v6
import cnn_ddr_v8_runtime as v8
import cnn_pipeline_v8_compat as compat
from cnn_pipeline_v8_compat import _Abi6NormalFacade


def identity():
    return {
        "core_id": v8.CORE_ID,
        "core_abi": v8.CORE_ABI,
        "guard_caps": v8.GUARD_CAPS,
        "abi_version": v8.SOFTWARE_ABI,
        "caps": 7,
        "address_bits": 40,
        "data_bits": 128,
        "arena_count": 2,
        "profile_count": v8.PROFILE_COUNT,
        "max_blocks": v8.PROFILE_MAX_BLOCKS,
        "channels": v8.PROFILE_CHANNELS,
        "widths": v8.PROFILE_WIDTHS,
        "block_stride_words": v8.PROFILE_STRIDE_WORDS,
        "reserved0": 0,
        "arena_bytes": (0x3ff00000, 0x40000000),
        "parameter_manifest_words": (0,) * 8,
    }


def validator(value):
    transport = v8.LinuxIoctlV8Transport.__new__(v8.LinuxIoctlV8Transport)
    transport.identity = value
    transport.expected_parameter_manifest_words = (0,) * 8
    return transport


class V8CompatibilityTests(unittest.TestCase):
    def test_v8_identity_keeps_v6_binary_shape_but_zeroes_removed_profiles(self):
        transport = validator(identity())
        transport._validate_identity()
        self.assertEqual(len(v8.PROFILE_MAX_BLOCKS), 7)
        self.assertEqual(v8.PROFILE_MAX_BLOCKS[3:], (0, 0, 0, 0))

    def test_v8_identity_rejects_a_hidden_bridge_profile(self):
        value = identity()
        value["max_blocks"] = (12, 20, 4, 1, 0, 0, 0)
        with self.assertRaisesRegex(v6.V6NotReady, "max_blocks"):
            validator(value)._validate_identity()

    def test_facade_preserves_physical_evidence_and_normalizes_backend_view(self):
        class Physical(object):
            pass
        physical = Physical()
        physical.identity = identity()
        facade = _Abi6NormalFacade(physical)
        self.assertEqual(facade.physical_identity["core_id"], v8.CORE_ID)
        self.assertEqual(facade.physical_identity["profile_count"], 3)
        self.assertEqual(facade.identity["core_id"], 0x465A5636)
        self.assertEqual(facade.identity["profile_count"], 7)
        self.assertEqual(physical.identity["profile_count"], 3)

    def test_v8_submit_rejects_bridge_before_any_ioctl(self):
        transport = v8.LinuxIoctlV8Transport.__new__(v8.LinuxIoctlV8Transport)
        with self.assertRaisesRegex(ValueError, "only normal profiles"):
            transport.submit(3, 1, 1, 2, 0, 0)
        with self.assertRaisesRegex(ValueError, "zero input offset"):
            transport.submit(2, 4, 1, 2, 0, 16)

    def test_factory_reuses_only_the_v6_normal_fallback_business_path(self):
        class Physical(object):
            pass
        class Runtime(object):
            pass
        physical = Physical()
        physical.identity = identity()
        called = {}
        original = compat.create_cnn_pipeline_v6_runtime

        def fake_create(facade, contract, expected, clients, **kwargs):
            called["identity"] = dict(facade.identity)
            called["physical"] = dict(facade.physical_identity)
            called["mode"] = kwargs.get("mode")
            return Runtime()

        compat.create_cnn_pipeline_v6_runtime = fake_create
        try:
            runtime = compat.create_cnn_pipeline_v8_runtime(
                physical, {}, "a" * 64, {}, thread_mode="pipeline")
        finally:
            compat.create_cnn_pipeline_v6_runtime = original
        self.assertEqual(called["mode"], "normal_fallback")
        self.assertEqual(called["identity"]["profile_count"], 7)
        self.assertEqual(called["physical"]["profile_count"], 3)
        self.assertEqual(runtime.fzv8_identity["core_id"], v8.CORE_ID)
        self.assertEqual(runtime.execution, "board_linux_ioctl_fzv8_abi6_normal")


if __name__ == "__main__":
    unittest.main()
