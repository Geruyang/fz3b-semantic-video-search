`timescale 1ns/1ps

// One registered signed 16x16 product, optionally accumulated from C or PCIN.
// AREG/BREG/MREG/PREG are enabled to keep the multiplier and ALU out of one
// combinational cycle.  Adjacent cascade levels still finish one enabled
// cycle apart because PCIN enters the ALU after the product M register.
module cnn_v10_pw_dsp_muladd #(
    parameter integer ADD_SOURCE = 0, // 0: M, 1: M+C, 2: M+PCIN, 3: M+PCIN+C
    parameter integer EXTRA_AB_REG = 0
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
    localparam [8:0] OPMODE_VALUE =
        (ADD_SOURCE == 1) ? 9'h035 :
        (ADD_SOURCE == 2) ? 9'h015 :
        (ADD_SOURCE == 3) ? 9'h195 : 9'h005;

    wire [29:0] a_ext = {{14{value[15]}}, value};
    wire [17:0] b_ext = {{2{weight[15]}}, weight};
    wire [47:0] c_mux = ((ADD_SOURCE == 1) || (ADD_SOURCE == 3)) ? c_value : 48'd0;

    wire [29:0] acout_unused;
    wire [17:0] bcout_unused;
    wire [3:0] carryout_unused;
    wire carrycascout_unused;
    wire multsignout_unused;
    wire overflow_unused;
    wire patternbdetect_unused;
    wire patterndetect_unused;
    wire underflow_unused;
    wire [7:0] xorout_unused;

    DSP48E2 #(
        .ACASCREG(1),
        .ADREG(0),
        .ALUMODEREG(0),
        .AMULTSEL("A"),
        .AREG(EXTRA_AB_REG ? 2 : 1),
        .AUTORESET_PATDET("NO_RESET"),
        .AUTORESET_PRIORITY("RESET"),
        .A_INPUT("DIRECT"),
        .BCASCREG(1),
        .BMULTSEL("B"),
        .BREG(EXTRA_AB_REG ? 2 : 1),
        .B_INPUT("DIRECT"),
        .CARRYINREG(0),
        .CARRYINSELREG(0),
        .CREG(0),
        .DREG(0),
        .INMODEREG(0),
        .MASK(48'h3fffffffffff),
        .MREG(1),
        .OPMODEREG(0),
        .PATTERN(48'h000000000000),
        .PREADDINSEL("A"),
        .PREG(1),
        .RND(48'h000000000000),
        .SEL_MASK("MASK"),
        .SEL_PATTERN("PATTERN"),
        .USE_MULT("MULTIPLY"),
        .USE_PATTERN_DETECT("NO_PATDET"),
        .USE_SIMD("ONE48"),
        .USE_WIDEXOR("FALSE"),
        .XORSIMD("XOR24_48_96")
    ) dsp_i (
        .A(a_ext),
        .ACIN(30'd0),
        .ACOUT(acout_unused),
        .ALUMODE(4'd0),
        .B(b_ext),
        .BCIN(18'd0),
        .BCOUT(bcout_unused),
        .C(c_mux),
        .CARRYCASCIN(1'b0),
        .CARRYCASCOUT(carrycascout_unused),
        .CARRYIN(1'b0),
        .CARRYINSEL(3'd0),
        .CARRYOUT(carryout_unused),
        .CEA1(EXTRA_AB_REG ? ap_ce : 1'b0),
        .CEA2(ap_ce),
        .CEAD(1'b0),
        .CEALUMODE(1'b0),
        .CEB1(EXTRA_AB_REG ? ap_ce : 1'b0),
        .CEB2(ap_ce),
        .CEC(1'b0),
        .CECARRYIN(1'b0),
        .CECTRL(1'b0),
        .CED(1'b0),
        .CEINMODE(1'b0),
        .CEM(ap_ce),
        .CEP(ap_ce),
        .CLK(ap_clk),
        .D(27'd0),
        .INMODE(5'd0),
        .MULTSIGNIN(1'b0),
        .MULTSIGNOUT(multsignout_unused),
        .OPMODE(OPMODE_VALUE),
        .OVERFLOW(overflow_unused),
        .P(p),
        .PATTERNBDETECT(patternbdetect_unused),
        .PATTERNDETECT(patterndetect_unused),
        .PCIN(pcin),
        .PCOUT(pcout),
        .RSTA(ap_rst),
        .RSTALLCARRYIN(1'b0),
        .RSTALUMODE(1'b0),
        .RSTB(ap_rst),
        .RSTC(1'b0),
        .RSTCTRL(1'b0),
        .RSTD(1'b0),
        .RSTINMODE(1'b0),
        .RSTM(ap_rst),
        .RSTP(ap_rst),
        .UNDERFLOW(underflow_unused),
        .XOROUT(xorout_unused)
    );
endmodule

module cnn_v10_pw_dsp_chain4 #(
    parameter integer START_WITH_PRIOR = 0
) (
    input  wire                    ap_clk,
    input  wire                    ap_rst,
    input  wire                    ap_ce,
    input  wire        [47:0]      prior,
    input  wire        [15:0]      value0,
    input  wire        [15:0]      weight0,
    input  wire        [15:0]      value1,
    input  wire        [15:0]      weight1,
    input  wire        [15:0]      value2,
    input  wire        [15:0]      weight2,
    input  wire        [15:0]      value3,
    input  wire        [15:0]      weight3,
    output wire        [47:0]      partial
);
    reg signed [15:0] value1_d1, weight1_d1;
    reg signed [15:0] value2_d1, weight2_d1;
    reg signed [15:0] value2_d2, weight2_d2;
    reg signed [15:0] value3_d1, weight3_d1;
    reg signed [15:0] value3_d2, weight3_d2;
    reg signed [15:0] value3_d3, weight3_d3;
    reg signed [47:0] prior_d1, prior_d2;

    always @(posedge ap_clk) begin
        if (ap_rst) begin
            value1_d1 <= 16'sd0;
            weight1_d1 <= 16'sd0;
            value2_d1 <= 16'sd0;
            weight2_d1 <= 16'sd0;
            value2_d2 <= 16'sd0;
            weight2_d2 <= 16'sd0;
            value3_d1 <= 16'sd0;
            weight3_d1 <= 16'sd0;
            value3_d2 <= 16'sd0;
            weight3_d2 <= 16'sd0;
            value3_d3 <= 16'sd0;
            weight3_d3 <= 16'sd0;
            prior_d1 <= 48'sd0;
            prior_d2 <= 48'sd0;
        end else if (ap_ce) begin
            value1_d1 <= value1;
            weight1_d1 <= weight1;
            value2_d1 <= value2;
            weight2_d1 <= weight2;
            value2_d2 <= value2_d1;
            weight2_d2 <= weight2_d1;
            value3_d1 <= value3;
            weight3_d1 <= weight3;
            value3_d2 <= value3_d1;
            weight3_d2 <= weight3_d1;
            value3_d3 <= value3_d2;
            weight3_d3 <= weight3_d2;
            prior_d1 <= prior;
            prior_d2 <= prior_d1;
        end
    end

    wire signed [47:0] p0, pc0, p1, pc1, p2, pc2, pc3;
    cnn_v10_pw_dsp_muladd #(.ADD_SOURCE(START_WITH_PRIOR ? 1 : 0)) stage0 (
        .ap_clk(ap_clk), .ap_rst(ap_rst), .ap_ce(ap_ce),
        .value(value0), .weight(weight0), .c_value(prior_d2), .pcin(48'd0),
        .p(p0), .pcout(pc0));
    cnn_v10_pw_dsp_muladd #(.ADD_SOURCE(2)) stage1 (
        .ap_clk(ap_clk), .ap_rst(ap_rst), .ap_ce(ap_ce),
        .value(value1_d1), .weight(weight1_d1), .c_value(48'd0), .pcin(pc0),
        .p(p1), .pcout(pc1));
    cnn_v10_pw_dsp_muladd #(.ADD_SOURCE(2)) stage2 (
        .ap_clk(ap_clk), .ap_rst(ap_rst), .ap_ce(ap_ce),
        .value(value2_d2), .weight(weight2_d2), .c_value(48'd0), .pcin(pc1),
        .p(p2), .pcout(pc2));
    cnn_v10_pw_dsp_muladd #(.ADD_SOURCE(2)) stage3 (
        .ap_clk(ap_clk), .ap_rst(ap_rst), .ap_ce(ap_ce),
        .value(value3_d3), .weight(weight3_d3), .c_value(48'd0), .pcin(pc2),
        .p(partial), .pcout(pc3));
endmodule

// Chain 1 is delayed one fast cycle in the DSP A/B input registers.  Its last
// DSP consumes chain 0 through C and performs C+PCIN+M in the same PREG edge,
// replacing the former 48-bit fabric partial0+partial1 register.
module cnn_v10_pw_dsp_chain4_fused_tail (
    input  wire               ap_clk,
    input  wire               ap_rst,
    input  wire               ap_ce,
    input  wire [47:0]        final_c,
    input  wire [15:0]        value0,
    input  wire [15:0]        weight0,
    input  wire [15:0]        value1,
    input  wire [15:0]        weight1,
    input  wire [15:0]        value2,
    input  wire [15:0]        weight2,
    input  wire [15:0]        value3,
    input  wire [15:0]        weight3,
    output wire [47:0]        partial
);
    reg signed [15:0] value1_d1, weight1_d1;
    reg signed [15:0] value2_d1, weight2_d1;
    reg signed [15:0] value2_d2, weight2_d2;
    reg signed [15:0] value3_d1, weight3_d1;
    reg signed [15:0] value3_d2, weight3_d2;
    reg signed [15:0] value3_d3, weight3_d3;

    always @(posedge ap_clk) begin
        if (ap_rst) begin
            value1_d1 <= 16'sd0; weight1_d1 <= 16'sd0;
            value2_d1 <= 16'sd0; weight2_d1 <= 16'sd0;
            value2_d2 <= 16'sd0; weight2_d2 <= 16'sd0;
            value3_d1 <= 16'sd0; weight3_d1 <= 16'sd0;
            value3_d2 <= 16'sd0; weight3_d2 <= 16'sd0;
            value3_d3 <= 16'sd0; weight3_d3 <= 16'sd0;
        end else if (ap_ce) begin
            value1_d1 <= value1; weight1_d1 <= weight1;
            value2_d1 <= value2; weight2_d1 <= weight2;
            value2_d2 <= value2_d1; weight2_d2 <= weight2_d1;
            value3_d1 <= value3; weight3_d1 <= weight3;
            value3_d2 <= value3_d1; weight3_d2 <= weight3_d1;
            value3_d3 <= value3_d2; weight3_d3 <= weight3_d2;
        end
    end

    wire signed [47:0] p0, pc0, p1, pc1, p2, pc2, pc3;
    cnn_v10_pw_dsp_muladd #(.ADD_SOURCE(0), .EXTRA_AB_REG(1)) stage0 (
        .ap_clk(ap_clk), .ap_rst(ap_rst), .ap_ce(ap_ce),
        .value(value0), .weight(weight0), .c_value(48'd0), .pcin(48'd0),
        .p(p0), .pcout(pc0));
    cnn_v10_pw_dsp_muladd #(.ADD_SOURCE(2), .EXTRA_AB_REG(1)) stage1 (
        .ap_clk(ap_clk), .ap_rst(ap_rst), .ap_ce(ap_ce),
        .value(value1_d1), .weight(weight1_d1), .c_value(48'd0), .pcin(pc0),
        .p(p1), .pcout(pc1));
    cnn_v10_pw_dsp_muladd #(.ADD_SOURCE(2), .EXTRA_AB_REG(1)) stage2 (
        .ap_clk(ap_clk), .ap_rst(ap_rst), .ap_ce(ap_ce),
        .value(value2_d2), .weight(weight2_d2), .c_value(48'd0), .pcin(pc1),
        .p(p2), .pcout(pc2));
    cnn_v10_pw_dsp_muladd #(.ADD_SOURCE(3), .EXTRA_AB_REG(1)) stage3 (
        .ap_clk(ap_clk), .ap_rst(ap_rst), .ap_ce(ap_ce),
        .value(value3_d3), .weight(weight3_d3), .c_value(final_c), .pcin(pc2),
        .p(partial), .pcout(pc3));
endmodule

module cnn_v10_pw_dsp16 (
    input  wire                    ap_clk,
    input  wire                    ap_rst,
    input  wire                    ap_ce,
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
    input  wire        [15:0]      value8,
    input  wire        [15:0]      weight8,
    input  wire        [15:0]      value9,
    input  wire        [15:0]      weight9,
    input  wire        [15:0]      value10,
    input  wire        [15:0]      weight10,
    input  wire        [15:0]      value11,
    input  wire        [15:0]      weight11,
    input  wire        [15:0]      value12,
    input  wire        [15:0]      weight12,
    input  wire        [15:0]      value13,
    input  wire        [15:0]      weight13,
    input  wire        [15:0]      value14,
    input  wire        [15:0]      weight14,
    input  wire        [15:0]      value15,
    input  wire        [15:0]      weight15,
    output reg         [47:0]      result
);
    wire signed [47:0] partial0, partial1, partial2, partial3;
    reg signed [47:0] sum01, sum23;

    cnn_v10_pw_dsp_chain4 #(.START_WITH_PRIOR(1)) chain0 (
        .ap_clk(ap_clk), .ap_rst(ap_rst), .ap_ce(ap_ce), .prior(prior),
        .value0(value0), .weight0(weight0), .value1(value1), .weight1(weight1),
        .value2(value2), .weight2(weight2), .value3(value3), .weight3(weight3),
        .partial(partial0));
    cnn_v10_pw_dsp_chain4 chain1 (
        .ap_clk(ap_clk), .ap_rst(ap_rst), .ap_ce(ap_ce), .prior(48'd0),
        .value0(value4), .weight0(weight4), .value1(value5), .weight1(weight5),
        .value2(value6), .weight2(weight6), .value3(value7), .weight3(weight7),
        .partial(partial1));
    cnn_v10_pw_dsp_chain4 chain2 (
        .ap_clk(ap_clk), .ap_rst(ap_rst), .ap_ce(ap_ce), .prior(48'd0),
        .value0(value8), .weight0(weight8), .value1(value9), .weight1(weight9),
        .value2(value10), .weight2(weight10), .value3(value11), .weight3(weight11),
        .partial(partial2));
    cnn_v10_pw_dsp_chain4 chain3 (
        .ap_clk(ap_clk), .ap_rst(ap_rst), .ap_ce(ap_ce), .prior(48'd0),
        .value0(value12), .weight0(weight12), .value1(value13), .weight1(weight13),
        .value2(value14), .weight2(weight14), .value3(value15), .weight3(weight15),
        .partial(partial3));

    always @(posedge ap_clk) begin
        if (ap_rst) begin
            sum01 <= 48'sd0;
            sum23 <= 48'sd0;
            result <= 48'sd0;
        end else if (ap_ce) begin
            sum01 <= partial0 + partial1;
            sum23 <= partial2 + partial3;
            result <= sum01 + sum23;
        end
    end
endmodule
