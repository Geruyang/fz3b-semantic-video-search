// Two burst buffers and four in-order scratch ownership credits.
module cnn_residual_store(input logic clk,rst,start,input logic [1:0] profile,transition_stage,input logic [4:0] block_index,input logic [31:0] slot_words,output logic busy,done,output logic [31:0] trace,input logic in_valid,output logic in_ready,input logic signed [15:0] in_data,output logic cmd_valid,input logic cmd_ready,output logic [31:0] cmd_addr,output logic [5:0] cmd_words,output logic data_valid,input logic data_ready,output logic [127:0] data,input logic commit_valid,output logic commit_ready,output logic ready_valid,input logic ready_ready,output logic [31:0] ready_token,input logic release_valid,output logic release_ready);
 typedef enum logic [2:0] {WAIT,CMD,SEND,COMMIT,TOKEN,DRAIN} state_t;state_t state;
 logic [1:0] full;logic fb,sb,allocated;
 logic [4:0] wr,rd,fill_burst,send_burst;logic [2:0] lane,credits,published;
 logic [6:0] pairs,fill_pair,send_pair;logic [31:0] base,sequence_number;
 wire take_release=release_valid&&release_ready;
 wire allocate=busy&&!allocated&&fill_pair<pairs&&credits<4;
 wire publish=ready_valid&&ready_ready;
 wire token_push_ready,token_valid;
 wire [31:0] token_data;
 wire [2:0] token_level;
 // Four committed chunks may wait for PW2 without stopping DDR production.
 // published counts only tokens actually accepted by PW2, so an early release
 // cannot free a queued-but-unseen chunk.
 cnn_fifo #(.WIDTH(32),.DEPTH(4)) committed_tokens(
  .clk(clk),.rst(rst||(start&&!busy)),
  .s_valid(busy&&state==TOKEN),.s_ready(token_push_ready),.s_data(sequence_number),
  .m_valid(token_valid),.m_ready(busy&&ready_ready),.m_data(token_data),.level(token_level));
 generate for(genvar pixel_lane=0;pixel_lane<8;pixel_lane++)begin: pixel_banks
  (* ram_style="distributed" *)logic [15:0] mem[0:63];
  always_ff @(posedge clk)if(!rst&&in_valid&&in_ready&&lane==pixel_lane)mem[{fb,wr}]<=in_data;
  assign data[pixel_lane*16+:16]=mem[{sb,rd}];
 end endgenerate
 assign in_ready=busy&&allocated&&!full[fb];assign cmd_valid=busy&&state==CMD;assign cmd_words=32;
 assign cmd_addr=base+{sequence_number[1:0],10'b0}+{send_burst,5'b0};assign data_valid=busy&&state==SEND;assign commit_ready=busy&&state==COMMIT;
 assign ready_valid=busy&&token_valid;assign ready_token=token_data;assign release_ready=busy&&published!=0;assign trace=busy?32'h80000000|sequence_number:0;
 always_ff @(posedge clk)begin
  if(rst)begin busy<=0;done<=0;state<=WAIT;full<=0;fb<=0;sb<=0;allocated<=0;wr<=0;rd<=0;fill_burst<=0;send_burst<=0;lane<=0;credits<=0;published<=0;pairs<=0;fill_pair<=0;send_pair<=0;base<=0;sequence_number<=0;end
  else begin done<=0;
   if(start&&!busy)begin
    if(transition_stage!=0)done<=1;
    else begin busy<=1;state<=WAIT;full<=0;fb<=0;sb<=0;allocated<=0;wr<=0;rd<=0;fill_burst<=0;send_burst<=0;lane<=0;credits<=0;published<=0;pairs<=profile==0?16:profile==1?8:32;fill_pair<=0;send_pair<=0;base<=slot_words<<1;sequence_number<=block_index*(profile==0?16:profile==1?8:32);end
   end else if(busy)begin
    case({allocate,take_release})2'b10:credits<=credits+1;2'b01:credits<=credits-1;default:;endcase
    case({publish,take_release})2'b10:published<=published+1;2'b01:published<=published-1;default:;endcase
    if(allocate)allocated<=1;
    if(in_valid&&in_ready)begin
     if(lane==7)begin lane<=0;if(wr==31)begin wr<=0;full[fb]<=1;fb<=!fb;
      if(fill_burst==31)begin fill_burst<=0;fill_pair<=fill_pair+1;allocated<=0;end else fill_burst<=fill_burst+1;
     end else wr<=wr+1;end else lane<=lane+1;
    end
    case(state)
     WAIT:if(full[sb])begin rd<=0;state<=CMD;end
     CMD:if(cmd_ready)state<=SEND;
     SEND:if(data_ready)begin if(rd==31)state<=COMMIT;else rd<=rd+1;end
     COMMIT:if(commit_valid)begin full[sb]<=0;sb<=!sb;if(send_burst==31)state<=TOKEN;else begin send_burst<=send_burst+1;state<=WAIT;end end
     TOKEN:if(token_push_ready)begin if(send_pair+1==pairs)state<=DRAIN;else begin send_pair<=send_pair+1;sequence_number<=sequence_number+1;send_burst<=0;state<=WAIT;end end
     DRAIN:if(credits==0)begin busy<=0;done<=1;end
    endcase
   end
  end
 end
endmodule

