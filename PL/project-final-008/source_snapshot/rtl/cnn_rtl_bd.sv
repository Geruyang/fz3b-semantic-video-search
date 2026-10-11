// Handwritten protocol wrapper. No generated compute logic.
module cnn_rtl_bd (
  (* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 ap_clk CLK", X_INTERFACE_PARAMETER = "ASSOCIATED_BUSIF m_axi_g_param1:m_axi_g_param2:m_axi_g_act_a_r:m_axi_g_act_a_w:m_axi_g_act_b_r:m_axi_g_act_b_w:s_axi_control, ASSOCIATED_RESET ap_rst_n, FREQ_HZ 199998002" *)
  input logic ap_clk,
  (* X_INTERFACE_INFO = "xilinx.com:signal:reset:1.0 ap_rst_n RST", X_INTERFACE_PARAMETER = "POLARITY ACTIVE_LOW" *)
  input logic ap_rst_n,
  (* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 pw_fast_clk CLK", X_INTERFACE_PARAMETER = "FREQ_HZ 399996004, ASSOCIATED_RESET pw_fast_rst" *)
  input logic pw_fast_clk,
  (* X_INTERFACE_INFO = "xilinx.com:signal:reset:1.0 pw_fast_rst RST", X_INTERFACE_PARAMETER = "POLARITY ACTIVE_HIGH" *)
  input logic pw_fast_rst,
  input logic ap_start,
  output logic ap_done,
  output logic ap_idle,
  output logic ap_ready,
  output logic [31:0] protocol_error,
  output logic protocol_error_ap_vld,
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
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param1 AWVALID", X_INTERFACE_PARAMETER = "READ_WRITE_MODE READ_WRITE, PROTOCOL AXI4, ADDR_WIDTH 64, DATA_WIDTH 128, ID_WIDTH 1, HAS_BURST 1, MAX_BURST_LENGTH 32, NUM_READ_OUTSTANDING 4, NUM_WRITE_OUTSTANDING 4" *)
  output logic m_axi_g_param1_AWVALID,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param1 AWADDR" *)
  output logic [63:0] m_axi_g_param1_AWADDR,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param1 AWID" *)
  output logic m_axi_g_param1_AWID,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param1 AWLEN" *)
  output logic [7:0] m_axi_g_param1_AWLEN,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param1 AWSIZE" *)
  output logic [2:0] m_axi_g_param1_AWSIZE,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param1 AWBURST" *)
  output logic [1:0] m_axi_g_param1_AWBURST,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param1 AWLOCK" *)
  output logic m_axi_g_param1_AWLOCK,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param1 AWCACHE" *)
  output logic [3:0] m_axi_g_param1_AWCACHE,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param1 AWPROT" *)
  output logic [2:0] m_axi_g_param1_AWPROT,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param1 AWQOS" *)
  output logic [3:0] m_axi_g_param1_AWQOS,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param1 AWREGION" *)
  output logic [3:0] m_axi_g_param1_AWREGION,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param1 AWUSER" *)
  output logic m_axi_g_param1_AWUSER,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param1 WVALID" *)
  output logic m_axi_g_param1_WVALID,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param1 WDATA" *)
  output logic [127:0] m_axi_g_param1_WDATA,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param1 WSTRB" *)
  output logic [15:0] m_axi_g_param1_WSTRB,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param1 WLAST" *)
  output logic m_axi_g_param1_WLAST,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param1 WUSER" *)
  output logic m_axi_g_param1_WUSER,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param1 ARVALID" *)
  output logic m_axi_g_param1_ARVALID,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param1 ARADDR" *)
  output logic [63:0] m_axi_g_param1_ARADDR,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param1 ARID" *)
  output logic m_axi_g_param1_ARID,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param1 ARLEN" *)
  output logic [7:0] m_axi_g_param1_ARLEN,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param1 ARSIZE" *)
  output logic [2:0] m_axi_g_param1_ARSIZE,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param1 ARBURST" *)
  output logic [1:0] m_axi_g_param1_ARBURST,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param1 ARLOCK" *)
  output logic m_axi_g_param1_ARLOCK,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param1 ARCACHE" *)
  output logic [3:0] m_axi_g_param1_ARCACHE,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param1 ARPROT" *)
  output logic [2:0] m_axi_g_param1_ARPROT,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param1 ARQOS" *)
  output logic [3:0] m_axi_g_param1_ARQOS,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param1 ARREGION" *)
  output logic [3:0] m_axi_g_param1_ARREGION,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param1 ARUSER" *)
  output logic m_axi_g_param1_ARUSER,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param1 RREADY" *)
  output logic m_axi_g_param1_RREADY,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param1 BREADY" *)
  output logic m_axi_g_param1_BREADY,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param1 AWREADY" *)
  input logic m_axi_g_param1_AWREADY,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param1 WREADY" *)
  input logic m_axi_g_param1_WREADY,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param1 ARREADY" *)
  input logic m_axi_g_param1_ARREADY,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param1 RVALID" *)
  input logic m_axi_g_param1_RVALID,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param1 RDATA" *)
  input logic [127:0] m_axi_g_param1_RDATA,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param1 RLAST" *)
  input logic m_axi_g_param1_RLAST,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param1 RID" *)
  input logic m_axi_g_param1_RID,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param1 RUSER" *)
  input logic m_axi_g_param1_RUSER,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param1 RRESP" *)
  input logic [1:0] m_axi_g_param1_RRESP,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param1 BVALID" *)
  input logic m_axi_g_param1_BVALID,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param1 BRESP" *)
  input logic [1:0] m_axi_g_param1_BRESP,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param1 BID" *)
  input logic m_axi_g_param1_BID,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param1 BUSER" *)
  input logic m_axi_g_param1_BUSER,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param2 AWVALID", X_INTERFACE_PARAMETER = "READ_WRITE_MODE READ_WRITE, PROTOCOL AXI4, ADDR_WIDTH 64, DATA_WIDTH 128, ID_WIDTH 1, HAS_BURST 1, MAX_BURST_LENGTH 32, NUM_READ_OUTSTANDING 4, NUM_WRITE_OUTSTANDING 4" *)
  output logic m_axi_g_param2_AWVALID,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param2 AWADDR" *)
  output logic [63:0] m_axi_g_param2_AWADDR,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param2 AWID" *)
  output logic m_axi_g_param2_AWID,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param2 AWLEN" *)
  output logic [7:0] m_axi_g_param2_AWLEN,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param2 AWSIZE" *)
  output logic [2:0] m_axi_g_param2_AWSIZE,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param2 AWBURST" *)
  output logic [1:0] m_axi_g_param2_AWBURST,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param2 AWLOCK" *)
  output logic m_axi_g_param2_AWLOCK,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param2 AWCACHE" *)
  output logic [3:0] m_axi_g_param2_AWCACHE,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param2 AWPROT" *)
  output logic [2:0] m_axi_g_param2_AWPROT,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param2 AWQOS" *)
  output logic [3:0] m_axi_g_param2_AWQOS,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param2 AWREGION" *)
  output logic [3:0] m_axi_g_param2_AWREGION,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param2 AWUSER" *)
  output logic m_axi_g_param2_AWUSER,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param2 WVALID" *)
  output logic m_axi_g_param2_WVALID,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param2 WDATA" *)
  output logic [127:0] m_axi_g_param2_WDATA,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param2 WSTRB" *)
  output logic [15:0] m_axi_g_param2_WSTRB,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param2 WLAST" *)
  output logic m_axi_g_param2_WLAST,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param2 WUSER" *)
  output logic m_axi_g_param2_WUSER,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param2 ARVALID" *)
  output logic m_axi_g_param2_ARVALID,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param2 ARADDR" *)
  output logic [63:0] m_axi_g_param2_ARADDR,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param2 ARID" *)
  output logic m_axi_g_param2_ARID,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param2 ARLEN" *)
  output logic [7:0] m_axi_g_param2_ARLEN,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param2 ARSIZE" *)
  output logic [2:0] m_axi_g_param2_ARSIZE,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param2 ARBURST" *)
  output logic [1:0] m_axi_g_param2_ARBURST,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param2 ARLOCK" *)
  output logic m_axi_g_param2_ARLOCK,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param2 ARCACHE" *)
  output logic [3:0] m_axi_g_param2_ARCACHE,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param2 ARPROT" *)
  output logic [2:0] m_axi_g_param2_ARPROT,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param2 ARQOS" *)
  output logic [3:0] m_axi_g_param2_ARQOS,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param2 ARREGION" *)
  output logic [3:0] m_axi_g_param2_ARREGION,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param2 ARUSER" *)
  output logic m_axi_g_param2_ARUSER,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param2 RREADY" *)
  output logic m_axi_g_param2_RREADY,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param2 BREADY" *)
  output logic m_axi_g_param2_BREADY,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param2 AWREADY" *)
  input logic m_axi_g_param2_AWREADY,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param2 WREADY" *)
  input logic m_axi_g_param2_WREADY,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param2 ARREADY" *)
  input logic m_axi_g_param2_ARREADY,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param2 RVALID" *)
  input logic m_axi_g_param2_RVALID,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param2 RDATA" *)
  input logic [127:0] m_axi_g_param2_RDATA,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param2 RLAST" *)
  input logic m_axi_g_param2_RLAST,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param2 RID" *)
  input logic m_axi_g_param2_RID,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param2 RUSER" *)
  input logic m_axi_g_param2_RUSER,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param2 RRESP" *)
  input logic [1:0] m_axi_g_param2_RRESP,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param2 BVALID" *)
  input logic m_axi_g_param2_BVALID,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param2 BRESP" *)
  input logic [1:0] m_axi_g_param2_BRESP,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param2 BID" *)
  input logic m_axi_g_param2_BID,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_param2 BUSER" *)
  input logic m_axi_g_param2_BUSER,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_r AWVALID", X_INTERFACE_PARAMETER = "READ_WRITE_MODE READ_WRITE, PROTOCOL AXI4, ADDR_WIDTH 64, DATA_WIDTH 128, ID_WIDTH 1, HAS_BURST 1, MAX_BURST_LENGTH 32, NUM_READ_OUTSTANDING 4, NUM_WRITE_OUTSTANDING 4" *)
  output logic m_axi_g_act_a_r_AWVALID,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_r AWADDR" *)
  output logic [63:0] m_axi_g_act_a_r_AWADDR,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_r AWID" *)
  output logic m_axi_g_act_a_r_AWID,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_r AWLEN" *)
  output logic [7:0] m_axi_g_act_a_r_AWLEN,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_r AWSIZE" *)
  output logic [2:0] m_axi_g_act_a_r_AWSIZE,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_r AWBURST" *)
  output logic [1:0] m_axi_g_act_a_r_AWBURST,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_r AWLOCK" *)
  output logic m_axi_g_act_a_r_AWLOCK,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_r AWCACHE" *)
  output logic [3:0] m_axi_g_act_a_r_AWCACHE,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_r AWPROT" *)
  output logic [2:0] m_axi_g_act_a_r_AWPROT,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_r AWQOS" *)
  output logic [3:0] m_axi_g_act_a_r_AWQOS,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_r AWREGION" *)
  output logic [3:0] m_axi_g_act_a_r_AWREGION,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_r AWUSER" *)
  output logic m_axi_g_act_a_r_AWUSER,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_r WVALID" *)
  output logic m_axi_g_act_a_r_WVALID,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_r WDATA" *)
  output logic [127:0] m_axi_g_act_a_r_WDATA,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_r WSTRB" *)
  output logic [15:0] m_axi_g_act_a_r_WSTRB,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_r WLAST" *)
  output logic m_axi_g_act_a_r_WLAST,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_r WUSER" *)
  output logic m_axi_g_act_a_r_WUSER,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_r ARVALID" *)
  output logic m_axi_g_act_a_r_ARVALID,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_r ARADDR" *)
  output logic [63:0] m_axi_g_act_a_r_ARADDR,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_r ARID" *)
  output logic m_axi_g_act_a_r_ARID,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_r ARLEN" *)
  output logic [7:0] m_axi_g_act_a_r_ARLEN,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_r ARSIZE" *)
  output logic [2:0] m_axi_g_act_a_r_ARSIZE,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_r ARBURST" *)
  output logic [1:0] m_axi_g_act_a_r_ARBURST,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_r ARLOCK" *)
  output logic m_axi_g_act_a_r_ARLOCK,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_r ARCACHE" *)
  output logic [3:0] m_axi_g_act_a_r_ARCACHE,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_r ARPROT" *)
  output logic [2:0] m_axi_g_act_a_r_ARPROT,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_r ARQOS" *)
  output logic [3:0] m_axi_g_act_a_r_ARQOS,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_r ARREGION" *)
  output logic [3:0] m_axi_g_act_a_r_ARREGION,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_r ARUSER" *)
  output logic m_axi_g_act_a_r_ARUSER,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_r RREADY" *)
  output logic m_axi_g_act_a_r_RREADY,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_r BREADY" *)
  output logic m_axi_g_act_a_r_BREADY,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_r AWREADY" *)
  input logic m_axi_g_act_a_r_AWREADY,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_r WREADY" *)
  input logic m_axi_g_act_a_r_WREADY,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_r ARREADY" *)
  input logic m_axi_g_act_a_r_ARREADY,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_r RVALID" *)
  input logic m_axi_g_act_a_r_RVALID,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_r RDATA" *)
  input logic [127:0] m_axi_g_act_a_r_RDATA,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_r RLAST" *)
  input logic m_axi_g_act_a_r_RLAST,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_r RID" *)
  input logic m_axi_g_act_a_r_RID,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_r RUSER" *)
  input logic m_axi_g_act_a_r_RUSER,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_r RRESP" *)
  input logic [1:0] m_axi_g_act_a_r_RRESP,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_r BVALID" *)
  input logic m_axi_g_act_a_r_BVALID,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_r BRESP" *)
  input logic [1:0] m_axi_g_act_a_r_BRESP,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_r BID" *)
  input logic m_axi_g_act_a_r_BID,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_r BUSER" *)
  input logic m_axi_g_act_a_r_BUSER,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_r AWVALID", X_INTERFACE_PARAMETER = "READ_WRITE_MODE READ_WRITE, PROTOCOL AXI4, ADDR_WIDTH 64, DATA_WIDTH 128, ID_WIDTH 1, HAS_BURST 1, MAX_BURST_LENGTH 32, NUM_READ_OUTSTANDING 4, NUM_WRITE_OUTSTANDING 4" *)
  output logic m_axi_g_act_b_r_AWVALID,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_r AWADDR" *)
  output logic [63:0] m_axi_g_act_b_r_AWADDR,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_r AWID" *)
  output logic m_axi_g_act_b_r_AWID,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_r AWLEN" *)
  output logic [7:0] m_axi_g_act_b_r_AWLEN,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_r AWSIZE" *)
  output logic [2:0] m_axi_g_act_b_r_AWSIZE,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_r AWBURST" *)
  output logic [1:0] m_axi_g_act_b_r_AWBURST,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_r AWLOCK" *)
  output logic m_axi_g_act_b_r_AWLOCK,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_r AWCACHE" *)
  output logic [3:0] m_axi_g_act_b_r_AWCACHE,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_r AWPROT" *)
  output logic [2:0] m_axi_g_act_b_r_AWPROT,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_r AWQOS" *)
  output logic [3:0] m_axi_g_act_b_r_AWQOS,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_r AWREGION" *)
  output logic [3:0] m_axi_g_act_b_r_AWREGION,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_r AWUSER" *)
  output logic m_axi_g_act_b_r_AWUSER,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_r WVALID" *)
  output logic m_axi_g_act_b_r_WVALID,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_r WDATA" *)
  output logic [127:0] m_axi_g_act_b_r_WDATA,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_r WSTRB" *)
  output logic [15:0] m_axi_g_act_b_r_WSTRB,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_r WLAST" *)
  output logic m_axi_g_act_b_r_WLAST,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_r WUSER" *)
  output logic m_axi_g_act_b_r_WUSER,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_r ARVALID" *)
  output logic m_axi_g_act_b_r_ARVALID,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_r ARADDR" *)
  output logic [63:0] m_axi_g_act_b_r_ARADDR,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_r ARID" *)
  output logic m_axi_g_act_b_r_ARID,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_r ARLEN" *)
  output logic [7:0] m_axi_g_act_b_r_ARLEN,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_r ARSIZE" *)
  output logic [2:0] m_axi_g_act_b_r_ARSIZE,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_r ARBURST" *)
  output logic [1:0] m_axi_g_act_b_r_ARBURST,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_r ARLOCK" *)
  output logic m_axi_g_act_b_r_ARLOCK,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_r ARCACHE" *)
  output logic [3:0] m_axi_g_act_b_r_ARCACHE,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_r ARPROT" *)
  output logic [2:0] m_axi_g_act_b_r_ARPROT,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_r ARQOS" *)
  output logic [3:0] m_axi_g_act_b_r_ARQOS,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_r ARREGION" *)
  output logic [3:0] m_axi_g_act_b_r_ARREGION,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_r ARUSER" *)
  output logic m_axi_g_act_b_r_ARUSER,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_r RREADY" *)
  output logic m_axi_g_act_b_r_RREADY,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_r BREADY" *)
  output logic m_axi_g_act_b_r_BREADY,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_r AWREADY" *)
  input logic m_axi_g_act_b_r_AWREADY,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_r WREADY" *)
  input logic m_axi_g_act_b_r_WREADY,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_r ARREADY" *)
  input logic m_axi_g_act_b_r_ARREADY,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_r RVALID" *)
  input logic m_axi_g_act_b_r_RVALID,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_r RDATA" *)
  input logic [127:0] m_axi_g_act_b_r_RDATA,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_r RLAST" *)
  input logic m_axi_g_act_b_r_RLAST,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_r RID" *)
  input logic m_axi_g_act_b_r_RID,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_r RUSER" *)
  input logic m_axi_g_act_b_r_RUSER,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_r RRESP" *)
  input logic [1:0] m_axi_g_act_b_r_RRESP,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_r BVALID" *)
  input logic m_axi_g_act_b_r_BVALID,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_r BRESP" *)
  input logic [1:0] m_axi_g_act_b_r_BRESP,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_r BID" *)
  input logic m_axi_g_act_b_r_BID,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_r BUSER" *)
  input logic m_axi_g_act_b_r_BUSER,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_w AWVALID", X_INTERFACE_PARAMETER = "READ_WRITE_MODE READ_WRITE, PROTOCOL AXI4, ADDR_WIDTH 64, DATA_WIDTH 128, ID_WIDTH 1, HAS_BURST 1, MAX_BURST_LENGTH 32, NUM_READ_OUTSTANDING 4, NUM_WRITE_OUTSTANDING 4" *)
  output logic m_axi_g_act_a_w_AWVALID,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_w AWADDR" *)
  output logic [63:0] m_axi_g_act_a_w_AWADDR,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_w AWID" *)
  output logic m_axi_g_act_a_w_AWID,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_w AWLEN" *)
  output logic [7:0] m_axi_g_act_a_w_AWLEN,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_w AWSIZE" *)
  output logic [2:0] m_axi_g_act_a_w_AWSIZE,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_w AWBURST" *)
  output logic [1:0] m_axi_g_act_a_w_AWBURST,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_w AWLOCK" *)
  output logic m_axi_g_act_a_w_AWLOCK,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_w AWCACHE" *)
  output logic [3:0] m_axi_g_act_a_w_AWCACHE,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_w AWPROT" *)
  output logic [2:0] m_axi_g_act_a_w_AWPROT,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_w AWQOS" *)
  output logic [3:0] m_axi_g_act_a_w_AWQOS,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_w AWREGION" *)
  output logic [3:0] m_axi_g_act_a_w_AWREGION,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_w AWUSER" *)
  output logic m_axi_g_act_a_w_AWUSER,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_w WVALID" *)
  output logic m_axi_g_act_a_w_WVALID,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_w WDATA" *)
  output logic [127:0] m_axi_g_act_a_w_WDATA,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_w WSTRB" *)
  output logic [15:0] m_axi_g_act_a_w_WSTRB,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_w WLAST" *)
  output logic m_axi_g_act_a_w_WLAST,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_w WUSER" *)
  output logic m_axi_g_act_a_w_WUSER,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_w ARVALID" *)
  output logic m_axi_g_act_a_w_ARVALID,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_w ARADDR" *)
  output logic [63:0] m_axi_g_act_a_w_ARADDR,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_w ARID" *)
  output logic m_axi_g_act_a_w_ARID,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_w ARLEN" *)
  output logic [7:0] m_axi_g_act_a_w_ARLEN,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_w ARSIZE" *)
  output logic [2:0] m_axi_g_act_a_w_ARSIZE,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_w ARBURST" *)
  output logic [1:0] m_axi_g_act_a_w_ARBURST,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_w ARLOCK" *)
  output logic m_axi_g_act_a_w_ARLOCK,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_w ARCACHE" *)
  output logic [3:0] m_axi_g_act_a_w_ARCACHE,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_w ARPROT" *)
  output logic [2:0] m_axi_g_act_a_w_ARPROT,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_w ARQOS" *)
  output logic [3:0] m_axi_g_act_a_w_ARQOS,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_w ARREGION" *)
  output logic [3:0] m_axi_g_act_a_w_ARREGION,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_w ARUSER" *)
  output logic m_axi_g_act_a_w_ARUSER,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_w RREADY" *)
  output logic m_axi_g_act_a_w_RREADY,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_w BREADY" *)
  output logic m_axi_g_act_a_w_BREADY,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_w AWREADY" *)
  input logic m_axi_g_act_a_w_AWREADY,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_w WREADY" *)
  input logic m_axi_g_act_a_w_WREADY,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_w ARREADY" *)
  input logic m_axi_g_act_a_w_ARREADY,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_w RVALID" *)
  input logic m_axi_g_act_a_w_RVALID,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_w RDATA" *)
  input logic [127:0] m_axi_g_act_a_w_RDATA,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_w RLAST" *)
  input logic m_axi_g_act_a_w_RLAST,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_w RID" *)
  input logic m_axi_g_act_a_w_RID,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_w RUSER" *)
  input logic m_axi_g_act_a_w_RUSER,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_w RRESP" *)
  input logic [1:0] m_axi_g_act_a_w_RRESP,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_w BVALID" *)
  input logic m_axi_g_act_a_w_BVALID,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_w BRESP" *)
  input logic [1:0] m_axi_g_act_a_w_BRESP,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_w BID" *)
  input logic m_axi_g_act_a_w_BID,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_a_w BUSER" *)
  input logic m_axi_g_act_a_w_BUSER,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_w AWVALID", X_INTERFACE_PARAMETER = "READ_WRITE_MODE READ_WRITE, PROTOCOL AXI4, ADDR_WIDTH 64, DATA_WIDTH 128, ID_WIDTH 1, HAS_BURST 1, MAX_BURST_LENGTH 32, NUM_READ_OUTSTANDING 4, NUM_WRITE_OUTSTANDING 4" *)
  output logic m_axi_g_act_b_w_AWVALID,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_w AWADDR" *)
  output logic [63:0] m_axi_g_act_b_w_AWADDR,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_w AWID" *)
  output logic m_axi_g_act_b_w_AWID,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_w AWLEN" *)
  output logic [7:0] m_axi_g_act_b_w_AWLEN,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_w AWSIZE" *)
  output logic [2:0] m_axi_g_act_b_w_AWSIZE,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_w AWBURST" *)
  output logic [1:0] m_axi_g_act_b_w_AWBURST,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_w AWLOCK" *)
  output logic m_axi_g_act_b_w_AWLOCK,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_w AWCACHE" *)
  output logic [3:0] m_axi_g_act_b_w_AWCACHE,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_w AWPROT" *)
  output logic [2:0] m_axi_g_act_b_w_AWPROT,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_w AWQOS" *)
  output logic [3:0] m_axi_g_act_b_w_AWQOS,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_w AWREGION" *)
  output logic [3:0] m_axi_g_act_b_w_AWREGION,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_w AWUSER" *)
  output logic m_axi_g_act_b_w_AWUSER,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_w WVALID" *)
  output logic m_axi_g_act_b_w_WVALID,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_w WDATA" *)
  output logic [127:0] m_axi_g_act_b_w_WDATA,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_w WSTRB" *)
  output logic [15:0] m_axi_g_act_b_w_WSTRB,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_w WLAST" *)
  output logic m_axi_g_act_b_w_WLAST,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_w WUSER" *)
  output logic m_axi_g_act_b_w_WUSER,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_w ARVALID" *)
  output logic m_axi_g_act_b_w_ARVALID,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_w ARADDR" *)
  output logic [63:0] m_axi_g_act_b_w_ARADDR,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_w ARID" *)
  output logic m_axi_g_act_b_w_ARID,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_w ARLEN" *)
  output logic [7:0] m_axi_g_act_b_w_ARLEN,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_w ARSIZE" *)
  output logic [2:0] m_axi_g_act_b_w_ARSIZE,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_w ARBURST" *)
  output logic [1:0] m_axi_g_act_b_w_ARBURST,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_w ARLOCK" *)
  output logic m_axi_g_act_b_w_ARLOCK,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_w ARCACHE" *)
  output logic [3:0] m_axi_g_act_b_w_ARCACHE,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_w ARPROT" *)
  output logic [2:0] m_axi_g_act_b_w_ARPROT,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_w ARQOS" *)
  output logic [3:0] m_axi_g_act_b_w_ARQOS,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_w ARREGION" *)
  output logic [3:0] m_axi_g_act_b_w_ARREGION,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_w ARUSER" *)
  output logic m_axi_g_act_b_w_ARUSER,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_w RREADY" *)
  output logic m_axi_g_act_b_w_RREADY,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_w BREADY" *)
  output logic m_axi_g_act_b_w_BREADY,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_w AWREADY" *)
  input logic m_axi_g_act_b_w_AWREADY,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_w WREADY" *)
  input logic m_axi_g_act_b_w_WREADY,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_w ARREADY" *)
  input logic m_axi_g_act_b_w_ARREADY,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_w RVALID" *)
  input logic m_axi_g_act_b_w_RVALID,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_w RDATA" *)
  input logic [127:0] m_axi_g_act_b_w_RDATA,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_w RLAST" *)
  input logic m_axi_g_act_b_w_RLAST,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_w RID" *)
  input logic m_axi_g_act_b_w_RID,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_w RUSER" *)
  input logic m_axi_g_act_b_w_RUSER,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_w RRESP" *)
  input logic [1:0] m_axi_g_act_b_w_RRESP,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_w BVALID" *)
  input logic m_axi_g_act_b_w_BVALID,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_w BRESP" *)
  input logic [1:0] m_axi_g_act_b_w_BRESP,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_w BID" *)
  input logic m_axi_g_act_b_w_BID,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi_g_act_b_w BUSER" *)
  input logic m_axi_g_act_b_w_BUSER,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_control AWVALID", X_INTERFACE_PARAMETER = "XIL_INTERFACENAME s_axi_control, READ_WRITE_MODE READ_WRITE, HAS_PROT 0, HAS_CACHE 0, HAS_LOCK 0, HAS_QOS 0, HAS_REGION 0, PROTOCOL AXI4LITE, ADDR_WIDTH 12, DATA_WIDTH 32, HAS_BURST 0" *)
  input logic s_axi_control_AWVALID,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_control AWREADY" *)
  output logic s_axi_control_AWREADY,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_control AWADDR" *)
  input logic [11:0] s_axi_control_AWADDR,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_control WVALID" *)
  input logic s_axi_control_WVALID,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_control WREADY" *)
  output logic s_axi_control_WREADY,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_control WDATA" *)
  input logic [31:0] s_axi_control_WDATA,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_control WSTRB" *)
  input logic [3:0] s_axi_control_WSTRB,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_control BVALID" *)
  output logic s_axi_control_BVALID,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_control BREADY" *)
  input logic s_axi_control_BREADY,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_control BRESP" *)
  output logic [1:0] s_axi_control_BRESP,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_control ARVALID" *)
  input logic s_axi_control_ARVALID,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_control ARREADY" *)
  output logic s_axi_control_ARREADY,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_control ARADDR" *)
  input logic [11:0] s_axi_control_ARADDR,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_control RVALID" *)
  output logic s_axi_control_RVALID,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_control RREADY" *)
  input logic s_axi_control_RREADY,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_control RDATA" *)
  output logic [31:0] s_axi_control_RDATA,
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_control RRESP" *)
  output logic [1:0] s_axi_control_RRESP
);
  import cnn_axi_pkg::*;
  read_m2s_t rd_m [4]; read_s2m_t rd_s [4];
  write_m2s_t wr_m [2]; write_s2m_t wr_s [2];
  assign m_axi_g_param1_AWVALID = '0;
  assign m_axi_g_param1_AWADDR = '0;
  assign m_axi_g_param1_AWID = '0;
  assign m_axi_g_param1_AWLEN = '0;
  assign m_axi_g_param1_AWSIZE = '0;
  assign m_axi_g_param1_AWBURST = '0;
  assign m_axi_g_param1_AWLOCK = '0;
  assign m_axi_g_param1_AWCACHE = '0;
  assign m_axi_g_param1_AWPROT = '0;
  assign m_axi_g_param1_AWQOS = '0;
  assign m_axi_g_param1_AWREGION = '0;
  assign m_axi_g_param1_AWUSER = '0;
  assign m_axi_g_param1_WVALID = '0;
  assign m_axi_g_param1_WDATA = '0;
  assign m_axi_g_param1_WSTRB = '0;
  assign m_axi_g_param1_WLAST = '0;
  assign m_axi_g_param1_WUSER = '0;
  assign m_axi_g_param1_ARVALID = rd_m[0].arvalid;
  assign m_axi_g_param1_ARADDR = rd_m[0].araddr;
  assign m_axi_g_param1_ARID = rd_m[0].arid;
  assign m_axi_g_param1_ARLEN = rd_m[0].arlen;
  assign m_axi_g_param1_ARSIZE = rd_m[0].arsize;
  assign m_axi_g_param1_ARBURST = rd_m[0].arburst;
  assign m_axi_g_param1_ARLOCK = rd_m[0].arlock;
  assign m_axi_g_param1_ARCACHE = rd_m[0].arcache;
  assign m_axi_g_param1_ARPROT = rd_m[0].arprot;
  assign m_axi_g_param1_ARQOS = rd_m[0].arqos;
  assign m_axi_g_param1_ARREGION = '0;
  assign m_axi_g_param1_ARUSER = '0;
  assign m_axi_g_param1_RREADY = rd_m[0].rready;
  assign m_axi_g_param1_BREADY = 1'b1;
  assign rd_s[0].arready = m_axi_g_param1_ARREADY;
  assign rd_s[0].rvalid = m_axi_g_param1_RVALID;
  assign rd_s[0].rdata = m_axi_g_param1_RDATA;
  assign rd_s[0].rlast = m_axi_g_param1_RLAST;
  assign rd_s[0].rid = m_axi_g_param1_RID;
  assign rd_s[0].rresp = m_axi_g_param1_RRESP;
  assign m_axi_g_param2_AWVALID = '0;
  assign m_axi_g_param2_AWADDR = '0;
  assign m_axi_g_param2_AWID = '0;
  assign m_axi_g_param2_AWLEN = '0;
  assign m_axi_g_param2_AWSIZE = '0;
  assign m_axi_g_param2_AWBURST = '0;
  assign m_axi_g_param2_AWLOCK = '0;
  assign m_axi_g_param2_AWCACHE = '0;
  assign m_axi_g_param2_AWPROT = '0;
  assign m_axi_g_param2_AWQOS = '0;
  assign m_axi_g_param2_AWREGION = '0;
  assign m_axi_g_param2_AWUSER = '0;
  assign m_axi_g_param2_WVALID = '0;
  assign m_axi_g_param2_WDATA = '0;
  assign m_axi_g_param2_WSTRB = '0;
  assign m_axi_g_param2_WLAST = '0;
  assign m_axi_g_param2_WUSER = '0;
  assign m_axi_g_param2_ARVALID = rd_m[1].arvalid;
  assign m_axi_g_param2_ARADDR = rd_m[1].araddr;
  assign m_axi_g_param2_ARID = rd_m[1].arid;
  assign m_axi_g_param2_ARLEN = rd_m[1].arlen;
  assign m_axi_g_param2_ARSIZE = rd_m[1].arsize;
  assign m_axi_g_param2_ARBURST = rd_m[1].arburst;
  assign m_axi_g_param2_ARLOCK = rd_m[1].arlock;
  assign m_axi_g_param2_ARCACHE = rd_m[1].arcache;
  assign m_axi_g_param2_ARPROT = rd_m[1].arprot;
  assign m_axi_g_param2_ARQOS = rd_m[1].arqos;
  assign m_axi_g_param2_ARREGION = '0;
  assign m_axi_g_param2_ARUSER = '0;
  assign m_axi_g_param2_RREADY = rd_m[1].rready;
  assign m_axi_g_param2_BREADY = 1'b1;
  assign rd_s[1].arready = m_axi_g_param2_ARREADY;
  assign rd_s[1].rvalid = m_axi_g_param2_RVALID;
  assign rd_s[1].rdata = m_axi_g_param2_RDATA;
  assign rd_s[1].rlast = m_axi_g_param2_RLAST;
  assign rd_s[1].rid = m_axi_g_param2_RID;
  assign rd_s[1].rresp = m_axi_g_param2_RRESP;
  assign m_axi_g_act_a_r_AWVALID = '0;
  assign m_axi_g_act_a_r_AWADDR = '0;
  assign m_axi_g_act_a_r_AWID = '0;
  assign m_axi_g_act_a_r_AWLEN = '0;
  assign m_axi_g_act_a_r_AWSIZE = '0;
  assign m_axi_g_act_a_r_AWBURST = '0;
  assign m_axi_g_act_a_r_AWLOCK = '0;
  assign m_axi_g_act_a_r_AWCACHE = '0;
  assign m_axi_g_act_a_r_AWPROT = '0;
  assign m_axi_g_act_a_r_AWQOS = '0;
  assign m_axi_g_act_a_r_AWREGION = '0;
  assign m_axi_g_act_a_r_AWUSER = '0;
  assign m_axi_g_act_a_r_WVALID = '0;
  assign m_axi_g_act_a_r_WDATA = '0;
  assign m_axi_g_act_a_r_WSTRB = '0;
  assign m_axi_g_act_a_r_WLAST = '0;
  assign m_axi_g_act_a_r_WUSER = '0;
  assign m_axi_g_act_a_r_ARVALID = rd_m[2].arvalid;
  assign m_axi_g_act_a_r_ARADDR = rd_m[2].araddr;
  assign m_axi_g_act_a_r_ARID = rd_m[2].arid;
  assign m_axi_g_act_a_r_ARLEN = rd_m[2].arlen;
  assign m_axi_g_act_a_r_ARSIZE = rd_m[2].arsize;
  assign m_axi_g_act_a_r_ARBURST = rd_m[2].arburst;
  assign m_axi_g_act_a_r_ARLOCK = rd_m[2].arlock;
  assign m_axi_g_act_a_r_ARCACHE = rd_m[2].arcache;
  assign m_axi_g_act_a_r_ARPROT = rd_m[2].arprot;
  assign m_axi_g_act_a_r_ARQOS = rd_m[2].arqos;
  assign m_axi_g_act_a_r_ARREGION = '0;
  assign m_axi_g_act_a_r_ARUSER = '0;
  assign m_axi_g_act_a_r_RREADY = rd_m[2].rready;
  assign m_axi_g_act_a_r_BREADY = 1'b1;
  assign rd_s[2].arready = m_axi_g_act_a_r_ARREADY;
  assign rd_s[2].rvalid = m_axi_g_act_a_r_RVALID;
  assign rd_s[2].rdata = m_axi_g_act_a_r_RDATA;
  assign rd_s[2].rlast = m_axi_g_act_a_r_RLAST;
  assign rd_s[2].rid = m_axi_g_act_a_r_RID;
  assign rd_s[2].rresp = m_axi_g_act_a_r_RRESP;
  assign m_axi_g_act_b_r_AWVALID = '0;
  assign m_axi_g_act_b_r_AWADDR = '0;
  assign m_axi_g_act_b_r_AWID = '0;
  assign m_axi_g_act_b_r_AWLEN = '0;
  assign m_axi_g_act_b_r_AWSIZE = '0;
  assign m_axi_g_act_b_r_AWBURST = '0;
  assign m_axi_g_act_b_r_AWLOCK = '0;
  assign m_axi_g_act_b_r_AWCACHE = '0;
  assign m_axi_g_act_b_r_AWPROT = '0;
  assign m_axi_g_act_b_r_AWQOS = '0;
  assign m_axi_g_act_b_r_AWREGION = '0;
  assign m_axi_g_act_b_r_AWUSER = '0;
  assign m_axi_g_act_b_r_WVALID = '0;
  assign m_axi_g_act_b_r_WDATA = '0;
  assign m_axi_g_act_b_r_WSTRB = '0;
  assign m_axi_g_act_b_r_WLAST = '0;
  assign m_axi_g_act_b_r_WUSER = '0;
  assign m_axi_g_act_b_r_ARVALID = rd_m[3].arvalid;
  assign m_axi_g_act_b_r_ARADDR = rd_m[3].araddr;
  assign m_axi_g_act_b_r_ARID = rd_m[3].arid;
  assign m_axi_g_act_b_r_ARLEN = rd_m[3].arlen;
  assign m_axi_g_act_b_r_ARSIZE = rd_m[3].arsize;
  assign m_axi_g_act_b_r_ARBURST = rd_m[3].arburst;
  assign m_axi_g_act_b_r_ARLOCK = rd_m[3].arlock;
  assign m_axi_g_act_b_r_ARCACHE = rd_m[3].arcache;
  assign m_axi_g_act_b_r_ARPROT = rd_m[3].arprot;
  assign m_axi_g_act_b_r_ARQOS = rd_m[3].arqos;
  assign m_axi_g_act_b_r_ARREGION = '0;
  assign m_axi_g_act_b_r_ARUSER = '0;
  assign m_axi_g_act_b_r_RREADY = rd_m[3].rready;
  assign m_axi_g_act_b_r_BREADY = 1'b1;
  assign rd_s[3].arready = m_axi_g_act_b_r_ARREADY;
  assign rd_s[3].rvalid = m_axi_g_act_b_r_RVALID;
  assign rd_s[3].rdata = m_axi_g_act_b_r_RDATA;
  assign rd_s[3].rlast = m_axi_g_act_b_r_RLAST;
  assign rd_s[3].rid = m_axi_g_act_b_r_RID;
  assign rd_s[3].rresp = m_axi_g_act_b_r_RRESP;
  assign m_axi_g_act_a_w_AWVALID = wr_m[0].awvalid;
  assign m_axi_g_act_a_w_AWADDR = wr_m[0].awaddr;
  assign m_axi_g_act_a_w_AWID = wr_m[0].awid;
  assign m_axi_g_act_a_w_AWLEN = wr_m[0].awlen;
  assign m_axi_g_act_a_w_AWSIZE = wr_m[0].awsize;
  assign m_axi_g_act_a_w_AWBURST = wr_m[0].awburst;
  assign m_axi_g_act_a_w_AWLOCK = wr_m[0].awlock;
  assign m_axi_g_act_a_w_AWCACHE = wr_m[0].awcache;
  assign m_axi_g_act_a_w_AWPROT = wr_m[0].awprot;
  assign m_axi_g_act_a_w_AWQOS = wr_m[0].awqos;
  assign m_axi_g_act_a_w_AWREGION = '0;
  assign m_axi_g_act_a_w_AWUSER = '0;
  assign m_axi_g_act_a_w_WVALID = wr_m[0].wvalid;
  assign m_axi_g_act_a_w_WDATA = wr_m[0].wdata;
  assign m_axi_g_act_a_w_WSTRB = wr_m[0].wstrb;
  assign m_axi_g_act_a_w_WLAST = wr_m[0].wlast;
  assign m_axi_g_act_a_w_WUSER = '0;
  assign m_axi_g_act_a_w_ARVALID = '0;
  assign m_axi_g_act_a_w_ARADDR = '0;
  assign m_axi_g_act_a_w_ARID = '0;
  assign m_axi_g_act_a_w_ARLEN = '0;
  assign m_axi_g_act_a_w_ARSIZE = '0;
  assign m_axi_g_act_a_w_ARBURST = '0;
  assign m_axi_g_act_a_w_ARLOCK = '0;
  assign m_axi_g_act_a_w_ARCACHE = '0;
  assign m_axi_g_act_a_w_ARPROT = '0;
  assign m_axi_g_act_a_w_ARQOS = '0;
  assign m_axi_g_act_a_w_ARREGION = '0;
  assign m_axi_g_act_a_w_ARUSER = '0;
  assign m_axi_g_act_a_w_RREADY = 1'b1;
  assign m_axi_g_act_a_w_BREADY = wr_m[0].bready;
  assign wr_s[0].awready = m_axi_g_act_a_w_AWREADY;
  assign wr_s[0].wready = m_axi_g_act_a_w_WREADY;
  assign wr_s[0].bvalid = m_axi_g_act_a_w_BVALID;
  assign wr_s[0].bresp = m_axi_g_act_a_w_BRESP;
  assign wr_s[0].bid = m_axi_g_act_a_w_BID;
  assign m_axi_g_act_b_w_AWVALID = wr_m[1].awvalid;
  assign m_axi_g_act_b_w_AWADDR = wr_m[1].awaddr;
  assign m_axi_g_act_b_w_AWID = wr_m[1].awid;
  assign m_axi_g_act_b_w_AWLEN = wr_m[1].awlen;
  assign m_axi_g_act_b_w_AWSIZE = wr_m[1].awsize;
  assign m_axi_g_act_b_w_AWBURST = wr_m[1].awburst;
  assign m_axi_g_act_b_w_AWLOCK = wr_m[1].awlock;
  assign m_axi_g_act_b_w_AWCACHE = wr_m[1].awcache;
  assign m_axi_g_act_b_w_AWPROT = wr_m[1].awprot;
  assign m_axi_g_act_b_w_AWQOS = wr_m[1].awqos;
  assign m_axi_g_act_b_w_AWREGION = '0;
  assign m_axi_g_act_b_w_AWUSER = '0;
  assign m_axi_g_act_b_w_WVALID = wr_m[1].wvalid;
  assign m_axi_g_act_b_w_WDATA = wr_m[1].wdata;
  assign m_axi_g_act_b_w_WSTRB = wr_m[1].wstrb;
  assign m_axi_g_act_b_w_WLAST = wr_m[1].wlast;
  assign m_axi_g_act_b_w_WUSER = '0;
  assign m_axi_g_act_b_w_ARVALID = '0;
  assign m_axi_g_act_b_w_ARADDR = '0;
  assign m_axi_g_act_b_w_ARID = '0;
  assign m_axi_g_act_b_w_ARLEN = '0;
  assign m_axi_g_act_b_w_ARSIZE = '0;
  assign m_axi_g_act_b_w_ARBURST = '0;
  assign m_axi_g_act_b_w_ARLOCK = '0;
  assign m_axi_g_act_b_w_ARCACHE = '0;
  assign m_axi_g_act_b_w_ARPROT = '0;
  assign m_axi_g_act_b_w_ARQOS = '0;
  assign m_axi_g_act_b_w_ARREGION = '0;
  assign m_axi_g_act_b_w_ARUSER = '0;
  assign m_axi_g_act_b_w_RREADY = 1'b1;
  assign m_axi_g_act_b_w_BREADY = wr_m[1].bready;
  assign wr_s[1].awready = m_axi_g_act_b_w_AWREADY;
  assign wr_s[1].wready = m_axi_g_act_b_w_WREADY;
  assign wr_s[1].bvalid = m_axi_g_act_b_w_BVALID;
  assign wr_s[1].bresp = m_axi_g_act_b_w_BRESP;
  assign wr_s[1].bid = m_axi_g_act_b_w_BID;
  cnn_rtl_top core (
    .ap_clk(ap_clk),
    .ap_rst_n(ap_rst_n),
    .pw_fast_clk(pw_fast_clk),
    .pw_fast_rst(pw_fast_rst),
    .ap_start(ap_start),
    .ap_done(ap_done),
    .ap_idle(ap_idle),
    .ap_ready(ap_ready),
    .protocol_error(protocol_error),
    .protocol_error_ap_vld(protocol_error_ap_vld),
    .trace_a_feed(trace_a_feed),
    .trace_a_dw3(trace_a_dw3),
    .trace_a_dw7(trace_a_dw7),
    .trace_a_pw1(trace_a_pw1),
    .trace_a_pw2(trace_a_pw2),
    .trace_a_write(trace_a_write),
    .trace_b_feed(trace_b_feed),
    .trace_b_dw3(trace_b_dw3),
    .trace_b_dw7(trace_b_dw7),
    .trace_b_pw1(trace_b_pw1),
    .trace_b_pw2(trace_b_pw2),
    .trace_b_write(trace_b_write),
    .s_axi_control_AWVALID(s_axi_control_AWVALID),
    .s_axi_control_AWREADY(s_axi_control_AWREADY),
    .s_axi_control_AWADDR(s_axi_control_AWADDR),
    .s_axi_control_WVALID(s_axi_control_WVALID),
    .s_axi_control_WREADY(s_axi_control_WREADY),
    .s_axi_control_WDATA(s_axi_control_WDATA),
    .s_axi_control_WSTRB(s_axi_control_WSTRB),
    .s_axi_control_BVALID(s_axi_control_BVALID),
    .s_axi_control_BREADY(s_axi_control_BREADY),
    .s_axi_control_BRESP(s_axi_control_BRESP),
    .s_axi_control_ARVALID(s_axi_control_ARVALID),
    .s_axi_control_ARREADY(s_axi_control_ARREADY),
    .s_axi_control_ARADDR(s_axi_control_ARADDR),
    .s_axi_control_RVALID(s_axi_control_RVALID),
    .s_axi_control_RREADY(s_axi_control_RREADY),
    .s_axi_control_RDATA(s_axi_control_RDATA),
    .s_axi_control_RRESP(s_axi_control_RRESP),
    .rd_m(rd_m), .rd_s(rd_s), .wr_m(wr_m), .wr_s(wr_s)
  );
endmodule

