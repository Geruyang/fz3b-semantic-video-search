"""Narrow guard against confusing cascade blocks with physical DMA frames."""
import re
import unittest
from pathlib import Path


SOURCE = Path(__file__).resolve().parents[1] / "network2_v3_driver_candidate.c"


class Network2V3DmaFrameContractTests(unittest.TestCase):
    def test_batch_count_is_one_for_the_single_physical_packet(self):
        source = SOURCE.read_text(encoding="utf-8")
        writes = re.findall(r"core_write\s*\(\s*d\s*,\s*CORE_BATCH_COUNT\s*,(.*?)\)\s*;",
                            source, flags=re.DOTALL)
        self.assertEqual(len(writes), 1)
        self.assertEqual(writes[0].strip(), "1")


if __name__ == "__main__":
    unittest.main()
