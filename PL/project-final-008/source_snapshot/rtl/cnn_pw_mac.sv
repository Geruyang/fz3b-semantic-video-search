`timescale 1ns/1ps
// Four-output elastic tile MAC. Hand-written DSP source provenance:
// releases/final/PL/transforms/cnn_v10_pw_dsp16_{half2x_fused_alu,fused_alu_primitives}.v
// Related clocks must have coincident rising edges and a 2:1 frequency ratio.
module cnn_pw_mac(
 input wire clk,rst,fast_clk,fast_rst,
 input wire s_valid, output wire s_ready,
 input wire [255:0] s_values,input wire [1023:0] s_weights,
 input wire [191:0] s_prior,
 output reg m_valid,input wire m_ready,output reg [191:0] m_result
);
 wire advance=!m_valid || m_ready;
 assign s_ready=advance;
 wire [3:0] lane_valid;
 wire [191:0] lane_result;
 genvar o;
 generate for(o=0;o<4;o=o+1) begin: output_lane
  cnn_pw_dsp16_half2x_fused_alu leaf(
   .slow_clk(clk),.slow_rst(rst),.slow_ce(advance),
   .fast_clk(fast_clk),.fast_rst(fast_rst),.in_valid(s_valid),
   .prior(s_prior[o*48+:48]),
   .value0(s_values[0*16+:16]),.weight0(s_weights[(o*16+0)*16+:16]),
   .value1(s_values[1*16+:16]),.weight1(s_weights[(o*16+1)*16+:16]),
   .value2(s_values[2*16+:16]),.weight2(s_weights[(o*16+2)*16+:16]),
   .value3(s_values[3*16+:16]),.weight3(s_weights[(o*16+3)*16+:16]),
   .value4(s_values[4*16+:16]),.weight4(s_weights[(o*16+4)*16+:16]),
   .value5(s_values[5*16+:16]),.weight5(s_weights[(o*16+5)*16+:16]),
   .value6(s_values[6*16+:16]),.weight6(s_weights[(o*16+6)*16+:16]),
   .value7(s_values[7*16+:16]),.weight7(s_weights[(o*16+7)*16+:16]),
   .value8(s_values[8*16+:16]),.weight8(s_weights[(o*16+8)*16+:16]),
   .value9(s_values[9*16+:16]),.weight9(s_weights[(o*16+9)*16+:16]),
   .value10(s_values[10*16+:16]),.weight10(s_weights[(o*16+10)*16+:16]),
   .value11(s_values[11*16+:16]),.weight11(s_weights[(o*16+11)*16+:16]),
   .value12(s_values[12*16+:16]),.weight12(s_weights[(o*16+12)*16+:16]),
   .value13(s_values[13*16+:16]),.weight13(s_weights[(o*16+13)*16+:16]),
   .value14(s_values[14*16+:16]),.weight14(s_weights[(o*16+14)*16+:16]),
   .value15(s_values[15*16+:16]),.weight15(s_weights[(o*16+15)*16+:16]),
   .out_valid(lane_valid[o]),.result(lane_result[o*48+:48]));
 end endgenerate
 always @(posedge clk) begin
  if(rst) begin m_valid<=0;m_result<=0;end
  else if(advance) begin m_valid<=lane_valid[0];if(lane_valid[0]) m_result<=lane_result;end
 end
endmodule
