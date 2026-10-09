"""Repack frozen FZV5 raw parameter blocks into the FZVA/ABI10 layout."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import cnn_v10_param_contract as v10


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _slice(raw: memoryview, item: tuple[int, int]) -> memoryview:
    off, size = item
    return raw[off:off + size]


def repack_block(source: bytes | bytearray | memoryview,
                 profile: int, block_index: int) -> bytes:
    cfg = v10.profile_config(profile)
    c = cfg["channels"]
    old = v10.v5_layout(c)
    new = v10.v10_layout(c)
    raw = memoryview(source)
    if len(raw) != old["stride"][1]:
        raise ValueError("FZV5 source block length does not match frozen stride")

    out = bytearray(new["stride"][1])
    for name in ("dw3", "dw7", "bias", "multiplier", "shift",
                 "scale_multiplier", "scale_shift", "residual"):
        if old[name][1] != new[name][1] or old[name][0] != new[name][0]:
            raise AssertionError(f"unexpected non-PW offset change for {name}")
        off, size = new[name]
        out[off:off + size] = _slice(raw, old[name])

    full_gelu = np.frombuffer(_slice(raw, old["gelu"]), dtype="<i2")
    bound = v10.gelu_bound(profile, block_index)
    if np.any(full_gelu[:bound.zero_prefix] != 0):
        raise ValueError(f"profile {profile} block {block_index} GELU prefix is not zero")
    if np.any(full_gelu[bound.tail_start:] != 32767):
        raise ValueError(f"profile {profile} block {block_index} GELU tail is not 32767")
    gelu_off, gelu_size = new["gelu_compact"]
    compact = np.frombuffer(out, dtype="<i2", count=gelu_size // 2,
                            offset=gelu_off)
    compact[:bound.load_entries] = full_gelu[bound.load_begin:bound.load_end]

    pw1 = v10.unpack_v5_pw6x16(_slice(raw, old["pw1"]), 3 * c, c)
    pw2 = v10.unpack_v5_pw6x16(_slice(raw, old["pw2"]), c, 3 * c)
    for name, matrix, outputs, inputs in (
        ("pw1", pw1, 3 * c, c), ("pw2", pw2, c, 3 * c)):
        off, size = new[name]
        packed = (v10.pack_pw4x16(matrix, outputs, inputs) if name == "pw1" else
                  v10.pack_pw2_r_group_4x16(matrix, outputs, inputs))
        if len(packed) != size:
            raise AssertionError(f"V10 {name} packed length mismatch")
        out[off:off + size] = packed

    result = bytes(out)
    v10.validate_metadata(result, profile, block_index)
    if not np.array_equal(v10.reconstruct_gelu(result, profile, block_index), full_gelu):
        raise AssertionError("V10 compact GELU reconstruction mismatch")
    return result


def repack_file(source: Path, output: Path, profile: int, blocks: int) -> dict:
    cfg = v10.profile_config(profile)
    count = int(blocks)
    if count <= 0 or count > cfg["max_blocks"]:
        raise ValueError("blocks outside V10 profile contract")
    source_bytes = source.read_bytes()
    old_stride = v10.v5_layout(cfg["channels"])["stride"][1]
    if len(source_bytes) != count * old_stride:
        raise ValueError(f"source has {len(source_bytes)} bytes, expected {count * old_stride}")
    pieces = []
    for block in range(count):
        pieces.append(repack_block(source_bytes[block * old_stride:(block + 1) * old_stride],
                                   profile, block))
    payload = b"".join(pieces)
    expected = count * v10.v10_layout(cfg["channels"])["stride"][1]
    if len(payload) != expected:
        raise AssertionError("V10 output length mismatch")
    if output.exists():
        raise FileExistsError(f"refusing to overwrite {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(payload)
    return {
        "profile": profile,
        "blocks": count,
        "channels": cfg["channels"],
        "source": {"path": str(source.resolve()), "bytes": len(source_bytes),
                   "sha256": sha256_bytes(source_bytes)},
        "output": {"path": str(output.resolve()), "bytes": len(payload),
                   "sha256": sha256_bytes(payload)},
        "v5_stride_bytes": old_stride,
        "v10_stride_bytes": v10.v10_layout(cfg["channels"])["stride"][1],
        "v10_stride_words": v10.stride_words(cfg["channels"]),
        "pw1_tile_order": "output_group_outer_then_reduction",
        "pw2_tile_order": "reduction_outer_then_output_group",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--profile", type=int, required=True)
    parser.add_argument("--blocks", type=int, required=True)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()
    meta = repack_file(args.source, args.output, args.profile, args.blocks)
    meta.update({"schema": "cnn-v10.1-repack-v1", "core_identity": hex(v10.CORE_IDENTITY),
                 "abi_identity": hex(v10.ABI_IDENTITY),
                 "software_identity": v10.SOFTWARE_IDENTITY,
                 "packer_sha256": sha256_file(Path(__file__))})
    if args.manifest:
        if args.manifest.exists():
            raise FileExistsError(f"refusing to overwrite {args.manifest}")
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        args.manifest.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(meta, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

