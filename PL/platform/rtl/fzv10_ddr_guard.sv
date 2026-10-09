`timescale 1ns/1ps

// ABI10: six shutdown managers ordered PARAM1, PARAM2, A_READ, A_WRITE,
// B_READ, B_WRITE. ACKS at 0x14 packs all[5:0], read[11:6], write[17:12].
// All six acknowledgements in every class are mandatory before safe reset.
// CAPS 0x7ff uses ABI10 meanings, not the older four-master capability map:
// bit0 six shutdown requests; bit1 six read acknowledgements; bit2 six write
// acknowledgements; bit3 transaction-drain counters; bit4 AXI response latch;
// bit5 guarded reset; bit6 permanent poison; bit7 64-bit job-cycle timer;
// bit8 protocol-error latch; bit9 reset feedback; bit10 external HLS handshake.
// Register offsets, CONTROL commands and STATUS/ERROR bits retain the v4
// guard semantics; board wiring and clocks require separate integration proof.

module fzv10_ddr_guard #(
    parameter logic [31:0] ID_VALUE          = 32'h465a5641,
    parameter logic [31:0] ABI_VERSION_VALUE = 32'h000a0004,
    parameter logic [31:0] CAPS_VALUE        = 32'h000007ff,
    parameter int unsigned RESET_CYCLES      = 32
) (
    input  logic        clk,
    input  logic        rst,

    input  logic [15:0] s_awaddr,
    input  logic        s_awvalid,
    output logic        s_awready,
    input  logic [31:0] s_wdata,
    input  logic [3:0]  s_wstrb,
    input  logic        s_wvalid,
    output logic        s_wready,
    output logic [1:0]  s_bresp,
    output logic        s_bvalid,
    input  logic        s_bready,
    input  logic [15:0] s_araddr,
    input  logic        s_arvalid,
    output logic        s_arready,
    output logic [31:0] s_rdata,
    output logic [1:0]  s_rresp,
    output logic        s_rvalid,
    input  logic        s_rready,

    input  logic [5:0]  shutdown_ack,
    input  logic [5:0]  shutdown_rd_ack,
    input  logic [5:0]  shutdown_wr_ack,
    output logic [5:0]  shutdown_request,

    input  logic        down_ar_fire,
    input  logic [1:0]  down_rresp,
    input  logic        down_r_fire,
    input  logic        down_rlast_fire,
    input  logic        down_aw_fire,
    input  logic        down_wlast_fire,
    input  logic [1:0]  down_bresp,
    input  logic        down_b_fire,

    input  logic        hls_ap_idle,
    input  logic        hls_ap_done,
    input  logic        hls_ap_ready,
    input  logic [31:0] hls_protocol_error,
    input  logic        hls_protocol_error_ap_vld,
    input  logic        core_reset_feedback_aresetn,
    output logic        hls_ap_start,
    output logic        core_reset_req,

    output logic        safe_to_reset,
    output logic        poisoned,
    output logic [31:0] debug_status,
    output logic [31:0] debug_error_flags
);
    localparam logic [1:0] AXI_OKAY   = 2'b00;
    localparam logic [1:0] AXI_SLVERR = 2'b10;

    localparam logic [15:0] REG_ID               = 16'h0000;
    localparam logic [15:0] REG_ABI              = 16'h0004;
    localparam logic [15:0] REG_CAPS             = 16'h0008;
    localparam logic [15:0] REG_CONTROL          = 16'h000c;
    localparam logic [15:0] REG_STATUS           = 16'h0010;
    localparam logic [15:0] REG_SHUTDOWN_ACK     = 16'h0014;
    localparam logic [15:0] REG_AR_ACCEPTED      = 16'h0018;
    localparam logic [15:0] REG_RLAST_ACCEPTED   = 16'h001c;
    localparam logic [15:0] REG_AW_ACCEPTED      = 16'h0020;
    localparam logic [15:0] REG_WLAST_ACCEPTED   = 16'h0024;
    localparam logic [15:0] REG_B_ACCEPTED       = 16'h0028;
    localparam logic [15:0] REG_ERROR_FLAGS      = 16'h002c;
    localparam logic [15:0] REG_RESET_GENERATION = 16'h0030;
    localparam logic [15:0] REG_JOB_CYCLES_LO    = 16'h0034;
    localparam logic [15:0] REG_JOB_CYCLES_HI    = 16'h0038;
    localparam logic [15:0] REG_PROTOCOL_ERROR   = 16'h003c;

    localparam int unsigned RESET_COUNT_WIDTH =
        (RESET_CYCLES < 2) ? 1 : $clog2(RESET_CYCLES + 1);

    logic        aw_full;
    logic        w_full;
    logic [15:0] awaddr_q;
    logic [31:0] wdata_q;
    logic [3:0]  wstrb_q;
    logic        write_fire;
    logic        write_bad;
    logic        control_write;

    logic        shutdown_latched;
    logic        axi_response_error;
    logic        counter_error;
    logic        hls_error_latched;
    logic [31:0] hls_error_code_latched;
    logic        done_latched;
    logic [31:0] ar_accepted;
    logic [31:0] rlast_accepted;
    logic [31:0] aw_accepted;
    logic [31:0] wlast_accepted;
    logic [31:0] b_accepted;
    logic [31:0] reset_generation;
    logic [RESET_COUNT_WIDTH-1:0] reset_count;
    logic        reset_active;
    logic        counters_quiescent;
    logic        all_shutdown_ack;
    logic        all_read_ack;
    logic        all_write_ack;
    logic        monitor_fire;
    logic        counter_clear_request;
    logic        set_shutdown_request;
    logic        clear_shutdown_request;
    logic        reset_request;
    logic        poison_request;
    logic        start_request;
    logic        hls_busy;
    logic        job_timer_running;
    logic        job_complete;
    logic [63:0] job_cycles;

    assign s_awready = !aw_full && !s_bvalid;
    assign s_wready  = !w_full && !s_bvalid;
    assign s_arready = !s_rvalid;
    assign write_fire = aw_full && w_full && !s_bvalid;
    assign control_write = write_fire && !write_bad && (awaddr_q == REG_CONTROL);

    assign set_shutdown_request   = control_write && wdata_q[0];
    assign clear_shutdown_request = control_write && wdata_q[1];
    assign reset_request          = control_write && wdata_q[2];
    assign counter_clear_request  = control_write && wdata_q[3];
    assign poison_request         = control_write && wdata_q[4];
    assign start_request          = control_write && wdata_q[5];

    assign monitor_fire = down_ar_fire || down_r_fire || down_rlast_fire || down_aw_fire ||
                          down_wlast_fire || down_b_fire;
    assign counters_quiescent = (ar_accepted == rlast_accepted) &&
                                (aw_accepted == wlast_accepted) &&
                                (aw_accepted == b_accepted);
    assign all_shutdown_ack = &shutdown_ack;
    assign all_read_ack = &shutdown_rd_ack;
    assign all_write_ack = &shutdown_wr_ack;
    assign safe_to_reset = shutdown_latched && all_shutdown_ack &&
                           all_read_ack && all_write_ack &&
                           counters_quiescent && !monitor_fire;
    assign reset_active = core_reset_req || !core_reset_feedback_aresetn;
    assign shutdown_request = {6{shutdown_latched}};
    assign job_complete = job_timer_running && (done_latched || hls_ap_done) &&
                          hls_ap_idle && counters_quiescent && !monitor_fire;

    assign debug_status = {
        16'd0,
        job_timer_running,
        hls_ap_ready,
        hls_busy,
        core_reset_feedback_aresetn,
        done_latched,
        hls_ap_idle,
        counter_error,
        axi_response_error,
        poisoned,
        reset_active,
        safe_to_reset,
        counters_quiescent,
        all_write_ack,
        all_read_ack,
        all_shutdown_ack,
        shutdown_latched
    };
    assign debug_error_flags = {
        27'd0,
        hls_error_latched,
        counter_error,
        axi_response_error,
        poisoned,
        1'b0
    };

    always_comb begin
        write_bad = 1'b0;
        if ((awaddr_q[1:0] != 2'b00) || (wstrb_q != 4'hf)) begin
            write_bad = 1'b1;
        end else if (awaddr_q != REG_CONTROL) begin
            write_bad = 1'b1;
        end else if ((wdata_q & 32'hffffffc0) != 32'd0) begin
            write_bad = 1'b1;
        end else if (!$onehot0(wdata_q[5:0])) begin
            write_bad = 1'b1;
        end else if (wdata_q[2] && !safe_to_reset) begin
            write_bad = 1'b1;
        end else if (wdata_q[3] &&
                     (!safe_to_reset || reset_active || monitor_fire)) begin
            write_bad = 1'b1;
        end else if (wdata_q[1] && (poisoned || reset_active)) begin
            write_bad = 1'b1;
        end else if (wdata_q[5] &&
                     (shutdown_latched || poisoned || reset_active || hls_busy ||
                      !counters_quiescent || !hls_ap_idle)) begin
            write_bad = 1'b1;
        end
    end

    always_ff @(posedge clk) begin
        if (rst) begin
            aw_full <= 1'b0;
            w_full <= 1'b0;
            awaddr_q <= '0;
            wdata_q <= '0;
            wstrb_q <= '0;
            s_bresp <= AXI_OKAY;
            s_bvalid <= 1'b0;
            s_rdata <= '0;
            s_rresp <= AXI_OKAY;
            s_rvalid <= 1'b0;
        end else begin
            if (s_awready && s_awvalid) begin
                aw_full <= 1'b1;
                awaddr_q <= s_awaddr;
            end
            if (s_wready && s_wvalid) begin
                w_full <= 1'b1;
                wdata_q <= s_wdata;
                wstrb_q <= s_wstrb;
            end
            if (write_fire) begin
                aw_full <= 1'b0;
                w_full <= 1'b0;
                s_bresp <= write_bad ? AXI_SLVERR : AXI_OKAY;
                s_bvalid <= 1'b1;
            end else if (s_bvalid && s_bready) begin
                s_bvalid <= 1'b0;
            end

            if (s_arready && s_arvalid) begin
                s_rvalid <= 1'b1;
                s_rresp <= AXI_OKAY;
                unique case (s_araddr)
                    REG_ID:               s_rdata <= ID_VALUE;
                    REG_ABI:              s_rdata <= ABI_VERSION_VALUE;
                    REG_CAPS:             s_rdata <= CAPS_VALUE;
                    REG_CONTROL:          s_rdata <= 32'd0;
                    REG_STATUS:           s_rdata <= debug_status;
                    REG_SHUTDOWN_ACK:     s_rdata <= {14'd0, shutdown_wr_ack,
                                                      shutdown_rd_ack,
                                                      shutdown_ack};
                    REG_AR_ACCEPTED:      s_rdata <= ar_accepted;
                    REG_RLAST_ACCEPTED:   s_rdata <= rlast_accepted;
                    REG_AW_ACCEPTED:      s_rdata <= aw_accepted;
                    REG_WLAST_ACCEPTED:   s_rdata <= wlast_accepted;
                    REG_B_ACCEPTED:       s_rdata <= b_accepted;
                    REG_ERROR_FLAGS:      s_rdata <= debug_error_flags;
                    REG_RESET_GENERATION: s_rdata <= reset_generation;
                    REG_JOB_CYCLES_LO:    s_rdata <= job_cycles[31:0];
                    REG_JOB_CYCLES_HI:    s_rdata <= job_cycles[63:32];
                    REG_PROTOCOL_ERROR:   s_rdata <= hls_error_code_latched;
                    default: begin
                        s_rdata <= 32'd0;
                        s_rresp <= AXI_SLVERR;
                    end
                endcase
            end else if (s_rvalid && s_rready) begin
                s_rvalid <= 1'b0;
            end
        end
    end

    always_ff @(posedge clk) begin
        if (rst) begin
            shutdown_latched <= 1'b1;
            poisoned <= 1'b0;
            axi_response_error <= 1'b0;
            counter_error <= 1'b0;
            hls_error_latched <= 1'b0;
            hls_error_code_latched <= 32'd0;
            done_latched <= 1'b0;
            ar_accepted <= 32'd0;
            rlast_accepted <= 32'd0;
            aw_accepted <= 32'd0;
            wlast_accepted <= 32'd0;
            b_accepted <= 32'd0;
            reset_generation <= 32'd0;
            reset_count <= '0;
            hls_ap_start <= 1'b0;
            hls_busy <= 1'b0;
            job_timer_running <= 1'b0;
            job_cycles <= 64'd0;
            core_reset_req <= 1'b0;
        end else begin
            if (set_shutdown_request) begin
                shutdown_latched <= 1'b1;
            end else if (clear_shutdown_request) begin
                shutdown_latched <= 1'b0;
            end

            if (hls_ap_done) begin
                done_latched <= 1'b1;
            end

            if (start_request) begin
                hls_ap_start <= 1'b1;
                hls_busy <= 1'b1;
                done_latched <= 1'b0;
                hls_error_code_latched <= 32'd0;
            end else if (hls_ap_start && hls_ap_ready) begin
                hls_ap_start <= 1'b0;
            end

            if (start_request) begin
                job_timer_running <= 1'b1;
                job_cycles <= 64'd1;
            end else if (job_complete) begin
                job_timer_running <= 1'b0;
                hls_busy <= 1'b0;
            end else if (job_timer_running) begin
                if (job_cycles == 64'hffffffffffffffff) begin
                    counter_error <= 1'b1;
                end else begin
                    job_cycles <= job_cycles + 64'd1;
                end
            end

            if (reset_request) begin
                hls_ap_start <= 1'b0;
                hls_busy <= 1'b0;
                job_timer_running <= 1'b0;
            end

            if (counter_clear_request) begin
                ar_accepted <= 32'd0;
                rlast_accepted <= 32'd0;
                aw_accepted <= 32'd0;
                wlast_accepted <= 32'd0;
                b_accepted <= 32'd0;
                done_latched <= 1'b0;
            end else begin
                if (down_ar_fire) begin
                    if (ar_accepted == 32'hffffffff) begin
                        counter_error <= 1'b1;
                    end else begin
                        ar_accepted <= ar_accepted + 32'd1;
                    end
                end
                if (down_rlast_fire) begin
                    if (rlast_accepted == 32'hffffffff ||
                        ((rlast_accepted == ar_accepted) && !down_ar_fire)) begin
                        counter_error <= 1'b1;
                    end else begin
                        rlast_accepted <= rlast_accepted + 32'd1;
                    end
                end
                if (down_r_fire && (down_rresp != AXI_OKAY)) begin
                    axi_response_error <= 1'b1;
                end
                if (down_aw_fire) begin
                    if (aw_accepted == 32'hffffffff) begin
                        counter_error <= 1'b1;
                    end else begin
                        aw_accepted <= aw_accepted + 32'd1;
                    end
                end
                if (down_wlast_fire) begin
                    if (wlast_accepted == 32'hffffffff) begin
                        counter_error <= 1'b1;
                    end else begin
                        wlast_accepted <= wlast_accepted + 32'd1;
                    end
                end
                if (down_b_fire) begin
                    if (b_accepted == 32'hffffffff ||
                        ((b_accepted == aw_accepted) && !down_aw_fire) ||
                        ((b_accepted == wlast_accepted) && !down_wlast_fire)) begin
                        counter_error <= 1'b1;
                    end else begin
                        b_accepted <= b_accepted + 32'd1;
                    end
                    if (down_bresp != AXI_OKAY) begin
                        axi_response_error <= 1'b1;
                    end
                end
            end

            if (hls_protocol_error_ap_vld && (hls_protocol_error != 32'd0)) begin
                hls_error_latched <= 1'b1;
            end
            if (hls_protocol_error_ap_vld) begin
                hls_error_code_latched <= hls_protocol_error;
            end

            if (poison_request || axi_response_error || counter_error ||
                (hls_protocol_error_ap_vld && (hls_protocol_error != 32'd0))) begin
                poisoned <= 1'b1;
                shutdown_latched <= 1'b1;
            end

            if (reset_request) begin
                reset_count <= RESET_CYCLES[RESET_COUNT_WIDTH-1:0];
                core_reset_req <= 1'b1;
                reset_generation <= reset_generation + 32'd1;
            end else if (reset_count != '0) begin
                reset_count <= reset_count - 1'b1;
                core_reset_req <= 1'b1;
            end else begin
                core_reset_req <= 1'b0;
            end
        end
    end

endmodule

// tampered
