"""Synthetic scheduler-buffer regressions; these are not board evidence."""
import copy
import tempfile
import unittest
from pathlib import Path

from audit_cnn_pipeline_v6_features import audit_frames, sha


class FeatureAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.golden = {"execution": {"boot_id": "synthetic-boot"},
                       "source_hashes": {"canonical_bundle_manifest": "bundle",
                                         "runtime_split_manifest": "split"}, "results": []}
        self.report = {"status": "BOARD_V6_BENCHMARK_COMPLETED", "pl_execution": True,
                       "kernel_boot_id": "synthetic-boot", "split_manifest_sha256": "split",
                       "parameter_binding": {"production_mode": "normal_fallback",
                                             "physical_profiles": [2, 0, 1],
                                             "v5_bundle_manifest_sha256": "bundle"},
                       "feature_outputs": [], "measurement": {"frames": []}}
        for index in range(3):
            raw = bytes([index + 1]) * 2048
            name = "%d.f32" % index
            (self.root / name).write_bytes(raw)
            self.golden["results"].append({"sample_id": str(index), "input_sha256": str(index),
                "feature": {"path": name, "sha256": sha(raw), "bytes": 2048}})
        for fid in range(30):
            source = fid % 3
            ref = self.golden["results"][source]["feature"]
            self.report["measurement"]["frames"].append({"frame_id": fid, "input_sha256": str(source)})
            self.report["feature_outputs"].append({"frame_id": fid, "relative_path": ref["path"],
                                                   "sha256": ref["sha256"], "bytes": 2048})

    def audit(self, report):
        return audit_frames(report, self.root, self.golden, self.root)

    def test_all_thirty_input_bound_outputs(self):
        self.assertEqual(len(self.audit(self.report)), 30)

    def test_valid_file_hash_cannot_hide_swapped_frames(self):
        bad = copy.deepcopy(self.report)
        bad["measurement"]["frames"][0]["input_sha256"] = "1"
        with self.assertRaises(ValueError):
            self.audit(bad)

    def test_duplicate_frame_cannot_replace_missing_result(self):
        bad = copy.deepcopy(self.report)
        bad["measurement"]["frames"][1] = copy.deepcopy(bad["measurement"]["frames"][0])
        with self.assertRaises(ValueError):
            self.audit(bad)


if __name__ == "__main__":
    unittest.main()
