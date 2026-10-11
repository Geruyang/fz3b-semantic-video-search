`timescale 1ns/1ps
module math_gelu_tb;
 logic clk=0,rst=1;always #2.5 clk=~clk;
 logic load_valid=0,load_ready,load_last=0,error,mode_folded=1;
 logic[15:0]load_index=0;logic signed[15:0]load_data=0;
 logic[15:0]compact_begin=10000,compact_zero=10003,compact_tail=11020;
 logic[1:0]s_valid,s_ready,m_valid,m_ready;logic signed[15:0]s_data[2],m_data[2];
 logic[15:0]folded[65536],normal[65536];
 int sent[2]='{0,0},received[2]='{0,0};int cycle=0,phase=0,fd,rc;
 logic running=0;logic[1:0]stalled=0;logic[15:0]saved[2];
 cnn_gelu dut(.*);
 function automatic int table_value(input int i);return -(i/32%100)*2-100+(i%32)*3;endfunction
 always_comb for(int p=0;p<2;p++) begin
   s_valid[p]=running && sent[p]<(phase==2?24:65536);
   s_data[p]=16'(sent[p]-32768);
   m_ready[p]=(cycle+p*2)%13>3;
 end
 always @(posedge clk) if(!rst) begin
   cycle<=cycle+1;
   for(int p=0;p<2;p++)begin
     if(stalled[p]&&(!m_valid[p]||m_data[p]!==saved[p]))$fatal(1,"GELU unstable");
     stalled[p]<=m_valid[p]&&!m_ready[p];saved[p]<=m_data[p];
     if(s_valid[p]&&s_ready[p])sent[p]<=sent[p]+1;
     if(m_valid[p]&&m_ready[p])begin
       if(m_data[p] !== (phase==2?16'(table_value(received[p])):(phase==0?folded[received[p]]:normal[received[p]])))$fatal(1,"GELU mismatch phase%0d port%0d qindex%0d got%h",phase,p,received[p],m_data[p]);
       received[p]<=received[p]+1;
     end
   end
   if(cycle>250000)$fatal(1,"timeout");
 end
 task automatic load_table(input int n);
   for(int i=0;i<n;i++)begin
     @(negedge clk);load_valid=1;load_index=16'(i);load_data=16'(table_value(i));load_last=i==n-1;
     do @(posedge clk);while(!load_ready);
   end
   @(negedge clk);load_valid=0;load_last=0;
 endtask
 initial begin
   fd=$fopen("gelu_vectors.txt","r");if(!fd)$fatal(1,"GELU oracle missing");
   for(int i=0;i<65536;i++)rc=$fscanf(fd,"%h %h\n",folded[i],normal[i]);$fclose(fd);
   repeat(4)@(negedge clk);rst=0;load_table(32768);running=1;
   wait(received[0]==65536&&received[1]==65536);
   @(negedge clk);running=0;mode_folded=0;phase=1;sent[0]=0;sent[1]=0;received[0]=0;received[1]=0;
   load_table(1024);running=1;
   wait(received[0]==65536&&received[1]==65536);
   @(negedge clk);running=0;if(error)$fatal(1,"GELU unexpected load error");
   // A partial final segment must commit, and an invalid span must be rejected.
   phase=2;compact_begin=0;compact_zero=0;compact_tail=24;sent[0]=0;sent[1]=0;received[0]=0;received[1]=0;
   load_table(24);running=1;wait(received[0]==24&&received[1]==24);
   @(negedge clk);running=0;load_valid=1;load_index=0;load_data=-32768;load_last=0;
   @(negedge clk);load_index=1;load_data=32767;load_last=1;
   @(negedge clk);load_valid=0;load_last=0;
   if(!error)$fatal(1,"GELU span rejection missing");
   $display("PASS math_gelu exhaustive_queries=262144 partial_segment=24 span_reject=1");$finish;
 end
endmodule
