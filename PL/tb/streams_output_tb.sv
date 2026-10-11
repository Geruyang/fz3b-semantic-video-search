module streams_output_tb;
 logic clk=0;always #5 clk=~clk;
 logic rst=1,start=0;logic [1:0] profile=1,transition_stage=0;
 logic [4:0] block_index=0;logic [31:0] slot_words=8192;
 wire busy,done;wire [31:0] trace;
 logic in_valid=0;wire in_ready;logic signed [15:0] in_data;
 wire cmd_valid;logic cmd_ready=0;wire [31:0] cmd_addr;wire [5:0] cmd_words;
 wire data_valid;logic data_ready=0;wire [127:0] data;
 logic commit_valid=0;wire commit_ready;
 wire row_commit_valid;wire [5:0] row_commit_index;
 wire [4:0] row_commit_block;
 cnn_output dut(.*);
 integer sent,commands,received,cycle,delay_count,pending,burst_len,burst_pos;
 integer width,groups,expected_addr,rr,g,y,k,chunk,remaining_words,rows;
 logic [63:0] rows_seen;
 logic previous_commit;integer previous_row,previous_end;
 function automatic logic [15:0] pixel(input integer n);pixel=n*17+9;endfunction
 task automatic run(input integer p,input integer stage,input integer slot,input bit ideal=0,input bit odd_block=0);
 begin
  @(negedge clk);profile=p;transition_stage=stage;slot_words=slot;block_index=odd_block;start=1;
  sent=0;commands=0;received=0;cycle=0;pending=0;delay_count=0;burst_pos=0;
  width=stage!=0?32:p==0?32:p==1?16:64;groups=4096/width/4;
  remaining_words=stage!=0?16384:slot;
  rows=0;rows_seen=0;previous_commit=0;previous_row=0;previous_end=0;
  @(negedge clk);start=0;block_index=5'd31; // Event epoch must use idle-start context.
  while(!done) begin
   in_valid=sent<remaining_words*8 && (ideal||cycle%7!=3);in_data=pixel(sent);
   cmd_ready=ideal||(cycle>19 && cycle%5!=0);data_ready=ideal||cycle%4!=0;
   commit_valid=pending && delay_count==0;
   @(posedge clk);
   if(row_commit_valid)begin
    if(row_commit_block!=={4'b0,odd_block})$fatal(1,"row block context");
    if(!previous_commit||previous_end!=512||row_commit_index!==previous_row||rows_seen[row_commit_index])$fatal(1,"row commit before B, duplicate or wrong row");
    rows_seen[row_commit_index]=1;rows=rows+1;
   end
   previous_commit=commit_valid&&commit_ready;
   previous_row=(cmd_addr-(stage==2?0:stage==1?slot:odd_block?0:slot))/512;
   previous_end=((cmd_addr-(stage==2?0:stage==1?slot:odd_block?0:slot))%512)+cmd_words;
   if(ideal&&sent<remaining_words*8&&!in_ready)$fatal(1,"output steady-state bubble pixel=%0d",sent);
   if(in_valid&&in_ready) sent=sent+1;
   if(cmd_valid&&cmd_ready) begin
    chunk=stage==1?32:width/2;
    rr=commands%2;g=(commands/2)%groups;y=(commands/(2*groups))*2;
    expected_addr=stage==1?slot+commands*32:(stage==2?0:odd_block?0:slot)+(y+rr)*512+g*chunk;
    if(cmd_addr!==expected_addr || cmd_words!==chunk) $fatal(1,"scatter addr cmd=%0d got=%0d exp=%0d len=%0d",commands,cmd_addr,expected_addr,cmd_words);
    burst_len=cmd_words;burst_pos=0;commands=commands+1;
   end
   if(data_valid&&data_ready) begin
    for(k=0;k<8;k=k+1) if(data[k*16+:16]!==pixel(received*8+k)) $fatal(1,"packing word=%0d lane=%0d",received,k);
    received=received+1;burst_pos=burst_pos+1;
    if(burst_pos==burst_len) begin pending=1;delay_count=ideal?0:11;end
   end
   if(commit_valid&&commit_ready) pending=0;
   if(delay_count>0) delay_count=delay_count-1;
   cycle=cycle+1;if(cycle>1000000)$fatal(1,"timeout");
   @(negedge clk);
  end
  // Final row commit and done share the same registered edge.
  if(row_commit_valid)begin
   if(row_commit_block!=={4'b0,odd_block})$fatal(1,"final row block context");
   if(!previous_commit||previous_end!=512||row_commit_index!==previous_row||rows_seen[row_commit_index])$fatal(1,"final row commit invalid");
   rows_seen[row_commit_index]=1;rows=rows+1;
  end
  in_valid=0;commit_valid=0;
  if(pending || received!=remaining_words || sent!=remaining_words*8||rows!=width)$fatal(1,"early done or missing row commits");
  $display("PASS output profile=%0d stage=%0d words=%0d cycles=%0d ideal=%0d",p,stage,received,cycle,ideal);
 end endtask
 initial begin repeat(3)@(negedge clk);rst=0;run(1,0,8192);run(0,0,16384);run(2,0,32768);run(3,1,32768);run(3,2,32768);run(1,0,8192,1);run(0,0,16384,1);run(2,0,32768,1);run(1,0,8192,0,1);run(0,0,16384,0,1);run(2,0,32768,0,1);$finish;end
endmodule
