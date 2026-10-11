// Handwritten transport: one command owner, full32-word response reservation.
module cnn_axi_read #(parameter int ID_WIDTH=1)(
input logic clk, rst,
 input logic [63:0] base_addr,
 input logic cmd_valid, output logic cmd_ready,
 input logic [31:0] cmd_addr, input logic [5:0] cmd_words,
 output logic [31:0] error, output logic idle,
 output logic data_valid, input logic data_ready, output logic [127:0] data,
 output logic [ID_WIDTH-1:0] m_axi_arid, output logic [63:0] m_axi_araddr,
 output logic [7:0] m_axi_arlen, output logic [2:0] m_axi_arsize,
 output logic [1:0] m_axi_arburst, output logic m_axi_arlock,
 output logic [3:0] m_axi_arcache, output logic [2:0] m_axi_arprot,
 output logic [3:0] m_axi_arqos, output logic m_axi_arvalid, input logic m_axi_arready,
 input logic [ID_WIDTH-1:0] m_axi_rid, input logic [127:0] m_axi_rdata,
 input logic [1:0] m_axi_rresp, input logic m_axi_rlast, m_axi_rvalid,
 output logic m_axi_rready);
 typedef enum logic [2:0] {S_IDLE,S_AR,S_DATA,S_PAD,S_DRAIN} state_t;
 state_t state;
 logic [63:0] addr;
 logic [5:0] remaining, burst_words, beat;
 logic [8:0] boundary_words;
 logic [5:0] piece;
 logic [63:0] incoming_addr;
 logic rx_push,rx_ready;
 logic[127:0] rx_input;
 logic[5:0] rx_level;
 cnn_fifo #(.WIDTH(128),.DEPTH(32)) response_fifo(
  .clk(clk),.rst(rst),.s_valid(rx_push),.s_ready(rx_ready),.s_data(rx_input),
  .m_valid(data_valid),.m_ready(data_ready),.m_data(data),.level(rx_level)
 );
 assign incoming_addr=base_addr+{28'b0,cmd_addr,4'b0};
 assign boundary_words=9'd256-{1'b0,addr[11:4]};
 assign piece=(boundary_words < {3'b0,remaining}) ? boundary_words[5:0] : remaining;
 assign idle=(state==S_IDLE) && rx_level==0;
 assign cmd_ready=idle;
 assign m_axi_arid='0; assign m_axi_araddr=addr;
 assign m_axi_arlen={2'b0,piece}-8'd1;
 assign m_axi_arsize=3'd4; assign m_axi_arburst=2'b01;
 assign m_axi_arlock=0; assign m_axi_arcache=4'b0011;
 assign m_axi_arprot=0; assign m_axi_arqos=0;
 assign m_axi_arvalid=state==S_AR;
 assign rx_push=(state==S_DATA && m_axi_rvalid)||(state==S_PAD);
 assign rx_input=state==S_PAD ? 128'b0 : m_axi_rdata;
 assign m_axi_rready=(state==S_DATA && rx_ready)||(state==S_DRAIN);
 task automatic advance_piece;
 begin
  remaining<=remaining-burst_words;
  addr<=addr+({58'b0,burst_words}<<4);
  if(remaining==burst_words) state<=S_IDLE; else state<=S_AR;
 end
 endtask
 always_ff @(posedge clk) begin
  if(rst) begin state<=S_IDLE; error<=0; addr<=0; remaining<=0;burst_words<=0;beat<=0; end
  else unique case(state)
   S_IDLE: if(cmd_valid && cmd_ready) begin
    addr<={incoming_addr[63:4],4'b0};
    remaining<=(cmd_words>=1 && cmd_words<=32)?cmd_words:6'd1;
    if(incoming_addr[3:0]!=0 || cmd_words==0 || cmd_words>32) error[0]<=1;
    state<=S_AR;
   end
   S_AR: if(m_axi_arready) begin burst_words<=piece;beat<=0;state<=S_DATA;end
   S_DATA: if(m_axi_rvalid && m_axi_rready) begin
    if(m_axi_rresp!=0) error[1]<=1;
    if(m_axi_rid!=0) error[3]<=1;
    beat<=beat+1'b1;
    if(m_axi_rlast!=(beat==burst_words-1'b1)) error[2]<=1;
    if(m_axi_rlast && beat!=burst_words-1'b1) state<=S_PAD;
    else if(beat==burst_words-1'b1) begin
     if(m_axi_rlast) advance_piece(); else state<=S_DRAIN;
    end
   end
   S_PAD: if(rx_ready) begin
    beat<=beat+1'b1;
    if(beat==burst_words-1'b1) advance_piece();
   end
   S_DRAIN: if(m_axi_rvalid) begin
    if(m_axi_rresp!=0) error[1]<=1;
    if(m_axi_rlast) advance_piece();
   end
   default: state<=S_IDLE;
  endcase
 end
endmodule
