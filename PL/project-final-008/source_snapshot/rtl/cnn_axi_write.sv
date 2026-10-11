// AW and W progress independently. Commit follows every B response, including split pieces.
module cnn_axi_write #(parameter int ID_WIDTH=1)(
input logic clk, rst,
 input logic [63:0] base_addr,
 input logic cmd_valid, output logic cmd_ready,
 input logic [31:0] cmd_addr, input logic [5:0] cmd_words,
 output logic [31:0] error, output logic idle,
 input logic data_valid, output logic data_ready, input logic [127:0] data,
 output logic commit_valid, input logic commit_ready,
 output logic [ID_WIDTH-1:0] m_axi_awid, output logic [63:0] m_axi_awaddr,
 output logic [7:0] m_axi_awlen, output logic [2:0] m_axi_awsize,
 output logic [1:0] m_axi_awburst, output logic m_axi_awlock,
 output logic [3:0] m_axi_awcache, output logic [2:0] m_axi_awprot,
 output logic [3:0] m_axi_awqos, output logic m_axi_awvalid, input logic m_axi_awready,
 output logic [127:0] m_axi_wdata, output logic [15:0] m_axi_wstrb,
 output logic m_axi_wlast,m_axi_wvalid, input logic m_axi_wready,
 input logic [ID_WIDTH-1:0] m_axi_bid, input logic [1:0] m_axi_bresp,
 input logic m_axi_bvalid, output logic m_axi_bready);
 typedef enum logic [1:0] {S_IDLE,S_SEND,S_B,S_COMMIT} state_t;
 state_t state;
 logic [63:0] addr,incoming_addr;
 logic [5:0] remaining,beat,piece;
 logic [8:0] boundary_words;
 logic aw_done,w_done;
 assign incoming_addr=base_addr+{28'b0,cmd_addr,4'b0};
 assign boundary_words=9'd256-{1'b0,addr[11:4]};
 assign piece=(boundary_words < {3'b0,remaining}) ? boundary_words[5:0] : remaining;
 assign idle=state==S_IDLE; assign cmd_ready=idle;
 assign m_axi_awid='0;assign m_axi_awaddr=addr;assign m_axi_awlen={2'b0,piece}-8'd1;
 assign m_axi_awsize=3'd4;assign m_axi_awburst=2'b01;assign m_axi_awlock=0;
 assign m_axi_awcache=4'b0011;assign m_axi_awprot=0;assign m_axi_awqos=0;
 assign m_axi_awvalid=state==S_SEND && !aw_done;
 assign m_axi_wvalid=state==S_SEND && !w_done && data_valid;
 assign data_ready=state==S_SEND && !w_done && m_axi_wready;
 assign m_axi_wdata=data;assign m_axi_wstrb=16'hffff;assign m_axi_wlast=beat==piece-1'b1;
 assign m_axi_bready=state==S_B;
 assign commit_valid=state==S_COMMIT;
 always_ff @(posedge clk) begin
  if(rst) begin state<=S_IDLE;addr<=0;remaining<=0;beat<=0;aw_done<=0;w_done<=0;error<=0;end
  else unique case(state)
   S_IDLE: if(cmd_valid) begin
    addr<={incoming_addr[63:4],4'b0};remaining<=(cmd_words>=1 && cmd_words<=32)?cmd_words:6'd1;
    if(incoming_addr[3:0]!=0 || cmd_words==0 || cmd_words>32) error[0]<=1;
    aw_done<=0;w_done<=0;beat<=0;state<=S_SEND;
   end
   S_SEND: begin
    if(m_axi_awvalid && m_axi_awready) aw_done<=1;
    if(m_axi_wvalid && m_axi_wready) begin
     beat<=beat+1'b1;
     if(m_axi_wlast) w_done<=1;
    end
    if((aw_done || (m_axi_awvalid && m_axi_awready)) &&
       (w_done || (m_axi_wvalid && m_axi_wready && m_axi_wlast))) state<=S_B;
   end
   S_B: if(m_axi_bvalid) begin
    if(m_axi_bresp!=0) error[1]<=1;
    if(m_axi_bid!=0) error[3]<=1;
    if(remaining==piece) state<=S_COMMIT;
    else begin
     addr<=addr+({58'b0,piece}<<4);remaining<=remaining-piece;
     aw_done<=0;w_done<=0;beat<=0;state<=S_SEND;
    end
   end
   S_COMMIT: if(commit_ready) state<=S_IDLE;
   default:state<=S_IDLE;
  endcase
 end
endmodule
