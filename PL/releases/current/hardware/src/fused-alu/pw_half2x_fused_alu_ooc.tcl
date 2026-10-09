# Local OOC implementation for cnn_v10_pw_dsp16_half2x.
# argv: primitive_rtl half2x_rtl wrapper_rtl output_dir

if {$argc != 5} {
    error "usage: pw_half2x_fused_alu_ooc.tcl primitive_rtl fused_leaf_rtl clock_tree_rtl wrapper_rtl output_dir"
}

set primitive_rtl [file normalize [lindex $argv 0]]
set fused_leaf_rtl [file normalize [lindex $argv 1]]
set clock_tree_rtl [file normalize [lindex $argv 2]]
set wrapper_rtl [file normalize [lindex $argv 3]]
set output_dir [file normalize [lindex $argv 4]]
set target_part "xazu3eg-sfvc784-1-i"

foreach required [list $primitive_rtl $fused_leaf_rtl $clock_tree_rtl $wrapper_rtl] {
    if {![file isfile $required]} {
        error "required RTL does not exist: $required"
    }
}
file mkdir $output_dir

set_param general.maxThreads 16
set_param synth.maxThreads 8
create_project -in_memory -part $target_part
read_verilog $primitive_rtl
read_verilog $fused_leaf_rtl
read_verilog -sv $clock_tree_rtl
read_verilog $wrapper_rtl

# Use a physically connected common 400 MHz root.  The fast domain uses a
# BUFG, while BUFGCE_DIV produces the 200 MHz slow domain.  This models the
# shared platform clock tree and avoids asserting a generated relationship
# between unrelated package ports.
set xdc_path [file join $output_dir pw_half2x_ooc.xdc]
set xdc_fh [open $xdc_path w]
puts $xdc_fh {create_clock -name clock_400_root -period 2.500 -waveform {0.000 1.250} [get_ports clock_400_in]}
puts $xdc_fh {create_generated_clock -name fast_clk -source [get_ports clock_400_in] -divide_by 1 [get_pins clock_tree/pw_local_bufgce_div/O]}
puts $xdc_fh {create_generated_clock -name slow_clk -source [get_ports clock_400_in] -divide_by 2 [get_pins clock_tree/driver_job_bufgce_div/O]}
puts $xdc_fh {set_clock_uncertainty -setup 0.250 [get_clocks slow_clk]}
puts $xdc_fh {set_clock_uncertainty -hold 0.050 [get_clocks slow_clk]}
puts $xdc_fh {set_clock_uncertainty -setup 0.125 [get_clocks fast_clk]}
puts $xdc_fh {set_clock_uncertainty -hold 0.025 [get_clocks fast_clk]}

# External harness ports are deliberately outside this physical experiment.
# Real slow-domain launch and capture registers inside the wrapper time every
# production interface path.  Only the synthetic stimulus/sink boundaries and
# asynchronous reset assertion are exempted.
puts $xdc_fh {set_false_path -from [get_ports {reset_async slow_ce_in in_valid_in prior_in[*] value_bus_in[*] weight_bus_in[*]}]}
puts $xdc_fh {set_false_path -to [get_ports {out_valid_out result_out[*]}]}
close $xdc_fh
read_xdc $xdc_path

synth_design -top cnn_v10_pw_dsp16_half2x_fused_alu_ooc_wrapper -part $target_part \
    -mode out_of_context -flatten_hierarchy rebuilt \
    -directive PerformanceOptimized

set synth_dsp_cells [get_cells -quiet -hierarchical -filter {REF_NAME == DSP48E2}]
set synth_dsp_count [llength $synth_dsp_cells]
if {$synth_dsp_count != 8} {
    error "expected exactly 8 DSP48E2 cells after synthesis, found $synth_dsp_count"
}

write_checkpoint -force [file join $output_dir pw_half2x_fused_alu-post-synth.dcp]
report_utilization -file [file join $output_dir utilization-post-synth.rpt]
report_utilization -hierarchical -file [file join $output_dir utilization-hierarchical-post-synth.rpt]
report_timing_summary -delay_type min_max -report_unconstrained \
    -check_timing_verbose -file [file join $output_dir timing-summary-post-synth.rpt]

opt_design -directive Explore
place_design -directive Explore
phys_opt_design -directive AggressiveExplore
route_design -directive Explore

set routed_dsp_cells [get_cells -quiet -hierarchical -filter {REF_NAME == DSP48E2}]
set routed_dsp_count [llength $routed_dsp_cells]
if {$routed_dsp_count != 8} {
    error "expected exactly 8 DSP48E2 cells after route, found $routed_dsp_count"
}

write_checkpoint -force [file join $output_dir pw_half2x_fused_alu-routed.dcp]
report_utilization -file [file join $output_dir utilization-post-route.rpt]
report_utilization -hierarchical -file [file join $output_dir utilization-hierarchical-post-route.rpt]
report_timing_summary -delay_type min_max -report_unconstrained \
    -check_timing_verbose -file [file join $output_dir timing-summary-post-route.rpt]

foreach clock_name {slow_clk fast_clk} {
    report_timing -delay_type max -from [get_clocks $clock_name] \
        -to [get_clocks $clock_name] -max_paths 20 -nworst 2 \
        -file [file join $output_dir setup-${clock_name}-post-route.rpt]
    report_timing -delay_type min -from [get_clocks $clock_name] \
        -to [get_clocks $clock_name] -max_paths 20 -nworst 2 \
        -file [file join $output_dir hold-${clock_name}-post-route.rpt]
}
foreach pair {{slow_clk fast_clk} {fast_clk slow_clk}} {
    lassign $pair from_clock to_clock
    report_timing -delay_type max -from [get_clocks $from_clock] \
        -to [get_clocks $to_clock] -max_paths 20 -nworst 2 \
        -file [file join $output_dir setup-${from_clock}-to-${to_clock}-post-route.rpt]
    report_timing -delay_type min -from [get_clocks $from_clock] \
        -to [get_clocks $to_clock] -max_paths 20 -nworst 2 \
        -file [file join $output_dir hold-${from_clock}-to-${to_clock}-post-route.rpt]
}

report_pulse_width -file [file join $output_dir pulse-width-post-route.rpt]
report_clock_interaction -file [file join $output_dir clock-interaction-post-route.rpt]
report_cdc -details -file [file join $output_dir cdc-post-route.rpt]
check_timing -verbose -file [file join $output_dir check-timing-post-route.rpt]
report_route_status -file [file join $output_dir route-status-post-route.rpt]
report_drc -file [file join $output_dir drc-post-route.rpt]
report_clock_utilization -file [file join $output_dir clock-utilization-post-route.rpt]
report_methodology -file [file join $output_dir methodology-post-route.rpt]
report_design_analysis -of_timing_paths [get_timing_paths -delay_type max -max_paths 100 -nworst 2] -file [file join $output_dir design-analysis-top100-post-route.rpt]
set fused_tail_cell [get_cells -quiet dut/half_dot/chain1/stage3/dsp_i]
set fused_c_pins [get_pins -quiet -of_objects $fused_tail_cell -filter {REF_PIN_NAME =~ C*}]
if {[llength $fused_c_pins] > 0} {
    report_timing -delay_type max -through $fused_c_pins -max_paths 20 -nworst 2 -file [file join $output_dir timing-fused-c-to-p-post-route.rpt]
} else {
    set fh [open [file join $output_dir timing-fused-c-to-p-post-route.rpt] w]; puts $fh "NO_MATCH fused chain1 stage3 C pin"; close $fh
}
set outer_nets [get_nets -quiet -hierarchical -filter {NAME =~ */phase0_partial*}]
if {[llength $outer_nets] > 0} {
    report_timing -delay_type max -through $outer_nets -max_paths 20 -nworst 2 -file [file join $output_dir timing-outer-fifo-add-post-route.rpt]
} else {
    set fh [open [file join $output_dir timing-outer-fifo-add-post-route.rpt] w]; puts $fh "NO_MATCH phase0_partial net"; close $fh
}

set contract_fh [open [file join $output_dir pw_half2x_fused_alu-contract.txt] w]
puts $contract_fh "part=$target_part"
puts $contract_fh "top=cnn_v10_pw_dsp16_half2x_fused_alu_ooc_wrapper"
puts $contract_fh "boundary=registered_slow_launch_and_capture"
puts $contract_fh "slow_clk_period_ns=5.000"
puts $contract_fh "fast_clk_period_ns=2.500"
puts $contract_fh "clock_phase=same_origin_coincident_rising_edges"
puts $contract_fh "clock_tree=real_cnn_v10_half2x_clock_tree_sibling_bufgce_div1_div2"
puts $contract_fh "fused_alu_opmode=0x195"
puts $contract_fh "chain1_areg_breg=2"
puts $contract_fh "chain1_creg=0"
puts $contract_fh "general_threads=16"
puts $contract_fh "synthesis_threads=8"
puts $contract_fh "jobs=1"
puts $contract_fh "synth_dsp48e2=$synth_dsp_count"
puts $contract_fh "routed_dsp48e2=$routed_dsp_count"
close $contract_fh

puts "PW_HALF2X_FUSED_ALU_OOC_COMPLETE part=$target_part dsp48e2=$routed_dsp_count"
exit 0

