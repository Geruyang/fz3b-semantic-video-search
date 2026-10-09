`timescale 1ns/1ps

module tb_cnn_v10_pw_half2x_fastmodel_miter;
    localparam int RANDOM_SLOW_CYCLES = 4096;
    logic slow_clk = 1'b0;
    logic fast_clk = 1'b1;
    always #2.5 slow_clk = ~slow_clk;
    always #1.25 fast_clk = ~fast_clk;

    logic slow_rst = 1'b1, fast_rst = 1'b1;
    logic slow_ce = 1'b0, in_valid = 1'b0;
    logic [47:0] prior = '0;
    logic [15:0] value [0:15];
    logic [15:0] weight [0:15];
    wire actual_valid, model_valid;
    wire [47:0] actual_result, model_result;
    int checked_slow_edges = 0;
    int checked_valid_outputs = 0;
    int reset_ce0_overlap = 0;
    int reset_ce1_overlap = 0;
    int long_ce_hold_cycles = 0;

`define HALF2X_PORTS(VALID, RESULT) \
        .slow_clk(slow_clk), .slow_rst(slow_rst), .slow_ce(slow_ce), \
        .fast_clk(fast_clk), .fast_rst(fast_rst), .in_valid(in_valid), \
        .prior(prior), \
        .value0(value[0]), .weight0(weight[0]), \
        .value1(value[1]), .weight1(weight[1]), \
        .value2(value[2]), .weight2(weight[2]), \
        .value3(value[3]), .weight3(weight[3]), \
        .value4(value[4]), .weight4(weight[4]), \
        .value5(value[5]), .weight5(weight[5]), \
        .value6(value[6]), .weight6(weight[6]), \
        .value7(value[7]), .weight7(weight[7]), \
        .value8(value[8]), .weight8(weight[8]), \
        .value9(value[9]), .weight9(weight[9]), \
        .value10(value[10]), .weight10(weight[10]), \
        .value11(value[11]), .weight11(weight[11]), \
        .value12(value[12]), .weight12(weight[12]), \
        .value13(value[13]), .weight13(weight[13]), \
        .value14(value[14]), .weight14(weight[14]), \
        .value15(value[15]), .weight15(weight[15]), \
        .out_valid(VALID), .result(RESULT)

    cnn_v10_pw_dsp16_half2x actual (`HALF2X_PORTS(actual_valid, actual_result));
    cnn_v10_pw_dsp16_half2x_fastmodel model (`HALF2X_PORTS(model_valid, model_result));

    task automatic drive_pattern(input int n);
        int k;
        begin
            prior = {$urandom, $urandom} & 48'hffff_ffff_ffff;
            for (k = 0; k < 16; k++) begin
                value[k] = $urandom;
                weight[k] = $urandom;
            end
            if ((n % 61) == 0) begin
                prior = 48'h8000_0000_0000;
                value[0] = 16'h8000; weight[0] = 16'h8000;
                value[1] = 16'h7fff; weight[1] = 16'h8000;
                value[15] = 16'hffff; weight[15] = 16'h7fff;
            end
        end
    endtask

    task automatic set_reset(input logic asserted, input logic ce_value);
        begin
            @(negedge fast_clk);
            slow_ce = ce_value;
            in_valid = 1'b0;
            slow_rst = asserted;
            fast_rst = asserted;
            if (asserted && ce_value) reset_ce1_overlap++;
            if (asserted && !ce_value) reset_ce0_overlap++;
        end
    endtask

    always @(posedge slow_clk) begin
        #2ps;
        checked_slow_edges++;
        if (actual_valid !== model_valid)
            $fatal(1, "valid mismatch edge=%0d actual=%b model=%b", checked_slow_edges,
                   actual_valid, model_valid);
        if (actual_result !== model_result) begin
            $display("MITER_INTERNAL actual_half=%h model_half=%h actual_phase=%b model_phase=%b actual_p0=%h model_p0=%h actual_p1=%h model_p1=%h",
                     actual.half_partial, model.half_partial,
                     actual.half_phase1, model.half_phase1,
                     actual.half_dot.partial0, model.half_dot.partial0,
                     actual.half_dot.partial1, model.half_dot.partial1);
            $fatal(1, "result mismatch edge=%0d actual=%h model=%h valid=%b",
                   checked_slow_edges, actual_result, model_result, actual_valid);
        end
        if (actual_valid) checked_valid_outputs++;
    end

    always @(posedge fast_clk) begin
        #2ps;
        if (actual.half_valid !== model.half_valid ||
            actual.half_phase1 !== model.half_phase1 ||
            actual.half_partial !== model.half_partial)
            $fatal(1, "fast internal mismatch valid=%b/%b phase=%b/%b partial=%h/%h",
                   actual.half_valid, model.half_valid,
                   actual.half_phase1, model.half_phase1,
                   actual.half_partial, model.half_partial);
    end

    initial begin : stimulus
        int n;
        for (n = 0; n < 16; n++) begin value[n] = '0; weight[n] = '0; end
        set_reset(1'b1, 1'b0);
        // glbl.GSR holds UltraScale+ primitives reset for about 100 ns.
        // Keep both implementations in their local reset beyond that window.
        repeat (32) @(posedge slow_clk);
        set_reset(1'b0, 1'b0);
        repeat (3) @(posedge slow_clk);

        // Back-to-back traffic with independently changing CE and valid.
        for (n = 0; n < RANDOM_SLOW_CYCLES; n++) begin
            @(negedge slow_clk);
            drive_pattern(n);
            slow_ce = (($urandom % 7) != 0);
            in_valid = (($urandom % 5) != 0);
            if ((n % 257) == 0) begin
                // Reset while CE=0 and CE=1 are both required coverage.
                set_reset(1'b1, (n & 1) != 0);
                repeat (2 + (n % 3)) @(posedge slow_clk);
                set_reset(1'b0, 1'b0);
            end
        end

        // Long CE hold after accepted traffic checks internal atomic progress
        // and stable observable state in both implementations.
        @(negedge slow_clk);
        drive_pattern(9001);
        slow_ce = 1'b1;
        in_valid = 1'b1;
        @(posedge slow_clk);
        @(negedge slow_clk);
        slow_ce = 1'b0;
        in_valid = 1'b0;
        repeat (128) begin
            @(posedge slow_clk);
            long_ce_hold_cycles++;
        end
        @(negedge slow_clk);
        slow_ce = 1'b1;
        repeat (32) @(posedge slow_clk);

        set_reset(1'b1, 1'b1);
        repeat (4) @(posedge slow_clk);
        set_reset(1'b0, 1'b0);
        repeat (8) @(posedge slow_clk);

        if (checked_valid_outputs < 1000 || reset_ce0_overlap == 0 ||
            reset_ce1_overlap == 0 || long_ce_hold_cycles != 128)
            $fatal(1, "coverage incomplete outputs=%0d reset_ce0=%0d reset_ce1=%0d hold=%0d",
                   checked_valid_outputs, reset_ce0_overlap, reset_ce1_overlap,
                   long_ce_hold_cycles);
        $display("CNN_V10_PW_HALF2X_FASTMODEL_MITER_PASS slow_edges=%0d valid_outputs=%0d reset_ce0=%0d reset_ce1=%0d long_ce_hold=%0d",
                 checked_slow_edges, checked_valid_outputs, reset_ce0_overlap,
                 reset_ce1_overlap, long_ce_hold_cycles);
        $finish;
    end

    initial begin
        #100us;
        $fatal(1, "half2x fastmodel miter timeout");
    end
endmodule
