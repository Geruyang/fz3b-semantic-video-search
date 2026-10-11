`timescale 1ns/1ps
module math_fifo_tb #(parameter int DEPTH=16);
 logic clk=0,rst=1;always #2.5 clk=~clk;
 logic s_valid,s_ready,m_valid,m_ready;logic[31:0]s_data,m_data;logic[$clog2(DEPTH+1)-1:0]level;
 int sent=0,received=0,cycle=0;logic stalled=0;logic[31:0]saved;
 cnn_fifo #(.WIDTH(32),.DEPTH(DEPTH)) dut(.*);
 always_comb begin
   s_data=sent;s_valid=!rst&&sent<10000&&(cycle<2000||cycle%7!=0);
   m_ready=cycle<DEPTH+10?0:(cycle<2000?1:(cycle%13>4));
 end
 always @(posedge clk) if(!rst) begin
   cycle<=cycle+1;
   if(stalled&&(!m_valid||m_data!==saved))$fatal(1,"unstable FIFO");
   stalled<=m_valid&&!m_ready;saved<=m_data;
   if(s_valid&&s_ready)sent<=sent+1;
   if(m_valid&&m_ready)begin if(m_data!==received)$fatal(1,"FIFO order");received<=received+1;end
   if(cycle>DEPTH+20&&cycle<1990&&(!m_valid||!s_ready))$fatal(1,"FIFO bubble");
   if(level!==sent-received)$fatal(1,"FIFO level");
   if(received==10000)begin $display("PASS math_fifo depth=%0d words=10000 sustained_II=1 wraps=%0d",DEPTH,sent/DEPTH);$finish;end
   if(cycle>30000)$fatal(1,"timeout");
 end
 initial begin repeat(4)@(negedge clk);rst=0;end
endmodule
