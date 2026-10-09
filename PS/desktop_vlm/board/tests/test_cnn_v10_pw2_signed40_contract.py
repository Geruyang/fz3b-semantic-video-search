from __future__ import print_function

import hashlib
import importlib.util
import json
import pathlib
import struct
import tempfile
import unittest
from unittest import mock


BOARD = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "signed40", str(BOARD / "cnn_v10_pw2_signed40_contract.py"))
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)
AUDIT_SPEC = importlib.util.spec_from_file_location(
    "signed40_audit", str(BOARD.parent / "scripts" / "acceleration" /
                          "audit_cnn_v10_pw2_signed40.py"))
AUDIT = importlib.util.module_from_spec(AUDIT_SPEC)
AUDIT_SPEC.loader.exec_module(AUDIT)
PARAM_SPEC = importlib.util.spec_from_file_location(
    "signed40_params", str(BOARD / "cnn_pipeline_v10_signed40_parameters.py"))
PARAM = importlib.util.module_from_spec(PARAM_SPEC)
PARAM_SPEC.loader.exec_module(PARAM)
CANDIDATE_SPEC = importlib.util.spec_from_file_location(
    "signed40_candidate", str(BOARD /
                              "cnn_ddr_v10_signed40_candidate_runtime.py"))
CANDIDATE = importlib.util.module_from_spec(CANDIDATE_SPEC)
CANDIDATE_SPEC.loader.exec_module(CANDIDATE)


def contract_for(payloads):
    return {
        "kind": MOD.CONTRACT_KIND,
        "storage_signed_bits": 40,
        "input_code_abs_bound": 32768,
        "max_abs_bound_inclusive": (1 << 39) - 1,
        "bound_formula": "abs(bias)+32768*sumabs(weight)",
        "proof_layout_version": MOD.LAYOUT_VERSION,
        "proof_receipt_sha256": "1" * 64,
        "approved_raw_parameter_sha256_by_profile": {
            str(profile): hashlib.sha256(payloads[profile]).hexdigest()
            for profile in range(4)
        },
        "required_core_abi": 0x000A0005,
        "required_guard_cap_bit": 0x800,
        "required_guard_caps": 0xfff,
        "required_combined_manifest_sha256": "2" * 64,
    }


class FakeBase(object):
    def __init__(self, *args, **kwargs):
        self.allocations = {10: {"bytes": 16}, 20: {"bytes": 16},
                            30: {"bytes": 16}}
        self.uploaded = []
        self.submitted = []

    def upload(self, handle, offset, payload):
        self.uploaded.append((handle, offset, bytes(payload)))

    def upload_array(self, handle, offset, array):
        self.uploaded.append((handle, offset, bytes(array)))

    def cached_dma_upload(self, handle, offset, array, timeout_ms=2000):
        self.uploaded.append((handle, offset, bytes(array), timeout_ms))

    def map_arena(self, handle, offset, size, access):
        return (handle, offset, size, access)

    def copy_arena(self, source_handle, source_offset, destination_handle,
                   destination_offset, size, *args, **kwargs):
        return size

    def free(self, handle):
        del self.allocations[handle]

    def submit(self, profile, block_count, params_handle,
               activation_a_handle, activation_b_handle, *args, **kwargs):
        self.submitted.append((profile, params_handle))
        return "submitted"


class CandidateTransport(MOD.Signed40AdmissionTransportMixin, FakeBase):
    pass


class Signed40ContractTests(unittest.TestCase):
    def setUp(self):
        self.payloads = [bytes([profile + 1]) * 16 for profile in range(4)]
        self.contract = contract_for(self.payloads)
        self.admission = MOD.Signed40ParameterAdmission(self.contract)

    def test_full_upload_authorizes_only_matching_profile(self):
        token = self.admission.record_upload(10, 0, self.payloads[0], 16)
        self.assertEqual(token["profile"], 0)
        self.assertEqual(self.admission.authorize_submit(0, 10, 16)["sha256"],
                         hashlib.sha256(self.payloads[0]).hexdigest())
        with self.assertRaisesRegex(ValueError, "lacks a live approved token"):
            self.admission.authorize_submit(1, 10, 16)

    def test_partial_mutated_and_replaced_uploads_fail_closed(self):
        self.admission.record_upload(10, 0, self.payloads[0], 16)
        self.assertIsNone(self.admission.record_upload(10, 0, b"short", 16))
        with self.assertRaises(ValueError):
            self.admission.authorize_submit(0, 10, 16)
        mutated = bytearray(self.payloads[0])
        mutated[-1] ^= 1
        self.assertIsNone(self.admission.record_upload(10, 0, mutated, 16))

    def test_transport_uses_same_frozen_bytes_and_invalidates_other_writes(self):
        transport = CandidateTransport(pw2_signed40_admission=self.admission)
        mutable = bytearray(self.payloads[0])
        transport.upload(10, 0, mutable)
        mutable[0] ^= 1
        self.assertEqual(transport.uploaded[0][2], self.payloads[0])
        self.assertEqual(transport.submit(0, 1, 10, 20, 30), "submitted")
        transport.map_arena(10, 0, 16, 2)
        with self.assertRaisesRegex(ValueError, "lacks a live approved token"):
            transport.submit(0, 1, 10, 20, 30)
        # A mapping can retain a writable view beyond a subsequent upload, so
        # the handle stays ineligible until free instead of being re-approved.
        transport.upload(10, 0, self.payloads[0])
        with self.assertRaisesRegex(ValueError, "lacks a live approved token"):
            transport.submit(0, 1, 10, 20, 30)
        transport.free(10)
        transport.allocations[10] = {"bytes": 16}
        transport.upload(10, 0, self.payloads[0])
        transport.copy_arena(20, 0, 10, 0, 16)
        with self.assertRaises(ValueError):
            transport.submit(0, 1, 10, 20, 30)

    def test_array_and_cached_dma_paths_cannot_authorize_parameters(self):
        transport = CandidateTransport(pw2_signed40_admission=self.admission)
        transport.upload(10, 0, self.payloads[0])
        transport.upload_array(10, 0, self.payloads[0])
        with self.assertRaises(ValueError):
            transport.submit(0, 1, 10, 20, 30)
        transport.upload(10, 0, self.payloads[0])
        transport.cached_dma_upload(10, 0, self.payloads[0])
        with self.assertRaises(ValueError):
            transport.submit(0, 1, 10, 20, 30)

    def test_candidate_identity_and_proof_are_both_required(self):
        with tempfile.TemporaryDirectory() as root_text:
            root = pathlib.Path(root_text)
            proof = {"schema": MOD.SCHEMA, "status": "PASS",
                     "approved_raw_parameter_sha256_by_profile":
                         self.contract["approved_raw_parameter_sha256_by_profile"]}
            proof_path = root / "proof.json"
            proof_path.write_text(json.dumps(proof), encoding="utf-8")
            proof_sha = MOD.sha256_file(proof_path)
            contract = dict(self.contract)
            contract["proof_receipt_sha256"] = proof_sha
            admission = {"schema": MOD.ADMISSION_SCHEMA, "status": "PASS",
                         "proof_receipt_sha256": proof_sha,
                         "contract": contract}
            admission_path = root / "admission.json"
            admission_path.write_text(json.dumps(admission), encoding="utf-8")
            admission_sha = MOD.sha256_file(admission_path)
            identity = {"core_abi": 0x000A0005, "guard_caps": 0xfff,
                        "combined_manifest_sha256": "2" * 64,
                        "pw2_storage_contract": MOD.CONTRACT_KIND}
            loaded = MOD.load_admission_manifest(
                admission_path, admission_sha, proof_path, proof_sha, identity)
            self.assertIsInstance(loaded, MOD.Signed40ParameterAdmission)
            identity["core_abi"] = 0x000A0004
            with self.assertRaisesRegex(ValueError, "does not advertise"):
                MOD.load_admission_manifest(
                    admission_path, admission_sha, proof_path, proof_sha, identity)

    def test_pending_hardware_identity_cannot_be_loaded(self):
        pending = dict(self.contract)
        pending["required_combined_manifest_sha256"] = MOD.PENDING_IDENTITY
        self.assertIs(MOD.validate_contract_object(
            pending, require_final_identity=False), pending)
        with self.assertRaises(ValueError):
            MOD.Signed40ParameterAdmission(pending)

    def test_audit_main_dependencies_are_imported(self):
        self.assertEqual(AUDIT.ADMISSION_SCHEMA, MOD.ADMISSION_SCHEMA)

    def test_profile2_layout_and_bound_are_parsed_per_channel(self):
        spec = AUDIT.PROFILES[2]
        raw = bytearray(spec["blocks"] * spec["stride_words"] * 16)
        bias_at = (spec["bias_offset_words"] * 16) + 5 * 64 * 8
        struct.pack_into("<q", raw, bias_at, -123456)
        weight_at = spec["pw2_weight_offset_words"] * 16
        # normal order is r outer, group inner, then 4 output lanes x 16.
        struct.pack_into("<h", raw, weight_at, -7)
        shift_at = ((spec["bias_offset_words"] + 3 * 64 + 6 * 64 // 4) * 16 +
                    5 * 64 * 4)
        for channel in range(64):
            struct.pack_into("<i", raw, shift_at + channel * 4, 31)
        result = AUDIT.audit_blob(2, bytes(raw))
        self.assertEqual(result["blocks_detail"][0]["channel_bounds"][0],
                         123456 + 32768 * 7)
        self.assertEqual(result["blocks_detail"][0]["channel_bounds"][1], 0)
        self.assertTrue(result["signed40_storage_applies"])

    def test_profile3_layout_is_audited_but_not_narrowed(self):
        spec = AUDIT.PROFILES[3]
        raw = bytearray(spec["stride_words"] * 16)
        for channel in range(128):
            struct.pack_into("<i", raw, 7152 * 16 + channel * 4, 31)
        result = AUDIT.audit_blob(3, bytes(raw))
        self.assertEqual(result["pw2_weight_tile_order"],
                         "p3_pw_group_r_v1")
        self.assertFalse(result["signed40_storage_applies"])

    def test_actual_combined_builder_and_loader_bind_proof_and_admission(self):
        root = BOARD.parents[1]
        source = (root / "artifacts" / "board-debug-20261008" /
                  "acceleration" / "host" /
                  "network10-v10.4-p3-dma-deployment-final-002" /
                  "parameters" / "chain-manifest.json")
        proof = (root / "artifacts" / "board-debug-20261008" /
                 "acceleration" / "host" /
                 "network10-v10.5-pw2-signed40-proof-003" / "proof.json")
        p3_params = (root / "artifacts" / "board-debug-20261008" /
                     "acceleration" / "host" /
                     "network10-v10.4-a0004-validation-payload-004" /
                     "fixtures" / "profile3" / "params.bin")
        with tempfile.TemporaryDirectory() as root_text:
            output = pathlib.Path(root_text) / "candidate"
            receipt = PARAM.build_a0005_combined(
                source, PARAM.SOURCE_A0004_COMBINED_SHA256,
                p3_params, proof, MOD.sha256_file(proof), output)
            loaded = PARAM.load_v10_signed40_parameters(
                output / "manifest.json", receipt["manifest_sha256"],
                output / "admission.json", receipt["admission_sha256"],
                proof, receipt["proof_sha256"])
            self.assertEqual(
                loaded["pw2_signed40_admission"].contract["required_core_abi"],
                0x000A0005)
            self.assertEqual(loaded["parameter_manifest_words"], tuple(
                int(receipt["manifest_sha256"][index:index + 8], 16)
                for index in range(0, 64, 8)))
            tampered = json.loads((output / "manifest.json").read_text(
                encoding="utf-8"))
            tampered["parameter_compatibility"][MOD.CONTRACT_KIND][
                "approved_raw_parameter_sha256_by_profile"]["0"] = "0" * 64
            (output / "manifest.json").write_text(
                json.dumps(tampered, sort_keys=True), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "compatibility mismatch"):
                PARAM.load_v10_signed40_parameters(
                    output / "manifest.json", MOD.sha256_file(
                        output / "manifest.json"),
                    output / "admission.json", receipt["admission_sha256"],
                    proof, receipt["proof_sha256"])

    def test_candidate_transport_rejects_a0004_live_identity(self):
        cls = CANDIDATE.LinuxIoctlV10Signed40CandidateTransport
        transport = cls.__new__(cls)
        transport.expected_parameter_manifest_words = tuple(range(8))
        caps = transport.CAP_LOW_ARENA | transport.CAP_SIX_M_AXI
        transport.identity = {
            "core_id": CANDIDATE.CORE_ID,
            "core_abi": CANDIDATE.CORE_ABI,
            "guard_caps": CANDIDATE.GUARD_CAPS,
            "abi_version": 10,
            "address_bits": 40,
            "data_bits": 128,
            "profile_count": 4,
            "max_blocks": CANDIDATE.dma.PROFILE_MAX_BLOCKS,
            "channels": CANDIDATE.dma.PROFILE_CHANNELS,
            "widths": CANDIDATE.dma.PROFILE_WIDTHS,
            "block_stride_words": CANDIDATE.dma.PROFILE_STRIDE_WORDS,
            "reserved0": 0,
            "parameter_manifest_words": tuple(range(8)),
            "caps": caps,
            "arena_count": 1,
            "arena_bytes": (transport.LOW_ARENA_BYTES, 0),
        }
        transport._validate_identity()
        transport.identity["core_abi"] = 0x000A0004
        with self.assertRaisesRegex(Exception, "core_abi mismatch"):
            transport._validate_identity()

    def test_transport_base_allows_strict_subclass_device_override(self):
        class AlternateDeviceTransport(
                CANDIDATE.dma.LinuxIoctlV10P3A0004Transport):
            DEVICE_PATH = "/dev/network10_v10_signed40"

        with mock.patch.object(
                CANDIDATE.dma.v6.LinuxIoctlV6Transport, "__init__",
                return_value=None) as base_init:
            AlternateDeviceTransport(
                device_path="/dev/network10_v10_signed40",
                expected_parameter_manifest_words=tuple(range(8)))
        base_init.assert_called_once()
        with self.assertRaisesRegex(ValueError, "candidate device"):
            AlternateDeviceTransport(
                device_path="/dev/network10_v10_p3_dma",
                expected_parameter_manifest_words=tuple(range(8)))

    def test_signed40_transport_overrides_candidate_device_path(self):
        self.assertEqual(
            CANDIDATE.LinuxIoctlV10Signed40CandidateTransport.DEVICE_PATH,
            CANDIDATE.DEVICE_PATH)

    def test_candidate_constructor_rejects_mixed_parameter_bundles_pre_open(self):
        with self.assertRaisesRegex(ValueError, "manifest words and admission"):
            CANDIDATE.LinuxIoctlV10Signed40CandidateTransport(
                expected_parameter_manifest_words=tuple(range(8)),
                pw2_signed40_admission=self.admission,
                fd=-1, ioctl_callable=lambda *args: None)


if __name__ == "__main__":
    unittest.main()
