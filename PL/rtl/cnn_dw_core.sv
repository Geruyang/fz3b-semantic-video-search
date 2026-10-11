// Hand-written banked depthwise engine. HCW order; no full-frame storage.
// Coefficients are broadcast by cnn_dw_stage before start.
module cnn_dw_core #(parameter integer K=3, LANES=4)(
 input logic clk,rst,start,bypass,transition,
 input logic [8:0] channels,input logic [6:0] width,
 output logic [12:0] weight_read_address,output logic weight_read_enable,
 input logic signed [15:0] weight_even,weight_odd,
 output logic [6:0] coeff_read_address,output logic coeff_read_enable,
 input logic signed [47:0] b_even,b_odd,
 input logic signed [31:0] m_even,m_odd,input logic [5:0] s_even,s_odd,
 input logic in_valid,output logic in_ready,input logic signed [15:0] in_data,
 output logic out_valid,input logic out_ready,output logic signed [15:0] out_data,
 output logic skip_valid,input logic skip_ready,output logic signed [15:0] skip_data,
 output logic scale_req_valid,input logic scale_req_ready,
 output logic signed [47:0] scale_req_value,
 output logic signed [31:0] scale_req_multiplier,output logic [5:0] scale_req_shift,
 input logic scale_rsp_valid,output logic scale_rsp_ready,input logic signed [15:0] scale_rsp_data,
 output logic done,busy,output logic [31:0] trace
);
 localparam integer BS=$clog2(LANES), ROWDEPTH=4096/LANES, AW=$clog2(K*ROWDEPTH);
 typedef enum logic [3:0] {IDLE,LOAD,INIT,INITACC,TAPS,WAITMAC,SAVE,EMIT,NEXT,BYPASS,FINISH} state_t;
 state_t state;
 logic [8:0] c,ch,load_ch; logic [6:0] w,ow,step,load_x,xb;
 logic [2:0] slot,ky,kx; logic trans,byp;
 logic [2:0] bank_shift;
 logic [4:0] emit_lane; logic [6:0] pair_emit;
 logic signed [47:0] accum[LANES];
 logic signed [47:0] pair_value[LANES];
 logic signed [15:0] center[LANES];
 logic signed [15:0] bank_q[LANES]; logic [LANES-1:0] bank_mask;
 logic [AW-1:0] read_address[LANES],write_address;
 logic signed [31:0] product_q[LANES];
 logic read_valid,read_last,product_valid,product_last;
 logic signed [4:0] read_dx;
 logic [18:0] produced,consumed,total;
 logic [4:0] credit; logic [3:0] sh,st;
 logic signed [15:0] skip_ring[16];
 logic oh,kh; logic signed [15:0] od,kd;
 integer bank,xx,yy,row_slot,addr,src,pair_channel,ci;
 logic req_fire,rsp_fire,output_fire,skip_fire;
 assign req_fire=scale_req_valid&&scale_req_ready;
 assign rsp_fire=scale_rsp_valid&&scale_rsp_ready;
 assign output_fire=oh&&out_ready;
 assign skip_fire=kh&&skip_ready;
 assign weight_read_address=13'((trans?ch:(ch>>1))*K*K+ky*K+kx);
 assign coeff_read_address=trans?ch[6:0]:ch[7:1];
 assign weight_read_enable=state==TAPS;
 assign coeff_read_enable=state==INIT;
 // P3 channel-pair reorder: 16 single-write banks, four entries each.
 // This holds one output channel pair only (64 accumulators), never an image.
 for(genvar l=0;l<LANES;l=l+1) begin:gen_pair
   (* ram_style="distributed" *) logic signed [47:0] memory[4];
   always_ff @(posedge clk)if(state==SAVE&&trans)memory[xb[4:3]]<=accum[l];
   assign pair_value[l]=memory[pair_emit[4:3]];
 end
 // Fixed generate-bank selects permit one write + one synchronous read per RAM.
 // INIT selects the center; the first TAPS edge captures that prior read.
 for(genvar b=0;b<LANES;b=b+1) begin:gen_rows
   (* ram_style="block" *) logic signed [15:0] memory[K*ROWDEPTH];
   always_ff @(posedge clk) begin
     if(state==LOAD && in_valid && in_ready && load_x[BS-1:0]==b)
       memory[write_address]<=in_data;
     if(state==INIT || state==TAPS) bank_q[b]<=memory[read_address[b]];
   end
 end
 always_comb begin:row_addresses
   integer rs,sx,dx,linear;
   write_address=AW'(slot*ROWDEPTH+(load_ch<<bank_shift)+(load_x>>BS));
   rs=slot+1+(state==INIT?K/2:integer'(ky));if(rs>=K)rs=rs-K;
   dx=integer'(kx)-K/2;
   for(integer b=0;b<LANES;b=b+1)begin
     sx=(trans?2*integer'(xb):integer'(xb))+((b-dx)&(LANES-1))+dx;
     linear=(state==INIT)?(xb>>BS):((sx>=0&&sx<w)?sx>>BS:0);
     read_address[b]=AW'(rs*ROWDEPTH+(ch<<bank_shift)+linear);
   end
 end
 always_comb begin
   in_ready=0; out_valid=oh;out_data=od;skip_valid=kh;skip_data=kd;
   scale_req_valid=state==EMIT && credit<16;
   ci=trans ? ((ch<<1)+(pair_emit>>5)) : ch;
   scale_req_value=trans ? pair_value[{pair_emit[5],pair_emit[2:0]}] : accum[emit_lane];
   scale_req_multiplier=(trans?pair_emit[5]:ch[0])?m_odd:m_even;
   scale_req_shift=(trans?pair_emit[5]:ch[0])?s_odd:s_even;
   scale_rsp_ready=!oh&&!kh;
   if(state==LOAD) in_ready=1;
   if(state==BYPASS) begin
     in_ready=(!oh||out_ready) && produced<total;
     scale_rsp_ready=0;
   end
 end
 always_ff @(posedge clk) begin
   done<=0;
   read_valid<=0;product_valid<=read_valid;product_last<=read_last;
   if(read_valid) for(integer l=0;l<LANES;l=l+1) begin
     src=trans ? ((2*(l%8)+read_dx)&(LANES-1)) : ((l+read_dx)&(LANES-1));
     product_q[l]<= (bank_mask[src] ? bank_q[src] : 16'sd0) *
                   ((trans?(l>=8):ch[0])?weight_odd:weight_even);
   end
   if(product_valid) for(integer l=0;l<LANES;l=l+1)
     accum[l]<=accum[l]+{{16{product_q[l][31]}},product_q[l]};
   if(output_fire) begin oh<=0;consumed<=consumed+1;end
   if(skip_fire) kh<=0;
   if(rsp_fire && !byp) begin
     oh<=1;od<=scale_rsp_data;
     if(K==7&&!trans) begin kh<=1;kd<=skip_ring[sh];end
     sh<=sh+1;
   end
   case({req_fire,rsp_fire&&!byp})
     2'b10:credit<=credit+1;
     2'b01:credit<=credit-1;
     default:;
   endcase
   if(req_fire) begin
     skip_ring[st]<=center[emit_lane];st<=st+1;produced<=produced+1;
   end
   case(state)
     IDLE: if(start) begin
       busy<=1;c<=channels;w<=width;ow<=transition?32:width;
       trans<=transition;byp<=bypass;
       bank_shift<=(width==64?6:width==32?5:4)-BS;
       total<=transition&&!bypass?19'd131072:({12'd0,width}<<12);
       slot<=0;step<=0;ch<=0;load_ch<=0;load_x<=0;xb<=0;
       credit<=0;sh<=0;st<=0;oh<=0;kh<=0;consumed<=0;produced<=0;
       state<=bypass?BYPASS:LOAD;
     end
     LOAD: if(in_valid&&in_ready) begin
       if(load_x==w-1) begin
         load_x<=0;
         if(load_ch==c-1) begin
           load_ch<=0;
           if(step>=K/2 && (!trans||((step-K/2)&1)==0)) begin ch<=0;xb<=0;state<=INIT;end
           else state<=NEXT;
         end else load_ch<=load_ch+1;
       end else load_x<=load_x+1;
     end
     INIT: begin
       state<=INITACC;
     end
     INITACC: begin
       for(integer l=0;l<LANES;l=l+1) begin
         accum[l]<=(trans?(l>=8):ch[0])?b_odd:b_even;
         center[l]<=bank_q[l];
       end
       ky<=0;kx<=0;state<=TAPS;
     end
     TAPS: begin
       yy=step-K/2+ky-K/2;
       for(integer b=0;b<LANES;b=b+1) begin
         xx=(trans?2*xb:xb)+((b-(integer'(kx)-K/2))&(LANES-1))+(integer'(kx)-K/2);
         bank_mask[b]<=yy>=0&&yy<w&&xx>=0&&xx<w;
       end
       read_dx<=integer'(kx)-K/2;read_valid<=1;read_last<=ky==K-1&&kx==K-1;
       if(kx==K-1) begin
         kx<=0;
         if(ky==K-1) state<=WAITMAC;else ky<=ky+1;
       end else kx<=kx+1;
     end
     WAITMAC: if(product_valid&&product_last) state<=SAVE;
     SAVE: begin
       emit_lane<=0;pair_emit<=0;
       if(trans) begin
         if(xb+8<ow) begin xb<=xb+8;state<=INIT;end
         else state<=EMIT;
       end else state<=EMIT;
     end
     EMIT: if(req_fire) begin
       if(trans) begin
         if(pair_emit==63) begin
           pair_emit<=0;xb<=0;
           if(ch==c-1)state<=NEXT;else begin ch<=ch+1;state<=INIT;end
         end else pair_emit<=pair_emit+1;
       end else if(emit_lane==LANES-1) begin
         emit_lane<=0;
         if(xb+LANES<ow)begin xb<=xb+LANES;state<=INIT;end
         else begin
           xb<=0;if(ch==c-1)state<=NEXT;else begin ch<=ch+1;state<=INIT;end
         end
       end else emit_lane<=emit_lane+1;
     end
     NEXT: begin
       slot<=slot==K-1?0:slot+1;step<=step+1;
       if(step==w+K/2-1)state<=FINISH;
       else if(step+1<w)state<=LOAD;
       else if(!trans||((step+1-K/2)&1)==0)begin ch<=0;xb<=0;state<=INIT;end
     end
     BYPASS: begin
       if(in_valid&&in_ready) begin oh<=1;od<=in_data;produced<=produced+1;end
       if(consumed==total&&!oh)state<=FINISH;
     end
     FINISH: if(consumed==total&&!oh&&!kh&&credit==0) begin state<=IDLE;busy<=0;done<=1;end
     default:state<=IDLE;
   endcase
   trace<=busy?{busy,12'd0,step,4'd0,state,4'd0}:32'd0;
   if(rst)begin state<=IDLE;busy<=0;done<=0;oh<=0;kh<=0;credit<=0;read_valid<=0;product_valid<=0;produced<=0;consumed<=0;trace<=0;byp<=0;end
 end
endmodule
