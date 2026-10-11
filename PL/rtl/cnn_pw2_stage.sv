// Hand-written PW2: dual pipelined MACs, shared tile broadcast, 16 scale credits.
// Normal-only packed40 state. Every MAC transaction is retired before reuse.
module cnn_pw2_stage (
 input logic clk,rst,fast_clk,fast_rst,start,
 output logic done,busy,
 input logic [1:0] profile,transition_stage,
 input logic [4:0] block_index,
 input logic [31:0] slot_words,
 input logic [1:0] in_valid, output logic [1:0] in_ready,
 input logic signed [15:0] in_data [2],
 output logic [1:0] out_valid,input logic [1:0] out_ready,
 output logic signed [15:0] out_data [2],
 output logic cmd_valid,input logic cmd_ready,
 output logic [31:0] cmd_addr,output logic [5:0] cmd_words,
 input logic data_valid,output logic data_ready,input logic [127:0] data,
 output logic [1:0] res_cmd_valid,input logic [1:0] res_cmd_ready,
 output logic [31:0] res_cmd_addr [2],output logic [5:0] res_cmd_words [2],
 input logic [1:0] res_data_valid,output logic [1:0] res_data_ready,
 input logic [127:0] res_data [2],
 input logic [1:0] res_ready_valid,output logic [1:0] res_ready_ready,
 input logic [31:0] res_ready_token [2],
 output logic [1:0] res_release_valid,input logic [1:0] res_release_ready,
 output logic [1:0] scale_req_valid,input logic [1:0] scale_req_ready,
 output logic signed [47:0] scale_req_value [2],
 output logic signed [31:0] scale_req_multiplier [2],output logic [5:0] scale_req_shift [2],
 input logic [1:0] scale_rsp_valid,output logic [1:0] scale_rsp_ready,
 input logic signed [15:0] scale_rsp_data [2],
 output logic [31:0] trace [2],output logic [31:0] error
);
 typedef enum logic [4:0] {IDLE,CO_CMD,CO_DATA,INPUT_TILE,WT_CMD,WT_DATA,
 PREP,MAC_SEND,MAC_RECV,TOKEN,RES_CMD,RES_DATA,SCALE_SEND,SCALE_RECV,OUTPUT_PIXEL,
 RELEASE_PAIR,BYPASS,Q_WAIT,Q_PREF,Q_FILL,WAIT_DONE} state_t;
 state_t state;
 typedef enum logic [2:0] {P_IDLE,P_TOKEN,P_RES_CMD,P_RES_DATA,P_RUN,P_RELEASE} post_state_t;
 post_state_t post_state;
 logic q_cache_busy,q_responses_active;
 logic [5:0] q_pair_tag,post_pair;
 logic [1:0] post_accepted,q_fetch_valid;
 logic [13:0] q_sent [2],q_received [2],q_read_cursor [2];
 logic [6:0] post_read_sent [2];
 logic signed [15:0] q_read_data [2];
 logic [1:0] q_read_en,q_context_valid,q_context_pending;
 logic [5:0] q_context_group [2];
 logic [127:0] q_mul_cache [2],q_coef_read;
 logic [23:0] q_shift_cache [2],q_shift_read;
 logic q_header_en,q_header_lane,q_header_pending,q_header_rr,q_header_return_lane;
 logic [5:0] q_header_group,q_header_return_group;
 logic [1:0] q_need_context;
 logic [13:0] q_next [2];
 function automatic logic [10:0] q_raw_address(input logic [13:0] index,input logic [2:0] rs);
  q_raw_address=((index>>(rs+3))<<(rs+1))+(((index>>(rs+2))&1)<<rs)+(index&((14'd1<<rs)-1));
 endfunction
 logic [191:0] group_bias;
 (* ram_style="block" *) logic [95:0] bias_store [128];
 (* ram_style="block" *) logic [127:0] mul_store [64],output_mul_store [64];
 (* ram_style="distributed" *) logic [23:0] shift_store [64],output_shift_store [64];
 logic [127:0] mul_cache,output_mul_cache;
 logic [23:0] shift_cache,output_shift_cache;
 logic signed [31:0] residual_mul;
 logic [5:0] residual_shift;
 logic [1023:0] weights;
 logic loader_start,loader_busy,loader_done,loader_cmd_valid,loader_data_ready,loader_out_valid,loader_out_ready;
 logic [31:0] loader_cmd_addr;logic [5:0] loader_cmd_words;logic [1023:0] loader_out_data;
 logic [15:0] loader_tile_count;
 logic [255:0] mac_values [2];logic [191:0] mac_prior [2],mac_result [2];
 logic [1:0] mac_sv,mac_sr,mac_mv,mac_mr;
 logic [1:0] post_sv,post_sr,post_mv;logic signed [15:0] post_skip [2],post_data [2];
 logic [1:0] accepted;
 logic [7:0] issued [2],retired [2];
 logic [6:0] scale_sent [2],scale_received [2],post_received [2];
 logic input_capture_active;
 logic [8:0] fill_seq [2],compute_seq,tile_epoch [2][2];
 logic [1:0] tile_full [2];
 logic [11:0] input_count [2];logic [2:0] row_shift;logic [3:0] channel_shift;
 logic [8:0] c;logic [6:0] w;logic [31:0] base,bias_base,weight_base;
 logic [2:0] field,word_index;
 logic [7:0] co_word,co_count;logic [5:0] co_remaining;
 logic [5:0] reduction,group_index,row_pair;
 integer input_index,column_index;
 logic rr;logic [7:0] channel_index;logic [5:0] res_word_index [2];logic [17:0] bypass_count [2];integer x_index;
 logic [127:0] residual_read_word [2];
 logic signed [15:0] pixel_reg [2];
 logic [159:0] read_packed [2];
 logic [31:0] sequence_id,scratch_base;
 assign loader_tile_count=c==64?16'd192:c==128?16'd768:16'd3072;
 cnn_tile_loader weight_prefetch(.clk(clk),.rst(rst),.start(loader_start),.busy(loader_busy),.done(loader_done),
  .base_addr(weight_base),.tile_count(loader_tile_count),.cmd_valid(loader_cmd_valid),.cmd_ready(cmd_ready),
  .cmd_addr(loader_cmd_addr),.cmd_words(loader_cmd_words),.data_valid(data_valid),.data_ready(loader_data_ready),.data(data),
  .out_valid(loader_out_valid),.out_ready(loader_out_ready),.out_data(loader_out_data));
 for(genvar lane=0;lane<2;lane++)begin: engines
  // A row/group buffer has one fixed-lane write port and one async word read.
  // Keep the word mux outside the RAM template so this remains bounded LUTRAM.
  (* ram_style="distributed" *) logic [127:0] residual_mem [32];
  logic [4:0] residual_read_addr;
  assign residual_read_addr=5'((channel_index%4)*(w/8)+scale_received[lane]/8);
  assign residual_read_word[lane]=residual_mem[residual_read_addr];
  always_ff @(posedge clk)begin
   if(!rst&&res_data_valid[lane]&&res_data_ready[lane])residual_mem[res_word_index[lane][4:0]]<=res_data[lane];
  end
  (* ram_style="block" *) logic [159:0] accum_mem [2048];
  logic accum_read_en,accum_write_en,tile_read_en;
  logic [10:0] accum_read_addr,accum_write_addr;
  logic [7:0] tile_read_addr,tile_write_addr;
  logic [3:0] tile_write_bank;
  logic [159:0] packed_result;
  always_comb begin
   accum_write_en=!rst&&state==MAC_SEND&&mac_mv[lane]&&mac_mr[lane];
   accum_write_addr=(32'(group_index)<<(row_shift+1))+retired[lane];
   packed_result={mac_result[lane][183:144],mac_result[lane][135:96],mac_result[lane][87:48],mac_result[lane][39:0]};
   accum_read_en=0;accum_read_addr=0;
   if(!rst)begin
    if(state==PREP&&reduction!=0)begin accum_read_en=1;accum_read_addr=32'(group_index)<<(row_shift+1);end
    else if(state==MAC_SEND&&mac_sv[lane]&&mac_sr[lane]&&issued[lane]+1<2*w&&reduction!=0)begin
     accum_read_en=1;accum_read_addr=(32'(group_index)<<(row_shift+1))+issued[lane]+1;
    end else if(state==Q_PREF)begin accum_read_en=1;accum_read_addr=0;
    end else if(state==Q_FILL&&scale_req_valid[lane]&&scale_req_ready[lane]&&q_sent[lane]+1<8192)begin
     accum_read_en=1;accum_read_addr=q_raw_address(q_next[lane],row_shift);
    end
   end
   tile_read_en=!rst&&(state==PREP||(state==MAC_SEND&&mac_sv[lane]&&mac_sr[lane]&&issued[lane]+1<2*w));
   tile_read_addr={compute_seq[0],7'(state==PREP?0:issued[lane]+1)};
   tile_write_bank=((input_count[lane]>>(row_shift+3))<<2)+((input_count[lane]>>row_shift)&3);
   tile_write_addr={fill_seq[lane][0],7'((((input_count[lane]>>(row_shift+2))&1)<<row_shift)+(input_count[lane]&(w-1)))};
  end
  for(genvar bank=0;bank<16;bank++)begin: input_bank
   (* ram_style="distributed" *) logic signed [15:0] tile_mem [256];
   logic tile_write_en;
   assign tile_write_en=!rst&&in_valid[lane]&&in_ready[lane]&&input_capture_active&&tile_write_bank==bank;
   always_ff @(posedge clk)begin
    if(tile_write_en)tile_mem[tile_write_addr]<=in_data[lane];
    if(tile_read_en)mac_values[lane][bank*16+:16]<=tile_mem[tile_read_addr];
   end
  end
  always_ff @(posedge clk)begin
   if(accum_write_en)accum_mem[accum_write_addr]<=packed_result;
   if(accum_read_en)read_packed[lane]<=accum_mem[accum_read_addr];
  end
  (* ram_style="block" *) logic signed [15:0] q_mem [8192];
  always_ff @(posedge clk)begin
   if(scale_rsp_valid[lane]&&scale_rsp_ready[lane])q_mem[q_received[lane][12:0]]<=scale_rsp_data[lane];
   if(q_read_en[lane])q_read_data[lane]<=q_mem[q_read_cursor[lane][12:0]];
  end
  always_comb begin
   for(integer k=0;k<4;k++)mac_prior[lane][k*48+:48]=reduction==0 ? group_bias[k*48+:48] : {{8{read_packed[lane][k*40+39]}},read_packed[lane][k*40+:40]};
  end
  cnn_pw_mac mac(.clk(clk),.rst(rst),.fast_clk(fast_clk),.fast_rst(fast_rst),
   .s_valid(mac_sv[lane]),.s_ready(mac_sr[lane]),.s_values(mac_values[lane]),
   .s_weights(weights),.s_prior(mac_prior[lane]),.m_valid(mac_mv[lane]),
   .m_ready(mac_mr[lane]),.m_result(mac_result[lane]));
  cnn_narrow_post post_pipe(.clk(clk),.rst(rst),.s_valid(post_sv[lane]),.s_ready(post_sr[lane]),
   .s_q(q_read_data[lane]),.s_skip(post_skip[lane]),.s_output_multiplier($signed(output_mul_cache[(channel_index%4)*32+:32])),
   .s_residual_multiplier(residual_mul),.s_output_shift(output_shift_cache[(channel_index%4)*6+:6]),.s_residual_shift(residual_shift),
   .m_valid(post_mv[lane]),.m_ready(out_ready[lane]),.m_data(post_data[lane]));
 end
 always_comb begin
  for(integer lane=0;lane<2;lane++)begin
   q_next[lane]=q_sent[lane]+1;
   q_need_context[lane]=(state==Q_PREF||state==Q_FILL)&&q_sent[lane]<8192&&!q_context_pending[lane]&&
    (!q_context_valid[lane]||q_context_group[lane]!=(q_sent[lane]>>(row_shift+3)));
  end
  q_header_en=|q_need_context;
  q_header_lane=q_need_context[q_header_rr]?q_header_rr:!q_header_rr;
  q_header_group=q_sent[q_header_lane]>>(row_shift+3);
 end
 always_ff @(posedge clk)begin
  if(state==CO_DATA&&data_valid&&field==1)mul_store[co_word]<=data;
  if(state==CO_DATA&&data_valid&&field==2)shift_store[co_word]<={data[101:96],data[69:64],data[37:32],data[5:0]};
  if(q_header_en)begin q_coef_read<=mul_store[q_header_group];q_shift_read<=shift_store[q_header_group];end
 end
 always_comb begin
  busy=state!=IDLE;cmd_valid=loader_cmd_valid;data_ready=loader_data_ready;cmd_addr=loader_cmd_addr;cmd_words=loader_cmd_words;loader_out_ready=state==WT_CMD;
  q_read_en=0;
  in_ready=0;for(integer lane=0;lane<2;lane++)in_ready[lane]=input_capture_active&&fill_seq[lane]<384&&!tile_full[lane][fill_seq[lane][0]];out_valid=0;res_cmd_valid=0;res_data_ready=0;res_ready_ready=0;
  res_release_valid=0;scale_req_valid=0;scale_rsp_ready=0;mac_sv=0;mac_mr=0;post_sv=0;
  sequence_id=block_index*(w/2)+post_pair;scratch_base=2*slot_words+(sequence_id&3)*1024;
  for(integer lane=0;lane<2;lane++)begin
   post_skip[lane]=scale_received[lane]<w ? $signed(residual_read_word[lane][(scale_received[lane]%8)*16+:16]) : 16'sd0;
   out_data[lane]=pixel_reg[lane];res_cmd_addr[lane]=scratch_base+rr*512+(32'({channel_index[7:2],2'b00})<<(row_shift-3));
   res_cmd_words[lane]=w/2;scale_req_value[lane]={{8{read_packed[lane][((q_sent[lane]>>row_shift)&3)*40+39]}},read_packed[lane][((q_sent[lane]>>row_shift)&3)*40+:40]};
   scale_req_multiplier[lane]=$signed(q_mul_cache[lane][((q_sent[lane]>>row_shift)&3)*32+:32]);
   scale_req_shift[lane]=q_shift_cache[lane][((q_sent[lane]>>row_shift)&3)*6+:6];
   scale_rsp_ready[lane]=q_responses_active&&q_received[lane]<8192;
   trace[lane]=busy ? (32'h80000000 | (block_index<<16) | ((row_pair*2)<<8) | state) : 0;
  end
  unique case(state)
   CO_CMD:begin
    cmd_valid=1;data_ready=0;cmd_words=(co_count-co_word)>32?32:(co_count-co_word);
    unique case(field)
     0:cmd_addr=bias_base+5*c/2+co_word;
     1:cmd_addr=bias_base+3*c+5*c/4+co_word;
     2:cmd_addr=bias_base+3*c+6*c/4+5*c/4+co_word;
     3:cmd_addr=bias_base+6*c+co_word;
     4:cmd_addr=bias_base+6*c+c/4+co_word;
     default:cmd_addr=bias_base+6*c+c/2;
    endcase
   end
   CO_DATA:begin cmd_valid=0;data_ready=1;end


   MAC_SEND:begin
    for(integer lane=0;lane<2;lane++)begin mac_sv[lane]=issued[lane]<2*w;mac_mr[lane]=1;end
   end
   Q_FILL:for(integer lane=0;lane<2;lane++)scale_req_valid[lane]=q_sent[lane]<8192&&q_sent[lane]-q_received[lane]<16&&q_context_valid[lane]&&q_context_group[lane]==(q_sent[lane]>>(row_shift+3));
   BYPASS:for(integer lane=0;lane<2;lane++)begin
    out_data[lane]=in_data[lane];out_valid[lane]=in_valid[lane]&&(bypass_count[lane]<131072);
    in_ready[lane]=out_ready[lane]&&(bypass_count[lane]<131072);
   end
   default:begin end
  endcase
  unique case(post_state)
   P_TOKEN:res_ready_ready=~post_accepted;
   P_RES_CMD:res_cmd_valid=~post_accepted;
   P_RES_DATA:for(integer lane=0;lane<2;lane++)res_data_ready[lane]=res_word_index[lane]<w/2;
   P_RUN:for(integer lane=0;lane<2;lane++)begin
    q_read_en[lane]=(!q_fetch_valid[lane]||post_sr[lane])&&post_read_sent[lane]<w&&q_read_cursor[lane]<q_received[lane];
    post_sv[lane]=q_fetch_valid[lane];out_valid[lane]=post_mv[lane];out_data[lane]=post_data[lane];
   end
   P_RELEASE:res_release_valid=~post_accepted;
   default:begin end
  endcase
 end
 always_ff @(posedge clk)begin
  if(rst)begin state<=IDLE;done<=0;loader_start<=0;input_capture_active<=0;compute_seq<=0;post_state<=P_IDLE;q_cache_busy<=0;q_responses_active<=0;post_pair<=0;post_accepted<=0;q_fetch_valid<=0;q_context_valid<=0;q_context_pending<=0;q_header_pending<=0;q_header_rr<=0;error<=0;c<=64;w<=64;row_shift<=6;channel_shift<=6;accepted<=0;channel_index<=0;
   rr<=0;row_pair<=0;field<=0;co_word<=0;co_count<=0;co_remaining<=0;base<=0;bias_base<=0;weight_base<=0;
   input_index<=0;reduction<=0;group_index<=0;column_index<=0;word_index<=0;
   for(integer lane=0;lane<2;lane++)begin bypass_count[lane]<=0;input_count[lane]<=0;fill_seq[lane]<=0;tile_full[lane]<=0;res_word_index[lane]<=0;pixel_reg[lane]<=0;end
  end else begin
   done<=0;loader_start<=0;
   q_header_pending<=q_header_en;
   if(q_header_en)begin
    q_header_return_lane<=q_header_lane;q_header_return_group<=q_header_group;q_context_pending[q_header_lane]<=1;q_header_rr<=!q_header_lane;
   end
   if(q_header_pending)begin
    q_mul_cache[q_header_return_lane]<=q_coef_read;q_shift_cache[q_header_return_lane]<=q_shift_read;
    q_context_group[q_header_return_lane]<=q_header_return_group;q_context_valid[q_header_return_lane]<=1;q_context_pending[q_header_return_lane]<=0;
   end
   for(integer lane=0;lane<2;lane++)begin
    if(scale_req_valid[lane]&&scale_req_ready[lane])q_sent[lane]<=q_sent[lane]+1;
    if(scale_rsp_valid[lane]&&scale_rsp_ready[lane])q_received[lane]<=q_received[lane]+1;
    if(q_read_en[lane])begin q_read_cursor[lane]<=q_read_cursor[lane]+1;post_read_sent[lane]<=post_read_sent[lane]+1;q_fetch_valid[lane]<=1;end
    else if(post_sv[lane]&&post_sr[lane])q_fetch_valid[lane]<=0;
   end
   if(q_responses_active&&q_received[0]==8192&&q_received[1]==8192)q_responses_active<=0;
   for(integer lane=0;lane<2;lane++)if(input_capture_active&&in_valid[lane]&&in_ready[lane])begin
    if(input_count[lane]+1==32*w)begin
     input_count[lane]<=0;tile_full[lane][fill_seq[lane][0]]<=1;
     tile_epoch[lane][fill_seq[lane][0]]<=fill_seq[lane];fill_seq[lane]<=fill_seq[lane]+1;
    end else input_count[lane]<=input_count[lane]+1;
   end
   unique case(state)
    IDLE:if(start)begin
     error<=0;accepted<=0;input_capture_active<=0;compute_seq<=0;post_state<=P_IDLE;q_cache_busy<=0;q_responses_active<=0;post_pair<=0;post_accepted<=0;q_fetch_valid<=0;q_context_valid<=0;q_context_pending<=0;q_header_pending<=0;row_pair<=0;rr<=0;channel_index<=0;x_index<=0;field<=0;co_word<=0;input_index<=0;reduction<=0;group_index<=0;column_index<=0;
     for(integer lane=0;lane<2;lane++)begin bypass_count[lane]<=0;input_count[lane]<=0;fill_seq[lane]<=0;tile_full[lane]<=0;end
     if(transition_stage!=0)state<=BYPASS;
     else begin
      c<=profile==0?128:profile==1?256:64;w<=profile==0?32:profile==1?16:64;row_shift<=profile==0?5:profile==1?4:6;channel_shift<=profile==0?7:profile==1?8:6;
      base<=block_index*(profile==0?21081:profile==1?59705:10985);
      bias_base<=block_index*(profile==0?21081:profile==1?59705:10985)+(profile==0?928:profile==1?1856:464);
      weight_base<=block_index*(profile==0?21081:profile==1?59705:10985)+(profile==0?14937:profile==1?35129:9449);
      co_count<=(profile==0?128:profile==1?256:64)/2;state<=CO_CMD;
     end
    end
    CO_CMD:if(cmd_ready)begin co_remaining<=cmd_words;state<=CO_DATA;end
    CO_DATA:if(data_valid)begin
     co_remaining<=co_remaining-1;
     if(field==0)bias_store[co_word]<={data[111:64],data[47:0]};
     if(field==3)output_mul_store[co_word]<=data;
     if(field==4)output_shift_store[co_word]<={data[101:96],data[69:64],data[37:32],data[5:0]};
     if(field==5)begin residual_mul<=data[31:0];residual_shift<=data[37:32];end
     if(co_word+1==co_count)begin
      co_word<=0;field<=field+1;co_count<=field==4?1:c/4;
      state<=field==5?INPUT_TILE:CO_CMD;if(field==5)begin loader_start<=1;input_capture_active<=1;end
     end else begin co_word<=co_word+1;if(co_remaining==1)state<=CO_CMD;end
    end
    INPUT_TILE:begin
     if(tile_full[0][compute_seq[0]]&&tile_full[1][compute_seq[0]])begin
      if(tile_epoch[0][compute_seq[0]]!=compute_seq||tile_epoch[1][compute_seq[0]]!=compute_seq)error<=error|32'h8;
      else begin group_index<=0;state<=WT_CMD;end
     end
    end
    WT_CMD:if(loader_out_valid)begin
     weights<=loader_out_data;
     if(reduction==0)group_bias<={bias_store[group_index*2+1],bias_store[group_index*2]};
     state<=PREP;
    end
    PREP:begin
     for(integer lane=0;lane<2;lane++)begin
      issued[lane]<=0;retired[lane]<=0;
     end
     state<=MAC_SEND;
    end
    MAC_SEND:begin
     for(integer lane=0;lane<2;lane++)begin
      if(mac_sv[lane]&&mac_sr[lane])begin
       issued[lane]<=issued[lane]+1;
      end
      if(mac_mv[lane]&&mac_mr[lane])begin
       retired[lane]<=retired[lane]+1;
      end
     end
     if(retired[0]==2*w&&retired[1]==2*w)begin
      if(group_index+1<c/4)begin group_index<=group_index+1;state<=WT_CMD;end
      else begin
       for(integer lane=0;lane<2;lane++)tile_full[lane][compute_seq[0]]<=0;
       compute_seq<=compute_seq+1;
       if(reduction+1<3*c/16)begin reduction<=reduction+1;state<=INPUT_TILE;end
       else state<=Q_WAIT;
      end
     end
    end
    Q_WAIT:if(!q_cache_busy)begin
     q_cache_busy<=1;q_responses_active<=1;q_pair_tag<=row_pair;q_context_valid<=0;q_context_pending<=0;
     post_accepted<=0;rr<=0;channel_index<=0;post_state<=P_TOKEN;q_fetch_valid<=0;
     for(integer lane=0;lane<2;lane++)begin q_sent[lane]<=0;q_received[lane]<=0;q_read_cursor[lane]<=0;end
     state<=Q_PREF;
    end
    Q_PREF:state<=Q_FILL;
    Q_FILL:if(q_sent[0]==8192&&q_sent[1]==8192)begin
     // All raw reads completed and all values captured by the wide service.
     // Old qpair responses retain q_cache ownership while nextpair MAC starts.
     if(row_pair+1==w/2)state<=WAIT_DONE;
     else begin row_pair<=row_pair+1;reduction<=0;group_index<=0;loader_start<=1;state<=INPUT_TILE;end
    end
    WAIT_DONE:if(post_pair==w/2&&!q_cache_busy&&!q_responses_active&&!loader_busy)begin
     input_capture_active<=0;state<=IDLE;done<=1;
    end
    BYPASS:begin
     for(integer lane=0;lane<2;lane++)if(in_valid[lane]&&in_ready[lane])bypass_count[lane]<=bypass_count[lane]+1;
     if(bypass_count[0]==131072&&bypass_count[1]==131072)begin state<=IDLE;done<=1;end
    end
    default:state<=IDLE;
   endcase
   unique case(post_state)
    P_TOKEN:begin
     for(integer lane=0;lane<2;lane++)if(res_ready_valid[lane]&&res_ready_ready[lane])begin
      post_accepted[lane]<=1;if(res_ready_token[lane]!=sequence_id||q_pair_tag!=post_pair)error<=error|32'h4;
     end
     if(&(post_accepted|(res_ready_valid&res_ready_ready)))begin post_accepted<=0;post_state<=P_RES_CMD;end
    end
    P_RES_CMD:begin
     post_accepted<=post_accepted|(res_cmd_valid&res_cmd_ready);
     if(&(post_accepted|(res_cmd_valid&res_cmd_ready)))begin post_accepted<=0;for(integer lane=0;lane<2;lane++)res_word_index[lane]<=0;post_state<=P_RES_DATA;end
    end
    P_RES_DATA:begin
     for(integer lane=0;lane<2;lane++)if(res_data_valid[lane]&&res_data_ready[lane])begin
      res_word_index[lane]<=res_word_index[lane]+1;
     end
     if(res_word_index[0]==w/2&&res_word_index[1]==w/2)begin
      output_mul_cache<=output_mul_store[channel_index>>2];output_shift_cache<=output_shift_store[channel_index>>2];
      for(integer lane=0;lane<2;lane++)begin scale_received[lane]<=0;post_received[lane]<=0;post_read_sent[lane]<=0;end
      post_state<=P_RUN;
     end
    end
    P_RUN:begin
     for(integer lane=0;lane<2;lane++)begin
      if(post_sv[lane]&&post_sr[lane])scale_received[lane]<=scale_received[lane]+1;
      if(out_valid[lane]&&out_ready[lane])post_received[lane]<=post_received[lane]+1;
     end
     if(post_received[0]==w&&post_received[1]==w)begin
      post_accepted<=0;
      if(channel_index%4<3)begin
       // The entire four-channel group is owned until both lanes drain.
       channel_index<=channel_index+1;
       for(integer lane=0;lane<2;lane++)begin scale_received[lane]<=0;post_received[lane]<=0;post_read_sent[lane]<=0;end
       post_state<=P_RUN;
      end
      else if(rr==0)begin rr<=1;channel_index<=channel_index-3;post_state<=P_RES_CMD;end
      else if(channel_index+1<c)begin rr<=0;channel_index<=channel_index+1;post_state<=P_RES_CMD;end
      else post_state<=P_RELEASE;
     end
    end
    P_RELEASE:begin
     post_accepted<=post_accepted|(res_release_valid&res_release_ready);
     if(&(post_accepted|(res_release_valid&res_release_ready)))begin
      post_accepted<=0;q_cache_busy<=0;post_pair<=post_pair+1;post_state<=P_IDLE;
     end
    end
    default:begin end
   endcase
  end
 end
endmodule
