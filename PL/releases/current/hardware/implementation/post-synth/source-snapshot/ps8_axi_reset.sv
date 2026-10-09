`timescale 1ns/1ps
module ps8_axi_reset (
    (* X_INTERFACE_INFO="xilinx.com:signal:clock:1.0 CLK CLK", X_INTERFACE_PARAMETER="XIL_INTERFACENAME CLK, ASSOCIATED_RESET rst:aresetn" *) input logic clk,
    input logic ps_resetn,
    (* X_INTERFACE_INFO="xilinx.com:signal:reset:1.0 RST RST", X_INTERFACE_PARAMETER="XIL_INTERFACENAME RST, POLARITY ACTIVE_HIGH" *) output logic rst,
    (* X_INTERFACE_INFO="xilinx.com:signal:reset:1.0 ARESETN RST", X_INTERFACE_PARAMETER="XIL_INTERFACENAME ARESETN, POLARITY ACTIVE_LOW" *) output logic aresetn,
    output logic [31:0] heartbeat
);
    logic eos, release_request;
    (* ASYNC_REG="TRUE",SHREG_EXTRACT="NO" *) logic [1:0] release_sync=0;
    STARTUPE3 #(.PROG_USR("FALSE"),.SIM_CCLK_FREQ(0.0)) startup(
        .CFGCLK(),.CFGMCLK(),.DI(),.EOS(eos),.PREQ(),
        .DO(4'b0),.DTS(4'hf),.FCSBO(1'b1),.FCSBTS(1'b1),
        .GSR(1'b0),.GTS(1'b0),.KEYCLEARB(1'b1),.PACK(1'b0),
        .USRCCLKO(1'b0),.USRCCLKTS(1'b1),.USRDONEO(1'b1),.USRDONETS(1'b1));
    assign release_request=eos && ps_resetn;
    always_ff @(posedge clk or negedge release_request) begin
        if(!release_request) release_sync<=0;
        else release_sync<={release_sync[0],1'b1};
    end
    assign aresetn=release_sync[1];
    assign rst=~release_sync[1];
    always_ff @(posedge clk) begin
        if(rst) heartbeat<=0;
        else heartbeat<=heartbeat+1'b1;
    end
endmodule
