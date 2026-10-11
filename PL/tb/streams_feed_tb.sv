module streams_feed_tb;
 logic clk=0;always #5 clk=~clk;
 logic rst=1,start=0;logic [1:0] profile=0,transition_stage=0;
 logic [4:0] block_index=1;logic [31:0] slot_words=16384;
 wire busy,done;wire [31:0] trace;
 wire cmd_valid;logic cmd_ready;wire [31:0] cmd_addr;wire [5:0] cmd_words;
 logic data_valid;wire data_ready;logic [127:0] data;
 wire out_valid;logic out_ready;wire signed [15:0] out_data;
 cnn_feed dut(.*);
 integer cycle,n,pending,word_index,expected_base,total,k;
 function automatic logic [15:0] pixel(input integer x);pixel=x*19+11;endfunction
 task automatic run(input integer stage,input bit ideal=0);
 begin
  @(negedge clk);transition_stage=stage;start=1;cycle=0;n=0;pending=0;word_index=0;
  total=stage==1?32768:16384;expected_base=stage==1?0:slot_words;
  @(negedge clk);start=0;
  while(!done)begin
   cmd_ready=ideal||(cycle>20&&cycle%5!=0);data_valid=pending>0&&(ideal||cycle%3!=0);out_ready=ideal||cycle%7!=0;
   for(k=0;k<8;k=k+1)data[k*16+:16]=pixel(word_index*8+k);
   @(posedge clk);
   if(ideal&&n>0&&n<total*8&&!out_valid)$fatal(1,"feed steady-state bubble pixel=%0d",n);
   if(cmd_valid&&cmd_ready) begin
    if(cmd_addr!==expected_base+word_index||cmd_words!==32)$fatal(1,"feed address");pending=32;
   end
   if(data_valid&&data_ready)begin pending=pending-1;word_index=word_index+1;end
   if(out_valid&&out_ready)begin if(out_data!==pixel(n))$fatal(1,"feed endian %0d",n);n=n+1;end
   cycle=cycle+1;if(cycle>1000000)$fatal(1,"feed timeout");@(negedge clk);
  end
  if(n!=total*8||pending!=0)$fatal(1,"feed early done");
  $display("PASS feed stage=%0d words=%0d cycles=%0d ideal=%0d",stage,total,cycle,ideal);
 end endtask
 initial begin repeat(3)@(negedge clk);rst=0;run(0);run(1);run(2);run(0,1);$finish;end
endmodule
