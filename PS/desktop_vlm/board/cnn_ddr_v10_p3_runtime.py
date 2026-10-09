"""Linux ioctl transport for the isolated FZVA/ABI10.2 P3 candidate.

This module keeps the 200-byte ABI10 identity wire unchanged while gating on
profile 3 and the distinct /dev/network10_v10_p3 candidate device.
"""

import struct

try:
    import cnn_ddr_v10_runtime as v10
    import cnn_ddr_v6_runtime as v6
except ImportError:
    from . import cnn_ddr_v10_runtime as v10
    from . import cnn_ddr_v6_runtime as v6


DEVICE_PATH = "/dev/network10_v10_p3"
DRIVER_NAME = "cnn_ddr_v10_p3_candidate"
COMPATIBLE = "fz3b,cnn-ddr-v10-p3-candidate"
CORE_ID = 0x465A5641
CORE_ABI = 0x000A0002
SOFTWARE_ABI = 10
GUARD_CAPS = 0x000007ff
PROFILE_COUNT = 4
PROFILE_SLOTS = 7
WORD_BYTES = 16
SCRATCH_WORDS = 4096

PROFILE_MAX_BLOCKS = (12, 20, 4, 1, 0, 0, 0)
PROFILE_CHANNELS = (128, 256, 64, 64, 0, 0, 0)
PROFILE_WIDTHS = (32, 16, 64, 64, 0, 0, 0)
PROFILE_STRIDE_WORDS = (21081, 59705, 10985, 11280, 0, 0, 0)
PROFILE_SLOT_WORDS = (16384, 8192, 32768, 32768)
PROFILE_ARENA_WORDS = (36864, 20480, 69632, 69632)
PROFILE_OUTPUT_WORDS = (16384, 8192, 32768, 16384)
CAP_SIX_M_AXI = 1 << 2
_UINT32_MAX = 0xffffffff
_SUBMIT_STRUCT = struct.Struct("<8I")


def profile_contract(profile, block_count):
    if isinstance(profile, bool) or not isinstance(profile, int) or not 0 <= profile < PROFILE_COUNT:
        raise ValueError("P3 candidate supports only profiles 0..3")
    if (isinstance(block_count, bool) or not isinstance(block_count, int) or
            not 1 <= block_count <= PROFILE_MAX_BLOCKS[profile]):
        raise ValueError("invalid P3 candidate block count")
    stride = PROFILE_STRIDE_WORDS[profile]
    slot_words = PROFILE_SLOT_WORDS[profile]
    arena_words = PROFILE_ARENA_WORDS[profile]
    if arena_words != 2 * slot_words + SCRATCH_WORDS:
        raise AssertionError("internal P3 arena contract is inconsistent")
    output_offset_bytes = (0 if profile == 3 else
                           (block_count & 1) * slot_words * WORD_BYTES)
    output_words = PROFILE_OUTPUT_WORDS[profile]
    return {
        "profile": profile,
        "block_count": block_count,
        "params_words": stride * block_count,
        "params_bytes": stride * block_count * WORD_BYTES,
        "slot_words": slot_words,
        "slot_bytes": slot_words * WORD_BYTES,
        "arena_words": arena_words,
        "arena_bytes": arena_words * WORD_BYTES,
        "scratch_words": SCRATCH_WORDS,
        "input_words": slot_words,
        "input_bytes": slot_words * WORD_BYTES,
        "output_words": output_words,
        "output_bytes": output_words * WORD_BYTES,
        "output_offset_bytes": output_offset_bytes,
    }


def validate_submission(allocations, profile, block_count, params_handle,
                        activation_a_handle, activation_b_handle,
                        activation_a_base_offset_bytes=0,
                        activation_b_base_offset_bytes=0, reserved=0):
    """Validate the frozen ABI10 submit against live opaque allocations.

    Activation allocations may be larger than a profile's required arena, so a
    caller can keep the same A/B handles while submitting P2, P3, then P0.
    The selected extent and initialized input are still profile-exact.
    """
    contract = profile_contract(profile, block_count)
    handles = (params_handle, activation_a_handle, activation_b_handle)
    for index, handle in enumerate(handles):
        if (isinstance(handle, bool) or not isinstance(handle, int) or
                not 0 <= handle <= _UINT32_MAX or not handle or handle not in allocations):
            raise ValueError("unknown P3 candidate %s allocation handle" %
                             ("params", "activation A", "activation B")[index])
    if len(set(handles)) != 3:
        raise ValueError("params, activation A, and activation B handles must be distinct")
    if isinstance(reserved, bool) or reserved != 0:
        raise ValueError("P3 candidate submit reserved field must be zero")
    if allocations[params_handle]["bytes"] != contract["params_bytes"]:
        raise ValueError("parameter allocation does not match exact P3/V10 extent")
    bases = (activation_a_base_offset_bytes, activation_b_base_offset_bytes)
    for label, handle, base in zip(("A", "B"), handles[1:], bases):
        if (isinstance(base, bool) or not isinstance(base, int) or base < 0 or base & 15):
            raise ValueError("activation %s base must be non-negative and 16-byte aligned" % label)
        extent = allocations[handle]["bytes"]
        if base > extent or contract["arena_bytes"] > extent - base:
            raise ValueError("activation %s allocation lacks the exact P3/V10 arena extent" % label)
    result = dict(contract)
    result.update({
        "params_handle": params_handle,
        "activation_a_handle": activation_a_handle,
        "activation_b_handle": activation_b_handle,
        "activation_a_base_offset_bytes": activation_a_base_offset_bytes,
        "activation_b_base_offset_bytes": activation_b_base_offset_bytes,
        "input_a_offset_bytes": activation_a_base_offset_bytes,
        "input_b_offset_bytes": activation_b_base_offset_bytes,
        "output_a_offset_bytes": activation_a_base_offset_bytes + contract["output_offset_bytes"],
        "output_b_offset_bytes": activation_b_base_offset_bytes + contract["output_offset_bytes"],
    })
    return result


class LinuxIoctlV10P3Transport(v10.LinuxIoctlV10Transport):
    """ABI10.2 P3 transport; rejects a base ABI10 driver identity."""

    CORE_ID = CORE_ID
    CORE_ABI = CORE_ABI
    ABI_VERSION = SOFTWARE_ABI
    CAP_SIX_M_AXI = CAP_SIX_M_AXI

    def __init__(self, device_path=DEVICE_PATH, *,
                 expected_parameter_manifest_words=None, fd=None,
                 ioctl_callable=None):
        if device_path != DEVICE_PATH:
            raise ValueError("P3 candidate device must be %s" % DEVICE_PATH)
        if expected_parameter_manifest_words is None:
            raise ValueError("P3 combined parameter manifest identity is required")
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
                raise v6.V6NotReady("P3 driver identity %s mismatch" % name)
        known = self.CAP_LOW_ARENA | self.CAP_HIGH_ARENA | self.CAP_SIX_M_AXI
        required = self.CAP_LOW_ARENA | self.CAP_SIX_M_AXI
        if identity["caps"] & ~known or identity["caps"] & required != required:
            raise v6.V6NotReady("P3 arena/six-master capabilities mismatch")
        high = bool(identity["caps"] & self.CAP_HIGH_ARENA)
        if (identity["arena_count"] != (2 if high else 1) or
                identity["arena_bytes"] != (
                    self.LOW_ARENA_BYTES,
                    self.HIGH_ARENA_BYTES if high else 0)):
            raise v6.V6NotReady("P3 driver arena identity mismatch")

    def submit(self, profile, block_count, params_handle,
               activation_a_handle, activation_b_handle,
               activation_a_base_offset_bytes=0,
               activation_b_base_offset_bytes=0, reserved=0):
        descriptor = validate_submission(
            self.allocations, profile, block_count, params_handle,
            activation_a_handle, activation_b_handle,
            activation_a_base_offset_bytes, activation_b_base_offset_bytes,
            reserved)
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
                raise v6.V6NotReady("unexpected P3 reset generation before submit")
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
    "DEVICE_PATH", "DRIVER_NAME", "COMPATIBLE", "CORE_ID", "CORE_ABI", "SOFTWARE_ABI", "GUARD_CAPS",
    "PROFILE_COUNT", "PROFILE_SLOTS", "WORD_BYTES", "SCRATCH_WORDS",
    "PROFILE_MAX_BLOCKS", "PROFILE_CHANNELS", "PROFILE_WIDTHS",
    "PROFILE_STRIDE_WORDS", "PROFILE_SLOT_WORDS", "PROFILE_ARENA_WORDS",
    "PROFILE_OUTPUT_WORDS", "CAP_SIX_M_AXI", "profile_contract",
    "validate_submission", "LinuxIoctlV10P3Transport",
]


