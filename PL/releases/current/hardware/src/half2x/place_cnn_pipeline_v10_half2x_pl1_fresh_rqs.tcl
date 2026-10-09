# Prepared fallback for the half2x PL1 candidate.  It discovers only the
# automatic congestion transformations on an exact placed reference, then
# applies them to a fresh implementation from the exact post-synthesis DCP.
# It does not route, write a bitstream, or access hardware.

if {$argc != 5} {
    error "usage: place_cnn_pipeline_v10_half2x_pl1_fresh_rqs.tcl <reference_dcp> <reference_sha> <synth_dcp> <synth_sha> <output_dir>"
}
lassign $argv reference_dcp reference_sha synth_dcp synth_sha output_dir
foreach v {reference_dcp synth_dcp output_dir} {set $v [file normalize [set $v]]}
foreach f [list $reference_dcp $synth_dcp] {if {![file isfile $f]} {error "Missing input DCP: $f"}}
if {![file isdirectory $output_dir]} {error "Output directory must already exist"}

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
    if {[expr {[get_property IS_GENERATED $clock] ? 1 : 0}] != $generated} {error "Clock $name generated classification mismatch"}
    if {abs(double([get_property PERIOD $clock]) - $period) > 0.000001} {error "Clock $name period mismatch"}
    if {$generated && [get_property MASTER_CLOCK $clock] ne $master_name} {error "Clock $name master mismatch"}
    return $clock
}

if {[sha256_file $reference_dcp] ne [string tolower $reference_sha]} {error "Reference DCP SHA mismatch"}
if {[sha256_file $synth_dcp] ne [string tolower $synth_sha]} {error "Synthesis DCP SHA mismatch"}
set_param general.maxThreads 16

# The allowlist deliberately excludes utilization and clock suggestions.  The
# BRAM usage is already 81%, and the 100/200/400 MHz clock contract is fixed.
open_checkpoint $reference_dcp
report_qor_suggestions -report_all_suggestions -file [file join $output_dir reference-qor-suggestions.rpt]
set enabled_auto_suggestions {}
foreach suggestion [get_qor_suggestions] {
    if {[get_property AUTO $suggestion] && [regexp {^RQS_CONG-(2_1|9|3_1)-[0-9]+$} $suggestion]} {
        set_property ENABLED 1 $suggestion
        lappend enabled_auto_suggestions $suggestion
    }
}
if {[llength $enabled_auto_suggestions] < 1} {error "No allowlisted automatic congestion suggestion found"}
set rqs_file [file join $output_dir half2x-congestion-suggestions.rqs]
write_qor_suggestions -force $rqs_file
report_qor_suggestions -of_objects [get_qor_suggestions] -file [file join $output_dir reference-qor-enabled.rpt]
close_design

open_checkpoint $synth_dcp
if {[get_property PART [current_design]] ne "xazu3eg-sfvc784-1-i"} {error "Unexpected target part"}
set master_name clk_pl_1
set slow_name clk_out1_cnn_pipeline_v10_shell_clock_wiz_0
set fast_name clk_out2_cnn_pipeline_v10_shell_clock_wiz_0
require_clock $master_name 10.0 0 ""
require_clock $slow_name 5.0 1 $master_name
require_clock $fast_name 2.5 1 $master_name
set unresolved [get_cells -quiet -hier -filter {IS_BLACKBOX == 1 && REF_NAME != DSP48E2}]
if {[llength $unresolved] != 0} {error "Unresolved custom blackboxes: $unresolved"}
set half2x_cells [get_cells -quiet -hier -filter {ORIG_REF_NAME == cnn_v10_pw_dsp16_half2x || REF_NAME == cnn_v10_pw_dsp16_half2x}]
if {[llength $half2x_cells] != 16} {error "Expected 16 half2x units, found [llength $half2x_cells]"}
set constraints_before [file join $output_dir timing-constraints-before-rqs.xdc]
write_xdc -force -type timing -constraints valid $constraints_before

read_qor_suggestions $rqs_file
set enabled_count 0
foreach suggestion [get_qor_suggestions] {
    if {[get_property AUTO $suggestion]} {
        if {![regexp {^RQS_CONG-(2_1|9|3_1)-[0-9]+$} $suggestion]} {error "Unexpected auto suggestion in frozen RQS: $suggestion"}
        set_property ENABLED 1 $suggestion
        incr enabled_count
    }
}
if {$enabled_count != [llength $enabled_auto_suggestions]} {error "QoR suggestion count changed after read"}

opt_design -directive Explore
write_checkpoint -force [file join $output_dir half2x-fresh-rqs-post-opt.dcp]
place_design -directive AltSpreadLogic_high
write_checkpoint -force [file join $output_dir half2x-fresh-rqs-post-place.dcp]
phys_opt_design -directive AggressiveExplore
set physopt_dcp [file join $output_dir half2x-fresh-rqs-post-physopt.dcp]
write_checkpoint -force $physopt_dcp

set application_report [file join $output_dir post-physopt-qor-application.rpt]
set congestion_report [file join $output_dir post-physopt-congestion.rpt]
report_qor_suggestions -of_objects [get_qor_suggestions] -file $application_report
report_timing_summary -delay_type min_max -report_unconstrained -file [file join $output_dir post-physopt-timing.rpt]
report_pulse_width -file [file join $output_dir post-physopt-pulse-width.rpt]
check_timing -verbose -file [file join $output_dir post-physopt-check-timing.rpt]
report_clock_interaction -file [file join $output_dir post-physopt-clock-interaction.rpt]
report_utilization -hierarchical -hierarchical_depth 8 -file [file join $output_dir post-physopt-utilization-hierarchical.rpt]
report_design_analysis -congestion -file $congestion_report
report_drc -file [file join $output_dir post-physopt-drc.rpt]
report_methodology -file [file join $output_dir post-physopt-methodology.rpt]
report_route_status -file [file join $output_dir post-physopt-route-status.rpt]

require_clock $master_name 10.0 0 ""
require_clock $slow_name 5.0 1 $master_name
require_clock $fast_name 2.5 1 $master_name
set constraints_after [file join $output_dir timing-constraints-post-physopt.xdc]
write_xdc -force -type timing -constraints valid $constraints_after
set exceptions_before [timing_exception_commands $constraints_before]
set exceptions_after [timing_exception_commands $constraints_after]
set new_exception_count 0
foreach exception $exceptions_after {
    if {[lsearch -exact $exceptions_before $exception] < 0} {incr new_exception_count}
}

set application_fd [open $application_report r]
set application_text [read $application_fd]
close $application_fd
set applied_count [regexp -all {\|[ \t]+Applied[ \t]+\|} $application_text]
set failed_count [regexp -all {\|[ \t]+Failed to Apply[ \t]+\|} $application_text]
if {$applied_count < 1} {error "No allowlisted congestion suggestion was applied"}

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
set fd [open [file join $output_dir fresh-rqs-place-status.rpt] w]
puts $fd "status=HALF2X_PL1_FRESH_RQS_PLACE_COMPLETE"
puts $fd "reference_dcp_sha256=[sha256_file $reference_dcp]"
puts $fd "synth_dcp_sha256=[sha256_file $synth_dcp]"
puts $fd "rqs_sha256=[sha256_file $rqs_file]"
puts $fd "enabled_auto_suggestion_count=$enabled_count"
puts $fd "applied_suggestion_count=$applied_count"
puts $fd "failed_suggestion_count=$failed_count"
puts $fd "half2x_unit_count=[llength $half2x_cells]"
puts $fd "unresolved_custom_blackbox_count=[llength $unresolved]"
puts $fd "opt_directive=Explore"
puts $fd "place_directive=AltSpreadLogic_high"
puts $fd "physopt_directive=AggressiveExplore"
puts $fd "incremental_reference_used=false"
puts $fd "setup_wns_ns=[get_property SLACK $setup]"
puts $fd "hold_whs_ns=[get_property SLACK $hold]"
puts $fd "new_timing_exception_count=$new_exception_count"
puts $fd "maximum_congestion_level=$maximum_congestion_level"
puts $fd "level5_or_worse_window_count=$level5_or_worse_count"
puts $fd "route_launched=false"
puts $fd "hardware_programmed=false"
close $fd

if {$new_exception_count != 0} {error "Fresh RQS placement introduced new timing exceptions"}
puts "HALF2X_PL1_FRESH_RQS_PLACE_COMPLETE setup=[get_property SLACK $setup] hold=[get_property SLACK $hold] max_congestion=$maximum_congestion_level applied=$applied_count failed=$failed_count"
close_design
exit 0
