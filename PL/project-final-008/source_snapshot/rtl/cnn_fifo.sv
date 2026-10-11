module cnn_fifo #(parameter int WIDTH=16, DEPTH=16)(
  input logic clk,rst,s_valid, output logic s_ready,
  input logic [WIDTH-1:0] s_data, output logic m_valid,
  input logic m_ready, output logic [WIDTH-1:0] m_data,
  output logic [$clog2(DEPTH+1)-1:0] level
);
  localparam int PW = (DEPTH>1)?$clog2(DEPTH):1;
  logic [WIDTH-1:0] ram_data,bypass_data;
  logic from_memory;
  logic [PW-1:0] rd_ptr,wr_ptr;
  logic [$clog2(DEPTH+1)-1:0] count;
  logic push,pop,refill,bypass,store,read_mem;
  assign level = count + m_valid;
  assign pop = m_valid && m_ready;
  assign s_ready = level < DEPTH || pop;
  assign push = s_valid && s_ready;
  assign refill = !m_valid || pop;
  assign read_mem = refill && count!=0;
  assign bypass = refill && count==0 && push;
  assign store = push && !bypass;
  assign m_data = from_memory ? ram_data : bypass_data;
  if(DEPTH>=128) begin: block_storage
    (* ram_style="block" *) logic [WIDTH-1:0] mem[DEPTH];
    always_ff @(posedge clk) begin
      if(!rst && store) mem[wr_ptr]<=s_data;
      if(!rst && read_mem) ram_data<=mem[rd_ptr];
    end
  end else begin: distributed_storage
    (* ram_style="distributed" *) logic [WIDTH-1:0] mem[DEPTH];
    always_ff @(posedge clk) begin
      if(!rst && store) mem[wr_ptr]<=s_data;
      if(!rst && read_mem) ram_data<=mem[rd_ptr];
    end
  end
  always_ff @(posedge clk) begin
    if (rst) begin
      rd_ptr<='0;wr_ptr<='0;count<='0;m_valid<=0;
    end else begin
      if (refill) begin
        m_valid <= read_mem || bypass;
        if(read_mem) from_memory<=1;
        else if(bypass) begin from_memory<=0;bypass_data<=s_data;end
      end
      if (store) begin
        wr_ptr <= wr_ptr==DEPTH-1 ? '0 : wr_ptr+1'b1;
      end
      if (read_mem) rd_ptr <= rd_ptr==DEPTH-1 ? '0 : rd_ptr+1'b1;
      case ({store,read_mem})
        2'b10: count<=count+1'b1;
        2'b01: count<=count-1'b1;
        default: count<=count;
      endcase
    end
  end
endmodule
