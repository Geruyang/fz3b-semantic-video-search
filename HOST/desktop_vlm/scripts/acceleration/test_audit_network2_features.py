"""HOST_CONTRACT_ONLY: checker tests, never board inference evidence."""
import copy
import unittest
from pathlib import Path

import numpy as np

import audit_network2_features as audit


class FeatureAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        repo = Path(__file__).resolve().parents[3]
        oracle = repo / "artifacts/board-debug-20261005/acceleration/host/network2-int-oracle-board-ps-001"
        cls.references, cls.text = audit.load_oracle(oracle)
        cls.records = []
        for index in range(30):
            sample = "image-%02d" % (index % 3)
            feature = cls.references[sample]["quantized"].astype("<f4")
            cls.records.append({"frame_id": index, "sample_id": sample,
                                "feature_f32": feature.tolist(),
                                "feature_sha256": audit.digest(feature.tobytes())})

    def test_exact_saved_reference_roundtrip(self):
        import json
        records = json.loads(json.dumps(self.records))
        result = audit.audit_records(records, self.references, self.text)
        self.assertEqual(len(result), 30)
        self.assertTrue(all(row["vs_quantized"]["max_abs"] == 0 for row in result))

    def test_modified_feature_with_valid_new_hash_fails_numeric_gate(self):
        records = copy.deepcopy(self.records)
        value = np.asarray(records[0]["feature_f32"], dtype="<f4")
        value[0] += .01
        records[0]["feature_f32"] = value.tolist()
        records[0]["feature_sha256"] = audit.digest(value.tobytes())
        with self.assertRaisesRegex(ValueError, "differs from quantized"):
            audit.audit_records(records, self.references, self.text)

    def test_wrong_hash_is_rejected(self):
        records = copy.deepcopy(self.records)
        records[0]["feature_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "SHA mismatch"):
            audit.audit_records(records, self.references, self.text)

    def test_nonfinite_is_rejected(self):
        records = copy.deepcopy(self.records)
        records[0]["feature_f32"][0] = float("nan")
        with self.assertRaisesRegex(ValueError, "nonfinite"):
            audit.audit_records(records, self.references, self.text)

    def test_sample_mapping_is_checked(self):
        records = copy.deepcopy(self.records)
        records[0]["sample_id"] = "image-01"
        with self.assertRaisesRegex(ValueError, "order mismatch"):
            audit.audit_records(records, self.references, self.text)

    def test_host_contract_report_cannot_pass_board_entry(self):
        report = {"execution": "host", "pl_execution": False,
                  "status": "HOST_CONTRACT_ONLY", "records": self.records}
        with self.assertRaisesRegex(ValueError, "requires real board"):
            audit.audit_board_report(report, self.references, self.text)


if __name__ == "__main__":
    unittest.main()
