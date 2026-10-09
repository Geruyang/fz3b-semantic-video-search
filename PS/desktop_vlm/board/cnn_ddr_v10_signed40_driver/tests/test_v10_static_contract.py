"""Static checks for the isolated A0005 signed40 DMA/WC candidate."""

import os
import re
import struct
import unittest
from pathlib import Path


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PROJECT = Path(__file__).resolve().parents[4]


def read(name):
    with open(os.path.join(ROOT, name), "r", encoding="utf-8") as stream:
        return stream.read()


def macro(source, name):
    match = re.search(r"^#define\s+" + re.escape(name) + r"\s+([^\s/]+)",
                      source, re.MULTILINE)
    if not match:
        raise AssertionError("missing macro " + name)
    return match.group(1).rstrip("Uu")


class V10StaticContractTests(unittest.TestCase):
    def test_identity_profiles_and_submit_layout(self):
        header = read("network10_v10_uapi.h")
        self.assertEqual(int(macro(header, "NETWORK10_V10_CORE_ID"), 0), 0x465A5641)
        self.assertEqual(int(macro(header, "NETWORK10_V10_CORE_ABI"), 0), 0x000A0005)
        self.assertEqual(int(macro(header, "NETWORK10_V10_GUARD_CAPS"), 0), 0xfff)
        self.assertEqual(int(macro(header, "NETWORK10_V10_ABI_VERSION"), 0), 10)
        self.assertEqual(struct.calcsize("<8I"), 32)
        self.assertEqual(int(macro(header, "NETWORK10_V10_PROFILE_COUNT"), 0), 4)
        self.assertEqual(int(macro(header, "NETWORK10_V10_IDENTITY_PROFILE_SLOTS"), 0), 7)
        # 9 scalar words + four 7-word arrays + reserved + two u64 + eight words.
        self.assertEqual((9 + 4 * 7 + 1 + 2 * 2 + 8) * 4, 200)
        for name, value in (("CHANNELS", 64), ("WIDTH", 64), ("MAX_BLOCKS", 1),
                            ("FINAL_OUTPUT_WORDS", 16384)):
            self.assertEqual(int(macro(header, "NETWORK10_V10_PROFILE3_" + name), 0), value)
        self.assertIn("activation_a_handle, activation_b_handle", header)
        self.assertIn("activation_a_base_offset_bytes", header)
        self.assertIn("activation_b_base_offset_bytes", header)
        self.assertIn("NETWORK10_V10_CAP_SIX_M_AXI", header)
        self.assertNotIn("CAP_FOUR_M_AXI", header)
        expected = ((21081, 16384, 36864), (59705, 8192, 20480),
                    (10985, 32768, 69632), (11280, 32768, 69632))
        for profile, values in enumerate(expected):
            prefix = "NETWORK10_V10_PROFILE%d_" % profile
            actual = tuple(int(macro(header, prefix + suffix), 0) for suffix in
                           ("BLOCK_STRIDE_WORDS", "SLOT_WORDS", "ARENA_WORDS"))
            self.assertEqual(actual, values)

    def test_six_master_guard_and_hls004_offsets_are_exact(self):
        regs = read("network10_v10_regs.h")
        self.assertEqual(int(macro(regs, "V10_CORE_CAPS"), 0), 0xfff)
        self.assertEqual(int(macro(regs, "V10_ACK_PACKED_MASK"), 0), 0x3ffff)
        for name in ("PARAM1", "PARAM2", "A_READ", "A_WRITE", "B_READ", "B_WRITE"):
            self.assertIn("V10_MASTER_" + name, regs)
        self.assertIn("HLS004", regs)
        generated = (PROJECT / "b/v10h004/hls/impl/ip/drivers/"
                     "cnn_pipeline_v10_v1_0/src/xcnn_pipeline_v10_hw.h").read_text()
        pairs = {
            "PARAM1_LO": "PARAMS_PW1_DATA",
            "PARAM2_LO": "PARAMS_PW2_DATA",
            "ACT_A_R_LO": "ACTIVATION_A_RD_DATA",
            "ACT_A_W_LO": "ACTIVATION_A_WR_DATA",
            "ACT_B_R_LO": "ACTIVATION_B_RD_DATA",
            "ACT_B_W_LO": "ACTIVATION_B_WR_DATA",
            "PROFILE": "PROFILE_DATA",
            "BLOCK_COUNT": "BLOCK_COUNT_DATA",
            "PARAMS_WORDS": "PARAMS_WORDS_DATA",
            "SLOT_WORDS": "SLOT_WORDS_DATA",
            "ARENA_WORDS": "ARENA_WORDS_DATA",
            "FLAGS": "FLAGS_DATA",
        }
        for local, generated_name in pairs.items():
            generated_value = macro(
                generated, "XCNN_PIPELINE_V10_CONTROL_ADDR_" + generated_name)
            self.assertEqual(int(macro(regs, "V10_HLS_" + local), 0),
                             int(generated_value, 0))
        self.assertEqual(int(macro(regs, "V10_HLS_REQUIRED_BYTES"), 0), 0x84)

    def test_three_handle_pin_and_exact_init_rules_are_present(self):
        arena = read("network10_v10_arena.c")
        submit = read("network10_v10_submit.c")
        self.assertIn("p == a || p == b || a == b", arena)
        self.assertIn("++p->job_refs", arena)
        self.assertIn("++a->job_refs", arena)
        self.assertIn("++b->job_refs", arena)
        self.assertEqual(submit.count("network10_v10_arena_require_initialized("), 3)
        self.assertIn("plan->arena_bytes > a_object_bytes - a_base", submit)
        self.assertIn("plan->arena_bytes > b_object_bytes - b_base", submit)
        self.assertIn("network10_v10_arena_mark_initialized", submit)
        self.assertNotIn("V10_HLS_", submit)

    def test_isolated_candidate_programs_six_ports_and_preserves_lifecycle(self):
        driver = read("network10_v10_driver.c")
        makefile = read("Makefile")
        for port in ("PARAM1", "PARAM2", "ACT_A_R", "ACT_A_W",
                     "ACT_B_R", "ACT_B_W"):
            self.assertIn("V10_HLS_" + port + "_LO", driver)
        for scalar in ("PROFILE", "BLOCK_COUNT", "PARAMS_WORDS", "SLOT_WORDS",
                       "ARENA_WORDS", "FLAGS"):
            self.assertIn("V10_HLS_" + scalar, driver)
        self.assertIn("network10_v10_prepare_job", driver)
        self.assertIn("network10_v10_complete_job", driver)
        self.assertIn("network10_v10_abort_job", driver)
        self.assertIn("guard_has_all_acks", driver)
        self.assertIn("V10_ACK_PACKED_MASK", driver)
        self.assertIn("guard_read(d, V10_GUARD_CAPS) != V10_CORE_CAPS", driver)
        self.assertIn("A0005 approved-parameter identity", driver)
        self.assertNotIn("BUILD_BLOCKED", driver)
        self.assertNotIn("83df8803", driver)
        self.assertIn("identity.software_parameter_manifest_words[i]", driver)
        self.assertIn("v10_parameter_manifest_words", driver)
        self.assertIn("sizeof(struct network10_v10_submit) != 32", driver)
        self.assertIn("resource_size(resource) < V10_HLS_REQUIRED_BYTES", driver)
        self.assertIn('"fz3b,cnn-ddr-v10-signed40-candidate"', driver)
        self.assertIn('"cnn_ddr_v10_signed40_candidate"', driver)
        self.assertNotIn("NETWORK10_V10_CAP_FOUR_M_AXI", driver)
        self.assertIn("network10_v10_submit.o", makefile)

    def test_job_traffic_counters_accept_wrap_and_require_nonzero_modular_delta(self):
        driver = read("network10_v10_driver.c")
        traffic = driver[driver.index("ar_now = guard_read"):driver.index("goto complete;", driver.index("ar_now = guard_read"))]
        for name in ("ar", "rlast", "aw", "wlast", "b"):
            self.assertIn("(u32)(%s_now - %s_before) != 0U" % (name, name), traffic)
            self.assertNotIn("%s_now > %s_before" % (name, name), traffic)
        self.assertIn("per-job traffic count is contractually < 2^32", driver)
        self.assertIn("guard_counters_match(d, ar, rlast, aw, wlast, b)", driver)

        def modular_delta(before, now):
            return (now - before) & 0xffffffff

        self.assertEqual(modular_delta(0xfffffffe, 1), 3)
        self.assertEqual(modular_delta(17, 18), 1)
        self.assertEqual(modular_delta(17, 17), 0)
        self.assertNotEqual(modular_delta(0xfffffffe, 1), 0)
        self.assertNotEqual(modular_delta(17, 18), 0)
        self.assertEqual(modular_delta(17, 17), 0)

    def test_p3_submit_requires_exact_extent_and_marks_only_final_slot0_prefix(self):
        submit = read("network10_v10_submit.c")
        header = read("network10_v10_uapi.h")
        driver = read("network10_v10_driver.c")
        plan_h = read("network10_v10_submit.h")
        self.assertIn("NETWORK10_V10_PROFILE3_BLOCK_STRIDE_WORDS 11280U", header)
        self.assertIn("NETWORK10_V10_PROFILE3_SLOT_WORDS 32768U", header)
        self.assertIn("NETWORK10_V10_PROFILE3_ARENA_WORDS 69632U", header)
        self.assertIn("NETWORK10_V10_EXTERNAL_STAGE_RING_WORDS 0U", header)
        self.assertNotIn("NETWORK10_V10_Q3_STAGE_WORDS", header)
        self.assertNotIn("NETWORK10_V10_STAGE_RING_WORDS", header)
        self.assertIn("*output_words = NETWORK10_V10_PROFILE3_FINAL_OUTPUT_WORDS", submit)
        self.assertIn("submit->profile == NETWORK10_V10_PROFILE_P3 ? 0", submit)
        self.assertIn("(submit->block_count & 1U) ? plan->slot_bytes : 0", submit)
        self.assertIn("plan->params_words = stride_words * submit->block_count", submit)
        self.assertIn("params_object_bytes != plan->params_bytes", submit)
        self.assertIn("submit->activation_a_handle, a_base, plan->slot_bytes", submit)
        self.assertIn("submit->activation_b_handle, b_base, plan->slot_bytes", submit)
        self.assertIn("plan->output_bytes = (u64)output_words * 16U", submit)
        self.assertEqual(submit.count("plan->output_bytes);"), 2)
        self.assertIn("u64 output_bytes;", plan_h)
        self.assertIn('"cnn_ddr_v10_signed40_candidate"', driver)
        self.assertIn('"network10_v10_signed40"', driver)
        self.assertIn('"fz3b,cnn-ddr-v10-signed40-candidate"', driver)
        self.assertIn("NETWORK10_V10_PROFILE3_MAX_BLOCKS", driver)

    def test_transfer_uses_one_bounded_temporary_mapping_per_ioctl(self):
        arena = read("network10_v10_arena.c")
        header = read("network10_v10_arena.h")
        transfer = arena[arena.index("static int arena_transfer"):]
        pin = arena[arena.index("int network10_v10_arena_pin_job"):]
        self.assertEqual(arena.count("ioremap_wc("), 1)
        self.assertEqual(arena.count("iounmap("), 1)
        self.assertIn("NETWORK10_V10_MAX_TRANSFER_BYTES (32U * 1024U * 1024U)", header)
        self.assertLessEqual(59705 * 20 * 16, 32 * 1024 * 1024)
        self.assertIn("resolve_locked(set, handle, offset, bytes, 1, &physical)", transfer)
        self.assertIn("ioremap_wc(map_base, map_bytes)", transfer)
        self.assertIn("transfer_chunk(mapping, map_offset + done", transfer)
        self.assertNotIn("ioremap_wc", transfer[transfer.index("while (done < bytes)"):])
        self.assertIn("wmb();", transfer)
        self.assertIn("rmb();", transfer)
        self.assertLess(transfer.index("iounmap(mapping)"),
                        transfer.rindex("--object->transfer_refs"))
        self.assertIn("DT/kernel contract", arena)
        self.assertNotIn("sg_table", arena)
        self.assertIn("mutex_lock(&set->lock);", pin)
        self.assertIn("if (p == a || p == b || a == b)", pin)
        increments = [pin.index("++p->job_refs"), pin.index("++a->job_refs"),
                      pin.index("++b->job_refs")]
        self.assertEqual(increments, sorted(increments))
        self.assertLess(pin.index("if (p == a || p == b || a == b)"), increments[0])
        self.assertLess(pin.index("if (p->job_refs"), increments[0])

    def test_overlay_candidate_is_disabled_and_exact(self):
        overlay = read("network10_v10_signed40_overlay_candidate.dts")
        for value in (
                'compatible = "fz3b,cnn-ddr-v10-signed40-candidate";',
                'reg-names = "hls-control", "guard-identity";',
                'status = "disabled";',
                'fz3b,address-bits = <40>;',
                'fz3b,data-bits = <128>;',
                'fz3b,core-id = <0x465a5641>;',
                'fz3b,abi-version = <0x000a0005>;',
                'fz3b,high-ddr-path-required;',
                'fz3b,arena-low = <0x0 0x40000000 0x0 0x3ff00000>;',
                'fz3b,arena-high = <0x8 0x00000000 0x0 0x40000000>;'):
            self.assertIn(value, overlay)
        self.assertIn('0x0 0xa4000000 0x0 0x00010000', overlay)
        self.assertIn('0x0 0xa4010000 0x0 0x00010000', overlay)


if __name__ == "__main__":
    unittest.main()
