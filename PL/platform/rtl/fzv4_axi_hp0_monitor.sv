`timescale 1ns/1ps

// Passive monitor on the single SmartConnect-to-HP0 AXI net.  It has no path
// state and cannot alter READY/VALID or address/data signals.
module fzv4_axi_hp0_monitor (
    (* X_INTERFACE_INFO="xilinx.com:signal:clock:1.0 clk CLK", X_INTERFACE_PARAMETER="XIL_INTERFACENAME clk, ASSOCIATED_BUSIF MON_AXI, ASSOCIATED_RESET resetn" *) input logic clk,
    (* X_INTERFACE_INFO="xilinx.com:signal:reset:1.0 resetn RST", X_INTERFACE_PARAMETER="XIL_INTERFACENAME resetn, POLARITY ACTIVE_LOW" *) input logic resetn,
    (* X_INTERFACE_MODE="Monitor", X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 MON_AXI AWADDR", X_INTERFACE_PARAMETER="XIL_INTERFACENAME MON_AXI, PROTOCOL AXI4, DATA_WIDTH 64, ADDR_WIDTH 49, ID_WIDTH 6, AWUSER_WIDTH 1, ARUSER_WIDTH 1, READ_WRITE_MODE READ_WRITE, HAS_BURST 1, HAS_LOCK 1, HAS_CACHE 1, HAS_QOS 1, HAS_REGION 0, HAS_PROT 1, HAS_WSTRB 1, MAX_BURST_LENGTH 256" *) input logic [48:0] mon_axi_awaddr,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 MON_AXI AWID" *) input logic [5:0] mon_axi_awid,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 MON_AXI AWLEN" *) input logic [7:0] mon_axi_awlen,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 MON_AXI AWSIZE" *) input logic [2:0] mon_axi_awsize,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 MON_AXI AWBURST" *) input logic [1:0] mon_axi_awburst,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 MON_AXI AWLOCK" *) input logic mon_axi_awlock,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 MON_AXI AWCACHE" *) input logic [3:0] mon_axi_awcache,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 MON_AXI AWPROT" *) input logic [2:0] mon_axi_awprot,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 MON_AXI AWQOS" *) input logic [3:0] mon_axi_awqos,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 MON_AXI AWUSER" *) input logic mon_axi_awuser,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 MON_AXI AWVALID" *) input logic mon_axi_awvalid,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 MON_AXI AWREADY" *) input logic mon_axi_awready,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 MON_AXI WDATA" *) input logic [63:0] mon_axi_wdata,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 MON_AXI WSTRB" *) input logic [7:0] mon_axi_wstrb,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 MON_AXI WLAST" *) input logic mon_axi_wlast,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 MON_AXI WVALID" *) input logic mon_axi_wvalid,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 MON_AXI WREADY" *) input logic mon_axi_wready,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 MON_AXI BID" *) input logic [5:0] mon_axi_bid,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 MON_AXI BRESP" *) input logic [1:0] mon_axi_bresp,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 MON_AXI BVALID" *) input logic mon_axi_bvalid,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 MON_AXI BREADY" *) input logic mon_axi_bready,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 MON_AXI ARADDR" *) input logic [48:0] mon_axi_araddr,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 MON_AXI ARID" *) input logic [5:0] mon_axi_arid,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 MON_AXI ARLEN" *) input logic [7:0] mon_axi_arlen,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 MON_AXI ARSIZE" *) input logic [2:0] mon_axi_arsize,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 MON_AXI ARBURST" *) input logic [1:0] mon_axi_arburst,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 MON_AXI ARLOCK" *) input logic mon_axi_arlock,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 MON_AXI ARCACHE" *) input logic [3:0] mon_axi_arcache,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 MON_AXI ARPROT" *) input logic [2:0] mon_axi_arprot,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 MON_AXI ARQOS" *) input logic [3:0] mon_axi_arqos,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 MON_AXI ARUSER" *) input logic mon_axi_aruser,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 MON_AXI ARVALID" *) input logic mon_axi_arvalid,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 MON_AXI ARREADY" *) input logic mon_axi_arready,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 MON_AXI RID" *) input logic [5:0] mon_axi_rid,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 MON_AXI RDATA" *) input logic [63:0] mon_axi_rdata,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 MON_AXI RRESP" *) input logic [1:0] mon_axi_rresp,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 MON_AXI RLAST" *) input logic mon_axi_rlast,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 MON_AXI RVALID" *) input logic mon_axi_rvalid,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 MON_AXI RREADY" *) input logic mon_axi_rready,
    output logic down_ar_fire,
    output logic down_r_fire,
    output logic down_rlast_fire,
    output logic [1:0] down_rresp,
    output logic down_aw_fire,
    output logic down_wlast_fire,
    output logic down_b_fire,
    output logic [1:0] down_bresp
);
    assign down_ar_fire = mon_axi_arvalid && mon_axi_arready;
    assign down_r_fire = mon_axi_rvalid && mon_axi_rready;
    assign down_rlast_fire = mon_axi_rvalid && mon_axi_rready && mon_axi_rlast;
    assign down_rresp = mon_axi_rresp;
    assign down_aw_fire = mon_axi_awvalid && mon_axi_awready;
    assign down_wlast_fire = mon_axi_wvalid && mon_axi_wready && mon_axi_wlast;
    assign down_b_fire = mon_axi_bvalid && mon_axi_bready;
    assign down_bresp = mon_axi_bresp;
    logic unused;
    assign unused = clk ^ resetn ^ ^{mon_axi_awaddr,mon_axi_awid,mon_axi_awlen,mon_axi_awsize,
        mon_axi_awburst,mon_axi_awlock,mon_axi_awcache,mon_axi_awprot,mon_axi_awqos,mon_axi_awuser,
        mon_axi_wdata,mon_axi_wstrb,mon_axi_bid,mon_axi_araddr,mon_axi_arid,mon_axi_arlen,
        mon_axi_arsize,mon_axi_arburst,mon_axi_arlock,mon_axi_arcache,mon_axi_arprot,
        mon_axi_arqos,mon_axi_aruser,mon_axi_rid,mon_axi_rdata};
endmodule
