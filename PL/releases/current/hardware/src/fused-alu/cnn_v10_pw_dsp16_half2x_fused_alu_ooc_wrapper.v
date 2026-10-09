`timescale 1ns/1ps

// Physical OOC timing harness for cnn_v10_pw_dsp16_half2x.
//
// The experiment module will be called by registered HLS logic.  This
// wrapper supplies real same-domain launch/capture flip-flops so Vivado can
// place and route the module boundary rather than timing a zero-delay package
// port directly into the DUT.  The wrapper's external stimulus ports are test
// harness boundaries and are excluded by the OOC XDC; all register-to-register
// paths through and across the DUT remain timed.
module cnn_v10_pw_dsp16_half2x_fused_alu_ooc_wrapper (
    input  wire         clock_400_in,
    input  wire         reset_async,
    input  wire         slow_ce_in,
    input  wire         in_valid_in,
    input  wire [47:0]  prior_in,
    input  wire [255:0] value_bus_in,
    input  wire [255:0] weight_bus_in,
    output wire         out_valid_out,
    output wire [47:0]  result_out
);
    wire fast_clk;
    wire slow_clk;
    cnn_v10_half2x_clock_tree clock_tree (
        .root_clk_400(clock_400_in),
        .pw_local_clk_400(fast_clk),
        .driver_job_clk_200(slow_clk)
    );

    (* ASYNC_REG = "TRUE" *) reg slow_rst_q1, slow_rst_q2;
    (* ASYNC_REG = "TRUE" *) reg fast_rst_q1, fast_rst_q2;

    always @(posedge slow_clk or posedge reset_async or posedge fast_rst_q2) begin
        if (reset_async || fast_rst_q2) begin
            slow_rst_q1 <= 1'b1;
            slow_rst_q2 <= 1'b1;
        end else begin
            slow_rst_q1 <= 1'b0;
            slow_rst_q2 <= slow_rst_q1;
        end
    end

    always @(posedge fast_clk or posedge reset_async) begin
        if (reset_async) begin
            fast_rst_q1 <= 1'b1;
            fast_rst_q2 <= 1'b1;
        end else begin
            fast_rst_q1 <= 1'b0;
            fast_rst_q2 <= fast_rst_q1;
        end
    end

    reg slow_ce_launch;
    reg in_valid_launch;
    reg [47:0] prior_launch;
    reg [255:0] value_bus_launch;
    reg [255:0] weight_bus_launch;
    always @(posedge slow_clk) begin
        if (slow_rst_q2) begin
            slow_ce_launch <= 1'b0;
            in_valid_launch <= 1'b0;
            prior_launch <= 48'd0;
            value_bus_launch <= 256'd0;
            weight_bus_launch <= 256'd0;
        end else begin
            slow_ce_launch <= slow_ce_in;
            in_valid_launch <= in_valid_in;
            prior_launch <= prior_in;
            value_bus_launch <= value_bus_in;
            weight_bus_launch <= weight_bus_in;
        end
    end

    wire dut_out_valid;
    wire [47:0] dut_result;
    cnn_v10_pw_dsp16_half2x_fused_alu dut (
        .slow_clk(slow_clk), .slow_rst(slow_rst_q2),
        .slow_ce(slow_ce_launch), .fast_clk(fast_clk),
        .fast_rst(fast_rst_q2), .in_valid(in_valid_launch),
        .prior(prior_launch),
        .value0(value_bus_launch[15:0]), .weight0(weight_bus_launch[15:0]),
        .value1(value_bus_launch[31:16]), .weight1(weight_bus_launch[31:16]),
        .value2(value_bus_launch[47:32]), .weight2(weight_bus_launch[47:32]),
        .value3(value_bus_launch[63:48]), .weight3(weight_bus_launch[63:48]),
        .value4(value_bus_launch[79:64]), .weight4(weight_bus_launch[79:64]),
        .value5(value_bus_launch[95:80]), .weight5(weight_bus_launch[95:80]),
        .value6(value_bus_launch[111:96]), .weight6(weight_bus_launch[111:96]),
        .value7(value_bus_launch[127:112]), .weight7(weight_bus_launch[127:112]),
        .value8(value_bus_launch[143:128]), .weight8(weight_bus_launch[143:128]),
        .value9(value_bus_launch[159:144]), .weight9(weight_bus_launch[159:144]),
        .value10(value_bus_launch[175:160]), .weight10(weight_bus_launch[175:160]),
        .value11(value_bus_launch[191:176]), .weight11(weight_bus_launch[191:176]),
        .value12(value_bus_launch[207:192]), .weight12(weight_bus_launch[207:192]),
        .value13(value_bus_launch[223:208]), .weight13(weight_bus_launch[223:208]),
        .value14(value_bus_launch[239:224]), .weight14(weight_bus_launch[239:224]),
        .value15(value_bus_launch[255:240]), .weight15(weight_bus_launch[255:240]),
        .out_valid(dut_out_valid), .result(dut_result)
    );

    reg out_valid_capture;
    reg [47:0] result_capture;
    always @(posedge slow_clk) begin
        if (slow_rst_q2) begin
            out_valid_capture <= 1'b0;
            result_capture <= 48'd0;
        end else begin
            out_valid_capture <= dut_out_valid;
            result_capture <= dut_result;
        end
    end

    assign out_valid_out = out_valid_capture;
    assign result_out = result_capture;
endmodule
