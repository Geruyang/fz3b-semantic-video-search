module streams_residual_tb;
 logic clk=0;always #5 clk=~clk;
 logic rst=1,start=0;logic [1:0] profile=1,transition_stage=0;
 logic [4:0] block_index=3;logic [31:0] slot_words=8192;
 wire busy,done;wire [31:0] trace;
 logic in_valid;wire in_ready;logic signed [15:0] in_data;
 wire cmd_valid;logic cmd_ready;wire [31:0] cmd_addr;wire [5:0] cmd_words;
 wire data_valid;logic data_ready;wire [127:0] data;
 logic commit_valid;wire commit_ready;wire ready_valid;logic ready_ready;wire [31:0] ready_token;
 logic release_valid;wire release_ready;
 cnn_residual_store dut(.*);
 integer cycle,sent,words,commands,delay_count,pending,tokens,releases,k,held,commits;
 function automatic logic [15:0] pixel(input integer x);pixel=x*23+7;endfunction
 task automatic run(input bit ideal,input bit pause_consumer=0);
 begin
  transition_stage=0;start=1;
  @(negedge clk);start=0;cycle=0;sent=0;words=0;commands=0;pending=0;delay_count=0;tokens=0;releases=0;held=0;commits=0;
  while(!done) begin
   in_valid=sent<65536&&(ideal||cycle%7!=0);in_data=pixel(sent);
   cmd_ready=ideal||(cycle>19&&cycle%3!=0);data_ready=ideal||cycle%5!=0;commit_valid=pending&&delay_count==0;
   ready_ready=(ideal||cycle%11!=0)&&(!pause_consumer||held>100);
   // Hold all four credits until producer actually stalls at its fifth pair.
   if((pause_consumer?commits==128&&tokens==0:tokens>=4)&&sent==32768)held=held+1;
   release_valid=(pause_consumer&&held<=100)?1:(ideal||held>50)&&releases<tokens&&(ideal||cycle%13==0);
   @(posedge clk);
   if(ideal&&!pause_consumer&&sent>0&&sent<65536&&sent%8192!=0&&!in_ready)$fatal(1,"residual steady burst bubble %0d",sent);
   if(pause_consumer&&tokens==0&&release_ready)$fatal(1,"early release before token acceptance");
   if(pause_consumer&&held>=10&&held<=100)begin
    if(dut.token_level!==3'd4||in_ready||commands!=128||words!=4096)$fatal(1,"four queued committed chunks must fill ring before PW2 resumes");
   end
   if(in_valid&&in_ready)sent=sent+1;
   if(cmd_valid&&cmd_ready)begin
    if(cmd_words!==32||cmd_addr!==16384+((commands/32+24)%4)*1024+(commands%32)*32)$fatal(1,"scratch address cmd %0d",commands);
    if(commands/32>=4&&releases<=commands/32-4)$fatal(1,"overwrite owned chunk");
    commands=commands+1;
   end
   if(data_valid&&data_ready)begin
    for(k=0;k<8;k=k+1)if(data[k*16+:16]!==pixel(words*8+k))$fatal(1,"residual packing");
    words=words+1;if(words%32==0)begin pending=1;delay_count=ideal?0:9;end
   end
   if(commit_valid&&commit_ready)begin pending=0;commits=commits+1;end
   if(ready_valid&&ready_ready)begin
    if(ready_token!==tokens+24||commits<(tokens+1)*32)$fatal(1,"token before B or token ordering");tokens=tokens+1;
   end
   if(release_valid&&release_ready)releases=releases+1;
   if(delay_count>0)delay_count=delay_count-1;
   cycle=cycle+1;if(cycle>200000)$fatal(1,"residual timeout");@(negedge clk);
  end
  if(tokens!=8||releases!=8||words!=8192||(!ideal&&held<50))$fatal(1,"drain failed");
  if(pause_consumer&&held<=100)$fatal(1,"consumer pause gate not exercised");
  $display("PASS residual 8 pairs wrap stalled release cycles=%0d ideal=%0d consumer_pause=%0d",cycle,ideal,pause_consumer);
 end endtask
 initial begin
  in_valid=0;cmd_ready=0;data_ready=0;commit_valid=0;ready_ready=0;release_valid=0;
  repeat(3)@(negedge clk);rst=0;
  run(0);run(1);run(0,1);
  transition_stage=1;start=1;@(negedge clk);start=0;
  if(!done||busy||cmd_valid||in_ready)$fatal(1,"P3 bypass");
  $display("PASS residual P3 bypass");$finish;
 end
endmodule
