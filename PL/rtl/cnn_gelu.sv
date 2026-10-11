// Provisional only. Single-copy canonical TDP tables, independent read ports.
// Address/tag -> synchronous table read -> read-after register -> output. II=1.
module cnn_gelu #(parameter int ENTRIES=56256)(
 input logic clk,rst,load_valid,output logic load_ready,
 input logic [15:0] load_index,input logic signed [15:0] load_data,input logic load_last,
 input logic mode_folded,input logic [15:0] compact_begin,compact_zero,compact_tail,
 input logic [1:0] s_valid,output logic [1:0] s_ready,input logic signed [15:0] s_data[2],
 output logic [1:0] m_valid,input logic [1:0] m_ready,output logic signed [15:0] m_data[2],
 output logic error
);
 localparam int SEGMENTS=(ENTRIES+31)/32;
 (* ram_style="block" *) logic [7:0] low[ENTRIES];
 (* ram_style="block" *) logic signed [15:0] base[SEGMENTS];
 typedef struct packed {
   logic signed [15:0] q;
   logic positive,folded,zero_sel,tail_sel;
 } tag_t;
 tag_t tag0[2],tag1[2],tag2[2];
 logic [1:0] v0,v1,v2,advance,read_enable,read_ok;
 logic [15:0] query_index[2],full_index[2],input_index[2];
 logic [15:0] port_a_low_address;
 logic [10:0] port_a_base_address;
 logic signed [15:0] anchor[2],minimum,maximum,next_min,next_max;
 logic [7:0] low_byte[2],reconstructed_high[2];
 logic signed [15:0] anchor_registered[2];
 logic [7:0] low_registered[2];
 logic signed [15:0] reconstructed[2];
 logic [15:0] expected;
 logic load_fire,segment_commit;
 assign load_ready=!(|v0)&&!(|v1)&&!(|v2)&&!(|m_valid);
 assign load_fire=load_valid&&load_ready;
 assign segment_commit=load_fire&&(load_index[4:0]==31||load_last);
 assign port_a_low_address=load_fire?load_index:query_index[0];
 assign port_a_base_address=segment_commit?load_index[15:5]:query_index[0][15:5];
 always_comb begin
   next_min=minimum;next_max=maximum;
   if(load_index[4:0]==0)begin next_min=load_data;next_max=load_data;end
   else begin
     if(load_data<minimum)next_min=load_data;
     if(load_data>maximum)next_max=load_data;
   end
 end
 always_ff @(posedge clk)begin
   if(rst)begin error<=0;expected<=0;minimum<=0;maximum<=0;end
   else if(load_fire)begin
     if(load_index>=ENTRIES||(load_index!=0&&load_index!=expected))error<=1;
     expected<=load_index+1'b1;minimum<=next_min;maximum<=next_max;
     if(segment_commit&&($signed({next_max[15],next_max})-$signed({next_min[15],next_min}))>17'sd255)error<=1;
   end
 end
 // Port A has ONE address for write/read (READ_FIRST). During loading these
 // old-value read outputs carry no valid query tag and are never consumed.
 always_ff @(posedge clk)begin
   if(!rst&&((load_fire&&load_index<ENTRIES)||read_enable[0]))begin
     if(load_fire)low[port_a_low_address]<=load_data[7:0];
     low_byte[0]<=low[port_a_low_address];
   end
   if(!rst&&((segment_commit&&load_index<ENTRIES)||read_enable[0]))begin
     if(segment_commit)base[port_a_base_address]<=next_min;
     anchor[0]<=base[port_a_base_address];
   end
 end
 // Port B is independent synchronous read-only; no third RAM access exists.
 always_ff @(posedge clk)begin
   if(!rst&&read_enable[1])begin
     low_byte[1]<=low[query_index[1]];
     anchor[1]<=base[query_index[1][15:5]];
   end
 end
 for(genvar p=0;p<2;p++)begin: lookup_ports
   assign advance[p]=!m_valid[p]||m_ready[p];
   assign s_ready[p]=advance[p]&&!load_valid;
   assign full_index[p]={~s_data[p][15],s_data[p][14:0]};
   assign input_index[p]=mode_folded ?
      (s_data[p][15]?full_index[p]:(16'd32768-16'(s_data[p]))) :
      (full_index[p]-compact_begin);
   assign read_enable[p]=advance[p]&&v0[p]&&read_ok[p];
   // Modulo256 reconstruction: carry to high byte iff original low byte is
   // below minimum's low byte. All arithmetic wraps identically to signed16.
   assign reconstructed_high[p]=anchor_registered[p][15:8]+8'(low_registered[p]<anchor_registered[p][7:0]);
   assign reconstructed[p]=$signed({reconstructed_high[p],low_registered[p]});
   always_ff @(posedge clk)begin
     if(rst)begin v0[p]<=0;v1[p]<=0;v2[p]<=0;m_valid[p]<=0;end
     else if(advance[p])begin
       v0[p]<=s_valid[p]&&s_ready[p];v1[p]<=v0[p];v2[p]<=v1[p];m_valid[p]<=v2[p];
       query_index[p]<=input_index[p];read_ok[p]<=input_index[p]<ENTRIES;
       tag0[p].q<=s_data[p];tag0[p].positive<=!s_data[p][15];tag0[p].folded<=mode_folded;
       tag0[p].zero_sel<=mode_folded?s_data[p]==0:full_index[p]<compact_zero;
       tag0[p].tail_sel<=!mode_folded&&full_index[p]>=compact_tail;
       tag1[p]<=tag0[p];
       tag2[p]<=tag1[p];anchor_registered[p]<=anchor[p];low_registered[p]<=low_byte[p];
       if(tag2[p].zero_sel)m_data[p]<=0;
       else if(tag2[p].tail_sel)m_data[p]<=16'sd32767;
       else m_data[p]<=reconstructed[p]+((tag2[p].folded&&tag2[p].positive)?tag2[p].q:16'sd0);
     end
   end
 end
endmodule
