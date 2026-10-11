`timescale 1ns/1ps
module math_direct_tb;
 logic clk=0,rst=1;always #2.5 clk=~clk;
 logic s_valid,s_ready,m_valid,m_ready;logic signed[47:0]s_value;logic signed[31:0]s_multiplier;logic[5:0]s_shift;logic signed[15:0]m_data;
 logic[47:0]vals[12000];logic[31:0]muls[12000];logic[5:0]shifts[12000];logic[15:0]expected[12000];
 int count=0,sent=0,received=0,cycle=0,fd,rc;logic stalled=0;logic[15:0]saved;
 cnn_scale dut(.*);
 always_comb begin
   s_valid=!rst&&sent<count;s_value=vals[sent];s_multiplier=muls[sent];s_shift=shifts[sent];
   m_ready=cycle<2000 || cycle%17>5;
 end
 always @(posedge clk)if(!rst)begin
   cycle<=cycle+1;
   if(stalled&&(!m_valid||m_data!==saved))$fatal(1,"scale output unstable");
   stalled<=m_valid&&!m_ready;saved<=m_data;
   if(s_valid&&s_ready)sent<=sent+1;
   if(m_valid&&m_ready)begin
     if(m_data!==expected[received])$fatal(1,"direct scale mismatch vector%0d",received);
     received<=received+1;
   end
   if(cycle>10&&cycle<1990&&(!s_ready||!m_valid))$fatal(1,"scale pipeline bubble");
   if(cycle==10&&!m_valid)$fatal(1,"scale latency not10 stages");
   if(cycle<10&&m_valid)$fatal(1,"scale latency too short");
   if(received==count)begin $display("PASS math_direct vectors=%0d latency_stages=10 sustained_II=1",count);$finish;end
   if(cycle>30000)$fatal(1,"direct timeout");
 end
 initial begin
   fd=$fopen("vectors.txt","r");if(!fd)$fatal(1,"vectors missing");
   while(!$feof(fd))begin rc=$fscanf(fd,"%h %h %h %h\n",vals[count],muls[count],shifts[count],expected[count]);if(rc==4)count++;end
   $fclose(fd);repeat(4)@(negedge clk);rst=0;
 end
endmodule
