// Fair packet-level arbitration; no tag reuse until complete.
module cnn_read_router #(parameter int N=3)(
input logic clk,rst,
 input logic [N-1:0] cmd_valid, output logic [N-1:0] cmd_ready,
 input logic [31:0] cmd_addr [N], input logic [5:0] cmd_words [N],
 output logic m_cmd_valid,input logic m_cmd_ready,
 output logic [31:0] m_cmd_addr,output logic [5:0] m_cmd_words,
 output logic [N-1:0] data_valid,input logic [N-1:0] data_ready,
 output logic [127:0] data [N],input logic m_data_valid,output logic m_data_ready,
 input logic [127:0] m_data);
 localparam int CW=(N<=1)?1:$clog2(N);
 logic [CW-1:0] owner,round_robin,selected;
 logic active, found, grant_hold;
 logic [CW-1:0] grant;
 logic [5:0] left_words;
 integer candidate;
 always_comb begin
  found=0;selected=round_robin;candidate=0;
  for(int k=0;k<N;k++) begin
   candidate=int'(round_robin)+k;
   if(candidate>=N) candidate=candidate-N;
   if(!found && cmd_valid[candidate]) begin found=1;selected=CW'(candidate);end
  end
  if(grant_hold) begin selected=grant;found=1;end
  cmd_ready='0;m_cmd_valid=found && !active;
  m_cmd_addr=cmd_addr[selected];m_cmd_words=cmd_words[selected];
  if(!active && found) cmd_ready[selected]=m_cmd_ready;
  data_valid='0;m_data_ready=0;
  for(int k=0;k<N;k++) data[k]=m_data;
  if(active) begin data_valid[owner]=m_data_valid;m_data_ready=data_ready[owner];end
 end
 always_ff @(posedge clk) begin
  if(rst) begin owner<=0;round_robin<=0;active<=0;left_words<=0;grant_hold<=0;grant<=0;end
  else begin
   if(!active && found && !m_cmd_ready && !grant_hold) begin grant_hold<=1;grant<=selected;end
   if(m_cmd_valid && m_cmd_ready) begin
    owner<=selected;active<=1;grant_hold<=0;left_words<=m_cmd_words;
    round_robin<=(selected==N-1)?CW'(0):selected+1'b1;
   end
   if(active && m_data_valid && m_data_ready) begin
    left_words<=left_words-1'b1;if(left_words==1) active<=0;
   end
 end
 end
endmodule
