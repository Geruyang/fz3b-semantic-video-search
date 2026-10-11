`timescale 1ns/1ps
module pw2_tb;

 logic clk,rst,fast_clk,fast_rst,start;
 logic done,busy;
 logic [1:0] profile,transition_stage;
 logic [4:0] block_index;
 logic [31:0] slot_words;
 logic [1:0] in_valid; logic [1:0] in_ready;
 logic signed [15:0] in_data [2];
 logic [1:0] out_valid; logic [1:0] out_ready;
 logic signed [15:0] out_data [2];
 logic cmd_valid; logic cmd_ready;
 logic [31:0] cmd_addr; logic [5:0] cmd_words;
 logic data_valid; logic data_ready; logic [127:0] data;
 logic [1:0] res_cmd_valid; logic [1:0] res_cmd_ready;
 logic [31:0] res_cmd_addr [2]; logic [5:0] res_cmd_words [2];
 logic [1:0] res_data_valid; logic [1:0] res_data_ready;
 logic [127:0] res_data [2];
 logic [1:0] res_ready_valid; logic [1:0] res_ready_ready;
 logic [31:0] res_ready_token [2];
 logic [1:0] res_release_valid; logic [1:0] res_release_ready;
 logic [1:0] scale_req_valid; logic [1:0] scale_req_ready;
 logic signed [47:0] scale_req_value [2];
 logic signed [31:0] scale_req_multiplier [2]; logic [5:0] scale_req_shift [2];
 logic [1:0] scale_rsp_valid; logic [1:0] scale_rsp_ready;
 logic signed [15:0] scale_rsp_data [2];
 logic [31:0] trace [2]; logic [31:0] error
;
 
 cnn_pw2_stage dut(.*);
 initial clk=0;always #2.5 clk=~clk;
 initial fast_clk=0;always #1.25 fast_clk=~fast_clk;
 integer cycle=0,pc_left=0,pc_addr=0,icount[2],ocount[2],rleft[2],raddr[2],qwr[2],qrd[2],tok[2],released[2];
 logic signed [15:0] sq[2][16];
 logic [15:0] expected[0:524287];
 logic [1:0] held_out=0,held_scale=0,held_res=0;
 logic signed [15:0] saved_out[2];logic [85:0] saved_scale[2];logic [37:0] saved_res[2];
 logic held_cmd=0;logic [37:0] saved_cmd;
 always @(posedge clk)begin
  if(rst)begin held_out<=0;held_scale<=0;held_res<=0;held_cmd<=0;end
  else begin
   if(held_cmd&&(!cmd_valid||{cmd_addr,cmd_words}!==saved_cmd))$fatal(1,"command instability");
   held_cmd<=cmd_valid&&!cmd_ready;saved_cmd<={cmd_addr,cmd_words};
   for(integer l=0;l<2;l++)begin
    if(held_out[l]&&(!out_valid[l]||out_data[l]!==saved_out[l]))$fatal(1,"output instability lane%0d",l);
    if(held_scale[l]&&(!scale_req_valid[l]||{scale_req_value[l],scale_req_multiplier[l],scale_req_shift[l]}!==saved_scale[l]))$fatal(1,"scale request instability lane%0d",l);
    if(held_res[l]&&(!res_cmd_valid[l]||{res_cmd_addr[l],res_cmd_words[l]}!==saved_res[l]))$fatal(1,"residual command instability lane%0d",l);
    held_out[l]<=out_valid[l]&&!out_ready[l];saved_out[l]<=out_data[l];
    held_scale[l]<=scale_req_valid[l]&&!scale_req_ready[l];saved_scale[l]<={scale_req_value[l],scale_req_multiplier[l],scale_req_shift[l]};
    held_res[l]<=res_cmd_valid[l]&&!res_cmd_ready[l];saved_res[l]<={res_cmd_addr[l],res_cmd_words[l]};
   end
  end
 end
 integer meta_requests=0,meta_beats=0,meta_field=0,meta_word=0,res_requests[2],res_beats[2],pc_delay=0,res_delay[2];bit coalesce=0;
 integer overlap_capture[2],q_overlap_capture[2],post_stall_remaining[2];bit post_stall_armed[2],long_stall=0;integer mode=0;logic quick=0,cancel_vectors=0;integer quick_pairs=1; integer C=64,W=64,P=2,PB=464,PW=9449,SLOT=32768,B=0,STRIDE=10985; string fixture;
 function automatic integer metadata_span(input integer f);
 metadata_span=f==0?C/2:f==5?1:C/4;
 endfunction
 function automatic integer metadata_base(input integer f);
 case(f)
 0:metadata_base=PB+5*C/2;
 1:metadata_base=PB+3*C+5*C/4;
 2:metadata_base=PB+3*C+6*C/4+5*C/4;
 3:metadata_base=PB+6*C;
 4:metadata_base=PB+6*C+C/4;
 5:metadata_base=PB+6*C+C/2;
 default:metadata_base=-1;
 endcase
 metadata_base=metadata_base+B*STRIDE;
 endfunction
 function automatic integer iv(input integer l,ix);
 integer r,sg,rr0,k,x,ic,y;
 begin r=ix/(32*W)%(3*C/16);sg=ix/(8*W)%4;rr0=ix/(4*W)%2;k=ix/W%4;x=ix%W;ic=r*16+sg*4+k;y=ix/(32*W*(3*C/16))*2+rr0;
 iv=((ic*7+y*13+x*11+l*17)%257-128)*127;end
 endfunction
 function automatic integer sk(input integer l,addr,k);
 integer seq,off,row,ch,x;
 begin seq=(addr-(2*SLOT))/1024;off=(addr-(2*SLOT))%1024;row=off/512;ch=(off%512)*8/W;x=(off%(W/8))*8+k;
 // Ring chunk seq identifies row_pair modulo4; token tracks current full pair.
 sk=(ch*(cancel_vectors?7919:37)+(tok[l]-1-B*(W/2))*2*19+row*19+x*23+l*41)%65536-32768;end
 endfunction
 function automatic logic [127:0] paramword(input integer addr);
 logic [127:0] v;integer f,j,ch,tile,red,g,ic,oc,wi;
 begin v=0;addr=addr-B*STRIDE;
 if(addr>=PW)begin tile=(addr-PW)/8;wi=(addr-PW)%8;red=tile/(C/4);g=tile%(C/4);
 for(integer k=0;k<8;k++)begin oc=g*4+(wi*8+k)/16;ic=red*16+(wi*8+k)%16;v[k*16+:16]=(oc+ic)%3==0?32767:(oc+ic)%3==1?-32767:173;end
 end else if(addr>=PB+6*C)begin
 j=addr-(PB+6*C);
 if(j<C/4)for(integer k=0;k<4;k++)v[k*32+:32]=3;
 else if(j<C/2)for(integer k=0;k<4;k++)v[k*32+:32]=2;
 else begin v[31:0]=-3;v[37:32]=1;end
 end else if(addr>=PB+3*C+6*C/4+5*C/4)begin
 j=addr-(PB+3*C+6*C/4+5*C/4);for(integer k=0;k<4;k++)begin ch=j*4+k;v[k*32+:32]=ch%8==0?0:25;end
 end else if(addr>=PB+3*C+5*C/4)begin
 j=addr-(PB+3*C+5*C/4);for(integer k=0;k<4;k++)begin ch=j*4+k;v[k*32+:32]=ch%8==0?7:ch%8==1?-1:1;end
 end else begin
 j=addr-(PB+5*C/2);for(integer k=0;k<2;k++)begin ch=j*2+k;
 case(ch%4)0:v[k*64+:64]=64'sd274877906944;1:v[k*64+:64]=-64'sd274877906944;2:v[k*64+:64]=31;3:v[k*64+:64]=-33;endcase end
 end paramword=v;end
 endfunction
 function automatic logic signed [15:0] wide(input logic signed [47:0] value,input logic signed [31:0] multiplier,input logic [5:0] sh);
 logic signed [79:0] p;logic [79:0] a,q,rem,h;logic signed [79:0] r;
 begin p=value*multiplier;a=p<0?-p:p;q=a>>sh;rem=a-(q<<sh);h=sh?80'd1<<(sh-1):0;
 if(sh&&(rem>h||(rem==h&&q[0])))q=q+1;r=p<0?-$signed(q):$signed(q);wide=r>32767?32767:r< -32767?-32767:r[15:0];end
 endfunction
 always_comb begin
 cmd_ready=pc_left==0&&(cycle%7!=0);data_valid=pc_left>0&&pc_delay==0&&(cycle%5!=0);data=paramword(pc_addr);
 for(integer l=0;l<2;l++)begin
 in_data[l]=mode?icount[l]^ (l*197):iv(l,icount[l]);
 out_ready[l]=(cycle%(l+5)!=0)&&(post_stall_remaining[l]==0||mode);
 res_cmd_ready[l]=(rleft[l]==0)&&(cycle%(l+4)!=0);
 res_data_valid[l]=(rleft[l]>0)&&res_delay[l]==0&&(cycle%(l+6)!=0);
 for(integer k=0;k<8;k++)res_data[l][k*16+:16]=sk(l,raddr[l],k);
 res_ready_valid[l]=tok[l]<B*(W/2)+W/2;res_ready_token[l]=tok[l];res_release_ready[l]=cycle%(l+7)!=0;
 scale_req_ready[l]=(qwr[l]-qrd[l]<16)&&(cycle%(l+4)!=0);
 scale_rsp_data[l]=sq[l][qrd[l]%16];
 end
 end
 always @(posedge clk)if(!rst)begin
 cycle<=cycle+1;
 if(pc_delay>0)pc_delay<=pc_delay-1;
 for(integer l=0;l<2;l++)if(res_delay[l]>0)res_delay[l]<=res_delay[l]-1;
 if(cmd_valid&&cmd_ready)begin
 pc_left<=cmd_words;pc_addr<=cmd_addr;pc_delay<=coalesce?29:0;
 if(coalesce&&dut.state==1)begin
 if(cmd_addr!=metadata_base(meta_field)+meta_word||cmd_words!=((metadata_span(meta_field)-meta_word)>32?32:(metadata_span(meta_field)-meta_word)))$fatal(1,"metadata burst length/extent");
 if(meta_word+cmd_words==metadata_span(meta_field))begin meta_field<=meta_field+1;meta_word<=0;end
 else meta_word<=meta_word+cmd_words;
 meta_requests<=meta_requests+1;
 end
 end
 if(data_valid&&data_ready)begin pc_left<=pc_left-1;pc_addr<=pc_addr+1;if(dut.state==2)meta_beats<=meta_beats+1;end
 for(integer l=0;l<2;l++)begin
 if(post_stall_remaining[l]>0)post_stall_remaining[l]<=post_stall_remaining[l]-1;
 if(long_stall&&!mode&&!post_stall_armed[l]&&ocount[l]>=128&&out_valid[l])begin post_stall_armed[l]<=1;post_stall_remaining[l]<=l==0?90000:120000;end
 if(dut.state==7&&dut.q_cache_busy&&dut.row_pair!=dut.q_pair_tag)q_overlap_capture[l]<=q_overlap_capture[l]+1;
 if(dut.q_cache_busy&&(dut.q_sent[l]>8192||dut.q_received[l]>8192||dut.q_read_cursor[l]>dut.q_received[l]))$fatal(1,"Qcache prefix/limit lane%0d",l);
 if(!in_valid[l]||in_ready[l])in_valid[l]<= (cycle%(l+3)!=0)&&(icount[l]+(in_valid[l]&&in_ready[l])<(mode?131072:3*C*W*W));
 if(!scale_rsp_valid[l]||scale_rsp_ready[l])scale_rsp_valid[l]<= (cycle%(l+6)!=0)&&(qwr[l]+(scale_req_valid[l]&&scale_req_ready[l])>qrd[l]+(scale_rsp_valid[l]&&scale_rsp_ready[l]));
 if(mode&&(cmd_valid||res_cmd_valid||scale_req_valid||res_release_valid||res_ready_ready))$fatal(1,"P3 illegal normal access");
 if(in_valid[l]&&in_ready[l])begin icount[l]<=icount[l]+1;if(dut.state==7)overlap_capture[l]<=overlap_capture[l]+1;end
 if(res_cmd_valid[l]&&res_cmd_ready[l])begin rleft[l]<=res_cmd_words[l];raddr[l]<=res_cmd_addr[l];res_delay[l]<=coalesce?(l==0?47:83):0;
 if(coalesce)begin
 if(res_cmd_words[l]!=W/2||res_cmd_addr[l]!=2*SLOT+((tok[l]-1)%4)*1024+(res_requests[l]%2)*512+((res_requests[l]%(C/2))/2)*(W/2))$fatal(1,"residual group extent/order lane%0d request%0d",l,res_requests[l]);
 res_requests[l]<=res_requests[l]+1;
 end end
 if(res_data_valid[l]&&res_data_ready[l])begin rleft[l]<=rleft[l]-1;raddr[l]<=raddr[l]+1;res_beats[l]<=res_beats[l]+1;end
 if(res_ready_valid[l]&&res_ready_ready[l])tok[l]<=tok[l]+1;
 if(res_release_valid[l]&&res_release_ready[l])begin released[l]<=released[l]+1;
 if(coalesce&&(res_requests[l]!=(released[l]+1)*(C/2)||res_beats[l]!=(released[l]+1)*1024))$fatal(1,"residual coverage/count lane%0d",l);
 if(l==0)$display("PW2_PAIR profile%0d pair%0d cycle%0d",P,released[l],cycle);end
 if(scale_req_valid[l]&&scale_req_ready[l])begin sq[l][qwr[l]%16]<=wide(scale_req_value[l],scale_req_multiplier[l],scale_req_shift[l]);qwr[l]<=qwr[l]+1;end
 if(scale_rsp_valid[l]&&scale_rsp_ready[l])qrd[l]<=qrd[l]+1;
 if(out_valid[l]&&out_ready[l])begin
 if(out_data[l]!== (mode?16'(ocount[l]^(l*197)):expected[ocount[l]*2+l]))$fatal(1,"PW2 mismatch lane%0d at%0d got%0d expected%0d",l,ocount[l],out_data[l],$signed(expected[ocount[l]*2+l]));
 ocount[l]<=ocount[l]+1;
 end
 end
 if(cycle>5000000)$fatal(1,"timeout");
 end
 initial begin
 coalesce=$test$plusargs("COALESCE");quick=$test$plusargs("QUICK");long_stall=$test$plusargs("LONGSTALL");if($test$plusargs("TWOPAIRS"))quick_pairs=2;cancel_vectors=$test$plusargs("CANCEL");if($test$plusargs("BLOCK1"))B=1;if($test$plusargs("P0"))P=0; if($test$plusargs("P1"))P=1;
 C=P==0?128:P==1?256:64;W=P==0?32:P==1?16:64;PB=P==0?928:P==1?1856:464;PW=P==0?14937:P==1?35129:9449;SLOT=P==0?16384:P==1?8192:32768;STRIDE=P==0?21081:P==1?59705:10985;
 fixture=cancel_vectors?"normal_p2_cancel_expected.hex":$sformatf("normal_p%0d_expected.hex",P);$readmemh(fixture,expected,0,cancel_vectors?4*C*W-1:C*W*W*2-1);rst=1;fast_rst=1;start=0;profile=P;transition_stage=0;block_index=B;slot_words=SLOT;
 for(integer l=0;l<2;l++)begin in_valid[l]=0;scale_rsp_valid[l]=0;overlap_capture[l]=0;q_overlap_capture[l]=0;post_stall_remaining[l]=0;post_stall_armed[l]=0;icount[l]=0;ocount[l]=0;rleft[l]=0;raddr[l]=0;qwr[l]=0;qrd[l]=0;tok[l]=B*(W/2);released[l]=0;res_requests[l]=0;res_beats[l]=0;res_delay[l]=0;end
 repeat(8)@(negedge clk);rst=0;fast_rst=0;start=1;@(negedge clk);start=0;
 if(quick)begin
 wait(released[0]==quick_pairs&&released[1]==quick_pairs);@(negedge clk);
 if(error||ocount[0]!=2*C*W*quick_pairs||ocount[1]!=2*C*W*quick_pairs)$fatal(1,"quick pair mismatch");
 if($test$plusargs("OVERLAP"))begin if(overlap_capture[0]==0||overlap_capture[1]==0)$fatal(1,"NO_OVERLAP capture0=%0d capture1=%0d",overlap_capture[0],overlap_capture[1]);$display("PW2_OVERLAP_PASS capture%0d/%0d",overlap_capture[0],overlap_capture[1]);end
 if($test$plusargs("QOVERLAP"))begin if(q_overlap_capture[0]==0||q_overlap_capture[1]==0)$fatal(1,"NO_Q_RAW_OVERLAP");$display("PW2_Q_RAW_OVERLAP_PASS cycles%0d/%0d",q_overlap_capture[0],q_overlap_capture[1]);end
 if(coalesce)begin
 if(meta_requests!=(C/2+31)/32+4*((C/4+31)/32)+1||meta_beats!=3*C/2+1)$fatal(1,"metadata coverage/count");
 $display("PW2_COALESCE_PASS metadata=%0d beats=%0d residual=%0d/%0d beats=%0d/%0d",meta_requests,meta_beats,res_requests[0],res_requests[1],res_beats[0],res_beats[1]);end
 $display("PW2_QUICK_PAIR_PASS profile%0d pixels%0d cycles%0d",P,ocount[0]*2,cycle);if($test$plusargs("PAIRONLY"))begin $display("PW2_PAIRONLY_PASS");$finish;end
 rst=1;fast_rst=1;pc_left=0;
 for(integer l=0;l<2;l++)begin rleft[l]=0;qwr[l]=0;qrd[l]=0;scale_rsp_valid[l]=0;in_valid[l]=0;post_stall_remaining[l]=0;end
 repeat(8)@(negedge clk);rst=0;fast_rst=0;
 end else begin wait(done);@(negedge clk);
 if(error||ocount[0]!=C*W*W||ocount[1]!=C*W*W||released[0]!=W/2||released[1]!=W/2)$fatal(1,"normal completion mismatch");
 $display("PW2_NORMAL_PASS profile%0d pixels%0d cycles%0d",P,ocount[0]*2,cycle);end
 for(integer stage=1;stage<=2;stage++)begin
 mode=1;transition_stage=stage;
 for(integer l=0;l<2;l++)begin in_valid[l]=0;icount[l]=0;ocount[l]=0;end
 start=1;@(negedge clk);start=0;wait(done);@(negedge clk);
 if(ocount[0]!=131072||ocount[1]!=131072||pc_left!=0||qwr[0]!=qrd[0]||qwr[1]!=qrd[1])$fatal(1,"bypass counts");
 end
 $display("PW2_PASS normal,P3stage1,P3stage2 randomizedstalls cycles%0d",cycle);$finish;
 end
endmodule


