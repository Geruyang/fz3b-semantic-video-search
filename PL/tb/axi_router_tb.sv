`timescale 1ns/1ps
module axi_router_tb;
 logic clk=0,rst=1;always #5 clk=~clk;
 logic [2:0] cmd_valid,cmd_ready,data_valid,data_ready,commit_valid,commit_ready;
 logic [31:0] cmd_addr[3];logic [5:0] cmd_words[3];logic [127:0] data[3];
 logic m_cmd_valid,m_cmd_ready,m_data_valid,m_data_ready,m_commit_valid,m_commit_ready;
 logic [31:0] m_cmd_addr;logic [5:0] m_cmd_words;logic [127:0] m_data;
 cnn_write_router #(.N(3)) dut(.*);
 integer packets=0;
 task automatic transfer(input integer owner);
  begin
   wait(m_cmd_valid);
   if(m_cmd_addr!=cmd_addr[owner])$fatal(1,"grant order");
   repeat(3)@(negedge clk);
   if(m_cmd_addr!=cmd_addr[owner])$fatal(1,"grant changed under stall");
   m_cmd_ready=1;@(negedge clk);m_cmd_ready=0;cmd_valid[owner]=0;
   for(integer k=0;k<3;k++)begin
    data_valid[owner]=1;data[owner]=128'(owner*10+k);
    repeat(2)@(negedge clk);
    if(m_data!=128'(owner*10+k) || !m_data_valid)$fatal(1,"payload route");
    if(data_ready!=0)$fatal(1,"unexpected data ready");
    m_data_ready=1;
    @(negedge clk);m_data_ready=0;
   end
   data_valid[owner]=0;m_commit_valid=1;
   repeat(3)@(negedge clk);
   if(commit_valid!=(3'b001<<owner)||m_commit_ready)$fatal(1,"commit route");
   commit_ready[owner]=1;@(negedge clk);
   m_commit_valid=0;commit_ready=0;packets=packets+1;
  end
 endtask
 initial begin
  cmd_valid=0;data_valid=0;commit_ready=0;m_cmd_ready=0;m_data_ready=0;m_commit_valid=0;
  for(integer k=0;k<3;k++)begin cmd_addr[k]=100+k;cmd_words[k]=3;data[k]=0;end
  repeat(3)@(negedge clk);rst=0;
  cmd_valid=3'b100;
  // Lock client2 while lower-priority clients arrive during command backpressure.
  repeat(2)@(negedge clk);cmd_valid=3'b111;
  transfer(2);transfer(0);transfer(1);
  cmd_valid=3'b111;
  transfer(2);transfer(0);transfer(1);
  $display("PASS WRITE ROUTER packets=%0d grant hold and round robin",packets);$finish;
 end
 initial begin #20000;$fatal(1,"timeout");end
endmodule
