`timescale 1ns/1ps
module math_missing; logic clk=0,rst=1; logic sr,mv; logic signed [15:0] md; cnn_scale dut(.clk,.rst,.s_valid(1'b0),.s_ready(sr),.s_value(48'sd0),.s_multiplier(32'sd0),.s_shift(6'd0),.m_valid(mv),.m_ready(1'b1),.m_data(md)); endmodule
