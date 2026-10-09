"""Offline contract and future Linux ioctl transport for paired FZVA/ABI10.

The pure validation helpers are usable before packaging. Constructing the
real transport requires an explicit parameter-manifest identity and rejects
anything except the frozen FZVA/ABI10/0x7ff guard identity. Register offsets,
address maps, and deployment receipts remain separate release gates.
"""

import struct

try:
    import cnn_ddr_v6_runtime as v6
except ImportError:
    from . import cnn_ddr_v6_runtime as v6


CORE_ID = 0x465A5641
CORE_ABI = 0x000A0001
SOFTWARE_ABI = 10
GUARD_CAPS = 0x000007ff
PROFILE_COUNT = 3
WORD_BYTES = 16
SCRATCH_WORDS = 4096

PROFILE_MAX_BLOCKS = (12, 20, 4, 0, 0, 0, 0)
PROFILE_CHANNELS = (128, 256, 64, 0, 0, 0, 0)
PROFILE_WIDTHS = (32, 16, 64, 0, 0, 0, 0)
PROFILE_STRIDE_WORDS = (21081, 59705, 10985, 0, 0, 0, 0)
PROFILE_SLOT_WORDS = (16384, 8192, 32768)
PROFILE_ARENA_WORDS = (36864, 20480, 69632)

CAP_SIX_M_AXI = 1 << 2
_SUBMIT_STRUCT = struct.Struct("<8I")
_UINT32_MAX = 0xffffffff


def _uint32(value, label):
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= _UINT32_MAX:
        raise ValueError("%s must be uint32" % label)
    return value


def profile_contract(profile, block_count):
    if isinstance(profile, bool) or not isinstance(profile, int) or not 0 <= profile < 3:
        raise ValueError("FZVA supports only profiles 0..2")
    if (isinstance(block_count, bool) or not isinstance(block_count, int) or
            not 1 <= block_count <= PROFILE_MAX_BLOCKS[profile]):
        raise ValueError("invalid FZVA block count")
    slot_words = PROFILE_SLOT_WORDS[profile]
    arena_words = PROFILE_ARENA_WORDS[profile]
    if arena_words != 2 * slot_words + SCRATCH_WORDS:
        raise AssertionError("internal V10 arena contract is inconsistent")
    return {
        "profile": profile,
        "block_count": block_count,
        "params_words": PROFILE_STRIDE_WORDS[profile] * block_count,
        "params_bytes": PROFILE_STRIDE_WORDS[profile] * block_count * WORD_BYTES,
        "slot_words": slot_words,
        "slot_bytes": slot_words * WORD_BYTES,
        "arena_words": arena_words,
        "arena_bytes": arena_words * WORD_BYTES,
        "scratch_words": SCRATCH_WORDS,
        "output_offset_bytes": (block_count & 1) * slot_words * WORD_BYTES,
    }


def validate_submission(allocations, profile, block_count, params_handle,
                        activation_a_handle, activation_b_handle,
                        activation_a_base_offset_bytes=0,
                        activation_b_base_offset_bytes=0, reserved=0):
    """Validate the frozen 32-byte submit without touching hardware."""
    contract = profile_contract(profile, block_count)
    handles = (params_handle, activation_a_handle, activation_b_handle)
    for index, handle in enumerate(handles):
        _uint32(handle, ("params", "activation_a", "activation_b")[index] + " handle")
        if not handle or handle not in allocations:
            raise ValueError("unknown FZVA allocation handle")
    if len(set(handles)) != 3:
        raise ValueError("params, activation A, and activation B handles must be distinct")
    if reserved != 0:
        raise ValueError("FZVA submit reserved field must be zero")
    if allocations[params_handle]["bytes"] != contract["params_bytes"]:
        raise ValueError("parameter allocation does not match exact V10 extent")
    for label, handle, base in (
            ("A", activation_a_handle, activation_a_base_offset_bytes),
            ("B", activation_b_handle, activation_b_base_offset_bytes)):
        if (isinstance(base, bool) or not isinstance(base, int) or base < 0 or base & 15):
            raise ValueError("activation %s base must be non-negative and 16-byte aligned" % label)
        extent = allocations[handle]["bytes"]
        if base > extent or contract["arena_bytes"] > extent - base:
            raise ValueError("activation %s allocation lacks the exact V10 arena extent" % label)
    result = dict(contract)
    result.update({
        "params_handle": params_handle,
        "activation_a_handle": activation_a_handle,
        "activation_b_handle": activation_b_handle,
        "activation_a_base_offset_bytes": activation_a_base_offset_bytes,
        "activation_b_base_offset_bytes": activation_b_base_offset_bytes,
        "input_a_offset_bytes": activation_a_base_offset_bytes,
        "input_b_offset_bytes": activation_b_base_offset_bytes,
        "output_a_offset_bytes": (activation_a_base_offset_bytes +
                                  contract["output_offset_bytes"]),
        "output_b_offset_bytes": (activation_b_base_offset_bytes +
                                  contract["output_offset_bytes"]),
    })
    return result


class LinuxIoctlV10Transport(v6.LinuxIoctlV6Transport):
    """ABI10 transport, gated on packaged guard and parameter identities."""

    CORE_ID = CORE_ID
    CORE_ABI = CORE_ABI
    ABI_VERSION = SOFTWARE_ABI
    CAP_SIX_M_AXI = CAP_SIX_M_AXI

    def __init__(self, device_path="/dev/network10_v10", *,
                 expected_parameter_manifest_words=None,
                 fd=None, ioctl_callable=None):
        if expected_parameter_manifest_words is None:
            raise ValueError("V10 parameter manifest identity is required")
        super().__init__(
            device_path=device_path,
            expected_parameter_manifest_words=expected_parameter_manifest_words,
            fd=fd,
            ioctl_callable=ioctl_callable)

    def _validate_identity(self):
        identity = self.identity
        expected = {
            "core_id": CORE_ID,
            "core_abi": CORE_ABI,
            "guard_caps": GUARD_CAPS,
            "abi_version": SOFTWARE_ABI,
            "address_bits": 40,
            "data_bits": 128,
            "profile_count": PROFILE_COUNT,
            "max_blocks": PROFILE_MAX_BLOCKS,
            "channels": PROFILE_CHANNELS,
            "widths": PROFILE_WIDTHS,
            "block_stride_words": PROFILE_STRIDE_WORDS,
            "reserved0": 0,
            "parameter_manifest_words": self.expected_parameter_manifest_words,
        }
        for name, wanted in expected.items():
            if identity.get(name) != wanted:
                raise v6.V6NotReady("FZVA driver identity %s mismatch" % name)
        known = self.CAP_LOW_ARENA | self.CAP_HIGH_ARENA | self.CAP_SIX_M_AXI
        required = self.CAP_LOW_ARENA | self.CAP_SIX_M_AXI
        if identity["caps"] & ~known or identity["caps"] & required != required:
            raise v6.V6NotReady("FZVA arena/six-master capabilities mismatch")
        high = bool(identity["caps"] & self.CAP_HIGH_ARENA)
        if (identity["arena_count"] != (2 if high else 1) or
                identity["arena_bytes"] != (
                    self.LOW_ARENA_BYTES,
                    self.HIGH_ARENA_BYTES if high else 0)):
            raise v6.V6NotReady("FZVA driver arena identity mismatch")

    def submit(self, profile, block_count, params_handle,
               activation_a_handle, activation_b_handle,
               activation_a_base_offset_bytes=0,
               activation_b_base_offset_bytes=0, reserved=0):
        descriptor = validate_submission(
            self.allocations, profile, block_count, params_handle,
            activation_a_handle, activation_b_handle,
            activation_a_base_offset_bytes,
            activation_b_base_offset_bytes, reserved)
        if self.quiesced:
            raise v6.V6NotReady("SUBMIT is unavailable after QUIESCE")
        before = self._validate_status(self.get_status(), expected_flags=0)
        mode_switch = bool(before["completed_frames"] and before["profile"] != profile)
        expected_generation = ((before["reset_generation"] +
                                (1 if mode_switch else 0)) & _UINT32_MAX)
        with self._generation_lock:
            if (self._inflight_generation is not None or
                    self._pending_completion is not None or
                    before["reset_generation"] != self._accepted_reset_generation):
                raise v6.V6NotReady("unexpected FZVA reset generation before submit")
            self._inflight_generation = (
                before["reset_generation"], expected_generation, profile)
        raw = bytearray(_SUBMIT_STRUCT.pack(
            profile, block_count, params_handle,
            activation_a_handle, activation_b_handle,
            activation_a_base_offset_bytes,
            activation_b_base_offset_bytes, reserved))
        request = v6._iow(0x45, _SUBMIT_STRUCT.size)
        try:
            self._ioctl(request, raw)
        except Exception:
            with self._generation_lock:
                self._inflight_generation = None
            raise
        self._pending_completion = (
            before, profile, mode_switch, expected_generation)
        return descriptor


__all__ = [
    "CORE_ID", "CORE_ABI", "SOFTWARE_ABI", "GUARD_CAPS", "PROFILE_COUNT", "WORD_BYTES",
    "SCRATCH_WORDS", "PROFILE_MAX_BLOCKS", "PROFILE_CHANNELS",
    "PROFILE_WIDTHS", "PROFILE_STRIDE_WORDS", "PROFILE_SLOT_WORDS",
    "PROFILE_ARENA_WORDS", "CAP_SIX_M_AXI", "profile_contract",
    "validate_submission", "LinuxIoctlV10Transport",
]
