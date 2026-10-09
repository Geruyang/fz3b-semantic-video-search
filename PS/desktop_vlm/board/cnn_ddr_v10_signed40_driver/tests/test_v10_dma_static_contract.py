import os
import unittest


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def read(name):
    with open(os.path.join(ROOT, name), "r", encoding="utf-8") as stream:
        return stream.read()


class DmaStaticContractTests(unittest.TestCase):
    def test_dmaengine_is_real_and_fail_closed(self):
        dma = read("network10_v10_dma.c")
        for token in ("dma_request_chan(dev, \"memcpy\")",
                      "dma_map_resource", "dmaengine_prep_dma_memcpy",
                      "dmaengine_submit", "dma_async_issue_pending",
                      "wait_for_completion_timeout", "dmaengine_terminate_sync",
                      "dmaengine_synchronize"):
            self.assertIn(token, dma)
        self.assertIn("if (submitted)", dma)
        self.assertLess(dma.index("if (submitted)"),
                        dma.index("cpu_wc_copy(source"))
        self.assertIn("IS_ENABLED(CONFIG_DMA_ENGINE)", dma)
        self.assertIn("ret == -EPROBE_DEFER", dma)
        self.assertIn("device_terminate_all", dma)
        self.assertIn("device_synchronize", dma)
        self.assertIn("module_param_named(allow_global_zynqmp_memcpy", dma)
        self.assertIn("dma_request_channel(", dma)
        self.assertIn("network10_v10_zynqmp_memcpy_filter", dma)
        self.assertIn('"xlnx,zynqmp-dma-1.0"', dma)
        self.assertIn("DMA_BIT_MASK(NETWORK10_V10_REQUIRED_DMA_BITS)", dma)
        self.assertIn("network10_v10_dma_range_supported", dma)
        self.assertIn("engine->quarantined = true", dma)
        self.assertIn("if (safe_to_release)", dma)
        self.assertIn("quarantine_completion", dma)

    def test_mapping_has_ticket_refs_and_explicit_sync(self):
        driver = read("network10_v10_driver.c")
        arena = read("network10_v10_arena.c")
        for token in ("NETWORK10_V10_IOC_MAP_PREP",
                      "NETWORK10_V10_IOC_MAP_CANCEL",
                      "NETWORK10_V10_IOC_SYNC_RANGE", "remap_pfn_range",
                      "pgprot_writecombine", "VM_DONTCOPY"):
            self.assertIn(token, driver)
        self.assertIn("VM_MAYWRITE", driver)
        self.assertIn("refcount_inc(&mapping->vma_refs)", driver)
        self.assertIn("refcount_dec_and_test(&mapping->vma_refs)", driver)
        self.assertIn("object->map_refs", arena)
        self.assertIn("object->map_access", arena)
        self.assertIn("NETWORK10_V10_SYNC_COMMIT_HOST_WRITE", arena)
        self.assertIn("span_covered", arena)
        self.assertIn("range_remove(object, offset, bytes)", arena)

    def test_overlay_does_not_invent_dma_channel(self):
        overlay = read("network10_v10_signed40_overlay_candidate.dts")
        self.assertNotIn("dmas =", overlay)
        self.assertNotIn("dma-names =", overlay)
        self.assertIn('status = "disabled"', overlay)
        self.assertIn("0x000a0005", overlay)

    def test_offline_manifest_is_bound_but_not_deployable(self):
        driver = read("network10_v10_driver.c")
        self.assertIn("A0005 approved-parameter identity", driver)
        for word in ("4a32c937", "3e783ac5", "72a5d337", "4b316181",
                     "a4d52ae9", "a92ec45f", "8b13d763", "ef028690"):
            self.assertIn("0x" + word + "U", driver)

    def test_cached_upload_uapi_and_linux_414_page_dma_lifecycle(self):
        uapi = read("network10_v10_uapi.h")
        dma = read("network10_v10_dma.c")
        driver = read("network10_v10_driver.c")
        arena = read("network10_v10_arena.c")
        self.assertIn("NETWORK10_V10_TRANSFER_ABI_VERSION 2U", uapi)
        self.assertIn("NETWORK10_V10_TRANSFER_CAP_CACHED_DMA_UPLOAD (1U << 3)", uapi)
        self.assertIn("NETWORK10_V10_IOC_MAGIC, 0x4d", uapi)
        self.assertIn("sizeof(struct network10_v10_cached_upload) != 64", driver)
        self.assertIn("_IOC_SIZE(NETWORK10_V10_IOC_UPLOAD_CACHED) != 64", driver)
        for field in ("destination_handle", "destination_offset", "user_ptr",
                      "segment_count", "dma_elapsed_ns"):
            self.assertIn(field, uapi)
        for token in ("get_user_pages_fast(first_page, page_count, 0, pages)",
                      "sg_alloc_table_from_pages", "dma_map_sg(dma_dev",
                      "DMA_TO_DEVICE", "dma_unmap_sg(dma_dev",
                      "engine->quarantine_orig_nents", "VERIFY_READ",
                      "dmaengine_terminate_sync", "dmaengine_synchronize"):
            self.assertIn(token, dma)
        self.assertNotIn(".compat_ioctl", driver)
        self.assertNotIn("compat_ptr", driver)
        self.assertIn("range_remove(object, offset, bytes)", arena)
        self.assertLess(arena.index("range_remove(object, offset, bytes)",
                                   arena.index("network10_v10_arena_pin_upload")),
                        arena.index("++object->transfer_refs;",
                                    arena.index("network10_v10_arena_pin_upload")))

    def test_cached_upload_is_transactional_and_status_errors_stop_dma(self):
        dma = read("network10_v10_dma.c")
        cached_start = dma.rindex("static int dmaengine_cached_upload")
        cached = dma[cached_start:dma.index("\n#endif", cached_start)]
        self.assertIn("if (!length || dest_offset > request->bytes", cached)
        self.assertIn("length > request->bytes - dest_offset", cached)
        self.assertIn("if (time_after_eq(jiffies, deadline))", cached)
        self.assertIn("cookie = dmaengine_submit(descriptor)", cached)
        self.assertIn("if (submitted && ret)", cached)
        self.assertIn("if (stop_ret)", cached)
        self.assertIn("engine->quarantine_sgt = sgt", cached)
        self.assertIn("engine->quarantine_pages = pages", cached)
        self.assertIn("engine->quarantine_sg_mapped = true", cached)
        old_copy = dma[dma.index("static int dmaengine_copy"):dma.index("static void release_user_pages")]
        self.assertIn("dma_async_is_tx_complete", old_copy)
        self.assertLess(old_copy.index("if (ret) {\n\t\tint stop_ret"),
                        old_copy.index("dmaengine_synchronize(engine->channel)"))
        self.assertNotIn("cpu_wc_copy", cached)


if __name__ == "__main__":
    unittest.main()
