// Fair packet-level arbitration; no tag reuse until complete.
module cnn_write_router #(parameter int N=3)(
input logic clk,rst,
 input logic [N-1:0] cmd_valid, output logic [N-1:0] cmd_ready,
 input logic [31:0] cmd_addr [N], input logic [5:0] cmd_words [N],
 output logic m_cmd_valid,input logic m_cmd_ready,
 output logic [31:0] m_cmd_addr,output logic [5:0] m_cmd_words,
 input logic [N-1:0] data_valid,output logic [N-1:0] data_ready,
 input logic [127:0] data [N],output logic m_data_valid,input logic m_data_ready,
 output logic [127:0] m_data,
 output logic [N-1:0] commit_valid,input logic [N-1:0] commit_ready,
 input logic m_commit_valid,output logic m_commit_ready);
 localparam int CW=(N<=1)?1:$clog2(N);
 logic [CW-1:0] owner,round_robin,selected;
 logic active, found, grant_hold;
 logic [CW-1:0] grant;
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
  data_ready='0;commit_valid='0;m_data_valid=0;m_data='0;m_commit_ready=0;
  if(active) begin
   m_data_valid=data_valid[owner];m_data=data[owner];data_ready[owner]=m_data_ready;
   commit_valid[owner]=m_commit_valid;m_commit_ready=commit_ready[owner];
  end
 end
 always_ff @(posedge clk) begin
  if(rst) begin owner<=0;round_robin<=0;active<=0;grant_hold<=0;grant<=0;end
  else begin
   if(!active && found && !m_cmd_ready && !grant_hold) begin grant_hold<=1;grant<=selected;end
   if(m_cmd_valid && m_cmd_ready) begin
    owner<=selected;active<=1;grant_hold<=0;
    round_robin<=(selected==N-1)?CW'(0):selected+1'b1;
   end
   if(active && m_commit_valid && m_commit_ready) active<=0;
 end
 end
endmodule
