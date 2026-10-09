import hashlib
import json
import pathlib
import sys
import tempfile
import unittest


BOARD = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BOARD))

from run_cnn_pipeline_v10_a0005_validation import (  # noqa: E402
    COMBINED_MANIFEST_SHA256, FIXTURE_SCHEMA, load_fixture_manifest, main)
from desktop_vlm.board.tests.test_run_cnn_pipeline_v10_a0004_validation import (  # noqa: E402
    FakeTransport)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


class A0005ValidationRunnerTest(unittest.TestCase):
    def _package(self, root):
        expected = bytes(range(32))
        cases = []
        for profile in range(4):
            records = {}
            for name, raw in (("params", b"p" * 16),
                              ("input_a", b"a" * 32),
                              ("expected_a", expected),
                              ("input_b", b"b" * 32),
                              ("expected_b", expected)):
                path = root / ("p%d-%s.bin" % (profile, name))
                path.write_bytes(raw)
                records[name] = {"path": path.name, "bytes": len(raw),
                                 "sha256": sha(raw)}
            cases.append({
                "case_id": "profile-%d" % profile,
                "profile": profile, "block_count": 1,
                "contract": {"params_bytes": 16, "arena_bytes": 64,
                             "input_bytes": 32, "output_bytes": 32,
                             "output_offset_bytes": 0},
                "files": records})
        value = {"schema": FIXTURE_SCHEMA,
                 "status": "PASS_HOST_FIXTURES_ONLY",
                 "core_abi": "0x000A0005",
                 "combined_parameter_manifest_sha256":
                     COMBINED_MANIFEST_SHA256,
                 "cases": cases}
        path = root / "manifest.json"
        path.write_text(json.dumps(value), encoding="utf-8")
        return path, sha(path.read_bytes()), expected

    def test_manifest_rejects_a0004_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            path, unused_digest, unused_expected = self._package(root)
            value = json.loads(path.read_text(encoding="utf-8"))
            value["core_abi"] = "0x000A0004"
            path.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "contract mismatch"):
                load_fixture_manifest(path, sha(path.read_bytes()))

    def test_cli_mock_is_not_hardware_and_binds_admission(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            path, digest, expected = self._package(root)
            output = root / "result.json"

            def factory(unused_args):
                return FakeTransport(expected, expected), lambda p, n: {
                    "params_bytes": 16, "arena_bytes": 64,
                    "input_bytes": 32, "output_bytes": 32,
                    "output_offset_bytes": 0, "slot_words": 2}

            admission_sha = "1" * 64
            proof_sha = "2" * 64
            rc = main([
                "--fixture-manifest", str(path),
                "--expected-fixture-manifest-sha256", digest,
                "--combined-manifest", str(root / "unused-combined.json"),
                "--expected-combined-manifest-sha256",
                COMBINED_MANIFEST_SHA256,
                "--admission", str(root / "unused-admission.json"),
                "--expected-admission-sha256", admission_sha,
                "--proof", str(root / "unused-proof.json"),
                "--expected-proof-sha256", proof_sha,
                "--output", str(output)], transport_factory=factory)
            self.assertEqual(rc, 0)
            result = json.loads(output.read_text(encoding="utf-8"))
            self.assertFalse(result["hardware_execution"])
            self.assertEqual(result["core_abi"], "0x000A0005")
            self.assertEqual(result["profiles"], [0, 1, 2, 3])
            self.assertEqual(result["pw2_signed40_admission_sha256"],
                             admission_sha)
            self.assertEqual(result["pw2_signed40_proof_sha256"], proof_sha)
            self.assertIn("release-no-ila", result["reject_gate"]["reason"])


if __name__ == "__main__":
    unittest.main()
