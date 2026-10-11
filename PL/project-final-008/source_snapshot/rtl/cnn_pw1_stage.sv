`timescale 1ns/1ps
// Source schedule: pointwise_compute + pointwise_post_expand, A0005 C++ oracle.
// Eight true-dual-port banks per image hold a HCW row pair. Only counters reset.
module cnn_pw1_stage(
 input logic clk,rst,fast_clk,fast_rst,start,
 output logic done,busy,input logic[1:0] profile,
 input logic[4:0] block_index,input logic[1:0] transition_stage,
 input logic[1:0] in_valid,output logic[1:0] in_ready,
 input logic signed[15:0] in_data[2],
 output logic[1:0] out_valid,input logic[1:0] out_ready,
 output logic signed[15:0] out_data[2],
 output logic cmd_valid,input logic cmd_ready,
 output logic[31:0] cmd_addr,output logic[5:0] cmd_words,
 input logic data_valid,output logic data_ready,input logic[127:0] data,
 output logic[31:0] trace[2],output logic[31:0] error
);
 typedef enum logic[4:0] {IDLE,CO_CMD,CO_DATA,G_CMD,G_DATA,G_UNPACK,
   INPUT_PAIR,W_CMD,W_DATA,COMPUTE,DRAIN,EMIT,EMIT_DRAIN,BYPASS} state_t;
 state_t state;
 logic[8:0] c;logic[9:0] oc;logic[6:0] w,y;logic[2:0] row_shift;logic[7:0] group;logic[4:0] reduction;
 logic[31:0] base,bias_base,gelu_base,weight_base;
 logic[15:0] zero_bound,tail_bound,begin_bound,gelu_count,gelu_pos;
 logic[15:0] region_pos,region_words;logic[1:0] field;
 logic[5:0] burst_len,burst_pos,gelu_burst_remaining;logic[2:0] unpack_pos;
 logic[127:0] gelu_word;logic[1023:0] tile_weight;
 (* ram_style="distributed" *) logic[95:0] bias_words[384];
 (* ram_style="distributed" *) logic[127:0] mul_words[192];
 (* ram_style="distributed" *) logic[23:0] shift_words[192];
 logic[13:0] load_count[2];logic[7:0] fetch_z,ret_z;
 logic fetch_valid,emit_active;logic[7:0] emit_group;logic[255:0] fetch_values[2];logic[191:0] fetch_prior[2];
 wire[191:0] accum_prior[2],accum_emit[2];
 wire[6:0] emit_z[2];
 logic[9:0] emit_count[2];logic[17:0] out_count[2];
 logic[1:0] mac_sready,mac_mvalid;logic[191:0] mac_result[2];
 logic[1:0] scale_svalid,scale_sready,scale_mvalid,scale_mready;
 logic signed[47:0] scale_raw[2];logic signed[31:0] scale_mul[2];logic[5:0] scale_shift[2];
 logic signed[15:0] scale_q[2];logic[1:0] gelu_svalid,gelu_sready;
 logic signed[15:0] gelu_q[2];logic gelu_load_valid,gelu_load_ready,gelu_error;
 wire[15:0] gelu_words_remaining=(gelu_count-gelu_pos)>>3;
 wire[31:0] bound_word=bounds(profile,block_index);
 logic tile_start,tile_busy,tile_done,tile_cmd_valid,tile_cmd_ready,tile_data_ready,tile_valid,tile_ready;
 logic[31:0] tile_cmd_addr;logic[5:0] tile_cmd_words;logic[1023:0] prefetched_tile;
 wire metadata_active=(state==CO_CMD||state==CO_DATA||state==G_CMD||state==G_DATA||state==G_UNPACK);
 wire[15:0] pair_tile_count=(oc>>2)*(c>>4);
 cnn_tile_loader weight_loader(.clk(clk),.rst(rst),.start(tile_start),.busy(tile_busy),.done(tile_done),
  .base_addr(weight_base),.tile_count(pair_tile_count),.cmd_valid(tile_cmd_valid),.cmd_ready(tile_cmd_ready),
  .cmd_addr(tile_cmd_addr),.cmd_words(tile_cmd_words),.data_valid(data_valid&&!metadata_active),
  .data_ready(tile_data_ready),.data(data),.out_valid(tile_valid),.out_ready(tile_ready),.out_data(prefetched_tile));
 assign tile_cmd_ready=cmd_ready&&!metadata_active;
 assign tile_ready=state==W_CMD;
 wire folded=transition_stage!=0;
 wire fetch_fire=(state==COMPUTE)&&(!fetch_valid||(&mac_sready))&&(fetch_z<2*w);
 wire mac_fire=fetch_valid&&(&mac_sready);
 wire[9:0] fetch_addr=(fetch_z>=w?10'd256:10'd0)+(reduction<<row_shift)+(fetch_z>=w?fetch_z-w:fetch_z);
 function automatic[31:0] normal_stride(input logic[1:0] p);
  case(p)0:normal_stride=21081;1:normal_stride=59705;default:normal_stride=10985;endcase
 endfunction
 // Bounds generated directly from cnn_v10_gelu.hpp; unknown keys rejected at start.
 function automatic[31:0] bounds(input logic[1:0] p,input logic[4:0] b);
  case({p,b})
7'd0:bounds={16'd52936,16'd15136};
7'd1:bounds={16'd48646,16'd7424};
7'd2:bounds={16'd48845,16'd7109};
7'd3:bounds={16'd53151,16'd1949};
7'd4:bounds={16'd49881,16'd0};
7'd5:bounds={16'd48536,16'd0};
7'd6:bounds={16'd47407,16'd2420};
7'd7:bounds={16'd53999,16'd0};
7'd8:bounds={16'd50477,16'd0};
7'd9:bounds={16'd45132,16'd6159};
7'd10:bounds={16'd49941,16'd4602};
7'd11:bounds={16'd38148,16'd25501};
7'd32:bounds={16'd48704,16'd1756};
7'd33:bounds={16'd51761,16'd4433};
7'd34:bounds={16'd54883,16'd6077};
7'd35:bounds={16'd52628,16'd6559};
7'd36:bounds={16'd53218,16'd8485};
7'd37:bounds={16'd49106,16'd10116};
7'd38:bounds={16'd50628,16'd9466};
7'd39:bounds={16'd56097,16'd11635};
7'd40:bounds={16'd53282,16'd8084};
7'd41:bounds={16'd48134,16'd5675};
7'd42:bounds={16'd56252,16'd0};
7'd43:bounds={16'd53479,16'd292};
7'd44:bounds={16'd56320,16'd4914};
7'd45:bounds={16'd57196,16'd13445};
7'd46:bounds={16'd50287,16'd11670};
7'd47:bounds={16'd50325,16'd17357};
7'd48:bounds={16'd51714,16'd19327};
7'd49:bounds={16'd52132,16'd18908};
7'd50:bounds={16'd59373,16'd19032};
7'd51:bounds={16'd61454,16'd19136};
7'd64:bounds={16'd50236,16'd25496};
7'd65:bounds={16'd55552,16'd16299};
7'd66:bounds={16'd49509,16'd13211};
7'd67:bounds={16'd52328,16'd17193};
  default:bounds=0;
  endcase
 endfunction
 genvar img,bank;
 generate for(img=0;img<2;img++) begin: image
  (* ram_style="distributed" *) logic[191:0] accum_ram[256];
  assign emit_z[img]=(emit_count[img]&(w-1))+((emit_count[img]>>(row_shift+2))<<row_shift);
  assign accum_prior[img]=accum_ram[{group[0],fetch_z[6:0]}];
  assign accum_emit[img]=accum_ram[{emit_group[0],emit_z[img]}];
  always_ff @(posedge clk)if((state==COMPUTE||state==DRAIN)&&mac_mvalid[img])
   accum_ram[{group[0],ret_z[6:0]}]<=mac_result[img];
  for(bank=0;bank<8;bank++) begin: input_bank
   (* ram_style="block" *) logic signed[15:0] ram[1024];
   wire[8:0] load_ch=(load_count[img]>>row_shift)&(c-1);
   wire[6:0] load_x=load_count[img]&(w-1);
   wire[9:0] load_address=(load_ch[0]?10'd512:10'd0)+
     (load_count[img]>=4096?10'd256:10'd0)+((load_ch>>4)<<row_shift)+load_x;
   always_ff @(posedge clk) begin
    if(state==INPUT_PAIR&&in_valid[img]&&in_ready[img]&&load_ch[3:1]==bank)
     ram[load_address]<=in_data[img];
    else if(fetch_fire) begin
     fetch_values[img][(2*bank)*16+:16]<=ram[fetch_addr];

    end
   end
   always_ff @(posedge clk) if(fetch_fire)
    fetch_values[img][(2*bank+1)*16+:16]<=ram[512+fetch_addr];
  end
  cnn_pw_mac mac(.clk(clk),.rst(rst),.fast_clk(fast_clk),.fast_rst(fast_rst),
   .s_valid(fetch_valid&&mac_sready[1-img]),.s_ready(mac_sready[img]),
   .s_values(fetch_values[img]),.s_weights(tile_weight),.s_prior(fetch_prior[img]),
   .m_valid(mac_mvalid[img]),.m_ready(1'b1),.m_result(mac_result[img]));
  cnn_scale scale(.clk(clk),.rst(rst),.s_valid(scale_svalid[img]),.s_ready(scale_sready[img]),
   .s_value(scale_raw[img]),.s_multiplier(scale_mul[img]),.s_shift(scale_shift[img]),
   .m_valid(scale_mvalid[img]),.m_ready(scale_mready[img]),.m_data(scale_q[img]));
  always_comb begin
   scale_raw[img]=$signed(accum_emit[img][(((emit_count[img]>>row_shift))%4)*48+:48]);
   scale_mul[img]=mul_words[emit_group][(((emit_count[img]>>row_shift))%4)*32+:32];
   scale_shift[img]=shift_words[emit_group][(((emit_count[img]>>row_shift))%4)*6+:6];
   scale_svalid[img]=emit_active&&(emit_count[img]<8*w);
   scale_mready[img]=gelu_sready[img];
   gelu_svalid[img]=state==BYPASS?in_valid[img]:scale_mvalid[img];
   gelu_q[img]=state==BYPASS?in_data[img]:scale_q[img];
   in_ready[img]=state==BYPASS?gelu_sready[img]:
     ((state==INPUT_PAIR)&&(load_count[img]<8192));
  end
 end endgenerate
 assign gelu_load_valid=state==G_UNPACK;
 cnn_gelu gelu(.clk(clk),.rst(rst),.load_valid(gelu_load_valid),.load_ready(gelu_load_ready),
  .load_index(gelu_pos),.load_data(gelu_word[unpack_pos*16+:16]),
  .load_last(gelu_pos+1==gelu_count),.mode_folded(folded),
  .compact_begin(begin_bound),.compact_zero(zero_bound),.compact_tail(tail_bound),
  .s_valid(gelu_svalid),.s_ready(gelu_sready),.s_data(gelu_q),
  .m_valid(out_valid),.m_ready(out_ready),.m_data(out_data),.error(gelu_error));
 always_comb begin
  cmd_valid=metadata_active?(state==CO_CMD||state==G_CMD):tile_cmd_valid;
  cmd_words=state==G_CMD?(gelu_words_remaining>=32?6'd32:6'(gelu_words_remaining)):(region_words-region_pos>=32?6'd32:6'(region_words-region_pos));
  cmd_addr=state==G_CMD?gelu_base+(gelu_pos>>3):
   bias_base+(field==0?0:3*c)+(field==2?(6*c/4):0)+
   (field==0?c: c/2)+region_pos;
  if(transition_stage==2&&state==CO_CMD)
   cmd_addr=(field==0?7056:field==1?7120:7152)+region_pos;
  if(!metadata_active)begin cmd_addr=tile_cmd_addr;cmd_words=tile_cmd_words;end
  data_ready=metadata_active?(state==CO_DATA||state==G_DATA):tile_data_ready;
  for(int n=0;n<2;n++)trace[n]=busy?32'h80000031|({25'd0,y}<<8):0;
 end
 always_ff @(posedge clk) begin
  if(rst)begin state<=IDLE;busy<=0;done<=0;error<=0;fetch_valid<=0;emit_active<=0;tile_start<=0;end
  else begin
   done<=0;tile_start<=0;
   if(gelu_error)error<=error|32'h00010000;
   for(int n=0;n<2;n++)begin
    if(state==INPUT_PAIR&&in_valid[n]&&in_ready[n])load_count[n]<=load_count[n]+1;

    if(emit_active&&scale_svalid[n]&&scale_sready[n])emit_count[n]<=emit_count[n]+1;
    if((emit_active||state==BYPASS)&&out_valid[n]&&out_ready[n])out_count[n]<=out_count[n]+1;
   end
   if((state==COMPUTE||state==DRAIN)&&(&mac_mvalid))ret_z<=ret_z+1;
   if(emit_active&&out_count[0]==8*w&&out_count[1]==8*w)emit_active<=0;
   if(mac_fire)fetch_valid<=0;
   if(fetch_fire)begin
    fetch_valid<=1;fetch_z<=fetch_z+1;
    for(int n=0;n<2;n++)for(int l=0;l<4;l++)
     fetch_prior[n][l*48+:48]<=reduction==0?bias_words[group*2+(l>>1)][(l%2)*48+:48]:accum_prior[n][l*48+:48];
   end
   case(state)
   IDLE:if(start)begin
    busy<=1;error<=0;y<=0;group<=0;reduction<=0;field<=0;region_pos<=0;gelu_pos<=0;
    c<=transition_stage==0?(profile==1?256:profile==2?64:128):128;
    oc<=transition_stage==0?(profile==1?768:profile==2?192:384):128;
    row_shift<=transition_stage==0?(profile==1?4:profile==2?6:5):5;
    w<=transition_stage==0?(profile==1?16:profile==2?64:32):32;
    base<=block_index*normal_stride(profile);
    bias_base<=block_index*normal_stride(profile)+(profile==1?1856:profile==2?464:928);
    weight_base<=transition_stage==2?5008:block_index*normal_stride(profile)+(profile==1?10553:profile==2?7913:8793);
    zero_bound<=bound_word[15:0];
    tail_bound<=bound_word[31:16];
    begin_bound<=transition_stage!=0?0:(bounds(profile,block_index)&16'hfff8);
    gelu_count<=transition_stage!=0?32768:
     (((bounds(profile,block_index)>>16)+7)&16'hfff8)-(bounds(profile,block_index)&16'hfff8);
    gelu_base<=transition_stage==1?912:transition_stage==2?7184:
     block_index*normal_stride(profile)+(profile==1?3521:profile==2?881:1761);
    region_words<=transition_stage!=0?64:(profile==1?384:profile==2?96:192);
    burst_len<=32;
    for(int n=0;n<2;n++)begin load_count[n]<=0;out_count[n]<=0;end
    if(transition_stage==1)state<=G_CMD;else state<=CO_CMD;
    if((transition_stage==0&&bounds(profile,block_index)==0)||transition_stage==3)begin
     error<=1;busy<=0;done<=1;state<=IDLE;
    end
   end
   CO_CMD:if(cmd_ready)begin burst_pos<=0;burst_len<=cmd_words;state<=CO_DATA;end
   CO_DATA:if(data_valid)begin
    if(field==0)bias_words[region_pos+burst_pos]<={data[64+:48],data[0+:48]};
    if(field==1)mul_words[region_pos+burst_pos]<=data;
    if(field==2)shift_words[region_pos+burst_pos]<={data[96+:6],data[64+:6],data[32+:6],data[0+:6]};    if(burst_pos+1==burst_len)begin
     if(region_pos+burst_len==region_words)begin
      region_pos<=0;field<=field+1;
      region_words<=oc/4;burst_len<=32;
      state<=field==2?G_CMD:CO_CMD;
     end else begin region_pos<=region_pos+burst_len;state<=CO_CMD;end
    end else burst_pos<=burst_pos+1;
   end
   G_CMD:if(cmd_ready)begin
    // Keep one DDR burst context while publishing each word as eight scalars.
    gelu_burst_remaining<=cmd_words;state<=G_DATA;
   end
   G_DATA:if(data_valid)begin
    gelu_word<=data;unpack_pos<=0;gelu_burst_remaining<=gelu_burst_remaining-1'b1;
    state<=G_UNPACK;
   end   G_UNPACK:if(gelu_load_ready)begin
    gelu_pos<=gelu_pos+1;
    if(gelu_pos+1==gelu_count)begin
     state<=transition_stage==1?BYPASS:INPUT_PAIR;
     if(transition_stage!=1)tile_start<=1;
    end
    else if(unpack_pos==7)state<=gelu_burst_remaining!=0?G_DATA:G_CMD;
    else unpack_pos<=unpack_pos+1;
   end
   INPUT_PAIR:if(load_count[0]==8192&&load_count[1]==8192)state<=W_CMD;
   W_CMD:if(tile_valid)begin
    tile_weight<=prefetched_tile;fetch_z<=0;ret_z<=0;fetch_valid<=0;state<=COMPUTE;
   end   COMPUTE:if(fetch_z==2*w&&!fetch_valid)state<=DRAIN;
   DRAIN:if(ret_z==2*w)begin
    if(reduction+1==c/16)begin
     if(!emit_active)begin
      emit_active<=1;emit_group<=group;
      for(int n=0;n<2;n++)begin emit_count[n]<=0;out_count[n]<=0;end
      reduction<=0;
      if(group+1==oc/4)state<=EMIT_DRAIN;
      else begin group<=group+1;state<=W_CMD;end
     end
    end else begin reduction<=reduction+1;state<=W_CMD;end
   end
   EMIT_DRAIN:if(!emit_active)begin
    group<=0;
    if(y+2==w)begin busy<=0;done<=1;state<=IDLE;end
    else begin y<=y+2;for(int n=0;n<2;n++)load_count[n]<=0;state<=INPUT_PAIR;tile_start<=1;end
   end   BYPASS:if(out_count[0]==128*32*32&&out_count[1]==128*32*32)begin
    busy<=0;done<=1;state<=IDLE;
   end
   default:state<=IDLE;
   endcase
  end
 end
endmodule










