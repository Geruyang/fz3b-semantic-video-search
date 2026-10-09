import struct
import sys
import unittest
from pathlib import Path


BOARD = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BOARD))

import cnn_shared_v7_multicore_linux as transport


class MulticoreLinuxContractTest(unittest.TestCase):
    def test_struct_sizes_match_candidate_uapi(self):
        self.assertEqual(transport.IDENTITY.size, 160)
        self.assertEqual(transport.ALLOC.size, 32)
        self.assertEqual(transport.TRANSFER.size, 32)
        self.assertEqual(transport.SUBMIT.size, 72)
        self.assertEqual(transport.STATUS.size, 64)
        self.assertEqual(struct.calcsize("<4IQ12I"), 72)

    def test_identity_decodes_runtime_core_count(self):
        values = [0] * 38
        values[0:4] = [transport.CORE_ID, transport.CORE_ABI,
                       transport.GUARD_CAPS, transport.ABI_VERSION]
        values[8] = transport.PROFILE_COUNT
        values[27] = 2
        raw = transport.IDENTITY.pack(*(values[:28] + values[28:30] +
                                        values[30:38]))
        self.assertEqual(transport.decode_identity(raw)["core_count"], 2)

    def test_status_rejects_wrong_core(self):
        raw = transport.STATUS.pack(1, *([0] * 15))
        with self.assertRaisesRegex(RuntimeError, "different core"):
            transport.decode_status(raw, 0)


if __name__ == "__main__":
    unittest.main()
