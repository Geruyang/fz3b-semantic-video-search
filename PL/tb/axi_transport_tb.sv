`timescale 1ns/1ps
module axi_transport_tb;
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
 logic [63:0] wr_base_addr;
 logic  wr_cmd_valid;
 logic  wr_cmd_ready;
 logic [31:0] wr_cmd_addr;
 logic [5:0] wr_cmd_words;
 logic [31:0] wr_error;
 logic  wr_idle;
 logic  wr_data_valid;
 logic  wr_data_ready;
 logic [127:0] wr_data;
 logic  wr_commit_valid;
 logic  wr_commit_ready;
 logic [1-1:0] wr_m_axi_awid;
 logic [63:0] wr_m_axi_awaddr;
 logic [7:0] wr_m_axi_awlen;
 logic [2:0] wr_m_axi_awsize;
 logic [1:0] wr_m_axi_awburst;
 logic  wr_m_axi_awlock;
 logic [3:0] wr_m_axi_awcache;
 logic [2:0] wr_m_axi_awprot;
 logic [3:0] wr_m_axi_awqos;
 logic  wr_m_axi_awvalid;
 logic  wr_m_axi_awready;
 logic [127:0] wr_m_axi_wdata;
 logic [15:0] wr_m_axi_wstrb;
 logic  wr_m_axi_wlast;
 logic  wr_m_axi_wvalid;
 logic  wr_m_axi_wready;
 logic [1-1:0] wr_m_axi_bid;
 logic [1:0] wr_m_axi_bresp;
 logic  wr_m_axi_bvalid;
 logic  wr_m_axi_bready;
 cnn_axi_write wr_dut(.clk(clk),
.rst(rst),
.base_addr(wr_base_addr),
.cmd_valid(wr_cmd_valid),
.cmd_ready(wr_cmd_ready),
.cmd_addr(wr_cmd_addr),
.cmd_words(wr_cmd_words),
.error(wr_error),
.idle(wr_idle),
.data_valid(wr_data_valid),
.data_ready(wr_data_ready),
.data(wr_data),
.commit_valid(wr_commit_valid),
.commit_ready(wr_commit_ready),
.m_axi_awid(wr_m_axi_awid),
.m_axi_awaddr(wr_m_axi_awaddr),
.m_axi_awlen(wr_m_axi_awlen),
.m_axi_awsize(wr_m_axi_awsize),
.m_axi_awburst(wr_m_axi_awburst),
.m_axi_awlock(wr_m_axi_awlock),
.m_axi_awcache(wr_m_axi_awcache),
.m_axi_awprot(wr_m_axi_awprot),
.m_axi_awqos(wr_m_axi_awqos),
.m_axi_awvalid(wr_m_axi_awvalid),
.m_axi_awready(wr_m_axi_awready),
.m_axi_wdata(wr_m_axi_wdata),
.m_axi_wstrb(wr_m_axi_wstrb),
.m_axi_wlast(wr_m_axi_wlast),
.m_axi_wvalid(wr_m_axi_wvalid),
.m_axi_wready(wr_m_axi_wready),
.m_axi_bid(wr_m_axi_bid),
.m_axi_bresp(wr_m_axi_bresp),
.m_axi_bvalid(wr_m_axi_bvalid),
.m_axi_bready(wr_m_axi_bready));

 integer cycle=0,r_total=0,w_total=0,b_total=0,ar_total=0,aw_total=0;
 integer rn=0,ri=0,wi=0,bdelay=0;
 logic rp=0,aws=0,wls=0,bp=0,r_hs=0;
 integer rmode=0,wmode=0;
 logic [63:0] expected_ra,expected_wa,bus_read_base;
 logic [127:0] expected_read[4096];
 integer expected_tail=0;
 function automatic logic [127:0] memory_word(input logic[63:0] byte_addr);
  memory_word={byte_addr ^ 64'hc59ad6e73142b80f,byte_addr ^ 64'h8ed2176a90bc435f};
 endfunction
 always @(negedge clk) begin
  rd_m_axi_rid=rmode==5 ? 1'b1:1'b0;
  rd_m_axi_arready=cycle>12 && cycle%3!=0;
  // Slave VALID/payload remain asserted until handshake, including consumer stalls.
  if(!rd_m_axi_rvalid || r_hs) begin
   rd_m_axi_rvalid=rp && (rmode==4 || cycle%4!=0);
   rd_m_axi_rdata=memory_word(bus_read_base+64'(ri)*16);
   rd_m_axi_rresp=rmode==1 ? 2'b10:0;
   rd_m_axi_rlast=(rmode==2)?ri==0:((rmode==3)?ri==rn:ri==rn-1);
  end
  wr_m_axi_awready=cycle>20 && cycle%5==0;
  wr_m_axi_wready=cycle>8 && (wmode==2 || cycle%3!=0);
  wr_m_axi_bvalid=bp && bdelay==0;
  wr_m_axi_bresp=wmode==1 ? 2'b10:0;
  rd_data_ready=rmode==4 || cycle%5!=0;
 end
 always @(posedge clk) begin
  if(rst) begin cycle<=0;rp<=0;aws<=0;wls<=0;bp<=0;end
  else begin
   cycle<=cycle+1;
   r_hs<=rd_m_axi_rvalid && rd_m_axi_rready;
   if(rd_m_axi_arvalid && rd_m_axi_arready) begin
    if(rp) $fatal(1,"read outstanding exceeded");
    if(rd_m_axi_araddr!=expected_ra) $fatal(1,"read address %h expected %h",rd_m_axi_araddr,expected_ra);
    if(({1'b0,rd_m_axi_araddr[11:0]}+((rd_m_axi_arlen+1)*16))>4096) $fatal(1,"read crosses4K");
    expected_ra=expected_ra+((rd_m_axi_arlen+1)*16);
    bus_read_base<=rd_m_axi_araddr;rn<=rd_m_axi_arlen+1;ri<=0;rp<=1;ar_total<=ar_total+1;
   end
   if(rd_m_axi_rvalid && rd_m_axi_rready) begin
    ri<=ri+1;
    if(rd_m_axi_rlast)rp<=0;
   end
   if(rd_data_valid && rd_data_ready) begin
    if(r_total>=expected_tail)$fatal(1,"unexpected client read beat (late drain forwarded)");
    if(rd_data!==expected_read[r_total])$fatal(1,"read payload mismatch index=%0d got=%h expected=%h",r_total,rd_data,expected_read[r_total]);
    r_total<=r_total+1;
   end
   if(wr_m_axi_awvalid && wr_m_axi_awready) begin
    if(aws) $fatal(1,"double AW");
    if(wr_m_axi_awaddr!=expected_wa) $fatal(1,"write address");
    if(({1'b0,wr_m_axi_awaddr[11:0]}+((wr_m_axi_awlen+1)*16))>4096) $fatal(1,"write crosses4K");
    expected_wa=expected_wa+((wr_m_axi_awlen+1)*16);
    aws<=1;aw_total<=aw_total+1;
   end
   if(wr_m_axi_wvalid && wr_m_axi_wready) begin
    if(wr_m_axi_wdata!=128'(w_total)) $fatal(1,"write data order");
    if(wr_m_axi_wstrb!=16'hffff) $fatal(1,"write strobe");
    w_total<=w_total+1;wi<=wi+1;
    if(wr_m_axi_wlast)wls<=1;
   end
   if(aws && wls && !bp)begin bp<=1;bdelay<=9;end
   if(bp && bdelay>0)bdelay<=bdelay-1;
   if(wr_m_axi_bvalid && wr_m_axi_bready) begin
    bp<=0;aws<=0;wls<=0;wi<=0;b_total<=b_total+1;
   end
   if(wr_commit_valid && (bp || aws || wls)) $fatal(1,"early commit");
  end
 end
 task automatic read_cmd(input integer offset,words,mode);
  integer before_count;
  begin
   before_count=r_total;rmode=mode;expected_ra=rd_base_addr+offset*16;
   @(negedge clk);rd_cmd_valid=1;rd_cmd_addr=offset;rd_cmd_words=words;
   do @(posedge clk);while(!rd_cmd_ready);
   // Expected values derive from the accepted client command, independent of AR
   // split addresses, slave beat bookkeeping and observed client payload.
   for(integer j=0;j<words;j++)begin
    expected_read[expected_tail]=mode==2 && j!=0 && ((rd_base_addr+64'(offset+j)*16) & 64'hfff)!=0 ? 128'b0 : memory_word(rd_base_addr+64'(offset+j)*16);
    expected_tail=expected_tail+1;
   end
   @(negedge clk);rd_cmd_valid=0;
   wait(rd_idle);@(negedge clk);
   if(r_total-before_count!=words)$fatal(1,"read count %d expected %d",r_total-before_count,words);
  end
 endtask
 task automatic write_cmd(input integer offset,words,mode);
  integer before_count;
  begin
   before_count=w_total;wmode=mode;expected_wa=wr_base_addr+offset*16;
   @(negedge clk);wr_cmd_valid=1;wr_cmd_addr=offset;wr_cmd_words=words;
   do @(posedge clk);while(!wr_cmd_ready);
   @(negedge clk);wr_cmd_valid=0;
   for(integer j=0;j<words;j++)begin
    wr_data_valid=1;wr_data=128'(before_count+j);
    do @(posedge clk);while(!wr_data_ready);
    @(negedge clk);
   end
   wr_data_valid=0;
   wait(wr_commit_valid);
   repeat(4)@(negedge clk);
   if(!wr_commit_valid)$fatal(1,"commit unstable");
   wr_commit_ready=1;@(negedge clk);wr_commit_ready=0;
   wait(wr_idle);
   if(w_total-before_count!=words)$fatal(1,"write count");
  end
 endtask
 logic ar_stall=0,aw_stall=0,w_stall=0,d_stall=0;
 logic [71:0] ar_hold,aw_hold;
 logic [128:0] w_hold;
 logic [127:0] d_hold;
 always @(posedge clk) begin
  if(!rst)begin
   if(ar_stall && (!rd_m_axi_arvalid || {rd_m_axi_araddr,rd_m_axi_arlen}!==ar_hold))$fatal(1,"AR hold");
   if(aw_stall && (!wr_m_axi_awvalid || {wr_m_axi_awaddr,wr_m_axi_awlen}!==aw_hold))$fatal(1,"AW hold");
   if(w_stall && (!wr_m_axi_wvalid || {wr_m_axi_wdata,wr_m_axi_wlast}!==w_hold))$fatal(1,"W hold");
   if(d_stall && (!rd_data_valid || rd_data!==d_hold))$fatal(1,"read output hold");
   ar_stall<=rd_m_axi_arvalid && !rd_m_axi_arready;ar_hold<={rd_m_axi_araddr,rd_m_axi_arlen};
   aw_stall<=wr_m_axi_awvalid && !wr_m_axi_awready;aw_hold<={wr_m_axi_awaddr,wr_m_axi_awlen};
   w_stall<=wr_m_axi_wvalid && !wr_m_axi_wready;w_hold<={wr_m_axi_wdata,wr_m_axi_wlast};
   d_stall<=rd_data_valid && !rd_data_ready;d_hold<=rd_data;
  end else begin ar_stall<=0;aw_stall<=0;w_stall<=0;d_stall<=0;end
 end
 initial begin
  rd_cmd_valid=0;rd_cmd_addr=0;rd_cmd_words=0;rd_base_addr=64'h123456780000;
  rd_data_ready=0;rd_m_axi_rid=0;rd_m_axi_rvalid=0;rd_m_axi_rlast=0;rd_m_axi_rresp=0;rd_m_axi_rdata=0;rd_m_axi_arready=0;
  wr_cmd_valid=0;wr_cmd_addr=0;wr_cmd_words=0;wr_base_addr=64'habcdef120000;
  wr_data_valid=0;wr_data=0;wr_commit_ready=0;wr_m_axi_awready=0;wr_m_axi_wready=0;
  wr_m_axi_bid=0;wr_m_axi_bvalid=0;wr_m_axi_bresp=0;
  repeat(4)@(negedge clk);rst=0;
  fork
   begin read_cmd(255,32,0);read_cmd(20,1,0);read_cmd(254,4,1);read_cmd(20,4,2);read_cmd(20,4,3);read_cmd(32,32,4);read_cmd(255,4,2);read_cmd(255,4,3);read_cmd(20,4,5);end
   begin write_cmd(255,32,0);write_cmd(20,1,0);write_cmd(254,4,1);write_cmd(20,32,0);write_cmd(32,32,2);end
  join
  if(rd_error!==14 || wr_error!==2)$fatal(1,"error bits rd%h wr%h",rd_error,wr_error);
  @(negedge clk);rst=1;repeat(3)@(negedge clk);rst=0;
  if(rd_error!==0||wr_error!==0||!rd_idle||!wr_idle)$fatal(1,"sticky error reset");
  read_cmd(255,4,0);write_cmd(255,4,0);
  if(rd_error!==0||wr_error!==0)$fatal(1,"post-reset replay");
  $display("PASS AXI read_words=%0d write_words=%0d AR=%0d AW=%0d B=%0d cycles=%0d",r_total,w_total,ar_total,aw_total,b_total,cycle);$finish;
 end
 initial begin #100000;$fatal(1,"timeout");end
endmodule
