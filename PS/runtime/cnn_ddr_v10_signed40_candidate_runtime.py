"""Fail-closed A0005 transport for the PW2 signed40 candidate.

The candidate uses its own isolated A0005 device node.  The live identity
check makes the two ABIs mutually exclusive: an A0004 module is rejected
before any allocation or submission.
"""
from __future__ import print_function

import cnn_ddr_v6_runtime as v6
import cnn_ddr_v10_p3_dma_runtime as dma
from cnn_v10_pw2_signed40_contract import Signed40AdmissionTransportMixin


DEVICE_PATH = "/dev/network10_v10_signed40"
CORE_ID = dma.CORE_ID
CORE_ABI = 0x000A0005
GUARD_CAPS = 0x00000fff
PW2_SIGNED40_CAP_BIT = 0x00000800


class LinuxIoctlV10Signed40CandidateTransport(
        Signed40AdmissionTransportMixin, dma.LinuxIoctlV10P3DmaTransport):
    """A0005 identity plus immutable approved-parameter admission."""

    DEVICE_PATH = DEVICE_PATH
    CORE_ID = CORE_ID
    CORE_ABI = CORE_ABI
    ABI_VERSION = 10

    def __init__(self, *args, **kwargs):
        admission = kwargs.get("pw2_signed40_admission")
        words = kwargs.get("expected_parameter_manifest_words")
        contract = getattr(admission, "contract", None)
        identity = contract.get("required_combined_manifest_sha256") \
            if isinstance(contract, dict) else None
        if not isinstance(identity, str) or len(identity) != 64:
            raise ValueError("A0005 admission lacks a combined manifest identity")
        bound_words = tuple(int(identity[index:index + 8], 16)
                            for index in range(0, 64, 8))
        if tuple(words or ()) != bound_words:
            raise ValueError("A0005 manifest words and admission identity differ")
        super(LinuxIoctlV10Signed40CandidateTransport, self).__init__(
            *args, **kwargs)

    def _validate_identity(self):
        expected = {
            "core_id": CORE_ID,
            "core_abi": CORE_ABI,
            "guard_caps": GUARD_CAPS,
            "abi_version": 10,
            "address_bits": 40,
            "data_bits": 128,
            "profile_count": 4,
            "max_blocks": dma.PROFILE_MAX_BLOCKS,
            "channels": dma.PROFILE_CHANNELS,
            "widths": dma.PROFILE_WIDTHS,
            "block_stride_words": dma.PROFILE_STRIDE_WORDS,
            "reserved0": 0,
            "parameter_manifest_words": self.expected_parameter_manifest_words,
        }
        for name, wanted in expected.items():
            if self.identity.get(name) != wanted:
                raise v6.V6NotReady("A0005 signed40 identity %s mismatch" % name)
        if not (self.identity["guard_caps"] & PW2_SIGNED40_CAP_BIT):
            raise v6.V6NotReady("A0005 signed40 capability bit is absent")
        known = self.CAP_LOW_ARENA | self.CAP_HIGH_ARENA | self.CAP_SIX_M_AXI
        required = self.CAP_LOW_ARENA | self.CAP_SIX_M_AXI
        if (self.identity["caps"] & ~known or
                self.identity["caps"] & required != required):
            raise v6.V6NotReady("A0005 arena/six-master capabilities mismatch")
        high = bool(self.identity["caps"] & self.CAP_HIGH_ARENA)
        if (self.identity["arena_count"] != (2 if high else 1) or
                self.identity["arena_bytes"] !=
                (self.LOW_ARENA_BYTES,
                 self.HIGH_ARENA_BYTES if high else 0)):
            raise v6.V6NotReady("A0005 arena identity mismatch")


def open_signed40_candidate(parameter_bundle, device_path=DEVICE_PATH,
                            **transport_kwargs):
    """Open the candidate using one already strictly loaded parameter bundle."""
    if not isinstance(parameter_bundle, dict):
        raise ValueError("A0005 signed40 parameter bundle is required")
    return LinuxIoctlV10Signed40CandidateTransport(
        device_path=device_path,
        expected_parameter_manifest_words=
            parameter_bundle.get("parameter_manifest_words"),
        pw2_signed40_admission=
            parameter_bundle.get("pw2_signed40_admission"),
        **transport_kwargs)


__all__ = [
    "CORE_ABI", "DEVICE_PATH", "GUARD_CAPS",
    "LinuxIoctlV10Signed40CandidateTransport", "PW2_SIGNED40_CAP_BIT",
    "open_signed40_candidate",
]
