`timescale 1ns/1ps
// TEST ONLY. Replaces only DSP arithmetic with an exact seven-fast-edge pipeline.
// The related-clock epoch, atomic two-phase launch, FIFO and slow due pipeline
// below are copied unchanged from production cnn_dsp_primitives.v.
module cnn_pw_dsp8_fast_fused_alu(
 input wire fast_clk,fast_rst,fast_ce,launch_valid,launch_phase1,
 input wire[47:0] prior,
 input wire[15:0] value0,weight0,value1,weight1,value2,weight2,value3,weight3,
 input wire[15:0] value4,weight4,value5,weight5,value6,weight6,value7,weight7,
 output wire partial_valid,partial_phase1,output wire[47:0] partial
);
 reg[6:0] valid_pipe,phase_pipe;
 reg signed[47:0] p[0:6];
 reg signed[47:0] dot;
 always @* begin
  dot=$signed(prior);
  dot=dot+$signed(value0)*$signed(weight0)+$signed(value1)*$signed(weight1);
  dot=dot+$signed(value2)*$signed(weight2)+$signed(value3)*$signed(weight3);
  dot=dot+$signed(value4)*$signed(weight4)+$signed(value5)*$signed(weight5);
  dot=dot+$signed(value6)*$signed(weight6)+$signed(value7)*$signed(weight7);
 end
 always @(posedge fast_clk)begin
  if(fast_rst)begin valid_pipe<=0;phase_pipe<=0;for(integer j=0;j<7;j=j+1)p[j]<=0;end
  else if(fast_ce)begin
   valid_pipe<={valid_pipe[5:0],launch_valid};phase_pipe<={phase_pipe[5:0],launch_phase1};
   p[0]<=dot;for(integer j=1;j<7;j=j+1)p[j]<=p[j-1];
  end
 end
 assign partial_valid=valid_pipe[6];assign partial_phase1=phase_pipe[6];assign partial=p[6];
endmodule
module cnn_pw_dsp16_half2x_fused_alu (
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
            if (slow_ce) begin
                out_valid <= 1'b0;
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

    cnn_pw_dsp8_fast_fused_alu half_dot (
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




