import sys
import struct
import unittest
from pathlib import Path

import numpy as np


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))

import cnn_shared_v7_contract as contract
import cnn_shared_v7_fixtures as fixtures
import cnn_shared_v7_gelu_analysis as gelu_analysis
import cnn_shared_v7_multicore_plan as multicore_plan
import cnn_shared_v7_oracle as oracle
import cnn_shared_v7_resource_report as resource_report
import cnn_shared_v7_scheduler as scheduler
import cnn_w16_joint_oracle as full_oracle


def _small_params(seed=7):
    rng = np.random.RandomState(seed)
    channels = 2

    def layer(weight, outputs):
        return {
            "weights": np.asarray(weight, dtype="<i2"),
            "bias": np.zeros((outputs,), dtype=object),
            "multiplier": np.ones((outputs,), dtype="<i4"),
            "shift": np.zeros((outputs,), dtype="<i4"),
            "full_range_abs_bound": [0] * outputs,
        }

    identity_lut = np.arange(-32768, 32768, dtype=np.int32).astype("<i2")
    return {
        "layers": {
            "dw3": layer(rng.randint(-2, 3, (channels, 1, 3, 3)), channels),
            "dw7": layer(rng.randint(-1, 2, (channels, 1, 7, 7)), channels),
            "pw1": layer(rng.randint(-2, 3, (3 * channels, channels)), 3 * channels),
            "pw2": layer(rng.randint(-2, 3, (channels, 3 * channels)), channels),
        },
        "scale_multiplier": np.ones((channels,), dtype="<i4"),
        "scale_shift": np.zeros((channels,), dtype="<i4"),
        "residual_multiplier": np.ones((1,), dtype="<i4"),
        "residual_shift": np.zeros((1,), dtype="<i4"),
        "gelu": identity_lut,
    }


class SharedV7OfflineTests(unittest.TestCase):
 def test_stripe_geometry_uses_global_halo_and_constant_row_words(self):
    top = contract.stripe_geometry(2, 0, 4)
    middle = contract.stripe_geometry(2, 28, 4)
    bottom = contract.stripe_geometry(2, 60, 4)
    self.assertEqual(top, {
        "start_row": 0, "row_count": 4,
        "q3_start_row": 0, "q3_row_count": 7,
        "source_start_row": 0, "source_row_count": 8,
        "row_words": 512, "scratch_required_words": 3584,
    })
    self.assertEqual(middle["q3_start_row"], 25)
    self.assertEqual(middle["q3_row_count"], 10)
    self.assertEqual(middle["source_start_row"], 24)
    self.assertEqual(middle["source_row_count"], 12)
    self.assertEqual(middle["scratch_required_words"], 5120)
    self.assertEqual(bottom["q3_start_row"], 57)
    self.assertEqual(bottom["q3_row_count"], 7)
    self.assertEqual(bottom["source_start_row"], 56)
    self.assertEqual(bottom["source_row_count"], 8)


 def test_descriptor_accepts_disjoint_spans_and_rejects_every_overlap(self):
    valid = {
        "profile": 2,
        "param_base_words": 2 * 12193,
        "params_words": 4 * 12193,
        "memory_words": 100000,
        "src_words": 0,
        "dst_words": 40000,
        "scratch_words": 80000,
        "start_row": 28,
        "row_count": 4,
    }
    checked = contract.validate_descriptor(valid)
    self.assertEqual(checked["tensor_words"], 32768)
    self.assertEqual(checked["scratch_required_words"], 5120)
    for field, value in (("dst_words", 30000), ("scratch_words", 32000),
                         ("scratch_words", 70000)):
        bad = dict(valid)
        bad[field] = value
        with self.assertRaisesRegex(ValueError, "overlap"):
            contract.validate_descriptor(bad)


 def test_descriptor_rejects_invalid_unsigned_ranges_before_execution(self):
    cases = [
        ({"profile": 3}, "profile"),
        ({"row_count": 0}, "row_count"),
        ({"row_count": 5}, "row_count"),
        ({"start_row": 62}, "row range"),
        ({"param_base_words": 4 * 12193}, "parameter"),
        ({"memory_words": 83000}, "arena"),
        ({"src_words": 1 << 32}, "uint32"),
    ]
    for patch, message in cases:
        with self.subTest(patch=patch):
            value = {
                "profile": 2, "param_base_words": 0, "params_words": 12193,
                "memory_words": 100000, "src_words": 0, "dst_words": 40000,
                "scratch_words": 80000, "start_row": 0, "row_count": 4,
            }
            value.update(patch)
            with self.assertRaisesRegex(ValueError, message):
                contract.validate_descriptor(value)


 def test_resource_model_matches_frozen_stripe4_budget(self):
    expected = {
        2: (154, 184, 748, 2.40625, 0.6696428571428572),
        0: (74, 88, 364, 2.3125, 0.625),
        1: (34, 40, 172, 2.125, 0.5357142857142858),
    }
    for profile, values in expected.items():
        item = contract.resource_model(profile)
        self.assertEqual(item["q3_rows_computed"], values[0])
        self.assertEqual(item["source_rows_read"], values[1])
        self.assertEqual(item["activation_traffic_row_equivalents"], values[2])
        self.assertEqual(item["dw3_recompute_factor"], values[3])
        self.assertAlmostEqual(item["activation_traffic_increase_ratio"], values[4])
        self.assertEqual(item["scratch_peak_bytes"], 80 * 1024)
        self.assertEqual(item["local_shared_ram_bytes"], 32 * 1024)
        self.assertEqual(item["gelu_table_bram_bytes"], 128 * 1024)
        self.assertEqual(item["gelu_table_load_128b_beats_per_job"], 8192)
        self.assertEqual(item["gelu_table_load_bytes_per_job"], 128 * 1024)
        self.assertEqual(item["gelu_table_load_128b_beats_per_block"],
                         8192 * item["stripe_count"])
        # The C++ core fetches only valid PW output channels.  Packed padding
        # exists in the parameter window but is not requested over AXI.
        self.assertEqual(item["pw_weight_read_bytes_per_spatial_tile"],
                         12 * item["channels"] * item["channels"])
        self.assertEqual(item["spatial_tiles_per_block"],
                         item["width"] * item["width"] // 16)
        self.assertEqual(item["pw_weight_read_bytes_per_block"], 12 * 1024 * 1024)
        self.assertEqual(item["pw_weight_read_bytes_per_job"],
                         item["pw_weight_read_bytes_per_block"] //
                         item["stripe_count"])
        self.assertEqual(item["modeled_major_parameter_read_bytes_per_block"],
                         item["pw_weight_read_bytes_per_block"] +
                         item["gelu_table_load_bytes_per_job"] *
                         item["stripe_count"])
        self.assertEqual(item["gelu_lookups_per_block"],
                         3 * item["channels"] * item["width"] * item["width"])

 def test_resource_report_accounts_fixed_full_gelu_preload_per_job(self):
    cache = (ROOT / "artifacts/board-debug-20261005/acceleration/host/"
             "root-v7-first-stripe-001/cache-budget.json")
    gelu = (ROOT / "artifacts/board-debug-20261005/acceleration/host/"
            "cnn-shared-v7-gelu-analysis-001/manifest.json")
    report = resource_report.build_report(ROOT, cache, gelu)
    aggregate = report["aggregate_36_normal_blocks"]
    self.assertEqual(aggregate["gelu_table_load_128b_beats"], 1966080)
    self.assertEqual(aggregate["gelu_table_load_bytes"], 30 * 1024 * 1024)
    self.assertEqual(aggregate["modeled_major_parameter_read_bytes"],
                     462 * 1024 * 1024)
    self.assertEqual(aggregate["modeled_major_parameter_read_mib"], 462.0)
    self.assertTrue(report["superseded_selected_gelu_cache_replay"]
                    ["not_used_by_current_kernel"])


 def test_gelu_tail_analysis_finds_exact_constant_and_affine_regions(self):
    table = np.arange(-32768, 32768, dtype=np.int32)
    table[:11] = -7
    table[-17:] = np.arange(101, 118, dtype=np.int32)
    result = gelu_analysis.analyze_table(table.astype("<i2"))
    self.assertEqual(result["constant_prefix"]["entries"], 11)
    self.assertEqual(result["constant_prefix"]["input_max"], -32758)
    self.assertEqual(result["affine_suffix"]["entries"], 17)
    self.assertEqual(result["affine_suffix"]["input_min"], 32751)
    self.assertEqual(result["affine_suffix"]["delta_per_input"], 1)
    self.assertGreater(result["longest_exact_unit_slope_run"]["entries"], 65000)


 def test_origin_aware_stripes_stitch_to_independent_full_oracle_exactly(self):
    params = _small_params()
    rng = np.random.RandomState(11)
    source = rng.randint(-7, 8, (2, 8, 8)).astype("<i2")
    expected, expected_stages, _ = full_oracle.execute_block(source, params)
    stitched = np.empty_like(expected)
    for start in (0, 4):
        result = oracle.execute_stripe(source, params, start, 4, tile_pixels=16)
        stitched[:, start:start + 4, :] = result["output"]
        self.assertTrue(np.array_equal(result["q3_scratch"],
                                      expected_stages["dw3"][:, result["q3_start_row"]:
                                                             result["q3_end_row"], :]))
        for name in ("dw7", "pw1", "gelu", "pw2", "scale", "residual", "add"):
            self.assertTrue(np.array_equal(result[name], expected_stages[name][:, start:start + 4, :]))
    self.assertTrue(np.array_equal(stitched, expected))
    self.assertFalse(np.array_equal(expected_stages["residual"], source))


 def test_real_p2_block0_blob_decodes_without_repacking(self):
    path = (ROOT / "artifacts/board-debug-20261005/acceleration/host/"
            "network0-w16-preflight-001/params/profile2/block-00.bin")
    decoded = oracle.decode_w16_block(path.read_bytes(), profile=2)
    self.assertEqual(decoded["layers"]["dw3"]["weights"].shape, (64, 1, 3, 3))
    self.assertEqual(decoded["layers"]["dw7"]["weights"].shape, (64, 1, 7, 7))
    self.assertEqual(decoded["layers"]["pw1"]["weights"].shape, (192, 64))
    self.assertEqual(decoded["layers"]["pw2"]["weights"].shape, (64, 192))
    self.assertEqual(decoded["gelu"].shape, (65536,))
    self.assertEqual(decoded["packed_bytes"], 195088)

 def test_fixture_selection_is_first_middle_last_and_pins_canonical_sources(self):
    records = fixtures.canonical_sources(ROOT)
    self.assertEqual(sorted(records), [0, 1, 2])
    self.assertEqual(fixtures.selected_stripe_starts(64), [0, 32, 60])
    self.assertEqual(fixtures.selected_stripe_starts(32), [0, 16, 28])
    self.assertEqual(fixtures.selected_stripe_starts(16), [0, 8, 12])
    self.assertEqual(records[0]["manifest_sha256"],
                     "4d02889c23aa989dab76e4c5c0fd07143ed164a34fbe455901b566abd2767e4b")
    self.assertEqual(records[1]["manifest_sha256"], records[0]["manifest_sha256"])
    self.assertEqual(records[2]["manifest_sha256"],
                     "9fcc4a05e7668c523f0a94d54ed8731c68582e0958f24bc7589c2f702c9f7326")
    for profile, record in records.items():
        self.assertTrue(record["params"].is_file())
        self.assertTrue(record["input_hcw"].is_file())
        self.assertTrue(record["expected_block0_chw"].is_file())
        self.assertEqual(record["width"], contract.PROFILE_SPECS[profile]["width"])

 def test_native_tb_layout_uses_nonzero_disjoint_offsets(self):
    for profile in (0, 1, 2):
        width = contract.PROFILE_SPECS[profile]["width"]
        for start in fixtures.selected_stripe_starts(width):
            descriptor = fixtures.native_tb_descriptor(profile, start)
            checked = contract.validate_descriptor(descriptor)
            self.assertGreater(checked["src_words"], 0)
            self.assertGreater(checked["dst_words"], checked["spans"]["src"][1])
            self.assertGreater(checked["scratch_words"], checked["spans"]["dst"][1])

 def test_adjacent_block_waits_for_complete_halo4_in_same_frame(self):
    queue = scheduler.StripeScheduler()
    first = scheduler.StripeJob("frame-a", 0, 1, 0, 4, 0, "scratch-a",
                                "arena-a", 50000, 0)
    token0 = queue.dispatch(first)
    queue.complete(token0, success=True)
    downstream = scheduler.StripeJob("frame-a", 1, 1, 0, 4, 1,
                                     "scratch-b", "arena-a", 0, 10000)
    with self.assertRaisesRegex(RuntimeError, "predecessor rows"):
        queue.dispatch(downstream)
    second = scheduler.StripeJob("frame-a", 0, 1, 4, 4, 0,
                                 "scratch-a", "arena-a", 50000, 0)
    queue.complete(queue.dispatch(second), success=True)
    token1 = queue.dispatch(downstream)
    queue.complete(token1, success=True)
    self.assertEqual(queue.committed_intervals("frame-a", 1, 1), [(0, 4)])

 def test_scheduler_isolates_frame_tags_scratch_and_destination_writes(self):
    queue = scheduler.StripeScheduler()
    a = scheduler.StripeJob("frame-a", 0, 2, 0, 4, 0, "scratch-0",
                            "arena-0", 50000, 0)
    token_a = queue.dispatch(a)
    duplicate_tag = scheduler.StripeJob("frame-a", 0, 2, 0, 4, 2,
                                        "scratch-x", "arena-x", 50000, 0)
    with self.assertRaisesRegex(RuntimeError, "logical output"):
        queue.dispatch(duplicate_tag)
    same_scratch = scheduler.StripeJob("frame-b", 0, 2, 0, 4, 1,
                                       "scratch-0", "arena-1", 50000, 0)
    with self.assertRaisesRegex(RuntimeError, "scratch"):
        queue.dispatch(same_scratch)
    same_output = scheduler.StripeJob("frame-b", 0, 2, 0, 4, 1,
                                      "scratch-1", "arena-0", 60000, 0)
    with self.assertRaisesRegex(RuntimeError, "destination"):
        queue.dispatch(same_output)
    disjoint = scheduler.StripeJob("frame-b", 0, 2, 4, 4, 1,
                                   "scratch-1", "arena-0", 60000, 0)
    token_b = queue.dispatch(disjoint)
    queue.complete(token_a, success=True)
    with self.assertRaisesRegex(RuntimeError, "already committed"):
        queue.dispatch(duplicate_tag)
    queue.complete(token_b, success=False)
    self.assertEqual(queue.committed_intervals("frame-a", 2, 0), [(0, 4)])
    self.assertEqual(queue.committed_intervals("frame-b", 2, 0), [])
    frame_b_downstream = scheduler.StripeJob("frame-b", 1, 2, 0, 4, 0,
                                             "scratch-2", "arena-2", 0, 10000)
    with self.assertRaisesRegex(RuntimeError, "predecessor rows"):
        queue.dispatch(frame_b_downstream)
    with self.assertRaisesRegex(RuntimeError, "completion token"):
        queue.complete(9999, success=True)

 def test_scheduler_keys_commits_by_profile_and_blocks_active_read_write_hazards(self):
    queue = scheduler.StripeScheduler()
    # The same frame/block number in another profile is an independent chain.
    p2 = scheduler.StripeJob("frame-a", 0, 2, 0, 4, 0, "s0",
                             "arena-a", 50000, 0)
    p0 = scheduler.StripeJob("frame-a", 0, 0, 0, 4, 1, "s1",
                             "arena-b", 50000, 0)
    queue.complete(queue.dispatch(p2), success=True)
    queue.complete(queue.dispatch(p0), success=True)
    self.assertEqual(queue.committed_intervals("frame-a", 2, 0), [(0, 4)])
    self.assertEqual(queue.committed_intervals("frame-a", 0, 0), [(0, 4)])

    # A new writer may not overwrite an active job's real halo4 source span.
    reader = scheduler.StripeJob("frame-r", 0, 2, 0, 4, 0, "sr",
                                 "shared", 0, 50000)
    reader_token = queue.dispatch(reader)
    writer = scheduler.StripeJob("frame-w", 0, 2, 0, 4, 1, "sw",
                                 "shared", 60000, 0)
    with self.assertRaisesRegex(RuntimeError, "active source"):
        queue.dispatch(writer)
    queue.complete(reader_token, success=False)

    # The inverse ordering is also unsafe: a reader cannot enter an active
    # destination write span.
    writer_token = queue.dispatch(writer)
    with self.assertRaisesRegex(RuntimeError, "active destination"):
        queue.dispatch(reader)
    queue.complete(writer_token, success=False)

 def test_multicore_plan_keeps_every_block_tensor_and_core_scratch_private(self):
    plan = multicore_plan.build_plan(profile=0, core_count=2,
                                     frame_id="frame-a")
    self.assertEqual(plan["profile"], 0)
    self.assertEqual(plan["block_count"], 12)
    self.assertEqual(len(plan["tensor_regions"]), 13)
    self.assertEqual(len(plan["scratch_regions"]), 2)
    spans = []
    for region in plan["tensor_regions"] + plan["scratch_regions"]:
        self.assertEqual(region["offset_words"] % 4096, 0)
        span = (region["offset_words"],
                region["offset_words"] + region["extent_words"])
        self.assertTrue(all(span[1] <= other[0] or other[1] <= span[0]
                            for other in spans))
        spans.append(span)
    self.assertEqual(plan["jobs"][0]["src_words"],
                     plan["tensor_regions"][0]["offset_words"])
    for block, job in enumerate(plan["jobs"]):
        self.assertEqual(job["src_words"],
                         plan["tensor_regions"][block]["offset_words"])
        self.assertEqual(job["dst_words"],
                         plan["tensor_regions"][block + 1]["offset_words"])
        self.assertNotEqual(job["src_words"], job["dst_words"])

 def test_multicore_plan_builds_safe_descriptors_and_exact_memory_budget(self):
    report = multicore_plan.build_release_model(core_count=2)
    self.assertEqual(report["normal_blocks"], 36)
    self.assertEqual(report["tensor_regions"], 39)
    self.assertEqual(report["scratch_regions"], 6)
    self.assertEqual(report["params_bytes"], 24625728)
    self.assertEqual(report["memory_bytes"], 9568256)
    self.assertEqual(report["total_bytes"], 34193984)
    for profile_plan in report["profiles"]:
        for job in profile_plan["jobs"]:
            for core_id in range(2):
                descriptor = multicore_plan.stripe_descriptor(
                    profile_plan, job["block_index"], core_id,
                    start_row=0, row_count=4)
                checked = contract.validate_descriptor(descriptor)
                self.assertEqual(checked["src_words"], job["src_words"])
                self.assertEqual(checked["dst_words"], job["dst_words"])
                self.assertEqual(checked["scratch_words"],
                                 profile_plan["scratch_regions"][core_id]
                                 ["offset_words"])

 def test_multicore_scheduler_uses_profile_key_and_disjoint_block_storage(self):
    plan = multicore_plan.build_plan(profile=2, core_count=2,
                                     frame_id="frame-a")
    queue = scheduler.StripeScheduler()
    first = multicore_plan.scheduler_job(plan, block_index=0, core_id=0,
                                         start_row=0, row_count=4)
    token = queue.dispatch(first)
    # Another block cannot launch until the complete halo4 source interval is
    # committed, even though it already owns a separate destination tensor.
    second = multicore_plan.scheduler_job(plan, block_index=1, core_id=1,
                                          start_row=0, row_count=4)
    with self.assertRaisesRegex(RuntimeError, "predecessor rows"):
        queue.dispatch(second)
    queue.complete(token, success=True)
    first_next = multicore_plan.scheduler_job(plan, block_index=0, core_id=0,
                                              start_row=4, row_count=4)
    queue.complete(queue.dispatch(first_next), success=True)
    token2 = queue.dispatch(second)
    self.assertNotEqual(first.arena_id, "ping-pong")
    queue.complete(token2, success=True)

 def test_multicore_candidate_uapi_has_explicit_stable_sizes(self):
    header = (ROOT / "desktop_vlm/board/cnn_shared_v7_multicore_driver/"
              "network7_v7_multicore_uapi_candidate.h").read_text(
                  encoding="utf-8")
    for field in ("core_id", "frame_tag", "profile", "block_index",
                  "src_words", "dst_words", "scratch_words"):
        self.assertIn(field, header)
    self.assertEqual(struct.calcsize("<4IQ12I"), 72)
    self.assertEqual(struct.calcsize("<16I"), 64)


if __name__ == "__main__":
    unittest.main()
