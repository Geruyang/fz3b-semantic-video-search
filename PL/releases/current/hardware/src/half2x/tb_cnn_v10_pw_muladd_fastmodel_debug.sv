`timescale 1ns/1ps
module tb_cnn_v10_pw_muladd_fastmodel_debug;
  logic clk=0,rst=1,ce=1;
  logic [15:0] value=0,weight=0;
  logic [47:0] c_value=0,pcin=0;
  wire [47:0] actual_p,actual_pcout,model_p,model_pcout;
  always #1.25 clk=~clk;
  cnn_v10_pw_dsp_muladd #(.ADD_SOURCE(1)) a(
    .ap_clk(clk),.ap_rst(rst),.ap_ce(ce),.value(value),.weight(weight),
    .c_value(c_value),.pcin(pcin),.p(actual_p),.pcout(actual_pcout));
  cnn_v10_pw_dsp_muladd_fastmodel #(.ADD_SOURCE(1)) m(
    .ap_clk(clk),.ap_rst(rst),.ap_ce(ce),.value(value),.weight(weight),
    .c_value(c_value),.pcin(pcin),.p(model_p),.pcout(model_pcout));
  initial begin
    repeat(50) @(negedge clk); rst=0; value=16'd2;weight=16'd3;c_value=48'd5;
    repeat(12) begin @(posedge clk);#2ps;$display("MULADD_DEBUG t=%0t actual=%h model=%h",$time,actual_p,model_p);end
    $finish;
  end
endmodule
