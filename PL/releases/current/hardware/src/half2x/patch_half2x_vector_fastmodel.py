#!/usr/bin/env python3
"""Build a verification-only vector model of the half-width PW fast actor.

The related-clock bridge, epoch handshake, result FIFO, slow-domain due pipe,
CE semantics, and reset behavior remain the product RTL.  Only the internal
``cnn_v10_pw_dsp8_fast`` actor is replaced by a seven-fast-edge vector pipe.
The model is never synthesis input and must pass the actual-UNISIM miter.
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


VECTOR_ACTOR = r'''module cnn_v10_pw_dsp8_fast (
    input  wire                    fast_clk,
    input  wire                    fast_rst,
    input  wire                    fast_ce,
    input  wire                    launch_valid,
    input  wire                    launch_phase1,
    input  wire        [47:0]      prior,
    input  wire        [15:0]      value0,
    input  wire        [15:0]      weight0,
    input  wire        [15:0]      value1,
    input  wire        [15:0]      weight1,
    input  wire        [15:0]      value2,
    input  wire        [15:0]      weight2,
    input  wire        [15:0]      value3,
    input  wire        [15:0]      weight3,
    input  wire        [15:0]      value4,
    input  wire        [15:0]      weight4,
    input  wire        [15:0]      value5,
    input  wire        [15:0]      weight5,
    input  wire        [15:0]      value6,
    input  wire        [15:0]      weight6,
    input  wire        [15:0]      value7,
    input  wire        [15:0]      weight7,
    output wire                    partial_valid,
    output wire                    partial_phase1,
    output wire        [47:0]      partial
);
    wire signed [31:0] product0 = $signed(value0) * $signed(weight0);
    wire signed [31:0] product1 = $signed(value1) * $signed(weight1);
    wire signed [31:0] product2 = $signed(value2) * $signed(weight2);
    wire signed [31:0] product3 = $signed(value3) * $signed(weight3);
    wire signed [31:0] product4 = $signed(value4) * $signed(weight4);
    wire signed [31:0] product5 = $signed(value5) * $signed(weight5);
    wire signed [31:0] product6 = $signed(value6) * $signed(weight6);
    wire signed [31:0] product7 = $signed(value7) * $signed(weight7);
    wire signed [47:0] sx0 = {{16{product0[31]}}, product0};
    wire signed [47:0] sx1 = {{16{product1[31]}}, product1};
    wire signed [47:0] sx2 = {{16{product2[31]}}, product2};
    wire signed [47:0] sx3 = {{16{product3[31]}}, product3};
    wire signed [47:0] sx4 = {{16{product4[31]}}, product4};
    wire signed [47:0] sx5 = {{16{product5[31]}}, product5};
    wire signed [47:0] sx6 = {{16{product6[31]}}, product6};
    wire signed [47:0] sx7 = {{16{product7[31]}}, product7};
    wire signed [47:0] s0 = $signed(prior) + sx0;
    wire signed [47:0] s1 = s0 + sx1;
    wire signed [47:0] s2 = s1 + sx2;
    wire signed [47:0] s3 = s2 + sx3;
    wire signed [47:0] s4 = s3 + sx4;
    wire signed [47:0] s5 = s4 + sx5;
    wire signed [47:0] s6 = s5 + sx6;
    wire signed [47:0] vector_sum = s6 + sx7;

    reg [47:0] data_pipe [0:6];
    reg [6:0] valid_pipe;
    reg [6:0] phase_pipe;
    integer i;
    always @(posedge fast_clk) begin
        if (fast_rst) begin
            for (i = 0; i < 7; i = i + 1) data_pipe[i] <= 48'd0;
            valid_pipe <= 7'd0;
            phase_pipe <= 7'd0;
        end else if (fast_ce) begin
            data_pipe[0] <= vector_sum;
            for (i = 1; i < 7; i = i + 1) data_pipe[i] <= data_pipe[i-1];
            valid_pipe <= {valid_pipe[5:0], launch_valid};
            phase_pipe <= {phase_pipe[5:0], launch_phase1};
        end
    end
    assign partial_valid = valid_pipe[6];
    assign partial_phase1 = phase_pipe[6];
    assign partial = data_pipe[6];
endmodule'''


# The vector actor no longer instantiates the chain modules.  Keep every module
# in the generated leaf self-contained while removing the now-unreachable
# primitive template too, so a full-snapshot audit can prove that verification
# RTL contains no DSP48E2.  This fallback is not on the elaborated vector path.
BEHAVIORAL_MULADD = r'''module cnn_v10_pw_dsp_muladd #(
    parameter integer ADD_SOURCE = 0
) (
    input wire ap_clk, input wire ap_rst, input wire ap_ce,
    input wire [15:0] value, input wire [15:0] weight,
    input wire [47:0] c_value, input wire [47:0] pcin,
    output wire [47:0] p, output wire [47:0] pcout
);
    reg signed [15:0] a_q, b_q;
    reg signed [47:0] m_q, p_q;
    wire signed [47:0] addend =
        (ADD_SOURCE == 1) ? $signed(c_value) :
        (ADD_SOURCE == 2) ? $signed(pcin) : 48'sd0;
    always @(posedge ap_clk) begin
        if (ap_rst) begin a_q <= 0; b_q <= 0; m_q <= 0; p_q <= 0; end
        else if (ap_ce) begin
            a_q <= $signed(value); b_q <= $signed(weight);
            m_q <= a_q * b_q; p_q <= m_q + addend;
        end
    end
    assign p = p_q;
    assign pcout = p_q;
endmodule'''


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replace_module(text: str, name: str, replacement: str) -> str:
    start = re.search(rf"(?m)^module\s+{re.escape(name)}\b", text)
    if not start:
        raise ValueError(f"module {name} not found")
    end = re.search(r"(?m)^endmodule\s*$", text[start.start():])
    if not end:
        raise ValueError(f"endmodule for {name} not found")
    stop = start.start() + end.end()
    return text[:start.start()] + replacement + text[stop:]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    ap.add_argument("--manifest", required=True, type=Path)
    ap.add_argument("--suffix", default="_vector_model")
    args = ap.parse_args()
    if not re.fullmatch(r"_[A-Za-z][A-Za-z0-9_]*", args.suffix):
        raise SystemExit("suffix must be an underscore-prefixed Verilog identifier")

    text = args.source.read_text(encoding="utf-8", errors="strict")
    for module in MODULES:
        if len(re.findall(rf"(?m)^module\s+{re.escape(module)}\b", text)) != 1:
            raise ValueError(f"expected one declaration of {module}")
    text = replace_module(text, "cnn_v10_pw_dsp_muladd", BEHAVIORAL_MULADD)
    text = replace_module(text, "cnn_v10_pw_dsp8_fast", VECTOR_ACTOR)
    for module in sorted(MODULES, key=len, reverse=True):
        text = re.sub(rf"\b{re.escape(module)}\b", module + args.suffix, text)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8", newline="\n")
    manifest = {
        "schema": "cnn-v10-pw-half2x-vector-fastmodel-transform-v1",
        "verification_only": True,
        "synthesis_allowed": False,
        "source": str(args.source.resolve()),
        "source_sha256": digest(args.source),
        "output": str(args.output.resolve()),
        "output_sha256": digest(args.output),
        "suffix": args.suffix,
        "preserved": ["dual_clock_bridge", "epoch_handshake", "result_fifo", "slow_due_pipe", "ce_reset"],
        "replaced": "cnn_v10_pw_dsp8_fast internals; unreachable DSP primitive template sanitized",
        "fast_latency_edges": 7,
    }
    args.manifest.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"CNN_V10_HALF2X_VECTOR_FASTMODEL_PATCH_PASS output_sha256={manifest['output_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
