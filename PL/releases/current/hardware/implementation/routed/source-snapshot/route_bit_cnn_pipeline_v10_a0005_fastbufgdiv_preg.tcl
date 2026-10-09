# Route and bitstream signoff for the frozen A0005 fused-IP 1.3 PREG-protected post-physopt
# checkpoint.  The routed DCP is written immediately after route_design, before
# reports or parsing.  This script never reads an incremental checkpoint,
# applies LOCs, creates pblocks, emits an LTX, or accesses hardware.

if {$argc != 3} {
    error "usage: route_bit_cnn_pipeline_v10_a0005_fastbufgdiv.tcl POST_PHYS_DCP EXPECTED_SHA256 OUTPUT_DIR"
}
lassign $argv input_dcp expected_sha output_dir
set input_dcp [file normalize $input_dcp]
set output_dir [file normalize $output_dir]
if {![file isfile $input_dcp]} {error "Missing A0005 post-physopt DCP: $input_dcp"}
if {![file isdirectory $output_dir]} {error "Output directory must already exist: $output_dir"}

proc sha256_file {path} {
    set value [string tolower [lindex [split [exec certutil -hashfile $path SHA256] \n] 1]]
    regsub -all { } $value {} value
    return $value
}
proc require_one {objects label} {
    if {[llength $objects] != 1} {error "Expected exactly one $label, got [llength $objects]: $objects"}
    return [lindex $objects 0]
}
proc require_clock {name period generated master_name} {
    set clock [get_clocks -quiet $name]
    if {[llength $clock] != 1} {error "Expected exactly one clock named $name"}
    if {[expr {[get_property IS_GENERATED $clock] ? 1 : 0}] != $generated} {
        error "Clock $name generated-clock classification mismatch"
    }
    if {abs(double([get_property PERIOD $clock]) - double($period)) > 0.000001} {
        error "Clock $name period mismatch"
    }
    if {$generated && [get_property MASTER_CLOCK $clock] ne $master_name} {
        error "Clock $name master-clock mismatch"
    }
    return $clock
}
proc require_path_slack {label from_clock to_clock delay_type} {
    set paths [get_timing_paths -quiet -from $from_clock -to $to_clock -delay_type $delay_type -max_paths 1]
    if {[llength $paths] != 1} {error "Missing real $delay_type timing path for $label"}
    set slack [get_property SLACK $paths]
    if {![string is double -strict $slack] || double($slack) < 0.0} {
        error "$label $delay_type slack is negative or invalid: $slack"
    }
    return $slack
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
proc parse_pulse_report {path} {
    set fd [open $path r]
    set text [read $fd]
    close $fd
    set match_count 0
    set minimum_slack 1.0e30
    foreach line [split $text \n] {
        if {[regexp {[ \t](-?[0-9]+\.[0-9]+)[ \t]+(-?[0-9]+\.[0-9]+)[ \t]+(-?[0-9]+\.[0-9]+)[ \t]+(?:[A-Za-z0-9_/-]+)[ \t]+} $line -> required actual slack]} {
            incr match_count
            if {double($slack) < $minimum_slack} {set minimum_slack $slack}
        }
    }
    if {$match_count == 0} {error "Pulse report contained no parseable checks"}
    if {double($minimum_slack) < 0.0} {error "Pulse-width slack is negative: $minimum_slack"}
    return [list $match_count $minimum_slack]
}
proc parse_check_timing {path} {
    set fd [open $path r]
    set text [read $fd]
    close $fd
    set category_count 0
    set issue_count 0
    foreach line [split $text \n] {
        if {[regexp {^[0-9]+\. checking [^(]+\(([0-9]+)\)} [string trim $line] -> count]} {
            incr category_count
            incr issue_count $count
        }
    }
    if {$category_count < 12} {error "check_timing report contained only $category_count categories"}
    if {$issue_count != 0} {error "check_timing has $issue_count issues"}
    return [list $category_count $issue_count]
}

set required_input_sha 0b621562e9a0e749eafffed987b13182c64948aa8a3fd6df96cc3831a9197d40
if {[string tolower $expected_sha] ne $required_input_sha || [sha256_file $input_dcp] ne $required_input_sha} {
    error "A0005 post-physopt DCP SHA mismatch"
}
foreach stale {
    a0005-post-route.dcp a0005-post-route.bit a0005-post-route.bin
    a0005-route-bit-status.rpt timing-summary-post-route.rpt route-status-post-route.rpt
} {
    if {[file exists [file join $output_dir $stale]]} {error "Output result already exists: $stale"}
}

set_param general.maxThreads 16
if {[get_param general.maxThreads] != 16} {error "general.maxThreads did not accept 16"}
set_param synth.maxThreads 8
if {[get_param synth.maxThreads] != 8} {error "synth.maxThreads did not accept 8"}
set_param general.maxThreads 8
if {[get_param general.maxThreads] != 8} {error "implementation maxThreads did not accept 8"}

open_checkpoint $input_dcp
if {[get_property PART [current_design]] ne "xazu3eg-sfvc784-1-i"} {error "Unexpected target part"}

set master_name clk_pl_1
set fast_name clock_wiz_clk_out1
set slow_name half2x_clock_tree_driver_job_clk_200
set master [require_clock $master_name 10.0 0 ""]
set fast [require_clock $fast_name 2.5 1 $master_name]
set slow [require_clock $slow_name 5.0 1 $fast_name]

set mmcm [require_one [get_cells -quiet -hierarchical -filter {REF_NAME =~ MMCME* && NAME =~ *clock_wiz*}] "clock-wizard MMCM"]
foreach {property expected} {CLKFBOUT_MULT_F 12.000 DIVCLK_DIVIDE 1 CLKOUT0_DIVIDE_F 3.000} {
    if {abs(double([get_property $property $mmcm]) - double($expected)) > 0.0005} {error "MMCM $property mismatch"}
}
set fast_buffer [require_one [get_cells -quiet -hierarchical -filter {REF_NAME == BUFGCE_DIV && NAME =~ *half2x_clock_tree*pw_local*}] "fast BUFGCE_DIV"]
set slow_buffer [require_one [get_cells -quiet -hierarchical -filter {REF_NAME == BUFGCE_DIV && NAME =~ *half2x_clock_tree*driver_job*}] "slow BUFGCE_DIV"]
if {[get_property BUFGCE_DIVIDE $fast_buffer] != 1 || [get_property BUFGCE_DIVIDE $slow_buffer] != 2} {
    error "BUFGCE_DIV ratio mismatch"
}
set fast_i [require_one [get_pins -quiet -of_objects $fast_buffer -filter {REF_PIN_NAME == I}] "fast divider I"]
set slow_i [require_one [get_pins -quiet -of_objects $slow_buffer -filter {REF_PIN_NAME == I}] "slow divider I"]
set root_net [require_one [get_nets -quiet -of_objects $fast_i] "fast divider root net"]
if {$root_net ne [require_one [get_nets -quiet -of_objects $slow_i] "slow divider root net"]} {
    error "BUFGCE_DIV siblings do not share one root net"
}
set root_driver [require_one [get_pins -quiet -leaf -of_objects $root_net -filter {DIRECTION == OUT}] "root clock driver"]
if {[get_property REF_PIN_NAME $root_driver] ne "CLKOUT0" || ![string match {MMCME*} [get_property REF_NAME [get_cells -of_objects $root_driver]]]} {
    error "BUFGCE_DIV siblings are not directly driven by MMCM CLKOUT0"
}

set fused_units [get_cells -quiet -hierarchical -filter {ORIG_REF_NAME == cnn_v10_pw_dsp16_half2x_fused_alu || REF_NAME =~ *cnn_v10_pw_dsp16_half2x_fused_alu*}]
if {[llength $fused_units] != 16} {error "Expected 16 fused half2x units, found [llength $fused_units]"}
set fused_dsps [get_cells -quiet -hierarchical -filter {REF_NAME == DSP48E2 && NAME =~ *fused_half2x*}]
if {[llength $fused_dsps] != 128} {error "Expected 128 fused pointwise DSP48E2 cells, found [llength $fused_dsps]"}
set non_preg_dsps {}
foreach dsp $fused_dsps {
    if {[get_property PREG $dsp] != 1} {lappend non_preg_dsps $dsp}
}
if {[llength $non_preg_dsps] != 0} {error "Fused pointwise PREG=1 pre-route gate failed: $non_preg_dsps"}
set unresolved [get_cells -quiet -hierarchical -filter {IS_BLACKBOX == 1 && REF_NAME != DSP48E2}]
if {[llength $unresolved] != 0} {error "Unresolved custom blackboxes: $unresolved"}

set constraints_before [file join $output_dir timing-constraints-before-route.xdc]
write_xdc -force -type timing -constraints valid $constraints_before

# One fresh route from the frozen placed/physopt DCP.  No incremental reference,
# historical exact locations, or new physical constraints are read or applied.
route_design -directive MoreGlobalIterations

# Preserve the expensive result before any report command or parser can fail.
set routed_dcp [file join $output_dir a0005-post-route.dcp]
write_checkpoint -force $routed_dcp

report_clocks -file [file join $output_dir clocks-post-route.rpt]
report_clock_interaction -file [file join $output_dir clock-interaction-post-route.rpt]
report_timing_summary -delay_type min_max -report_unconstrained -check_timing_verbose -file [file join $output_dir timing-summary-post-route.rpt]
foreach {label from_clock to_clock} [list \
    slow200-to-slow200 $slow $slow \
    fast400-to-fast400 $fast $fast \
    slow200-to-fast400 $slow $fast \
    fast400-to-slow200 $fast $slow] {
    report_timing -from $from_clock -to $to_clock -delay_type max -max_paths 100 -file [file join $output_dir ${label}-setup-post-route.rpt]
    report_timing -from $from_clock -to $to_clock -delay_type min -max_paths 100 -file [file join $output_dir ${label}-hold-post-route.rpt]
}
set pulse_file [file join $output_dir pulse-width-post-route.rpt]
report_pulse_width -file $pulse_file
set check_timing_file [file join $output_dir check-timing-post-route.rpt]
check_timing -verbose -file $check_timing_file
set route_status_file [file join $output_dir route-status-post-route.rpt]
report_route_status -file $route_status_file
report_utilization -file [file join $output_dir utilization-post-route.rpt]
report_utilization -hierarchical -hierarchical_depth 12 -file [file join $output_dir utilization-hierarchical-post-route.rpt]
set drc_file [file join $output_dir drc-post-route.rpt]
report_drc -file $drc_file
report_methodology -file [file join $output_dir methodology-post-route.rpt]
report_cdc -details -file [file join $output_dir cdc-post-route.rpt]
report_bus_skew -file [file join $output_dir bus-skew-post-route.rpt]
report_design_analysis -congestion -file [file join $output_dir congestion-post-route.rpt]
report_qor_suggestions -report_all_suggestions -file [file join $output_dir qor-suggestions-post-route.rpt]

set constraints_after [file join $output_dir timing-constraints-post-route.xdc]
write_xdc -force -type timing -constraints valid $constraints_after
set new_exception_count 0
set exceptions_before [timing_exception_commands $constraints_before]
foreach exception [timing_exception_commands $constraints_after] {
    if {[lsearch -exact $exceptions_before $exception] < 0} {incr new_exception_count}
}

set master_after [require_clock $master_name 10.0 0 ""]
set fast_after [require_clock $fast_name 2.5 1 $master_name]
set slow_after [require_clock $slow_name 5.0 1 $fast_name]
set setup [get_timing_paths -quiet -delay_type max -max_paths 1]
set hold [get_timing_paths -quiet -delay_type min -max_paths 1]
if {[llength $setup] != 1 || [llength $hold] != 1} {error "Missing global setup/hold paths"}
set setup_slack [get_property SLACK $setup]
set hold_slack [get_property SLACK $hold]
if {double($setup_slack) < 0.0 || double($hold_slack) < 0.0} {
    error "Global timing failed: WNS=$setup_slack WHS=$hold_slack"
}

array set class_slack {}
foreach {label from_clock to_clock} [list \
    slow200_to_slow200 $slow_after $slow_after \
    fast400_to_fast400 $fast_after $fast_after \
    slow200_to_fast400 $slow_after $fast_after \
    fast400_to_slow200 $fast_after $slow_after] {
    set class_slack(${label}_setup) [require_path_slack $label $from_clock $to_clock max]
    set class_slack(${label}_hold) [require_path_slack $label $from_clock $to_clock min]
}
set pulse_result [parse_pulse_report $pulse_file]
set check_result [parse_check_timing $check_timing_file]

set route_fd [open $route_status_file r]
set route_text [read $route_fd]
close $route_fd
if {![regexp {# of unrouted nets\.+[ \t]*:[ \t]*([0-9]+)} $route_text -> unrouted_net_count]} {
    error "Could not parse unrouted-net count"
}
if {![regexp {# of nets with routing errors\.+[ \t]*:[ \t]*([0-9]+)} $route_text -> routing_error_count]} {
    error "Could not parse routing-error count"
}
if {$unrouted_net_count != 0 || $routing_error_count != 0} {
    error "Route signoff failed: unrouted=$unrouted_net_count routing_errors=$routing_error_count"
}
set severe_drc [get_drc_violations -quiet -filter {SEVERITY == Error || SEVERITY == "Critical Warning"}]
if {[llength $severe_drc] != 0} {error "Post-route Error/Critical-Warning DRC count is [llength $severe_drc]"}
if {$new_exception_count != 0} {error "Route introduced $new_exception_count new timing exceptions"}

# Recheck structure after route and before bitstream generation.
set fused_dsps_after [get_cells -quiet -hierarchical -filter {REF_NAME == DSP48E2 && NAME =~ *fused_half2x*}]
set preg1_after 0
foreach dsp $fused_dsps_after {if {[get_property PREG $dsp] == 1} {incr preg1_after}}
if {[llength $fused_dsps_after] != 128 || $preg1_after != 128} {error "Post-route fused DSP/PREG identity changed"}
if {[llength [get_debug_cores -quiet]] != 0} {error "Debug core found; no-LTX release image required"}
set debug_cells [get_cells -quiet -hierarchical -filter {REF_NAME =~ *ILA* || REF_NAME =~ *VIO* || NAME =~ *dbg_hub*}]
if {[llength $debug_cells] != 0} {error "Debug/ILA cell found; no-LTX release image required"}

set bit_file [file join $output_dir a0005-post-route.bit]
set_property BITSTREAM.GENERAL.COMPRESS TRUE [current_design]
write_bitstream -force -bin_file $bit_file
set bin_file [file rootname $bit_file].bin
if {![file isfile $bit_file] || [file size $bit_file] == 0} {error "Missing or empty bitstream"}
if {![file isfile $bin_file] || [file size $bin_file] == 0} {error "Missing or empty bin image"}
set ltx_files [glob -nocomplain -directory $output_dir *.ltx]
if {[llength $ltx_files] != 0} {error "Unexpected LTX output: $ltx_files"}

set status [open [file join $output_dir a0005-route-bit-status.rpt] w]
puts $status "status=A0005_ROUTE_BIT_PASS"
puts $status "input_post_phys_dcp_sha256=[sha256_file $input_dcp]"
puts $status "routed_dcp_sha256=[sha256_file $routed_dcp]"
puts $status "bit_sha256=[sha256_file $bit_file]"
puts $status "bin_sha256=[sha256_file $bin_file]"
puts $status "general_threads_supported=16"
puts $status "synth_threads_supported=8"
puts $status "implementation_threads_effective=[get_param general.maxThreads]"
puts $status "jobs=1"
puts $status "route_directive=MoreGlobalIterations"
puts $status "incremental_reference_used=false"
puts $status "exactloc_applied_by_route_script=false"
puts $status "master_period_ns=[get_property PERIOD $master_after]"
puts $status "fast_period_ns=[get_property PERIOD $fast_after]"
puts $status "slow_period_ns=[get_property PERIOD $slow_after]"
puts $status "mmcm_m=[get_property CLKFBOUT_MULT_F $mmcm]"
puts $status "mmcm_d=[get_property DIVCLK_DIVIDE $mmcm]"
puts $status "mmcm_o_fast=[get_property CLKOUT0_DIVIDE_F $mmcm]"
puts $status "pw_local_bufgce_divide=[get_property BUFGCE_DIVIDE $fast_buffer]"
puts $status "driver_job_bufgce_divide=[get_property BUFGCE_DIVIDE $slow_buffer]"
puts $status "common_mmcm_root_net=$root_net"
puts $status "fused_unit_count=[llength $fused_units]"
puts $status "fused_dsp48e2_count=[llength $fused_dsps_after]"
puts $status "fused_dsp_preg1_count=$preg1_after"
puts $status "setup_wns_ns=$setup_slack"
puts $status "hold_whs_ns=$hold_slack"
foreach key [lsort [array names class_slack]] {puts $status "path_class.$key=$class_slack($key)"}
puts $status "pulse_check_count=[lindex $pulse_result 0]"
puts $status "pulse_minimum_slack_ns=[lindex $pulse_result 1]"
puts $status "check_timing_category_count=[lindex $check_result 0]"
puts $status "check_timing_issue_count=[lindex $check_result 1]"
puts $status "unrouted_net_count=$unrouted_net_count"
puts $status "routing_error_count=$routing_error_count"
puts $status "severe_drc_count=[llength $severe_drc]"
puts $status "new_timing_exception_count=$new_exception_count"
puts $status "debug_core_count=0"
puts $status "ltx_count=0"
puts $status "bitstream_written=true"
puts $status "bin_written=true"
puts $status "hardware_accessed=false"
close $status

puts "A0005_ROUTE_BIT_PASS routed_dcp=$routed_dcp bit=$bit_file bin=$bin_file no_ltx=true"
close_design
exit 0
