"""Construct a v5 full-kernel fixture with independently known wide Q31 results.

All convolution weights are zero. DW3 biases exercise products above 64 bits;
the FFN contributes zero and the residual returns DW3 exactly. This isolates
rounding, signed multiplication and saturation without reimplementing the DUT.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path


def nearest_even(numerator, denominator):
    # Python's integer divmod gives an exact, independent rational oracle.
    sign = -1 if numerator < 0 else 1
    whole, remainder = divmod(abs(numerator), denominator)
    if 2 * remainder > denominator or (2 * remainder == denominator and whole % 2):
        whole += 1
    return sign * whole


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--blocks", type=int, choices=(1, 2, 4), default=1)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    cases = []
    for integer in (256, 257):
        for offset in (-1, 0, 1):
            for sign in (-1, 1):
                cases.append((sign * (integer * (1 << 32) + (1 << 31) + offset), 1 << 30, 62))
    cases += [(1 << 40, -(1 << 30), 62), ((1 << 47) - 1, (1 << 31) - 1, 62),
              (-(1 << 47), (1 << 31) - 1, 62), (-(1 << 47), -(1 << 31), 62),
              (3, 1, 1), (5, 1, 1), (-3, 1, 1), (-5, 1, 1), (0, 0, 0)]
    c, width = 64, 64
    biases = [0] * (6*c)
    mults = [0] * (6*c)
    shifts = [0] * (6*c)
    expected = []
    case_records = []
    for channel in range(c):
        bias, mult, shift = cases[channel % len(cases)]
        biases[channel], mults[channel], shifts[channel] = bias, mult, shift
        product = bias * mult
        rounded = nearest_even(product, 1 << shift)
        value = max(-32767, min(32767, rounded))
        expected.append(value)
        case_records.append({"channel": channel, "bias": bias, "multiplier": mult,
                             "shift": shift, "product": str(product),
                             "product_magnitude_bits": abs(product).bit_length(),
                             "rounded": rounded, "clipped": value})
    payload = bytearray(116*c)
    payload += struct.pack("<%dq" % (6*c), *biases)
    payload += struct.pack("<%di" % (6*c), *mults)
    payload += struct.pack("<%di" % (6*c), *shifts)
    payload += bytes(8*c)  # branch scale multiplier/shift, both zero
    payload += struct.pack("<iiQ", 1, 0, 0)  # exact residual pass-through
    payload += bytes(131072)  # GELU is zero for every code
    payload += bytes(((3*c+5)//6)*(c//16)*192)
    payload += bytes(((c+5)//6)*(3*c//16)*192)
    if len(payload) != 195088:
        raise AssertionError("v5 C64 layout mismatch")
    row = b"".join(struct.pack("<h", value) * width for value in expected)
    files = {"params.bin": bytes(payload) * args.blocks, "input-hcw.i16": bytes(2*c*width*width),
             "expected-hcw.i16": row * width}
    records = {}
    for name, data in files.items():
        (args.output / name).write_bytes(data)
        records[name] = {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    report = {"status": "SYNTHETIC_V5_WIDE_Q31_FIXTURE_NOT_EXECUTED",
              "profile": 2, "blocks": args.blocks, "pl_execution": False,
              "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "oracle": "Python exact integer rational ties-even; zero FFN, exact residual",
              "cases": case_records, "files": records}
    (args.output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
