#!/usr/bin/env python3
"""Create a verification-only half2x leaf with behavioral DSP primitives.

The dual-clock bridge, result FIFO, CE/reset handling, and all scheduling RTL
remain byte-for-byte equivalent apart from deterministic module renaming.  Only
the DSP48E2-backed ``cnn_v10_pw_dsp_muladd`` implementation is replaced.  This
file is simulation collateral and must never be used as synthesis input.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


MODULES = (
    "cnn_v10_pw_dsp_muladd",
    "cnn_v10_pw_dsp_chain4",
    "cnn_v10_pw_dsp16_fullwidth_reference",
    "cnn_v10_pw_dsp8_fast",
    "cnn_v10_pw_dsp16_half2x",
    "cnn_v10_pw_dsp16",
)


FAST_MULADD = r'''module cnn_v10_pw_dsp_muladd #(
    parameter integer ADD_SOURCE = 0
) (
    input  wire                    ap_clk,
    input  wire                    ap_rst,
    input  wire                    ap_ce,
    input  wire        [15:0]      value,
    input  wire        [15:0]      weight,
    input  wire        [47:0]      c_value,
    input  wire        [47:0]      pcin,
    output wire        [47:0]      p,
    output wire        [47:0]      pcout
);
    // Verification-only cycle model of AREG=BREG=MREG=PREG=1.  Signed
    // multiplication and the final add wrap modulo 2^48, matching DSP48E2.
    reg signed [15:0] a_q;
    reg signed [15:0] b_q;
    reg signed [47:0] m_q;
    reg signed [47:0] p_q;
    wire signed [47:0] addend =
        (ADD_SOURCE == 1) ? $signed(c_value) :
        (ADD_SOURCE == 2) ? $signed(pcin) : 48'sd0;
    always @(posedge ap_clk) begin
        if (ap_rst) begin
            a_q <= 16'sd0;
            b_q <= 16'sd0;
            m_q <= 48'sd0;
            p_q <= 48'sd0;
        end else if (ap_ce) begin
            a_q <= $signed(value);
            b_q <= $signed(weight);
            m_q <= a_q * b_q;
            p_q <= m_q + addend;
        end
    end
    assign p = p_q;
    assign pcout = p_q;
endmodule'''


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replace_first_module(text: str, name: str, replacement: str) -> str:
    start = re.search(rf"(?m)^module\s+{re.escape(name)}\b", text)
    if not start:
        raise ValueError(f"module {name} not found")
    end = re.search(r"(?m)^endmodule\s*$", text[start.start():])
    if not end:
        raise ValueError(f"endmodule for {name} not found")
    stop = start.start() + end.end()
    return text[:start.start()] + replacement + text[stop:]


def render(source: Path, suffix: str) -> str:
    text = source.read_text(encoding="utf-8", errors="strict")
    for module in MODULES:
        count = len(re.findall(rf"(?m)^module\s+{re.escape(module)}\b", text))
        if count != 1:
            raise ValueError(f"expected one {module} declaration, got {count}")
    if text.count("DSP48E2 #(") != 1:
        raise ValueError("expected exactly one DSP48E2 primitive template")
    text = replace_first_module(text, "cnn_v10_pw_dsp_muladd", FAST_MULADD)
    for module in sorted(MODULES, key=len, reverse=True):
        text = re.sub(rf"\b{re.escape(module)}\b", module + suffix, text)
    if "DSP48E2 #(" in text:
        raise ValueError("behavioral output still contains DSP48E2")
    return text


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--suffix", default="_fastmodel")
    args = parser.parse_args()
    if not re.fullmatch(r"_[A-Za-z][A-Za-z0-9_]*", args.suffix):
        raise SystemExit("suffix must be an underscore-prefixed Verilog identifier")
    rendered = render(args.source, args.suffix)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8", newline="\n")
    manifest = {
        "schema": "cnn-v10-pw-half2x-fastmodel-transform-v1",
        "verification_only": True,
        "synthesis_allowed": False,
        "source": str(args.source.resolve()),
        "source_sha256": sha256(args.source),
        "output": str(args.output.resolve()),
        "output_sha256": sha256(args.output),
        "suffix": args.suffix,
        "preserved": ["dual_clock_bridge", "result_fifo", "ce_reset", "latency8"],
        "replaced": "DSP48E2 muladd primitive internals only",
    }
    args.manifest.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"CNN_V10_HALF2X_FASTMODEL_PATCH_PASS output_sha256={manifest['output_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
