`timescale 1ns/1ps
module pw1_mac_tb;
 reg clk=0,fast_clk=0,rst=1,fast_rst=1;
 always #2.5 clk=~clk;
 initial begin #2.5;fast_clk=1;forever #1.25 fast_clk=~fast_clk;end
 reg s_valid=0,m_ready=0;wire s_ready,m_valid;
 reg [255:0] s_values;reg [1023:0] s_weights;reg [191:0] s_prior;
 wire [191:0] m_result;
 cnn_pw_mac dut(.*);
 reg [191:0] expected[0:4095];integer wr=0,rd=0,n,i,o,cycles=0;
 reg signed[47:0] sum;reg signed[15:0] a,b;
 integer first_accept_cycle;
 reg [191:0] e;
 always @(negedge clk) if(!rst)m_ready=(cycles<200)||((cycles%97)<25);
 always @(posedge clk) if(!rst) begin
  if(s_valid && s_ready) begin
   for(o=0;o<4;o=o+1) begin
    sum=$signed(s_prior[o*48+:48]);
    for(i=0;i<16;i=i+1) begin
     a=$signed(s_values[i*16+:16]);b=$signed(s_weights[(o*16+i)*16+:16]);
     sum=sum+a*b;
    end
    e[o*48+:48]=sum;
   end
   if(wr==0)first_accept_cycle=cycles;
   expected[wr]=e;wr=wr+1;
  end
  if(m_valid && m_ready) begin
   if(rd>=wr || m_result!==expected[rd]) begin
    $display("FAIL index=%0d actual=%h expected=%h",rd,m_result,expected[rd]);$fatal;
   end
   if(rd==0)$display("MAC_FIRST_ACCEPT_TO_CONSUME_CYCLES=%0d",cycles-first_accept_cycle);
   rd=rd+1;
  end
  cycles=cycles+1;
  if(cycles>10000)$fatal(1,"timeout wr=%0d rd=%0d",wr,rd);
 end
 initial begin
  repeat(40)@(negedge clk);rst=0;fast_rst=0;
  for(n=0;n<1024;n=n+1) begin
   @(negedge clk);
   
   s_valid=1;
   for(i=0;i<16;i=i+1) s_values[i*16+:16]=(n%7==0)?16'h8000:$random;
   for(i=0;i<64;i=i+1) s_weights[i*16+:16]=(n%11==0)?16'h7fff:$random;
   for(i=0;i<4;i=i+1) s_prior[i*48+:48]={$random,$random};
   while(!s_ready) @(negedge clk);
  end
  @(negedge clk);s_valid=0;
  wait(rd==wr);repeat(4)@(negedge clk);
  $display("PASS real UNISIM DSP48E2 tiles=%0d lane_results=%0d cycles=%0d",rd,4*rd,cycles);$finish;
 end
endmodule



