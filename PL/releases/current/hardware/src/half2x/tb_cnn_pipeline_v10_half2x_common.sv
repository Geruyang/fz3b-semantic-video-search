`timescale 1ns/1ps

module tb_cnn_pipeline_v10_half2x_common #(parameter bit REJECT_ONLY = 1'b0);
    import tb_cnn_v10_fixture_pkg::*;

    localparam int NUM_RD = 4;
    localparam int NUM_WR = 2;
    // The body uses a deliberately wide ID container. The generated binding
    // slices/extends the real RTL ID width after HLS freezes the module ports.
    localparam int TB_ID_W = 16;
    localparam int MAX_PARAMS = 1_400_000;
    localparam int MAX_ACT = 262_144;
    localparam int MAX_SLOT = 32_768;
    localparam int GUARD = 8;
    localparam logic [127:0] CANARY =
        128'hd17eca11f00d9876beef4321cafe0123;

    logic clk=0;
    logic fast_clk=1;
    logic rst_n=0;
    logic fast_rst=1;
    logic ap_start=0;
    logic ap_done,ap_idle,ap_ready;
    logic [31:0] protocol_error;
    logic protocol_vld;
    logic [11:0][31:0] trace_value;
    always #2.5 clk=~clk;
    always #1.25 fast_clk=~fast_clk;

    logic [NUM_RD-1:0] rd_arvalid,rd_arready;
    logic [NUM_RD-1:0][63:0] rd_araddr;
    logic [NUM_RD-1:0][TB_ID_W-1:0] rd_arid;
    logic [NUM_RD-1:0][7:0] rd_arlen;
    logic [NUM_RD-1:0][2:0] rd_arsize;
    logic [NUM_RD-1:0][1:0] rd_arburst;
    logic [NUM_RD-1:0] rd_rvalid,rd_rready,rd_rlast;
    logic [NUM_RD-1:0][127:0] rd_rdata;
    logic [NUM_RD-1:0][TB_ID_W-1:0] rd_rid;
    logic [NUM_RD-1:0][1:0] rd_rresp;

    logic [NUM_WR-1:0] wr_awvalid,wr_awready;
    logic [NUM_WR-1:0][63:0] wr_awaddr;
    logic [NUM_WR-1:0][TB_ID_W-1:0] wr_awid;
    logic [NUM_WR-1:0][7:0] wr_awlen;
    logic [NUM_WR-1:0][2:0] wr_awsize;
    logic [NUM_WR-1:0][1:0] wr_awburst;
    logic [NUM_WR-1:0] wr_wvalid,wr_wready,wr_wlast;
    logic [NUM_WR-1:0][127:0] wr_wdata;
    logic [NUM_WR-1:0][15:0] wr_wstrb;
    logic [NUM_WR-1:0] wr_bvalid,wr_bready;
    logic [NUM_WR-1:0][TB_ID_W-1:0] wr_bid;
    logic [NUM_WR-1:0][1:0] wr_bresp;

    logic ctl_awvalid=0,ctl_awready;
    logic [31:0] ctl_awaddr=0;
    logic ctl_wvalid=0,ctl_wready;
    logic [31:0] ctl_wdata=0;
    logic [3:0] ctl_wstrb=4'hf;
    logic ctl_bvalid,ctl_bready=0;
    logic [1:0] ctl_bresp;

`ifdef CNN_V10_BINDING_READY
`include "tb_cnn_v10_generated_binding.svh"
`else
    localparam logic [31:0] V10_CTL_PARAMS1_LO='x,V10_CTL_PARAMS1_HI='x;
    localparam logic [31:0] V10_CTL_PARAMS2_LO='x,V10_CTL_PARAMS2_HI='x;
    localparam logic [31:0] V10_CTL_ACT_A_RD_LO='x,V10_CTL_ACT_A_RD_HI='x;
    localparam logic [31:0] V10_CTL_ACT_A_WR_LO='x,V10_CTL_ACT_A_WR_HI='x;
    localparam logic [31:0] V10_CTL_ACT_B_RD_LO='x,V10_CTL_ACT_B_RD_HI='x;
    localparam logic [31:0] V10_CTL_ACT_B_WR_LO='x,V10_CTL_ACT_B_WR_HI='x;
    localparam logic [31:0] V10_CTL_PROFILE='x,V10_CTL_BLOCKS='x;
    localparam logic [31:0] V10_CTL_PARAMS_WORDS='x,V10_CTL_SLOT_WORDS='x;
    localparam logic [31:0] V10_CTL_ARENA_WORDS='x,V10_CTL_FLAGS='x;
    initial begin
        #1 $fatal(1,"CNN_V10_BINDING_READY is absent; use frozen generated RTL binding");
    end
`endif

    logic [63:0] params1_base=64'h0000_0008_0000_0000;
    logic [63:0] params2_base=64'h0000_0009_0000_0000;
    logic [63:0] act_a_base=64'h0000_0000_4000_0000;
    logic [63:0] act_b_base=64'h0000_0000_6000_0000;
    int unsigned profile,block_count,param_count,slot_count,arena_count,flags;
    int unsigned token_numer=1,token_denom=2,token_burst=32;
    int unsigned b_response_delay=3,stress_mode=0,repeat_launch=0;
    int unsigned second_profile=32'hffff,second_swapped=1;
    logic profile_switch=0;
    logic scoreboard_new_launch=0;
    logic force_pause;
    logic [NUM_RD-1:0] read_client_pause;
    logic [NUM_WR-1:0] write_client_pause;

    logic [NUM_RD-1:0][63:0] read_beats,read_bursts;
    logic [NUM_RD-1:0][63:0] read_backpressure_cycles,read_pause_hit_cycles;
    logic [NUM_WR-1:0][63:0] write_beats,write_bursts;
    logic [NUM_WR-1:0][63:0] write_backpressure_cycles,write_pause_hit_cycles;
    logic [63:0] aggregate_read_beats,aggregate_write_beats;
    logic [63:0] aggregate_budget_beats;

    tb_cnn_v10_shared_ddr #(
        .NUM_RD(NUM_RD),.NUM_WR(NUM_WR),.ADDR_W(64),.DATA_W(128),
        .ID_W(TB_ID_W),.MAX_BURST_BEATS(32),
        .MAX_PARAMS_WORDS(MAX_PARAMS),.MAX_ACT_WORDS(MAX_ACT)
    ) u_ddr (
        .clk(clk),.rst_n(rst_n),.scoreboard_new_launch(scoreboard_new_launch),
        .rd_arvalid(rd_arvalid),.rd_arready(rd_arready),.rd_araddr(rd_araddr),
        .rd_arid(rd_arid),.rd_arlen(rd_arlen),.rd_arsize(rd_arsize),
        .rd_arburst(rd_arburst),.rd_rvalid(rd_rvalid),.rd_rready(rd_rready),
        .rd_rdata(rd_rdata),.rd_rlast(rd_rlast),.rd_rid(rd_rid),.rd_rresp(rd_rresp),
        .wr_awvalid(wr_awvalid),.wr_awready(wr_awready),.wr_awaddr(wr_awaddr),
        .wr_awid(wr_awid),.wr_awlen(wr_awlen),.wr_awsize(wr_awsize),
        .wr_awburst(wr_awburst),.wr_wvalid(wr_wvalid),.wr_wready(wr_wready),
        .wr_wdata(wr_wdata),.wr_wstrb(wr_wstrb),.wr_wlast(wr_wlast),
        .wr_bvalid(wr_bvalid),.wr_bready(wr_bready),.wr_bid(wr_bid),.wr_bresp(wr_bresp),
        .params1_base(params1_base),.params2_base(params2_base),
        .act_a_base(act_a_base),.act_b_base(act_b_base),
        .params_words(param_count),.act_words(arena_count),
        .scratch_word_base(2*slot_count),.scratch_words(TRANSIENT_WORDS),
        .token_numer(token_numer),.token_denom(token_denom),.token_burst(token_burst),
        .write_response_delay(b_response_delay),.force_pause(force_pause),
        .read_client_pause(read_client_pause),.write_client_pause(write_client_pause),
        .read_beats(read_beats),.read_bursts(read_bursts),
        .read_backpressure_cycles(read_backpressure_cycles),
        .read_pause_hit_cycles(read_pause_hit_cycles),
        .write_beats(write_beats),.write_bursts(write_bursts),
        .write_backpressure_cycles(write_backpressure_cycles),
        .write_pause_hit_cycles(write_pause_hit_cycles),
        .aggregate_read_beats(aggregate_read_beats),
        .aggregate_write_beats(aggregate_write_beats),
        .aggregate_budget_beats(aggregate_budget_beats)
    );

    logic [127:0] input_a[0:MAX_SLOT-1],input_b[0:MAX_SLOT-1];
    logic [127:0] expected_a[0:MAX_SLOT-1],expected_b[0:MAX_SLOT-1];
    logic [127:0] early_expected_a[0:MAX_SLOT-1];
    logic [127:0] early_expected_b[0:MAX_SLOT-1];
    string fixture_root,params_file,input_a_file,input_b_file;
    string expected_a_file,expected_b_file,error_kind;
    string early_expected_a_file,early_expected_b_file;

    logic early_enable=0;
    int unsigned early_words_arg=32,early_full_slot_arg=0,early_target_words=0;
    longint unsigned early_aw_base[0:1];
    int unsigned early_aw_beats[0:1],early_aw_position[0:1];
    int unsigned early_checked[0:1];
    logic early_aw_valid[0:1],early_aw_normal[0:1];
    logic early_aw_needs_b[0:1],early_target_b_done[0:1];
    logic early_seen[0:1][0:MAX_SLOT-1];

    longint unsigned cycles=0,launch_cycle=0,done_cycle=0;
    longint unsigned last_b_cycle[0:1];
    longint unsigned trace_active[0:11],trace_first[0:11],trace_last[0:11];
    logic launch_active=0,monitor_new_launch=0,done_seen=0;
    logic protocol_seen=0,expected_error_seen=0;
    logic [31:0] expected_error_current=0,observed_protocol_error=0;
    longint unsigned start_read[0:3],start_write[0:1],start_budget;
    longint unsigned start_rpause[0:3],start_wpause[0:1];
    longint unsigned start_residual_write_bursts[0:1];
    longint unsigned start_residual_read_bursts[0:1];
    longint unsigned start_residual_write_wraps[0:1];
    longint unsigned start_residual_read_wraps[0:1];
    longint unsigned mon_ar[0:3],mon_r[0:3];
    longint unsigned mon_aw[0:1],mon_w[0:1],mon_b[0:1];
    longint unsigned last_progress_cycle;
    logic [11:0][31:0] last_trace_value;
    logic any_axi_handshake,known_trace_change;

    always_comb begin
        any_axi_handshake=|(rd_arvalid&rd_arready) ||
                          |(rd_rvalid&rd_rready) ||
                          |(wr_awvalid&wr_awready) ||
                          |(wr_wvalid&wr_wready) ||
                          |(wr_bvalid&wr_bready);
        known_trace_change=1'b0;
        for (int t=0;t<12;t++) begin
            // ap_none traces may be X until their producer first writes them.
            // Only a fully known value transition is evidence of progress.
            if (!$isunknown(trace_value[t]) &&
                trace_value[t]!==last_trace_value[t])
                known_trace_change=1'b1;
        end
    end

    always_comb begin
        read_client_pause='0;
        write_client_pause='0;
        force_pause=1'b0;
        if (launch_active && stress_mode!=0) begin
            if (stress_mode==1) begin
                // Historical asymmetric pressure profile.
                read_client_pause[3]=(cycles%23)<5;
                write_client_pause[1]=(cycles%19)<4;
                force_pause=(cycles%31)==0;
            end else begin
                // A0004 strong pressure reaches every live client with distinct
                // deterministic phases and also inserts aggregate DDR gaps.
                read_client_pause[0]=(cycles%17)<3;
                read_client_pause[1]=((cycles+5)%19)<4;
                read_client_pause[2]=((cycles+7)%23)<5;
                read_client_pause[3]=((cycles+11)%29)<6;
                write_client_pause[0]=((cycles+3)%13)<3;
                write_client_pause[1]=((cycles+9)%31)<7;
                force_pause=(cycles%37)<2;
            end
        end
    end

    always_ff @(posedge clk) begin
        cycles<=cycles+1;
        if (!rst_n || monitor_new_launch) begin
            done_seen<=0;
            protocol_seen<=0;
            expected_error_seen<=0;
            observed_protocol_error<=0;
            done_cycle<=0;
            last_b_cycle[0]<=0;last_b_cycle[1]<=0;
            last_progress_cycle<=0;
            last_trace_value<=trace_value;
            for (int r=0;r<4;r++) begin
                mon_ar[r]<=0;mon_r[r]<=0;
            end
            for (int w=0;w<2;w++) begin
                mon_aw[w]<=0;mon_w[w]<=0;mon_b[w]<=0;
            end
            for (int t=0;t<12;t++) begin
                trace_active[t]<=0;trace_first[t]<=0;trace_last[t]<=0;
            end
        end else if (launch_active) begin
            for (int r=0;r<4;r++) begin
                if (rd_arvalid[r] && rd_arready[r]) mon_ar[r]<=mon_ar[r]+1;
                if (rd_rvalid[r] && rd_rready[r]) mon_r[r]<=mon_r[r]+1;
            end
            for (int w=0;w<2;w++) begin
                if (wr_awvalid[w] && wr_awready[w]) mon_aw[w]<=mon_aw[w]+1;
                if (wr_wvalid[w] && wr_wready[w]) mon_w[w]<=mon_w[w]+1;
                if (wr_bvalid[w] && wr_bready[w]) mon_b[w]<=mon_b[w]+1;
            end
            if (any_axi_handshake || known_trace_change || ap_done===1'b1) begin
                last_progress_cycle<=cycles-launch_cycle;
                last_trace_value<=trace_value;
            end
            if (protocol_vld===1'b1) begin
                protocol_seen<=1;
                if (protocol_error===expected_error_current) begin
                    if (expected_error_current!=0) begin
                        expected_error_seen<=1;
                        observed_protocol_error<=protocol_error;
                    end
                end else if (protocol_error!==32'd0) begin
                    $fatal(1,"v10 unexpected protocol_error=%h expected=%0d",
                           protocol_error,expected_error_current);
                end
            end else if (protocol_vld!==1'b0) begin
                $fatal(1,"v10 protocol_error_ap_vld is X after launch");
            end
            if (wr_bvalid[0] && wr_bready[0]) last_b_cycle[0]<=cycles-launch_cycle;
            if (wr_bvalid[1] && wr_bready[1]) last_b_cycle[1]<=cycles-launch_cycle;
            for (int t=0;t<12;t++) begin
                if (trace_value[t][31]===1'b1) begin
                    if (trace_active[t]==0) trace_first[t]<=cycles-launch_cycle;
                    trace_active[t]<=trace_active[t]+1;
                    trace_last[t]<=cycles-launch_cycle;
                end
            end
            if (ap_done!==1'b0 && ap_done!==1'b1) begin
                $fatal(1,"v10 ap_done is X after launch");
            end else if (ap_done===1'b1 && !done_seen) begin
                done_seen<=1;
                done_cycle<=cycles-launch_cycle;
            end
            if (REJECT_ONLY &&
                (rd_arvalid[2]!==1'b0 || rd_arvalid[3]!==1'b0 ||
                 wr_awvalid[0]!==1'b0 || wr_awvalid[1]!==1'b0 ||
                 wr_wvalid[0]!==1'b0 || wr_wvalid[1]!==1'b0))
                $fatal(1,"v10 reject issued activation AXI traffic AR=%b/%b AW=%b/%b W=%b/%b",
                       rd_arvalid[2],rd_arvalid[3],wr_awvalid[0],wr_awvalid[1],
                       wr_wvalid[0],wr_wvalid[1]);
            if ((cycles-launch_cycle)!=0 &&
                ((cycles-launch_cycle)%1_000_000)==0)
                $display("CNN_PIPELINE_V10_PROGRESS cycles=%0d trace=%h/%h/%h/%h/%h/%h/%h/%h/%h/%h/%h/%h AR=%0d/%0d/%0d/%0d R=%0d/%0d/%0d/%0d AW=%0d/%0d W=%0d/%0d B=%0d/%0d last_progress=%0d",
                         cycles-launch_cycle,
                         trace_value[0],trace_value[1],trace_value[2],
                         trace_value[3],trace_value[4],trace_value[5],
                         trace_value[6],trace_value[7],trace_value[8],
                         trace_value[9],trace_value[10],trace_value[11],
                         mon_ar[0],mon_ar[1],mon_ar[2],mon_ar[3],
                         mon_r[0],mon_r[1],mon_r[2],mon_r[3],
                         mon_aw[0],mon_aw[1],mon_w[0],mon_w[1],
                         mon_b[0],mon_b[1],last_progress_cycle);
            if ((cycles-launch_cycle)>last_progress_cycle+1_000_000)
                $fatal(1,"v10 no AXI/known-trace progress cycles=%0d last=%0d trace=%h/%h/%h/%h/%h/%h/%h/%h/%h/%h/%h/%h AR=%0d/%0d/%0d/%0d R=%0d/%0d/%0d/%0d AW=%0d/%0d W=%0d/%0d B=%0d/%0d",
                       cycles-launch_cycle,last_progress_cycle,
                       trace_value[0],trace_value[1],trace_value[2],
                       trace_value[3],trace_value[4],trace_value[5],
                       trace_value[6],trace_value[7],trace_value[8],
                       trace_value[9],trace_value[10],trace_value[11],
                       mon_ar[0],mon_ar[1],mon_ar[2],mon_ar[3],
                       mon_r[0],mon_r[1],mon_r[2],mon_r[3],
                       mon_aw[0],mon_aw[1],mon_w[0],mon_w[1],
                       mon_b[0],mon_b[1]);
            if (cycles-launch_cycle>120_000_000)
                $fatal(1,"v10 watchdog cycles=%0d reads=%0d/%0d/%0d/%0d writes=%0d/%0d",
                       cycles-launch_cycle,read_beats[0],read_beats[1],
                       read_beats[2],read_beats[3],write_beats[0],write_beats[1]);
        end
    end

    // Optional fast functional gate for a newly generated RTL snapshot.  It
    // compares addressed block-0 normal-output W handshakes against an
    // independent golden image and waits for the corresponding B responses.
    // The default scope is deliberately only the first 32 normal words per
    // core; the final full-inference scoreboard remains the acceptance gate.
    always @(posedge clk) begin : monitor_early_output
        longint unsigned slot_begin,slot_end,burst_end,beat_address;
        int unsigned word_index;
        logic [127:0] golden_word;
        if (!rst_n || monitor_new_launch) begin
            for (int w=0;w<2;w++) begin
                early_aw_base[w]=0;
                early_aw_beats[w]=0;
                early_aw_position[w]=0;
                early_checked[w]=0;
                early_aw_valid[w]=0;
                early_aw_normal[w]=0;
                early_aw_needs_b[w]=0;
                early_target_b_done[w]=0;
            end
        end else if (early_enable && launch_active) begin
            for (int w=0;w<2;w++) begin
                slot_begin=(w==0 ? act_a_base : act_b_base)+
                           longint'(slot_count)*16;
                slot_end=slot_begin+longint'(slot_count)*16;
                if (wr_awvalid[w] && wr_awready[w]) begin
                    if (early_aw_valid[w])
                        $fatal(1,"v10 early gate observed overlapping AW master=%0d",w);
                    burst_end=wr_awaddr[w]+longint'(int'(wr_awlen[w])+1)*16;
                    if (wr_awaddr[w]<slot_end && burst_end>slot_begin &&
                        !(wr_awaddr[w]>=slot_begin && burst_end<=slot_end))
                        $fatal(1,"v10 early gate normal burst crosses slot boundary master=%0d addr=%h len=%0d",
                               w,wr_awaddr[w],wr_awlen[w]);
                    early_aw_base[w]=wr_awaddr[w];
                    early_aw_beats[w]=int'(wr_awlen[w])+1;
                    early_aw_position[w]=0;
                    early_aw_valid[w]=1;
                    early_aw_normal[w]=(wr_awaddr[w]>=slot_begin &&
                                        burst_end<=slot_end);
                    early_aw_needs_b[w]=early_aw_normal[w] &&
                                        early_checked[w]<early_target_words;
                end
                if (wr_wvalid[w] && wr_wready[w]) begin
                    if (!early_aw_valid[w])
                        $fatal(1,"v10 early gate W without tracked AW master=%0d",w);
                    if (early_aw_normal[w] && early_checked[w]<early_target_words) begin
                        beat_address=early_aw_base[w]+longint'(early_aw_position[w])*16;
                        word_index=int'((beat_address-slot_begin)/16);
                        if (word_index>=slot_count)
                            $fatal(1,"v10 early gate word index outside slot master=%0d index=%0d",
                                   w,word_index);
                        if (early_seen[w][word_index])
                            $fatal(1,"v10 early gate duplicate normal word master=%0d index=%0d",
                                   w,word_index);
                        golden_word=(w==0 ? early_expected_a[word_index] :
                                            early_expected_b[word_index]);
                        if (wr_wdata[w] !== golden_word)
                            $fatal(1,"v10 early output mismatch master=%0d checked=%0d word=%0d addr=%h got=%h expected=%h",
                                   w,early_checked[w],word_index,beat_address,
                                   wr_wdata[w],golden_word);
                        early_seen[w][word_index]=1;
                        early_checked[w]=early_checked[w]+1;
                    end
                    early_aw_position[w]=early_aw_position[w]+1;
                    if (wr_wlast[w] && early_aw_position[w]!=early_aw_beats[w])
                        $fatal(1,"v10 early gate WLAST length mismatch master=%0d position=%0d beats=%0d",
                               w,early_aw_position[w],early_aw_beats[w]);
                end
                if (wr_bvalid[w] && wr_bready[w]) begin
                    if (!early_aw_valid[w])
                        $fatal(1,"v10 early gate B without tracked AW master=%0d",w);
                    if (early_aw_needs_b[w] && early_checked[w]>=early_target_words)
                        early_target_b_done[w]=1;
                    early_aw_valid[w]=0;
                    early_aw_normal[w]=0;
                    early_aw_needs_b[w]=0;
                end
            end
            if (early_checked[0]>=early_target_words &&
                early_checked[1]>=early_target_words &&
                early_target_b_done[0] && early_target_b_done[1]) begin
                $display("CNN_PIPELINE_V10_EARLY_OUTPUT_PASS scope=%s region=%s profile=%0d blocks=%0d early_words_per_core=%0d corresponding_b=1 full_block=%0d full_inference=0 performance_reference=0 shared_ddr=1 cycles=%0d",
                         early_full_slot_arg!=0 ? "block0_slot" : "first_normal_words",
                         region_name(profile),profile,block_count,early_target_words,
                         early_full_slot_arg!=0,cycles-launch_cycle);
                $finish;
            end
        end
    end

    task automatic axil_write(input logic [31:0] address,
                               input logic [31:0] value);
        logic aw_done,w_done;
        begin
            aw_done=0;w_done=0;
            @(negedge clk);ctl_awaddr=address;ctl_wdata=value;
            ctl_awvalid=1;ctl_wvalid=1;
            while (!aw_done || !w_done) begin
                @(posedge clk);
                if (ctl_awvalid && ctl_awready) aw_done=1;
                if (ctl_wvalid && ctl_wready) w_done=1;
                @(negedge clk);ctl_awvalid=!aw_done;ctl_wvalid=!w_done;
            end
            ctl_bready=1;
            do @(posedge clk); while (ctl_bvalid!==1'b1);
            if (ctl_bresp!==2'b00)
                $fatal(1,"v10 AXI-Lite write error address=%h response=%b",address,ctl_bresp);
            @(negedge clk);ctl_bready=0;
        end
    endtask

    task automatic program_control(input int unsigned run_profile,
                                   input int unsigned run_blocks,
                                   input int unsigned run_params,
                                   input int unsigned run_slot,
                                   input int unsigned run_arena,
                                   input int unsigned run_flags);
        begin
            axil_write(V10_CTL_PARAMS1_LO,params1_base[31:0]);
            axil_write(V10_CTL_PARAMS1_HI,params1_base[63:32]);
            axil_write(V10_CTL_PARAMS2_LO,params2_base[31:0]);
            axil_write(V10_CTL_PARAMS2_HI,params2_base[63:32]);
            axil_write(V10_CTL_ACT_A_RD_LO,act_a_base[31:0]);
            axil_write(V10_CTL_ACT_A_RD_HI,act_a_base[63:32]);
            axil_write(V10_CTL_ACT_A_WR_LO,act_a_base[31:0]);
            axil_write(V10_CTL_ACT_A_WR_HI,act_a_base[63:32]);
            axil_write(V10_CTL_ACT_B_RD_LO,act_b_base[31:0]);
            axil_write(V10_CTL_ACT_B_RD_HI,act_b_base[63:32]);
            axil_write(V10_CTL_ACT_B_WR_LO,act_b_base[31:0]);
            axil_write(V10_CTL_ACT_B_WR_HI,act_b_base[63:32]);
            axil_write(V10_CTL_PROFILE,run_profile);
            axil_write(V10_CTL_BLOCKS,run_blocks);
            axil_write(V10_CTL_PARAMS_WORDS,run_params);
            axil_write(V10_CTL_SLOT_WORDS,run_slot);
            axil_write(V10_CTL_ARENA_WORDS,run_arena);
            axil_write(V10_CTL_FLAGS,run_flags);
        end
    endtask

    task automatic scoreboard_boundary(input logic clear_monitor);
        begin
            @(negedge clk);
            scoreboard_new_launch=1;
            monitor_new_launch=clear_monitor;
            @(posedge clk);
            @(negedge clk);
            scoreboard_new_launch=0;
            monitor_new_launch=0;
        end
    endtask

    task automatic assert_launch_drained;
        begin
            @(negedge clk);
            if (|u_ddr.rd_active || |u_ddr.rd_rvalid || |u_ddr.wr_active ||
                |u_ddr.wr_pending_response || |u_ddr.wr_bvalid)
                $fatal(1,"v10 repeat launch has model AXI state active rd=%b r=%b wr=%b pending_b=%b b=%b",
                       u_ddr.rd_active,u_ddr.rd_rvalid,u_ddr.wr_active,
                       u_ddr.wr_pending_response,u_ddr.wr_bvalid);
            if (|rd_arvalid || |rd_rvalid || |wr_awvalid || |wr_wvalid || |wr_bvalid)
                $fatal(1,"v10 repeat launch has visible AXI valid AR=%b R=%b AW=%b W=%b B=%b",
                       rd_arvalid,rd_rvalid,wr_awvalid,wr_wvalid,wr_bvalid);
            for (int s=0;s<TRANSIENT_WORDS;s++) begin
                if ((u_ddr.scratch_valid_a[s] && !u_ddr.scratch_read_a[s]) ||
                    (u_ddr.scratch_valid_b[s] && !u_ddr.scratch_read_b[s]))
                    $fatal(1,"v10 repeat launch has unreleased scratch word=%0d A=%0d/%0d B=%0d/%0d",
                           s,u_ddr.scratch_valid_a[s],u_ddr.scratch_read_a[s],
                           u_ddr.scratch_valid_b[s],u_ddr.scratch_read_b[s]);
            end
        end
    endtask

    task automatic snapshot_traffic;
        begin
            for (int r=0;r<4;r++) begin
                start_read[r]=read_beats[r];
                start_rpause[r]=read_pause_hit_cycles[r];
            end
            for (int w=0;w<2;w++) begin
                start_write[w]=write_beats[w];
                start_wpause[w]=write_pause_hit_cycles[w];
            end
            for (int core=0;core<2;core++) begin
                start_residual_write_bursts[core]=u_ddr.residual_write_bursts[core];
                start_residual_read_bursts[core]=u_ddr.residual_read_bursts[core];
                start_residual_write_wraps[core]=u_ddr.residual_write_wraps[core];
                start_residual_read_wraps[core]=u_ddr.residual_read_wraps[core];
            end
            start_budget=aggregate_budget_beats;
        end
    endtask

    task automatic launch_and_wait(input logic [31:0] expected_error);
        begin
            expected_error_current=expected_error;
            snapshot_traffic();
            @(negedge clk);
            launch_cycle=cycles;
            launch_active=1;
            ap_start=1;
            do @(posedge clk); while (ap_ready!==1'b1);
            @(negedge clk);ap_start=0;
            while (!done_seen) @(posedge clk);
            wait(ap_idle===1'b1);
            repeat(4) @(posedge clk);
            @(negedge clk);launch_active=0;
        end
    endtask

    task automatic load_images(input logic swapped);
        begin
            for (int i=0;i<slot_count;i++) begin
                u_ddr.activation_a[i]=swapped?input_b[i]:input_a[i];
                u_ddr.activation_b[i]=swapped?input_a[i]:input_b[i];
            end
        end
    endtask

    task automatic load_profile_fixture(input int unsigned run_profile,
                                        input logic swapped);
        int unsigned differing_expected;
        begin
            profile=run_profile;
            block_count=blocks(profile);param_count=params_words(profile);
            slot_count=slot_words(profile);arena_count=arena_words(profile);flags=0;
            params_file=fixture_path(fixture_root,profile,"params.mem");
            input_a_file=fixture_path(fixture_root,profile,"input_a.mem");
            input_b_file=fixture_path(fixture_root,profile,"input_b.mem");
            expected_a_file=fixture_path(fixture_root,profile,"expected_a.mem");
            expected_b_file=fixture_path(fixture_root,profile,"expected_b.mem");
            for (int i=0;i<MAX_ACT;i++) begin
                u_ddr.activation_a[i]=CANARY;u_ddr.activation_b[i]=CANARY;
            end
            $readmemh(params_file,u_ddr.params_pw1,0,param_count-1);
            $readmemh(params_file,u_ddr.params_pw2,0,param_count-1);
            $readmemh(input_a_file,input_a,0,slot_count-1);
            $readmemh(input_b_file,input_b,0,slot_count-1);
            $readmemh(expected_a_file,expected_a,0,output_words(profile)-1);
            $readmemh(expected_b_file,expected_b,0,output_words(profile)-1);
            differing_expected=0;
            for (int i=0;i<output_words(profile);i++)
                if (expected_a[i]!==expected_b[i]) differing_expected++;
            if (differing_expected==0)
                $fatal(1,"paired expected images are not distinct profile=%0d",profile);
            load_images(swapped);
        end
    endtask

    task automatic check_output(input logic swapped,input int unsigned run_index,
                                input logic performance_reference);
        int unsigned dst;
        longint unsigned common_cycles,delta_r[0:3],delta_w[0:1],delta_budget;
        longint unsigned pause_hits;
        begin
            common_cycles=done_cycle;
            dst=output_slot(profile,block_count);
            for (int i=0;i<output_words(profile);i++) begin
                if (u_ddr.activation_a[dst+i] !== (swapped?expected_b[i]:expected_a[i]))
                    $fatal(1,"v10 output A mismatch run=%0d word=%0d got=%h expected=%h",
                           run_index,i,u_ddr.activation_a[dst+i],
                           swapped?expected_b[i]:expected_a[i]);
                if (u_ddr.activation_b[dst+i] !== (swapped?expected_a[i]:expected_b[i]))
                    $fatal(1,"v10 output B mismatch run=%0d word=%0d got=%h expected=%h",
                           run_index,i,u_ddr.activation_b[dst+i],
                           swapped?expected_a[i]:expected_b[i]);
            end
            for (int i=0;i<GUARD;i++) begin
                if (u_ddr.activation_a[arena_count+i]!==CANARY ||
                    u_ddr.activation_b[arena_count+i]!==CANARY)
                    $fatal(1,"v10 activation arena canary changed run=%0d word=%0d",run_index,i);
            end
            if (!protocol_seen || expected_error_seen || observed_protocol_error!=0)
                $fatal(1,"v10 normal protocol result missing/bad seen=%0d error=%h",
                       protocol_seen,observed_protocol_error);
            if (last_b_cycle[0]==0 || last_b_cycle[1]==0 ||
                last_b_cycle[0]>common_cycles || last_b_cycle[1]>common_cycles)
                $fatal(1,"v10 invalid completion cycles common=%0d A=%0d B=%0d",
                       common_cycles,last_b_cycle[0],last_b_cycle[1]);
            pause_hits=0;
            for (int r=0;r<4;r++) begin
                delta_r[r]=read_beats[r]-start_read[r];
                pause_hits+=read_pause_hit_cycles[r]-start_rpause[r];
            end
            for (int w=0;w<2;w++) begin
                delta_w[w]=write_beats[w]-start_write[w];
                pause_hits+=write_pause_hit_cycles[w]-start_wpause[w];
            end
            delta_budget=aggregate_budget_beats-start_budget;
            if (delta_r[0]==0 || (profile!=3 && delta_r[1]==0) ||
                delta_r[2]==0 || delta_r[3]==0 ||
                delta_w[0]==0 || delta_w[1]==0 || delta_budget==0)
                $fatal(1,"v10 normal run missing DDR traffic");
            if (stress_mode!=0 && pause_hits==0)
                $fatal(1,"v10 stress configured but no pause hit a live request");
            if (stress_mode==2) begin
                for (int r=0;r<4;r++) begin
                    if (delta_r[r]!=0 && read_pause_hit_cycles[r]==start_rpause[r])
                        $fatal(1,"v10 strong pressure missed live read client=%0d",r);
                end
                for (int w=0;w<2;w++) begin
                    if (delta_w[w]!=0 && write_pause_hit_cycles[w]==start_wpause[w])
                        $fatal(1,"v10 strong pressure missed live write client=%0d",w);
                end
            end
            for (int core=0;core<2;core++) begin
                if (profile!=3 &&
                    (u_ddr.residual_write_bursts[core]==start_residual_write_bursts[core] ||
                     u_ddr.residual_read_bursts[core]==start_residual_read_bursts[core] ||
                     u_ddr.residual_write_wraps[core]==start_residual_write_wraps[core] ||
                     u_ddr.residual_read_wraps[core]==start_residual_read_wraps[core]))
                    $fatal(1,"v10 residual DDR ring coverage missing run=%0d core=%0d wb=%0d rb=%0d ww=%0d rw=%0d",
                           run_index,core,
                           u_ddr.residual_write_bursts[core]-start_residual_write_bursts[core],
                           u_ddr.residual_read_bursts[core]-start_residual_read_bursts[core],
                           u_ddr.residual_write_wraps[core]-start_residual_write_wraps[core],
                           u_ddr.residual_read_wraps[core]-start_residual_read_wraps[core]);
                if (profile==3 &&
                    (u_ddr.residual_write_bursts[core]!=start_residual_write_bursts[core] ||
                     u_ddr.residual_read_bursts[core]!=start_residual_read_bursts[core] ||
                     u_ddr.residual_write_wraps[core]!=start_residual_write_wraps[core] ||
                     u_ddr.residual_read_wraps[core]!=start_residual_read_wraps[core]))
                    $fatal(1,"v10 transition unexpectedly accessed residual DDR ring run=%0d core=%0d wb=%0d rb=%0d ww=%0d rw=%0d",
                           run_index,core,
                           u_ddr.residual_write_bursts[core]-start_residual_write_bursts[core],
                           u_ddr.residual_read_bursts[core]-start_residual_read_bursts[core],
                           u_ddr.residual_write_wraps[core]-start_residual_write_wraps[core],
                           u_ddr.residual_read_wraps[core]-start_residual_read_wraps[core]);
                if (u_ddr.legacy_stage_write_bursts[core]!=0 ||
                    u_ddr.legacy_stage_read_bursts[core]!=0)
                    $fatal(1,"v10 stale stage DDR access run=%0d core=%0d writes=%0d reads=%0d",
                           run_index,core,u_ddr.legacy_stage_write_bursts[core],
                           u_ddr.legacy_stage_read_bursts[core]);
                $display("CNN_PIPELINE_V10_RESIDUAL_RING_SUMMARY run=%0d core=%0d write_bursts=%0d read_bursts=%0d write_wraps=%0d read_wraps=%0d legacy_stage_writes=%0d legacy_stage_reads=%0d",
                         run_index,core,
                         u_ddr.residual_write_bursts[core]-start_residual_write_bursts[core],
                         u_ddr.residual_read_bursts[core]-start_residual_read_bursts[core],
                         u_ddr.residual_write_wraps[core]-start_residual_write_wraps[core],
                         u_ddr.residual_read_wraps[core]-start_residual_read_wraps[core],
                         u_ddr.legacy_stage_write_bursts[core],
                         u_ddr.legacy_stage_read_bursts[core]);
            end
            $display("CNN_PIPELINE_V10_SHARED_PASS run=%0d region=%s profile=%0d blocks=%0d cycles=%0d core_a_last_b=%0d core_b_last_b=%0d functional_pass=1 shared_ddr=1 performance_reference=%0d stress_exercised=%0d pressure_mode=%0d token=%0d/%0d/%0d b_delay=%0d read_beats=%0d/%0d/%0d/%0d write_beats=%0d/%0d aggregate_issued=%0d pause_hits=%0d repeat_without_reset=%0d profile_switch=%0d swapped=%0d",
                     run_index,region_name(profile),profile,block_count,common_cycles,
                     last_b_cycle[0],last_b_cycle[1],performance_reference,
                     stress_mode!=0,stress_mode,token_numer,token_denom,token_burst,b_response_delay,
                     delta_r[0],delta_r[1],delta_r[2],delta_r[3],
                     delta_w[0],delta_w[1],delta_budget,pause_hits,run_index!=0,
                     run_index!=0 && profile_switch,swapped);
        end
    endtask

    task automatic mutate_reject_fixture(output logic [31:0] expected_error,
                                         output int unsigned run_profile,
                                         output int unsigned run_blocks,
                                         output int unsigned run_params,
                                         output int unsigned run_slot,
                                         output int unsigned run_arena,
                                         output int unsigned run_flags);
        int unsigned word,lane;
        begin
            expected_error=2;
            run_profile=profile;run_blocks=block_count;run_params=param_count;
            run_slot=slot_count;run_arena=arena_count;run_flags=flags;
            if (error_kind=="bad_profile") begin run_profile=4;expected_error=1;end
            else if (error_kind=="bad_blocks") begin run_blocks=0;expected_error=1;end
            else if (error_kind=="bad_params_words") begin run_params=param_count-1;expected_error=1;end
            else if (error_kind=="bad_slot_words") begin run_slot=slot_count+1;expected_error=1;end
            else if (error_kind=="bad_arena_words") begin run_arena=arena_count+1;expected_error=1;end
            else if (error_kind=="bad_flags") begin run_flags=1;expected_error=1;end
            else if (error_kind=="metadata_p1")
                u_ddr.params_pw1[metadata_shift_word(profile)][31:0]=32'd63;
            else if (error_kind=="metadata_p2")
                u_ddr.params_pw2[metadata_shift_word(profile)][31:0]=32'd63;
            else if (error_kind=="gelu_tail") begin
                if (profile!=2) $fatal(1,"gelu_tail requires profile2/block0 fixture");
                word=gelu_tail_word(2,0);lane=gelu_tail_lane(2,0);
                u_ddr.params_pw1[word][lane*16 +: 16]=16'd32766;
            end else if (error_kind=="later_tail") begin
                if (profile!=1) $fatal(1,"later_tail requires profile1/block10 fixture");
                word=gelu_tail_word(1,10);lane=gelu_tail_lane(1,10);
                u_ddr.params_pw1[word][lane*16 +: 16]=16'd32766;
            end else if (error_kind=="gelu_span256_normal" ||
                         error_kind=="gelu_span256_p3_dw" ||
                         error_kind=="gelu_span256_p3_pw") begin
                if (error_kind=="gelu_span256_normal") begin
                    if (profile!=0) $fatal(1,"gelu_span256_normal requires profile0");
                    word=bad_gelu_segment_word(0,0);
                end else if (error_kind=="gelu_span256_p3_dw") begin
                    if (profile!=3) $fatal(1,"gelu_span256_p3_dw requires profile3");
                    word=bad_gelu_segment_word(3,1);
                end else begin
                    if (profile!=3) $fatal(1,"gelu_span256_p3_pw requires profile3");
                    word=bad_gelu_segment_word(3,2);
                end
                if (word==32'hffff_ffff) $fatal(1,"missing bad GELU segment fixture");
                for (int segment_word=0;segment_word<4;segment_word++) begin
                    for (int segment_lane=0;segment_lane<8;segment_lane++)
                        u_ddr.params_pw1[word+segment_word][segment_lane*16 +: 16]=
                            (segment_word==0 && segment_lane==0) ? 16'h8000 : 16'h8100;
                end
            end else $fatal(1,"unsupported ERROR_KIND=%s",error_kind);
        end
    endtask

    initial begin : run_test
        int unsigned run_profile,run_blocks,run_params,run_slot,run_arena,run_flags;
        logic [31:0] reject_error;
        longint unsigned reject_cycles;
        if (!$value$plusargs("FIXTURE_ROOT=%s",fixture_root) ||
            !$value$plusargs("PROFILE=%d",profile))
            $fatal(1,"required plusargs: FIXTURE_ROOT PROFILE");
        if (profile>3) $fatal(1,"invalid fixture profile=%0d",profile);
        block_count=blocks(profile);param_count=params_words(profile);
        slot_count=slot_words(profile);arena_count=arena_words(profile);flags=0;
        if (!$value$plusargs("TOKEN_NUMER=%d",token_numer)) token_numer=1;
        if (!$value$plusargs("TOKEN_DENOM=%d",token_denom)) token_denom=2;
        if (!$value$plusargs("TOKEN_BURST=%d",token_burst)) token_burst=32;
        if (!$value$plusargs("B_DELAY=%d",b_response_delay)) b_response_delay=3;
        if (!$value$plusargs("STRESS=%d",stress_mode)) stress_mode=0;
        if (!$value$plusargs("REPEAT=%d",repeat_launch)) repeat_launch=(profile==2);
        profile_switch=$value$plusargs("SECOND_PROFILE=%d",second_profile);
        if (!$value$plusargs("SECOND_SWAPPED=%d",second_swapped)) second_swapped=1;
        if (profile_switch) repeat_launch=1;
        if (stress_mode>2 || repeat_launch>1) $fatal(1,"invalid STRESS/REPEAT");
        if (second_swapped>1) $fatal(1,"invalid SECOND_SWAPPED=%0d",second_swapped);
        if (profile_switch && (REJECT_ONLY || second_profile>3 || second_profile==profile))
            $fatal(1,"invalid profile switch reject=%0d first=%0d second=%0d",
                   REJECT_ONLY,profile,second_profile);
        if ($value$plusargs("EARLY_EXPECTED_A=%s",early_expected_a_file) !=
            $value$plusargs("EARLY_EXPECTED_B=%s",early_expected_b_file))
            $fatal(1,"EARLY_EXPECTED_A and EARLY_EXPECTED_B must be supplied together");
        early_enable=(early_expected_a_file!="" && early_expected_b_file!="");
        if (!$value$plusargs("EARLY_WORDS=%d",early_words_arg)) early_words_arg=32;
        if (!$value$plusargs("EARLY_FULL_SLOT=%d",early_full_slot_arg))
            early_full_slot_arg=0;
        if (early_full_slot_arg>1)
            $fatal(1,"invalid EARLY_FULL_SLOT=%0d",early_full_slot_arg);
        early_target_words=early_full_slot_arg!=0 ? slot_count : early_words_arg;
        if (early_enable && (REJECT_ONLY || profile!=2 || repeat_launch!=0 ||
                             early_target_words==0 || early_target_words>slot_count))
            $fatal(1,"invalid early gate reject=%0d profile=%0d repeat=%0d words=%0d slot=%0d",
                   REJECT_ONLY,profile,repeat_launch,early_target_words,slot_count);

        load_profile_fixture(profile,0);
        if (early_enable) begin
            $readmemh(early_expected_a_file,early_expected_a,0,slot_count-1);
            $readmemh(early_expected_b_file,early_expected_b,0,slot_count-1);
        end
        for (int w=0;w<2;w++)
            for (int i=0;i<slot_count;i++) early_seen[w][i]=0;
        repeat(8) @(posedge clk);
        @(negedge fast_clk);fast_rst=0;
        @(negedge clk);rst_n=1;
        repeat(4) @(posedge clk);
        scoreboard_boundary(1);

        if (!REJECT_ONLY) begin
            program_control(profile,block_count,param_count,slot_count,arena_count,flags);
            launch_and_wait(0);
            check_output(0,0,stress_mode==0 && token_numer==1 && token_denom==2 &&
                                      token_burst==32 && b_response_delay==3);
            if (repeat_launch!=0) assert_launch_drained();
            scoreboard_boundary(repeat_launch!=0);
            if (repeat_launch!=0) begin
                if (profile_switch)
                    load_profile_fixture(second_profile,second_swapped!=0);
                else
                    load_images(1);
                program_control(profile,block_count,param_count,slot_count,arena_count,flags);
                launch_and_wait(0);
                check_output(profile_switch ? second_swapped!=0 : 1'b1,1,0);
                scoreboard_boundary(0);
            end
        end else begin
            if (!$value$plusargs("ERROR_KIND=%s",error_kind))
                $fatal(1,"reject test requires ERROR_KIND");
            mutate_reject_fixture(reject_error,run_profile,run_blocks,run_params,
                                  run_slot,run_arena,run_flags);
            program_control(run_profile,run_blocks,run_params,run_slot,run_arena,run_flags);
            launch_and_wait(reject_error);
            reject_cycles=done_cycle;
            if (!protocol_seen || !expected_error_seen ||
                observed_protocol_error!==reject_error)
                $fatal(1,"v10 reject result missing/bad kind=%s expected=%0d observed=%h",
                       error_kind,reject_error,observed_protocol_error);
            if (read_beats[2]!=start_read[2] || read_beats[3]!=start_read[3] ||
                write_beats[0]!=start_write[0] || write_beats[1]!=start_write[1])
                $fatal(1,"v10 reject activation traffic count changed");
            for (int t=0;t<12;t++) begin
                if (trace_active[t]!=0)
                    $fatal(1,"v10 reject trace was active trace=%0d cycles=%0d",t,trace_active[t]);
            end
            $display("CNN_PIPELINE_V10_REJECT_PASS error_kind=%s region=%s profile=%0d blocks=%0d cycles=%0d expected_protocol_error=%0d observed_protocol_error=%0d functional_pass=1 shared_ddr=1 performance_reference=0 stress_exercised=0 activation_ar=0/0 activation_aw=0/0 activation_w=0/0 trace_inert=1",
                     error_kind,region_name(profile),profile,block_count,reject_cycles,
                     reject_error,observed_protocol_error);
            scoreboard_boundary(0);
        end
        $finish;
    end
endmodule
