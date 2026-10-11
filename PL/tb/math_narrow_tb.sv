`timescale 1ns/1ps
module math_narrow_tb;
 logic clk=0,rst=1;always #2.5 clk=~clk;
 logic s_valid,s_ready,m_valid,m_ready;
 logic signed[15:0]s_q,s_skip,m_data;
 logic signed[31:0]s_output_multiplier,s_residual_multiplier;
 logic[5:0]s_output_shift,s_residual_shift;
 logic[15:0]qs[20000],skips[20000],expected[20000];
 logic[31:0]om[20000],rm[20000];logic[5:0]os[20000],rs[20000];
 int count=0,sent=0,received=0,cycle=0,fd,rc;
 logic stalled=0;logic[15:0]saved;
 cnn_narrow_post dut(.*);
 always_comb begin
   s_valid=!rst&&sent<count;
   s_q=qs[sent];s_skip=skips[sent];s_output_multiplier=om[sent];s_residual_multiplier=rm[sent];
   s_output_shift=os[sent];s_residual_shift=rs[sent];
   m_ready=cycle<2000||cycle%19>6;
 end
 always @(posedge clk)if(!rst)begin
   cycle<=cycle+1;
   if(stalled&&(!m_valid||m_data!==saved))$fatal(1,"narrow unstable");
   stalled<=m_valid&&!m_ready;saved<=m_data;
   if(s_valid&&s_ready)sent<=sent+1;
   if(m_valid&&m_ready)begin
     if(m_data!==expected[received])$fatal(1,"narrow mismatch vector%0d got%h expected%h",received,m_data,expected[received]);
     received<=received+1;
   end
   if(cycle>11&&cycle<1990&&(!s_ready||!m_valid))$fatal(1,"narrow pipeline bubble");
   if(cycle==11&&!m_valid)$fatal(1,"narrow latency not11 stages");
   if(cycle<11&&m_valid)$fatal(1,"narrow latency too short");
   if(received==count)begin $display("PASS math_narrow vectors=%0d latency_stages=11 sustained_II=1",count);$finish;end
   if(cycle>40000)$fatal(1,"narrow timeout");
 end
 initial begin
   fd=$fopen("narrow_vectors.txt","r");if(!fd)$fatal(1,"narrow vectors missing");
   while(!$feof(fd))begin rc=$fscanf(fd,"%h %h %h %h %h %h %h\n",qs[count],skips[count],om[count],rm[count],os[count],rs[count],expected[count]);if(rc==7)count++;end
   $fclose(fd);repeat(4)@(negedge clk);rst=0;
 end
endmodule
