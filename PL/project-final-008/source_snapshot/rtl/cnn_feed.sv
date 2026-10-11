// Double bounded read buffers; one pixel per cycle after first burst.
module cnn_feed(input logic clk,rst,start,input logic [1:0] profile,transition_stage,input logic [4:0] block_index,input logic [31:0] slot_words,output logic busy,done,output logic [31:0] trace,output logic cmd_valid,input logic cmd_ready,output logic [31:0] cmd_addr,output logic [5:0] cmd_words,input logic data_valid,output logic data_ready,input logic [127:0] data,output logic out_valid,input logic out_ready,output logic signed [15:0] out_data);
 typedef enum logic [1:0] {WAIT,CMD,READ} state_t;state_t state;
 (* ram_style="distributed" *) logic [127:0] mem[0:63];logic [1:0] full;logic fb,pb;
 logic [5:0] wr,rd,len[0:1],flen;logic [2:0] lane;logic [31:0] remaining,address,count,total;
 assign cmd_valid=busy&&state==CMD;assign cmd_addr=address;assign cmd_words=flen;
 wire [127:0] read_word=mem[{pb,rd[4:0]}];
 assign data_ready=busy&&state==READ;assign out_valid=busy&&full[pb];assign out_data=$signed(read_word[lane*16+:16]);assign trace=busy?32'h80000000|count:0;
 always_ff @(posedge clk)if(!rst&&data_valid&&data_ready)mem[{fb,wr[4:0]}]<=data;
 always_ff @(posedge clk)begin
  if(rst)begin busy<=0;done<=0;state<=WAIT;full<=0;fb<=0;pb<=0;wr<=0;rd<=0;lane<=0;remaining<=0;address<=0;count<=0;total<=0;flen<=0;len[0]<=0;len[1]<=0;end
  else begin done<=0;
   if(start&&!busy)begin busy<=1;full<=0;fb<=0;pb<=0;wr<=0;rd<=0;lane<=0;state<=WAIT;remaining<=transition_stage==1?32768:transition_stage==2?16384:slot_words;total<=(transition_stage==1?32768:transition_stage==2?16384:slot_words)<<3;address<=transition_stage==1?0:transition_stage==2?slot_words:(block_index[0]?slot_words:0);count<=0;end
   else if(busy)begin
    case(state)
     WAIT:if(!full[fb]&&remaining!=0)begin flen<=remaining>=32?32:remaining[5:0];state<=CMD;end
     CMD:if(cmd_ready)begin wr<=0;state<=READ;end
     READ:if(data_valid)begin if(wr+1==flen)begin full[fb]<=1;len[fb]<=flen;fb<=!fb;address<=address+flen;remaining<=remaining-flen;state<=WAIT;end else wr<=wr+1;end
    endcase
    if(out_valid&&out_ready)begin count<=count+1;if(count+1==total)begin busy<=0;done<=1;end
     if(lane==7)begin lane<=0;if(rd+1==len[pb])begin full[pb]<=0;pb<=!pb;rd<=0;end else rd<=rd+1;end else lane<=lane+1;
    end
   end
  end
 end
endmodule
