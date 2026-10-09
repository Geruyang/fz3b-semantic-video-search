# Half-width PW DSP platform placement assessment.
#
# The script starts from the integrated post-synthesis checkpoint, runs a fresh
# placement without an incremental reference from the full-width design, and
# stops before route_design.  The half-width design has a materially different
# DSP topology and a new 400 MHz clock domain, so inheriting full-width DSP
# locations would obscure the first physical feasibility result.

if {$argc != 3} {
    error "usage: place_cnn_pipeline_v10_half2x_pl1.tcl <post_synth_dcp> <expected_sha256> <output_dir>"
}
lassign $argv input_dcp expected_sha output_dir
set input_dcp [file normalize $input_dcp]
set output_dir [file normalize $output_dir]
if {![file isfile $input_dcp]} {error "Missing post-synthesis DCP: $input_dcp"}
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

if {[sha256_file $input_dcp] ne [string tolower $expected_sha]} {
    error "Integrated post-synthesis DCP SHA mismatch"
}

set_param general.maxThreads 16
open_checkpoint $input_dcp
if {[get_property PART [current_design]] ne "xazu3eg-sfvc784-1-i"} {error "Unexpected target part"}

set master_name clk_pl_1
set slow_name clk_out1_cnn_pipeline_v10_shell_clock_wiz_0
set fast_name clk_out2_cnn_pipeline_v10_shell_clock_wiz_0
set master [require_clock $master_name 10.0 0 ""]
set slow [require_clock $slow_name 5.0 1 $master_name]
set fast [require_clock $fast_name 2.5 1 $master_name]

# clk_pl_0 remains a PS model clock in the generated wrapper, but this
# candidate's compute/reset chain must be driven only by clk_pl_1 derivatives.
set clk0 [get_clocks -quiet clk_pl_0]
if {[llength $clk0] != 1} {error "Expected the unused clk_pl_0 model clock"}

set unresolved [get_cells -quiet -hier -filter {IS_BLACKBOX == 1 && REF_NAME != DSP48E2}]
if {[llength $unresolved] != 0} {error "Unresolved custom blackboxes before placement: $unresolved"}
set half2x_cells [get_cells -quiet -hier -filter {ORIG_REF_NAME == cnn_v10_pw_dsp16_half2x || REF_NAME == cnn_v10_pw_dsp16_half2x}]
if {[llength $half2x_cells] != 16} {error "Expected 16 half2x pointwise units, found [llength $half2x_cells]"}

set timing_before [file join $output_dir timing-constraints-before-place.xdc]
write_xdc -force -type timing -constraints valid $timing_before

# Fresh physical baseline: avoid importing full-width DSP locations.  Explore
# plus AggressiveExplore are supported by this installed 2026.1 tool and have
# already completed on the same device.  No hard pblocks are imposed; the
# placer remains free to co-locate each 400 MHz half2x chain while spreading
# the LUT-heavy shell.
opt_design -directive Explore
set opt_dcp [file join $output_dir half2x-post-opt.dcp]
write_checkpoint -force $opt_dcp

place_design -directive Explore
set placed_dcp [file join $output_dir half2x-post-place.dcp]
write_checkpoint -force $placed_dcp

phys_opt_design -directive AggressiveExplore
set physopt_dcp [file join $output_dir half2x-post-physopt.dcp]
write_checkpoint -force $physopt_dcp

# Expensive stages are checkpointed before all reports and acceptance parsing.
report_timing_summary -delay_type min_max -report_unconstrained -file [file join $output_dir post-physopt-timing-summary.rpt]
report_timing -from $fast -to $fast -delay_type max -max_paths 100 -file [file join $output_dir fast400-to-fast400-setup-top100.rpt]
report_timing -from $slow -to $slow -delay_type max -max_paths 100 -file [file join $output_dir slow200-to-slow200-setup-top100.rpt]
report_timing -from $slow -to $fast -delay_type max -max_paths 100 -file [file join $output_dir slow200-to-fast400-setup-top100.rpt]
report_timing -from $fast -to $slow -delay_type max -max_paths 100 -file [file join $output_dir fast400-to-slow200-setup-top100.rpt]
report_timing -from $fast -to $fast -delay_type min -max_paths 100 -file [file join $output_dir fast400-to-fast400-hold-top100.rpt]
report_timing -from $slow -to $fast -delay_type min -max_paths 100 -file [file join $output_dir slow200-to-fast400-hold-top100.rpt]
report_timing -from $fast -to $slow -delay_type min -max_paths 100 -file [file join $output_dir fast400-to-slow200-hold-top100.rpt]
report_pulse_width -file [file join $output_dir post-physopt-pulse-width.rpt]
check_timing -verbose -file [file join $output_dir post-physopt-check-timing.rpt]
report_clocks -file [file join $output_dir post-physopt-clocks.rpt]
report_clock_interaction -file [file join $output_dir post-physopt-clock-interaction.rpt]
report_utilization -file [file join $output_dir post-physopt-utilization.rpt]
report_utilization -hierarchical -hierarchical_depth 8 -file [file join $output_dir post-physopt-utilization-hierarchical.rpt]
set congestion_report [file join $output_dir post-physopt-congestion.rpt]
report_design_analysis -congestion -file $congestion_report
report_control_sets -verbose -file [file join $output_dir post-physopt-control-sets.rpt]
report_drc -file [file join $output_dir post-physopt-drc.rpt]
report_methodology -file [file join $output_dir post-physopt-methodology.rpt]
report_route_status -file [file join $output_dir post-physopt-route-status.rpt]
report_qor_suggestions -file [file join $output_dir post-physopt-qor-suggestions.rpt]

set master_after [require_clock $master_name 10.0 0 ""]
set slow_after [require_clock $slow_name 5.0 1 $master_name]
set fast_after [require_clock $fast_name 2.5 1 $master_name]
set timing_after [file join $output_dir timing-constraints-post-physopt.xdc]
write_xdc -force -type timing -constraints valid $timing_after
set exceptions_before [timing_exception_commands $timing_before]
set exceptions_after [timing_exception_commands $timing_after]
set new_exception_count 0
foreach exception $exceptions_after {
    if {[lsearch -exact $exceptions_before $exception] < 0} {incr new_exception_count}
}

set congestion_fd [open $congestion_report r]
set congestion_text [read $congestion_fd]
close $congestion_fd
set maximum_congestion_level 0
set level5_or_worse_count 0
set matched_congestion_windows 0
foreach line [split $congestion_text \n] {
    if {[regexp {^\|[ \t]+(North|South|East|West)[ \t]+\|[ \t]+(Global|Long|Short)[ \t]+\|[ \t]+([0-9]+)[ \t]+\|} $line -> direction type level]} {
        incr matched_congestion_windows
        if {$level > $maximum_congestion_level} {set maximum_congestion_level $level}
        if {$level >= 5} {incr level5_or_worse_count}
    }
}
if {$matched_congestion_windows == 0} {error "Congestion report contained no parseable windows"}

set setup [get_timing_paths -delay_type max -max_paths 1]
set hold [get_timing_paths -delay_type min -max_paths 1]
if {[llength $setup] != 1 || [llength $hold] != 1} {error "Expected setup and hold paths"}
set pulse [get_timing_paths -quiet -check_type pulse_width -max_paths 1]

set fd [open [file join $output_dir half2x-place-status.rpt] w]
puts $fd "status=HALF2X_PL1_PLACE_COMPLETE"
puts $fd "input_dcp_sha256=[sha256_file $input_dcp]"
puts $fd "opt_dcp_sha256=[sha256_file $opt_dcp]"
puts $fd "placed_dcp_sha256=[sha256_file $placed_dcp]"
puts $fd "physopt_dcp_sha256=[sha256_file $physopt_dcp]"
puts $fd "part=[get_property PART [current_design]]"
puts $fd "master_clock=$master_after"
puts $fd "master_period_ns=[get_property PERIOD $master_after]"
puts $fd "slow_clock=$slow_after"
puts $fd "slow_period_ns=[get_property PERIOD $slow_after]"
puts $fd "fast_clock=$fast_after"
puts $fd "fast_period_ns=[get_property PERIOD $fast_after]"
puts $fd "half2x_unit_count=[llength $half2x_cells]"
puts $fd "unresolved_custom_blackbox_count=[llength $unresolved]"
puts $fd "opt_directive=Explore"
puts $fd "place_directive=Explore"
puts $fd "physopt_directive=AggressiveExplore"
puts $fd "incremental_reference_used=false"
puts $fd "hard_pblocks_added=false"
puts $fd "setup_wns_ns=[get_property SLACK $setup]"
puts $fd "hold_whs_ns=[get_property SLACK $hold]"
puts $fd "pulse_width_slack_ns=[expr {[llength $pulse] == 1 ? [get_property SLACK $pulse] : "NA"}]"
puts $fd "fast400_to_fast400_setup_wns_ns=[path_slack $fast_after $fast_after max]"
puts $fd "slow200_to_slow200_setup_wns_ns=[path_slack $slow_after $slow_after max]"
puts $fd "slow200_to_fast400_setup_wns_ns=[path_slack $slow_after $fast_after max]"
puts $fd "fast400_to_slow200_setup_wns_ns=[path_slack $fast_after $slow_after max]"
puts $fd "fast400_to_fast400_hold_whs_ns=[path_slack $fast_after $fast_after min]"
puts $fd "slow200_to_fast400_hold_whs_ns=[path_slack $slow_after $fast_after min]"
puts $fd "fast400_to_slow200_hold_whs_ns=[path_slack $fast_after $slow_after min]"
puts $fd "timing_constraints_before_sha256=[sha256_file $timing_before]"
puts $fd "timing_constraints_post_physopt_sha256=[sha256_file $timing_after]"
puts $fd "timing_exception_sets_identical=[expr {$exceptions_before eq $exceptions_after}]"
puts $fd "new_timing_exception_count=$new_exception_count"
puts $fd "matched_congestion_windows=$matched_congestion_windows"
puts $fd "maximum_congestion_level=$maximum_congestion_level"
puts $fd "level5_or_worse_window_count=$level5_or_worse_count"
puts $fd "route_launched=false"
puts $fd "route_gate_requires_evidence_review=true"
puts $fd "hardware_programmed=false"
close $fd

if {$new_exception_count != 0} {error "Placement introduced new timing exceptions"}
puts "HALF2X_PL1_PLACE_COMPLETE route=false setup=[get_property SLACK $setup] hold=[get_property SLACK $hold] max_congestion=$maximum_congestion_level level5plus=$level5_or_worse_count"
close_design
exit 0
