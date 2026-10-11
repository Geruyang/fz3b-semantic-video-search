module cnn_scale_service(
 input logic clk,rst,input logic [2:0] req_valid,output logic [2:0] req_ready,
 input logic signed [47:0] req_value[3],input logic signed [31:0] req_multiplier[3],input logic [5:0] req_shift[3],
 output logic [2:0] rsp_valid,input logic [2:0] rsp_ready,output logic signed [15:0] rsp_data[3]
);
 logic [1:0] rr,selected,tag;
 logic chosen,scale_ready,scale_valid,scale_out_valid,scale_out_ready;
 logic signed [15:0] result;
 logic [4:0] credit[3];
 logic tag_ready,tag_valid;
 logic [5:0] tag_level;
 logic [2:0] fifo_ready;
 logic [4:0] fifo_level[3];
 always_comb begin
   selected=rr;chosen=0;req_ready='0;
   for(int d=0;d<3;d++) begin
     if(!chosen && req_valid[(int'(rr)+d)%3] && credit[(int'(rr)+d)%3]<16) begin
       selected=2'((int'(rr)+d)%3);chosen=1;
     end
   end
   scale_valid=chosen && tag_ready;
   if(chosen) req_ready[selected]=scale_ready && tag_ready;
 end
 cnn_scale arithmetic(.clk,.rst,.s_valid(scale_valid),.s_ready(scale_ready),.s_value(req_value[selected]),.s_multiplier(req_multiplier[selected]),.s_shift(req_shift[selected]),.m_valid(scale_out_valid),.m_ready(scale_out_ready),.m_data(result));
 cnn_fifo #(.WIDTH(2),.DEPTH(48)) tags(.clk,.rst,.s_valid(scale_valid&&scale_ready),.s_ready(tag_ready),.s_data(selected),.m_valid(tag_valid),.m_ready(scale_out_valid&&scale_out_ready),.m_data(tag),.level(tag_level));
 assign scale_out_ready=tag_valid && fifo_ready[tag];
 for(genvar c=0;c<3;c++) begin: clients
   cnn_fifo #(.WIDTH(16),.DEPTH(16)) responses(.clk,.rst,.s_valid(scale_out_valid&&tag_valid&&tag==c),.s_ready(fifo_ready[c]),.s_data(result),.m_valid(rsp_valid[c]),.m_ready(rsp_ready[c]),.m_data(rsp_data[c]),.level(fifo_level[c]));
   always_ff @(posedge clk) begin
     if(rst) credit[c]<=0;
     else case({(req_valid[c]&&req_ready[c]),(rsp_valid[c]&&rsp_ready[c])})
       2'b10:credit[c]<=credit[c]+1'b1;
       2'b01:credit[c]<=credit[c]-1'b1;
       default:credit[c]<=credit[c];
     endcase
   end
 end
 always_ff @(posedge clk) begin
   if(rst) rr<=0;
   else if(scale_valid&&scale_ready) rr<= selected==2 ? 0:selected+1'b1;
 end
endmodule
