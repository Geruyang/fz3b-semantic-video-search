import hashlib
import json
import pathlib
import tempfile
import unittest

import numpy as np

from benchmark_cnn_v10_p3_oracle_quality import SuffixInputCaptureClient


class _Client(object):
    header = {"kind": "test"}
    outputs_have_independent_lifetime = True
    validates_tensor_finiteness = True

    def __init__(self):
        self.closed = False

    def infer(self, tensors):
        return {"feature": np.array([1.0], dtype=np.float32)}, 2.5

    def close(self):
        self.closed = True


class SuffixInputCaptureTest(unittest.TestCase):
    def test_capture_is_sha_deduplicated_and_delegates(self):
        with tempfile.TemporaryDirectory() as root:
            capture = pathlib.Path(root) / "capture"
            inner = _Client()
            client = SuffixInputCaptureClient(inner, capture)
            value = np.arange(12, dtype="<f4").reshape(1, 3, 2, 2)
            result, run_ms = client.infer([value])
            client.infer([value.copy()])
            client.close()
            self.assertEqual(run_ms, 2.5)
            self.assertEqual(result["feature"].tolist(), [1.0])
            self.assertTrue(inner.closed)
            manifest = json.loads((capture / "manifest.json").read_text("utf-8"))
            self.assertEqual(len(manifest["records"]), 1)
            record = manifest["records"][0]
            raw = value.tobytes(order="C")
            self.assertEqual(record["sha256"], hashlib.sha256(raw).hexdigest())
            self.assertEqual(record["shape"], [1, 3, 2, 2])
            self.assertEqual((capture / record["path"]).read_bytes(), raw)

    def test_nonfinite_input_is_rejected_before_delegate(self):
        with tempfile.TemporaryDirectory() as root:
            client = SuffixInputCaptureClient(_Client(), pathlib.Path(root) / "capture")
            with self.assertRaisesRegex(ValueError, "non-finite"):
                client.infer([np.array([np.nan], dtype=np.float32)])
            client.close()


if __name__ == "__main__":
    unittest.main()
