`timescale 1ns/1ps
module pw1_profile_tb;
 reg clk=0,fast_clk=0,rst=1,fast_rst=1,start=0;
 always #2.5 clk=~clk;
 initial begin #2.5;fast_clk=1;forever #1.25 fast_clk=~fast_clk;end
 wire done,busy;reg[1:0]profile=2,transition_stage=0;reg[4:0]block_index=0;
 reg[1:0]in_valid=0,out_ready=0;wire[1:0]in_ready,out_valid;
 reg signed[15:0]in_data[2];wire signed[15:0]out_data[2];
 wire cmd_valid;reg cmd_ready=0;wire[31:0]cmd_addr;wire[5:0]cmd_words;
 reg data_valid=0;wire data_ready;reg[127:0]data;wire[31:0]trace[2],error;
 cnn_pw1_stage dut(.*);
 integer C,W,OC,p,b,mode,biasbase,gelubase,weightbase,beginidx,geluentries;
 integer inp[2]='{0,0},outp[2]='{0,0},cycles=0,readaddr=0,left=0;
 integer sequence_test=0,pairs=1;integer ideal=0;
 longint state_hist[0:31];longint emit_active_cycles=0,emit_blocked=0,output_blocked=0,input_wait=0,mac_launches=0,weights_wait=0;
 integer expected_addr[0:20000],expected_words[0:20000],expected_cmds=0,seen_cmds=0;
 integer n,k,ch,x,rr,idx,group,l,sum,expected,limit;
 function automatic integer pixel_value(input integer image,input integer row,input integer channel,input integer xx);
  pixel_value=-1-((image+row+channel+xx)%3);
 endfunction
 function automatic[127:0] param_word(input integer a);
  reg[127:0] v;integer q,j,tg,tr,tw,ol,il;
  begin
   v=0;
   if(a>=gelubase&&a<gelubase+(geluentries/8))begin
    for(j=0;j<8;j++)begin q=(a-gelubase)*8+j+beginidx-32768;v[j*16+:16]=16'(q);end
   end else if(a>=weightbase&&a<weightbase+(OC/4)*(C/16)*8)begin
    tg=((a-weightbase)/8)/(C/16);tr=((a-weightbase)/8)%(C/16);tw=(a-weightbase)%8;
    for(j=0;j<8;j++)begin ol=(tw*8+j)/16;il=(tw*8+j)%16;
     v[j*16+:16]=16'((((tg*4+ol)+(tr*16+il))%5)-2);end
   end else if(transition_stage==2)begin
    if(a>=7056&&a<7120)for(j=0;j<2;j++)v[j*64+:64]=64'(42+((a-7056)*2+j)%7);
    if(a>=7120&&a<7152)for(j=0;j<4;j++)v[j*32+:32]=32'd1;
   end else if(transition_stage==0)begin
    if(a>=biasbase+C&&a<biasbase+C+OC/2)
     for(j=0;j<2;j++)v[j*64+:64]=64'(42+((a-biasbase-C)*2+j)%7);
    if(a>=biasbase+3*C+C/2&&a<biasbase+3*C+C/2+OC/4)
     for(j=0;j<4;j++)v[j*32+:32]=32'd1;
   end
   param_word=v;
  end
 endfunction
 always @(negedge clk)if(!rst)begin
  cmd_ready=left==0 && (ideal||(cycles%13!=0));
  data_valid=left!=0 && (ideal||(cycles%11!=0));
  data=param_word(readaddr);
  for(n=0;n<2;n++)begin
   in_valid[n]=inp[n]<(transition_stage==1?131072:2*C*W*pairs)&&(ideal||(cycles%(n==0?7:9)!=0));
   if(transition_stage==1)in_data[n]=pixel_value(n,inp[n]/(128*32),(inp[n]/32)%128,inp[n]%32);
   else in_data[n]=pixel_value(n,inp[n]/(C*W),(inp[n]/W)%C,inp[n]%W);
   out_ready[n]=ideal||((cycles%(n==0?17:19))<11);
  end
 end
 always @(posedge clk)if(!rst)begin
  cycles=cycles+1;
  state_hist[dut.state]++;
  if(dut.emit_active)emit_active_cycles++;
  if(dut.scale_svalid[0]&&!dut.scale_sready[0])emit_blocked++;
  if(out_valid[0]&&!out_ready[0])output_blocked++;
  if(in_ready[0]&&!in_valid[0])input_wait++;
  if(dut.mac_fire)mac_launches++;
  if(dut.state==dut.W_CMD&&!dut.tile_valid)weights_wait++;
  if(cmd_valid&&cmd_ready)begin
   if(seen_cmds>=expected_cmds||cmd_addr!==expected_addr[seen_cmds]||cmd_words!==expected_words[seen_cmds])
    $fatal(1,"PW1 paramcmd mismatch at%0d gotaddr%0d words%0d expectedaddr%0d words%0d",seen_cmds,cmd_addr,cmd_words,expected_addr[seen_cmds],expected_words[seen_cmds]);
   seen_cmds=seen_cmds+1;readaddr=cmd_addr;left=cmd_words;
  end
  else if(data_valid&&data_ready)begin readaddr=readaddr+1;left=left-1;end
  for(integer image=0;image<2;image++)begin
   if(in_valid[image]&&in_ready[image])inp[image]=inp[image]+1;
   if(out_valid[image]&&out_ready[image])begin
    idx=outp[image];
    if(transition_stage==1)expected=pixel_value(image,idx/(128*32),(idx/32)%128,idx%32);
    else begin
     group=(idx%(2*OC*W))/(8*W);rr=(idx/(2*OC*W))*2+(idx%(8*W))/(4*W);l=(idx/W)%4;x=idx%W;ch=group*4+l;
     sum=42+ch%7;
     for(k=0;k<C;k++)sum=sum+pixel_value(image,rr,k,x)*(((ch+k)%5)-2);
     expected=(transition_stage==2&&sum>=0)?0:sum;
    end
    if($signed(out_data[image])!==expected)begin
     $display("FAIL p%0d stage%0d lane%0d index%0d got%0d exp%0d state%0d",profile,transition_stage,image,idx,$signed(out_data[image]),expected,dut.state);$fatal;
    end
    outp[image]=outp[image]+1;
   end
  end
  if(error!=0)$fatal(1,"stage error %h",error);
  if(cycles>1000000)$fatal(1,"timeout state%0d in%0d out%0d",dut.state,inp[0],outp[0]);
  if(start&&busy)start<=0;
  if(outp[0]>=limit&&outp[1]>=limit&&(transition_stage!=1||done))begin
   if(seen_cmds!=expected_cmds||left!=0)$fatal(1,"incomplete command coverage got%0d expected%0d pending%0d",seen_cmds,expected_cmds,left);
   $display("PASS PW1 p%0d stage%0d MAC=%s rowpair outputs=%0d cycles=%0d independent integer oracle",profile,transition_stage,($test$plusargs("FAST")?"fast-cycle-equivalent":"real-UNISIM"),outp[0]+outp[1],cycles);
   $display("PROFILE ideal%0d emit_active%0d emit_blocked%0d output_blocked%0d input_wait%0d mac_launches%0d weights_wait%0d",ideal,emit_active_cycles,emit_blocked,output_blocked,input_wait,mac_launches,weights_wait);
   for(integer st=0;st<32;st++)if(state_hist[st]!=0)$display("STATE %0d cycles%0d",st,state_hist[st]);
   if(sequence_test&&transition_stage==1)begin
    transition_stage=2;gelubase=7184;limit=8192*pairs;start<=1;make_commands();
    for(integer image=0;image<2;image++)begin inp[image]=0;outp[image]=0;end
   end else $finish;
  end
 end
 task automatic add_command(input integer a,input integer words);
  expected_addr[expected_cmds]=a;expected_words[expected_cmds]=words;expected_cmds=expected_cmds+1;
 endtask
 task automatic make_commands;
  integer f,offset,words,pos,len,row_pair;
  begin
   expected_cmds=0;seen_cmds=0;
   if(transition_stage!=1)begin
    for(f=0;f<3;f=f+1)begin
     words=f==0?OC/2:OC/4;
     if(transition_stage==2)offset=f==0?7056:f==1?7120:7152;
     else offset=biasbase+(f==0?C:3*C+C/2)+(f==2?6*C/4:0);
     for(pos=0;pos<words;pos=pos+32)begin
      len=(words-pos)<32?(words-pos):32;add_command(offset+pos,len);
     end
    end
   end
   for(pos=0;pos<geluentries/8;pos=pos+1)add_command(gelubase+pos,1);
   if(transition_stage!=1)begin
    words=(OC/4)*(C/16)*8;
    for(row_pair=0;row_pair<pairs;row_pair=row_pair+1)
     for(pos=0;pos<words;pos=pos+32)begin
      len=(words-pos)<32?(words-pos):32;add_command(weightbase+pos,len);
     end
   end
  end
 endtask
 initial begin
  p=2;mode=0;for(integer st=0;st<32;st++)state_hist[st]=0;
  if($value$plusargs("PROFILE=%d",p));if($value$plusargs("STAGE=%d",mode));if($value$plusargs("PAIRS=%d",pairs));if($value$plusargs("IDEAL=%d",ideal));
  sequence_test=mode==3;if(sequence_test)mode=1;
  profile=p;transition_stage=mode;
  C=p==1?256:p==2?64:128;W=p==1?16:p==2?64:32;OC=3*C;
  biasbase=p==1?1856:p==2?464:928;gelubase=p==1?3521:p==2?881:1761;
  weightbase=p==1?10553:p==2?7913:8793;
  beginidx=p==1?1752:p==2?25496:15136;
  geluentries=(p==1?48704:p==2?50240:52936)-beginidx;
  if(mode!=0)begin C=128;W=32;OC=128;beginidx=0;geluentries=32768;gelubase=mode==1?912:7184;weightbase=5008;end
  limit=mode==1?131072:2*OC*W*pairs;make_commands();
  repeat(40)@(negedge clk);rst=0;fast_rst=0;
  @(negedge clk);start=1;@(negedge clk);start=0;
 end
endmodule






