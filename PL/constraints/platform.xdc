# Retain PS PL1 100 MHz input. MMCM/BUFGCE_DIV clocks are related.
create_clock -period 10.000 -name clk_pl_1 -waveform {0 5} [get_pins {cnn_rtl_platform_i/ps/inst/PS8_i/PLCLK[1]}]
# No blanket asynchronous exception; standard IP owns scoped reset exceptions.
