`timescale 1ns/1ps

module tb_cnn_v10_pw_half2x_fused_alu_clock_tree;
    localparam int QUEUE_DEPTH = 4096;
    localparam int CONTINUOUS_TRANSACTIONS = 256;
    localparam int RANDOM_CYCLES = 640;

    // The leaf is driven only from the real sibling BUFGCE_DIV clock tree.
    // The common 400 MHz root runs through GSR; lock remains low until the
    // UNISIM startup interval has elapsed.
    logic root_clk_400 = 1'b0;
    logic root_run = 1'b1;
    logic mmcm_locked = 1'b0;
    logic slow_clk;
    logic fast_clk;
    always #1.25 begin
        if (root_run)
            root_clk_400 = ~root_clk_400;
        else
            root_clk_400 = 1'b0;
    end

    logic fast_rst_q1 = 1'b1;
    logic fast_rst_q2 = 1'b1;
    logic slow_rst_q1 = 1'b1;
    logic slow_rst_q2 = 1'b1;
    wire reset_async = ~mmcm_locked;
    wire slow_reset_async = reset_async | fast_rst_q2;
    wire fast_rst = fast_rst_q2;
    wire slow_rst = slow_rst_q2;
    logic slow_ce = 1'b0;
    logic in_valid = 1'b0;
    logic signed [47:0] prior = '0;
    logic signed [15:0] value [0:15];
    logic signed [15:0] weight [0:15];
    logic out_valid;
    logic signed [47:0] result;

    logic signed [47:0] expected_data [0:QUEUE_DEPTH-1];
    logic expected_continuous [0:QUEUE_DEPTH-1];
    int expected_sequence [0:QUEUE_DEPTH-1];
    int accepted_enabled_cycle [0:QUEUE_DEPTH-1];
    int queue_head = 0;
    int queue_tail = 0;
    int slow_cycle = 0;
    int slow_enabled_cycle = 0;
    int sequence_number = 0;
    int accepted_since_reset = 0;
    int returned_since_reset = 0;
    int accepted_lifetime = 0;
    int returned_lifetime = 0;
    int discarded_by_reset = 0;
    int continuous_returns = 0;
    int continuous_gap_checks = 0;
    int latency8_checks = 0;
    int last_continuous_return_cycle = -1;
    int full_pause_cycles = 0;
    int half_boundary_pause_checks = 0;
    int half_boundary_reset_checks = 0;
    int random_reset_checks = 0;
    int synchronous_reset_count = 0;
    int fast_before_slow_release_checks = 0;
    int gsr_start_checks = 0;
    int relock_checks = 0;
    int ce_boundary_checks = 0;
    int pause_stability_checks = 0;
    int maximum_outstanding = 0;
    logic drive_is_continuous = 1'b0;
    logic pause_sample_valid = 1'b0;
    logic pause_out_valid = 1'b0;
    logic signed [47:0] pause_result = '0;

    cnn_v10_half2x_clock_tree clock_tree (
        .root_clk_400(root_clk_400),
        .driver_job_clk_200(slow_clk),
        .pw_local_clk_400(fast_clk)
    );

    // Platform-equivalent reset ordering: async assertion from lock loss,
    // fast synchronous release first, then slow synchronous release gated by
    // the synchronized fast reset.
    always_ff @(posedge fast_clk or posedge reset_async) begin
        if (reset_async) begin
            fast_rst_q1 <= 1'b1;
            fast_rst_q2 <= 1'b1;
        end else begin
            fast_rst_q1 <= 1'b0;
            fast_rst_q2 <= fast_rst_q1;
        end
    end

    always_ff @(posedge slow_clk or posedge slow_reset_async) begin
        if (slow_reset_async) begin
            slow_rst_q1 <= 1'b1;
            slow_rst_q2 <= 1'b1;
        end else begin
            slow_rst_q1 <= 1'b0;
            slow_rst_q2 <= slow_rst_q1;
        end
    end

    cnn_v10_pw_dsp16_half2x_fused_alu dut (
        .slow_clk(slow_clk), .slow_rst(slow_rst), .slow_ce(slow_ce),
        .fast_clk(fast_clk), .fast_rst(fast_rst), .in_valid(in_valid),
        .prior(prior),
        .value0(value[0]), .weight0(weight[0]),
        .value1(value[1]), .weight1(weight[1]),
        .value2(value[2]), .weight2(weight[2]),
        .value3(value[3]), .weight3(weight[3]),
        .value4(value[4]), .weight4(weight[4]),
        .value5(value[5]), .weight5(weight[5]),
        .value6(value[6]), .weight6(weight[6]),
        .value7(value[7]), .weight7(weight[7]),
        .value8(value[8]), .weight8(weight[8]),
        .value9(value[9]), .weight9(weight[9]),
        .value10(value[10]), .weight10(weight[10]),
        .value11(value[11]), .weight11(weight[11]),
        .value12(value[12]), .weight12(weight[12]),
        .value13(value[13]), .weight13(weight[13]),
        .value14(value[14]), .weight14(weight[14]),
        .value15(value[15]), .weight15(weight[15]),
        .out_valid(out_valid), .result(result)
    );

    wire model_partial_valid, model_partial_phase1;
    wire [47:0] model_partial;
    integer fast_miter_checks = 0;
    cnn_v10_pw_half2x_fused_fast_model fast_model (
        .fast_clk(fast_clk), .fast_rst(fast_rst), .fast_ce(dut.fast_ce),
        .launch_valid(dut.launch_valid), .launch_phase1(dut.launch_phase1),
        .prior(dut.selected_prior),
        .value0(dut.selected_value0), .weight0(dut.selected_weight0),
        .value1(dut.selected_value1), .weight1(dut.selected_weight1),
        .value2(dut.selected_value2), .weight2(dut.selected_weight2),
        .value3(dut.selected_value3), .weight3(dut.selected_weight3),
        .value4(dut.selected_value4), .weight4(dut.selected_weight4),
        .value5(dut.selected_value5), .weight5(dut.selected_weight5),
        .value6(dut.selected_value6), .weight6(dut.selected_weight6),
        .value7(dut.selected_value7), .weight7(dut.selected_weight7),
        .partial_valid(model_partial_valid),
        .partial_phase1(model_partial_phase1), .partial(model_partial)
    );

    always @(posedge fast_clk) begin
        #1;
        if (!fast_rst) begin
            fast_miter_checks = fast_miter_checks + 1;
            if (model_partial_valid !== dut.half_valid)
                $fatal(1, "fused fast miter valid mismatch check=%0d model=%b dut=%b",
                       fast_miter_checks, model_partial_valid, dut.half_valid);
            if (model_partial_phase1 !== dut.half_phase1)
                $fatal(1, "fused fast miter phase mismatch check=%0d model=%b dut=%b",
                       fast_miter_checks, model_partial_phase1, dut.half_phase1);
            if (model_partial_valid && model_partial !== dut.half_partial)
                $fatal(1, "fused fast miter data mismatch check=%0d model=%h dut=%h",
                       fast_miter_checks, model_partial, dut.half_partial);
        end
    end

    function automatic logic signed [47:0] reference_mac;
        input logic signed [47:0] p;
        longint signed sum;
        int k;
        begin
            sum = p;
            for (k = 0; k < 16; k++)
                sum = sum + $signed(value[k]) * $signed(weight[k]);
            reference_mac = sum[47:0];
        end
    endfunction

    task automatic clear_inputs;
        int k;
        begin
            prior = '0;
            for (k = 0; k < 16; k++) begin
                value[k] = '0;
                weight[k] = '0;
            end
        end
    endtask

    task automatic drive_random(input int index);
        int k;
        begin
            prior = $signed({$urandom, $urandom}) & 48'hffffffffffff;
            for (k = 0; k < 16; k++) begin
                value[k] = $urandom;
                weight[k] = $urandom;
            end
            if ((index % 29) == 0) begin
                prior = 48'sh800000000000;
                value[0] = -16'sd32768;
                weight[0] = -16'sd32768;
                value[1] = 16'sd32767;
                weight[1] = -16'sd32768;
                value[15] = -16'sd1;
                weight[15] = 16'sd32767;
            end
        end
    endtask

    task automatic drive_directed(input int index);
        int k;
        begin
            clear_inputs();
            unique case (index)
                0: begin prior = 48'sd0; value[0] = 16'sd1; weight[0] = 16'sd1; end
                1: begin prior = -48'sd1; value[0] = -16'sd1; weight[0] = 16'sd1; end
                2: begin prior = 48'sh7fffffffffff; value[0] = 16'sd1; weight[0] = 16'sd1; end
                3: begin prior = 48'sh800000000000; value[0] = -16'sd1; weight[0] = 16'sd1; end
                4: begin value[0] = -16'sd32768; weight[0] = -16'sd32768; end
                5: begin value[0] = 16'sd32767; weight[0] = 16'sd32767; end
                6: begin value[0] = -16'sd32768; weight[0] = 16'sd32767; end
                7: begin
                    prior = 48'sh123456789abc;
                    for (k = 0; k < 16; k++) begin
                        value[k] = (k[0]) ? -16'sd32768 : 16'sd32767;
                        weight[k] = (k[1]) ? -16'sd32768 : 16'sd32767;
                    end
                end
                default: drive_random(index);
            endcase
        end
    endtask

    task automatic drop_lock(input logic stop_root);
        begin
            slow_ce = 1'b0;
            in_valid = 1'b0;
            drive_is_continuous = 1'b0;
            mmcm_locked = 1'b0;
            #1ps;
            if (fast_rst !== 1'b1 || slow_rst !== 1'b1)
                $fatal(1, "lock loss did not asynchronously assert both resets fast=%b slow=%b",
                       fast_rst, slow_rst);
            if (stop_root)
                root_run = 1'b0;
        end
    endtask

    task automatic release_lock(input int unlocked_root_cycles);
        time fast_release_time;
        time slow_release_time;
        begin
            fast_release_time = 0;
            slow_release_time = 0;
            if (!root_run) begin
                #(unlocked_root_cycles * 2.5ns);
                root_run = 1'b1;
            end else begin
                repeat (unlocked_root_cycles) @(posedge fast_clk);
            end
            repeat (4) @(posedge fast_clk);
            if (fast_rst !== 1'b1 || slow_rst !== 1'b1)
                $fatal(1, "consumer reset released while lock low fast=%b slow=%b",
                       fast_rst, slow_rst);
            mmcm_locked = 1'b1;
            fork
                begin @(negedge fast_rst); fast_release_time = $time; end
                begin @(negedge slow_rst); slow_release_time = $time; end
            join
            if (fast_release_time == 0 || slow_release_time == 0 ||
                fast_release_time >= slow_release_time)
                $fatal(1, "reset release order invalid fast=%0t slow=%0t",
                       fast_release_time, slow_release_time);
            synchronous_reset_count++;
            fast_before_slow_release_checks++;
            repeat (2) @(posedge slow_clk);
        end
    endtask

    task automatic apply_lock_reset(input int unlocked_root_cycles,
                                    input logic stop_root,
                                    input logic midpoint_phase);
        begin
            // Exercise both coincident slow/fast phase-1 edges and the
            // midpoint fast phase-0 edge between adjacent slow edges.
            @(posedge slow_clk);
            if (midpoint_phase)
                @(posedge fast_clk);
            drop_lock(stop_root);
            release_lock(unlocked_root_cycles);
            relock_checks++;
        end
    endtask

    task automatic drain_expected(input int limit);
        int waited;
        begin
            @(negedge slow_clk);
            slow_ce = 1'b1;
            in_valid = 1'b0;
            drive_is_continuous = 1'b0;
            waited = 0;
            while ((queue_head != queue_tail || out_valid) && waited < limit) begin
                @(posedge slow_clk);
                #2ps;
                waited++;
            end
            if (queue_head != queue_tail)
                $fatal(1, "drain timeout outstanding=%0d", queue_tail - queue_head);
        end
    endtask

    // Transactions are accepted and committed only on enabled slow edges.
    always @(posedge slow_clk) begin
        int outstanding;
        slow_cycle++;
        #1ps;
        if (slow_rst) begin
            discarded_by_reset += queue_tail - queue_head;
            queue_head = 0;
            queue_tail = 0;
            slow_enabled_cycle = 0;
            accepted_since_reset = 0;
            returned_since_reset = 0;
            last_continuous_return_cycle = -1;
            pause_sample_valid = 1'b0;
        end else begin
            if (slow_ce)
                slow_enabled_cycle++;
            if ($isunknown(out_valid) || (out_valid && $isunknown(result)))
                $fatal(1, "unknown output at slow cycle %0d valid=%b result=%h",
                       slow_cycle, out_valid, result);

            if (!slow_ce) begin
                full_pause_cycles++;
                if (pause_sample_valid) begin
                    if (out_valid !== pause_out_valid || result !== pause_result)
                        $fatal(1, "output changed while slow_ce=0 valid=%b/%b result=%h/%h",
                               out_valid, pause_out_valid, result, pause_result);
                    pause_stability_checks++;
                end
                pause_sample_valid = 1'b1;
                pause_out_valid = out_valid;
                pause_result = result;
            end else begin
                pause_sample_valid = 1'b0;
            end

            if (slow_ce && out_valid) begin
                if (queue_head == queue_tail)
                    $fatal(1, "unexpected output with empty scoreboard at cycle %0d result=%h",
                           slow_cycle, result);
                if (result !== expected_data[queue_head])
                    $fatal(1, "result mismatch sequence=%0d cycle=%0d got=%h expected=%h",
                           expected_sequence[queue_head], slow_cycle, result,
                           expected_data[queue_head]);
                latency8_checks++;
                if ((slow_enabled_cycle - accepted_enabled_cycle[queue_head] + 1) != 8)
                    $fatal(1, "latency mismatch sequence=%0d accepted_enabled=%0d returned_enabled=%0d expected_inclusive_latency=8",
                           expected_sequence[queue_head],
                           accepted_enabled_cycle[queue_head], slow_enabled_cycle);
                if (expected_continuous[queue_head]) begin
                    continuous_returns++;
                    if (last_continuous_return_cycle >= 0) begin
                        continuous_gap_checks++;
                        if ((slow_cycle - last_continuous_return_cycle) != 1)
                            $fatal(1, "continuous throughput gap sequence=%0d prior_cycle=%0d cycle=%0d",
                                   expected_sequence[queue_head], last_continuous_return_cycle,
                                   slow_cycle);
                    end
                    last_continuous_return_cycle = slow_cycle;
                end
                queue_head++;
                returned_since_reset++;
                returned_lifetime++;
            end

            if (slow_ce && in_valid) begin
                if (queue_tail >= QUEUE_DEPTH)
                    $fatal(1, "scoreboard queue overflow");
                expected_data[queue_tail] = reference_mac(prior);
                expected_continuous[queue_tail] = drive_is_continuous;
                expected_sequence[queue_tail] = sequence_number;
                accepted_enabled_cycle[queue_tail] = slow_enabled_cycle;
                queue_tail++;
                sequence_number++;
                accepted_since_reset++;
                accepted_lifetime++;
            end

            outstanding = queue_tail - queue_head;
            if (outstanding > maximum_outstanding)
                maximum_outstanding = outstanding;
        end
    end

    initial begin : stimulus
        int k;
        // XSIM 2026.1 does not support the seeded $urandom system-task form
        // during O3 elaboration.  Stimulus remains deterministic in structure;
        // exact random values are bound by the preserved simulator log/WDB.
        clear_inputs();
        // glbl holds UltraScale+ global resources in startup for about 100 ns.
        // Keep lock low beyond that window, then prove fast-before-slow release.
        #120ns;
        if (fast_rst !== 1'b1 || slow_rst !== 1'b1)
            $fatal(1, "consumer reset escaped during glbl startup");
        gsr_start_checks++;
        release_lock(8);

        // Reset after phase 0 but before the coincident phase-1 edge. The
        // accepted transaction must be flushed, with no stale response.
        @(negedge slow_clk);
        drive_directed(7);
        slow_ce = 1'b1;
        in_valid = 1'b1;
        @(posedge slow_clk);
        @(posedge fast_clk);
        // Lock loss after phase 0 flushes the accepted transaction.  Stop the
        // root clock as well, restart it while unlocked, then relock.
        drop_lock(1'b1);
        release_lock(6);
        relock_checks++;
        half_boundary_reset_checks++;
        repeat (3) @(posedge slow_clk);
        if (out_valid)
            $fatal(1, "stale output after half-transaction synchronous reset");

        // Signed extrema, negative prior, and 48-bit modular wrap cases.
        for (k = 0; k < 12; k++) begin
            @(negedge slow_clk);
            drive_directed(k);
            slow_ce = 1'b1;
            in_valid = 1'b1;
            drive_is_continuous = 1'b0;
        end
        drain_expected(128);

        // One accepted transaction per slow clock: exact code, order,
        // latency=8, and one response per slow cycle after pipeline fill.
        last_continuous_return_cycle = -1;
        for (k = 0; k < CONTINUOUS_TRANSACTIONS; k++) begin
            @(negedge slow_clk);
            drive_random(1000 + k);
            slow_ce = 1'b1;
            in_valid = 1'b1;
            drive_is_continuous = 1'b1;
        end
        drain_expected(256);

        // Random full slow-cycle CE pauses.
        for (k = 0; k < RANDOM_CYCLES; k++) begin
            @(negedge slow_clk);
            drive_random(2000 + k);
            slow_ce = (($urandom % 5) != 0);
            in_valid = (($urandom % 4) != 0);
            drive_is_continuous = 1'b0;
        end
        drain_expected(512);

        // Random synchronous reset points with requests still in flight.
        // The scoreboard is flushed only when slow_rst is sampled, and any
        // later stale response is therefore an immediate empty-queue error.
        for (k = 0; k < 12; k++) begin
            int burst;
            int j;
            burst = 3 + ($urandom % 13);
            for (j = 0; j < burst; j++) begin
                @(negedge slow_clk);
                drive_random(4000 + k * 32 + j);
                slow_ce = (($urandom % 4) != 0);
                in_valid = 1'b1;
                drive_is_continuous = 1'b0;
            end
            if (($urandom & 1) != 0)
                @(posedge fast_clk);
            apply_lock_reset(2 + ($urandom % 4), 1'b0, k[0]);
            random_reset_checks++;
        end

        // Change CE only on slow-domain drive boundaries.  An accepted
        // transaction completes internally; CE suppresses later slow
        // acceptance/commit and the visible output must remain stable.
        @(negedge slow_clk);
        drive_directed(7);
        slow_ce = 1'b1;
        in_valid = 1'b1;
        drive_is_continuous = 1'b0;
        @(posedge slow_clk);
        @(negedge slow_clk);
        slow_ce = 1'b0;
        in_valid = 1'b0;
        ce_boundary_checks++;
        repeat (5) @(posedge slow_clk);
        half_boundary_pause_checks++;
        @(negedge slow_clk);
        slow_ce = 1'b1;
        drain_expected(256);

        // The legacy 725-transaction count was an accidental consequence of
        // XSIM's default random stream.  Adding the real clock-tree hierarchy
        // changes that stream.  Preserve the intended fixed coverage contract
        // explicitly by topping up with ordinary scored transactions.
        if (accepted_lifetime > 725)
            $fatal(1, "random stimulus exceeded canonical transaction budget accepted=%0d",
                   accepted_lifetime);
        while (accepted_lifetime < 725) begin
            @(negedge slow_clk);
            if (accepted_lifetime < 725) begin
                drive_random(6000 + accepted_lifetime);
                slow_ce = 1'b1;
                in_valid = 1'b1;
                drive_is_continuous = 1'b0;
            end else begin
                in_valid = 1'b0;
            end
        end
        drain_expected(256);

        if (queue_head != queue_tail)
            $fatal(1, "scoreboard not empty at end outstanding=%0d", queue_tail - queue_head);
        if (accepted_since_reset != returned_since_reset)
            $fatal(1, "accepted/returned mismatch accepted=%0d returned=%0d",
                   accepted_since_reset, returned_since_reset);
        if (continuous_returns != CONTINUOUS_TRANSACTIONS)
            $fatal(1, "continuous coverage mismatch returned=%0d expected=%0d",
                   continuous_returns, CONTINUOUS_TRANSACTIONS);
        if (latency8_checks != returned_lifetime)
            $fatal(1, "latency coverage mismatch checks=%0d returned=%0d",
                   latency8_checks, returned_lifetime);
        if (accepted_lifetime != 725)
            $fatal(1, "canonical transaction count mismatch accepted=%0d expected=725",
                   accepted_lifetime);
        if (accepted_lifetime != returned_lifetime + discarded_by_reset)
            $fatal(1, "lifetime accounting mismatch accepted=%0d returned=%0d discarded_by_reset=%0d",
                   accepted_lifetime, returned_lifetime, discarded_by_reset);
        if (continuous_gap_checks != (CONTINUOUS_TRANSACTIONS - 1))
            $fatal(1, "continuous throughput checks incomplete got=%0d expected=%0d",
                   continuous_gap_checks, CONTINUOUS_TRANSACTIONS - 1);
        if (full_pause_cycles == 0 || half_boundary_pause_checks != 1)
            $fatal(1, "pause coverage incomplete full=%0d half=%0d",
                   full_pause_cycles, half_boundary_pause_checks);
        if (half_boundary_reset_checks != 1 || random_reset_checks != 12 ||
            fast_before_slow_release_checks != 14 || synchronous_reset_count != 14 ||
            relock_checks != 13 || gsr_start_checks != 1 || ce_boundary_checks != 1 ||
            pause_stability_checks == 0)
            $fatal(1, "reset/clock coverage incomplete reset=%0d half=%0d random=%0d fast_before_slow=%0d relock=%0d gsr=%0d ce_boundary=%0d pause_stable=%0d",
                   synchronous_reset_count, half_boundary_reset_checks,
                   random_reset_checks, fast_before_slow_release_checks,
                   relock_checks, gsr_start_checks, ce_boundary_checks,
                   pause_stability_checks);

        if (fast_miter_checks < 1000)
            $fatal(1, "insufficient fused fast miter coverage checks=%0d", fast_miter_checks);
        $display("CNN_V10_PW_HALF2X_FUSED_ALU_CLOCK_TREE_PASS accepted_lifetime=%0d returned_lifetime=%0d discarded_by_reset=%0d accepted_since_reset=%0d returned_since_reset=%0d continuous=%0d latency8=%0d gap_checks=%0d full_pause_cycles=%0d pause_stable=%0d half_pause=%0d half_reset=%0d random_resets=%0d resets=%0d fast_before_slow=%0d relocks=%0d gsr=%0d ce_boundary=%0d max_outstanding=%0d fast_miter_checks=%0d",
                 accepted_lifetime, returned_lifetime, discarded_by_reset, accepted_since_reset,
                 returned_since_reset, continuous_returns, latency8_checks,
                 continuous_gap_checks, full_pause_cycles, pause_stability_checks,
                 half_boundary_pause_checks, half_boundary_reset_checks,
                 random_reset_checks,
                 synchronous_reset_count, fast_before_slow_release_checks, relock_checks,
                 gsr_start_checks, ce_boundary_checks,
                 maximum_outstanding, fast_miter_checks);
        $finish;
    end

    initial begin : timeout
        #250us;
        $fatal(1, "half2x UNISIM testbench timeout");
    end
endmodule
