// A producer's B-committed row must match the exact preceding block epoch.
module cnn_row_guard(
 input logic clk,rst,job_start,
 input logic [1:0] profile,input logic [31:0] slot_words,
 input logic [4:0] feed_block_index,input logic [31:0] feed_cmd_addr,
 input logic row_commit_valid,input logic [5:0] row_commit_index,
 input logic [4:0] writer_block_index,
 output logic can_read
);
 (* ram_style="distributed" *) logic [4:0] row_epoch[128];
 logic [127:0] row_valid;
 logic [31:0] relative_addr;
 logic [6:0] read_index,write_index;
 assign relative_addr=feed_cmd_addr-(feed_block_index[0]?slot_words:32'd0);
 assign read_index={feed_block_index[0],relative_addr[14:9]};
 assign write_index={!writer_block_index[0],row_commit_index};
 assign can_read=profile==3 || feed_block_index==0 ||
  (row_valid[read_index] && row_epoch[read_index]==feed_block_index-5'd1);
 always_ff @(posedge clk)begin
  if(rst||job_start)row_valid<=0;
  else if(row_commit_valid)row_valid[write_index]<=1;
  if(!rst&&!job_start&&row_commit_valid)row_epoch[write_index]<=writer_block_index;
 end
endmodule
