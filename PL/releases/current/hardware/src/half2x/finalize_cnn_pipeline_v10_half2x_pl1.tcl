# Finalize one already-routed half2x PL1 checkpoint.  This stage does not run
# implementation and never opens hardware.  It rechecks routing, clocks,
# timing, debug inventory, and DRC before producing the no-ILA bit/bin pair.

if {$argc != 4} {
    error "usage: finalize_cnn_pipeline_v10_half2x_pl1.tcl <routed_dcp> <expected_sha256> <synth_evidence_dir> <output_dir>"
}
lassign $argv input_dcp expected_sha synth_evidence output_dir
foreach variable {input_dcp synth_evidence output_dir} {
    set $variable [file normalize [set $variable]]
}
if {![file isfile $input_dcp]} {error "Missing routed DCP: $input_dcp"}
if {![file isdirectory $synth_evidence]} {error "Missing synthesis evidence: $synth_evidence"}
if {![file isdirectory $output_dir]} {error "Output directory must already exist: $output_dir"}

proc sha256_file {path} {
    set value [string tolower [lindex [split [exec certutil -hashfile $path SHA256] \n] 1]]
    regsub -all { } $value {} value
    return $value
}
proc require_clock {name period generated master_name} {
    set clock [get_clocks -quiet $name]
    if {[llength $clock] != 1} {error "Expected exactly one clock named $name"}
    if {[expr {[get_property IS_GENERATED $clock] ? 1 : 0}] != $generated} {
        error "Clock $name generated classification mismatch"
    }
    if {abs(double([get_property PERIOD $clock]) - $period) > 0.000001} {
        error "Clock $name period mismatch"
    }
    if {$generated && [get_property MASTER_CLOCK $clock] ne $master_name} {
        error "Clock $name master mismatch"
    }
    return $clock
}
proc path_slack {from_clock to_clock delay_type} {
    set path [get_timing_paths -quiet -from $from_clock -to $to_clock -delay_type $delay_type -max_paths 1]
    if {[llength $path] != 1} {error "Missing $delay_type path from $from_clock to $to_clock"}
    return [get_property SLACK $path]
}
proc parse_route_count {text label pattern} {
    if {![regexp $pattern $text -> value]} {error "Could not parse $label"}
    return $value
}

if {[sha256_file $input_dcp] ne [string tolower $expected_sha]} {error "Routed DCP SHA mismatch"}
foreach stale {half2x-final.dcp cnn-pipeline-v10-half2x-pl1.bit cnn-pipeline-v10-half2x-pl1.bin final-stage-status.rpt} {
    if {[file exists [file join $output_dir $stale]]} {error "Output result already exists: $stale"}
}

set_param general.maxThreads 16
if {[get_param general.maxThreads] != 16} {error "general.maxThreads did not read back 16"}
open_checkpoint $input_dcp
if {[get_property PART [current_design]] ne "xazu3eg-sfvc784-1-i"} {error "Unexpected target part"}

set master_name clk_pl_1
set slow_name clk_out1_cnn_pipeline_v10_shell_clock_wiz_0
set fast_name clk_out2_cnn_pipeline_v10_shell_clock_wiz_0
set master [require_clock $master_name 10.0 0 ""]
set slow [require_clock $slow_name 5.0 1 $master_name]
set fast [require_clock $fast_name 2.5 1 $master_name]
set mmcms [get_cells -quiet -hier -filter {REF_NAME =~ MMCME* && NAME =~ *clock_wiz*}]
if {[llength $mmcms] != 1} {error "Expected one implemented clock_wiz MMCM"}
set mmcm_m [get_property CLKFBOUT_MULT_F $mmcms]
set mmcm_d [get_property DIVCLK_DIVIDE $mmcms]
set mmcm_slow [get_property CLKOUT0_DIVIDE_F $mmcms]
set mmcm_fast [get_property CLKOUT1_DIVIDE $mmcms]
foreach {label actual expected} [list M $mmcm_m 12.0 D $mmcm_d 1 Oslow $mmcm_slow 6.0 Ofast $mmcm_fast 3.0] {
    if {abs(double($actual) - double($expected)) > 0.0005} {error "MMCM $label mismatch: $actual"}
}

set unresolved [get_cells -quiet -hier -filter {IS_BLACKBOX == 1 && REF_NAME != DSP48E2}]
if {[llength $unresolved] != 0} {error "Unresolved custom blackboxes: $unresolved"}
set half2x_cells [get_cells -quiet -hier -filter {ORIG_REF_NAME == cnn_v10_pw_dsp16_half2x || REF_NAME == cnn_v10_pw_dsp16_half2x}]
if {[llength $half2x_cells] != 16} {error "Expected 16 half2x units"}
set debug_cores [get_debug_cores -quiet]
set debug_hubs [get_cells -quiet -hier -filter {NAME =~ *dbg_hub*}]
set trace_pack [get_cells -quiet -hier -filter {NAME =~ *trace_pack*}]
if {[llength $debug_cores] || [llength $debug_hubs] || [llength $trace_pack]} {
    error "release-no-ila inventory mismatch"
}

# Preserve an independently named final checkpoint before reports and bitgen.
set final_dcp [file join $output_dir half2x-final.dcp]
write_checkpoint -force $final_dcp

report_clocks -file [file join $output_dir clocks.rpt]
report_clock_interaction -file [file join $output_dir clock-interaction.rpt]
report_timing_summary -delay_type min_max -report_unconstrained -check_timing_verbose -file [file join $output_dir timing-summary.rpt]
report_pulse_width -file [file join $output_dir pulse-width.rpt]
report_exceptions -file [file join $output_dir timing-exceptions.rpt]
check_timing -verbose -file [file join $output_dir check-timing.rpt]
set route_report [file join $output_dir route-status.rpt]
report_route_status -file $route_report
report_utilization -file [file join $output_dir utilization.rpt]
report_utilization -hierarchical -hierarchical_depth 8 -file [file join $output_dir utilization-hierarchical.rpt]
report_drc -file [file join $output_dir drc.rpt]
report_methodology -file [file join $output_dir methodology.rpt]
report_cdc -details -file [file join $output_dir cdc.rpt]
report_bus_skew -file [file join $output_dir bus-skew.rpt]
report_design_analysis -congestion -file [file join $output_dir congestion.rpt]

set route_fd [open $route_report r]
set route_text [read $route_fd]
close $route_fd
set unrouted [parse_route_count $route_text "unrouted nets" {# of unrouted nets\.+[ \t]*:[ \t]*([0-9]+)}]
set route_errors [parse_route_count $route_text "routing errors" {# of nets with routing errors\.+[ \t]*:[ \t]*([0-9]+)}]
set setup [get_timing_paths -delay_type max -max_paths 1]
set hold [get_timing_paths -delay_type min -max_paths 1]
if {[llength $setup] != 1 || [llength $hold] != 1} {error "Expected global setup and hold paths"}
set setup_slack [get_property SLACK $setup]
set hold_slack [get_property SLACK $hold]
set path_values [dict create \
    slow_to_slow_setup [path_slack $slow $slow max] \
    fast_to_fast_setup [path_slack $fast $fast max] \
    slow_to_fast_setup [path_slack $slow $fast max] \
    fast_to_slow_setup [path_slack $fast $slow max] \
    slow_to_slow_hold [path_slack $slow $slow min] \
    fast_to_fast_hold [path_slack $fast $fast min] \
    slow_to_fast_hold [path_slack $slow $fast min] \
    fast_to_slow_hold [path_slack $fast $slow min]]
set severe_drc [get_drc_violations -quiet -filter {SEVERITY == Error || SEVERITY == "Critical Warning"}]
set failed [expr {$unrouted != 0 || $route_errors != 0 || $setup_slack < 0.0 || $hold_slack < 0.0 || [llength $severe_drc] != 0}]
dict for {name value} $path_values {if {$value < 0.0} {set failed 1}}
set status_value PASS
if {$failed} {set status_value FAIL}

set status_file [file join $output_dir final-stage-status.rpt]
set fd [open $status_file w]
puts $fd "status=$status_value"
puts $fd "input_routed_dcp_sha256=[sha256_file $input_dcp]"
puts $fd "final_dcp_sha256=[sha256_file $final_dcp]"
puts $fd "general_threads_readback=[get_param general.maxThreads]"
puts $fd "half2x_unit_count=[llength $half2x_cells]"
puts $fd "unresolved_custom_blackbox_count=[llength $unresolved]"
puts $fd "setup_wns_ns=$setup_slack"
puts $fd "hold_whs_ns=$hold_slack"
dict for {name value} $path_values {puts $fd "${name}_ns=$value"}
puts $fd "unrouted_net_count=$unrouted"
puts $fd "routing_error_count=$route_errors"
puts $fd "severe_drc_count=[llength $severe_drc]"
puts $fd "master_clock=$master_name"
puts $fd "slow_clock=$slow_name"
puts $fd "fast_clock=$fast_name"
puts $fd "mmcm_m=$mmcm_m"
puts $fd "mmcm_d=$mmcm_d"
puts $fd "mmcm_slow_divide=$mmcm_slow"
puts $fd "mmcm_fast_divide=$mmcm_fast"
puts $fd "debug_profile=release-no-ila"
puts $fd "guard_ila_count=0"
puts $fd "pipeline_ila_count=0"
puts $fd "debug_hub_count=0"
puts $fd "trace_pack_present=false"
puts $fd "platform_trace_mmio_register_count=0"
puts $fd "hls_ap_none_trace_port_count=12"
puts $fd "trace_outputs_connected=false"
puts $fd "ltx_required=false"
puts $fd "hardware_programmed=false"
close $fd

if {$failed} {
    puts "HALF2X_PL1_FINALIZE_SIGNOFF_FAIL WNS=$setup_slack WHS=$hold_slack unrouted=$unrouted route_errors=$route_errors severe_drc=[llength $severe_drc]"
    close_design
    exit 2
}

set_property BITSTREAM.CONFIG.UNUSEDPIN Pullnone [current_design]
write_bitstream -force -bin_file [file join $output_dir cnn-pipeline-v10-half2x-pl1.bit]
puts "HALF2X_PL1_FINALIZE_PASS WNS=$setup_slack WHS=$hold_slack"
close_design
exit 0
