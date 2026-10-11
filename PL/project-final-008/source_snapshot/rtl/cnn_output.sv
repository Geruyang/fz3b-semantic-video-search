// Double-buffered group -> row(2) -> channel(4) -> x scatter.
module cnn_output(input logic clk,rst,start,input logic [1:0] profile,transition_stage,input logic [4:0] block_index,input logic [31:0] slot_words,output logic busy,done,output logic [31:0] trace,input logic in_valid,output logic in_ready,input logic signed [15:0] in_data,output logic cmd_valid,input logic cmd_ready,output logic [31:0] cmd_addr,output logic [5:0] cmd_words,output logic data_valid,input logic data_ready,output logic [127:0] data,input logic commit_valid,output logic commit_ready,output logic row_commit_valid,output logic [5:0] row_commit_index,output logic [4:0] row_commit_block);
 typedef enum logic [1:0] {WAIT,CMD,SEND,COMMIT} state_t;state_t state;
 logic [1:0] full;logic fb,sb;
 logic [4:0] block_tag;
 logic [5:0] wr,rd,words;logic [6:0] groups;logic [2:0] lane;logic rr,contiguous;logic [6:0] group_index,y;logic [31:0] base,remaining,address,count,total;
 generate for(genvar pixel_lane=0;pixel_lane<8;pixel_lane++)begin: pixel_banks
  (* ram_style="distributed" *)logic [15:0] mem[0:63];
  always_ff @(posedge clk)if(!rst&&in_valid&&in_ready&&lane==pixel_lane)mem[{fb,wr[4:0]}]<=in_data;
  assign data[pixel_lane*16+:16]=mem[{sb,rd[4:0]}];
 end endgenerate
 assign in_ready=busy&&!full[fb]&&count<total;assign cmd_valid=busy&&state==CMD;assign cmd_words=words;assign cmd_addr=contiguous?address:base+(y+rr)*512+group_index*words;
 assign data_valid=busy&&state==SEND;assign commit_ready=busy&&state==COMMIT;assign trace=busy?32'h80000000|count:0;
 always_ff @(posedge clk)begin
  if(rst)begin busy<=0;done<=0;row_commit_valid<=0;row_commit_index<=0;row_commit_block<=0;block_tag<=0;state<=WAIT;full<=0;fb<=0;sb<=0;wr<=0;rd<=0;lane<=0;words<=0;groups<=0;rr<=0;contiguous<=0;group_index<=0;y<=0;base<=0;remaining<=0;address<=0;count<=0;total<=0;end
  else begin done<=0;row_commit_valid<=0;
   if(start&&!busy)begin block_tag<=block_index;busy<=1;state<=WAIT;full<=0;fb<=0;sb<=0;contiguous<=transition_stage==1;base<=transition_stage==2?0:transition_stage==1?slot_words:(!block_index[0]?slot_words:0);address<=slot_words;remaining<=transition_stage!=0?16384:slot_words;total<=(transition_stage!=0?16384:slot_words)<<3;words<=transition_stage==1?32:transition_stage==2?16:profile==0?16:profile==1?8:32;groups<=transition_stage!=0?32:profile==0?32:profile==1?64:16;wr<=0;rd<=0;lane<=0;rr<=0;group_index<=0;y<=0;count<=0;end
   else if(busy)begin
    if(in_valid&&in_ready)begin count<=count+1;
     if(lane==7)begin lane<=0;if(wr+1==words)begin full[fb]<=1;fb<=!fb;wr<=0;end else wr<=wr+1;end else lane<=lane+1;
    end
    case(state)
     WAIT:if(full[sb])begin rd<=0;state<=CMD;end
     CMD:if(cmd_ready)state<=SEND;
     SEND:if(data_ready)begin if(rd+1==words)state<=COMMIT;else rd<=rd+1;end
     COMMIT:if(commit_valid)begin full[sb]<=0;sb<=!sb;remaining<=remaining-words;address<=address+words;state<=WAIT;if(remaining==words)begin busy<=0;done<=1;end
      // cmd_addr/base describe the draining bank, never the concurrently filled bank.
      if(((cmd_addr-base)&32'd511)+words==512)begin row_commit_valid<=1;row_commit_block<=block_tag;row_commit_index<=(cmd_addr-base)>>9;end
      if(!rr)rr<=1;else begin rr<=0;if(group_index+1==groups)begin group_index<=0;y<=y+2;end else group_index<=group_index+1;end
     end
    endcase
   end
  end
 end
endmodule


