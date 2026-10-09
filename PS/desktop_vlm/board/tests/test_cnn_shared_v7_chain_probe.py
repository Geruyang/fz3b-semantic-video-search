import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[3]
BOARD = ROOT / "desktop_vlm/board"
sys.path.insert(0, str(BOARD))
sys.path.insert(0, str(ROOT / "desktop_vlm/scripts/acceleration"))

import cnn_shared_v7_chain_bundle as bundle
import cnn_shared_v7_chain_probe as probe


RUNTIME = ROOT / ("artifacts/board-debug-20261005/acceleration/host/"
                  "network-w16-runtime-bundles-001")
GOLDEN = ROOT / ("artifacts/board-debug-20261005/acceleration/host/"
                 "network-w16-same-board-golden-001")


class FakeDevice(object):
    def __init__(self, plan):
        self.plan = {(item["profile"], item["block_index"]): item
                     for item in plan}
        self.next_handle = 1
        self.objects = {}
        self.state = dict((name, 0) for name in probe.STATUS_NAMES)
        self.state["job_cycles_lo"] = 17
        self.quiesced = False
        self.fail_on_job = None

    def identity(self):
        return {"core_id": probe.CORE_ID, "core_abi": probe.CORE_ABI,
                "guard_caps": probe.GUARD_CAPS,
                "abi_version": probe.ABI_VERSION, "profile_count": 3}

    def alloc(self, size, alignment=65536, flags=1):
        handle = self.next_handle
        self.next_handle += 1
        self.objects[handle] = bytearray(size)
        return {"handle": handle, "bytes": size, "alignment": alignment,
                "flags": flags, "arena_index": 0}

    def upload(self, handle, offset, payload):
        self.objects[handle][offset:offset + len(payload)] = payload

    def download(self, handle, offset, size):
        return bytes(self.objects[handle][offset:offset + size])

    def status(self):
        result = dict(self.state)
        result["job_cycles"] = ((result["job_cycles_hi"] << 32) |
                                result["job_cycles_lo"])
        return result

    def submit(self, descriptor, params_handle, memory_handle):
        if self.fail_on_job is not None and self.state["completed_jobs"] + 1 == self.fail_on_job:
            raise RuntimeError("injected submit failure")
        item = self.plan[(int(descriptor["profile"]),
                          int(descriptor["block_index"]))]
        row_bytes = int(descriptor["row_words"]) * 16
        start = int(descriptor["start_row"]) * row_bytes
        count = int(descriptor["row_count"]) * row_bytes
        dst = int(descriptor["dst_words"]) * 16
        scratch = int(descriptor["scratch_words"]) * 16
        scratch_size = int(descriptor["scratch_required_words"]) * 16
        self.objects[memory_handle][dst + start:dst + start + count] = \
            item["expected"][start:start + count]
        self.objects[memory_handle][scratch:scratch + scratch_size] = \
            bytearray([0x33]) * scratch_size
        self.state["completed_jobs"] += 1
        self.state["profile"] = int(descriptor["profile"])
        # The guard restarts job_cycles at every accepted START.  It is a
        # per-job duration, not a lifetime counter.
        self.state["job_cycles_lo"] = 25 + (self.state["completed_jobs"] & 1)
        for name, delta in (("ar_total", 3), ("rlast_total", 3),
                            ("aw_total", 2), ("wlast_total", 2),
                            ("b_total", 2)):
            self.state[name] += delta

    def quiesce(self):
        self.quiesced = True

    def free(self, handle):
        if not self.quiesced:
            raise RuntimeError("FREE before QUIESCE")
        del self.objects[handle]


class SharedV7ChainProbeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.out = Path(self.temp.name) / "bundle"
        bundle.build_bundle(ROOT, RUNTIME, GOLDEN, self.out)
        self.manifest_path = self.out / "manifest.json"
        self.manifest_sha = hashlib.sha256(self.manifest_path.read_bytes()).hexdigest()
        self.plan = probe.load_plan(str(self.out), str(self.manifest_path),
                                   self.manifest_sha)

    def tearDown(self):
        self.temp.cleanup()

    def test_bundle_has_frozen_counts_contiguous_params_and_pingpong(self):
        data = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        self.assertEqual({int(p): len(v["blocks"])
                          for p, v in data["profiles"].items()},
                         {0: 12, 1: 20, 2: 4})
        self.assertIn("profile 1 has 20 blocks", data["block_count_note"])
        for item in self.plan:
            descs = item["descriptors"]
            self.assertEqual(len(descs), item["width"] // 4)
            self.assertEqual({d["param_base_words"] for d in descs},
                             {item["block_index"] * item["stride_words"]})
            self.assertEqual(descs[0]["src_words"], item["src_words"])
            self.assertEqual(descs[0]["dst_words"], item["dst_words"])
            self.assertEqual(descs[0]["scratch_capacity_words"], 5120)

    def test_fake_device_runs_every_block_and_verifies_outputs(self):
        device = FakeDevice(self.plan)
        events = []
        result = probe.execute_plan(device, self.plan,
                                    progress_callback=events.append)
        self.assertEqual(result["status"],
                         "CNN_SHARED_V7_NORMAL_CHAIN_ALL_PROFILES_PASS")
        self.assertEqual(result["profile_block_counts"], {"0": 12, "1": 20, "2": 4})
        self.assertEqual(result["total_jobs"], sum(item["width"] // 4
                                                   for item in self.plan))
        self.assertEqual(len(result["completed_blocks"]), 36)
        self.assertEqual({job["job_cycles"] for job in result["jobs"]},
                         {25, 26})
        first_block = result["completed_blocks"][0]
        self.assertEqual(first_block["job_cycles"],
                         sum(job["job_cycles"] for job in result["jobs"][:8]))
        self.assertTrue(result["cleanup"]["quiesced"])
        self.assertFalse(device.objects)
        job_events = [item for item in events
                      if item["event"] == "job_complete"]
        block_events = [item for item in events
                        if item["event"] == "block_complete"]
        self.assertEqual(len(job_events), 240)
        self.assertEqual(len(block_events), 36)
        self.assertEqual(job_events[-1]["completed_jobs"], 240)
        self.assertEqual(block_events[-1]["completed_jobs"], 240)
        self.assertEqual(block_events[-1]["completed_blocks"], 36)

    def test_mid_chain_failure_preserves_partial_jobs_and_cleanup_evidence(self):
        device = FakeDevice(self.plan)
        device.fail_on_job = 3
        report = {}
        with self.assertRaisesRegex(RuntimeError, "injected submit failure"):
            probe.execute_plan(device, self.plan, report)
        self.assertEqual(len(report["jobs"]), 2)
        self.assertTrue(report["cleanup"]["quiesced"])
        self.assertTrue(report["cleanup"]["handles_freed"])
        self.assertFalse(device.objects)

    def test_overall_timeout_keeps_completed_job_and_cleanup_evidence(self):
        device = FakeDevice(self.plan)
        report = {}
        events = []
        ticks = iter(range(100000))

        def fake_time_ns():
            return next(ticks) * 1000000

        with mock.patch.object(probe, "_time_ns", side_effect=fake_time_ns):
            with self.assertRaisesRegex(RuntimeError, "overall timeout"):
                probe.execute_plan(device, self.plan, report,
                                   progress_callback=events.append,
                                   overall_timeout_s=0.0055)
        self.assertEqual(len(report["jobs"]), 1)
        self.assertEqual(events[-1]["event"], "job_complete")
        self.assertEqual(events[-1]["completed_jobs"], 1)
        self.assertTrue(report["cleanup"]["quiesced"])
        self.assertTrue(report["cleanup"]["handles_freed"])
        self.assertFalse(device.objects)

    def test_atomic_progress_writer_replaces_complete_json(self):
        output = Path(self.temp.name) / "progress.json"
        probe._write_json_atomic(str(output), {"completed_jobs": 1})
        probe._write_json_atomic(str(output), {"completed_jobs": 2,
                                               "status": "running"})
        self.assertEqual(json.loads(output.read_text()),
                         {"completed_jobs": 2, "status": "running"})
        self.assertFalse(Path(str(output) + ".tmp").exists())


if __name__ == "__main__":
    unittest.main()
