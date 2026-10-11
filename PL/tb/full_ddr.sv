`timescale 1ns/1ps

// Shared, bandwidth-limited DDR target for the v10 dual-image testbenches.
// Four read masters and two write masters arbitrate for one data-beat budget.
// Address channels have independent fair round-robin arbitration; read data and
// write data consume the same token bucket. Write data becomes visible when
// BVALID is raised, but scratch validity is released only by the B handshake;
// this lets the testbench detect missing write-response fences.
//
// The model deliberately knows no DUT port names. The enclosing v10 testbench
// maps final HLS ports onto these packed arrays after the ABI is frozen.
module tb_cnn_v10_shared_ddr #(
    parameter int NUM_RD = 4,
    parameter int NUM_WR = 2,
    parameter int ADDR_W = 64,
    parameter int DATA_W = 128,
    parameter int ID_W = 1,
    parameter int MAX_BURST_BEATS = 32,
    parameter int MAX_PARAMS_WORDS = 1_400_000,
    parameter int MAX_ACT_WORDS = 262_144
) (
    input  logic                         clk,
    input  logic                         rst_n,
    // One-cycle testbench scoreboard boundary between ap_ctrl_hs launches.
    // This never resets the DUT or cumulative traffic/token counters.
    input  logic                         scoreboard_new_launch,

    input  logic [NUM_RD-1:0]            rd_arvalid,
    output logic [NUM_RD-1:0]            rd_arready,
    input  logic [NUM_RD-1:0][ADDR_W-1:0] rd_araddr,
    input  logic [NUM_RD-1:0][ID_W-1:0]  rd_arid,
    input  logic [NUM_RD-1:0][7:0]       rd_arlen,
    input  logic [NUM_RD-1:0][2:0]       rd_arsize,
    input  logic [NUM_RD-1:0][1:0]       rd_arburst,
    output logic [NUM_RD-1:0]            rd_rvalid,
    input  logic [NUM_RD-1:0]            rd_rready,
    output logic [NUM_RD-1:0][DATA_W-1:0] rd_rdata,
    output logic [NUM_RD-1:0]            rd_rlast,
    output logic [NUM_RD-1:0][ID_W-1:0]  rd_rid,
    output logic [NUM_RD-1:0][1:0]       rd_rresp,

    input  logic [NUM_WR-1:0]            wr_awvalid,
    output logic [NUM_WR-1:0]            wr_awready,
    input  logic [NUM_WR-1:0][ADDR_W-1:0] wr_awaddr,
    input  logic [NUM_WR-1:0][ID_W-1:0]  wr_awid,
    input  logic [NUM_WR-1:0][7:0]       wr_awlen,
    input  logic [NUM_WR-1:0][2:0]       wr_awsize,
    input  logic [NUM_WR-1:0][1:0]       wr_awburst,
    input  logic [NUM_WR-1:0]            wr_wvalid,
    output logic [NUM_WR-1:0]            wr_wready,
    input  logic [NUM_WR-1:0][DATA_W-1:0] wr_wdata,
    input  logic [NUM_WR-1:0][DATA_W/8-1:0] wr_wstrb,
    input  logic [NUM_WR-1:0]            wr_wlast,
    output logic [NUM_WR-1:0]            wr_bvalid,
    input  logic [NUM_WR-1:0]            wr_bready,
    output logic [NUM_WR-1:0][ID_W-1:0]  wr_bid,
    output logic [NUM_WR-1:0][1:0]       wr_bresp,

    input  logic [ADDR_W-1:0]            params1_base,
    input  logic [ADDR_W-1:0]            params2_base,
    input  logic [ADDR_W-1:0]            act_a_base,
    input  logic [ADDR_W-1:0]            act_b_base,
    input  int unsigned                  params_words,
    input  int unsigned                  act_words,
    input  int unsigned                  scratch_word_base,
    input  int unsigned                  scratch_words,

    // token_numer/token_denom is the aggregate data-beat rate. For example,
    // 1/1 allows one beat/cycle and 1/2 allows one beat every two cycles.
    // token_burst caps saved credit in whole beats. force_pause stops data only.
    input  int unsigned                  token_numer,
    input  int unsigned                  token_denom,
    input  int unsigned                  token_burst,
    input  int unsigned                  write_response_delay,
    input  logic                         force_pause,
    input  logic [NUM_RD-1:0]            read_client_pause,
    input  logic [NUM_WR-1:0]            write_client_pause,

    output logic [NUM_RD-1:0][63:0]      read_beats,
    output logic [NUM_RD-1:0][63:0]      read_bursts,
    output logic [NUM_RD-1:0][63:0]      read_backpressure_cycles,
    output logic [NUM_RD-1:0][63:0]      read_pause_hit_cycles,
    output logic [NUM_WR-1:0][63:0]      write_beats,
    output logic [NUM_WR-1:0][63:0]      write_bursts,
    output logic [NUM_WR-1:0][63:0]      write_backpressure_cycles,
    output logic [NUM_WR-1:0][63:0]      write_pause_hit_cycles,
    // Read/write totals count AXI handshakes independently. budget_beats
    // counts aggregate DDR data issues charged to the shared token bucket.
    output logic [63:0]                  aggregate_read_beats,
    output logic [63:0]                  aggregate_write_beats,
    output logic [63:0]                  aggregate_budget_beats
);
    localparam int DATA_BYTES = DATA_W/8;
    localparam int TOTAL_DATA_CLIENTS = NUM_RD+NUM_WR;
    localparam int MAX_TRANSIENT_WORDS = 4096;
    localparam int LEGACY_STAGE_WORDS = 512+1024+256;

    initial begin
        if (NUM_RD!=4 || NUM_WR!=2 || DATA_W!=128)
            $fatal(1, "v10 DDR fixed ABI requires NUM_RD=4 NUM_WR=2 DATA_W=128");
    end

    logic [DATA_W-1:0] params_pw1 [0:MAX_PARAMS_WORDS-1];
    logic [DATA_W-1:0] params_pw2 [0:MAX_PARAMS_WORDS-1];
    logic [DATA_W-1:0] activation_a [0:MAX_ACT_WORDS-1];
    logic [DATA_W-1:0] activation_b [0:MAX_ACT_WORDS-1];
    logic scratch_valid_a [0:MAX_TRANSIENT_WORDS-1];
    logic scratch_valid_b [0:MAX_TRANSIENT_WORDS-1];
    logic scratch_read_a [0:MAX_TRANSIENT_WORDS-1];
    logic scratch_read_b [0:MAX_TRANSIENT_WORDS-1];

    // The residual scratch ring remains in DDR.  The following counters prove
    // real traffic/wrap and also make any stale q3/q7/expanded DDR access an
    // explicit failure, even if a candidate temporarily reserves the old tail.
    longint unsigned residual_write_bursts [0:NUM_WR-1];
    longint unsigned residual_read_bursts [0:NUM_WR-1];
    longint unsigned residual_write_wraps [0:NUM_WR-1];
    longint unsigned residual_read_wraps [0:NUM_WR-1];
    longint unsigned legacy_stage_write_bursts [0:NUM_WR-1];
    longint unsigned legacy_stage_read_bursts [0:NUM_WR-1];
    int signed residual_last_write_slot [0:NUM_WR-1];
    int signed residual_last_read_slot [0:NUM_WR-1];

    logic [NUM_RD-1:0] rd_active;
    logic [NUM_RD-1:0][ADDR_W-1:0] rd_next_addr;
    logic [NUM_RD-1:0][ADDR_W-1:0] rd_response_addr;
    logic [NUM_RD-1:0][8:0] rd_beats_left;
    logic [NUM_RD-1:0][ID_W-1:0] rd_saved_id;

    logic [NUM_WR-1:0] wr_active;
    logic [NUM_WR-1:0] wr_pending_response;
    logic [NUM_WR-1:0][ADDR_W-1:0] wr_next_addr;
    logic [NUM_WR-1:0][ADDR_W-1:0] wr_burst_base;
    logic [NUM_WR-1:0][8:0] wr_beats_left;
    logic [NUM_WR-1:0][8:0] wr_burst_beats;
    logic [NUM_WR-1:0][8:0] wr_buffer_position;
    logic [NUM_WR-1:0][ID_W-1:0] wr_saved_id;
    int unsigned wr_delay [0:NUM_WR-1];
    logic [DATA_W-1:0] pending_write [0:NUM_WR-1][0:MAX_BURST_BEATS-1];

    int unsigned ar_rr;
    int unsigned aw_rr;
    int unsigned data_rr;
    int signed ar_grant;
    int signed aw_grant;
    int signed read_issue_grant;
    int signed write_data_grant;
    longint unsigned token_credit;
    longint unsigned token_cap;
    logic budget_open;
    logic data_beat_issued;

    function automatic logic [DATA_W-1:0] read_memory(input int master,
                                                       input logic [ADDR_W-1:0] addr);
        longint unsigned index;
        begin
            if (addr[3:0] != 0)
                $fatal(1, "v10 DDR unaligned read addr=%h", addr);
            if (master==0) begin
                if (addr<params1_base ||
                    addr>=params1_base+64'(params_words)*DATA_BYTES)
                    $fatal(1, "v10 DDR params1 read outside region addr=%h",addr);
                index=(addr-params1_base)/DATA_BYTES;
                if (index >= MAX_PARAMS_WORDS)
                    $fatal(1, "v10 DDR params1 index overflow index=%0d", index);
                read_memory=params_pw1[index];
            end else if (master==1) begin
                if (addr<params2_base ||
                    addr>=params2_base+64'(params_words)*DATA_BYTES)
                    $fatal(1, "v10 DDR params2 read outside region addr=%h",addr);
                index=(addr-params2_base)/DATA_BYTES;
                if (index >= MAX_PARAMS_WORDS)
                    $fatal(1, "v10 DDR params2 index overflow index=%0d", index);
                read_memory=params_pw2[index];
            end else if (master==2) begin
                if (addr<act_a_base ||
                    addr>=act_a_base+64'(act_words)*DATA_BYTES)
                    $fatal(1, "v10 DDR activation A read outside arena addr=%h",addr);
                index=(addr-act_a_base)/DATA_BYTES;
                if (index >= MAX_ACT_WORDS)
                    $fatal(1, "v10 DDR activation A index overflow index=%0d", index);
                read_memory=activation_a[index];
            end else if (master==3) begin
                if (addr<act_b_base ||
                    addr>=act_b_base+64'(act_words)*DATA_BYTES)
                    $fatal(1, "v10 DDR activation B read outside arena addr=%h",addr);
                index=(addr-act_b_base)/DATA_BYTES;
                if (index >= MAX_ACT_WORDS)
                    $fatal(1, "v10 DDR activation B index overflow index=%0d", index);
                read_memory=activation_b[index];
            end else begin
                $fatal(1, "v10 DDR read outside configured regions addr=%h", addr);
                read_memory='x;
            end
        end
    endfunction

    function automatic logic enabled_write_has_x(
        input logic [DATA_W-1:0] data,
        input logic [DATA_BYTES-1:0] strb);
        logic bad;
        begin
            bad=1'b0;
            for (int byte_index=0;byte_index<DATA_BYTES;byte_index++) begin
                if (strb[byte_index] &&
                    $isunknown(data[byte_index*8 +: 8]))
                    bad=1'b1;
            end
            return bad;
        end
    endfunction

    function automatic logic scratch_released_same_cycle(
        input int write_master,
        input int unsigned scratch_index);
        int read_master;
        logic [ADDR_W-1:0] expected_addr;
        begin
            read_master=write_master+2;
            expected_addr=(write_master==0 ? act_a_base : act_b_base)+
                          ADDR_W'(scratch_word_base+scratch_index)*DATA_BYTES;
            scratch_released_same_cycle=
                rd_rvalid[read_master] && rd_rready[read_master] &&
                rd_response_addr[read_master]==expected_addr;
        end
    endfunction

    task automatic record_activation_read_burst(input int master,
                                                 input logic [ADDR_W-1:0] addr);
        longint unsigned arena_index,transient_index;
        int core,slot;
        begin
            if (master==2 || master==3) begin
                core=master-2;
                if (addr >= (core==0 ? act_a_base : act_b_base)) begin
                    arena_index=(addr-(core==0 ? act_a_base : act_b_base))/DATA_BYTES;
                    if (arena_index>=scratch_word_base) begin
                        transient_index=arena_index-scratch_word_base;
                        if (transient_index<MAX_TRANSIENT_WORDS) begin
                            slot=transient_index/MAX_BURST_BEATS;
                            residual_read_bursts[core]<=residual_read_bursts[core]+1;
                            if (residual_last_read_slot[core]>=0 &&
                                slot<residual_last_read_slot[core])
                                residual_read_wraps[core]<=residual_read_wraps[core]+1;
                            residual_last_read_slot[core]<=slot;
                        end else if (transient_index<MAX_TRANSIENT_WORDS+LEGACY_STAGE_WORDS) begin
                            legacy_stage_read_bursts[core]<=legacy_stage_read_bursts[core]+1;
                        end
                    end
                end
            end
        end
    endtask

    task automatic record_activation_write_burst(input int master,
                                                  input logic [ADDR_W-1:0] addr);
        longint unsigned arena_index,transient_index;
        int slot;
        begin
            if (addr >= (master==0 ? act_a_base : act_b_base)) begin
                arena_index=(addr-(master==0 ? act_a_base : act_b_base))/DATA_BYTES;
                if (arena_index>=scratch_word_base) begin
                    transient_index=arena_index-scratch_word_base;
                    if (transient_index<MAX_TRANSIENT_WORDS) begin
                        slot=transient_index/MAX_BURST_BEATS;
                        residual_write_bursts[master]<=residual_write_bursts[master]+1;
                        if (residual_last_write_slot[master]>=0 &&
                            slot<residual_last_write_slot[master])
                            residual_write_wraps[master]<=residual_write_wraps[master]+1;
                        residual_last_write_slot[master]<=slot;
                    end else if (transient_index<MAX_TRANSIENT_WORDS+LEGACY_STAGE_WORDS) begin
                        legacy_stage_write_bursts[master]<=legacy_stage_write_bursts[master]+1;
                    end
                end
            end
        end
    endtask

    task automatic record_scratch_read(input int master,
                                       input logic [ADDR_W-1:0] addr);
        longint unsigned arena_index;
        int unsigned scratch_index;
        begin
            if (master==2 && addr>=act_a_base) begin
                arena_index=(addr-act_a_base)/DATA_BYTES;
                if (arena_index>=scratch_word_base &&
                    arena_index<scratch_word_base+scratch_words) begin
                    scratch_index=arena_index-scratch_word_base;
                    if (!scratch_valid_a[scratch_index])
                        $fatal(1, "v10 DDR activation A scratch read before B commit word=%0d addr=%h",
                               scratch_index,addr);
                    scratch_read_a[scratch_index]<=1'b1;
                end
            end else if (master==3 && addr>=act_b_base) begin
                arena_index=(addr-act_b_base)/DATA_BYTES;
                if (arena_index>=scratch_word_base &&
                    arena_index<scratch_word_base+scratch_words) begin
                    scratch_index=arena_index-scratch_word_base;
                    if (!scratch_valid_b[scratch_index])
                        $fatal(1, "v10 DDR activation B scratch read before B commit word=%0d addr=%h",
                               scratch_index,addr);
                    scratch_read_b[scratch_index]<=1'b1;
                end
            end
        end
    endtask

    task automatic assert_scratch_read_committed(
        input int master,
        input logic [ADDR_W-1:0] addr,
        input int unsigned beats);
        longint unsigned arena_index;
        int unsigned scratch_index;
        begin
            if (master==2 && addr>=act_a_base) begin
                arena_index=(addr-act_a_base)/DATA_BYTES;
                for (int beat=0;beat<beats;beat++) begin
                    if (arena_index+beat>=scratch_word_base &&
                        arena_index+beat<scratch_word_base+scratch_words) begin
                        scratch_index=arena_index+beat-scratch_word_base;
                        if (!scratch_valid_a[scratch_index])
                            $fatal(1, "v10 DDR activation A scratch AR before B handshake word=%0d addr=%h",
                                   scratch_index,addr+ADDR_W'(beat*DATA_BYTES));
                    end
                end
            end else if (master==3 && addr>=act_b_base) begin
                arena_index=(addr-act_b_base)/DATA_BYTES;
                for (int beat=0;beat<beats;beat++) begin
                    if (arena_index+beat>=scratch_word_base &&
                        arena_index+beat<scratch_word_base+scratch_words) begin
                        scratch_index=arena_index+beat-scratch_word_base;
                        if (!scratch_valid_b[scratch_index])
                            $fatal(1, "v10 DDR activation B scratch AR before B handshake word=%0d addr=%h",
                                   scratch_index,addr+ADDR_W'(beat*DATA_BYTES));
                    end
                end
            end
        end
    endtask

    task automatic reserve_scratch_write(input int master,
                                         input logic [ADDR_W-1:0] addr,
                                         input int unsigned beats);
        longint unsigned arena_index;
        int unsigned scratch_index;
        begin
            arena_index=(addr-(master==0 ? act_a_base : act_b_base))/DATA_BYTES;
            for (int beat=0;beat<beats;beat++) begin
                if (arena_index+beat>=scratch_word_base &&
                    arena_index+beat<scratch_word_base+scratch_words) begin
                    scratch_index=arena_index+beat-scratch_word_base;
                    if (master==0) begin
                        if (scratch_valid_a[scratch_index] &&
                            !scratch_read_a[scratch_index] &&
                            !scratch_released_same_cycle(master,scratch_index))
                            $fatal(1, "v10 DDR activation A scratch overwritten before release word=%0d",
                                   scratch_index);
                        scratch_valid_a[scratch_index]<=1'b0;
                    end else begin
                        if (scratch_valid_b[scratch_index] &&
                            !scratch_read_b[scratch_index] &&
                            !scratch_released_same_cycle(master,scratch_index))
                            $fatal(1, "v10 DDR activation B scratch overwritten before release word=%0d",
                                   scratch_index);
                        scratch_valid_b[scratch_index]<=1'b0;
                    end
                end
            end
        end
    endtask

    task automatic commit_write_burst(input int master);
        longint unsigned index;
        begin
            if (wr_burst_base[master][3:0] != 0)
                $fatal(1, "v10 DDR unaligned write master=%0d addr=%h", master,
                       wr_burst_base[master]);
            if (wr_burst_base[master] >= act_a_base &&
                wr_burst_base[master]+ADDR_W'(wr_burst_beats[master])*DATA_BYTES <=
                    act_a_base+64'(act_words)*DATA_BYTES) begin
                if (master!=0)
                    $fatal(1, "v10 DDR wrong write master for activation A master=%0d addr=%h",
                           master,wr_burst_base[master]);
                index=(wr_burst_base[master]-act_a_base)/DATA_BYTES;
                for (int beat=0;beat<wr_burst_beats[master];beat++) begin
                    activation_a[index+beat] <= pending_write[master][beat];
                end
            end else if (wr_burst_base[master] >= act_b_base &&
                         wr_burst_base[master]+ADDR_W'(wr_burst_beats[master])*DATA_BYTES <=
                            act_b_base+64'(act_words)*DATA_BYTES) begin
                if (master!=1)
                    $fatal(1, "v10 DDR wrong write master for activation B master=%0d addr=%h",
                           master,wr_burst_base[master]);
                index=(wr_burst_base[master]-act_b_base)/DATA_BYTES;
                for (int beat=0;beat<wr_burst_beats[master];beat++) begin
                    activation_b[index+beat] <= pending_write[master][beat];
                end
            end else begin
                $fatal(1, "v10 DDR write outside one activation region master=%0d addr=%h beats=%0d",
                       master,wr_burst_base[master],wr_burst_beats[master]);
            end
        end
    endtask

    task automatic commit_scratch_response(input int master);
        longint unsigned index;
        begin
            index=(wr_burst_base[master]-(master==0 ? act_a_base : act_b_base)) /
                  DATA_BYTES;
            for (int beat=0;beat<wr_burst_beats[master];beat++) begin
                if (index+beat>=scratch_word_base &&
                    index+beat<scratch_word_base+scratch_words) begin
                    if (master==0) begin
                        scratch_valid_a[index+beat-scratch_word_base]<=1'b1;
                        scratch_read_a[index+beat-scratch_word_base]<=1'b0;
                    end else begin
                        scratch_valid_b[index+beat-scratch_word_base]<=1'b1;
                        scratch_read_b[index+beat-scratch_word_base]<=1'b0;
                    end
                end
            end
        end
    endtask

    always_comb begin
        ar_grant=-1;
        rd_arready='0;
        if (rst_n) begin
            for (int offset=0;offset<NUM_RD;offset++) begin
                int candidate;
                candidate=(ar_rr+offset)%NUM_RD;
                if (ar_grant<0 && rd_arvalid[candidate] && !read_client_pause[candidate] &&
                    !rd_active[candidate] &&
                    !rd_rvalid[candidate]) ar_grant=candidate;
            end
            if (ar_grant>=0) rd_arready[ar_grant]=1'b1;
        end
    end

    always_comb begin
        aw_grant=-1;
        wr_awready='0;
        if (rst_n) begin
            for (int offset=0;offset<NUM_WR;offset++) begin
                int candidate;
                candidate=(aw_rr+offset)%NUM_WR;
                if (aw_grant<0 && wr_awvalid[candidate] && !write_client_pause[candidate] &&
                    !wr_active[candidate] &&
                    !wr_bvalid[candidate]) aw_grant=candidate;
            end
            if (aw_grant>=0) wr_awready[aw_grant]=1'b1;
        end
    end

    always_comb begin
        token_cap=64'(token_denom)*(token_burst==0 ? 1 : token_burst);
        budget_open=rst_n && !force_pause && token_denom!=0 && token_credit>=token_denom;
        read_issue_grant=-1;
        write_data_grant=-1;
        wr_wready='0;
        if (budget_open) begin
            for (int offset=0;offset<TOTAL_DATA_CLIENTS;offset++) begin
                int candidate;
                candidate=(data_rr+offset)%TOTAL_DATA_CLIENTS;
                if (read_issue_grant<0 && write_data_grant<0) begin
                    if (candidate<NUM_RD) begin
                        if (!read_client_pause[candidate] && rd_active[candidate] &&
                            (!rd_rvalid[candidate] || rd_rready[candidate]))
                            read_issue_grant=candidate;
                    end else if (wr_active[candidate-NUM_RD] &&
                                 !write_client_pause[candidate-NUM_RD] &&
                                 !wr_pending_response[candidate-NUM_RD] &&
                                 !wr_bvalid[candidate-NUM_RD] &&
                                 wr_wvalid[candidate-NUM_RD]) begin
                        write_data_grant=candidate-NUM_RD;
                    end
                end
            end
            if (write_data_grant>=0) wr_wready[write_data_grant]=1'b1;
        end
        data_beat_issued=(read_issue_grant>=0) ||
                         (write_data_grant>=0 && wr_wvalid[write_data_grant]);
    end

    always_comb begin
        rd_rresp='0;
        wr_bresp='0;
        aggregate_read_beats=0;
        aggregate_write_beats=0;
        for (int r=0;r<NUM_RD;r++) aggregate_read_beats+=read_beats[r];
        for (int w=0;w<NUM_WR;w++) aggregate_write_beats+=write_beats[w];
    end

    always_ff @(posedge clk) begin
        if (!rst_n) begin
            rd_active<='0;
            rd_rvalid<='0;
            rd_rlast<='0;
            rd_rdata<='0;
            rd_rid<='0;
            wr_active<='0;
            wr_pending_response<='0;
            wr_bvalid<='0;
            wr_bid<='0;
            ar_rr<=0;
            aw_rr<=0;
            data_rr<=0;
            token_credit<=0;
            read_beats<='0;
            read_bursts<='0;
            read_backpressure_cycles<='0;
            read_pause_hit_cycles<='0;
            write_beats<='0;
            write_bursts<='0;
            write_backpressure_cycles<='0;
            write_pause_hit_cycles<='0;
            aggregate_budget_beats<=0;
            for (int r=0;r<NUM_RD;r++) begin
                rd_next_addr[r]<='0;
                rd_response_addr[r]<='0;
                rd_beats_left[r]<='0;
                rd_saved_id[r]<='0;
            end
            for (int w=0;w<NUM_WR;w++) begin
                wr_next_addr[w]<='0;
                wr_burst_base[w]<='0;
                wr_beats_left[w]<='0;
                wr_burst_beats[w]<='0;
                wr_buffer_position[w]<='0;
                wr_saved_id[w]<='0;
                wr_delay[w]<=0;
            end
            for (int s=0;s<MAX_TRANSIENT_WORDS;s++) begin
                scratch_valid_a[s]<=1'b0;
                scratch_valid_b[s]<=1'b0;
                scratch_read_a[s]<=1'b0;
                scratch_read_b[s]<=1'b0;
            end
            for (int core=0;core<NUM_WR;core++) begin
                residual_write_bursts[core]<=0;
                residual_read_bursts[core]<=0;
                residual_write_wraps[core]<=0;
                residual_read_wraps[core]<=0;
                legacy_stage_write_bursts[core]<=0;
                legacy_stage_read_bursts[core]<=0;
                residual_last_write_slot[core]<=-1;
                residual_last_read_slot[core]<=-1;
            end
        end else begin
            if (token_denom==0 || token_numer>token_denom || token_burst==0)
                $fatal(1, "v10 DDR invalid token budget numer=%0d denom=%0d burst=%0d",
                       token_numer,token_denom,token_burst);
            if (scratch_words>MAX_TRANSIENT_WORDS ||
                scratch_word_base+scratch_words>act_words)
                $fatal(1, "v10 DDR invalid scratch window base=%0d words=%0d arena=%0d",
                       scratch_word_base,scratch_words,act_words);
            if (scoreboard_new_launch) begin
                if (|rd_active || |rd_rvalid || |wr_active ||
                    |wr_pending_response || |wr_bvalid)
                    $fatal(1, "v10 DDR new launch while AXI transaction remains active");
                for (int s=0;s<MAX_TRANSIENT_WORDS;s++) begin
                    if ((scratch_valid_a[s] && !scratch_read_a[s]) ||
                        (scratch_valid_b[s] && !scratch_read_b[s]))
                        $fatal(1, "v10 DDR scratch generation ended before release word=%0d A=%0d/%0d B=%0d/%0d",
                               s,scratch_valid_a[s],scratch_read_a[s],
                               scratch_valid_b[s],scratch_read_b[s]);
                    scratch_valid_a[s]<=1'b0;
                    scratch_valid_b[s]<=1'b0;
                    scratch_read_a[s]<=1'b0;
                    scratch_read_b[s]<=1'b0;
                end
                for (int core=0;core<NUM_WR;core++) begin
                    residual_write_bursts[core]<=0;
                    residual_read_bursts[core]<=0;
                    residual_write_wraps[core]<=0;
                    residual_read_wraps[core]<=0;
                    legacy_stage_write_bursts[core]<=0;
                    legacy_stage_read_bursts[core]<=0;
                    residual_last_write_slot[core]<=-1;
                    residual_last_read_slot[core]<=-1;
                end
            end
            // Shared token bucket: all read and write data beats draw from this
            // single credit balance. Address and response channels do not.
            if (data_beat_issued) begin
                token_credit<=token_credit-token_denom+token_numer;
                aggregate_budget_beats<=aggregate_budget_beats+1;
                data_rr<=((read_issue_grant>=0 ? read_issue_grant :
                           NUM_RD+write_data_grant)+1)%TOTAL_DATA_CLIENTS;
            end else if (token_credit+token_numer>token_cap) begin
                token_credit<=token_cap;
            end else begin
                token_credit<=token_credit+token_numer;
            end

            if (ar_grant>=0 && rd_arvalid[ar_grant] && rd_arready[ar_grant]) begin
                if (rd_arsize[ar_grant] != $clog2(DATA_BYTES) ||
                    rd_arburst[ar_grant] != 2'b01 || rd_araddr[ar_grant][3:0] != 0)
                    $fatal(1, "v10 DDR invalid AR master=%0d addr=%h size=%0d burst=%0d",
                           ar_grant,rd_araddr[ar_grant],rd_arsize[ar_grant],
                           rd_arburst[ar_grant]);
                if ((int'(rd_araddr[ar_grant][11:0])+
                     (int'(rd_arlen[ar_grant])+1)*DATA_BYTES)>4096)
                    $fatal(1, "v10 DDR read burst crosses 4K master=%0d addr=%h len=%0d",
                           ar_grant,rd_araddr[ar_grant],rd_arlen[ar_grant]);
                if (int'(rd_arlen[ar_grant])+1>MAX_BURST_BEATS)
                    $fatal(1, "v10 DDR read burst exceeds model limit len=%0d",
                           int'(rd_arlen[ar_grant])+1);
                // The request itself is forbidden before the preceding write
                // response handshake. Checking only at R consumption would
                // miss an early AR hidden by downstream R backpressure.
                assert_scratch_read_committed(ar_grant,rd_araddr[ar_grant],
                                              int'(rd_arlen[ar_grant])+1);
                record_activation_read_burst(ar_grant,rd_araddr[ar_grant]);
                rd_active[ar_grant]<=1'b1;
                rd_next_addr[ar_grant]<=rd_araddr[ar_grant];
                rd_beats_left[ar_grant]<=int'(rd_arlen[ar_grant])+1;
                rd_saved_id[ar_grant]<=rd_arid[ar_grant];
                read_bursts[ar_grant]<=read_bursts[ar_grant]+1;
                ar_rr<=(ar_grant+1)%NUM_RD;
            end

            for (int r=0;r<NUM_RD;r++) begin
                if (read_client_pause[r] &&
                    (rd_arvalid[r] || rd_active[r] || rd_rvalid[r]))
                    read_pause_hit_cycles[r]<=read_pause_hit_cycles[r]+1;
                if (rd_rvalid[r] && !rd_rready[r])
                    read_backpressure_cycles[r]<=read_backpressure_cycles[r]+1;
                if (rd_rvalid[r] && $isunknown(rd_rdata[r]))
                    $fatal(1, "v10 DDR presented X RDATA master=%0d response_addr=%h beat_count=%0d data=%h ready=%b",
                           r,rd_response_addr[r],read_beats[r],rd_rdata[r],
                           rd_rready[r]);
                if (rd_rvalid[r] && rd_rready[r]) begin
                    // A scratch word is released only when the DUT accepts its
                    // R beat. Merely issuing or presenting the beat is too weak:
                    // a stalled R channel must keep the old chunk protected.
                    record_scratch_read(r,rd_response_addr[r]);
                    read_beats[r]<=read_beats[r]+1;
                    rd_rvalid[r]<=1'b0;
                end
            end
            if (read_issue_grant>=0) begin
                rd_rdata[read_issue_grant]
                    <=read_memory(read_issue_grant,rd_next_addr[read_issue_grant]);
                rd_response_addr[read_issue_grant]<=rd_next_addr[read_issue_grant];
                rd_rlast[read_issue_grant]<=(rd_beats_left[read_issue_grant]==1);
                rd_rid[read_issue_grant]<=rd_saved_id[read_issue_grant];
                rd_rvalid[read_issue_grant]<=1'b1;
                rd_next_addr[read_issue_grant]<=rd_next_addr[read_issue_grant]+DATA_BYTES;
                if (rd_beats_left[read_issue_grant]==1) begin
                    rd_beats_left[read_issue_grant]<=0;
                    rd_active[read_issue_grant]<=1'b0;
                end else begin
                    rd_beats_left[read_issue_grant]<=rd_beats_left[read_issue_grant]-1;
                end
            end

            if (aw_grant>=0 && wr_awvalid[aw_grant] && wr_awready[aw_grant]) begin
                if (wr_awsize[aw_grant] != $clog2(DATA_BYTES) ||
                    wr_awburst[aw_grant] != 2'b01 || wr_awaddr[aw_grant][3:0] != 0)
                    $fatal(1, "v10 DDR invalid AW master=%0d addr=%h size=%0d burst=%0d",
                           aw_grant,wr_awaddr[aw_grant],wr_awsize[aw_grant],
                           wr_awburst[aw_grant]);
                if ((int'(wr_awaddr[aw_grant][11:0])+
                     (int'(wr_awlen[aw_grant])+1)*DATA_BYTES)>4096)
                    $fatal(1, "v10 DDR write burst crosses 4K master=%0d addr=%h len=%0d",
                           aw_grant,wr_awaddr[aw_grant],wr_awlen[aw_grant]);
                if (int'(wr_awlen[aw_grant])+1>MAX_BURST_BEATS)
                    $fatal(1, "v10 DDR write burst exceeds model buffer len=%0d",
                           int'(wr_awlen[aw_grant])+1);
                if (aw_grant==0 &&
                    (wr_awaddr[aw_grant]<act_a_base ||
                     wr_awaddr[aw_grant]+ADDR_W'(int'(wr_awlen[aw_grant])+1)*DATA_BYTES>
                        act_a_base+64'(act_words)*DATA_BYTES))
                    $fatal(1, "v10 DDR activation A AW outside arena addr=%h len=%0d",
                           wr_awaddr[aw_grant],wr_awlen[aw_grant]);
                if (aw_grant==1 &&
                    (wr_awaddr[aw_grant]<act_b_base ||
                     wr_awaddr[aw_grant]+ADDR_W'(int'(wr_awlen[aw_grant])+1)*DATA_BYTES>
                        act_b_base+64'(act_words)*DATA_BYTES))
                    $fatal(1, "v10 DDR activation B AW outside arena addr=%h len=%0d",
                           wr_awaddr[aw_grant],wr_awlen[aw_grant]);
                wr_active[aw_grant]<=1'b1;
                wr_next_addr[aw_grant]<=wr_awaddr[aw_grant];
                wr_burst_base[aw_grant]<=wr_awaddr[aw_grant];
                wr_beats_left[aw_grant]<=int'(wr_awlen[aw_grant])+1;
                wr_burst_beats[aw_grant]<=int'(wr_awlen[aw_grant])+1;
                wr_buffer_position[aw_grant]<=0;
                wr_saved_id[aw_grant]<=wr_awid[aw_grant];
                write_bursts[aw_grant]<=write_bursts[aw_grant]+1;
                aw_rr<=(aw_grant+1)%NUM_WR;
                reserve_scratch_write(aw_grant,wr_awaddr[aw_grant],
                                      int'(wr_awlen[aw_grant])+1);
                record_activation_write_burst(aw_grant,wr_awaddr[aw_grant]);
            end

            for (int w=0;w<NUM_WR;w++) begin
                if (write_client_pause[w] &&
                    (wr_awvalid[w] || wr_active[w] || wr_wvalid[w]))
                    write_pause_hit_cycles[w]<=write_pause_hit_cycles[w]+1;
                if (wr_wvalid[w] && !wr_wready[w])
                    write_backpressure_cycles[w]<=write_backpressure_cycles[w]+1;
                if (wr_bvalid[w] && wr_bready[w]) begin
                    // This is the architectural commit point used by the
                    // residual scratch fence. A merely asserted, stalled
                    // BVALID must not authorize a dependent PW2 read.
                    commit_scratch_response(w);
                    wr_bvalid[w]<=1'b0;
                    wr_active[w]<=1'b0;
                end
            end
            if (write_data_grant>=0 && wr_wvalid[write_data_grant] &&
                wr_wready[write_data_grant]) begin
                if (enabled_write_has_x(wr_wdata[write_data_grant],
                                        wr_wstrb[write_data_grant]))
                    $fatal(1, "v10 DDR accepted X WDATA master=%0d burst_base=%h beat_addr=%h beat=%0d total_w=%0d/%0d data=%h",
                           write_data_grant,wr_burst_base[write_data_grant],
                           wr_next_addr[write_data_grant],
                           wr_buffer_position[write_data_grant],
                           write_beats[0],write_beats[1],
                           wr_wdata[write_data_grant]);
                if (wr_wstrb[write_data_grant] != {DATA_BYTES{1'b1}} ||
                    wr_wlast[write_data_grant] != (wr_beats_left[write_data_grant]==1))
                    $fatal(1, "v10 DDR bad W beat master=%0d addr=%h strb=%h last=%b left=%0d",
                           write_data_grant,wr_next_addr[write_data_grant],
                           wr_wstrb[write_data_grant],wr_wlast[write_data_grant],
                           wr_beats_left[write_data_grant]);
                pending_write[write_data_grant][wr_buffer_position[write_data_grant]]
                    <=wr_wdata[write_data_grant];
                wr_buffer_position[write_data_grant]
                    <=wr_buffer_position[write_data_grant]+1;
                wr_next_addr[write_data_grant]
                    <=wr_next_addr[write_data_grant]+DATA_BYTES;
                write_beats[write_data_grant]<=write_beats[write_data_grant]+1;
                if (wr_beats_left[write_data_grant]==1) begin
                    wr_beats_left[write_data_grant]<=0;
                    wr_pending_response[write_data_grant]<=1'b1;
                    wr_delay[write_data_grant]<=write_response_delay;
                end else begin
                    wr_beats_left[write_data_grant]
                        <=wr_beats_left[write_data_grant]-1;
                end
            end

            for (int w=0;w<NUM_WR;w++) begin
                if (wr_pending_response[w]) begin
                    if (wr_delay[w]!=0) begin
                        wr_delay[w]<=wr_delay[w]-1;
                    end else begin
                        commit_write_burst(w);
                        wr_bvalid[w]<=1'b1;
                        wr_bid[w]<=wr_saved_id[w];
                        wr_pending_response[w]<=1'b0;
                    end
                end
            end
        end
    end
endmodule
