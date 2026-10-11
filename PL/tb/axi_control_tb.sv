`timescale 1ns/1ps
module axi_control_tb;
 logic clk=0,rst=1;always #5 clk=~clk;
 logic [11:0] s_axi_control_awaddr,s_axi_control_araddr;
 logic s_axi_control_awvalid,s_axi_control_awready,s_axi_control_wvalid,s_axi_control_wready;
 logic [31:0] s_axi_control_wdata,s_axi_control_rdata;
 logic [3:0] s_axi_control_wstrb;
 logic [1:0] s_axi_control_bresp,s_axi_control_rresp;
 logic s_axi_control_bvalid,s_axi_control_bready,s_axi_control_arvalid,s_axi_control_arready,s_axi_control_rvalid,s_axi_control_rready;
 logic [63:0] params_pw1;
 logic [63:0] params_pw2;
 logic [63:0] activation_a_rd;
 logic [63:0] activation_a_wr;
 logic [63:0] activation_b_rd;
 logic [63:0] activation_b_wr;
 logic [31:0] profile;
 logic [31:0] block_count;
 logic [31:0] params_words;
 logic [31:0] slot_words;
 logic [31:0] arena_words;
 logic [31:0] flags;
 cnn_control dut(.*);
 task automatic wr(input integer addr,input logic [31:0] value,input logic[3:0] strobe,input integer order);
 begin
  if(order==0)begin
   @(negedge clk);s_axi_control_wdata=value;s_axi_control_wstrb=strobe;s_axi_control_wvalid=1;
   do @(posedge clk);while(!s_axi_control_wready);
   @(negedge clk);s_axi_control_wvalid=0;
   repeat(3)@(negedge clk);
   s_axi_control_awaddr=addr;s_axi_control_awvalid=1;
   do @(posedge clk);while(!s_axi_control_awready);
   @(negedge clk);s_axi_control_awvalid=0;
  end else begin
   @(negedge clk);s_axi_control_awaddr=addr;s_axi_control_awvalid=1;
   do @(posedge clk);while(!s_axi_control_awready);
   @(negedge clk);s_axi_control_awvalid=0;
   repeat(3)@(negedge clk);
   s_axi_control_wdata=value;s_axi_control_wstrb=strobe;s_axi_control_wvalid=1;
   do @(posedge clk);while(!s_axi_control_wready);
   @(negedge clk);s_axi_control_wvalid=0;
  end
  wait(s_axi_control_bvalid);
  repeat(4)@(negedge clk);
  if(!s_axi_control_bvalid||s_axi_control_bresp!=0)$fatal(1,"B stability");
  s_axi_control_bready=1;@(negedge clk);s_axi_control_bready=0;
 end
 endtask
 task automatic rd(input integer addr,input logic[31:0] expected);
 begin
  @(negedge clk);s_axi_control_araddr=addr;s_axi_control_arvalid=1;
  do @(posedge clk);while(!s_axi_control_arready);
  @(negedge clk);s_axi_control_arvalid=0;
  wait(s_axi_control_rvalid);
  repeat(4)@(negedge clk);
  if(!s_axi_control_rvalid||s_axi_control_rdata!==expected||s_axi_control_rresp!=0)$fatal(1,"read %h got %h expected %h",addr,s_axi_control_rdata,expected);
  s_axi_control_rready=1;@(negedge clk);s_axi_control_rready=0;
 end
 endtask
 initial begin
  s_axi_control_awvalid=0;s_axi_control_wvalid=0;s_axi_control_bready=0;s_axi_control_arvalid=0;s_axi_control_rready=0;
  s_axi_control_awaddr=0;s_axi_control_wdata=0;s_axi_control_wstrb=0;s_axi_control_araddr=0;
  repeat(3)@(negedge clk);rst=0;
  wr('h10,32'hdeadbeef,15,0);wr('h14,32'h12345678,15,1);
  wr('h11,32'haabbccdd,5,0);rd('h10,32'hdebb_bedd);
  rd('h14,32'h12345678);
  wr('h80,32'h10203040,15,1);rd('h80,32'h10203040);
  wr(0,32'hffffffff,15,0);rd(0,0);rd('h18,0);
  if(params_pw1!=64'h12345678debbbedd)$fatal(1,"pointer map");
  // Exercise every defined pointer half and scalar with alternating AW/W order.
  for(integer k=0;k<6;k++)begin
   wr('h10+k*12,32'h11000000+k,15,k%2);rd('h10+k*12,32'h11000000+k);
   wr('h14+k*12,32'h22000000+k,15,(k+1)%2);rd('h14+k*12,32'h22000000+k);
   wr('h58+k*8,32'h33000000+k,15,k%2);rd('h58+k*8,32'h33000000+k);
  end
  @(negedge clk);rst=1;repeat(3)@(negedge clk);rst=0;rd('h10,0);rd('h80,0);
  $display("PASS CONTROL independent AW/W, WSTRB, alignment, reserved, stable B/R");$finish;
 end
 initial begin #30000;$fatal(1,"timeout");end
endmodule
