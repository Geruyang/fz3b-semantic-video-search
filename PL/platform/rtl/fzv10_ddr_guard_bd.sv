`timescale 1ns/1ps

module fzv10_ddr_guard_bd #(
    parameter logic [31:0] ID_VALUE          = 32'h465a5641,
    parameter logic [31:0] ABI_VERSION_VALUE = 32'h000a0004,
    parameter logic [31:0] CAPS_VALUE        = 32'h000007ff,
    parameter int unsigned RESET_CYCLES      = 32
) (
    (* X_INTERFACE_INFO="xilinx.com:signal:clock:1.0 CLK CLK", X_INTERFACE_PARAMETER="XIL_INTERFACENAME CLK, ASSOCIATED_BUSIF S_AXI, ASSOCIATED_RESET rst" *) input logic clk,
    (* X_INTERFACE_INFO="xilinx.com:signal:reset:1.0 RST RST", X_INTERFACE_PARAMETER="XIL_INTERFACENAME RST, POLARITY ACTIVE_HIGH" *) input logic rst,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI AWADDR", X_INTERFACE_PARAMETER="XIL_INTERFACENAME S_AXI, PROTOCOL AXI4LITE, DATA_WIDTH 32, ADDR_WIDTH 40, READ_WRITE_MODE READ_WRITE, HAS_BURST 0, HAS_LOCK 0, HAS_CACHE 0, HAS_QOS 0, HAS_REGION 0, HAS_PROT 1" *) input logic [39:0] s_awaddr,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI AWPROT" *) input logic [2:0] s_awprot,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI AWVALID" *) input logic s_awvalid,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI AWREADY" *) output logic s_awready,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI WDATA" *) input logic [31:0] s_wdata,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI WSTRB" *) input logic [3:0] s_wstrb,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI WVALID" *) input logic s_wvalid,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI WREADY" *) output logic s_wready,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI BRESP" *) output logic [1:0] s_bresp,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI BVALID" *) output logic s_bvalid,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI BREADY" *) input logic s_bready,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI ARADDR" *) input logic [39:0] s_araddr,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI ARPROT" *) input logic [2:0] s_arprot,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI ARVALID" *) input logic s_arvalid,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI ARREADY" *) output logic s_arready,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI RDATA" *) output logic [31:0] s_rdata,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI RRESP" *) output logic [1:0] s_rresp,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI RVALID" *) output logic s_rvalid,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI RREADY" *) input logic s_rready,

    input logic [5:0] shutdown_ack,
    input logic [5:0] shutdown_rd_ack,
    input logic [5:0] shutdown_wr_ack,
    output logic [5:0] shutdown_request,
    input logic down_ar_fire,
    input logic [1:0] down_rresp,
    input logic down_r_fire,
    input logic down_rlast_fire,
    input logic down_aw_fire,
    input logic down_wlast_fire,
    input logic [1:0] down_bresp,
    input logic down_b_fire,
    input logic hls_ap_idle,
    input logic hls_ap_done,
    input logic hls_ap_ready,
    input logic [31:0] hls_protocol_error,
    input logic hls_protocol_error_ap_vld,
    (* X_INTERFACE_INFO="xilinx.com:signal:reset:1.0 CORE_RESET_FEEDBACK_ARESETN RST", X_INTERFACE_PARAMETER="XIL_INTERFACENAME CORE_RESET_FEEDBACK_ARESETN, POLARITY ACTIVE_LOW" *) input logic core_reset_feedback_aresetn,
    output logic hls_ap_start,
    (* X_INTERFACE_INFO="xilinx.com:signal:reset:1.0 CORE_RESET_REQ RST", X_INTERFACE_PARAMETER="XIL_INTERFACENAME CORE_RESET_REQ, POLARITY ACTIVE_HIGH" *) output logic core_reset_req,
    output logic safe_to_reset,
    output logic poisoned,
    output logic [31:0] debug_status,
    output logic [31:0] debug_error_flags
);
    logic [15:0] awlocal;
    logic [15:0] arlocal;
    logic unused_prot;
    assign awlocal = (s_awaddr[39:16] == 24'h00a401) ? s_awaddr[15:0] : 16'hfffc;
    assign arlocal = (s_araddr[39:16] == 24'h00a401) ? s_araddr[15:0] : 16'hfffc;
    assign unused_prot = ^{s_awprot, s_arprot};

    fzv10_ddr_guard #(.ID_VALUE(ID_VALUE), .ABI_VERSION_VALUE(ABI_VERSION_VALUE),
                     .CAPS_VALUE(CAPS_VALUE), .RESET_CYCLES(RESET_CYCLES)) u_guard (
        .clk, .rst, .s_awaddr(awlocal), .s_awvalid, .s_awready,
        .s_wdata, .s_wstrb, .s_wvalid, .s_wready, .s_bresp, .s_bvalid, .s_bready,
        .s_araddr(arlocal), .s_arvalid, .s_arready, .s_rdata, .s_rresp,
        .s_rvalid, .s_rready, .shutdown_ack, .shutdown_rd_ack, .shutdown_wr_ack,
        .shutdown_request, .down_ar_fire, .down_rresp, .down_r_fire,
        .down_rlast_fire, .down_aw_fire, .down_wlast_fire, .down_bresp,
        .down_b_fire, .hls_ap_idle, .hls_ap_done, .hls_ap_ready,
        .hls_protocol_error, .hls_protocol_error_ap_vld,
        .core_reset_feedback_aresetn, .hls_ap_start, .core_reset_req,
        .safe_to_reset, .poisoned, .debug_status, .debug_error_flags
    );
endmodule
