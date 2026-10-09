`timescale 1ns/1ps

module tb_cnn_v10_pw_dsp16;
    logic ap_clk = 1'b0;
    logic ap_rst = 1'b1;
    logic ap_ce = 1'b0;
    logic drive_valid = 1'b0;
    logic signed [47:0] prior;
    logic signed [15:0] value [0:15];
    logic signed [15:0] weight [0:15];
    logic signed [47:0] result;

    logic expected_valid [0:7];
    logic signed [47:0] expected_data [0:7];
    integer checks = 0;
    integer accepted = 0;
    integer returned = 0;
    integer cycle = 0;

    always #2.5 ap_clk = ~ap_clk;

    cnn_v10_pw_dsp16 dut (
        .ap_clk(ap_clk), .ap_rst(ap_rst), .ap_ce(ap_ce),
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
        .result(result));

    function automatic logic signed [47:0] reference_mac;
        input logic signed [47:0] p;
        longint signed sum;
        integer k;
        begin
            sum = p;
            for (k = 0; k < 16; k = k + 1)
                sum = sum + $signed(value[k]) * $signed(weight[k]);
            reference_mac = sum[47:0];
        end
    endfunction

    task automatic clear_reference;
        integer k;
        begin
            for (k = 0; k < 8; k = k + 1) begin
                expected_valid[k] = 1'b0;
                expected_data[k] = 48'sd0;
            end
        end
    endtask

    task automatic drive_random(input integer index);
        integer k;
        begin
            prior = {$urandom, $urandom} & 48'hffffffffffff;
            for (k = 0; k < 16; k = k + 1) begin
                value[k] = $urandom;
                weight[k] = $urandom;
            end
            // Deterministic signed extrema are mixed into the random stream.
            if ((index % 17) == 0) begin
                prior = 48'sh7fffffffffff;
                value[0] = -16'sd32768;
                weight[0] = -16'sd32768;
                value[1] = 16'sd32767;
                weight[1] = -16'sd32768;
            end
        end
    endtask

    task automatic reference_step;
        integer k;
        begin
            if (ap_rst) begin
                clear_reference();
                accepted = 0;
                returned = 0;
            end else if (ap_ce) begin
                for (k = 7; k > 0; k = k - 1) begin
                    expected_valid[k] = expected_valid[k-1];
                    expected_data[k] = expected_data[k-1];
                end
                expected_valid[0] = drive_valid;
                expected_data[0] = reference_mac(prior);
                if (drive_valid) accepted = accepted + 1;
            end
        end
    endtask

    task automatic check_output;
        begin
            #1;
            checks = checks + 1;
            // ap_ctrl_none has no transaction-valid port. The reference
            // valid queue marks meaningful test vectors while zero-valued
            // filler cycles drain the fixed-latency pipeline. A stalled
            // ap_ce holds both the reference position and result data.
            if (expected_valid[7]) begin
                if (result !== expected_data[7])
                    $fatal(1, "data mismatch cycle=%0d got=%h expected=%h",
                           cycle, result, expected_data[7]);
            end
            if (expected_valid[7] && ap_ce) begin
                returned = returned + 1;
                if (returned > accepted)
                    $fatal(1, "output count exceeded accepted count cycle=%0d accepted=%0d returned=%0d",
                           cycle, accepted, returned);
            end
        end
    endtask

    initial begin
        integer k;
        clear_reference();
        prior = 48'sd0;
        for (k = 0; k < 16; k = k + 1) begin
            value[k] = 16'sd0;
            weight[k] = 16'sd0;
        end

        // UNISIM glbl asserts global reset for its startup interval. Keep the
        // local synchronous reset active beyond that window so no reference
        // transaction is compared against a globally-reset primitive.
        repeat (30) begin
            @(negedge ap_clk);
            ap_rst = 1'b1;
            ap_ce = 1'b1;
            drive_valid = 1'b0;
            @(posedge ap_clk); cycle = cycle + 1; reference_step(); check_output();
        end
        @(negedge ap_clk); ap_rst = 1'b0;

        // Back-to-back and randomly CE-stalled transactions.
        for (k = 0; k < 700; k = k + 1) begin
            @(negedge ap_clk);
            drive_random(k);
            ap_ce = (($urandom % 5) != 0);
            drive_valid = ap_ce && (($urandom % 4) != 0);
            if (k == 311 || k == 312) begin
                ap_rst = 1'b1;
                ap_ce = 1'b1;
                drive_valid = 1'b0;
            end else begin
                ap_rst = 1'b0;
            end
            @(posedge ap_clk); cycle = cycle + 1; reference_step(); check_output();
        end

        // Drain using enabled cycles only.
        repeat (10) begin
            @(negedge ap_clk);
            ap_rst = 1'b0;
            ap_ce = 1'b1;
            drive_valid = 1'b0;
            @(posedge ap_clk); cycle = cycle + 1; reference_step(); check_output();
        end
        for (k = 0; k < 8; k = k + 1)
            if (expected_valid[k]) $fatal(1, "reference pipeline not empty");
        if (accepted != returned)
            $fatal(1, "transaction count mismatch accepted=%0d returned=%0d",
                   accepted, returned);
        $display("CNN_V10_PW_DSP16_UNISIM_PASS checks=%0d accepted=%0d returned=%0d",
                 checks, accepted, returned);
        $finish;
    end
endmodule
