// Shared DDR loader and true-dual-port parameter banks, one read port/image.
module cnn_dw_stage #(parameter integer K=3,LANES=4)(
 input logic clk,rst,start,output logic done,busy,
 input logic [1:0] profile,input logic [4:0] block_index,input logic [1:0] transition_stage,
 input logic [1:0] in_valid,output logic [1:0] in_ready,input logic signed [15:0] in_data[2],
 output logic [1:0] out_valid,input logic [1:0] out_ready,output logic signed [15:0] out_data[2],
 output logic [1:0] skip_valid,input logic [1:0] skip_ready,output logic signed [15:0] skip_data[2],
 output logic cmd_valid,input logic cmd_ready,output logic [31:0] cmd_addr,output logic [5:0] cmd_words,
 input logic data_valid,output logic data_ready,input logic [127:0] data,
 output logic [1:0] scale_req_valid,input logic [1:0] scale_req_ready,
 output logic signed [47:0] scale_req_value[2],output logic signed [31:0] scale_req_multiplier[2],
 output logic [5:0] scale_req_shift[2],input logic [1:0] scale_rsp_valid,
 output logic [1:0] scale_rsp_ready,input logic signed [15:0] scale_rsp_data[2],
 output logic [31:0] trace[2],output logic [31:0] error
);
 typedef enum logic [2:0] {IDLE,CMD,READ,UNPACK,LAUNCH,RUN} st_t;
 st_t state;
 logic [8:0] channels,weight_channels;logic [6:0] width;
 logic bypass,trans;
 logic [31:0] base,field_base;logic [13:0] field_words,word_pos;
 logic [1:0] field;logic [5:0] remaining,burst;
 logic [127:0] word_q;logic [2:0] item;
 logic cfg_valid,core_start;logic [13:0] cfg_index;logic [63:0] cfg_data;
 logic [5:0] weight_tap;logic [7:0] weight_channel;logic [12:0] weight_pair_base,cfg_weight_address;
 logic cfg_weight_odd;
 logic [1:0] core_done,core_busy,finished;
 logic [12:0] weight_read_address[2];logic [6:0] coeff_read_address[2];
 logic [1:0] weight_read_enable,coeff_read_enable;
 logic signed [15:0] weight_q[2][2];
 logic signed [47:0] bias_q[2][2];
 logic signed [31:0] mul_q[2][2];logic [5:0] shift_q[2][2];
 // During loading, port A writes. During compute both ports read independently.
 // Loading and compute never overlap; no third RAM port or parameter replicas.
 for(genvar p=0;p<2;p=p+1)begin:gen_parameters
   (* ram_style="block" *) logic signed [15:0] weights[128*K*K];
   (* ram_style="block" *) logic signed [47:0] biases[128];
   (* ram_style="block" *) logic signed [31:0] multipliers[128];
   (* ram_style="distributed" *) logic [5:0] shift_mem[128];
   logic wwe,bwe,mwe;
   logic [12:0] wa;
   logic [6:0] ba,ma;
   assign wwe=cfg_valid&&field==0&&cfg_weight_odd==p;
   assign bwe=cfg_valid&&field==1&&cfg_index[0]==p;
   assign mwe=cfg_valid&&field==2&&cfg_index[0]==p;
   assign wa=wwe?cfg_weight_address:weight_read_address[0];
   assign ba=bwe?cfg_index[7:1]:coeff_read_address[0];
   assign ma=mwe?cfg_index[7:1]:coeff_read_address[0];
   // Each port uses one address for both read/write. Explicit READ_FIRST
   // template avoids Vivado replicating a write port plus two read ports.
   always_ff @(posedge clk)begin
     if(wwe||weight_read_enable[0])begin
       if(wwe)weights[wa]<=cfg_data[15:0];
       weight_q[p][0]<=weights[wa];
     end
     if(bwe||coeff_read_enable[0])begin
       if(bwe)biases[ba]<=cfg_data[47:0];
       bias_q[p][0]<=biases[ba];
     end
     if(mwe||coeff_read_enable[0])begin
       if(mwe)multipliers[ma]<=cfg_data[31:0];
       mul_q[p][0]<=multipliers[ma];
     end
     if(cfg_valid&&field==3&&cfg_index[0]==p)shift_mem[cfg_index[7:1]]<=cfg_data[5:0];
     else if(coeff_read_enable[0])shift_q[p][0]<=shift_mem[coeff_read_address[0]];
     if(coeff_read_enable[1])shift_q[p][1]<=shift_mem[coeff_read_address[1]];
   end
   always_ff @(posedge clk)begin
     if(weight_read_enable[1])weight_q[p][1]<=weights[weight_read_address[1]];
     if(coeff_read_enable[1])begin
       bias_q[p][1]<=biases[coeff_read_address[1]];
       mul_q[p][1]<=multipliers[coeff_read_address[1]];
     end
   end
 end
 always_comb begin
   cmd_valid=state==CMD;cmd_addr=field_base+word_pos;
   cmd_words=(field_words-word_pos>32)?32:(field_words-word_pos);
   data_ready=state==READ;
   cfg_valid=state==UNPACK;
   cfg_index=field==1?{6'd0,word_pos[6:0],item[0]}:{6'd0,word_pos[5:0],item[1:0]};
   cfg_weight_address=weight_pair_base+weight_tap;cfg_weight_odd=weight_channel[0];
   cfg_data=field==0?{48'd0,word_q[item*16+:16]}:
            field==1?word_q[item*64+:64]:{32'd0,word_q[item*32+:32]};
   core_start=state==LAUNCH;
 end
 for(genvar l=0;l<2;l=l+1) begin:g_core
   cnn_dw_core #(.K(K),.LANES(LANES)) core(
    .clk,.rst,.start(core_start),.bypass,.transition(trans),.channels,.width,
    .weight_read_address(weight_read_address[l]),.weight_read_enable(weight_read_enable[l]),
    .weight_even(weight_q[0][l]),.weight_odd(weight_q[1][l]),
    .coeff_read_address(coeff_read_address[l]),.coeff_read_enable(coeff_read_enable[l]),
    .b_even(bias_q[0][l]),.b_odd(bias_q[1][l]),.m_even(mul_q[0][l]),.m_odd(mul_q[1][l]),
    .s_even(shift_q[0][l]),.s_odd(shift_q[1][l]),
    .in_valid(in_valid[l]),.in_ready(in_ready[l]),.in_data(in_data[l]),
    .out_valid(out_valid[l]),.out_ready(out_ready[l]),.out_data(out_data[l]),
    .skip_valid(skip_valid[l]),.skip_ready(skip_ready[l]),.skip_data(skip_data[l]),
    .scale_req_valid(scale_req_valid[l]),.scale_req_ready(scale_req_ready[l]),
    .scale_req_value(scale_req_value[l]),.scale_req_multiplier(scale_req_multiplier[l]),.scale_req_shift(scale_req_shift[l]),
    .scale_rsp_valid(scale_rsp_valid[l]),.scale_rsp_ready(scale_rsp_ready[l]),.scale_rsp_data(scale_rsp_data[l]),
    .done(core_done[l]),.busy(core_busy[l]),.trace(trace[l]));
 end
 always_ff @(posedge clk) begin
   done<=0;
   case(state)
    IDLE: if(start) begin
      busy<=1;error<=0;finished<=0;field<=0;word_pos<=0;weight_tap<=0;weight_channel<=0;weight_pair_base<=0;
      bypass<=transition_stage==2||(K==3&&transition_stage==1);
      trans<=K==7&&transition_stage==1;
      channels<=transition_stage==1?64:transition_stage==2?128:profile==0?128:profile==1?256:64;
      weight_channels<=transition_stage==1?128:profile==0?128:profile==1?256:64;
      width<=transition_stage==1?64:transition_stage==2?32:profile==0?32:profile==1?16:64;
      base<=block_index*(profile==0?21081:profile==1?59705:10985);
      if(transition_stage!=0)begin
        field_base<=0;field_words<=784;
      end else begin
        field_base<=block_index*(profile==0?21081:profile==1?59705:10985)+(K==3?0:(profile==0?144:profile==1?288:72));
        field_words<=K*K*(profile==0?128:profile==1?256:64)/8;
      end
      state<=transition_stage==2||(K==3&&transition_stage==1)?LAUNCH:CMD;
    end
    CMD: if(cmd_valid&&cmd_ready)begin remaining<=cmd_words;burst<=cmd_words;state<=READ;end
    READ: if(data_valid&&data_ready)begin word_q<=data;item<=0;state<=UNPACK;end
    UNPACK: begin
     if(field==0)begin
       if(weight_tap==K*K-1)begin
         weight_tap<=0;weight_channel<=weight_channel+1;
         if(weight_channel[0])weight_pair_base<=weight_pair_base+K*K;
       end else weight_tap<=weight_tap+1;
     end
     if(item==(field==0?7:field==1?1:3))begin
      item<=0;word_pos<=word_pos+1;remaining<=remaining-1;
      if(word_pos+1==field_words)begin
        word_pos<=0;field<=field+1;
        if(field==3)state<=LAUNCH;
        else begin
          state<=CMD;
          field_words<=weight_channels/(field==0?2:4);
          if(trans)field_base<=field==0?784:field==1?848:880;
          else field_base<=base+(channels==128?928:channels==256?1856:464)+
               (field==0?(K==3?0:channels/2):
                field==1?3*channels+(K==3?0:channels/4):
                         3*channels+6*channels/4+(K==3?0:channels/4));
        end
      end else state<=remaining==1?CMD:READ;
    end else item<=item+1;
    end
    LAUNCH:state<=RUN;
    RUN:begin
      finished<=finished|core_done;
      if(&(finished|core_done))begin done<=1;busy<=0;state<=IDLE;end
    end
    default:state<=IDLE;
   endcase
   if(rst)begin state<=IDLE;done<=0;busy<=0;error<=0;finished<=0;field<=0;end
 end
endmodule
