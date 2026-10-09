`timescale 1ns/1ps

// Vitis-HLS blackbox shell.  slow_clk/reset/ce are the standard common
// blackbox signals.  fast_clk/reset are direct one-bit data-wire mappings and
// must be connected to the shared 2x clock/reset at platform integration.
module cnn_v10_pw_dsp16_half2x_hls (
    input  wire slow_clk,
    input  wire slow_rst,
    input  wire slow_ce,
    input  wire fast_clk,
    input  wire fast_rst,
    input  wire [47:0] prior,
    input  wire [15:0] value0, input wire [15:0] weight0,
    input  wire [15:0] value1, input wire [15:0] weight1,
    input  wire [15:0] value2, input wire [15:0] weight2,
    input  wire [15:0] value3, input wire [15:0] weight3,
    input  wire [15:0] value4, input wire [15:0] weight4,
    input  wire [15:0] value5, input wire [15:0] weight5,
    input  wire [15:0] value6, input wire [15:0] weight6,
    input  wire [15:0] value7, input wire [15:0] weight7,
    input  wire [15:0] value8, input wire [15:0] weight8,
    input  wire [15:0] value9, input wire [15:0] weight9,
    input  wire [15:0] value10, input wire [15:0] weight10,
    input  wire [15:0] value11, input wire [15:0] weight11,
    input  wire [15:0] value12, input wire [15:0] weight12,
    input  wire [15:0] value13, input wire [15:0] weight13,
    input  wire [15:0] value14, input wire [15:0] weight14,
    input  wire [15:0] value15, input wire [15:0] weight15,
    output wire [47:0] result
);
    wire unused_out_valid;
    cnn_v10_pw_dsp16_half2x impl (
        .slow_clk(slow_clk), .slow_rst(slow_rst), .slow_ce(slow_ce),
        .fast_clk(fast_clk), .fast_rst(fast_rst), .in_valid(slow_ce),
        .prior(prior),
        .value0(value0), .weight0(weight0), .value1(value1), .weight1(weight1),
        .value2(value2), .weight2(weight2), .value3(value3), .weight3(weight3),
        .value4(value4), .weight4(weight4), .value5(value5), .weight5(weight5),
        .value6(value6), .weight6(weight6), .value7(value7), .weight7(weight7),
        .value8(value8), .weight8(weight8), .value9(value9), .weight9(weight9),
        .value10(value10), .weight10(weight10), .value11(value11), .weight11(weight11),
        .value12(value12), .weight12(weight12), .value13(value13), .weight13(weight13),
        .value14(value14), .weight14(weight14), .value15(value15), .weight15(weight15),
        .out_valid(unused_out_valid), .result(result));
endmodule
