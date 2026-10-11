`timescale 1ns/1ps
module tb_cnn_full;
 import cnn_axi_pkg::*;
 logic ap_clk=0,pw_fast_clk=0,ap_rst_n=0,pw_fast_rst=1;
 always #2.5 ap_clk=~ap_clk;
 always #1.25 pw_fast_clk=~pw_fast_clk;
 logic ap_start=0,ap_done,ap_idle,ap_ready;
 logic [31:0] protocol_error; logic protocol_error_ap_vld;
 read_m2s_t rd_m[4]; read_s2m_t rd_s[4];
 write_m2s_t wr_m[2]; write_s2m_t wr_s[2];
 logic [11:0] awaddr=0,araddr=0; logic [31:0] wdata=0,rdata;
 logic [3:0] wstrb=15;logic awvalid=0,wvalid=0,arvalid=0,bready=0,rready=0;
 logic awready,wready,bvalid,arready,rvalid;logic [1:0] bresp,rresp;
 logic new_launch=0;
 logic [31:0] trace_a_feed,trace_a_dw3,trace_a_dw7,trace_a_pw1,trace_a_pw2,trace_a_write;
 logic [31:0] trace_b_feed,trace_b_dw3,trace_b_dw7,trace_b_pw1,trace_b_pw2,trace_b_write;
 localparam logic [63:0] P1=64'h10000000,P2=64'h20000000,A=64'h30000000,B=64'h40000000;
 string fixture_root="../releases/current/hardware/fixtures/full-rtl";
 int params_words,slot_words,arena_words,blocks,profile;
 int token_numer=1,token_denom=2,token_burst=32,bdelay=3;
 longint cycles,maxcycles=200000000; int repeat_count=1,selected=-1,diag_blocks=0,diag_first_pair=0,mixed=0;bit performance_pass=1;
 bit measure_active=0;longint monitor_cycle;
 logic [127:0] gold_a[32768],gold_b[32768];
 localparam logic [127:0] CANARY=128'hcafe0011dead2233beef4455abba6677;
 logic [3:0] rd_arvalid;
 assign rd_arvalid[0]=rd_m[0].arvalid;
 assign rd_arvalid[1]=rd_m[1].arvalid;
 assign rd_arvalid[2]=rd_m[2].arvalid;
 assign rd_arvalid[3]=rd_m[3].arvalid;
 logic [3:0] rd_arready;
 assign rd_s[0].arready=rd_arready[0];
 assign rd_s[1].arready=rd_arready[1];
 assign rd_s[2].arready=rd_arready[2];
 assign rd_s[3].arready=rd_arready[3];
 logic [3:0] [63:0] rd_araddr;
 assign rd_araddr[0]=rd_m[0].araddr;
 assign rd_araddr[1]=rd_m[1].araddr;
 assign rd_araddr[2]=rd_m[2].araddr;
 assign rd_araddr[3]=rd_m[3].araddr;
 logic [3:0] rd_arid;
 assign rd_arid[0]=rd_m[0].arid;
 assign rd_arid[1]=rd_m[1].arid;
 assign rd_arid[2]=rd_m[2].arid;
 assign rd_arid[3]=rd_m[3].arid;
 logic [3:0] [7:0] rd_arlen;
 assign rd_arlen[0]=rd_m[0].arlen;
 assign rd_arlen[1]=rd_m[1].arlen;
 assign rd_arlen[2]=rd_m[2].arlen;
 assign rd_arlen[3]=rd_m[3].arlen;
 logic [3:0] [2:0] rd_arsize;
 assign rd_arsize[0]=rd_m[0].arsize;
 assign rd_arsize[1]=rd_m[1].arsize;
 assign rd_arsize[2]=rd_m[2].arsize;
 assign rd_arsize[3]=rd_m[3].arsize;
 logic [3:0] [1:0] rd_arburst;
 assign rd_arburst[0]=rd_m[0].arburst;
 assign rd_arburst[1]=rd_m[1].arburst;
 assign rd_arburst[2]=rd_m[2].arburst;
 assign rd_arburst[3]=rd_m[3].arburst;
 logic [3:0] rd_rvalid;
 assign rd_s[0].rvalid=rd_rvalid[0];
 assign rd_s[1].rvalid=rd_rvalid[1];
 assign rd_s[2].rvalid=rd_rvalid[2];
 assign rd_s[3].rvalid=rd_rvalid[3];
 logic [3:0] rd_rready;
 assign rd_rready[0]=rd_m[0].rready;
 assign rd_rready[1]=rd_m[1].rready;
 assign rd_rready[2]=rd_m[2].rready;
 assign rd_rready[3]=rd_m[3].rready;
 logic [3:0] [127:0] rd_rdata;
 assign rd_s[0].rdata=rd_rdata[0];
 assign rd_s[1].rdata=rd_rdata[1];
 assign rd_s[2].rdata=rd_rdata[2];
 assign rd_s[3].rdata=rd_rdata[3];
 logic [3:0] rd_rlast;
 assign rd_s[0].rlast=rd_rlast[0];
 assign rd_s[1].rlast=rd_rlast[1];
 assign rd_s[2].rlast=rd_rlast[2];
 assign rd_s[3].rlast=rd_rlast[3];
 logic [3:0] rd_rid;
 assign rd_s[0].rid=rd_rid[0];
 assign rd_s[1].rid=rd_rid[1];
 assign rd_s[2].rid=rd_rid[2];
 assign rd_s[3].rid=rd_rid[3];
 logic [3:0] [1:0] rd_rresp;
 assign rd_s[0].rresp=rd_rresp[0];
 assign rd_s[1].rresp=rd_rresp[1];
 assign rd_s[2].rresp=rd_rresp[2];
 assign rd_s[3].rresp=rd_rresp[3];
 logic [1:0] wr_awvalid;
 assign wr_awvalid[0]=wr_m[0].awvalid;
 assign wr_awvalid[1]=wr_m[1].awvalid;
 logic [1:0] wr_awready;
 assign wr_s[0].awready=wr_awready[0];
 assign wr_s[1].awready=wr_awready[1];
 logic [1:0] [63:0] wr_awaddr;
 assign wr_awaddr[0]=wr_m[0].awaddr;
 assign wr_awaddr[1]=wr_m[1].awaddr;
 logic [1:0] wr_awid;
 assign wr_awid[0]=wr_m[0].awid;
 assign wr_awid[1]=wr_m[1].awid;
 logic [1:0] [7:0] wr_awlen;
 assign wr_awlen[0]=wr_m[0].awlen;
 assign wr_awlen[1]=wr_m[1].awlen;
 logic [1:0] [2:0] wr_awsize;
 assign wr_awsize[0]=wr_m[0].awsize;
 assign wr_awsize[1]=wr_m[1].awsize;
 logic [1:0] [1:0] wr_awburst;
 assign wr_awburst[0]=wr_m[0].awburst;
 assign wr_awburst[1]=wr_m[1].awburst;
 logic [1:0] wr_wvalid;
 assign wr_wvalid[0]=wr_m[0].wvalid;
 assign wr_wvalid[1]=wr_m[1].wvalid;
 logic [1:0] wr_wready;
 assign wr_s[0].wready=wr_wready[0];
 assign wr_s[1].wready=wr_wready[1];
 logic [1:0] [127:0] wr_wdata;
 assign wr_wdata[0]=wr_m[0].wdata;
 assign wr_wdata[1]=wr_m[1].wdata;
 logic [1:0] [15:0] wr_wstrb;
 assign wr_wstrb[0]=wr_m[0].wstrb;
 assign wr_wstrb[1]=wr_m[1].wstrb;
 logic [1:0] wr_wlast;
 assign wr_wlast[0]=wr_m[0].wlast;
 assign wr_wlast[1]=wr_m[1].wlast;
 logic [1:0] wr_bvalid;
 assign wr_s[0].bvalid=wr_bvalid[0];
 assign wr_s[1].bvalid=wr_bvalid[1];
 logic [1:0] wr_bready;
 assign wr_bready[0]=wr_m[0].bready;
 assign wr_bready[1]=wr_m[1].bready;
 logic [1:0] wr_bid;
 assign wr_s[0].bid=wr_bid[0];
 assign wr_s[1].bid=wr_bid[1];
 logic [1:0] [1:0] wr_bresp;
 assign wr_s[0].bresp=wr_bresp[0];
 assign wr_s[1].bresp=wr_bresp[1];
 cnn_rtl_top dut(.ap_clk,.ap_rst_n,.pw_fast_clk,.pw_fast_rst,.ap_start,.ap_done,.ap_idle,.ap_ready,.protocol_error,.protocol_error_ap_vld,.rd_m,.rd_s,.wr_m,.wr_s,
 .trace_a_feed,.trace_a_dw3,.trace_a_dw7,.trace_a_pw1,.trace_a_pw2,.trace_a_write,
 .trace_b_feed,.trace_b_dw3,.trace_b_dw7,.trace_b_pw1,.trace_b_pw2,.trace_b_write,
 .s_axi_control_AWADDR(awaddr),
 .s_axi_control_AWVALID(awvalid),
 .s_axi_control_AWREADY(awready),
 .s_axi_control_WDATA(wdata),
 .s_axi_control_WSTRB(wstrb),
 .s_axi_control_WVALID(wvalid),
 .s_axi_control_WREADY(wready),
 .s_axi_control_BRESP(bresp),
 .s_axi_control_BVALID(bvalid),
 .s_axi_control_BREADY(bready),
 .s_axi_control_ARADDR(araddr),
 .s_axi_control_ARVALID(arvalid),
 .s_axi_control_ARREADY(arready),
 .s_axi_control_RDATA(rdata),
 .s_axi_control_RRESP(rresp),
 .s_axi_control_RVALID(rvalid),
 .s_axi_control_RREADY(rready));
 tb_cnn_v10_shared_ddr #(.MAX_PARAMS_WORDS(1200000),.MAX_ACT_WORDS(70000)) mem(.clk(ap_clk),.rst_n(ap_rst_n),.scoreboard_new_launch(new_launch),
.rd_arvalid(rd_arvalid),.rd_arready(rd_arready),.rd_araddr(rd_araddr),.rd_arid(rd_arid),.rd_arlen(rd_arlen),.rd_arsize(rd_arsize),.rd_arburst(rd_arburst),.rd_rvalid(rd_rvalid),.rd_rready(rd_rready),.rd_rdata(rd_rdata),.rd_rlast(rd_rlast),.rd_rid(rd_rid),.rd_rresp(rd_rresp),
.wr_awvalid(wr_awvalid),.wr_awready(wr_awready),.wr_awaddr(wr_awaddr),.wr_awid(wr_awid),.wr_awlen(wr_awlen),.wr_awsize(wr_awsize),.wr_awburst(wr_awburst),.wr_wvalid(wr_wvalid),.wr_wready(wr_wready),.wr_wdata(wr_wdata),.wr_wstrb(wr_wstrb),.wr_wlast(wr_wlast),.wr_bvalid(wr_bvalid),.wr_bready(wr_bready),.wr_bid(wr_bid),.wr_bresp(wr_bresp),
 .params1_base(P1),.params2_base(P2),.act_a_base(A),.act_b_base(B),.params_words(params_words),.act_words(arena_words),.scratch_word_base(2*slot_words),.scratch_words(4096),.token_numer(token_numer),.token_denom(token_denom),.token_burst(token_burst),.write_response_delay(bdelay),.force_pause(1'b0),.read_client_pause(4'b0),.write_client_pause(2'b0));
 task automatic write32(input logic[11:0] addr,input logic[31:0] value);
  @(negedge ap_clk);awaddr=addr;wdata=value;awvalid=1;wvalid=1;
  fork
   begin do @(posedge ap_clk);while(!awready);@(negedge ap_clk);awvalid=0;end
   begin do @(posedge ap_clk);while(!wready);@(negedge ap_clk);wvalid=0;end
  join
  repeat(3) @(negedge ap_clk);bready=1;
  do @(posedge ap_clk);while(!bvalid);
  if(bresp!=0)$fatal(1,"AXIL BRESP");@(negedge ap_clk);bready=0;
 endtask
 task automatic config_job(input int flags);
  write32('h10,P1);write32('h14,0);write32('h1c,P2);write32('h20,0);
  write32('h28,A);write32('h2c,0);write32('h34,A);write32('h38,0);
  write32('h40,B);write32('h44,0);write32('h4c,B);write32('h50,0);
  write32('h58,profile);write32('h60,blocks);write32('h68,params_words);
  write32('h70,slot_words);write32('h78,arena_words);write32('h80,flags);
 endtask
 task automatic launch;
  @(negedge ap_clk);new_launch=1;@(negedge ap_clk);new_launch=0;ap_start=1;cycles=0;monitor_cycle=0;measure_active=1;
  do begin @(posedge ap_clk);cycles++;if(cycles%100000==0)$display("PROGRESS P%0d cycle%0d traceA=%0d/%0d/%0d/%0d/%0d/%0d traceB=%0d/%0d/%0d/%0d/%0d/%0d",profile,cycles,trace_a_feed,trace_a_dw3,trace_a_dw7,trace_a_pw1,trace_a_pw2,trace_a_write,trace_b_feed,trace_b_dw3,trace_b_dw7,trace_b_pw1,trace_b_pw2,trace_b_write);if(cycles>maxcycles)$fatal(1,"TIMEOUT P%0d",profile);end while(!ap_ready);
  @(negedge ap_clk);ap_start=0;
  if(!ap_done)begin
   do begin @(posedge ap_clk);cycles++;if(cycles%100000==0)$display("PROGRESS P%0d cycle%0d traceA=%0d/%0d/%0d/%0d/%0d/%0d traceB=%0d/%0d/%0d/%0d/%0d/%0d",profile,cycles,trace_a_feed,trace_a_dw3,trace_a_dw7,trace_a_pw1,trace_a_pw2,trace_a_write,trace_b_feed,trace_b_dw3,trace_b_dw7,trace_b_pw1,trace_b_pw2,trace_b_write);if(cycles>maxcycles)$fatal(1,"TIMEOUT P%0d",profile);end while(!ap_done);
  end
  @(negedge ap_clk);measure_active=0;
 endtask
 task automatic run_profile(input int p);
  string dir; int output_words,offset; longint before_reads,before_writes;
  longint rd_before[2],wr_before[2],expected_read,expected_write;
  profile=p;
  case(p)
   0:begin blocks=12;slot_words=16384;params_words=252972;end
   1:begin blocks=20;slot_words=8192;params_words=1194100;end
   2:begin blocks=4;slot_words=32768;params_words=43940;end
   3:begin blocks=1;slot_words=32768;params_words=11280;end
  endcase
  arena_words=2*slot_words+4096;output_words=p==3?16384:slot_words;
  dir=$sformatf("%s/profile%0d/",fixture_root,p);
  for(int i=0;i<70000;i++)begin mem.activation_a[i]=CANARY;mem.activation_b[i]=CANARY;end
  $readmemh({dir,"params.mem"},mem.params_pw1,0,params_words-1);
  $readmemh({dir,"params.mem"},mem.params_pw2,0,params_words-1);
  $readmemh({dir,"input_a.mem"},mem.activation_a,0,slot_words-1);
  $readmemh({dir,"input_b.mem"},mem.activation_b,0,slot_words-1);
  $readmemh({dir,"expected_a.mem"},gold_a,0,output_words-1);
  $readmemh({dir,"expected_b.mem"},gold_b,0,output_words-1);
  if(diag_blocks>0)begin
   if(p==3 || diag_blocks>blocks)$fatal(1,"diagnostic block override must select normal profile and legal block count");
   blocks=diag_blocks;params_words=blocks*cnn_profile_pkg::stride(p);
  end
  for(int l=0;l<2;l++)begin rd_before[l]=mem.read_beats[l+2];wr_before[l]=mem.write_beats[l];end
  config_job(0);launch();
  if(protocol_error!==0)$fatal(1,"P%0d error %h",p,protocol_error);
  expected_read=p==3?49152:2*blocks*slot_words;
  expected_write=p==3?32768:2*blocks*slot_words;
  for(int l=0;l<2;l++)begin
   if(mem.read_beats[l+2]-rd_before[l]!=expected_read || mem.write_beats[l]-wr_before[l]!=expected_write)$fatal(1,"P%0d lane%0d activation traffic read%0d/%0d write%0d/%0d",p,l,mem.read_beats[l+2]-rd_before[l],expected_read,mem.write_beats[l]-wr_before[l],expected_write);
  end
  offset=p==3?0:(blocks&1)*slot_words;
  if(diag_blocks==0)for(int i=0;i<output_words;i++)begin
   if(mem.activation_a[offset+i]!==gold_a[i])$fatal(1,"P%0d A word%0d got%h expected%h",p,i,mem.activation_a[offset+i],gold_a[i]);
   if(mem.activation_b[offset+i]!==gold_b[i])$fatal(1,"P%0d B word%0d got%h expected%h",p,i,mem.activation_b[offset+i],gold_b[i]);
  end
  for(int i=arena_words;i<70000;i++)if(mem.activation_a[i]!==CANARY||mem.activation_b[i]!==CANARY)$fatal(1,"canary %0d",i);
  if(diag_blocks>0)begin
   $display("DIAGNOSTIC_PROFILE_DONE profile=%0d blocks=%0d cycles=%0d NO_NUMERICAL_QUALIFICATION",p,blocks,cycles);
   return;
  end
  $display("FULL_PASS profile=%0d blocks=%0d cycles=%0d",p,blocks,cycles);
  case(p)
   0:$display("CYCLE_GATE profile=0 target=18820869 pass=%0d",cycles<=18820869);
   1:$display("CYCLE_GATE profile=1 target=29923059 pass=%0d",cycles<=29923059);
   2:$display("CYCLE_GATE profile=2 target=7984637 pass=%0d",cycles<=7984637);
   3:$display("CYCLE_GATE profile=3 target=1539314 pass=%0d",cycles<=1539314);
  endcase
  if(token_denom!=2 || cycles>(p==0?18820869:p==1?29923059:p==2?7984637:1539314))performance_pass=0;
  before_reads=mem.read_beats[2]+mem.read_beats[3];before_writes=mem.aggregate_write_beats;
  config_job(1);launch();
  if(protocol_error!==1)$fatal(1,"bad flags expected error1 got%h",protocol_error);
  if(before_reads!=mem.read_beats[2]+mem.read_beats[3]||before_writes!=mem.aggregate_write_beats)$fatal(1,"rejected config activation traffic");
   config_job(0);
  begin
   int idx;logic [127:0] original;
   idx=p==3?784:cnn_profile_pkg::bias_offset(p);
   original=mem.params_pw1[idx];mem.params_pw1[idx][63:48]=~{16{original[47]}};
   launch();
   if(protocol_error!==2)$fatal(1,"bad metadata expected error2 got%h",protocol_error);
   if(before_reads!=mem.read_beats[2]+mem.read_beats[3]||before_writes!=mem.aggregate_write_beats)$fatal(1,"rejected metadata activation traffic");
   mem.params_pw1[idx]=original;
  end
 endtask
 read_m2s_t rd_prev[4];write_m2s_t wr_prev[2];logic [3:0] ar_stall=0;logic [1:0] aw_stall=0,w_stall=0;
 int committed_epoch[2][2][64];int launches[10];
 longint stage_begin[10][3][32];longint pw1_hist[32],pw2_hist[32];
 string pw1_names[32],pw2_names[32];
 longint dw_hist[2][2][16],dw_count[2][2][6],dw_fifo_empty[2][2],dw_fifo_full[2][2];
 int dw_fifo_min[2][2],dw_fifo_max[2][2];string dw_names[2][2][16];
 longint res_hist[2][8],res_unallocated[2],res_full[2],res_credit4[2];int res_credit_max[2],res_published_max[2];string res_names[2][8];
 task automatic sample_res(input int l,s,input string name,input bit active,allocated,full,input int credits,published);
  if(active)begin
   res_hist[l][s]++;res_names[l][s]=name;
   if(!allocated)res_unallocated[l]++;else if(full)res_full[l]++;
   if(credits==4)res_credit4[l]++;if(credits>res_credit_max[l])res_credit_max[l]=credits;if(published>res_published_max[l])res_published_max[l]=published;
  end
 endtask
 task automatic reset_dw_diagnostic;
  for(int l=0;l<2;l++)begin
   for(int n=0;n<8;n++)res_hist[l][n]=0;
   res_unallocated[l]=0;res_full[l]=0;res_credit4[l]=0;res_credit_max[l]=0;res_published_max[l]=0;
  end
  for(int k=0;k<2;k++)for(int l=0;l<2;l++)begin
   for(int n=0;n<16;n++)dw_hist[k][l][n]=0;
   for(int n=0;n<6;n++)dw_count[k][l][n]=0;
   dw_fifo_empty[k][l]=0;dw_fifo_full[k][l]=0;dw_fifo_min[k][l]=1000000;dw_fifo_max[k][l]=0;
  end
 endtask
 task automatic sample_dw(input int k,l,s,input string name,input bit active,iv,ir,reqv,reqr,oh,orr,kh,kr,input int credit,level,depth);
  if(active)begin
   dw_hist[k][l][s]++;dw_names[k][l][s]=name;
   if(name=="LOAD")begin if(iv&&ir)dw_count[k][l][0]++;if(!iv)dw_count[k][l][1]++;end
   if(name=="EMIT")begin if(credit==16)dw_count[k][l][2]++;if(reqv&&!reqr)dw_count[k][l][3]++;end
   if(oh&&!orr)dw_count[k][l][4]++;if(kh&&!kr)dw_count[k][l][5]++;
   if(level<dw_fifo_min[k][l])dw_fifo_min[k][l]=level;if(level>dw_fifo_max[k][l])dw_fifo_max[k][l]=level;
   if(level==0)dw_fifo_empty[k][l]++;if(level==depth)dw_fifo_full[k][l]++;
  end
 endtask
 longint emit_cycles,pw1_out_stall[2],pw1_scale_stall[2],q7_empty_input[2],expanded_full[2],pw2_input_handshakes[2],pw2_in_blocked[2],pw2_in_idle[2];
 longint hist_window_start,mac_accept[2],mac_result_accept[2],mac_source_stall[2],mac_ready_idle[2];int reported_pair=0,released_pairs=0;logic[1:0] release_mask=0;
`ifdef CNN_TB_QCACHE
 longint post_hist[8],q_req_count[2],q_rsp_count[2],q_read_count[2],q_water_wait[2],post_out_count[2];string post_names[8];
`endif
 task automatic dump_partial_diagnostic;
  $display("DIAGNOSTIC_PAIR_SNAPSHOT profile=%0d released_pairs=%0d cycle=%0d window_cycles=%0d",profile,released_pairs,monitor_cycle,monitor_cycle-hist_window_start);
  for(int l=0;l<2;l++)begin
   for(int n=0;n<8;n++)if(res_hist[l][n]!=0)$display("RES_HIST lane=%0d state=%s cycles=%0d",l,res_names[l][n],res_hist[l][n]);
   $display("RES_STATS lane=%0d unallocated=%0d buffer_full=%0d credit4=%0d credit_max=%0d published_max=%0d",l,res_unallocated[l],res_full[l],res_credit4[l],res_credit_max[l],res_published_max[l]);
  end
  $display("RES_PROGRESS lane=0 fill_pair=%0d send_pair=%0d fill_burst=%0d send_burst=%0d",dut.residual0.fill_pair,dut.residual0.send_pair,dut.residual0.fill_burst,dut.residual0.send_burst);
  $display("RES_PROGRESS lane=1 fill_pair=%0d send_pair=%0d fill_burst=%0d send_burst=%0d",dut.residual1.fill_pair,dut.residual1.send_pair,dut.residual1.fill_burst,dut.residual1.send_burst);
  for(int k=0;k<2;k++)for(int l=0;l<2;l++)begin
   for(int n=0;n<16;n++)if(dw_hist[k][l][n]!=0)$display("DW_HIST K=%0d lane=%0d state=%s cycles=%0d",k==0?3:7,l,dw_names[k][l][n],dw_hist[k][l][n]);
   $display("DW_STATS K=%0d lane=%0d load_accept=%0d load_empty=%0d emit_credit16=%0d emit_req_stall=%0d oh_stall=%0d kh_stall=%0d fifo_min=%0d fifo_max=%0d fifo_empty=%0d fifo_full=%0d",k==0?3:7,l,dw_count[k][l][0],dw_count[k][l][1],dw_count[k][l][2],dw_count[k][l][3],dw_count[k][l][4],dw_count[k][l][5],dw_fifo_min[k][l],dw_fifo_max[k][l],dw_fifo_empty[k][l],dw_fifo_full[k][l]);
  end
  for(int n=0;n<32;n++)begin
   if(pw1_hist[n]!=0)$display("STATE_HIST profile=%0d stage=4 block=0 state=%s id=%0d cycles=%0d",profile,pw1_names[n],n,pw1_hist[n]);
   if(pw2_hist[n]!=0)$display("STATE_HIST profile=%0d stage=5 block=0 state=%s id=%0d cycles=%0d",profile,pw2_names[n],n,pw2_hist[n]);
  end
  for(int l=0;l<2;l++)begin
   $display("PW1_STALL block=0 lane=%0d emit=%0d out_stall=%0d scale_stall=%0d q7_empty_input=%0d expanded_full=%0d",l,emit_cycles,pw1_out_stall[l],pw1_scale_stall[l],q7_empty_input[l],expanded_full[l]);
   $display("PW2_INPUT block=0 lane=%0d handshakes=%0d blocked=%0d ready_idle=%0d",l,pw2_input_handshakes[l],pw2_in_blocked[l],pw2_in_idle[l]);
   $display("PW2_MAC lane=%0d input_accept=%0d result_accept=%0d source_stall=%0d ready_idle=%0d",l,mac_accept[l],mac_result_accept[l],mac_source_stall[l],mac_ready_idle[l]);
  end
`ifdef CNN_TB_QCACHE
  for(int n=0;n<8;n++)if(post_hist[n]!=0)$display("POST_HIST state=%s id=%0d cycles=%0d",post_names[n],n,post_hist[n]);
  for(int l=0;l<2;l++)$display("Q_STATS lane=%0d req=%0d rsp=%0d reads=%0d water_wait=%0d outputs=%0d compute_pair=%0d post_pair=%0d q_tag=%0d",l,q_req_count[l],q_rsp_count[l],q_read_count[l],q_water_wait[l],post_out_count[l],dut.pw2.row_pair,dut.pw2.post_pair,dut.pw2.q_pair_tag);
`endif
 endtask
 always @(posedge ap_clk)if(measure_active)begin
  monitor_cycle++;
  if(dut.pw2.busy)begin
   release_mask=release_mask|(dut.res_release_v&dut.res_release_r);
   if(&release_mask)begin release_mask=0;released_pairs++;end
  end
  if(diag_first_pair!=0 && dut.pw2.busy && released_pairs>reported_pair)begin
   dump_partial_diagnostic();
   if(released_pairs>=diag_first_pair)begin $display("DIAGNOSTIC_SUITE_DONE NO_NUMERICAL_QUALIFICATION");$finish;end
   reported_pair=released_pairs;hist_window_start=monitor_cycle;
   reset_dw_diagnostic();
   for(int n=0;n<32;n++)begin pw1_hist[n]=0;pw2_hist[n]=0;end
   emit_cycles=0;
   for(int l=0;l<2;l++)begin pw1_out_stall[l]=0;pw1_scale_stall[l]=0;q7_empty_input[l]=0;expanded_full[l]=0;pw2_input_handshakes[l]=0;pw2_in_blocked[l]=0;pw2_in_idle[l]=0;mac_accept[l]=0;mac_result_accept[l]=0;mac_source_stall[l]=0;mac_ready_idle[l]=0;end
`ifdef CNN_TB_QCACHE
   for(int n=0;n<8;n++)post_hist[n]=0;
   for(int l=0;l<2;l++)begin q_req_count[l]=0;q_rsp_count[l]=0;q_read_count[l]=0;q_water_wait[l]=0;post_out_count[l]=0;end
`endif
  end
  for(int i=0;i<10;i++)begin
   if(dut.stage_start[i])begin
    stage_begin[i][dut.transition_stage][dut.block_index[i]]=monitor_cycle;
    $display("STAGE_START profile=%0d stage=%0d transition=%0d block=%0d cycle=%0d",profile,i,dut.transition_stage,dut.block_index[i],monitor_cycle);
   end
   if(dut.stage_done[i])begin
    $display("STAGE_DONE profile=%0d stage=%0d transition=%0d block=%0d cycle=%0d duration=%0d",profile,i,dut.transition_stage,dut.block_index[i],monitor_cycle,monitor_cycle-stage_begin[i][dut.transition_stage][dut.block_index[i]]);
   end
  end
  if(dut.stage_start[4])begin
   for(int n=0;n<32;n++)pw1_hist[n]=0;
   emit_cycles=0;for(int l=0;l<2;l++)begin pw1_out_stall[l]=0;pw1_scale_stall[l]=0;q7_empty_input[l]=0;expanded_full[l]=0;end
  end
  if(dut.stage_start[5])begin hist_window_start=monitor_cycle;reported_pair=0;released_pairs=0;release_mask=0;for(int n=0;n<32;n++)pw2_hist[n]=0;for(int l=0;l<2;l++)begin pw2_input_handshakes[l]=0;pw2_in_blocked[l]=0;pw2_in_idle[l]=0;mac_accept[l]=0;mac_result_accept[l]=0;mac_source_stall[l]=0;mac_ready_idle[l]=0;end
   reset_dw_diagnostic();
`ifdef CNN_TB_QCACHE
   for(int n=0;n<8;n++)post_hist[n]=0;
   for(int l=0;l<2;l++)begin q_req_count[l]=0;q_rsp_count[l]=0;q_read_count[l]=0;q_water_wait[l]=0;post_out_count[l]=0;end
`endif
  end
`define TB_SAMPLE_DW(K,L,H,Q,D) sample_dw(K,L,int'(H.state),H.state.name(),H.busy,H.in_valid,H.in_ready,H.scale_req_valid,H.scale_req_ready,H.oh,H.out_ready,H.kh,H.skip_ready,int'(H.credit),int'(Q.level),D);
  `TB_SAMPLE_DW(0,0,dut.dw3.g_core[0].core,dut.q30,4096)
  `TB_SAMPLE_DW(0,1,dut.dw3.g_core[1].core,dut.q31,4096)
  `TB_SAMPLE_DW(1,0,dut.dw7.g_core[0].core,dut.q70,8192)
  `TB_SAMPLE_DW(1,1,dut.dw7.g_core[1].core,dut.q71,8192)
`undef TB_SAMPLE_DW
  sample_res(0,int'(dut.residual0.state),dut.residual0.state.name(),dut.residual0.busy,dut.residual0.allocated,dut.residual0.full[dut.residual0.fb],int'(dut.residual0.credits),int'(dut.residual0.published));
  sample_res(1,int'(dut.residual1.state),dut.residual1.state.name(),dut.residual1.busy,dut.residual1.allocated,dut.residual1.full[dut.residual1.fb],int'(dut.residual1.credits),int'(dut.residual1.published));
  if(dut.pw1.busy)begin
   pw1_hist[int'(dut.pw1.state)]++;pw1_names[int'(dut.pw1.state)]=dut.pw1.state.name();
   if(dut.pw1.emit_active)emit_cycles++;
   for(int l=0;l<2;l++)begin
    if(dut.pw1_v[l]&&!dut.pw1_r[l])pw1_out_stall[l]++;
    if(dut.pw1.scale_svalid[l]&&!dut.pw1.scale_sready[l])pw1_scale_stall[l]++;
    if(dut.pw1.state.name()=="INPUT_PAIR"&&!dut.q7_v[l])q7_empty_input[l]++;
    if(l==0?dut.expanded0.level==2048:dut.expanded1.level==2048)expanded_full[l]++;
   end
  end
  if(dut.pw2.busy)begin
   pw2_hist[int'(dut.pw2.state)]++;pw2_names[int'(dut.pw2.state)]=dut.pw2.state.name();
   for(int l=0;l<2;l++)begin
    if(dut.ex_v[l]&&dut.ex_r[l])pw2_input_handshakes[l]++;
    if(dut.ex_v[l]&&!dut.ex_r[l])pw2_in_blocked[l]++;
    if(!dut.ex_v[l]&&dut.ex_r[l])pw2_in_idle[l]++;
    if(dut.pw2.state.name()=="MAC_SEND")begin
     if(dut.pw2.mac_sv[l]&&dut.pw2.mac_sr[l])mac_accept[l]++;
     if(dut.pw2.mac_mv[l]&&dut.pw2.mac_mr[l])mac_result_accept[l]++;
     if(dut.pw2.mac_sv[l]&&!dut.pw2.mac_sr[l])mac_source_stall[l]++;
     if(!dut.pw2.mac_sv[l]&&dut.pw2.mac_sr[l])mac_ready_idle[l]++;
    end
   end
`ifdef CNN_TB_QCACHE
   post_hist[int'(dut.pw2.post_state)]++;post_names[int'(dut.pw2.post_state)]=dut.pw2.post_state.name();
   for(int l=0;l<2;l++)begin
    if(dut.pw2.scale_req_valid[l]&&dut.pw2.scale_req_ready[l])q_req_count[l]++;
    if(dut.pw2.scale_rsp_valid[l]&&dut.pw2.scale_rsp_ready[l])q_rsp_count[l]++;
    if(dut.pw2.q_read_en[l])q_read_count[l]++;
    if(dut.pw2.post_state.name()=="P_RUN" && dut.pw2.post_read_sent[l]<64 && dut.pw2.q_read_cursor[l]>=dut.pw2.q_received[l])q_water_wait[l]++;
    if(dut.pw2.out_valid[l]&&dut.pw2.out_ready[l])post_out_count[l]++;
   end
`endif
  end
  if(dut.stage_done[4])begin
   for(int n=0;n<32;n++)if(pw1_hist[n]!=0)$display("STATE_HIST profile=%0d stage=4 block=%0d state=%s id=%0d cycles=%0d",profile,dut.block_index[4],pw1_names[n],n,pw1_hist[n]);
   for(int l=0;l<2;l++)$display("PW1_STALL block=%0d lane=%0d emit=%0d out_stall=%0d scale_stall=%0d q7_empty_input=%0d expanded_full=%0d",dut.block_index[4],l,emit_cycles,pw1_out_stall[l],pw1_scale_stall[l],q7_empty_input[l],expanded_full[l]);
  end
  if(dut.stage_done[5])begin
   for(int n=0;n<32;n++)if(pw2_hist[n]!=0)$display("STATE_HIST profile=%0d stage=5 block=%0d state=%s id=%0d cycles=%0d",profile,dut.block_index[5],pw2_names[n],n,pw2_hist[n]);
   for(int l=0;l<2;l++)$display("PW2_INPUT block=%0d lane=%0d handshakes=%0d",dut.block_index[5],l,pw2_input_handshakes[l]);
  end
 end
 always @(posedge ap_clk)begin
  if(!ap_rst_n || dut.capture_config)begin
   for(int l=0;l<2;l++)for(int s=0;s<2;s++)for(int r=0;r<64;r++)committed_epoch[l][s][r]=-1;
   for(int i=0;i<10;i++)launches[i]=0;
  end else begin
   for(int i=0;i<10;i++)if(dut.stage_start[i])begin
    if(dut.profile!=3 && dut.block_index[i]!=launches[i])$fatal(1,"stage%0d wrong block epoch got%0d expected%0d",i,dut.block_index[i],launches[i]);
    launches[i]++;
   end
   if(dut.profile!=3)for(int l=0;l<2;l++)begin
    if(dut.feed_cv[l] && dut.feed_cr[l] && dut.block_index[l]!=0)begin
     int row,slot;
     slot=dut.block_index[l]&1;row=(dut.feed_ca[l]-slot*slot_words)/512;
     if(row<0 || row>=64 || committed_epoch[l][slot][row]!=int'(dut.block_index[l])-1)$fatal(1,"feedback before exact committed row lane%0d block%0d row%0d epoch%0d",l,dut.block_index[l],row,committed_epoch[l][slot][row]);
    end
    if(dut.row_commit_valid[l])begin
     int slot;slot=(dut.row_commit_block[l]+1)&1;
     committed_epoch[l][slot][dut.row_commit_index[l]]=dut.row_commit_block[l];
    end
   end
   if(ap_done && protocol_error==0)begin
    if(dut.job.completed!==10'b1111111111)$fatal(1,"job done before final stage mask");
    for(int i=0;i<10;i++)begin
     if(dut.profile!=3 && (launches[i]!=blocks || dut.block_index[i]!=blocks-1))$fatal(1,"job final epoch stage%0d launches%0d block%0d",i,launches[i],dut.block_index[i]);
    end
    if(dut.q30.level!=0||dut.q31.level!=0||dut.q70.level!=0||dut.q71.level!=0||dut.expanded0.level!=0||dut.expanded1.level!=0)$fatal(1,"job done with pixel FIFO nonempty");
    if((&dut.read_idle)!==1'b1 || (&dut.write_idle)!==1'b1)$fatal(1,"job done before DDR adapters drained");
   end
  end
 end
 always @(posedge ap_clk) if(ap_rst_n)begin
  for(int l=0;l<2;l++)if(dut.feed_v[l] && dut.feed_r[l] && $isunknown(dut.feed_d[l]))$fatal(1,"FIRST_X feed lane%0d profile%0d stage%0d",l,profile,dut.transition_stage);
  for(int l=0;l<2;l++)if(dut.dw3_v[l] && dut.dw3_r[l] && $isunknown(dut.dw3_d[l]))$fatal(1,"FIRST_X dw3 lane%0d profile%0d stage%0d",l,profile,dut.transition_stage);
  for(int l=0;l<2;l++)if(dut.dw7_v[l] && dut.dw7_r[l] && $isunknown(dut.dw7_d[l]))$fatal(1,"FIRST_X dw7 lane%0d profile%0d stage%0d",l,profile,dut.transition_stage);
  for(int l=0;l<2;l++)if(dut.pw1_v[l] && dut.pw1_r[l] && $isunknown(dut.pw1_d[l]))$fatal(1,"FIRST_X pw1 lane%0d profile%0d stage%0d",l,profile,dut.transition_stage);
  for(int l=0;l<2;l++)if(dut.pw2_v[l] && dut.pw2_r[l] && $isunknown(dut.pw2_d[l]))$fatal(1,"FIRST_X pw2 lane%0d profile%0d stage%0d",l,profile,dut.transition_stage);
  for(int i=0;i<4;i++)begin
   if(ar_stall[i] && (!rd_m[i].arvalid || {rd_m[i].araddr,rd_m[i].arlen,rd_m[i].arsize,rd_m[i].arburst,rd_m[i].arid}!={rd_prev[i].araddr,rd_prev[i].arlen,rd_prev[i].arsize,rd_prev[i].arburst,rd_prev[i].arid}))$fatal(1,"AR unstable master%0d",i);
   ar_stall[i]<=rd_m[i].arvalid&&!rd_s[i].arready;rd_prev[i]<=rd_m[i];
  end
  for(int i=0;i<2;i++)begin
   if(aw_stall[i] && (!wr_m[i].awvalid || {wr_m[i].awaddr,wr_m[i].awlen,wr_m[i].awsize,wr_m[i].awburst,wr_m[i].awid}!={wr_prev[i].awaddr,wr_prev[i].awlen,wr_prev[i].awsize,wr_prev[i].awburst,wr_prev[i].awid}))$fatal(1,"AW unstable master%0d",i);
   if(w_stall[i] && (!wr_m[i].wvalid || {wr_m[i].wdata,wr_m[i].wstrb,wr_m[i].wlast}!={wr_prev[i].wdata,wr_prev[i].wstrb,wr_prev[i].wlast}))$fatal(1,"W unstable master%0d",i);
   aw_stall[i]<=wr_m[i].awvalid&&!wr_s[i].awready;w_stall[i]<=wr_m[i].wvalid&&!wr_s[i].wready;wr_prev[i]<=wr_m[i];
  end
 end
 initial begin
  if($value$plusargs("FIXTURE_ROOT=%s",fixture_root))begin end
  if($value$plusargs("PROFILE=%d",selected))begin end
  if($value$plusargs("REPEAT=%d",repeat_count))begin end
  if($value$plusargs("MAX_CYCLES=%d",maxcycles))begin end
  if($value$plusargs("TOKEN_DENOM=%d",token_denom))begin end
  if($value$plusargs("DIAG_BLOCKS=%d",diag_blocks))begin end
  if($value$plusargs("DIAG_FIRST_PAIR=%d",diag_first_pair))begin end
  if($value$plusargs("MIXED=%d",mixed))begin end
  if(mixed!=0 && diag_blocks>0)$fatal(1,"mixed qualification cannot use diagnostic block override");
  if(diag_blocks>0 && selected<0)$fatal(1,"diagnostic override requires selected profile");
  repeat(16)@(negedge ap_clk);ap_rst_n=1;pw_fast_rst=0;
  if(mixed!=0)begin
   run_profile(3);run_profile(2);run_profile(3);
   $display("MIXED_SEQUENCE_VERIFIED actual_sequence=3,2,3");
  end else for(int r=0;r<repeat_count;r++)for(int p=0;p<4;p++)if(selected<0||p==selected)run_profile(p);
  if(diag_blocks>0)$display("DIAGNOSTIC_SUITE_DONE NO_NUMERICAL_QUALIFICATION");
  else begin
   $display("FULL_FUNCTIONAL_SUITE_PASS");
   if(performance_pass)$display("FULL_SUITE_PASS");else $display("FULL_PERFORMANCE_FAIL");
  end
  $finish;
 end
endmodule

