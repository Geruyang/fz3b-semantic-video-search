`timescale 1ns/1ps
module math_scale_tb;
 logic clk=0,rst=1;always #2.5 clk=~clk;
 logic [2:0] req_valid,req_ready,rsp_valid,rsp_ready;
 logic signed [47:0] req_value[3];logic signed [31:0] req_multiplier[3];logic [5:0] req_shift[3];logic signed [15:0] rsp_data[3];
 logic [47:0] vals[12000];logic [31:0] muls[12000];logic [5:0] shifts[12000];logic [15:0] expected[12000];
 int sent[3]='{0,0,0},received[3]='{0,0,0};int count=0,fd,rc,cycle=0,total=0;
 logic [15:0] saved[3];logic [2:0] stalled=0;
 cnn_scale_service dut(.*);
 always_comb begin
   for(int c=0;c<3;c++) begin
     req_valid[c]=!rst && sent[c]<count;
     req_value[c]=vals[sent[c]];req_multiplier[c]=muls[sent[c]];req_shift[c]=shifts[sent[c]];
     rsp_ready[c]=cycle>100 && ((cycle+c*3)%11>3);
   end
 end
 always @(posedge clk) if(!rst) begin
   cycle<=cycle+1;
   for(int c=0;c<3;c++) begin
     if(stalled[c] && (!rsp_valid[c] || rsp_data[c]!==saved[c])) $fatal(1,"unstable response %d",c);
     stalled[c]<=rsp_valid[c]&&!rsp_ready[c];saved[c]<=rsp_data[c];
     if(req_valid[c]&&req_ready[c]) sent[c]<=sent[c]+1;
     if(rsp_valid[c]&&rsp_ready[c]) begin
       if(rsp_data[c]!==expected[received[c]]) $fatal(1,"scale mismatch client%0d vector%0d got%h expected%h",c,received[c],rsp_data[c],expected[received[c]]);
       received[c]<=received[c]+1;
     end
     if(sent[c]-received[c]>16) $fatal(1,"credit exceeded");
     if(cycle==99 && sent[c]!=16) $fatal(1,"credit fill missing %d",sent[c]);
   end
   if(received[0]==count&&received[1]==count&&received[2]==count) begin $display("PASS math_scale vectors=%0d responses=%0d cycles=%0d",count,count*3,cycle);$finish;end
   if(cycle>100000) $fatal(1,"timeout");
 end
 initial begin
   fd=$fopen("vectors.txt","r");if(fd==0)$fatal(1,"vectors missing");
   while(!$feof(fd)) begin rc=$fscanf(fd,"%h %h %h %h\n",vals[count],muls[count],shifts[count],expected[count]);if(rc==4)count++;end
   $fclose(fd);repeat(4)@(negedge clk);rst=0;
 end
endmodule
