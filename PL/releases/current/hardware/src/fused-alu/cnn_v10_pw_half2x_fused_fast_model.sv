`timescale 1ns/1ps

// Verification-only fast-domain model for the fused OPMODE=0x195 candidate.
// It models the externally visible seven enabled-fast-cycle pipeline without
// reusing the DSP primitive implementation.
module cnn_v10_pw_half2x_fused_fast_model (
    input logic fast_clk, input logic fast_rst, input logic fast_ce,
    input logic launch_valid, input logic launch_phase1,
    input logic [47:0] prior,
    input logic [15:0] value0, weight0, value1, weight1,
    input logic [15:0] value2, weight2, value3, weight3,
    input logic [15:0] value4, weight4, value5, weight5,
    input logic [15:0] value6, weight6, value7, weight7,
    output logic partial_valid, output logic partial_phase1,
    output logic [47:0] partial
);
    logic [47:0] data_pipe [0:6];
    logic [6:0] valid_pipe, phase_pipe;
    integer i;
    logic signed [47:0] next_sum;

    always_comb begin
        next_sum = $signed(prior);
        next_sum = next_sum + $signed(value0) * $signed(weight0);
        next_sum = next_sum + $signed(value1) * $signed(weight1);
        next_sum = next_sum + $signed(value2) * $signed(weight2);
        next_sum = next_sum + $signed(value3) * $signed(weight3);
        next_sum = next_sum + $signed(value4) * $signed(weight4);
        next_sum = next_sum + $signed(value5) * $signed(weight5);
        next_sum = next_sum + $signed(value6) * $signed(weight6);
        next_sum = next_sum + $signed(value7) * $signed(weight7);
    end

    always_ff @(posedge fast_clk) begin
        if (fast_rst) begin
            valid_pipe <= '0;
            phase_pipe <= '0;
            for (i = 0; i < 7; i = i + 1) data_pipe[i] <= '0;
        end else if (fast_ce) begin
            valid_pipe <= {valid_pipe[5:0], launch_valid};
            phase_pipe <= {phase_pipe[5:0], launch_phase1};
            data_pipe[0] <= next_sum;
            for (i = 1; i < 7; i = i + 1) data_pipe[i] <= data_pipe[i-1];
        end
    end

    assign partial_valid = valid_pipe[6];
    assign partial_phase1 = phase_pipe[6];
    assign partial = data_pipe[6];
endmodule
