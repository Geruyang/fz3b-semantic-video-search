// Handwritten parameter prefetch: four-tile capacity, one reserved DDR command.
// Relative addresses are128-bit word offsets. No memory arrays reset at row start.
module cnn_tile_loader(
 input logic clk,rst,start,output logic busy,done,
 input logic[31:0] base_addr,input logic[15:0] tile_count,
 output logic cmd_valid,input logic cmd_ready,
 output logic[31:0] cmd_addr,output logic[5:0] cmd_words,
 input logic data_valid,output logic data_ready,input logic[127:0] data,
 output logic out_valid,input logic out_ready,output logic[1023:0] out_data
);
 logic[31:0] base;
 logic[15:0] total_tiles,requested_tiles,consumed_tiles;
 logic[15:0] remaining_tiles;
 logic[2:0] batch_needed,command_tiles,word_index,fifo_level;
 logic[5:0] words_left;
 logic burst_active,fifo_push,fifo_ready;
 logic[895:0] partial_tile;
 logic[1023:0] fifo_input;
 assign remaining_tiles=total_tiles-requested_tiles;
 assign batch_needed=remaining_tiles>=16'd4 ? 3'd4 : remaining_tiles[2:0];
 assign data_ready=busy && burst_active && (word_index!=3'd7 || fifo_ready);
 assign fifo_push=busy && burst_active && data_valid && word_index==3'd7;
 // Incoming final word belongs above the seven already accepted words.
 assign fifo_input={data,partial_tile};
 cnn_fifo #(.WIDTH(1024),.DEPTH(4)) tile_fifo(
  .clk(clk),.rst(rst),.s_valid(fifo_push),.s_ready(fifo_ready),.s_data(fifo_input),
  .m_valid(out_valid),.m_ready(out_ready),.m_data(out_data),.level(fifo_level)
 );
 // Constant word banks avoid a wide variable-select feedback network.
 for(genvar bank=0;bank<7;bank++)begin: assembly_words
  logic[127:0] stored_word;
  always_ff @(posedge clk)begin
   if(!rst && data_valid && data_ready && word_index==3'(bank))stored_word<=data;
  end
  assign partial_tile[bank*128+:128]=stored_word;
 end
 always_ff @(posedge clk)begin
  if(rst)begin
   busy<=0;done<=0;cmd_valid<=0;cmd_addr<=0;cmd_words<=0;
   base<=0;total_tiles<=0;requested_tiles<=0;consumed_tiles<=0;
   command_tiles<=0;word_index<=0;words_left<=0;burst_active<=0;
  end else begin
   done<=0;
   if(start && !busy)begin
    base<=base_addr;total_tiles<=tile_count;requested_tiles<=0;consumed_tiles<=0;
    busy<=1;cmd_valid<=0;burst_active<=0;word_index<=0;words_left<=0;
   end else if(busy)begin
    // Plan maximal four-tile batches; only the final batch may be smaller.
    // The whole batch fits before VALID is asserted. While it stalls, the FIFO
    // can only drain; ownership prevents a second burst from consuming capacity.
    if(!cmd_valid && !burst_active && requested_tiles<total_tiles && fifo_level<=3'd4-batch_needed)begin
     cmd_valid<=1;cmd_addr<=base+{13'b0,requested_tiles,3'b0};
     cmd_words<={batch_needed,3'b0};command_tiles<=batch_needed;
    end
    if(cmd_valid && cmd_ready)begin
     cmd_valid<=0;burst_active<=1;word_index<=0;words_left<=cmd_words;
     requested_tiles<=requested_tiles+{13'b0,command_tiles};
    end
    if(data_valid && data_ready)begin
     word_index<=word_index+1'b1;words_left<=words_left-1'b1;
     if(words_left==6'd1)burst_active<=0;
    end
    if(out_valid && out_ready)consumed_tiles<=consumed_tiles+1'b1;
    if(!cmd_valid && !burst_active && requested_tiles==total_tiles && consumed_tiles==total_tiles && fifo_level==0)begin
     busy<=0;done<=1;
    end
   end
  end
 end
endmodule
