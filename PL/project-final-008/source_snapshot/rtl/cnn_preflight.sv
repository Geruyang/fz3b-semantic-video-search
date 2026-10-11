// Handwritten ABI10/A0005 preflight. Only one burst outstanding; invalid data
// is accumulated while all accepted commands are drained before completion.
module cnn_preflight (
 input logic clk,rst,start,
 output logic done,busy,
 input logic [31:0] profile,block_count,params_words,slot_words,arena_words,flags,
 output logic [31:0] error,
 output logic [1:0] cmd_valid,input logic [1:0] cmd_ready,
 output logic [31:0] cmd_addr [2],output logic [5:0] cmd_words [2],
 input logic [1:0] data_valid,output logic [1:0] data_ready,
 input logic [127:0] data [2]
);
 import cnn_profile_pkg::*;
 typedef enum logic[2:0] {IDLE,SETUP,COMMAND,READING,DRAIN,FINISH} state_t;
 state_t state;
 logic [31:0] p,blocks,block_no,base,offset,count,pos;
 logic [3:0] region;
 logic client,bad;
 logic [2:0] kind; // bias, shifts, scalar, normal table, folded table
 logic [5:0] left,burst;
 logic [31:0] used,begin_index,z,t;
 logic signed [15:0] seg_min,seg_max,word_min,word_max,next_min,next_max;
 logic signed [15:0] tree_min [15], tree_max [15];
 logic check_valid,check_bad,check_table,check_first,check_last,span_valid;
 logic signed [15:0] check_min,check_max,span_min,span_max;
 logic signed [16:0] span_delta;
 logic word_bad;
 integer c,k;
 always_comb begin
  c=channels(p);
  cmd_valid=0;data_ready=0;
  burst=(count-pos>32)?6'd32:count-pos;
  for(integer j=0;j<2;j=j+1) begin cmd_addr[j]=base+offset+pos;cmd_words[j]=burst;end
  if(state==COMMAND)cmd_valid[client]=1;
  if(state==READING)data_ready[client]=1;
  word_bad=0;
  // Three comparator levels, with signed types preserved at every node.
  for(integer j=0;j<8;j=j+1)begin
   tree_min[7+j]=$signed(data[client][j*16+:16]);
   tree_max[7+j]=$signed(data[client][j*16+:16]);
  end
  for(integer j=6;j>=0;j=j-1)begin
   tree_min[j]=(tree_min[2*j+1]<tree_min[2*j+2])?tree_min[2*j+1]:tree_min[2*j+2];
   tree_max[j]=(tree_max[2*j+1]>tree_max[2*j+2])?tree_max[2*j+1]:tree_max[2*j+2];
  end
  word_min=tree_min[0];word_max=tree_max[0];
  next_min=check_first?check_min:((check_min<seg_min)?check_min:seg_min);
  next_max=check_first?check_max:((check_max>seg_max)?check_max:seg_max);
  span_delta=$signed({span_max[15],span_max})-$signed({span_min[15],span_min});
  case(kind)
   0:for(integer j=0;j<2;j=j+1)if(data[client][j*64+48+:16]!={16{data[client][j*64+47]}})word_bad=1;
   1:for(integer j=0;j<4;j=j+1)if($signed(data[client][j*32+:32])<0 || $signed(data[client][j*32+:32])>62)word_bad=1;
   2:if(data[client][127:64]!=0 || $signed(data[client][63:32])<0 || $signed(data[client][63:32])>62)word_bad=1;
   3,4:begin
    if(kind==3 && pos>=used)begin if(data[client]!=0)word_bad=1;end
    else begin

     if(kind==3)for(integer j=0;j<8;j=j+1)begin
      if(pos==0 && begin_index+j<z && data[client][j*16+:16]!=0)word_bad=1;
      if(pos+1==used && begin_index+pos*8+j>=t && data[client][j*16+:16]!=16'd32767)word_bad=1;
     end
    end
   end
   default:word_bad=1;
  endcase
 end
 always_ff @(posedge clk)begin
  if(rst)begin state<=IDLE;done<=0;busy<=0;error<=0;p<=0;blocks<=0;block_no<=0;base<=0;offset<=0;count<=0;pos<=0;region<=0;client<=0;kind<=0;left<=0;used<=0;begin_index<=0;z<=0;t<=0;end
  else begin
   done<=0;
   case(state)
    IDLE:if(start)begin
     busy<=1;error<=0;p<=profile;blocks<=block_count;block_no<=0;base<=0;region<=0;
     if(profile>3 || flags!=0 || block_count==0 || block_count>max_blocks(profile) || params_words!=expected_param_words(profile,block_count) || slot_words!=slot_words_for(profile) || arena_words!=2*slot_words_for(profile)+4096)begin error<=1;state<=FINISH;end
     else state<=SETUP;
    end
    SETUP:begin
     pos<=0;client<=0;
     if(p==3)begin
      case(region)
       0:begin offset<=784;count<=64;kind<=0;end
       1:begin offset<=880;count<=32;kind<=1;end
       2:begin offset<=7056;count<=64;kind<=0;end
       3:begin offset<=7152;count<=32;kind<=1;end
       4:begin offset<=912;count<=4096;used<=4096;kind<=4;end
       5:begin offset<=7184;count<=4096;used<=4096;kind<=4;end
      endcase
     end else begin
      client<=(region>=4 && region<8);
      case(region)
       0,4:begin offset<=bias_offset(p);count<=3*c;kind<=0;end
       1,5:begin offset<=bias_offset(p)+3*c+6*c/4;count<=6*c/4;kind<=1;end
       2,6:begin offset<=bias_offset(p)+6*c+c/4;count<=c/4;kind<=1;end
       3,7:begin offset<=bias_offset(p)+6*c+c/2;count<=1;kind<=2;end
       8:begin offset<=gelu_offset(p);count<=7032;kind<=3;z<=gelu_zero(p,block_no);t<=gelu_tail(p,block_no);begin_index<=gelu_zero(p,block_no)&32'hfffffff8;used<=((gelu_tail(p,block_no)+7)/8)-(gelu_zero(p,block_no)/8);end
      endcase
     end
     state<=COMMAND;
    end
    COMMAND:if(cmd_ready[client])begin left<=burst;state<=READING;end
    READING:if(data_valid[client])begin
     pos<=pos+1;left<=left-1;
     if(pos+1==count)state<=DRAIN;
     else if(left==1)state<=COMMAND;
    end
    // No next-region reset or done may race the in-flight validators.
    DRAIN:if(!check_valid && !span_valid)begin
     if(region==(p==3?5:8))begin
      if(block_no+1==blocks)state<=FINISH;
      else begin block_no<=block_no+1;base<=base+stride(p);region<=0;state<=SETUP;end
     end else begin region<=region+1;state<=SETUP;end
    end
    FINISH:begin if(error!=1)error<=bad?2:0;busy<=0;done<=1;state<=IDLE;end
    default:state<=IDLE;
   endcase
  end
 end
 // Accepted beat -> balanced word extrema -> segment extrema -> span check.
 // Valid bubbles follow DDR pauses; the segment state changes only on tags.
 always_ff @(posedge clk)begin
  if(rst)begin
   check_valid<=0;check_bad<=0;check_table<=0;check_first<=0;check_last<=0;
   check_min<=0;check_max<=0;span_valid<=0;span_min<=0;span_max<=0;
   seg_min<=32767;seg_max<=-32768;bad<=0;
  end else begin
   check_valid<=(state==READING && data_valid[client]);
   span_valid<=check_valid && check_table && check_last;
   if(state==IDLE && start)bad<=0;
   else if((check_valid && check_bad) || (span_valid && span_delta>17'sd255))bad<=1;
   if(state==SETUP)begin seg_min<=32767;seg_max<=-32768;end
   if(state==READING && data_valid[client])begin
    check_bad<=word_bad;check_min<=word_min;check_max<=word_max;
    check_table<=(kind==4 || (kind==3 && pos<used));
    check_first<=pos[1:0]==0;check_last<=(pos[1:0]==3 || pos+1==used);
   end
   if(check_valid && check_table)begin
    seg_min<=next_min;seg_max<=next_max;span_min<=next_min;span_max<=next_max;
   end
  end
 end
endmodule
