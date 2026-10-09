import errno
import hashlib
import json
import struct
import tempfile
import unittest
from unittest import mock

import cnn_ddr_v10_runtime as runtime
import cnn_v10_wc_live_qualification as qualification
from cnn_pipeline_v10_wc_deployment import (
    LIVE_RECEIPT_SCHEMA, LIVE_RECEIPT_STATUS, LIVE_TRANSFER_GATES, TARGET)


BOOT_ID = "fd395d2a-974c-4a1a-827d-568452cd8488"


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _small_contract(profile, blocks):
    return {"profile": profile, "block_count": blocks,
            "params_bytes": 48, "slot_bytes": 32,
            "arena_bytes": 160, "output_offset_bytes": 0}


def _fake_cases():
    cases = []
    for profile, blocks in ((2, 4), (0, 12), (1, 20)):
        images = []
        for index in range(2):
            input_bytes = bytes([profile + index + 1]) * 32
            expected = bytes([profile + index + 11]) * 32
            images.append({"sample": "image-%02d" % index,
                           "input": input_bytes,
                           "input_sha256": _sha(input_bytes),
                           "expected": expected,
                           "expected_sha256": _sha(expected)})
        params = bytes([profile + 30]) * 48
        cases.append({"profile": profile, "block_count": blocks,
                      "params": params, "params_sha256": _sha(params),
                      "images": images})
    return {"manifest_sha256": "1" * 64, "cases": cases}


class FakeTransport:
    ALLOC_LOW_ONLY = 1
    ALLOC_HIGH_ONLY = 2

    def __init__(self, cases):
        self.allocations = {}
        self.memory = {}
        self.invalidated = set()
        self.next_handle = 1
        self.cases = cases
        self.submitted = []
        self.bad_uploads = 0
        self.closed = False
        self.quiesced = False

    def alloc(self, size, alignment=16, flags=0):
        handle = self.next_handle
        self.next_handle += 1
        arena = 0 if flags == self.ALLOC_LOW_ONLY else (
            1 if flags == self.ALLOC_HIGH_ONLY else 0)
        self.allocations[handle] = {"bytes": size, "arena_index": arena,
                                    "flags": flags}
        self.memory[handle] = bytearray(size)
        return handle

    def upload(self, handle, offset, payload):
        payload = bytes(payload)
        self.memory[handle][offset:offset + len(payload)] = payload
        self.invalidated.discard((handle, offset, len(payload)))

    def _ioctl(self, request, raw):
        if request != runtime.v6.IOCTL_REQUESTS["UPLOAD"]:
            raise AssertionError("unexpected ioctl in fake transport")
        handle, reserved, offset, size, pointer = runtime.v6._TRANSFER_STRUCT.unpack(raw)
        if reserved or pointer != 1:
            raise AssertionError("bad-pointer probe descriptor changed")
        self.bad_uploads += 1
        self.invalidated.add((handle, offset, size))
        raise OSError(errno.EFAULT, "injected copy_from_user failure")

    def download(self, handle, offset, size):
        if (handle, offset, size) in self.invalidated:
            raise OSError(getattr(errno, "ENODATA", 61), "uninitialized range")
        return bytes(self.memory[handle][offset:offset + size])

    def submit(self, profile, block_count, params, a, b, a_base, b_base):
        case = self.cases[len(self.submitted)]
        if case["profile"] != profile or case["block_count"] != block_count:
            raise AssertionError("unexpected profile sequence")
        self.memory[a][a_base:a_base + 32] = case["images"][0]["expected"]
        self.memory[b][b_base:b_base + 32] = case["images"][1]["expected"]
        result = {"profile": profile, "a_base": a_base, "b_base": b_base}
        self.submitted.append(result)
        return result

    def wait_complete(self, profile, timeout_s):
        return {"profile": profile, "completed": True}

    def close(self):
        self.quiesced = True
        self.closed = True
        return {"quiesce_confirmed": True, "all_handles_freed": True,
                "transport_closed": True}


class V10WCLiveQualificationTests(unittest.TestCase):
    def test_three_frozen_profiles_and_failed_copy_retry_derive_all_gates(self):
        cases = _fake_cases()
        transport = FakeTransport(cases["cases"])
        with mock.patch.object(qualification.runtime, "profile_contract",
                               _small_contract):
            result = qualification.run_qualification(
                transport, {"parameter_contract": {"profiles": {}}}, cases, 1.0)
        self.assertEqual([item["profile"] for item in result["case_results"]], [2, 0, 1])
        self.assertEqual([item["block_count"] for item in result["case_results"]], [4, 12, 20])
        self.assertTrue(all(result["gate_evidence"].values()))
        self.assertEqual(transport.bad_uploads, 3)
        self.assertEqual(len(transport.submitted), 3)
        for case, item in zip(cases["cases"], result["case_results"]):
            self.assertEqual(item["params_bytes"], len(case["params"]))
            self.assertTrue(item["params_readback_exact"])
            self.assertTrue(item["output_a_exact"] and item["output_b_exact"])
            self.assertTrue(all(item["canaries_before"].values()))
            self.assertTrue(all(item["canaries_after"].values()))
            self.assertFalse(item["scratch_inspected"])
            self.assertTrue(item["bad_user_pointer"][
                "transfer_refs_zero_after_error"])
            self.assertEqual(item["activation_a_arena_index"], 0)
            self.assertEqual(item["activation_b_arena_index"], 1)
            self.assertEqual(item["activation_allocation_bytes"],
                             item["activation_arena_bytes"] + 2 * qualification.CANARY_BYTES)

    def test_profile_one_exact_parameter_extent_is_19105600_bytes(self):
        self.assertEqual(runtime.profile_contract(1, 20)["params_bytes"], 19105600)

    def test_receipt_has_only_helper_contract_fields_and_details_are_sidecar(self):
        with tempfile.TemporaryDirectory() as directory:
            output = directory + "/live.json"
            evidence = dict((name, True) for name in LIVE_TRANSFER_GATES)
            details = {"boot_id_end": BOOT_ID, "transport_close_ok": True,
                       "case_results": [{"profile": 2, "output_a_exact": True}]}
            receipt, sidecar = qualification.write_receipts(
                output, BOOT_ID, "a" * 64, "b" * 64, evidence, details)
            self.assertEqual(receipt["schema"], LIVE_RECEIPT_SCHEMA)
            self.assertEqual(receipt["status"], LIVE_RECEIPT_STATUS)
            self.assertEqual(set(receipt), {"schema", "status", "target", "boot_id",
                             "driver_module_sha256", "dtbo_sha256", "completed_live_gates"})
            self.assertEqual(receipt["target"], TARGET)
            self.assertTrue(all(receipt["completed_live_gates"].values()))
            sidecar_value = json.loads(sidecar.read_text(encoding="utf-8"))
            self.assertEqual(sidecar_value["case_results"], details["case_results"])

    def test_failed_close_forces_fail_status_and_gate_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            evidence = dict((name, True) for name in LIVE_TRANSFER_GATES)
            details = {"boot_id_end": BOOT_ID, "transport_close_ok": False}
            receipt, unused_sidecar = qualification.write_receipts(
                directory + "/failed.json", BOOT_ID, "a" * 64, "b" * 64,
                evidence, details)
            self.assertNotEqual(receipt["status"], LIVE_RECEIPT_STATUS)
            self.assertFalse(receipt["completed_live_gates"][LIVE_TRANSFER_GATES[2]])

    def test_loader_rejects_unexpected_fixture_manifest_sha(self):
        with self.assertRaisesRegex(ValueError, "not the frozen"):
            qualification.load_frozen_fixtures(
                ".", "0" * 64, {}, ".")

    def test_record_path_accepts_string_asset_root_for_relocated_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            artifact = qualification.pathlib.Path(directory) / "artifacts" / "fixture.bin"
            artifact.parent.mkdir(parents=True)
            payload = b"relocated-fixture"
            artifact.write_bytes(payload)
            record = {"path": "Z:/old/artifacts/fixture.bin",
                      "bytes": len(payload), "sha256": _sha(payload)}
            raw, resolved = qualification._record_path(
                qualification.pathlib.Path(directory), record, "relocated", directory)
            self.assertEqual(raw, payload)
            self.assertEqual(resolved, artifact.resolve())


if __name__ == "__main__":
    unittest.main()
