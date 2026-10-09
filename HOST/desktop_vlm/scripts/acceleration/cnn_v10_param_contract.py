"""Host-side FZVA/ABI10 parameter and invocation contract.

V10 keeps the frozen FZV5 numeric fields, repacks pointwise weights into
4-output by 16-reduction tiles, and stores only the aligned programmable
middle of each fixed-model GELU table.  This module contains no board I/O.
"""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np


CORE_IDENTITY = 0x465A5641  # "FZVA"
ABI_IDENTITY = 0x000A0001
SOFTWARE_IDENTITY = "sw10.1"
GELU_ENTRIES = 65536
GELU_STORAGE_ENTRIES = 56256
GELU_STORAGE_BYTES = GELU_STORAGE_ENTRIES * 2
GELU_STORAGE_WORDS = GELU_STORAGE_BYTES // 16
RESIDUAL_RING_WORDS = 4096

PROFILE_CONFIG = {
    0: {"channels": 128, "width": 32, "max_blocks": 12, "slot_words": 16384},
    1: {"channels": 256, "width": 16, "max_blocks": 20, "slot_words": 8192},
    2: {"channels": 64, "width": 64, "max_blocks": 4, "slot_words": 32768},
}

_GELU_ZERO = {
    0: (15136, 7424, 7109, 1949, 0, 0, 2420, 0, 0, 6159, 4602, 25501),
    1: (1756, 4433, 6077, 6559, 8485, 10116, 9466, 11635, 8084, 5675,
        0, 292, 4914, 13445, 11670, 17357, 19327, 18908, 19032, 19136),
    2: (25496, 16299, 13211, 17193),
}
_GELU_TAIL = {
    0: (52936, 48646, 48845, 53151, 49881, 48536, 47407, 53999, 50477,
        45132, 49941, 38148),
    1: (48704, 51761, 54883, 52628, 53218, 49106, 50628, 56097, 53282,
        48134, 56252, 53479, 56320, 57196, 50287, 50325, 51714, 52132,
        59373, 61454),
    2: (50236, 55552, 49509, 52328),
}


@dataclass(frozen=True)
class GeluBound:
    zero_prefix: int
    tail_start: int

    @property
    def load_begin(self) -> int:
        return self.zero_prefix & ~7

    @property
    def load_end(self) -> int:
        return (self.tail_start + 7) & ~7

    @property
    def load_entries(self) -> int:
        return self.load_end - self.load_begin

    @property
    def load_words(self) -> int:
        return self.load_entries // 8


def profile_config(profile: int) -> dict[str, int]:
    try:
        return dict(PROFILE_CONFIG[int(profile)])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"unsupported V10 profile {profile}") from exc


def gelu_bound(profile: int, block: int) -> GeluBound:
    cfg = profile_config(profile)
    b = int(block)
    if b < 0 or b >= cfg["max_blocks"]:
        raise ValueError(f"invalid V10 block {block} for profile {profile}")
    result = GeluBound(_GELU_ZERO[int(profile)][b], _GELU_TAIL[int(profile)][b])
    if result.load_entries > GELU_STORAGE_ENTRIES:
        raise AssertionError("fixed GELU bound exceeds V10 compact slot")
    return result


def pw_tile_count(outputs: int, inputs: int) -> int:
    if outputs <= 0 or outputs % 4 or inputs <= 0 or inputs % 16:
        raise ValueError("V10 PW dimensions must be O%4==0 and I%16==0")
    return (outputs // 4) * (inputs // 16)


def pack_pw4x16(matrix: np.ndarray, outputs: int, inputs: int) -> bytes:
    a = np.asarray(matrix)
    if a.shape != (outputs, inputs) or a.dtype != np.dtype("<i2"):
        raise ValueError("V10 PW matrix must be little-endian int16 OI")
    pw_tile_count(outputs, inputs)
    chunks = []
    for group in range(outputs // 4):
        for red in range(inputs // 16):
            chunks.append(np.ascontiguousarray(
                a[group * 4:(group + 1) * 4, red * 16:(red + 1) * 16],
                dtype="<i2").tobytes())
    return b"".join(chunks)


def unpack_pw4x16(payload: bytes | bytearray | memoryview,
                   outputs: int, inputs: int) -> np.ndarray:
    tiles = pw_tile_count(outputs, inputs)
    raw = memoryview(payload)
    if len(raw) != tiles * 128:
        raise ValueError(f"V10 PW payload has {len(raw)} bytes, expected {tiles * 128}")
    packed = np.frombuffer(raw, dtype="<i2").reshape(tiles, 4, 16)
    result = np.empty((outputs, inputs), dtype="<i2")
    tile = 0
    for group in range(outputs // 4):
        for red in range(inputs // 16):
            result[group * 4:(group + 1) * 4,
                   red * 16:(red + 1) * 16] = packed[tile]
            tile += 1
    return result


def pack_pw2_r_group_4x16(matrix: np.ndarray, outputs: int, inputs: int) -> bytes:
    """Pack PW2 with reduction tile outer and four-output group inner."""
    a = np.asarray(matrix)
    if a.shape != (outputs, inputs) or a.dtype != np.dtype("<i2"):
        raise ValueError("V10.1 PW2 matrix must be little-endian int16 OI")
    pw_tile_count(outputs, inputs)
    chunks = []
    for red in range(inputs // 16):
        for group in range(outputs // 4):
            chunks.append(np.ascontiguousarray(
                a[group * 4:(group + 1) * 4, red * 16:(red + 1) * 16],
                dtype="<i2").tobytes())
    return b"".join(chunks)


def unpack_pw2_r_group_4x16(payload: bytes | bytearray | memoryview,
                            outputs: int, inputs: int) -> np.ndarray:
    """Decode the V10.1 PW2 order for host-only verification."""
    tiles = pw_tile_count(outputs, inputs)
    raw = memoryview(payload)
    if len(raw) != tiles * 128:
        raise ValueError(f"V10.1 PW2 payload has {len(raw)} bytes, expected {tiles * 128}")
    packed = np.frombuffer(raw, dtype="<i2").reshape(tiles, 4, 16)
    result = np.empty((outputs, inputs), dtype="<i2")
    tile = 0
    for red in range(inputs // 16):
        for group in range(outputs // 4):
            result[group * 4:(group + 1) * 4,
                   red * 16:(red + 1) * 16] = packed[tile]
            tile += 1
    return result


def unpack_v5_pw6x16(payload: bytes | bytearray | memoryview,
                     outputs: int, inputs: int) -> np.ndarray:
    if inputs <= 0 or inputs % 16:
        raise ValueError("FZV5 PW input dimension must be divisible by 16")
    groups = (outputs + 5) // 6
    tiles = groups * (inputs // 16)
    raw = memoryview(payload)
    if len(raw) != tiles * 192:
        raise ValueError(f"FZV5 PW payload has {len(raw)} bytes, expected {tiles * 192}")
    packed = np.frombuffer(raw, dtype="<i2").reshape(tiles, 6, 16)
    result = np.empty((outputs, inputs), dtype="<i2")
    tile = 0
    for group in range(groups):
        valid = min(6, outputs - group * 6)
        for red in range(inputs // 16):
            result[group * 6:group * 6 + valid,
                   red * 16:(red + 1) * 16] = packed[tile, :valid]
            tile += 1
    return result


def v5_layout(channels: int) -> dict[str, tuple[int, int]]:
    c = int(channels)
    if c not in (64, 128, 256):
        raise ValueError("channels must be 64, 128, or 256")
    pw1_tiles = ((3 * c + 5) // 6) * (c // 16)
    pw2_tiles = ((c + 5) // 6) * (3 * c // 16)
    fields = {}
    at = 0
    for name, size in (
        ("dw3", 18 * c), ("dw7", 98 * c), ("bias", 48 * c),
        ("multiplier", 24 * c), ("shift", 24 * c),
        ("scale_multiplier", 4 * c), ("scale_shift", 4 * c),
        ("residual", 16), ("gelu", 131072),
        ("pw1", 192 * pw1_tiles), ("pw2", 192 * pw2_tiles),
    ):
        fields[name] = (at, size)
        at += size
    fields["stride"] = (0, at)
    return fields


def v10_layout(channels: int) -> dict[str, tuple[int, int]]:
    c = int(channels)
    if c not in (64, 128, 256):
        raise ValueError("channels must be 64, 128, or 256")
    fields = {}
    at = 0
    for name, size in (
        ("dw3", 18 * c), ("dw7", 98 * c), ("bias", 48 * c),
        ("multiplier", 24 * c), ("shift", 24 * c),
        ("scale_multiplier", 4 * c), ("scale_shift", 4 * c),
        ("residual", 16), ("gelu_compact", GELU_STORAGE_BYTES),
        ("pw1", 6 * c * c), ("pw2", 6 * c * c),
    ):
        if at % 16 or size % 16:
            raise AssertionError(f"unaligned V10 field {name}")
        fields[name] = (at, size)
        at += size
    fields["stride"] = (0, at)
    return fields


def stride_words(channels: int) -> int:
    return v10_layout(channels)["stride"][1] // 16


def arena_words(profile: int) -> int:
    cfg = profile_config(profile)
    return 2 * cfg["slot_words"] + RESIDUAL_RING_WORDS


def validate_invocation(profile: int, block_count: int, params_words: int,
                        slot_words: int, supplied_arena_words: int,
                        flags: int) -> None:
    cfg = profile_config(profile)
    blocks = int(block_count)
    if blocks <= 0 or blocks > cfg["max_blocks"]:
        raise ValueError("V10 block_count is outside the profile contract")
    expected_params = blocks * stride_words(cfg["channels"])
    if int(params_words) != expected_params:
        raise ValueError(f"V10 params_words {params_words} != {expected_params}")
    if int(slot_words) != cfg["slot_words"]:
        raise ValueError(f"V10 slot_words {slot_words} != {cfg['slot_words']}")
    expected_arena = 2 * cfg["slot_words"] + RESIDUAL_RING_WORDS
    if int(supplied_arena_words) != expected_arena:
        raise ValueError(f"V10 arena_words {supplied_arena_words} != {expected_arena}")
    if int(flags) != 0:
        raise ValueError("V10 flags must be zero")


def validate_metadata(block: bytes | bytearray | memoryview,
                      profile: int, block_index: int) -> None:
    cfg = profile_config(profile)
    c = cfg["channels"]
    layout = v10_layout(c)
    raw = memoryview(block)
    if len(raw) != layout["stride"][1]:
        raise ValueError("V10 block length does not match stride")

    def array(name: str, dtype: str) -> np.ndarray:
        off, size = layout[name]
        return np.frombuffer(raw[off:off + size], dtype=dtype)

    bias = array("bias", "<i8")
    if np.any(bias < -(1 << 47)) or np.any(bias > (1 << 47) - 1):
        raise ValueError("V10 signed48 bias contract failed")
    for name in ("shift", "scale_shift"):
        shift = array(name, "<i4")
        if np.any(shift < 0) or np.any(shift > 62):
            raise ValueError(f"V10 {name} contract failed")
    residual = array("residual", "<i4")
    if residual.size != 4 or residual[1] < 0 or residual[1] > 62 or np.any(residual[2:] != 0):
        raise ValueError("V10 residual scalar/padding contract failed")

    bound = gelu_bound(profile, block_index)
    compact = array("gelu_compact", "<i2")
    if np.any(compact[bound.load_entries:] != 0):
        raise ValueError("V10 compact GELU unused capacity must be zero")
    aligned = compact[:bound.load_entries]
    left = bound.zero_prefix - bound.load_begin
    right = bound.tail_start - bound.load_begin
    if left and np.any(aligned[:left] != 0):
        raise ValueError("V10 compact GELU aligned prefix is invalid")
    if right < aligned.size and np.any(aligned[right:] != 32767):
        raise ValueError("V10 compact GELU aligned tail is invalid")


def reconstruct_gelu(block: bytes | bytearray | memoryview,
                     profile: int, block_index: int) -> np.ndarray:
    cfg = profile_config(profile)
    layout = v10_layout(cfg["channels"])
    raw = memoryview(block)
    if len(raw) != layout["stride"][1]:
        raise ValueError("V10 block length does not match stride")
    validate_metadata(raw, profile, block_index)
    off, size = layout["gelu_compact"]
    compact = np.frombuffer(raw[off:off + size], dtype="<i2")
    bound = gelu_bound(profile, block_index)
    result = np.empty(GELU_ENTRIES, dtype="<i2")
    result[:bound.zero_prefix] = 0
    result[bound.tail_start:] = 32767
    result[bound.load_begin:bound.load_end] = compact[:bound.load_entries]
    return result

