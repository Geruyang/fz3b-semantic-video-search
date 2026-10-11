// Generated connections from scripts/generate_top.py; no HLS logic.
module cnn_rtl_top(
 input logic ap_clk,ap_rst_n,pw_fast_clk,pw_fast_rst,ap_start,
 output logic ap_done,ap_idle,ap_ready,
 output logic [31:0] protocol_error,output logic protocol_error_ap_vld,
 output logic [31:0] trace_a_feed,
 output logic [31:0] trace_a_dw3,
 output logic [31:0] trace_a_dw7,
 output logic [31:0] trace_a_pw1,
 output logic [31:0] trace_a_pw2,
 output logic [31:0] trace_a_write,
 output logic [31:0] trace_b_feed,
 output logic [31:0] trace_b_dw3,
 output logic [31:0] trace_b_dw7,
 output logic [31:0] trace_b_pw1,
 output logic [31:0] trace_b_pw2,
 output logic [31:0] trace_b_write,
 input logic [11:0] s_axi_control_AWADDR,
 input logic s_axi_control_AWVALID,output logic s_axi_control_AWREADY,
 input logic [31:0] s_axi_control_WDATA,input logic [3:0] s_axi_control_WSTRB,
 input logic s_axi_control_WVALID,output logic s_axi_control_WREADY,
 output logic [1:0] s_axi_control_BRESP,output logic s_axi_control_BVALID,input logic s_axi_control_BREADY,
 input logic [11:0] s_axi_control_ARADDR,input logic s_axi_control_ARVALID,output logic s_axi_control_ARREADY,
 output logic [31:0] s_axi_control_RDATA,output logic [1:0] s_axi_control_RRESP,
 output logic s_axi_control_RVALID,input logic s_axi_control_RREADY,
 output cnn_axi_pkg::read_m2s_t rd_m[4],input cnn_axi_pkg::read_s2m_t rd_s[4],
 output cnn_axi_pkg::write_m2s_t wr_m[2],input cnn_axi_pkg::write_s2m_t wr_s[2]
);
 logic rst;
 assign rst=!ap_rst_n;
 logic capture_config,preflight_start,preflight_done,preflight_busy;
 logic [9:0] stage_start;
 logic [31:0] preflight_error,datapath_error;
 logic [1:0] profile,transition_stage;
 logic [4:0] block_index[10];
 logic [9:0] stage_done;
 logic [3:0] read_idle;logic [1:0] write_idle;
 logic [31:0] read_error[4],write_error[2],stage_error[4];
 logic [63:0] rd_base[4],wr_base[2];
 logic [63:0] cfg_params_pw1,job_params_pw1;
 logic [63:0] cfg_params_pw2,job_params_pw2;
 logic [63:0] cfg_activation_a_rd,job_activation_a_rd;
 logic [63:0] cfg_activation_a_wr,job_activation_a_wr;
 logic [63:0] cfg_activation_b_rd,job_activation_b_rd;
 logic [63:0] cfg_activation_b_wr,job_activation_b_wr;
 logic [31:0] cfg_profile,job_profile;
 logic [31:0] cfg_block_count,job_block_count;
 logic [31:0] cfg_params_words,job_params_words;
 logic [31:0] cfg_slot_words,job_slot_words;
 logic [31:0] cfg_arena_words,job_arena_words;
 logic [31:0] cfg_flags,job_flags;
 cnn_control control(.clk(ap_clk),.rst(rst),
 .s_axi_control_awaddr(s_axi_control_AWADDR),
 .s_axi_control_awvalid(s_axi_control_AWVALID),
 .s_axi_control_awready(s_axi_control_AWREADY),
 .s_axi_control_wdata(s_axi_control_WDATA),
 .s_axi_control_wstrb(s_axi_control_WSTRB),
 .s_axi_control_wvalid(s_axi_control_WVALID),
 .s_axi_control_wready(s_axi_control_WREADY),
 .s_axi_control_bresp(s_axi_control_BRESP),
 .s_axi_control_bvalid(s_axi_control_BVALID),
 .s_axi_control_bready(s_axi_control_BREADY),
 .s_axi_control_araddr(s_axi_control_ARADDR),
 .s_axi_control_arvalid(s_axi_control_ARVALID),
 .s_axi_control_arready(s_axi_control_ARREADY),
 .s_axi_control_rdata(s_axi_control_RDATA),
 .s_axi_control_rresp(s_axi_control_RRESP),
 .s_axi_control_rvalid(s_axi_control_RVALID),
 .s_axi_control_rready(s_axi_control_RREADY),
 .params_pw1(cfg_params_pw1),
 .params_pw2(cfg_params_pw2),
 .activation_a_rd(cfg_activation_a_rd),
 .activation_a_wr(cfg_activation_a_wr),
 .activation_b_rd(cfg_activation_b_rd),
 .activation_b_wr(cfg_activation_b_wr),
 .profile(cfg_profile),
 .block_count(cfg_block_count),
 .params_words(cfg_params_words),
 .slot_words(cfg_slot_words),
 .arena_words(cfg_arena_words),
 .flags(cfg_flags));
 always_ff @(posedge ap_clk)begin
 if(rst)begin
 job_params_pw1<=0;
 job_params_pw2<=0;
 job_activation_a_rd<=0;
 job_activation_a_wr<=0;
 job_activation_b_rd<=0;
 job_activation_b_wr<=0;
 job_profile<=0;
 job_block_count<=0;
 job_params_words<=0;
 job_slot_words<=0;
 job_arena_words<=0;
 job_flags<=0;
 end else if(capture_config)begin
 job_params_pw1<=cfg_params_pw1;
 job_params_pw2<=cfg_params_pw2;
 job_activation_a_rd<=cfg_activation_a_rd;
 job_activation_a_wr<=cfg_activation_a_wr;
 job_activation_b_rd<=cfg_activation_b_rd;
 job_activation_b_wr<=cfg_activation_b_wr;
 job_profile<=cfg_profile;
 job_block_count<=cfg_block_count;
 job_params_words<=cfg_params_words;
 job_slot_words<=cfg_slot_words;
 job_arena_words<=cfg_arena_words;
 job_flags<=cfg_flags;
 end end
 assign rd_base[0]=job_params_pw1;assign rd_base[1]=job_params_pw2;
 assign rd_base[2]=job_activation_a_rd;assign rd_base[3]=job_activation_b_rd;
 assign wr_base[0]=job_activation_a_wr;assign wr_base[1]=job_activation_b_wr;
 cnn_job job(.clk(ap_clk),.rst(rst),.ap_start,.ap_ready,.ap_done,.ap_idle,
 .cfg_profile,.cfg_block_count,.capture_config,.preflight_start,.stage_start,
 .preflight_done,.preflight_error,.stage_done,.fabric_idle((&read_idle)&&(&write_idle)),
 .datapath_error,.profile,.transition_stage,.block_index,.error(protocol_error),.error_valid(protocol_error_ap_vld));
 logic [1:0] pf_cv,pf_cr,pf_dv,pf_dr;
 logic [31:0] pf_ca[2];logic [5:0] pf_cw[2];logic [127:0] pf_data[2];
 cnn_preflight preflight(.clk(ap_clk),.rst,.start(preflight_start),.done(preflight_done),.busy(preflight_busy),
 .profile(job_profile),
 .block_count(job_block_count),
 .params_words(job_params_words),
 .slot_words(job_slot_words),
 .arena_words(job_arena_words),
 .flags(job_flags),
 .error(preflight_error),.cmd_valid(pf_cv),.cmd_ready(pf_cr),.cmd_addr(pf_ca),.cmd_words(pf_cw),.data_valid(pf_dv),.data_ready(pf_dr),.data(pf_data));
 logic [3:0] p1_cv,p1_cr,p1_dv,p1_dr;
 logic [31:0] p1_ca[4];logic [5:0] p1_cw[4];logic [127:0] p1_data[4];
 logic [1:0] p2_cv,p2_cr,p2_dv,p2_dr;
 logic [31:0] p2_ca[2];logic [5:0] p2_cw[2];logic [127:0] p2_data[2];
 logic [1:0] ar0_cv,ar0_cr,ar0_dv,ar0_dr;
 logic [31:0] ar0_ca[2];logic [5:0] ar0_cw[2];logic [127:0] ar0_data[2];
 logic [1:0] ar1_cv,ar1_cr,ar1_dv,ar1_dr;
 logic [31:0] ar1_ca[2];logic [5:0] ar1_cw[2];logic [127:0] ar1_data[2];
 logic [1:0] aw0_cv,aw0_cr,aw0_dv,aw0_dr;
 logic [31:0] aw0_ca[2];logic [5:0] aw0_cw[2];logic [127:0] aw0_data[2];
 logic [1:0] aw0_bv,aw0_br;
 logic [1:0] aw1_cv,aw1_cr,aw1_dv,aw1_dr;
 logic [31:0] aw1_ca[2];logic [5:0] aw1_cw[2];logic [127:0] aw1_data[2];
 logic [1:0] aw1_bv,aw1_br;
 logic [3:0] mc_v,mc_r,md_v,md_r;logic [31:0] mc_a[4];logic [5:0] mc_w[4];logic [127:0] md[4];
 logic [1:0] wc_v,wc_r,wd_v,wd_r,wb_v,wb_r;logic [31:0] wc_a[2];logic [5:0] wc_w[2];logic [127:0] wd[2];
 cnn_read_router #(.N(4)) router_p1(.clk(ap_clk),.rst,.cmd_valid(p1_cv),.cmd_ready(p1_cr),.cmd_addr(p1_ca),.cmd_words(p1_cw),
 .data_valid(p1_dv),.data_ready(p1_dr),.data(p1_data),.m_cmd_valid(mc_v[0]),.m_cmd_ready(mc_r[0]),.m_cmd_addr(mc_a[0]),.m_cmd_words(mc_w[0]),.m_data_valid(md_v[0]),.m_data_ready(md_r[0]),.m_data(md[0]));
 cnn_read_router #(.N(2)) router_p2(.clk(ap_clk),.rst,.cmd_valid(p2_cv),.cmd_ready(p2_cr),.cmd_addr(p2_ca),.cmd_words(p2_cw),
 .data_valid(p2_dv),.data_ready(p2_dr),.data(p2_data),.m_cmd_valid(mc_v[1]),.m_cmd_ready(mc_r[1]),.m_cmd_addr(mc_a[1]),.m_cmd_words(mc_w[1]),.m_data_valid(md_v[1]),.m_data_ready(md_r[1]),.m_data(md[1]));
 cnn_read_router #(.N(2)) router_ar0(.clk(ap_clk),.rst,.cmd_valid(ar0_cv),.cmd_ready(ar0_cr),.cmd_addr(ar0_ca),.cmd_words(ar0_cw),
 .data_valid(ar0_dv),.data_ready(ar0_dr),.data(ar0_data),.m_cmd_valid(mc_v[2]),.m_cmd_ready(mc_r[2]),.m_cmd_addr(mc_a[2]),.m_cmd_words(mc_w[2]),.m_data_valid(md_v[2]),.m_data_ready(md_r[2]),.m_data(md[2]));
 cnn_read_router #(.N(2)) router_ar1(.clk(ap_clk),.rst,.cmd_valid(ar1_cv),.cmd_ready(ar1_cr),.cmd_addr(ar1_ca),.cmd_words(ar1_cw),
 .data_valid(ar1_dv),.data_ready(ar1_dr),.data(ar1_data),.m_cmd_valid(mc_v[3]),.m_cmd_ready(mc_r[3]),.m_cmd_addr(mc_a[3]),.m_cmd_words(mc_w[3]),.m_data_valid(md_v[3]),.m_data_ready(md_r[3]),.m_data(md[3]));
 cnn_write_router #(.N(2)) router_aw0(.clk(ap_clk),.rst,.cmd_valid(aw0_cv),.cmd_ready(aw0_cr),.cmd_addr(aw0_ca),.cmd_words(aw0_cw),
 .data_valid(aw0_dv),.data_ready(aw0_dr),.data(aw0_data),.commit_valid(aw0_bv),.commit_ready(aw0_br),
 .m_cmd_valid(wc_v[0]),.m_cmd_ready(wc_r[0]),.m_cmd_addr(wc_a[0]),.m_cmd_words(wc_w[0]),.m_data_valid(wd_v[0]),.m_data_ready(wd_r[0]),.m_data(wd[0]),.m_commit_valid(wb_v[0]),.m_commit_ready(wb_r[0]));
 cnn_write_router #(.N(2)) router_aw1(.clk(ap_clk),.rst,.cmd_valid(aw1_cv),.cmd_ready(aw1_cr),.cmd_addr(aw1_ca),.cmd_words(aw1_cw),
 .data_valid(aw1_dv),.data_ready(aw1_dr),.data(aw1_data),.commit_valid(aw1_bv),.commit_ready(aw1_br),
 .m_cmd_valid(wc_v[1]),.m_cmd_ready(wc_r[1]),.m_cmd_addr(wc_a[1]),.m_cmd_words(wc_w[1]),.m_data_valid(wd_v[1]),.m_data_ready(wd_r[1]),.m_data(wd[1]),.m_commit_valid(wb_v[1]),.m_commit_ready(wb_r[1]));
 cnn_axi_read read0(.clk(ap_clk),.rst,.base_addr(rd_base[0]),.cmd_valid(mc_v[0]),.cmd_ready(mc_r[0]),.cmd_addr(mc_a[0]),.cmd_words(mc_w[0]),.data_valid(md_v[0]),.data_ready(md_r[0]),.data(md[0]),.error(read_error[0]),.idle(read_idle[0]),
 .m_axi_arid(rd_m[0].arid),
 .m_axi_araddr(rd_m[0].araddr),
 .m_axi_arlen(rd_m[0].arlen),
 .m_axi_arsize(rd_m[0].arsize),
 .m_axi_arburst(rd_m[0].arburst),
 .m_axi_arlock(rd_m[0].arlock),
 .m_axi_arcache(rd_m[0].arcache),
 .m_axi_arprot(rd_m[0].arprot),
 .m_axi_arqos(rd_m[0].arqos),
 .m_axi_arvalid(rd_m[0].arvalid),
 .m_axi_arready(rd_s[0].arready),
 .m_axi_rid(rd_s[0].rid),
 .m_axi_rdata(rd_s[0].rdata),
 .m_axi_rresp(rd_s[0].rresp),
 .m_axi_rlast(rd_s[0].rlast),
 .m_axi_rvalid(rd_s[0].rvalid),
 .m_axi_rready(rd_m[0].rready));
 cnn_axi_read read1(.clk(ap_clk),.rst,.base_addr(rd_base[1]),.cmd_valid(mc_v[1]),.cmd_ready(mc_r[1]),.cmd_addr(mc_a[1]),.cmd_words(mc_w[1]),.data_valid(md_v[1]),.data_ready(md_r[1]),.data(md[1]),.error(read_error[1]),.idle(read_idle[1]),
 .m_axi_arid(rd_m[1].arid),
 .m_axi_araddr(rd_m[1].araddr),
 .m_axi_arlen(rd_m[1].arlen),
 .m_axi_arsize(rd_m[1].arsize),
 .m_axi_arburst(rd_m[1].arburst),
 .m_axi_arlock(rd_m[1].arlock),
 .m_axi_arcache(rd_m[1].arcache),
 .m_axi_arprot(rd_m[1].arprot),
 .m_axi_arqos(rd_m[1].arqos),
 .m_axi_arvalid(rd_m[1].arvalid),
 .m_axi_arready(rd_s[1].arready),
 .m_axi_rid(rd_s[1].rid),
 .m_axi_rdata(rd_s[1].rdata),
 .m_axi_rresp(rd_s[1].rresp),
 .m_axi_rlast(rd_s[1].rlast),
 .m_axi_rvalid(rd_s[1].rvalid),
 .m_axi_rready(rd_m[1].rready));
 cnn_axi_read read2(.clk(ap_clk),.rst,.base_addr(rd_base[2]),.cmd_valid(mc_v[2]),.cmd_ready(mc_r[2]),.cmd_addr(mc_a[2]),.cmd_words(mc_w[2]),.data_valid(md_v[2]),.data_ready(md_r[2]),.data(md[2]),.error(read_error[2]),.idle(read_idle[2]),
 .m_axi_arid(rd_m[2].arid),
 .m_axi_araddr(rd_m[2].araddr),
 .m_axi_arlen(rd_m[2].arlen),
 .m_axi_arsize(rd_m[2].arsize),
 .m_axi_arburst(rd_m[2].arburst),
 .m_axi_arlock(rd_m[2].arlock),
 .m_axi_arcache(rd_m[2].arcache),
 .m_axi_arprot(rd_m[2].arprot),
 .m_axi_arqos(rd_m[2].arqos),
 .m_axi_arvalid(rd_m[2].arvalid),
 .m_axi_arready(rd_s[2].arready),
 .m_axi_rid(rd_s[2].rid),
 .m_axi_rdata(rd_s[2].rdata),
 .m_axi_rresp(rd_s[2].rresp),
 .m_axi_rlast(rd_s[2].rlast),
 .m_axi_rvalid(rd_s[2].rvalid),
 .m_axi_rready(rd_m[2].rready));
 cnn_axi_read read3(.clk(ap_clk),.rst,.base_addr(rd_base[3]),.cmd_valid(mc_v[3]),.cmd_ready(mc_r[3]),.cmd_addr(mc_a[3]),.cmd_words(mc_w[3]),.data_valid(md_v[3]),.data_ready(md_r[3]),.data(md[3]),.error(read_error[3]),.idle(read_idle[3]),
 .m_axi_arid(rd_m[3].arid),
 .m_axi_araddr(rd_m[3].araddr),
 .m_axi_arlen(rd_m[3].arlen),
 .m_axi_arsize(rd_m[3].arsize),
 .m_axi_arburst(rd_m[3].arburst),
 .m_axi_arlock(rd_m[3].arlock),
 .m_axi_arcache(rd_m[3].arcache),
 .m_axi_arprot(rd_m[3].arprot),
 .m_axi_arqos(rd_m[3].arqos),
 .m_axi_arvalid(rd_m[3].arvalid),
 .m_axi_arready(rd_s[3].arready),
 .m_axi_rid(rd_s[3].rid),
 .m_axi_rdata(rd_s[3].rdata),
 .m_axi_rresp(rd_s[3].rresp),
 .m_axi_rlast(rd_s[3].rlast),
 .m_axi_rvalid(rd_s[3].rvalid),
 .m_axi_rready(rd_m[3].rready));
 cnn_axi_write write0(.clk(ap_clk),.rst,.base_addr(wr_base[0]),.cmd_valid(wc_v[0]),.cmd_ready(wc_r[0]),.cmd_addr(wc_a[0]),.cmd_words(wc_w[0]),.data_valid(wd_v[0]),.data_ready(wd_r[0]),.data(wd[0]),.commit_valid(wb_v[0]),.commit_ready(wb_r[0]),.error(write_error[0]),.idle(write_idle[0]),
 .m_axi_awid(wr_m[0].awid),
 .m_axi_awaddr(wr_m[0].awaddr),
 .m_axi_awlen(wr_m[0].awlen),
 .m_axi_awsize(wr_m[0].awsize),
 .m_axi_awburst(wr_m[0].awburst),
 .m_axi_awlock(wr_m[0].awlock),
 .m_axi_awcache(wr_m[0].awcache),
 .m_axi_awprot(wr_m[0].awprot),
 .m_axi_awqos(wr_m[0].awqos),
 .m_axi_awvalid(wr_m[0].awvalid),
 .m_axi_awready(wr_s[0].awready),
 .m_axi_wdata(wr_m[0].wdata),
 .m_axi_wstrb(wr_m[0].wstrb),
 .m_axi_wlast(wr_m[0].wlast),
 .m_axi_wvalid(wr_m[0].wvalid),
 .m_axi_wready(wr_s[0].wready),
 .m_axi_bid(wr_s[0].bid),
 .m_axi_bresp(wr_s[0].bresp),
 .m_axi_bvalid(wr_s[0].bvalid),
 .m_axi_bready(wr_m[0].bready));
 cnn_axi_write write1(.clk(ap_clk),.rst,.base_addr(wr_base[1]),.cmd_valid(wc_v[1]),.cmd_ready(wc_r[1]),.cmd_addr(wc_a[1]),.cmd_words(wc_w[1]),.data_valid(wd_v[1]),.data_ready(wd_r[1]),.data(wd[1]),.commit_valid(wb_v[1]),.commit_ready(wb_r[1]),.error(write_error[1]),.idle(write_idle[1]),
 .m_axi_awid(wr_m[1].awid),
 .m_axi_awaddr(wr_m[1].awaddr),
 .m_axi_awlen(wr_m[1].awlen),
 .m_axi_awsize(wr_m[1].awsize),
 .m_axi_awburst(wr_m[1].awburst),
 .m_axi_awlock(wr_m[1].awlock),
 .m_axi_awcache(wr_m[1].awcache),
 .m_axi_awprot(wr_m[1].awprot),
 .m_axi_awqos(wr_m[1].awqos),
 .m_axi_awvalid(wr_m[1].awvalid),
 .m_axi_awready(wr_s[1].awready),
 .m_axi_wdata(wr_m[1].wdata),
 .m_axi_wstrb(wr_m[1].wstrb),
 .m_axi_wlast(wr_m[1].wlast),
 .m_axi_wvalid(wr_m[1].wvalid),
 .m_axi_wready(wr_s[1].wready),
 .m_axi_bid(wr_s[1].bid),
 .m_axi_bresp(wr_s[1].bresp),
 .m_axi_bvalid(wr_s[1].bvalid),
 .m_axi_bready(wr_m[1].bready));
 assign p1_cv[0]=pf_cv[0];assign pf_cr[0]=p1_cr[0];assign p1_ca[0]=pf_ca[0];assign p1_cw[0]=pf_cw[0];
 assign pf_dv[0]=p1_dv[0];assign p1_dr[0]=pf_dr[0];assign pf_data[0]=p1_data[0];
 assign p2_cv[0]=pf_cv[1];assign pf_cr[1]=p2_cr[0];assign p2_ca[0]=pf_ca[1];assign p2_cw[0]=pf_cw[1];
 assign pf_dv[1]=p2_dv[0];assign p2_dr[0]=pf_dr[1];assign pf_data[1]=p2_data[0];
 logic [1:0] feed_v,feed_r,dw3_v,dw3_r,dw7_v,dw7_r,pw1_v,pw1_r,pw2_v,pw2_r,skip_v,skip_r;
 logic signed [15:0] feed_d[2],dw3_d[2],dw7_d[2],pw1_d[2],pw2_d[2],skip_d[2];
 logic [1:0] q3_v,q3_r,q7_v,q7_r,ex_v,ex_r;
 logic signed [15:0] q3_d[2],q7_d[2],ex_d[2];
 logic [31:0] feed_trace[2],dw3_trace[2],dw7_trace[2],pw1_trace[2],pw2_trace[2],out_trace[2],res_trace[2];
 logic [1:0] res_token_v,res_token_r,res_release_v,res_release_r;
 logic [31:0] res_token[2];
 logic [1:0] row_commit_valid,row_can_read,feed_cv,feed_cr;
 logic [5:0] row_commit_index[2];logic [4:0] row_commit_block[2];
 logic [31:0] feed_ca[2];logic [5:0] feed_cw[2];
 logic [1:0] res_cv,res_cr,res_dv,res_dr;logic [31:0] res_ca[2];logic [5:0] res_cw[2];logic [127:0] res_data[2];
 logic [1:0] sqv[3],sqr[3],spv[3],spr[3];
 logic signed [47:0] sqvalue[3][2];logic signed [31:0] sqmul[3][2];logic [5:0] sqshift[3][2];logic signed [15:0] spdata[3][2];
 cnn_feed feed0(.clk(ap_clk),.rst,.start(stage_start[0]),.done(stage_done[0]),.busy(),.profile,.block_index(block_index[0]),.transition_stage,.slot_words(job_slot_words),.out_valid(feed_v[0]),.out_ready(feed_r[0]),.out_data(feed_d[0]),.trace(feed_trace[0]),.cmd_valid(feed_cv[0]),.cmd_ready(feed_cr[0]),.cmd_addr(feed_ca[0]),.cmd_words(feed_cw[0]),.data_valid(ar0_dv[0]),.data_ready(ar0_dr[0]),.data(ar0_data[0]));
 assign ar0_cv[0]=feed_cv[0]&&row_can_read[0];assign feed_cr[0]=ar0_cr[0]&&row_can_read[0];assign ar0_ca[0]=feed_ca[0];assign ar0_cw[0]=feed_cw[0];
 cnn_row_guard rows0(.clk(ap_clk),.rst,.job_start(capture_config),.profile,.slot_words(job_slot_words),.feed_block_index(block_index[0]),.feed_cmd_addr(feed_ca[0]),.row_commit_valid(row_commit_valid[0]),.row_commit_index(row_commit_index[0]),.writer_block_index(row_commit_block[0]),.can_read(row_can_read[0]));
 cnn_output output0(.clk(ap_clk),.rst,.start(stage_start[6]),.done(stage_done[6]),.busy(),.profile,.block_index(block_index[6]),.transition_stage,.slot_words(job_slot_words),.in_valid(pw2_v[0]),.in_ready(pw2_r[0]),.in_data(pw2_d[0]),.trace(out_trace[0]),.row_commit_valid(row_commit_valid[0]),.row_commit_index(row_commit_index[0]),.row_commit_block(row_commit_block[0]),.cmd_valid(aw0_cv[1]),.cmd_ready(aw0_cr[1]),.cmd_addr(aw0_ca[1]),.cmd_words(aw0_cw[1]),.data_valid(aw0_dv[1]),.data_ready(aw0_dr[1]),.data(aw0_data[1]),.commit_valid(aw0_bv[1]),.commit_ready(aw0_br[1]));
 cnn_residual_store residual0(.clk(ap_clk),.rst,.start(stage_start[8]),.done(stage_done[8]),.busy(),.profile,.block_index(block_index[8]),.transition_stage,.slot_words(job_slot_words),.in_valid(skip_v[0]),.in_ready(skip_r[0]),.in_data(skip_d[0]),.trace(res_trace[0]),.ready_valid(res_token_v[0]),.ready_ready(res_token_r[0]),.ready_token(res_token[0]),.release_valid(res_release_v[0]),.release_ready(res_release_r[0]),.cmd_valid(aw0_cv[0]),.cmd_ready(aw0_cr[0]),.cmd_addr(aw0_ca[0]),.cmd_words(aw0_cw[0]),.data_valid(aw0_dv[0]),.data_ready(aw0_dr[0]),.data(aw0_data[0]),.commit_valid(aw0_bv[0]),.commit_ready(aw0_br[0]));
 assign ar0_cv[1]=res_cv[0];assign res_cr[0]=ar0_cr[1];assign ar0_ca[1]=res_ca[0];assign ar0_cw[1]=res_cw[0];assign res_dv[0]=ar0_dv[1];assign ar0_dr[1]=res_dr[0];assign res_data[0]=ar0_data[1];
 cnn_fifo #(.WIDTH(16),.DEPTH(4096)) q30(.clk(ap_clk),.rst,.s_valid(dw3_v[0]),.s_ready(dw3_r[0]),.s_data(dw3_d[0]),.m_valid(q3_v[0]),.m_ready(q3_r[0]),.m_data(q3_d[0]),.level());
 cnn_fifo #(.WIDTH(16),.DEPTH(8192)) q70(.clk(ap_clk),.rst,.s_valid(dw7_v[0]),.s_ready(dw7_r[0]),.s_data(dw7_d[0]),.m_valid(q7_v[0]),.m_ready(q7_r[0]),.m_data(q7_d[0]),.level());
 cnn_fifo #(.WIDTH(16),.DEPTH(2048)) expanded0(.clk(ap_clk),.rst,.s_valid(pw1_v[0]),.s_ready(pw1_r[0]),.s_data(pw1_d[0]),.m_valid(ex_v[0]),.m_ready(ex_r[0]),.m_data(ex_d[0]),.level());
 logic [2:0] lane0_reqv,lane0_reqr,lane0_rspv,lane0_rspr;logic signed [47:0] lane0_value[3];logic signed[31:0] lane0_mul[3];logic [5:0] lane0_shift[3];logic signed[15:0] lane0_rsp[3];
 assign lane0_reqv[0]=sqv[0][0];assign sqr[0][0]=lane0_reqr[0];assign lane0_value[0]=sqvalue[0][0];assign lane0_mul[0]=sqmul[0][0];assign lane0_shift[0]=sqshift[0][0];assign spv[0][0]=lane0_rspv[0];assign lane0_rspr[0]=spr[0][0];assign spdata[0][0]=lane0_rsp[0];
 assign lane0_reqv[1]=sqv[1][0];assign sqr[1][0]=lane0_reqr[1];assign lane0_value[1]=sqvalue[1][0];assign lane0_mul[1]=sqmul[1][0];assign lane0_shift[1]=sqshift[1][0];assign spv[1][0]=lane0_rspv[1];assign lane0_rspr[1]=spr[1][0];assign spdata[1][0]=lane0_rsp[1];
 assign lane0_reqv[2]=sqv[2][0];assign sqr[2][0]=lane0_reqr[2];assign lane0_value[2]=sqvalue[2][0];assign lane0_mul[2]=sqmul[2][0];assign lane0_shift[2]=sqshift[2][0];assign spv[2][0]=lane0_rspv[2];assign lane0_rspr[2]=spr[2][0];assign spdata[2][0]=lane0_rsp[2];
 cnn_scale_service scale0(.clk(ap_clk),.rst,.req_valid(lane0_reqv),.req_ready(lane0_reqr),.req_value(lane0_value),.req_multiplier(lane0_mul),.req_shift(lane0_shift),.rsp_valid(lane0_rspv),.rsp_ready(lane0_rspr),.rsp_data(lane0_rsp));
 cnn_feed feed1(.clk(ap_clk),.rst,.start(stage_start[1]),.done(stage_done[1]),.busy(),.profile,.block_index(block_index[1]),.transition_stage,.slot_words(job_slot_words),.out_valid(feed_v[1]),.out_ready(feed_r[1]),.out_data(feed_d[1]),.trace(feed_trace[1]),.cmd_valid(feed_cv[1]),.cmd_ready(feed_cr[1]),.cmd_addr(feed_ca[1]),.cmd_words(feed_cw[1]),.data_valid(ar1_dv[0]),.data_ready(ar1_dr[0]),.data(ar1_data[0]));
 assign ar1_cv[0]=feed_cv[1]&&row_can_read[1];assign feed_cr[1]=ar1_cr[0]&&row_can_read[1];assign ar1_ca[0]=feed_ca[1];assign ar1_cw[0]=feed_cw[1];
 cnn_row_guard rows1(.clk(ap_clk),.rst,.job_start(capture_config),.profile,.slot_words(job_slot_words),.feed_block_index(block_index[1]),.feed_cmd_addr(feed_ca[1]),.row_commit_valid(row_commit_valid[1]),.row_commit_index(row_commit_index[1]),.writer_block_index(row_commit_block[1]),.can_read(row_can_read[1]));
 cnn_output output1(.clk(ap_clk),.rst,.start(stage_start[7]),.done(stage_done[7]),.busy(),.profile,.block_index(block_index[7]),.transition_stage,.slot_words(job_slot_words),.in_valid(pw2_v[1]),.in_ready(pw2_r[1]),.in_data(pw2_d[1]),.trace(out_trace[1]),.row_commit_valid(row_commit_valid[1]),.row_commit_index(row_commit_index[1]),.row_commit_block(row_commit_block[1]),.cmd_valid(aw1_cv[1]),.cmd_ready(aw1_cr[1]),.cmd_addr(aw1_ca[1]),.cmd_words(aw1_cw[1]),.data_valid(aw1_dv[1]),.data_ready(aw1_dr[1]),.data(aw1_data[1]),.commit_valid(aw1_bv[1]),.commit_ready(aw1_br[1]));
 cnn_residual_store residual1(.clk(ap_clk),.rst,.start(stage_start[9]),.done(stage_done[9]),.busy(),.profile,.block_index(block_index[9]),.transition_stage,.slot_words(job_slot_words),.in_valid(skip_v[1]),.in_ready(skip_r[1]),.in_data(skip_d[1]),.trace(res_trace[1]),.ready_valid(res_token_v[1]),.ready_ready(res_token_r[1]),.ready_token(res_token[1]),.release_valid(res_release_v[1]),.release_ready(res_release_r[1]),.cmd_valid(aw1_cv[0]),.cmd_ready(aw1_cr[0]),.cmd_addr(aw1_ca[0]),.cmd_words(aw1_cw[0]),.data_valid(aw1_dv[0]),.data_ready(aw1_dr[0]),.data(aw1_data[0]),.commit_valid(aw1_bv[0]),.commit_ready(aw1_br[0]));
 assign ar1_cv[1]=res_cv[1];assign res_cr[1]=ar1_cr[1];assign ar1_ca[1]=res_ca[1];assign ar1_cw[1]=res_cw[1];assign res_dv[1]=ar1_dv[1];assign ar1_dr[1]=res_dr[1];assign res_data[1]=ar1_data[1];
 cnn_fifo #(.WIDTH(16),.DEPTH(4096)) q31(.clk(ap_clk),.rst,.s_valid(dw3_v[1]),.s_ready(dw3_r[1]),.s_data(dw3_d[1]),.m_valid(q3_v[1]),.m_ready(q3_r[1]),.m_data(q3_d[1]),.level());
 cnn_fifo #(.WIDTH(16),.DEPTH(8192)) q71(.clk(ap_clk),.rst,.s_valid(dw7_v[1]),.s_ready(dw7_r[1]),.s_data(dw7_d[1]),.m_valid(q7_v[1]),.m_ready(q7_r[1]),.m_data(q7_d[1]),.level());
 cnn_fifo #(.WIDTH(16),.DEPTH(2048)) expanded1(.clk(ap_clk),.rst,.s_valid(pw1_v[1]),.s_ready(pw1_r[1]),.s_data(pw1_d[1]),.m_valid(ex_v[1]),.m_ready(ex_r[1]),.m_data(ex_d[1]),.level());
 logic [2:0] lane1_reqv,lane1_reqr,lane1_rspv,lane1_rspr;logic signed [47:0] lane1_value[3];logic signed[31:0] lane1_mul[3];logic [5:0] lane1_shift[3];logic signed[15:0] lane1_rsp[3];
 assign lane1_reqv[0]=sqv[0][1];assign sqr[0][1]=lane1_reqr[0];assign lane1_value[0]=sqvalue[0][1];assign lane1_mul[0]=sqmul[0][1];assign lane1_shift[0]=sqshift[0][1];assign spv[0][1]=lane1_rspv[0];assign lane1_rspr[0]=spr[0][1];assign spdata[0][1]=lane1_rsp[0];
 assign lane1_reqv[1]=sqv[1][1];assign sqr[1][1]=lane1_reqr[1];assign lane1_value[1]=sqvalue[1][1];assign lane1_mul[1]=sqmul[1][1];assign lane1_shift[1]=sqshift[1][1];assign spv[1][1]=lane1_rspv[1];assign lane1_rspr[1]=spr[1][1];assign spdata[1][1]=lane1_rsp[1];
 assign lane1_reqv[2]=sqv[2][1];assign sqr[2][1]=lane1_reqr[2];assign lane1_value[2]=sqvalue[2][1];assign lane1_mul[2]=sqmul[2][1];assign lane1_shift[2]=sqshift[2][1];assign spv[2][1]=lane1_rspv[2];assign lane1_rspr[2]=spr[2][1];assign spdata[2][1]=lane1_rsp[2];
 cnn_scale_service scale1(.clk(ap_clk),.rst,.req_valid(lane1_reqv),.req_ready(lane1_reqr),.req_value(lane1_value),.req_multiplier(lane1_mul),.req_shift(lane1_shift),.rsp_valid(lane1_rspv),.rsp_ready(lane1_rspr),.rsp_data(lane1_rsp));
 cnn_dw_stage #(.K(3),.LANES(4)) dw3(.clk(ap_clk),.rst,.start(stage_start[2]),.done(stage_done[2]),.busy(),.profile,.block_index(block_index[2]),.transition_stage,.in_valid(feed_v),.in_ready(feed_r),.in_data(feed_d),.out_valid(dw3_v),.out_ready(dw3_r),.out_data(dw3_d),.skip_valid(),.skip_ready(2'b11),.skip_data(),.cmd_valid(p1_cv[1]),.cmd_ready(p1_cr[1]),.cmd_addr(p1_ca[1]),.cmd_words(p1_cw[1]),.data_valid(p1_dv[1]),.data_ready(p1_dr[1]),.data(p1_data[1]),.scale_req_valid(sqv[0]),.scale_req_ready(sqr[0]),.scale_req_value(sqvalue[0]),.scale_req_multiplier(sqmul[0]),.scale_req_shift(sqshift[0]),.scale_rsp_valid(spv[0]),.scale_rsp_ready(spr[0]),.scale_rsp_data(spdata[0]),.trace(dw3_trace),.error(stage_error[0]));
 cnn_dw_stage #(.K(7),.LANES(16)) dw7(.clk(ap_clk),.rst,.start(stage_start[3]),.done(stage_done[3]),.busy(),.profile,.block_index(block_index[3]),.transition_stage,.in_valid(q3_v),.in_ready(q3_r),.in_data(q3_d),.out_valid(dw7_v),.out_ready(dw7_r),.out_data(dw7_d),.skip_valid(skip_v),.skip_ready(skip_r),.skip_data(skip_d),.cmd_valid(p1_cv[2]),.cmd_ready(p1_cr[2]),.cmd_addr(p1_ca[2]),.cmd_words(p1_cw[2]),.data_valid(p1_dv[2]),.data_ready(p1_dr[2]),.data(p1_data[2]),.scale_req_valid(sqv[1]),.scale_req_ready(sqr[1]),.scale_req_value(sqvalue[1]),.scale_req_multiplier(sqmul[1]),.scale_req_shift(sqshift[1]),.scale_rsp_valid(spv[1]),.scale_rsp_ready(spr[1]),.scale_rsp_data(spdata[1]),.trace(dw7_trace),.error(stage_error[1]));
 cnn_pw1_stage pw1(.clk(ap_clk),.rst,.start(stage_start[4]),.done(stage_done[4]),.busy(),.profile,.block_index(block_index[4]),.transition_stage,.fast_clk(pw_fast_clk),.fast_rst(pw_fast_rst),.in_valid(q7_v),.in_ready(q7_r),.in_data(q7_d),.out_valid(pw1_v),.out_ready(pw1_r),.out_data(pw1_d),.cmd_valid(p1_cv[3]),.cmd_ready(p1_cr[3]),.cmd_addr(p1_ca[3]),.cmd_words(p1_cw[3]),.data_valid(p1_dv[3]),.data_ready(p1_dr[3]),.data(p1_data[3]),.trace(pw1_trace),.error(stage_error[2]));
 cnn_pw2_stage pw2(.clk(ap_clk),.rst,.start(stage_start[5]),.done(stage_done[5]),.busy(),.profile,.block_index(block_index[5]),.transition_stage,.fast_clk(pw_fast_clk),.fast_rst(pw_fast_rst),.slot_words(job_slot_words),.in_valid(ex_v),.in_ready(ex_r),.in_data(ex_d),.out_valid(pw2_v),.out_ready(pw2_r),.out_data(pw2_d),.cmd_valid(p2_cv[1]),.cmd_ready(p2_cr[1]),.cmd_addr(p2_ca[1]),.cmd_words(p2_cw[1]),.data_valid(p2_dv[1]),.data_ready(p2_dr[1]),.data(p2_data[1]),.scale_req_valid(sqv[2]),.scale_req_ready(sqr[2]),.scale_req_value(sqvalue[2]),.scale_req_multiplier(sqmul[2]),.scale_req_shift(sqshift[2]),.scale_rsp_valid(spv[2]),.scale_rsp_ready(spr[2]),.scale_rsp_data(spdata[2]),.res_cmd_valid(res_cv),.res_cmd_ready(res_cr),.res_cmd_addr(res_ca),.res_cmd_words(res_cw),.res_data_valid(res_dv),.res_data_ready(res_dr),.res_data(res_data),.res_ready_valid(res_token_v),.res_ready_ready(res_token_r),.res_ready_token(res_token),.res_release_valid(res_release_v),.res_release_ready(res_release_r),.trace(pw2_trace),.error(stage_error[3]));
 assign trace_a_feed=feed_trace[0];
 assign trace_a_dw3=dw3_trace[0];
 assign trace_a_dw7=dw7_trace[0];
 assign trace_a_pw1=pw1_trace[0];
 assign trace_a_pw2=pw2_trace[0];
 assign trace_a_write=out_trace[0];
 assign trace_b_feed=feed_trace[1];
 assign trace_b_dw3=dw3_trace[1];
 assign trace_b_dw7=dw7_trace[1];
 assign trace_b_pw1=pw1_trace[1];
 assign trace_b_pw2=pw2_trace[1];
 assign trace_b_write=out_trace[1];
 assign datapath_error=read_error[0]|read_error[1]|read_error[2]|read_error[3]|write_error[0]|write_error[1]|stage_error[0]|stage_error[1]|stage_error[2]|stage_error[3];
endmodule
