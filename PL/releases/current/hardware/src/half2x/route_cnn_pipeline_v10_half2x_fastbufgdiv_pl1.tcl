# Route one frozen fast-root plus sibling-BUFGCE_DIV half2x PL1 post-physopt
# checkpoint.  This is an offline
# physical-signoff stage only: it deliberately does not write a bitstream or
# access hardware.  The routed checkpoint is saved before any report parsing.

if {$argc != 3} {
    error "usage: route_cnn_pipeline_v10_half2x_pl1.tcl <post_physopt_dcp> <expected_sha256> <output_dir>"
}
lassign $argv input_dcp expected_sha output_dir
set input_dcp [file normalize $input_dcp]
set output_dir [file normalize $output_dir]
if {![file isfile $input_dcp]} {error "Missing post-physopt DCP: $input_dcp"}
if {![file isdirectory $output_dir]} {error "Output directory must already exist: $output_dir"}

proc sha256_file {path} {
    set value [string tolower [lindex [split [exec certutil -hashfile $path SHA256] \n] 1]]
    regsub -all { } $value {} value
    return $value
}
proc timing_exception_commands {path} {
    set fd [open $path r]
    set text [read $fd]
    close $fd
    set result {}
    foreach line [split $text \n] {
        set normalized [string trim $line]
        if {[regexp {^(set_false_path|set_multicycle_path|set_max_delay|set_min_delay|set_clock_groups|set_disable_timing)([ \t]|$)} $normalized]} {
            lappend result $normalized
        }
    }
    return [lsort -unique $result]
}
proc require_clock {name period generated master_name} {
    set clock [get_clocks -quiet $name]
    if {[llength $clock] != 1} {error "Expected exactly one clock named $name"}
    if {[expr {[get_property IS_GENERATED $clock] ? 1 : 0}] != $generated} {
        error "Clock $name generated-clock classification mismatch"
    }
    if {abs(double([get_property PERIOD $clock]) - $period) > 0.000001} {
        error "Clock $name period mismatch"
    }
    if {$generated && [get_property MASTER_CLOCK $clock] ne $master_name} {
        error "Clock $name master-clock mismatch"
    }
    return $clock
}
proc path_slack {from_clock to_clock delay_type} {
    set path [get_timing_paths -quiet -from $from_clock -to $to_clock -delay_type $delay_type -max_paths 1]
    if {[llength $path] != 1} {return "NA"}
    return [get_property SLACK $path]
}
proc require_one {objects label} {
    if {[llength $objects] != 1} {error "Expected exactly one $label, got [llength $objects]: $objects"}
    return [lindex $objects 0]
}

if {[sha256_file $input_dcp] ne [string tolower $expected_sha]} {
    error "Post-physopt DCP SHA mismatch"
}
foreach stale {half2x-post-route.dcp route-stage-status.rpt timing-post-route.rpt route-status-post-route.rpt} {
    if {[file exists [file join $output_dir $stale]]} {error "Output result already exists: $stale"}
}

set_param general.maxThreads 16
if {[get_param general.maxThreads] != 16} {error "general.maxThreads did not read back 16"}
open_checkpoint $input_dcp
if {[get_property PART [current_design]] ne "xazu3eg-sfvc784-1-i"} {error "Unexpected target part"}

set master_name clk_pl_1
set slow_name half2x_clock_tree_driver_job_clk_200
set fast_name clock_wiz_clk_out1
set master [require_clock $master_name 10.0 0 ""]
set fast [require_clock $fast_name 2.5 1 $master_name]
set slow [require_clock $slow_name 5.0 1 $fast_name]
set clk0 [get_clocks -quiet clk_pl_0]
if {[llength $clk0] != 1} {error "Expected the unused clk_pl_0 model clock"}
set unresolved [get_cells -quiet -hier -filter {IS_BLACKBOX == 1 && REF_NAME != DSP48E2}]
if {[llength $unresolved] != 0} {error "Unresolved custom blackboxes: $unresolved"}
set half2x_cells [get_cells -quiet -hier -filter {ORIG_REF_NAME == cnn_v10_pw_dsp16_half2x || REF_NAME == cnn_v10_pw_dsp16_half2x}]
if {[llength $half2x_cells] != 16} {error "Expected 16 half2x pointwise units, found [llength $half2x_cells]"}

set mmcm [require_one [get_cells -quiet -hierarchical -filter {REF_NAME =~ MMCME* && NAME =~ *clock_wiz*}] "clock-wizard MMCM"]
foreach {property expected} {CLKFBOUT_MULT_F 12.000 DIVCLK_DIVIDE 1 CLKOUT0_DIVIDE_F 3.000} {
    if {abs(double([get_property $property $mmcm]) - double($expected)) > 0.0005} {error "MMCM $property mismatch"}
}
set fast_buffer [require_one [get_cells -quiet -hierarchical -filter {REF_NAME == BUFGCE_DIV && NAME =~ *half2x_clock_tree*pw_local*}] "fast BUFGCE_DIV"]
set slow_buffer [require_one [get_cells -quiet -hierarchical -filter {REF_NAME == BUFGCE_DIV && NAME =~ *half2x_clock_tree*driver_job*}] "slow BUFGCE_DIV"]
if {[get_property BUFGCE_DIVIDE $fast_buffer] != 1 || [get_property BUFGCE_DIVIDE $slow_buffer] != 2} {error "BUFGCE_DIV ratio mismatch"}
set fast_i [require_one [get_pins -quiet -of_objects $fast_buffer -filter {REF_PIN_NAME == I}] "fast divider I"]
set slow_i [require_one [get_pins -quiet -of_objects $slow_buffer -filter {REF_PIN_NAME == I}] "slow divider I"]
set root_net [require_one [get_nets -quiet -of_objects $fast_i] "fast divider input net"]
if {$root_net ne [require_one [get_nets -quiet -of_objects $slow_i] "slow divider input net"]} {error "Clock dividers do not share one root net"}
set root_driver [require_one [get_pins -quiet -leaf -of_objects $root_net -filter {DIRECTION == OUT}] "root clock driver"]
if {[get_property REF_PIN_NAME $root_driver] ne "CLKOUT0" || ![string match {MMCME*} [get_property REF_NAME [get_cells -of_objects $root_driver]]]} {
    error "Clock dividers are not directly driven by MMCM CLKOUT0"
}

set constraints_before [file join $output_dir timing-constraints-before-route.xdc]
write_xdc -force -type timing -constraints valid $constraints_before

# One bounded attempt.  The post-place evidence has positive setup on every
# 200/400 MHz clock pair and only four Short level-5 congestion windows.
route_design -directive MoreGlobalIterations

set routed_dcp [file join $output_dir half2x-post-route.dcp]
write_checkpoint -force $routed_dcp

report_clocks -file [file join $output_dir clocks-post-route.rpt]
report_clock_interaction -file [file join $output_dir clock-interaction-post-route.rpt]
report_timing_summary -delay_type min_max -report_unconstrained -check_timing_verbose -file [file join $output_dir timing-post-route.rpt]
report_timing -from $fast -to $fast -delay_type max -max_paths 100 -file [file join $output_dir fast400-to-fast400-setup-post-route.rpt]
report_timing -from $slow -to $slow -delay_type max -max_paths 100 -file [file join $output_dir slow200-to-slow200-setup-post-route.rpt]
report_timing -from $slow -to $fast -delay_type max -max_paths 100 -file [file join $output_dir slow200-to-fast400-setup-post-route.rpt]
report_timing -from $fast -to $slow -delay_type max -max_paths 100 -file [file join $output_dir fast400-to-slow200-setup-post-route.rpt]
report_timing -from $fast -to $fast -delay_type min -max_paths 100 -file [file join $output_dir fast400-to-fast400-hold-post-route.rpt]
report_timing -from $slow -to $slow -delay_type min -max_paths 100 -file [file join $output_dir slow200-to-slow200-hold-post-route.rpt]
report_timing -from $slow -to $fast -delay_type min -max_paths 100 -file [file join $output_dir slow200-to-fast400-hold-post-route.rpt]
report_timing -from $fast -to $slow -delay_type min -max_paths 100 -file [file join $output_dir fast400-to-slow200-hold-post-route.rpt]
report_pulse_width -file [file join $output_dir pulse-width-post-route.rpt]
report_exceptions -file [file join $output_dir timing-exceptions-post-route.rpt]
check_timing -verbose -file [file join $output_dir check-timing-post-route.rpt]
set route_status_file [file join $output_dir route-status-post-route.rpt]
report_route_status -file $route_status_file
report_utilization -file [file join $output_dir utilization-post-route.rpt]
report_utilization -hierarchical -hierarchical_depth 8 -file [file join $output_dir utilization-hierarchical-post-route.rpt]
report_drc -file [file join $output_dir drc-post-route.rpt]
report_methodology -file [file join $output_dir methodology-post-route.rpt]
report_cdc -details -file [file join $output_dir cdc-post-route.rpt]
report_bus_skew -file [file join $output_dir bus-skew-post-route.rpt]
report_design_analysis -congestion -file [file join $output_dir congestion-post-route.rpt]

set constraints_after [file join $output_dir timing-constraints-post-route.xdc]
write_xdc -force -type timing -constraints valid $constraints_after
set exceptions_before [timing_exception_commands $constraints_before]
set exceptions_after [timing_exception_commands $constraints_after]
set new_exception_count 0
foreach exception $exceptions_after {
    if {[lsearch -exact $exceptions_before $exception] < 0} {incr new_exception_count}
}

set master_after [require_clock $master_name 10.0 0 ""]
set fast_after [require_clock $fast_name 2.5 1 $master_name]
set slow_after [require_clock $slow_name 5.0 1 $fast_name]
set setup [get_timing_paths -delay_type max -max_paths 1]
set hold [get_timing_paths -delay_type min -max_paths 1]
if {[llength $setup] != 1 || [llength $hold] != 1} {error "Expected setup and hold paths"}
set setup_slack [get_property SLACK $setup]
set hold_slack [get_property SLACK $hold]
set severe_drc [get_drc_violations -quiet -filter {SEVERITY == Error || SEVERITY == "Critical Warning"}]
set route_fd [open $route_status_file r]
set route_text [read $route_fd]
close $route_fd
if {![regexp {# of unrouted nets\.+[ \t]*:[ \t]*([0-9]+)} $route_text -> unrouted_net_count]} {
    error "Could not parse unrouted-net count"
}
if {![regexp {# of nets with routing errors\.+[ \t]*:[ \t]*([0-9]+)} $route_text -> routing_error_count]} {
    error "Could not parse routing-error count"
}

set fd [open [file join $output_dir route-stage-status.rpt] w]
puts $fd "status=HALF2X_PL1_ROUTE_COMPLETE"
puts $fd "general_threads_readback=[get_param general.maxThreads]"
puts $fd "route_directive=MoreGlobalIterations"
puts $fd "input_dcp_sha256=[sha256_file $input_dcp]"
puts $fd "routed_dcp_sha256=[sha256_file $routed_dcp]"
puts $fd "master_period_ns=[get_property PERIOD $master_after]"
puts $fd "slow_period_ns=[get_property PERIOD $slow_after]"
puts $fd "fast_period_ns=[get_property PERIOD $fast_after]"
puts $fd "half2x_unit_count=[llength $half2x_cells]"
puts $fd "unresolved_custom_blackbox_count=[llength $unresolved]"
puts $fd "clock_topology=mmcm_fast_plus_bufgce_div_v1"
puts $fd "mmcm_m=[get_property CLKFBOUT_MULT_F $mmcm]"
puts $fd "mmcm_d=[get_property DIVCLK_DIVIDE $mmcm]"
puts $fd "mmcm_o_fast=[get_property CLKOUT0_DIVIDE_F $mmcm]"
puts $fd "driver_job_bufgce_divide=[get_property BUFGCE_DIVIDE $slow_buffer]"
puts $fd "pw_local_bufgce_divide=[get_property BUFGCE_DIVIDE $fast_buffer]"
puts $fd "common_mmcm_root_net=$root_net"
puts $fd "setup_wns_ns=$setup_slack"
puts $fd "hold_whs_ns=$hold_slack"
puts $fd "fast400_to_fast400_setup_wns_ns=[path_slack $fast_after $fast_after max]"
puts $fd "slow200_to_slow200_setup_wns_ns=[path_slack $slow_after $slow_after max]"
puts $fd "slow200_to_fast400_setup_wns_ns=[path_slack $slow_after $fast_after max]"
puts $fd "fast400_to_slow200_setup_wns_ns=[path_slack $fast_after $slow_after max]"
puts $fd "fast400_to_fast400_hold_whs_ns=[path_slack $fast_after $fast_after min]"
puts $fd "slow200_to_slow200_hold_whs_ns=[path_slack $slow_after $slow_after min]"
puts $fd "slow200_to_fast400_hold_whs_ns=[path_slack $slow_after $fast_after min]"
puts $fd "fast400_to_slow200_hold_whs_ns=[path_slack $fast_after $slow_after min]"
puts $fd "severe_drc_count=[llength $severe_drc]"
puts $fd "new_timing_exception_count=$new_exception_count"
puts $fd "unrouted_net_count=$unrouted_net_count"
puts $fd "routing_error_count=$routing_error_count"
puts $fd "bitstream_written=false"
puts $fd "hardware_programmed=false"
close $fd

if {$new_exception_count != 0} {error "Routing introduced new timing exceptions"}
if {$unrouted_net_count != 0 || $routing_error_count != 0 || $setup_slack < 0 || $hold_slack < 0 || [llength $severe_drc] != 0} {
    puts "HALF2X_PL1_ROUTE_SIGNOFF_FAIL unrouted=$unrouted_net_count routing_errors=$routing_error_count WNS=$setup_slack WHS=$hold_slack severe_drc=[llength $severe_drc]"
    close_design
    exit 2
}
puts "HALF2X_PL1_ROUTE_PASS WNS=$setup_slack WHS=$hold_slack"
close_design
exit 0
