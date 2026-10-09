# Fused half2x OOC clock contract: phase-aligned 200 MHz / 400 MHz.
create_clock -name ap_clk -period 5.000 [get_ports ap_clk]
create_clock -name pw_fast_clk -period 2.500 [get_ports pw_fast_clk]
