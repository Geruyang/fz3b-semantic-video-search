`timescale 1ns/1ps
module tb_job;
 logic clk=0,rst=1,ap_start=0,ap_ready,ap_done,ap_idle;
 logic [31:0] cfg_profile=0,cfg_block_count=2,preflight_error=0,datapath_error=0;
 logic capture_config,preflight_start,preflight_done=0,fabric_idle=1;
 logic [9:0] stage_start,stage_done=0;
 logic [1:0] profile,transition_stage;logic [4:0] block_index[10];
 logic [31:0] error;logic error_valid;
 integer checks=0;
 always #2.5 clk=~clk;
 cnn_job dut(.*);
 task automatic tick;begin @(posedge clk);#1;end endtask
 task automatic launch_job(input integer p,b);
  begin
   @(negedge clk);cfg_profile=p;cfg_block_count=b;ap_start=1;
   tick();if(!ap_ready||!preflight_start||ap_idle)$fatal(1,"accept handshake");
   @(negedge clk);ap_start=0;cfg_profile=1;cfg_block_count=20;tick();
   @(negedge clk);preflight_done=1;tick();@(negedge clk);preflight_done=0;
  end
 endtask
 task automatic mark_done(input logic[9:0] mask);
  begin @(negedge clk);stage_done=mask;tick();@(negedge clk);stage_done=0;end
 endtask
 task automatic release_fabric;
  begin
   repeat(4)begin tick();if(ap_done||(|stage_start))$fatal(1,"completed before B drain");end
   @(negedge clk);fabric_idle=1;
  end
 endtask
 initial begin
  repeat(3)tick();@(negedge clk);rst=0;
  launch_job(0,2);wait(&stage_start);#1;
  if(profile!=0)$fatal(1,"configuration changed during job");
  mark_done(1);if(stage_start!=1||block_index[0]!=1||block_index[4]!=0)$fatal(1,"independent feed restart");
  mark_done(1);if(stage_start!=0)$fatal(1,"feed beyond final block");
  for(int i=1;i<10;i++)begin
   mark_done(10'b1<<i);
   if(stage_start!=(10'b1<<i)||block_index[i]!=1)$fatal(1,"independent stage restart");
   mark_done(10'b1<<i);
  end
  fabric_idle=0;release_fabric();wait(ap_done);#1;
  if(error!=0||!error_valid||!ap_idle)$fatal(1,"normal completion");checks++;
  tick();
  launch_job(3,1);wait(&stage_start);#1;
  if(transition_stage!=1)$fatal(1,"P3 DW context");
  fabric_idle=0;mark_done('1);release_fabric();wait(&stage_start);#1;
  if(transition_stage!=2)$fatal(1,"P3 PW context");
  for(int i=0;i<10;i++)if(block_index[i]!=0)$fatal(1,"P3 block index");
  fabric_idle=0;mark_done('1);release_fabric();wait(ap_done);#1;
  if(error!=0)$fatal(1,"P3 completion");checks++;
  tick();preflight_error=2;
  launch_job(2,4);wait(ap_done);#1;
  if(error!=2||(|stage_start)||!error_valid)$fatal(1,"preflight rejection");checks++;
  tick();preflight_error=0;
  launch_job(1,1);wait(&stage_start);datapath_error=4;
  fabric_idle=0;mark_done('1);release_fabric();wait(ap_done);#1;
  if(error!=3)$fatal(1,"datapath error drain");checks++;
  $display("JOB_PASS checks=%0d independent_restarts=10",checks);$finish;
 end
 initial begin #100000;$fatal(1,"scheduler timeout");end
endmodule
