#!/usr/bin/env python3
"""Generate independent TSV oracles for the three storage candidates.

This file intentionally contains no candidate imports.  The future native test
binary consumes these vectors through the adapter contract and compares the
candidate mapping/packing results with the frozen values generated here.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from pathlib import Path


SIGNED40_MIN = -(1 << 39)
SIGNED40_MAX = (1 << 39) - 1
MASK40 = (1 << 40) - 1


def pw1_map(bank: int, old_address: int, bank_depth: int) -> tuple[int, int, int, int]:
    old_depth = 2 * bank_depth
    accepted = int(0 <= bank < 16 and 0 <= old_address < old_depth and bank_depth > 0)
    if not accepted:
        return 0, 0, 0, 0
    port = bank & 1
    return 1, bank >> 1, port, port * old_depth + old_address


def fixed_read_entry(
    width: int, channel: int, bank_shift: int, input_y: int,
    base_x: int, dx: int, physical_bank: int,
) -> tuple[int, int, int]:
    within = (physical_bank - dx) & 15
    source_x = base_x + within + dx
    valid = int(0 <= input_y < width and 0 <= source_x < width)
    safe_x = source_x if valid else 0
    address = (channel << bank_shift) + (safe_x >> 4)
    return physical_bank, valid, address


def pack40(values: tuple[int, int, int, int]) -> tuple[bool, tuple[int, int, int, int, int]]:
    if any(v < SIGNED40_MIN or v > SIGNED40_MAX for v in values):
        return False, (0, 0, 0, 0, 0)
    raw = 0
    for lane, value in enumerate(values):
        raw |= (value & MASK40) << (40 * lane)
    return True, tuple((raw >> (32 * word)) & 0xFFFFFFFF for word in range(5))


def unpack40(words: tuple[int, int, int, int, int]) -> tuple[int, int, int, int]:
    raw = sum((word & 0xFFFFFFFF) << (32 * index) for index, word in enumerate(words))
    result = []
    for lane in range(4):
        value = (raw >> (40 * lane)) & MASK40
        if value & (1 << 39):
            value -= 1 << 40
        result.append(value)
    return tuple(result)  # type: ignore[return-value]


def write_lines(path: Path, lines: list[str]) -> dict[str, object]:
    payload = ("\n".join(lines) + "\n").encode("ascii")
    path.write_bytes(payload)
    return {"file": path.name, "rows": len(lines) - 1, "sha256": hashlib.sha256(payload).hexdigest()}


def generate(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=False)
    tables: list[dict[str, object]] = []

    pw = ["bank\told_address\tbank_depth\taccepted\tphysical_bank\tport\tphysical_address"]
    for bank_depth in (1, 64):
        old_depth = 2 * bank_depth
        for bank in range(16):
            for old_address in range(old_depth):
                pw.append("\t".join(map(str, (bank, old_address, bank_depth, *pw1_map(bank, old_address, bank_depth)))))
        for bank, old_address in ((16, 0), (0, old_depth), (15, old_depth)):
            pw.append("\t".join(map(str, (bank, old_address, bank_depth, *pw1_map(bank, old_address, bank_depth)))))
    pw.append("\t".join(map(str, (0, 0, 0, *pw1_map(0, 0, 0)))))
    tables.append(write_lines(output / "pw1_bank_map.tsv", pw))

    normal = ["case\twidth\tchannel\tbank_shift\tinput_y\tbase_x\tdx\tphysical_bank\tvalid\taddress\tsource_bank"]
    case = 0
    for width in (16, 32, 64):
        bank_shift = {16: 0, 32: 1, 64: 2}[width]
        for channel in (0, 1, 63, 127):
            for xb in range(0, width, 16):
                for dx in range(-3, 4):
                    for input_y in (-1, 0, width - 1, width):
                        for physical_bank in range(16):
                            source_bank = (physical_bank + dx) & 15
                            normal.append("\t".join(map(str, (
                                case, width, channel, bank_shift, input_y, xb, dx,
                                *fixed_read_entry(width, channel, bank_shift, input_y, xb, dx, physical_bank),
                                source_bank,
                            ))))
                        case += 1
    tables.append(write_lines(output / "dw7_normal.tsv", normal))

    p3 = ["case\twidth\tchannel\tbank_shift\tinput_y\tbase_x\tdx\tphysical_bank\tvalid\taddress\tsource_lane\tsource_bank\tdestination0\tdestination1"]
    case = 0
    for channel in (0, 1, 31, 63):
        for xb in (0, 8, 16, 24):
            for dx in range(-3, 4):
                base_x = 2 * xb
                for input_y in (-1, 0, 63, 64):
                    for physical_bank in range(16):
                        source_lane = physical_bank if physical_bank < 8 else -1
                        source_bank = (2 * physical_bank + dx) & 15 if physical_bank < 8 else -1
                        destination0 = physical_bank if physical_bank < 8 else -1
                        destination1 = physical_bank + 8 if physical_bank < 8 else -1
                        p3.append("\t".join(map(str, (
                            case, 64, channel, 2, input_y, base_x, dx,
                            *fixed_read_entry(64, channel, 2, input_y, base_x, dx, physical_bank),
                            source_lane, source_bank, destination0, destination1,
                        ))))
                    case += 1
    tables.append(write_lines(output / "dw7_p3.tsv", p3))

    signed_cases: list[tuple[int, int, int, int]] = [
        (0, 0, 0, 0),
        (SIGNED40_MIN, SIGNED40_MAX, -1, 1),
        (0x7FFFFFFF, -0x80000000, 0x100000000, -0x100000000),
        (0x0123456789, -0x0123456789, 0x0055AA55AA, -0x0055AA55AA),
    ]
    rng = random.Random(0xA0004D7)
    for _ in range(64):
        signed_cases.append(tuple(rng.randint(SIGNED40_MIN, SIGNED40_MAX) for _ in range(4)))
    for lane in range(4):
        low = [0, 0, 0, 0]
        high = [0, 0, 0, 0]
        low[lane] = SIGNED40_MIN - 1
        high[lane] = SIGNED40_MAX + 1
        signed_cases.extend((tuple(low), tuple(high)))

    packed = ["case\tin0\tin1\tin2\tin3\taccepted\tword0\tword1\tword2\tword3\tword4\tout0\tout1\tout2\tout3"]
    for case, values in enumerate(signed_cases):
        accepted, words = pack40(values)
        unpacked = unpack40(words) if accepted else (0, 0, 0, 0)
        packed.append("\t".join(map(str, (case, *values, int(accepted), *words, *unpacked))))
    tables.append(write_lines(output / "signed40_packed4.tsv", packed))

    manifest = {
        "schema": "dual-lane-storage-dw7-opt-oracle-v1",
        "contract": {
            "pw1": {"logical_banks": 16, "physical_banks": 8, "ports": 2, "pairing": "adjacent_2p_and_2p_plus_1", "old_depth": "2*BANK_DEPTH", "physical_depth": "4*BANK_DEPTH"},
            "dw7": {"physical_banks": 16, "fixed_reads_per_tap": 16, "normal_lanes": 16, "p3_source_lanes": 8, "p3_outputs_per_source": 2, "dx_min": -3, "dx_max": 3, "padding": "masked_zero_after_safe_fixed_bank_read"},
            "packed": {"lanes": 4, "lane_bits": 40, "total_bits": 160, "lane_order": "lane0_in_bits_39_0", "overflow": "atomic_reject"},
        },
        "tables": tables,
    }
    (output / "oracle-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    generate(args.output)


if __name__ == "__main__":
    main()
