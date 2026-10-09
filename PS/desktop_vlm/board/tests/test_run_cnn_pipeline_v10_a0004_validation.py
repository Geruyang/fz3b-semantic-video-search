import hashlib
import json
import pathlib
import sys
import tempfile
import unittest


BOARD = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BOARD))

from run_cnn_pipeline_v10_a0004_validation import (  # noqa: E402
    load_fixture_manifest, main, run_exact_reuse_case, run_exact_suite,
    run_reject_case)


class FakeTransport(object):
    def __init__(self, expected_a, expected_b, reject=False,
                 activation_trace=None):
        self.expected_a = expected_a
        self.expected_b = expected_b
        self.reject = reject
        self.activation_trace = activation_trace
        self.memory = {}
        self.next_handle = 1
        self.submit_count = 0
        self.alloc_count = 0
        self.closed = False

    def alloc(self, size):
        handle = self.next_handle
        self.next_handle += 1
        self.alloc_count += 1
        self.memory[handle] = bytearray(size)
        return handle

    def upload(self, handle, offset, payload):
        self.memory[handle][offset:offset + len(payload)] = payload

    def download(self, handle, offset, size):
        return bytes(self.memory[handle][offset:offset + size])

    def get_status(self):
        return {"completed_frames": self.submit_count, "protocol_error": 0,
                "guard_error_flags": 0, "job_cycles": 0}

    def submit(self, profile, blocks, params, arena_a, arena_b):
        self.submit_count += 1
        self.pending = (profile, blocks, arena_a, arena_b)
        return {"profile": profile, "block_count": blocks}

    def wait_complete(self, profile, timeout_s):
        if self.reject:
            raise AssertionError("reject path must not use normal wait_complete")
        unused_profile, unused_blocks, arena_a, arena_b = self.pending
        output = self.expected_a if self.submit_count == 1 else self.expected_b
        other = self.expected_b if self.submit_count == 1 else self.expected_a
        self.memory[arena_a][:len(output)] = output
        self.memory[arena_b][:len(other)] = other
        return {"protocol_error": 0, "guard_error_flags": 0,
                "job_cycles": 1234, "profile": profile}

    def close(self):
        self.closed = True
        self.memory.clear()
        return {"quiesce_confirmed": True, "all_handles_freed": True,
                "transport_closed": True}

    def wait_reject(self, expected_error, timeout_s):
        if not self.reject:
            raise AssertionError("normal path must not use wait_reject")
        return {"protocol_error": expected_error, "guard_error_flags": 0,
                "job_cycles": 0}

    def read_activation_trace(self):
        if self.activation_trace is None:
            raise NotImplementedError
        return dict(self.activation_trace)


class A0004ValidationRunnerTest(unittest.TestCase):
    def test_exact_reuse_checks_words_canary_and_reuses_handles(self):
        slot = 32
        expected_a = bytes(range(slot))
        expected_b = bytes(reversed(range(slot)))
        transport = FakeTransport(expected_a, expected_b)
        result = run_exact_reuse_case(
            transport, profile=3, block_count=1, params=b"p" * 16,
            input_a=b"a" * slot, expected_a=expected_a,
            input_b=b"b" * slot, expected_b=expected_b,
            contract={"params_bytes": 16, "arena_bytes": 64,
                      "input_bytes": slot, "output_bytes": slot,
                      "output_offset_bytes": 0}, timeout_s=1.0)
        self.assertTrue(result["pass"])
        self.assertTrue(result["word_exact"])
        self.assertTrue(result["tail_canary_unchanged"])
        self.assertTrue(result["same_session_swapped_reuse"])
        self.assertEqual(transport.alloc_count, 3)
        self.assertEqual(transport.submit_count, 2)

    def test_exact_rejects_unclean_completion(self):
        class BadCompletion(FakeTransport):
            def wait_complete(self, profile, timeout_s):
                value = super(BadCompletion, self).wait_complete(profile, timeout_s)
                value["guard_error_flags"] = 1
                return value
        expected = bytes(range(32))
        with self.assertRaisesRegex(RuntimeError, "unclean completion"):
            run_exact_reuse_case(
                BadCompletion(expected, bytes(reversed(expected))), 3, 1,
                b"p" * 16, b"a" * 32, expected, b"b" * 32,
                bytes(reversed(expected)),
                {"params_bytes": 16, "arena_bytes": 64,
                 "input_bytes": 32, "output_bytes": 32,
                 "output_offset_bytes": 0}, 1.0)

    def test_word_mismatch_reports_word_and_lane(self):
        expected = bytes(range(32))
        bad = bytearray(expected)
        bad[19] ^= 1
        transport = FakeTransport(bytes(bad), expected)
        with self.assertRaisesRegex(RuntimeError, "word=1 lane=3"):
            run_exact_reuse_case(
                transport, 3, 1, b"p" * 16, b"a" * 32, expected,
                b"b" * 32, expected,
                {"params_bytes": 16, "arena_bytes": 64,
                 "input_bytes": 32, "output_bytes": 32,
                 "output_offset_bytes": 0}, 1.0)

    def test_reject_requires_error2_zero_activation_trace_and_canary(self):
        zeros = {name: 0 for name in (
            "a_feed", "a_dw3", "a_dw7", "a_pw1", "a_pw2", "a_write",
            "b_feed", "b_dw3", "b_dw7", "b_pw1", "b_pw2", "b_write")}
        transport = FakeTransport(b"", b"", reject=True,
                                  activation_trace=zeros)
        result = run_reject_case(
            transport, profile=0, block_count=1,
            corrupted_params=b"x" * 16, arena_bytes=64, timeout_s=1.0)
        self.assertTrue(result["pass"])
        self.assertEqual(result["protocol_error"], 2)
        self.assertTrue(result["activation_trace_zero"])
        self.assertTrue(result["activation_canary_unchanged"])

    def test_reject_fails_closed_without_trace_observability(self):
        transport = FakeTransport(b"", b"", reject=True,
                                  activation_trace=None)
        with self.assertRaisesRegex(RuntimeError, "activation trace"):
            run_reject_case(transport, 0, 1, b"x" * 16, 64, 1.0)

    def test_manifest_loader_binds_contract_extent_and_every_file_sha(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            records = {}
            for name, raw in (("params", b"p" * 16),
                              ("input_a", b"a" * 32),
                              ("expected_a", bytes(range(32))),
                              ("input_b", b"b" * 32),
                              ("expected_b", bytes(reversed(range(32))))):
                path = root / (name + ".bin")
                path.write_bytes(raw)
                records[name] = {"path": path.name, "bytes": len(raw),
                                 "sha256": hashlib.sha256(raw).hexdigest()}
            manifest = {
                "schema": "cnn-v10.4-a0004-board-validation-fixtures-v1",
                "status": "PASS_HOST_FIXTURES_ONLY",
                "core_abi": "0x000A0004",
                "combined_parameter_manifest_sha256": "e285a08615111752f7c71b9541267a8a1f3b7062c9a8cbb36a7bb2b5a609d5c9",
                "cases": [{"profile": 3, "block_count": 1,
                           "contract": {"params_bytes": 16,
                                        "arena_bytes": 64,
                                        "input_bytes": 32,
                                        "output_bytes": 32,
                                        "output_offset_bytes": 0},
                           "files": records}],
            }
            path = root / "manifest.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            loaded = load_fixture_manifest(str(path), digest)
            self.assertEqual(loaded["cases"][0]["files"]["input_a"], b"a" * 32)
            records["input_a"]["sha256"] = "0" * 64
            path.write_text(json.dumps(manifest), encoding="utf-8")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError, "input_a SHA"):
                load_fixture_manifest(str(path), digest)

    def test_exact_suite_derives_contract_and_closes_transport(self):
        expected_a = bytes(range(32))
        expected_b = bytes(reversed(range(32)))
        transport = FakeTransport(expected_a, expected_b)
        fixture = {"manifest_sha256": "1" * 64, "cases": [{
            "profile": 3, "block_count": 1,
            "contract": {"params_bytes": 16, "arena_bytes": 64,
                         "input_bytes": 32, "output_bytes": 32,
                         "output_offset_bytes": 0},
            "files": {"params": b"p" * 16, "input_a": b"a" * 32,
                      "expected_a": expected_a, "input_b": b"b" * 32,
                      "expected_b": expected_b}}]}
        result = run_exact_suite(
            transport, fixture, contract_resolver=lambda p, n: {
                "params_bytes": 16, "arena_bytes": 64, "input_bytes": 32,
                "output_bytes": 32, "output_offset_bytes": 0,
                "slot_words": 2, "residual_offset_words": 4}, timeout_s=1)
        self.assertTrue(result["pass"])
        self.assertTrue(result["cleanup"]["transport_closed"])
        self.assertTrue(transport.closed)

    def test_exact_suite_rejects_manifest_contract_before_allocation(self):
        transport = FakeTransport(b"", b"")
        fixture = {"manifest_sha256": "1" * 64, "cases": [{
            "profile": 0, "block_count": 12,
            "contract": {"params_bytes": 16, "arena_bytes": 64,
                         "input_bytes": 32, "output_bytes": 32,
                         "output_offset_bytes": 0},
            "files": {"params": b"p" * 16, "input_a": b"a" * 32,
                      "expected_a": b"a" * 32, "input_b": b"b" * 32,
                      "expected_b": b"b" * 32}}]}
        with self.assertRaisesRegex(ValueError, "contract differs"):
            run_exact_suite(
                transport, fixture, contract_resolver=lambda p, n: {
                    "params_bytes": 32, "arena_bytes": 64,
                    "input_bytes": 32, "output_bytes": 32,
                    "output_offset_bytes": 0}, timeout_s=1)
        self.assertEqual(transport.alloc_count, 0)
        self.assertTrue(transport.closed)

    def test_cli_requires_all_profiles_and_writes_exclusive_result(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
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
                    records[name] = {
                        "path": path.name, "bytes": len(raw),
                        "sha256": hashlib.sha256(raw).hexdigest()}
                cases.append({
                    "case_id": "profile-%d" % profile,
                    "profile": profile, "block_count": 1,
                    "contract": {"params_bytes": 16, "arena_bytes": 64,
                                 "input_bytes": 32, "output_bytes": 32,
                                 "output_offset_bytes": 0},
                    "files": records})
            manifest = {
                "schema": "cnn-v10.4-a0004-board-validation-fixtures-v1",
                "status": "PASS_HOST_FIXTURES_ONLY",
                "core_abi": "0x000A0004",
                "combined_parameter_manifest_sha256":
                    "e285a08615111752f7c71b9541267a8a1f3b7062c9a8cbb36a7bb2b5a609d5c9",
                "cases": cases}
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            manifest_sha = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
            output = root / "result.json"
            transport = FakeTransport(expected, expected)

            def factory(unused_args):
                return transport, lambda p, n: {
                    "profile": p, "block_count": n,
                    "params_bytes": 16, "arena_bytes": 64,
                    "input_bytes": 32, "output_bytes": 32,
                    "output_offset_bytes": 0, "slot_words": 2}

            rc = main([
                "--fixture-manifest", str(manifest_path),
                "--expected-fixture-manifest-sha256", manifest_sha,
                "--combined-manifest", str(root / "unused-combined.json"),
                "--expected-combined-manifest-sha256",
                "e285a08615111752f7c71b9541267a8a1f3b7062c9a8cbb36a7bb2b5a609d5c9",
                "--output", str(output)], transport_factory=factory)
            self.assertEqual(rc, 0)
            result = json.loads(output.read_text(encoding="utf-8"))
            self.assertFalse(result["hardware_execution"])
            self.assertEqual(result["profiles"], [0, 1, 2, 3])
            self.assertEqual(result["case_count"], 4)
            self.assertEqual(result["reject_gate"]["status"],
                             "NOT_RUN_BY_EXACT_CLI")
            with self.assertRaises(FileExistsError):
                main([
                    "--fixture-manifest", str(manifest_path),
                    "--expected-fixture-manifest-sha256", manifest_sha,
                    "--combined-manifest", str(root / "unused-combined.json"),
                    "--expected-combined-manifest-sha256",
                    "e285a08615111752f7c71b9541267a8a1f3b7062c9a8cbb36a7bb2b5a609d5c9",
                    "--output", str(output)],
                    transport_factory=lambda unused: (
                        FakeTransport(expected, expected), factory(unused)[1]))


if __name__ == "__main__":
    unittest.main()
