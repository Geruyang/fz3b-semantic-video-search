`timescale 1ps/1ps

module tb_cnn_v10_half2x_clock_tree;
    reg root_clk_400 = 1'b0;
    reg root_run = 1'b1;
    reg mmcm_locked = 1'b0;
    wire slow_clk;
    wire fast_clk;

    integer fast_count = 0;
    integer slow_count = 0;
    integer failures = 0;
    integer i;
    integer j;
    time fast_edges [0:255];
    time slow_edges [0:127];
    time last_fast = 0;
    time last_slow = 0;
    time fast_reset_release_time = 0;
    time slow_reset_release_time = 0;

    reg fast_rst_q1 = 1'b1;
    reg fast_rst_q2 = 1'b1;
    reg slow_rst_q1 = 1'b1;
    reg slow_rst_q2 = 1'b1;
    wire reset_async = ~mmcm_locked;
    wire slow_reset_async = reset_async | fast_rst_q2;

    always begin
        #1250;
        if (root_run) root_clk_400 = ~root_clk_400;
        else root_clk_400 = 1'b0;
    end

    cnn_v10_half2x_clock_tree dut (
        .root_clk_400(root_clk_400),
        .driver_job_clk_200(slow_clk),
        .pw_local_clk_400(fast_clk)
    );

    // Equivalent to the platform's two asynchronous-assert/synchronous-release
    // reset domains, including the fast-ready auxiliary gate on the slow
    // proc_sys_reset.  The actual BD connectivity is separately validated.
    always @(posedge fast_clk or posedge reset_async) begin
        if (reset_async) begin
            fast_rst_q1 <= 1'b1;
            fast_rst_q2 <= 1'b1;
        end else begin
            fast_rst_q1 <= 1'b0;
            fast_rst_q2 <= fast_rst_q1;
        end
    end

    always @(posedge slow_clk or posedge slow_reset_async) begin
        if (slow_reset_async) begin
            slow_rst_q1 <= 1'b1;
            slow_rst_q2 <= 1'b1;
        end else begin
            slow_rst_q1 <= 1'b0;
            slow_rst_q2 <= slow_rst_q1;
        end
    end

    always @(negedge fast_rst_q2) fast_reset_release_time = $time;
    always @(negedge slow_rst_q2) begin
        slow_reset_release_time = $time;
        if (fast_rst_q2 !== 1'b0 || fast_reset_release_time == 0 || $time <= fast_reset_release_time) begin
            $display("CLOCK_TREE_FAIL slow_reset_not_after_fast fast_release=%0t slow_release=%0t", fast_reset_release_time, $time);
            failures = failures + 1;
        end
    end

    always @(posedge fast_clk) begin
        if (last_fast != 0 && ($time - last_fast) != 2500) begin
            $display("CLOCK_TREE_FAIL fast_period now=%0t previous=%0t", $time, last_fast);
            failures = failures + 1;
        end
        fast_edges[fast_count] = $time;
        fast_count = fast_count + 1;
        last_fast = $time;
    end

    always @(posedge slow_clk) begin
        if (last_slow != 0 && ($time - last_slow) != 5000) begin
            $display("CLOCK_TREE_FAIL slow_period now=%0t previous=%0t", $time, last_slow);
            failures = failures + 1;
        end
        slow_edges[slow_count] = $time;
        slow_count = slow_count + 1;
        last_slow = $time;
    end

    task check_epoch;
        input integer fast_start;
        input integer slow_start;
        integer fi;
        integer si;
        integer found;
        begin
            if ((fast_count - fast_start) < 12 || (slow_count - slow_start) < 6) begin
                $display("CLOCK_TREE_FAIL too_few_edges fast=%0d slow=%0d", fast_count-fast_start, slow_count-slow_start);
                failures = failures + 1;
            end
            for (si = slow_start + 1; si < slow_count; si = si + 1) begin
                found = 0;
                for (fi = fast_start; fi < fast_count; fi = fi + 1) begin
                    if (fast_edges[fi] == slow_edges[si]) found = 1;
                end
                if (!found) begin
                    $display("CLOCK_TREE_FAIL slow_edge_not_fast_edge time=%0t", slow_edges[si]);
                    failures = failures + 1;
                end
            end
        end
    endtask

    task stop_restart_root;
        input integer offset_ps;
        input integer stopped_ps;
        begin
            #(offset_ps);
            mmcm_locked = 1'b0;
            #1;
            if (fast_rst_q2 !== 1'b1 || slow_rst_q2 !== 1'b1) begin
                $display("CLOCK_TREE_FAIL reset_not_async_asserted fast=%b slow=%b", fast_rst_q2, slow_rst_q2);
                failures = failures + 1;
            end
            last_fast = 0;
            last_slow = 0;
            root_run = 1'b0;
            #(stopped_ps);
            root_run = 1'b1;
            // Let the common root run before lock is reported.  Neither
            // consumer may leave reset during this interval.
            #7500;
            if (fast_rst_q2 !== 1'b1 || slow_rst_q2 !== 1'b1) begin
                $display("CLOCK_TREE_FAIL consumer_reset_released_without_lock");
                failures = failures + 1;
            end
            fast_reset_release_time = 0;
            slow_reset_release_time = 0;
            mmcm_locked = 1'b1;
            #25000;
            if (fast_rst_q2 !== 1'b0 || slow_rst_q2 !== 1'b0 ||
                fast_reset_release_time == 0 || slow_reset_release_time == 0) begin
                $display("CLOCK_TREE_FAIL reset_release_missing fast=%b slow=%b fast_t=%0t slow_t=%0t",
                         fast_rst_q2, slow_rst_q2, fast_reset_release_time, slow_reset_release_time);
                failures = failures + 1;
            end
        end
    endtask

    initial begin
        integer f0;
        integer s0;
        // UltraScale+ UNISIM holds the global buffers in startup/GSR for
        // roughly 100 ns.  Start the measured epochs after that interval.
        #120000;
        mmcm_locked = 1'b1;
        f0 = fast_count;
        s0 = slow_count;
        #65000;
        check_epoch(f0, s0);

        // Stop/restart at a non-coincident phase, then prove consumer reset
        // assertion and fast-before-slow release under the recovered clocks.
        stop_restart_root(3700, 8100);
        f0 = fast_count;
        s0 = slow_count;
        #65000;
        check_epoch(f0, s0);

        // Repeat at a different divider phase so both odd/even states are
        // exercised rather than relying on one favorable stop edge.
        stop_restart_root(1250, 6250);
        f0 = fast_count;
        s0 = slow_count;
        #65000;
        check_epoch(f0, s0);

        if (failures != 0) begin
            $fatal(1, "CLOCK_TREE_FAIL failures=%0d", failures);
        end
        $display("CLOCK_TREE_PASS fast_edges=%0d slow_edges=%0d", fast_count, slow_count);
        $finish;
    end

    initial begin
        #500000;
        $fatal(1, "CLOCK_TREE_TIMEOUT");
    end
endmodule
