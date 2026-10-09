"""PW2 signed40 parameter proof and fail-closed runtime admission.

This module is independent of the proven A0004 runtime.  A future narrowed
PW2 candidate must bind a finalized core ABI and combined-manifest identity
before :class:`Signed40ParameterAdmission` can be constructed.
"""
from __future__ import print_function

import hashlib
import json
import pathlib
import threading


SCHEMA = "cnn-v10-pw2-signed40-range-proof-v1"
ADMISSION_SCHEMA = "cnn-v10-pw2-signed40-admission-v1"
CONTRACT_KIND = "pw2_signed40_v1"
STORAGE_SIGNED_BITS = 40
INPUT_ABS_BOUND = 32768
MAX_ABS_BOUND = (1 << (STORAGE_SIGNED_BITS - 1)) - 1
LAYOUT_VERSION = "cnn_v10_pw2_layout_v1"
PENDING_IDENTITY = "PENDING_HARDWARE_FREEZE"


def sha256_bytes(raw):
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path):
    digest = hashlib.sha256()
    with pathlib.Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json_bytes(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _require_hex_sha(value, label):
    if (not isinstance(value, str) or len(value) != 64 or
            any(ch not in "0123456789abcdef" for ch in value)):
        raise ValueError("%s must be a lowercase SHA256" % label)
    return value


def _profile_map(value, label):
    if not isinstance(value, dict) or set(value) != set(("0", "1", "2", "3")):
        raise ValueError("%s must contain profiles 0..3" % label)
    return value


def validate_contract_object(value, require_final_identity=True):
    if not isinstance(value, dict) or value.get("kind") != CONTRACT_KIND:
        raise ValueError("PW2 signed40 contract kind mismatch")
    expected = {
        "storage_signed_bits": STORAGE_SIGNED_BITS,
        "input_code_abs_bound": INPUT_ABS_BOUND,
        "max_abs_bound_inclusive": MAX_ABS_BOUND,
        "bound_formula": "abs(bias)+32768*sumabs(weight)",
        "proof_layout_version": LAYOUT_VERSION,
        "required_guard_cap_bit": 0x00000800,
        "required_guard_caps": 0x00000fff,
    }
    for key, wanted in expected.items():
        if value.get(key) != wanted:
            raise ValueError("PW2 signed40 contract %s mismatch" % key)
    _require_hex_sha(value.get("proof_receipt_sha256"), "proof_receipt_sha256")
    approved = _profile_map(value.get("approved_raw_parameter_sha256_by_profile"),
                            "approved parameter identities")
    for profile, identity in approved.items():
        _require_hex_sha(identity, "profile %s parameter identity" % profile)
    abi = value.get("required_core_abi")
    combined = value.get("required_combined_manifest_sha256")
    if require_final_identity:
        if isinstance(abi, bool) or not isinstance(abi, int) or abi <= 0:
            raise ValueError("final candidate core ABI is required")
        _require_hex_sha(combined, "required_combined_manifest_sha256")
    else:
        if abi != PENDING_IDENTITY:
            if isinstance(abi, bool) or not isinstance(abi, int) or abi <= 0:
                raise ValueError("candidate ABI must be finalized or explicitly pending")
        if combined != PENDING_IDENTITY:
            _require_hex_sha(combined, "required_combined_manifest_sha256")
    return value


def load_admission_manifest(path, expected_sha256, proof_path,
                            expected_proof_sha256, candidate_identity):
    path = pathlib.Path(path)
    proof_path = pathlib.Path(proof_path)
    if sha256_file(path) != _require_hex_sha(expected_sha256, "admission SHA"):
        raise ValueError("PW2 signed40 admission SHA mismatch")
    if sha256_file(proof_path) != _require_hex_sha(expected_proof_sha256, "proof SHA"):
        raise ValueError("PW2 signed40 proof SHA mismatch")
    value = json.loads(path.read_text(encoding="utf-8"))
    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    if value.get("schema") != ADMISSION_SCHEMA or value.get("status") != "PASS":
        raise ValueError("PW2 signed40 admission is not PASS")
    if proof.get("schema") != SCHEMA or proof.get("status") != "PASS":
        raise ValueError("PW2 signed40 proof is not PASS")
    if value.get("proof_receipt_sha256") != expected_proof_sha256:
        raise ValueError("admission does not bind the supplied proof")
    contract = validate_contract_object(value.get("contract"), True)
    if not isinstance(candidate_identity, dict):
        raise ValueError("candidate identity is required")
    if (candidate_identity.get("core_abi") != contract["required_core_abi"] or
            candidate_identity.get("guard_caps") != contract["required_guard_caps"] or
            not (candidate_identity["guard_caps"] &
                 contract["required_guard_cap_bit"]) or
            candidate_identity.get("combined_manifest_sha256") !=
            contract["required_combined_manifest_sha256"] or
            candidate_identity.get("pw2_storage_contract") != CONTRACT_KIND):
        raise ValueError("hardware candidate does not advertise the signed40 contract")
    if proof.get("approved_raw_parameter_sha256_by_profile") != \
            contract["approved_raw_parameter_sha256_by_profile"]:
        raise ValueError("proof and admission approved sets differ")
    return Signed40ParameterAdmission(contract)


class Signed40ParameterAdmission(object):
    """Track full parameter uploads and reject stale/replaced handles.

    The transport candidate calls ``record_upload`` only after the underlying
    upload succeeds and calls ``authorize_submit`` immediately before SUBMIT.
    Any write, partial write, free, or handle reuse invalidates the token.
    """

    def __init__(self, contract):
        self.contract = validate_contract_object(contract, True)
        self._approved = dict(contract["approved_raw_parameter_sha256_by_profile"])
        self._tokens = {}
        self._generation = 0

    def invalidate(self, handle):
        self._tokens.pop(handle, None)

    def record_upload(self, handle, offset, payload, allocation_bytes):
        self.invalidate(handle)
        if (isinstance(handle, bool) or not isinstance(handle, int) or handle <= 0 or
                offset != 0):
            return None
        raw = bytes(payload)
        if len(raw) != allocation_bytes:
            return None
        identity = sha256_bytes(raw)
        matches = [int(profile) for profile, approved in self._approved.items()
                   if approved == identity]
        if len(matches) != 1:
            return None
        self._generation += 1
        token = {"profile": matches[0], "sha256": identity,
                 "bytes": len(raw), "generation": self._generation}
        self._tokens[handle] = token
        return dict(token)

    def authorize_submit(self, profile, handle, allocation_bytes):
        token = self._tokens.get(handle)
        if (token is None or token["profile"] != profile or
                token["bytes"] != allocation_bytes or
                token["sha256"] != self._approved.get(str(profile))):
            raise ValueError("PW2 signed40 parameter handle lacks a live approved token")
        return dict(token)


class Signed40AdmissionTransportMixin(object):
    """Candidate-only MRO hook that binds admission to upload/free/submit."""

    def __init__(self, *args, **kwargs):
        admission = kwargs.pop("pw2_signed40_admission", None)
        if not isinstance(admission, Signed40ParameterAdmission):
            raise ValueError("finalized PW2 signed40 admission is required")
        self.pw2_signed40_admission = admission
        self._pw2_signed40_lock = threading.RLock()
        # A live mapping can outlast a later approved upload.  Conservatively
        # make any mapped handle ineligible for admission until it is freed;
        # this prevents map -> upload -> mutate-through-old-view -> submit.
        self._pw2_signed40_mapped_handles = set()
        super(Signed40AdmissionTransportMixin, self).__init__(*args, **kwargs)

    def upload(self, handle, offset, payload):
        frozen = bytes(payload)
        with self._pw2_signed40_lock:
            self.pw2_signed40_admission.invalidate(handle)
            result = super(Signed40AdmissionTransportMixin, self).upload(
                handle, offset, frozen)
            allocation = self.allocations.get(handle)
            if (allocation is not None and
                    handle not in self._pw2_signed40_mapped_handles):
                self.pw2_signed40_admission.record_upload(
                    handle, offset, frozen, allocation["bytes"])
            return result

    def upload_array(self, handle, offset, array):
        with self._pw2_signed40_lock:
            self.pw2_signed40_admission.invalidate(handle)
            return super(Signed40AdmissionTransportMixin, self).upload_array(
                handle, offset, array)

    def cached_dma_upload(self, handle, offset, array, timeout_ms=2000):
        with self._pw2_signed40_lock:
            self.pw2_signed40_admission.invalidate(handle)
            return super(Signed40AdmissionTransportMixin, self).cached_dma_upload(
                handle, offset, array, timeout_ms)

    def map_arena(self, handle, offset, size, access):
        with self._pw2_signed40_lock:
            self.pw2_signed40_admission.invalidate(handle)
            self._pw2_signed40_mapped_handles.add(handle)
            return super(Signed40AdmissionTransportMixin, self).map_arena(
                handle, offset, size, access)

    def copy_arena(self, source_handle, source_offset, destination_handle,
                   destination_offset, size, *args, **kwargs):
        with self._pw2_signed40_lock:
            self.pw2_signed40_admission.invalidate(destination_handle)
            return super(Signed40AdmissionTransportMixin, self).copy_arena(
                source_handle, source_offset, destination_handle,
                destination_offset, size, *args, **kwargs)

    def free(self, handle):
        with self._pw2_signed40_lock:
            self.pw2_signed40_admission.invalidate(handle)
            result = super(Signed40AdmissionTransportMixin, self).free(handle)
            self._pw2_signed40_mapped_handles.discard(handle)
            return result

    def submit(self, profile, block_count, params_handle,
               activation_a_handle, activation_b_handle, *args, **kwargs):
        with self._pw2_signed40_lock:
            allocation = self.allocations.get(params_handle)
            if allocation is None:
                raise ValueError("unknown parameter allocation")
            self.pw2_signed40_admission.authorize_submit(
                profile, params_handle, allocation["bytes"])
            return super(Signed40AdmissionTransportMixin, self).submit(
                profile, block_count, params_handle, activation_a_handle,
                activation_b_handle, *args, **kwargs)


__all__ = [
    "ADMISSION_SCHEMA", "CONTRACT_KIND", "INPUT_ABS_BOUND", "LAYOUT_VERSION",
    "MAX_ABS_BOUND", "PENDING_IDENTITY", "SCHEMA", "STORAGE_SIGNED_BITS",
    "Signed40AdmissionTransportMixin", "Signed40ParameterAdmission",
    "canonical_json_bytes", "load_admission_manifest", "sha256_bytes",
    "sha256_file", "validate_contract_object",
]
