`timescale 1ns/1ps
module tb_row_guard;
 logic clk=0,rst=1,job_start=0;
 logic [1:0] profile=2;
 logic [31:0] slot_words=32768,feed_cmd_addr=32768;
 logic [4:0] feed_block_index=1,writer_block_index=0;
 logic row_commit_valid=0,can_read;
 logic [5:0] row_commit_index=0;
 integer checks=0;
 always #2.5 clk=~clk;
 cnn_row_guard dut(.*);
 task automatic tick;begin @(posedge clk);#1;end endtask
 task automatic check(input bit expected);begin #1;if(can_read!==expected)$fatal(1,"read epoch mismatch feedblock%0d addr%0d",feed_block_index,feed_cmd_addr);checks++;end endtask
 task automatic commit(input integer block_no,row_no);
  begin @(negedge clk);writer_block_index=block_no;row_commit_index=row_no;row_commit_valid=1;tick();@(negedge clk);row_commit_valid=0;end
 endtask
 initial begin
  repeat(3)tick();@(negedge clk);rst=0;
  check(0);commit(0,0);check(1);
  feed_cmd_addr=32768+512;check(0);commit(0,1);check(1);
  feed_block_index=2;feed_cmd_addr=0;check(0);commit(1,0);check(1);
  feed_block_index=3;feed_cmd_addr=32768;check(0);commit(2,0);check(1);
  feed_cmd_addr=32768+512;check(0); // old block0 row1 must not satisfy block3.
  commit(2,1);check(1);
  @(negedge clk);job_start=1;tick();@(negedge clk);job_start=0;check(0);
  feed_block_index=0;feed_cmd_addr=0;check(1);
  profile=3;feed_block_index=4;feed_cmd_addr=1234;check(1);
  // Exercise all legal row counts and both slots without relying on reset tags.
  profile=1;slot_words=8192;
  for(int b=0;b<19;b++)begin
   feed_block_index=b+1;
   for(int y=0;y<16;y++)begin
    feed_cmd_addr=((b+1)&1)*slot_words+y*512;
    check(0);commit(b,y);check(1);
   end
  end
  $display("ROW_GUARD_PASS checks=%0d",checks);$finish;
 end
 initial begin #100000;$fatal(1,"row guard timeout");end
endmodule
