`timescale 1ns/1ps
module axi_read_fifo_tb;
 logic clk=0,rst=1;always #5 clk=~clk;
 logic [63:0] rd_base_addr;
 logic  rd_cmd_valid;
 logic  rd_cmd_ready;
 logic [31:0] rd_cmd_addr;
 logic [5:0] rd_cmd_words;
 logic [31:0] rd_error;
 logic  rd_idle;
 logic  rd_data_valid;
 logic  rd_data_ready;
 logic [127:0] rd_data;
 logic [1-1:0] rd_m_axi_arid;
 logic [63:0] rd_m_axi_araddr;
 logic [7:0] rd_m_axi_arlen;
 logic [2:0] rd_m_axi_arsize;
 logic [1:0] rd_m_axi_arburst;
 logic  rd_m_axi_arlock;
 logic [3:0] rd_m_axi_arcache;
 logic [2:0] rd_m_axi_arprot;
 logic [3:0] rd_m_axi_arqos;
 logic  rd_m_axi_arvalid;
 logic  rd_m_axi_arready;
 logic [1-1:0] rd_m_axi_rid;
 logic [127:0] rd_m_axi_rdata;
 logic [1:0] rd_m_axi_rresp;
 logic  rd_m_axi_rlast;
 logic  rd_m_axi_rvalid;
 logic  rd_m_axi_rready;
 cnn_axi_read rd_dut(.clk(clk),
.rst(rst),
.base_addr(rd_base_addr),
.cmd_valid(rd_cmd_valid),
.cmd_ready(rd_cmd_ready),
.cmd_addr(rd_cmd_addr),
.cmd_words(rd_cmd_words),
.error(rd_error),
.idle(rd_idle),
.data_valid(rd_data_valid),
.data_ready(rd_data_ready),
.data(rd_data),
.m_axi_arid(rd_m_axi_arid),
.m_axi_araddr(rd_m_axi_araddr),
.m_axi_arlen(rd_m_axi_arlen),
.m_axi_arsize(rd_m_axi_arsize),
.m_axi_arburst(rd_m_axi_arburst),
.m_axi_arlock(rd_m_axi_arlock),
.m_axi_arcache(rd_m_axi_arcache),
.m_axi_arprot(rd_m_axi_arprot),
.m_axi_arqos(rd_m_axi_arqos),
.m_axi_arvalid(rd_m_axi_arvalid),
.m_axi_arready(rd_m_axi_arready),
.m_axi_rid(rd_m_axi_rid),
.m_axi_rdata(rd_m_axi_rdata),
.m_axi_rresp(rd_m_axi_rresp),
.m_axi_rlast(rd_m_axi_rlast),
.m_axi_rvalid(rd_m_axi_rvalid),
.m_axi_rready(rd_m_axi_rready));

 integer cycle=0,left_words=0,bus_index=0,pops=0,rbeats=0,arcount=0;
 integer due=0,last_r=-1,last_pop=-1,first_r=-1,stall_cycles=0,period=1,case_start;
 logic consumed_r=0,ar_stall=0,client_stall=0;
 logic[63:0] active_addr;
 logic[71:0] held_ar;logic[127:0] held_client;
 function automatic logic[127:0] memory_word(input logic[63:0] a);
  memory_word={a^64'h479a3efca26db815,a^64'h28df70a1b36c958e};
 endfunction
 always @(negedge clk)begin
  rd_m_axi_arready=cycle>case_start+10;
  rd_data_ready=(cycle%period)==0;
  if(!rd_m_axi_rvalid || consumed_r)begin
   rd_m_axi_rvalid=left_words>0 && cycle>=due && cycle%2==0;
   rd_m_axi_rdata=memory_word(active_addr+64'(bus_index)*16);
   rd_m_axi_rlast=left_words==1;
  end
 end
 always @(posedge clk)begin
  cycle<=cycle+1;consumed_r<=rd_m_axi_rvalid&&rd_m_axi_rready;
  if(!rst)begin
   if(ar_stall && (!rd_m_axi_arvalid || {rd_m_axi_araddr,rd_m_axi_arlen}!==held_ar))$fatal(1,"AR stability");
   if(client_stall && (!rd_data_valid || rd_data!==held_client))$fatal(1,"client stability");
   if(rd_m_axi_arvalid&&rd_m_axi_arready)begin
    if(left_words!=0 || arcount!=0)$fatal(1,"multiple physical bursts");
    if(rd_m_axi_arlen!=31 || rd_m_axi_araddr!==rd_base_addr+32'd4096)$fatal(1,"command shape");
    active_addr<=rd_m_axi_araddr;left_words<=32;bus_index<=0;due<=cycle+31;arcount<=arcount+1;
   end
   if(rd_m_axi_rvalid&&!rd_m_axi_rready)stall_cycles<=stall_cycles+1;
   if(rd_m_axi_rvalid&&rd_m_axi_rready)begin
    left_words<=left_words-1;bus_index<=bus_index+1;rbeats<=rbeats+1;
    if(first_r==-1)first_r<=cycle;
    if(rd_m_axi_rlast)last_r<=cycle;
   end
   if(rd_data_valid&&rd_data_ready)begin
    if(pops>=32 || rd_data!==memory_word(rd_base_addr+32'd4096+64'(pops)*16))$fatal(1,"independent payload check %d",pops);
    pops<=pops+1;last_pop<=cycle;
   end
   if(rbeats==32 && pops<32 && (rd_cmd_ready || rd_idle))$fatal(1,"next command permitted before FIFO drain");
   ar_stall<=rd_m_axi_arvalid&&!rd_m_axi_arready;held_ar<={rd_m_axi_araddr,rd_m_axi_arlen};
   client_stall<=rd_data_valid&&!rd_data_ready;held_client<=rd_data;
  end else begin ar_stall<=0;client_stall<=0;rbeats<=0;pops<=0;arcount<=0;left_words<=0;bus_index<=0;consumed_r<=0;last_r<=-1;last_pop<=-1;first_r<=-1;stall_cycles<=0;end
 end
 task automatic run_case(input integer slow_period);
 begin
  @(negedge clk);period=slow_period;case_start=cycle;
  left_words=0;bus_index=0;pops=0;rbeats=0;arcount=0;last_r=-1;last_pop=-1;first_r=-1;stall_cycles=0;
  rd_cmd_addr=256;rd_cmd_words=32;rd_cmd_valid=1;
  do @(posedge clk);while(!rd_cmd_ready);
  @(negedge clk);rd_cmd_valid=0;
  wait(rd_idle);@(negedge clk);
  if(pops!=32||rbeats!=32||arcount!=1||rd_error!==0)$fatal(1,"completion/counters");
  $display("READ_FIFO_CASE period=%0d physical_first_to_last=%0d Rstall=%0d last_R=%0d last_client=%0d client_lag=%0d",period,last_r-first_r,stall_cycles,last_r,last_pop,last_pop-last_r);
  if(period==9 && (last_r>=last_pop || stall_cycles!=0))$fatal(1,"response not independently buffered from slow consumer");
 end
 endtask
 task automatic full_buffer_reset;
 begin
  @(negedge clk);period=100000;case_start=cycle;
  left_words=0;bus_index=0;pops=0;rbeats=0;arcount=0;last_r=-1;last_pop=-1;first_r=-1;stall_cycles=0;
  rd_cmd_addr=256;rd_cmd_words=32;rd_cmd_valid=1;
  do @(posedge clk);while(!rd_cmd_ready);
  @(negedge clk);rd_cmd_valid=0;
  wait(rbeats==32);@(negedge clk);
  if(pops!=0 || !rd_data_valid || rd_cmd_ready || rd_idle || stall_cycles!=0)$fatal(1,"full32-word reservation failed");
  repeat(8)@(negedge clk);
  // Unit-local reset aborts the buffered command and its slave model together.
  rst=1;left_words=0;rd_m_axi_rvalid=0;consumed_r=0;
  repeat(3)@(negedge clk);rst=0;
  if(!rd_idle || rd_data_valid || rd_error!==0)$fatal(1,"buffered reset failed");
  $display("READ_FIFO_FULL32_AND_RESET PASS");
 end
 endtask
 initial begin
  case_start=0;rd_base_addr=64'h123450000000;rd_cmd_valid=0;rd_cmd_addr=0;rd_cmd_words=0;
  rd_m_axi_arready=0;rd_m_axi_rid=0;rd_m_axi_rresp=0;rd_m_axi_rvalid=0;rd_m_axi_rdata=0;rd_m_axi_rlast=0;rd_data_ready=0;
  repeat(4)@(negedge clk);rst=0;
  run_case(1);run_case(9);full_buffer_reset();run_case(1);
  $display("PASS READ RESPONSE FIFO long-first-beat/odd-consumer/payload/next-command-gate");$finish;
 end
 initial begin #20000;$fatal(1,"timeout");end
endmodule
