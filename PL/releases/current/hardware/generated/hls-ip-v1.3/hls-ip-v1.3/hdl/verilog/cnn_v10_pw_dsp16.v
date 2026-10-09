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

module cnn_v10_pw_dsp16_fullwidth_reference (
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

`timescale 1ns/1ps

// Experimental half-width PW dot product.
//
// Clock contract:
//   * slow_clk is the surrounding PW/HLS clock (target 200 MHz).
//   * fast_clk is a phase-related 2x clock (target 400 MHz).
//   * The clocks are edge-aligned.  A slow edge captures a request, the next
//     fast-only edge launches phase 0, and the following coincident edge
//     launches phase 1 from the still-stable old hold registers.  This gives
//     the slow-to-fast boundary half a slow period instead of 1.25 ns.
//   * slow_rst and fast_rst are synchronously asserted/deasserted in their
//     respective domains after the shared MMCM reports locked.
//
// slow_ce is the only externally visible pause/backpressure control.  It
// gates request acceptance and the fixed eight-enabled-cycle result schedule.
// Once a request is accepted, its two fast phases and DSP pipeline advance
// atomically into an eight-entry result FIFO.  Thus a slow_ce transition can
// never split a request between its two halves.  The fixed slow-domain due
// pipeline preserves the existing latency=8/II=1 observable contract.
//
// This module is an isolated experiment.  It does not replace the frozen
// cnn_v10_pw_dsp16 product source until the primitive, timing, and full-kernel
// gates pass.
module cnn_v10_pw_dsp8_fast_fused_alu (
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
    wire signed [47:0] partial0;
    wire signed [47:0] partial1;
    reg  [6:0] valid_pipe;
    reg  [6:0] phase_pipe;

    cnn_v10_pw_dsp_chain4 #(.START_WITH_PRIOR(1)) chain0 (
        .ap_clk(fast_clk), .ap_rst(fast_rst), .ap_ce(fast_ce), .prior(prior),
        .value0(value0), .weight0(weight0), .value1(value1), .weight1(weight1),
        .value2(value2), .weight2(weight2), .value3(value3), .weight3(weight3),
        .partial(partial0));
    cnn_v10_pw_dsp_chain4_fused_tail chain1 (
        .ap_clk(fast_clk), .ap_rst(fast_rst), .ap_ce(fast_ce), .final_c(partial0),
        .value0(value4), .weight0(weight4), .value1(value5), .weight1(weight5),
        .value2(value6), .weight2(weight6), .value3(value7), .weight3(weight7),
        .partial(partial1));

    always @(posedge fast_clk) begin
        if (fast_rst) begin
            valid_pipe <= 7'd0;
            phase_pipe <= 7'd0;
        end else if (fast_ce) begin
            valid_pipe <= {valid_pipe[5:0], launch_valid};
            phase_pipe <= {phase_pipe[5:0], launch_phase1};
        end
    end

    assign partial_valid = valid_pipe[6];
    assign partial_phase1 = phase_pipe[6];
    assign partial = partial1;
endmodule

module cnn_v10_pw_dsp16_half2x_fused_alu (
    input  wire                    slow_clk,
    input  wire                    slow_rst,
    input  wire                    slow_ce,
    input  wire                    fast_clk,
    input  wire                    fast_rst,
    input  wire                    in_valid,
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
    output reg                     out_valid,
    output reg         [47:0]      result
);
    reg slow_epoch;
    reg [47:0] prior_hold;
    reg [15:0] value_hold [0:15];
    reg [15:0] weight_hold [0:15];

    reg fast_seen_epoch;
    reg phase1_pending;
    wire fast_ce = 1'b1;
    wire launch_phase0 = !phase1_pending &&
                         (fast_seen_epoch != slow_epoch);
    wire launch_phase1 = phase1_pending;
    wire launch_valid = launch_phase0 || launch_phase1;

    wire [47:0] selected_prior = launch_phase1 ? 48'd0 : prior_hold;
    wire [15:0] selected_value0 = launch_phase1 ? value_hold[8]  : value_hold[0];
    wire [15:0] selected_value1 = launch_phase1 ? value_hold[9]  : value_hold[1];
    wire [15:0] selected_value2 = launch_phase1 ? value_hold[10] : value_hold[2];
    wire [15:0] selected_value3 = launch_phase1 ? value_hold[11] : value_hold[3];
    wire [15:0] selected_value4 = launch_phase1 ? value_hold[12] : value_hold[4];
    wire [15:0] selected_value5 = launch_phase1 ? value_hold[13] : value_hold[5];
    wire [15:0] selected_value6 = launch_phase1 ? value_hold[14] : value_hold[6];
    wire [15:0] selected_value7 = launch_phase1 ? value_hold[15] : value_hold[7];
    wire [15:0] selected_weight0 = launch_phase1 ? weight_hold[8]  : weight_hold[0];
    wire [15:0] selected_weight1 = launch_phase1 ? weight_hold[9]  : weight_hold[1];
    wire [15:0] selected_weight2 = launch_phase1 ? weight_hold[10] : weight_hold[2];
    wire [15:0] selected_weight3 = launch_phase1 ? weight_hold[11] : weight_hold[3];
    wire [15:0] selected_weight4 = launch_phase1 ? weight_hold[12] : weight_hold[4];
    wire [15:0] selected_weight5 = launch_phase1 ? weight_hold[13] : weight_hold[5];
    wire [15:0] selected_weight6 = launch_phase1 ? weight_hold[14] : weight_hold[6];
    wire [15:0] selected_weight7 = launch_phase1 ? weight_hold[15] : weight_hold[7];

    wire half_valid;
    wire half_phase1;
    wire [47:0] half_partial;
    reg  [47:0] phase0_partial;
    reg          have_phase0;
    // The related-clock result FIFO decouples completion of already accepted
    // requests from a later slow_ce pause.  Gray pointers make the boundary
    // explicit and keep the contract valid if implementation skew changes.
    reg [47:0] result_fifo [0:7];
    reg [3:0] result_wr_bin;
    reg [3:0] result_wr_gray;
    reg [3:0] result_rd_bin;
    reg [3:0] result_rd_gray;
    (* ASYNC_REG = "TRUE" *) reg [3:0] rd_gray_fast_q1, rd_gray_fast_q2;
    (* ASYNC_REG = "TRUE" *) reg [3:0] wr_gray_slow_q1, wr_gray_slow_q2;
    reg [6:0] due_valid_pipe;

    wire [3:0] result_wr_bin_next = result_wr_bin + 4'd1;
    wire [3:0] result_wr_gray_next =
        (result_wr_bin_next >> 1) ^ result_wr_bin_next;
    wire result_fifo_full =
        (result_wr_gray_next == {~rd_gray_fast_q2[3:2],
                                  rd_gray_fast_q2[1:0]});
    wire result_fifo_empty = (result_rd_gray == wr_gray_slow_q2);
    wire result_due = due_valid_pipe[6];

    integer i;
    always @(posedge slow_clk) begin
        if (slow_rst) begin
            slow_epoch <= 1'b0;
            prior_hold <= 48'd0;
            for (i = 0; i < 16; i = i + 1) begin
                value_hold[i] <= 16'd0;
                weight_hold[i] <= 16'd0;
            end
        end else begin
            if (slow_ce && in_valid) begin
                prior_hold <= prior;
                value_hold[0] <= value0;   weight_hold[0] <= weight0;
                value_hold[1] <= value1;   weight_hold[1] <= weight1;
                value_hold[2] <= value2;   weight_hold[2] <= weight2;
                value_hold[3] <= value3;   weight_hold[3] <= weight3;
                value_hold[4] <= value4;   weight_hold[4] <= weight4;
                value_hold[5] <= value5;   weight_hold[5] <= weight5;
                value_hold[6] <= value6;   weight_hold[6] <= weight6;
                value_hold[7] <= value7;   weight_hold[7] <= weight7;
                value_hold[8] <= value8;   weight_hold[8] <= weight8;
                value_hold[9] <= value9;   weight_hold[9] <= weight9;
                value_hold[10] <= value10; weight_hold[10] <= weight10;
                value_hold[11] <= value11; weight_hold[11] <= weight11;
                value_hold[12] <= value12; weight_hold[12] <= weight12;
                value_hold[13] <= value13; weight_hold[13] <= weight13;
                value_hold[14] <= value14; weight_hold[14] <= weight14;
                value_hold[15] <= value15; weight_hold[15] <= weight15;
                slow_epoch <= ~slow_epoch;
            end
        end
    end

    always @(posedge fast_clk) begin
        if (fast_rst) begin
            fast_seen_epoch <= 1'b0;
            phase1_pending <= 1'b0;
            phase0_partial <= 48'd0;
            have_phase0 <= 1'b0;
            result_wr_bin <= 4'd0;
            result_wr_gray <= 4'd0;
            rd_gray_fast_q1 <= 4'd0;
            rd_gray_fast_q2 <= 4'd0;
        end else begin
            rd_gray_fast_q1 <= result_rd_gray;
            rd_gray_fast_q2 <= rd_gray_fast_q1;
            if (launch_phase0) begin
                fast_seen_epoch <= slow_epoch;
                phase1_pending <= 1'b1;
            end else if (launch_phase1) begin
                phase1_pending <= 1'b0;
            end

            if (half_valid) begin
                if (!half_phase1) begin
                    phase0_partial <= half_partial;
                    have_phase0 <= 1'b1;
                end else begin
                    if (!result_fifo_full) begin
                        result_fifo[result_wr_bin[2:0]] <=
                            phase0_partial + half_partial;
                        result_wr_bin <= result_wr_bin_next;
                        result_wr_gray <= result_wr_gray_next;
                    end
                    have_phase0 <= 1'b0;
                end
            end
        end
    end

    always @(posedge slow_clk) begin
        if (slow_rst) begin
            result_rd_bin <= 4'd0;
            result_rd_gray <= 4'd0;
            wr_gray_slow_q1 <= 4'd0;
            wr_gray_slow_q2 <= 4'd0;
            due_valid_pipe <= 7'd0;
            out_valid <= 1'b0;
            result <= 48'd0;
        end else begin
            wr_gray_slow_q1 <= result_wr_gray;
            wr_gray_slow_q2 <= wr_gray_slow_q1;
            out_valid <= 1'b0;
            if (slow_ce) begin
                due_valid_pipe <= {due_valid_pipe[5:0], in_valid};
                if (result_due && !result_fifo_empty) begin
                    result <= result_fifo[result_rd_bin[2:0]];
                    result_rd_bin <= result_rd_bin + 4'd1;
                    result_rd_gray <= ((result_rd_bin + 4'd1) >> 1) ^
                                      (result_rd_bin + 4'd1);
                    out_valid <= 1'b1;
                end
            end
        end
    end

    cnn_v10_pw_dsp8_fast_fused_alu half_dot (
        .fast_clk(fast_clk), .fast_rst(fast_rst), .fast_ce(fast_ce),
        .launch_valid(launch_valid), .launch_phase1(launch_phase1),
        .prior(selected_prior),
        .value0(selected_value0), .weight0(selected_weight0),
        .value1(selected_value1), .weight1(selected_weight1),
        .value2(selected_value2), .weight2(selected_weight2),
        .value3(selected_value3), .weight3(selected_weight3),
        .value4(selected_value4), .weight4(selected_weight4),
        .value5(selected_value5), .weight5(selected_weight5),
        .value6(selected_value6), .weight6(selected_weight6),
        .value7(selected_value7), .weight7(selected_weight7),
        .partial_valid(half_valid), .partial_phase1(half_phase1),
        .partial(half_partial));

`ifndef SYNTHESIS
    // A second result must never retire without its matching first half.
    always @(posedge fast_clk)
        if (!fast_rst && half_valid && half_phase1 && !have_phase0)
            $fatal(1, "half2x phase-1 result without phase-0 partial");

    always @(posedge fast_clk)
        if (!fast_rst && half_valid && half_phase1 && result_fifo_full)
            $fatal(1, "half2x result FIFO overflow");

    always @(posedge slow_clk)
        if (!slow_rst && slow_ce && result_due && result_fifo_empty)
            $fatal(1, "half2x result missed fixed latency-8 deadline");
`endif
endmodule

// Deterministic post-HLS clock bridge wrapper.
module cnn_v10_pw_dsp16 (
    input wire ap_clk,
    input wire ap_rst,
    input wire ap_ce,
    input wire pw_fast_clk,
    input wire pw_fast_rst,
    input wire [47:0] prior,
    input wire [15:0] value0,
    input wire [15:0] weight0,
    input wire [15:0] value1,
    input wire [15:0] weight1,
    input wire [15:0] value2,
    input wire [15:0] weight2,
    input wire [15:0] value3,
    input wire [15:0] weight3,
    input wire [15:0] value4,
    input wire [15:0] weight4,
    input wire [15:0] value5,
    input wire [15:0] weight5,
    input wire [15:0] value6,
    input wire [15:0] weight6,
    input wire [15:0] value7,
    input wire [15:0] weight7,
    input wire [15:0] value8,
    input wire [15:0] weight8,
    input wire [15:0] value9,
    input wire [15:0] weight9,
    input wire [15:0] value10,
    input wire [15:0] weight10,
    input wire [15:0] value11,
    input wire [15:0] weight11,
    input wire [15:0] value12,
    input wire [15:0] weight12,
    input wire [15:0] value13,
    input wire [15:0] weight13,
    input wire [15:0] value14,
    input wire [15:0] weight14,
    input wire [15:0] value15,
    input wire [15:0] weight15,
    output wire [47:0] result
);
    wire result_valid_unused;
    cnn_v10_pw_dsp16_half2x_fused_alu fused_half2x (
        .slow_clk(ap_clk), .slow_rst(ap_rst), .slow_ce(ap_ce),
        .fast_clk(pw_fast_clk), .fast_rst(pw_fast_rst),
        .in_valid(1'b1), .prior(prior),
        .value0(value0), .weight0(weight0),
        .value1(value1), .weight1(weight1),
        .value2(value2), .weight2(weight2),
        .value3(value3), .weight3(weight3),
        .value4(value4), .weight4(weight4),
        .value5(value5), .weight5(weight5),
        .value6(value6), .weight6(weight6),
        .value7(value7), .weight7(weight7),
        .value8(value8), .weight8(weight8),
        .value9(value9), .weight9(weight9),
        .value10(value10), .weight10(weight10),
        .value11(value11), .weight11(weight11),
        .value12(value12), .weight12(weight12),
        .value13(value13), .weight13(weight13),
        .value14(value14), .weight14(weight14),
        .value15(value15), .weight15(weight15),
        .out_valid(result_valid_unused), .result(result));
endmodule
