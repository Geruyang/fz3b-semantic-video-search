`timescale 1ns/1ps
module axi_tile_tb;
 logic clk=0,rst=1,start=0,busy,done;always #5 clk=~clk;
 logic[31:0] base_addr=0,cmd_addr;logic[15:0] tile_count=0;
 logic cmd_valid,cmd_ready=0;logic[5:0] cmd_words;
 logic data_valid=0,data_ready;logic[127:0] data=0;
 logic out_valid,out_ready=0;logic[1023:0] out_data;
 cnn_tile_loader dut(.*);
 integer cycles=0,pending=0,accepted_tiles=0,consumed=0,produced_words=0,command_count=0;
 integer response_rate=1,hold_until=0,cases=0,previous_pop=-1,consecutive=0,max_consecutive=0;
 logic[31:0] bus_word_addr=0,lfsr=32'h3abd7201;
 logic data_hs=0,cmd_stall=0,out_stall=0;
 logic[37:0] held_cmd;logic[1023:0] held_out;
 function automatic logic[127:0] mem_word(input logic[31:0] a);
  mem_word={a^32'h7a89b321,a^32'h910e56bf,a^32'hc45a7320,a^32'h1832dead};
 endfunction
 always @(negedge clk)begin
  cmd_ready=cycles>hold_until-90 && lfsr[3:2]!=0;
  out_ready=cycles>=hold_until && (cases==2 || lfsr[1:0]!=0);
  if(!data_valid || data_hs)begin
   data_valid=pending>0 && (response_rate==1 || cycles%2==0);
   data=mem_word(bus_word_addr);
  end
 end
 always @(posedge clk)begin
  cycles<=cycles+1;
  lfsr<={lfsr[30:0],lfsr[31]^lfsr[21]^lfsr[1]^lfsr[0]};
  data_hs<=data_valid && data_ready;
  if(!rst)begin
   if(cmd_stall && (!cmd_valid || {cmd_addr,cmd_words}!==held_cmd))$fatal(1,"command instability");
   if(out_stall && (!out_valid || out_data!==held_out))$fatal(1,"tile instability");
   if(cmd_valid && cmd_ready)begin
    if(pending!=0)$fatal(1,"multiple outstanding commands");
    if(cmd_addr!==base_addr+32'(accepted_tiles*8))$fatal(1,"command address got%h expected%h",cmd_addr,base_addr+32'(accepted_tiles*8));
    if(cmd_words!==6'(((tile_count-accepted_tiles)>4?4:(tile_count-accepted_tiles))*8))$fatal(1,"burst not maximally batched");
    if(accepted_tiles-consumed+cmd_words/8>4)$fatal(1,"reservation overfill accepted%0d consumed%0d burst%0d",accepted_tiles,consumed,cmd_words);
    accepted_tiles<=accepted_tiles+cmd_words/8;pending<=cmd_words;bus_word_addr<=cmd_addr;command_count<=command_count+1;
   end
   if(data_valid && data_ready)begin
    if(pending<=0)$fatal(1,"unrequested DDR word");
    pending<=pending-1;bus_word_addr<=bus_word_addr+1;produced_words<=produced_words+1;
   end
   if(out_valid && out_ready)begin
    if(consumed>=tile_count)$fatal(1,"excess tile");
    for(integer w=0;w<8;w++)if(out_data[w*128+:128]!==mem_word(base_addr+32'(consumed*8+w)))$fatal(1,"packing tile%0d word%0d got%h expected%h",consumed,w,out_data[w*128+:128],mem_word(base_addr+32'(consumed*8+w)));
    consumed<=consumed+1;
    if(previous_pop==cycles-1)consecutive<=consecutive+1;else consecutive<=1;
    if(previous_pop==cycles-1 && consecutive+1>max_consecutive)max_consecutive<=consecutive+1;else if(max_consecutive==0)max_consecutive<=1;
    previous_pop<=cycles;
   end
   if(done)begin
    if(busy || cmd_valid || pending!=0 || consumed!=tile_count || accepted_tiles!=tile_count || produced_words!=tile_count*8 || out_valid)$fatal(1,"early done / not drained");
   end
   cmd_stall<=cmd_valid && !cmd_ready;held_cmd<={cmd_addr,cmd_words};
   out_stall<=out_valid && !out_ready;held_out<=out_data;
  end else begin cmd_stall<=0;out_stall<=0;end
 end
 task automatic run_case(input integer count,rate);
  integer begun;
  begin
   @(negedge clk);
   if(busy||out_valid)$fatal(1,"not idle before replay");
   base_addr=32'h91000321+32'(cases*997);tile_count=count;response_rate=rate;
   accepted_tiles=0;consumed=0;produced_words=0;command_count=0;previous_pop=-1;consecutive=0;max_consecutive=0;
   pending=0;data_valid=0;data_hs=0;hold_until=cycles+100;begun=cycles;
   start=1;@(negedge clk);start=0;
   wait(done);@(negedge clk);
   if(command_count!=(count+3)/4)$fatal(1,"command count");
   if(count==4 && max_consecutive<4)$fatal(1,"FIFO did not sustain II1 max%0d",max_consecutive);
   $display("TILE CASE count=%0d rate=%0d commands=%0d cycles=%0d max_consecutive=%0d",count,rate,command_count,cycles-begun,max_consecutive);
   @(negedge clk);if(done)$fatal(1,"done not pulse");cases=cases+1;
  end
 endtask
 initial begin
  repeat(4)@(negedge clk);rst=0;
  run_case(1,1);run_case(3,2);run_case(4,1);run_case(7,2);
  run_case(192,1);run_case(768,2);run_case(3072,1);run_case(1,2);run_case(0,1);
  $display("PASS TILE LOADER cases=%0d independent packing/reservation/stall/II1/noreset",cases);$finish;
 end
 initial begin #3000000;$fatal(1,"timeout");end
endmodule

