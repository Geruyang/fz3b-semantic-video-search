`timescale 1ns/1ps

// Phase-related 1x/2x clock tree for the half-width pointwise engine.
//
// The Clocking Wizard supplies one 400 MHz root.  Two sibling BUFGCE_DIV
// primitives distribute that root: DIVIDE=1 is the local PW clock and
// DIVIDE=2 is the 200 MHz job/AXI clock.  Both buffers are continuously
// enabled; configuration/GSR initializes the sibling divider phase.  MMCM
// lock gates the separate proc_sys_reset chains, not the clock tree itself.
// No generated clock is cascaded through another global buffer.
(* KEEP_HIERARCHY = "yes" *)
module cnn_v10_half2x_clock_tree (
    (* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 root_clk_400 CLK" *)
    // IP Integrator metadata follows the frozen PS model (99,999,001 Hz),
    // hence 399,996,004/199,998,002 here.  Implemented STA separately binds
    // the measured PL1 contract (99,999,999 Hz -> 399,999,996/199,999,998).
    (* X_INTERFACE_PARAMETER = "XIL_INTERFACENAME root_clk_400, FREQ_HZ 399996004, FREQ_TOLERANCE_HZ 0, PHASE 0.000, CLK_DOMAIN half2x_root_clk_400, INSERT_VIP 0" *)
    input  wire root_clk_400,
    (* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 driver_job_clk_200 CLK" *)
    (* X_INTERFACE_PARAMETER = "XIL_INTERFACENAME driver_job_clk_200, FREQ_HZ 199998002, FREQ_TOLERANCE_HZ 0, PHASE 0.000, CLK_DOMAIN half2x_driver_job_clk_200, INSERT_VIP 0" *)
    output wire driver_job_clk_200,
    (* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 pw_local_clk_400 CLK" *)
    (* X_INTERFACE_PARAMETER = "XIL_INTERFACENAME pw_local_clk_400, FREQ_HZ 399996004, FREQ_TOLERANCE_HZ 0, PHASE 0.000, CLK_DOMAIN half2x_pw_local_clk_400, INSERT_VIP 0" *)
    output wire pw_local_clk_400
);
    BUFGCE_DIV #(
        .BUFGCE_DIVIDE(1),
        .IS_CE_INVERTED(1'b0),
        .IS_CLR_INVERTED(1'b0),
        .IS_I_INVERTED(1'b0),
        .SIM_DEVICE("ULTRASCALE_PLUS")
    ) pw_local_bufgce_div (
        .I(root_clk_400),
        .CE(1'b1),
        .CLR(1'b0),
        .O(pw_local_clk_400)
    );

    BUFGCE_DIV #(
        .BUFGCE_DIVIDE(2),
        .IS_CE_INVERTED(1'b0),
        .IS_CLR_INVERTED(1'b0),
        .IS_I_INVERTED(1'b0),
        .SIM_DEVICE("ULTRASCALE_PLUS")
    ) driver_job_bufgce_div (
        .I(root_clk_400),
        .CE(1'b1),
        .CLR(1'b0),
        .O(driver_job_clk_200)
    );
endmodule
