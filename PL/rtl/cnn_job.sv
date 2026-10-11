// One job owns its latched configuration through preflight and all block drains.
module cnn_job (
 input logic clk,rst,ap_start,
 output logic ap_ready,ap_done,ap_idle,
 input logic [31:0] cfg_profile,cfg_block_count,
 output logic capture_config,preflight_start,output logic [9:0] stage_start,
 input logic preflight_done,input logic [31:0] preflight_error,
 input logic [9:0] stage_done,
 input logic fabric_idle,input logic [31:0] datapath_error,
 output logic [1:0] profile,transition_stage,
 output logic [4:0] block_index[10],
 output logic [31:0] error,
 output logic error_valid
);
 typedef enum logic [2:0] {IDLE,CHECK,LAUNCH,RUN,DRAIN,NEXT,FINISH} state_e;
 state_e state;
 logic [31:0] blocks;
 logic [9:0] completed;
 assign ap_idle=state==IDLE;
 assign capture_config=state==IDLE && ap_start;
 always_ff @(posedge clk) begin
  if(rst) begin
   state<=IDLE;profile<=0;transition_stage<=0;blocks<=0;
   for(int i=0;i<10;i++)block_index[i]<=0;
   ap_ready<=0;ap_done<=0;error<=0;error_valid<=0;
   preflight_start<=0;stage_start<=0;completed<=0;
  end else begin
   ap_ready<=0;ap_done<=0;error_valid<=0;preflight_start<=0;stage_start<=0;
   unique case(state)
    IDLE: if(ap_start) begin
     profile<=cfg_profile[1:0];blocks<=cfg_block_count;
     for(int i=0;i<10;i++)block_index[i]<=0;
     transition_stage<=cfg_profile==3?2'd1:2'd0;
     error<=0;ap_ready<=1;preflight_start<=1;state<=CHECK;
    end
    CHECK: if(preflight_done) begin
     error<=preflight_error;
     if(preflight_error!=0)state<=DRAIN;else state<=LAUNCH;
    end
    LAUNCH: begin stage_start<='1;completed<=0;state<=RUN;end
    RUN: begin
     for(int i=0;i<10;i++)if(stage_done[i])begin
      if(profile!=3 && {27'd0,block_index[i]}+1<blocks)begin
       block_index[i]<=block_index[i]+1'b1;stage_start[i]<=1;
      end else completed[i]<=1;
     end
     if(datapath_error!=0)error<=32'd3;
     if(&completed)state<=DRAIN;
    end
    DRAIN: if(fabric_idle)begin
     if(error!=0)state<=FINISH;else state<=NEXT;
    end
    NEXT: begin
     if(profile==3 && transition_stage==1)begin transition_stage<=2;state<=LAUNCH;end
     else state<=FINISH;
    end
    FINISH: begin ap_done<=1;error_valid<=1;state<=IDLE;end
    default:state<=IDLE;
   endcase
  end
 end
endmodule
