import hashlib
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
BOARD = ROOT / "desktop_vlm/board"
sys.path.insert(0, str(BOARD))

import cnn_shared_v7_probe as probe


MANIFEST = ROOT / ("artifacts/board-debug-20261005/acceleration/host/"
                   "cnn-shared-v7-native-tb-fixtures-001/manifest.json")


class FakeDevice(object):
    def __init__(self, plan):
        self.plan = {int(item["sequence"]["profile"]): item for item in plan}
        self.next_handle = 1
        self.objects = {}
        self.state = dict((name, 0) for name in probe.STATUS_NAMES)
        self.state["guard_status"] = 0x1C10
        self.state["guard_acks"] = 0xFF
        self.state["reset_generation"] = 1
        self.state["job_cycles_lo"] = 100
        self.quiesced = False

    def identity(self):
        return {"core_id": probe.CORE_ID, "core_abi": probe.CORE_ABI,
                "guard_caps": probe.GUARD_CAPS,
                "abi_version": probe.ABI_VERSION, "profile_count": 3}

    def alloc(self, size):
        handle = self.next_handle
        self.next_handle += 1
        self.objects[handle] = bytearray(size)
        return {"handle": handle, "bytes": size, "alignment": 65536,
                "flags": 1, "arena_index": 0}

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
        unused = params_handle
        item = self.plan[int(descriptor["profile"])]
        row_bytes = int(descriptor["row_words"]) * 16
        start = int(descriptor["start_row"]) * row_bytes
        count = int(descriptor["row_count"]) * row_bytes
        dst = int(descriptor["dst_words"]) * 16
        scratch = int(descriptor["scratch_words"]) * 16
        scratch_bytes = int(descriptor["scratch_required_words"]) * 16
        self.objects[memory_handle][dst + start:dst + start + count] = \
            item["expected"][start:start + count]
        self.objects[memory_handle][scratch:scratch + scratch_bytes] = \
            bytes(bytearray([0x33])) * scratch_bytes
        self.state["completed_jobs"] += 1
        self.state["profile"] = int(descriptor["profile"])
        for name, delta in (("ar_total", 5), ("rlast_total", 5),
                            ("aw_total", 2), ("wlast_total", 2),
                            ("b_total", 2)):
            self.state[name] += delta
        self.state["job_cycles_lo"] += 1000

    def quiesce(self):
        self.quiesced = True

    def free(self, handle):
        if not self.quiesced:
            raise RuntimeError("FREE before QUIESCE")
        del self.objects[handle]


class SharedV7ProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest_sha = hashlib.sha256(MANIFEST.read_bytes()).hexdigest()
        cls.plan = probe.load_plan(str(ROOT), str(MANIFEST), cls.manifest_sha)

    def test_uapi_struct_sizes_and_ioctl_magic(self):
        self.assertEqual(probe.IDENTITY.size, 160)
        self.assertEqual(probe.SUBMIT.size, 48)
        self.assertEqual(probe.STATUS.size, 60)
        self.assertEqual((probe.IOC_SUBMIT >> 8) & 0xFF, ord("Y"))

    def test_manifest_has_all_profiles_and_complete_stripes(self):
        self.assertEqual({item["sequence"]["profile"] for item in self.plan},
                         {0, 1, 2})
        self.assertEqual(sum(len(item["sequence"]["descriptors"])
                             for item in self.plan), 28)

    def test_expected_metrics_use_real_valid_channel_pw_reads(self):
        descriptor = next(item for item in self.plan
                          if item["sequence"]["profile"] == 2)["sequence"]["descriptors"][0]
        metrics = probe.expected_job_metrics(descriptor)
        self.assertEqual(metrics["pw_weight_read_bytes"], 786432)
        self.assertEqual(metrics["pw_weight_read_128b_beats"], 49152)
        self.assertEqual(metrics["gelu_lookups"], 49152)

    def test_fake_driver_runs_all_stripes_and_cleans_up(self):
        device = FakeDevice(self.plan)
        result = probe.execute_plan(device, self.plan)
        self.assertEqual(result["status"],
                         "CNN_SHARED_V7_SINGLE_CORE_ALL_STRIPES_PASS")
        self.assertEqual(len(result["jobs"]), 28)
        self.assertEqual(len(result["completed_sequences"]), 3)
        self.assertTrue(result["cleanup"]["quiesced"])
        self.assertFalse(device.objects)


if __name__ == "__main__":
    unittest.main()
