`timescale 1ns/1ps
module tb_preflight;
 `include "preflight_golden.svh"
 logic clk=0;always #2.5 clk=~clk;
 logic rst=1,start=0,done,busy;
 logic[31:0] profile,block_count,params_words,slot_words,arena_words,flags,error;
 wire[1:0] cmd_valid,data_ready;logic[1:0]cmd_ready,data_valid;
 wire[31:0]cmd_addr[2];wire[5:0]cmd_words[2];logic[127:0]data[2];
 integer cycle=0,requests=0,tests=0,mode=0,badclient=0;
 integer remaining[2],addr[2];
 logic[38:0]golden_requests[0:20000];
 integer golden_index=0,served=0,job_served=0;
 logic[38:0]actual_request;
 cnn_preflight dut(.*);
 function automatic logic[127:0] memory(input integer client,a);
  integer loc,bl,u,beg,g;logic[127:0]v;
  begin
   v=0;bl=a/stride(profile);loc=a%stride(profile);
   if(profile!=3)begin
    g=gelu_offset(profile);u=((gelu_tail(profile,bl)+7)/8)-(gelu_zero(profile,bl)/8);
    if(client==0 && loc>=g+((u-1)/4)*4 && loc<g+u)v={8{16'd32767}};
   end
   // Negative extrema and exact span 255 exercise the signed balanced tree.
   if(mode==11 && client==0 && loc>=g+4 && loc<g+((u-1)/4)*4)
    for(integer j=0;j<8;j=j+1)v[j*16+:16]=-32768+((loc-g)%4)*64+j*9;
   if(mode==1 && client==badclient && a==bias_offset(profile))v[48]=1;
   if(mode==2 && client==badclient && a==bias_offset(profile)+3*channels(profile)+6*channels(profile)/4)v[31:0]=63;
   if(mode==3 && client==0 && a==gelu_offset(profile)+7031)v=1;
   if(mode==4 && client==0 && a==gelu_offset(profile)+4)v[15:0]=256;
   if(mode==5 && client==0 && a==gelu_offset(profile))v[15:0]=1;
   if(mode==6 && client==0 && a==gelu_offset(profile)+u-1)v[127:112]=0;
   if(mode==7 && client==0 && a==bias_offset(profile)+6*channels(profile)+channels(profile)/2)v[64]=1;
   if(mode==8 && client==0 && a==7184)v[15:0]=256;
   if(mode==9 && client==0 && a==784)v[48]=1;
   if(mode==10 && client==0 && a==7152)v[31:0]=63;
   memory=v;
  end
 endfunction
 always_comb begin
  for(integer j=0;j<2;j=j+1)begin
   cmd_ready[j]=(cycle%5!=0 && remaining[j]==0);
   data_valid[j]=(remaining[j]>0 && cycle%7!=0);
   data[j]=memory(j,addr[j]);
  end
 end
 always @(posedge clk)begin
  cycle<=cycle+1;
  if(rst)begin remaining[0]<=0;remaining[1]<=0;addr[0]<=0;addr[1]<=0;end
  else for(integer j=0;j<2;j=j+1)begin
   if(cmd_valid[j]&&cmd_ready[j])begin
    actual_request={j[0],cmd_addr[j],cmd_words[j]};
    if(golden_index>=gold_end(tests) || actual_request !== golden_requests[golden_index])
     $fatal(1,"REQUEST SCOREBOARD job=%0d command=%0d got=%h expected=%h",tests,golden_index,actual_request,golden_requests[golden_index]);
    golden_index=golden_index+1;
    remaining[j]<=cmd_words[j];addr[j]<=cmd_addr[j];requests<=requests+1;
   end
   if(data_valid[j]&&data_ready[j])begin served=served+1;remaining[j]<=remaining[j]-1;addr[j]<=addr[j]+1;end
  end
 end
 task automatic run(input integer p,b,m,cl,expected,configbad);
  integer timeout,oldrequests;
  begin
   @(negedge clk);profile=p;block_count=b;mode=m;badclient=cl;flags=0;params_words=(p==3?11280:b*stride(p));slot_words=slot_words_for(p);arena_words=2*slot_words+4096;
   case(configbad)1:flags=1;2:params_words=params_words-1;3:slot_words=slot_words-1;4:arena_words=arena_words-1;endcase
   if(golden_index!=gold_start(tests))$fatal(1,"REQUEST SCOREBOARD job start mismatch");
   job_served=served;oldrequests=requests;start=1;@(negedge clk);start=0;timeout=0;
   while(!done && timeout<1000000)begin @(negedge clk);timeout=timeout+1;end
   if(done !== 1'b1 || error !== expected)$fatal(1,"FAIL p=%0d mode=%0d error=%0d expected=%0d timeout=%0d",p,m,error,expected,timeout);
   if(expected==1 && requests!=oldrequests)$fatal(1,"configuration issued read");
   if(golden_index!=gold_end(tests) || served-job_served!=gold_beats(tests))$fatal(1,"REQUEST SCOREBOARD missing region or consumed word job=%0d",tests);
   if(remaining[0]!=0 || remaining[1]!=0)$fatal(1,"undrained completion");
   @(negedge clk);if(done !== 1'b0)$fatal(1,"done not pulse");tests=tests+1;
  end
 endtask
 initial begin
  $readmemh("golden_requests.mem",golden_requests);
  profile=0;block_count=1;params_words=21081;slot_words=16384;arena_words=36864;flags=0;
  // Independent exact legal-count sweep for the multiplier-free config map.
  for(integer p=0;p<4;p=p+1)begin
   for(integer b=1;b<=(p==0?12:p==1?20:p==2?4:1);b=b+1)
    if(cnn_profile_pkg::expected_param_words(p,b) !== b*stride(p))$fatal(1,"CONFIG WORD MAP p=%0d b=%0d",p,b);
   if(cnn_profile_pkg::expected_param_words(p,0) !== 0 || cnn_profile_pkg::expected_param_words(p,32'hffffffff) !== 0)$fatal(1,"CONFIG INVALID MAP");
  end
  repeat(3)@(negedge clk);rst=0;
  run(0,12,0,0,0,0);run(1,20,0,0,0,0);run(2,4,0,0,0,0);run(3,1,0,0,0,0);
  for(integer m=1;m<=7;m=m+1)run(m==5?1:m==6?2:0,1,m,0,2,0);
  run(2,1,1,1,2,0);run(2,1,2,1,2,0);run(3,1,8,0,2,0);run(3,1,9,0,2,0);run(3,1,10,0,2,0);run(3,1,1,1,0,0);
  for(integer q=1;q<=4;q=q+1)run(0,1,0,0,1,q);
  run(0,0,0,0,1,0);run(1,21,0,0,1,0);run(4,1,0,0,1,0);
  run(0,1,11,0,0,0);$display("INDEPENDENT REQUEST COVERAGE PASS commands=%0d consumed_words=%0d",golden_index,served);$display("PREFLIGHT PASS tests=%0d requests=%0d cycles=%0d",tests,requests,cycle);$finish;
 end
endmodule


