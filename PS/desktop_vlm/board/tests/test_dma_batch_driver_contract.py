"""Minimal source contract checks; these are not DMA functional tests."""

from pathlib import Path
import unittest


BOARD_DIR = Path(__file__).resolve().parents[1]
DRIVER = (BOARD_DIR / "dma_batch_driver.c").read_text(encoding="utf-8")
UAPI = (BOARD_DIR / "dma_batch_uapi.h").read_text(encoding="utf-8")
HELPER = (BOARD_DIR / "dma_batch_helper.c").read_text(encoding="utf-8")


class DmaBatchDriverContractTest(unittest.TestCase):
    def test_uapi_has_only_fixed_scalar_configuration_and_payload_sizes(self):
        self.assertIn("DMA_BATCH_INPUT_BYTES  137344U", UAPI)
        self.assertIn("DMA_BATCH_OUTPUT_BYTES 524288U", UAPI)
        self.assertIn("DMA_BATCH_MAX_BYTES    4194304U", UAPI)
        self.assertIn("struct dma_batch_config", UAPI)
        self.assertNotIn("dma_addr_t", UAPI)
        self.assertNotIn("__u64", UAPI)

    def test_driver_excludes_dmaengine_and_fixed_candidate_addresses(self):
        self.assertIn('"fz3b,axi-dma-batch-v1"', DRIVER)
        self.assertIn('"xlnx,axi-dma-1.00.a"', DRIVER)  # explicit rejection
        self.assertNotIn("dma_request_chan", DRIVER)
        self.assertNotIn("dmaengine_", DRIVER)
        self.assertNotIn("0xa4010000", DRIVER.lower())
        self.assertNotIn("0xa4000000", DRIVER.lower())
        self.assertIn("suppress_bind_attrs = true", DRIVER)
        self.assertIn("dma_alloc_coherent(&pdev->dev, DMA_BATCH_MAX_BYTES", DRIVER)

    def test_helper_checks_input_before_opening_device(self):
        main = HELPER[HELPER.index("int main") :]
        read_input = main.index("read_exact_file(argv[3]")
        transfer_open = main.index("open(argv[1], O_RDWR)", read_input)
        self.assertLess(read_input, transfer_open)
        self.assertIn("DMA_BATCH_IOC_SET_CONFIG", HELPER)
        self.assertIn("DMA_BATCH_IOC_GET_STATUS", HELPER)


if __name__ == "__main__":
    unittest.main()
