`timescale 1ns/1ps
module dw_tb;
 parameter K=7;localparam LANES=K==7?16:4;
 logic clk=0;always #2.5 clk=~clk;
 logic rst=1,start=0,done,busy;logic [1:0] profile,transition_stage;logic[4:0] block_index;
 logic [1:0] in_valid,in_ready,out_valid,out_ready,skip_valid,skip_ready;
 logic signed [15:0] in_data[2],out_data[2],skip_data[2];
 logic cmd_valid,cmd_ready,data_valid,data_ready;logic[31:0]cmd_addr;logic[5:0]cmd_words;logic[127:0]data;
 logic[1:0]scale_req_valid,scale_req_ready,scale_rsp_valid,scale_rsp_ready;
 logic signed[47:0]scale_req_value[2];logic signed[31:0]scale_req_multiplier[2];logic[5:0]scale_req_shift[2];
 logic signed[15:0]scale_rsp_data[2];logic[31:0]trace[2],error;
 cnn_dw_stage #(.K(K),.LANES(LANES)) dut(.*);
 integer ic,iw,oc,ow,total_in,total_out,base,bias_at,mul_at,shift_at,weight_at,weight_count;
 integer sent[2],requested[2],received[2],skipped[2],qh[2],qt[2],qn[2];
 logic signed[15:0] queue[2][16];
 bit held_out[2],held_skip[2],held_req[2],held_cmd=0;
 logic signed[15:0] old_out[2],old_skip[2];logic signed[47:0] old_req[2];
 logic[31:0]old_addr;logic[5:0]old_words;
 integer active=0,reading=0,read_addr=0,read_left=0,cycles=0,jobs=0,checks=0;
 logic[31:0]rng=32'h519cc714;
 function automatic integer pixel(input integer lane,y,c,x);
   if((y+c+x+lane)%29==0)return -32768;
   if((y*3+c+x+lane)%31==0)return 32767;
   pixel=((y*11+c*7+x*3+lane*5)%17)-8;
 endfunction
 function automatic integer weight(input integer c,t);
   if((c+t)%19==0)return -32768;
   if((c*2+t)%23==0)return 32767;
   weight=((c*3+t*2)%5)-2;
 endfunction
 function automatic longint bvalue(input integer c);
   if(c%17==0)return -(64'sd1<<40)+7;
   if(c%13==0)return (64'sd1<<39)-9;
   bvalue=(c%7)-3;
 endfunction
 function automatic longint expected(input integer lane,index);
   integer y,c,x,yy,xx,cin,tx,ty;longint a;
   y=index/(oc*ow);c=(index/ow)%oc;x=index%ow;
   if(transition_stage==2||(transition_stage==1&&K==3))return pixel(lane,y,c,x);
   cin=transition_stage==1?c/2:c;a=bvalue(c);
   for(ty=0;ty<K;ty=ty+1)for(tx=0;tx<K;tx=tx+1)begin
     yy=(transition_stage==1?2*y:y)+ty-K/2;
     xx=(transition_stage==1?2*x:x)+tx-K/2;
     if(yy>=0&&yy<iw&&xx>=0&&xx<iw)a=a+64'(pixel(lane,yy,cin,xx))*64'(weight(c,ty*K+tx));
   end
   return a;
 endfunction
 function automatic integer center_value(input integer lane,index);
   return pixel(lane,index/(oc*ow),(index/ow)%oc,index%ow);
 endfunction
 // Test-only scale oracle: exact signed division with nearest-even at shift 1.
 function automatic integer quant(input longint value);
   longint mag,q;bit neg;
   neg=value<0;mag=neg?-value:value;q=mag>>1;
   if((mag&1)&&(q&1))q=q+1;
   if(neg)q=-q;
   if(q>32767)q=32767;if(q< -32767)q=-32767;return q;
 endfunction
 function automatic logic[127:0] param_word(input integer addr);
   logic[127:0] v;integer off,n;
   v=0;
   if(addr>=weight_at&&addr<weight_at+weight_count/8)begin
     for(integer k=0;k<8;k=k+1)begin n=(addr-weight_at)*8+k;v[k*16+:16]=weight(n/(K*K),n%(K*K));end
   end else if(addr>=bias_at&&addr<bias_at+oc/2)begin
     for(integer k=0;k<2;k=k+1) v[k*64+:64]=64'(bvalue((addr-bias_at)*2+k));
   end else if(addr>=mul_at&&addr<mul_at+oc/4)begin
     for(integer k=0;k<4;k=k+1)v[k*32+:32]=32'd3;
   end else if(addr>=shift_at&&addr<shift_at+oc/4)begin
     for(integer k=0;k<4;k=k+1)v[k*32+:32]=32'd1;
   end else $fatal(1,"Unexpected DDR word %0d",addr);
   return v;
 endfunction
 always_comb begin
   cmd_ready=!reading&&rng[0];data_valid=reading&&rng[1];data=param_word_safe(read_addr);
   for(integer l=0;l<2;l=l+1)begin
     in_valid[l]=active&&sent[l]<total_in&&rng[2+l];
     in_data[l]=pixel(l,sent[l]/(ic*iw),(sent[l]/iw)%ic,sent[l]%iw);
     out_ready[l]=rng[4+l];skip_ready[l]=rng[6+l];
     scale_req_ready[l]=qn[l]<16&&rng[8+l];
     scale_rsp_valid[l]=qn[l]!=0;scale_rsp_data[l]=queue[l][qh[l]];
   end
 end
 function automatic logic[127:0] param_word_safe(input integer addr);
   if(reading)return param_word(addr);else return 0;
 endfunction
 always @(posedge clk)begin
   rng<={rng[30:0],rng[31]^rng[21]^rng[1]^rng[0]};cycles<=cycles+1;
   #0;
   if(!rst)begin
     for(integer l=0;l<2;l=l+1)begin
       if($isunknown(trace[l]))$fatal(1,"Unknown DW trace lane%0d busy%0b",l,busy);
     end
     if(held_cmd&&(!cmd_valid||cmd_addr!==old_addr||cmd_words!==old_words))$fatal(1,"Command payload changed under stall");
     held_cmd=cmd_valid&&!cmd_ready;old_addr=cmd_addr;old_words=cmd_words;
     if(cmd_valid&&cmd_ready)begin reading=1;read_addr=cmd_addr;read_left=cmd_words;end
     else if(data_valid&&data_ready)begin read_addr=read_addr+1;read_left=read_left-1;if(read_left==0)reading=0;end
     for(integer l=0;l<2;l=l+1)begin
       if(held_out[l]&&(!out_valid[l]||out_data[l]!==old_out[l]))$fatal(1,"Output payload changed under stall");
       if(held_skip[l]&&(!skip_valid[l]||skip_data[l]!==old_skip[l]))$fatal(1,"Skip payload changed under stall");
       if(held_req[l]&&(!scale_req_valid[l]||scale_req_value[l]!==old_req[l]))$fatal(1,"Scale request changed under stall");
       held_out[l]=out_valid[l]&&!out_ready[l];held_skip[l]=skip_valid[l]&&!skip_ready[l];held_req[l]=scale_req_valid[l]&&!scale_req_ready[l];
       old_out[l]=out_data[l];old_skip[l]=skip_data[l];old_req[l]=scale_req_value[l];
       if(in_valid[l]&&in_ready[l])sent[l]=sent[l]+1;
       if(out_valid[l]&&out_ready[l])begin
         if(out_data[l]!==16'((transition_stage!=0&&(K==3||transition_stage==2))?expected(l,received[l]):quant(3*expected(l,received[l]))))
           $fatal(1,"K%0d job%0d lane%0d output%0d got%0d expected%0d",K,jobs,l,received[l],out_data[l],quant(3*expected(l,received[l])));
         received[l]=received[l]+1;checks=checks+1;
       end
       if(skip_valid[l]&&skip_ready[l])begin
         if(K!=7||transition_stage!=0)$fatal(1,"Unexpected skip");
         if(skip_data[l]!==16'(center_value(l,skipped[l])))$fatal(1,"Skip mismatch index%0d",skipped[l]);
         skipped[l]=skipped[l]+1;checks=checks+1;
       end
       if(scale_rsp_valid[l]&&scale_rsp_ready[l])begin qh[l]=(qh[l]+1)%16;qn[l]=qn[l]-1;end
       if(scale_req_valid[l]&&scale_req_ready[l])begin
         if(scale_req_value[l]!==48'(expected(l,requested[l])))
           $fatal(1,"Accumulator mismatch K%0d job%0d lane%0d index%0d got%0d expected%0d",K,jobs,l,requested[l],scale_req_value[l],expected(l,requested[l]));
         if(scale_req_multiplier[l]!==32'sd3||scale_req_shift[l]!==6'd1)$fatal(1,"Coefficient mismatch");
         queue[l][qt[l]]=quant(scale_req_value[l]*3);qt[l]=(qt[l]+1)%16;qn[l]=qn[l]+1;requested[l]=requested[l]+1;
       end
     end
     if(cycles>15000000)$fatal(1,"Timeout");
   end
 end
 task automatic run(input integer p,t,b);
   @(negedge clk);profile=p;transition_stage=t;block_index=b;
   ic=t==1?64:t==2?128:p==0?128:p==1?256:64;
   iw=t==1?64:t==2?32:p==0?32:p==1?16:64;
   oc=t==1&&K==7?128:ic;ow=t==1&&K==7?32:iw;
   total_in=ic*iw*iw;total_out=oc*ow*ow;
   base=b*(p==0?21081:p==1?59705:10985);
   weight_at=t==1?0:base+(K==3?0:9*ic/8);weight_count=K*K*oc;
   bias_at=t==1?784:base+(ic==128?928:ic==256?1856:464)+(K==3?0:ic/2);
   mul_at=t==1?848:base+(ic==128?928:ic==256?1856:464)+3*ic+(K==3?0:ic/4);
   shift_at=t==1?880:base+(ic==128?928:ic==256?1856:464)+3*ic+6*ic/4+(K==3?0:ic/4);
   for(integer l=0;l<2;l=l+1)begin sent[l]=0;requested[l]=0;received[l]=0;skipped[l]=0;qh[l]=0;qt[l]=0;qn[l]=0;end
   active=1;start=1;@(negedge clk);start=0;
   wait(done);@(negedge clk);active=0;jobs=jobs+1;
   for(integer l=0;l<2;l=l+1)begin
     if(sent[l]!=total_in||received[l]!=total_out||qn[l]!=0)$fatal(1,"Incomplete counts");
     if(K==7&&t==0&&skipped[l]!=total_out)$fatal(1,"Incomplete skip");
   end
   if(error)$fatal(1,"Stage error");
   $display("PASS K%0d profile%0d transition%0d block%0d cycles%0d checks%0d",K,p,t,b,cycles,checks);
   repeat(4)@(negedge clk);
   for(integer l=0;l<2;l=l+1)if(trace[l]!==32'd0)$fatal(1,"Nonzero idle trace after done");
 endtask
 initial begin
   profile=1;transition_stage=0;block_index=0;total_in=0;total_out=0;
   for(integer l=0;l<2;l=l+1)begin sent[l]=0;requested[l]=0;received[l]=0;skipped[l]=0;qh[l]=0;qt[l]=0;qn[l]=0;end
   repeat(5)@(negedge clk);rst=0;
   repeat(4)@(negedge clk);
   for(integer l=0;l<2;l=l+1)if(trace[l]!==32'd0)$fatal(1,"Nonzero idle trace after reset");
   run(1,0,2);run(3,1,0);run(3,2,0);run(0,0,1);run(2,0,1);run(1,0,0);
   $display("DW_ALL_PASS K%0d jobs%0d checks%0d cycles%0d",K,jobs,checks,cycles);$finish;
 end
endmodule
