# Fresh placement for the fast-root plus sibling-BUFGCE_DIV half2x PL1
# candidate.  It discovers only the allowlisted automatic congestion
# transformations on the exact historical half2x placed reference, then
# applies them to a fresh implementation from the exact new post-synthesis
# DCP.  The historical DCP is evidence only and is never used incrementally.
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
proc require_one {objects label} {
    if {[llength $objects] != 1} {error "Expected exactly one $label, got [llength $objects]: $objects"}
    return [lindex $objects 0]
}
proc report_path_class {label from_clock to_clock output_dir} {
    set setup [get_timing_paths -quiet -delay_type max -from $from_clock -to $to_clock -max_paths 100]
    set hold [get_timing_paths -quiet -delay_type min -from $from_clock -to $to_clock -max_paths 100]
    if {[llength $setup] == 0 || [llength $hold] == 0} {error "Missing real timed path class $label"}
    report_timing -delay_type max -from $from_clock -to $to_clock -max_paths 100 -file [file join $output_dir "$label-setup-top100.rpt"]
    report_timing -delay_type min -from $from_clock -to $to_clock -max_paths 100 -file [file join $output_dir "$label-hold-top100.rpt"]
    return [list [get_property SLACK [lindex $setup 0]] [get_property SLACK [lindex $hold 0]]]
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
    if {[get_property AUTO $suggestion]} {
        set_property ENABLED 0 $suggestion
        if {[regexp {^RQS_CONG-(2_1|9|3_1)-[0-9]+$} $suggestion]} {
            set_property ENABLED 1 $suggestion
            lappend enabled_auto_suggestions $suggestion
        }
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
set slow_name half2x_clock_tree_driver_job_clk_200
set fast_name clock_wiz_clk_out1
require_clock $master_name 10.0 0 ""
require_clock $fast_name 2.5 1 $master_name
require_clock $slow_name 5.0 1 $fast_name
set unresolved [get_cells -quiet -hier -filter {IS_BLACKBOX == 1 && REF_NAME != DSP48E2}]
if {[llength $unresolved] != 0} {error "Unresolved custom blackboxes: $unresolved"}
set half2x_cells [get_cells -quiet -hier -filter {ORIG_REF_NAME == cnn_v10_pw_dsp16_half2x || REF_NAME == cnn_v10_pw_dsp16_half2x}]
if {[llength $half2x_cells] != 16} {error "Expected 16 half2x units, found [llength $half2x_cells]"}

# Freeze the physical clock topology before any implementation transform.
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

# Evidence-backed loose placement hint: only the source FF and the two LUTs
# before the promoted high-fanout buffer.  The buffer and its 1056 sinks stay
# unconstrained.  Require exact single matches so hierarchy drift fails closed.
set broadcast_source [get_cells -quiet -hierarchical -filter {NAME =~ *p2_data_1_U/dout_vld_reg}]
set broadcast_lut_a [get_cells -quiet -hierarchical -filter {NAME =~ *weight_broadcast_U0*flow_control_loop_pipe_sequential_init_U/word_04_fu_82*3*_i_4}]
set broadcast_lut_b [get_cells -quiet -hierarchical -filter {NAME =~ *weight_broadcast_U0*flow_control_loop_pipe_sequential_init_U/word_04_fu_82*3*_i_1}]
foreach {label cells} [list source $broadcast_source lut_a $broadcast_lut_a lut_b $broadcast_lut_b] {
    if {[llength $cells] != 1} {error "Broadcast soft-group $label match count=[llength $cells]: $cells"}
}
set broadcast_cells [concat $broadcast_source $broadcast_lut_a $broadcast_lut_b]
create_pblock pblock_half2x_broadcast_prebuf
resize_pblock [get_pblocks pblock_half2x_broadcast_prebuf] -add {SLICE_X20Y60:SLICE_X48Y125}
add_cells_to_pblock [get_pblocks pblock_half2x_broadcast_prebuf] $broadcast_cells
set_property IS_SOFT TRUE [get_pblocks pblock_half2x_broadcast_prebuf]
set_property EXCLUDE_PLACEMENT FALSE [get_pblocks pblock_half2x_broadcast_prebuf]
set_property CONTAIN_ROUTING FALSE [get_pblocks pblock_half2x_broadcast_prebuf]
set constraints_before [file join $output_dir timing-constraints-before-rqs.xdc]
write_xdc -force -type timing -constraints valid $constraints_before

read_qor_suggestions $rqs_file
set enabled_count 0
foreach suggestion [get_qor_suggestions] {
    if {[get_property AUTO $suggestion]} {
        set_property ENABLED 0 $suggestion
        if {[regexp {^RQS_CONG-(2_1|9|3_1)-[0-9]+$} $suggestion]} {
            set_property ENABLED 1 $suggestion
            incr enabled_count
        }
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
require_clock $fast_name 2.5 1 $master_name
require_clock $slow_name 5.0 1 $fast_name
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
set slow_clock [get_clocks $slow_name]
set fast_clock [get_clocks $fast_name]
set slow_slow [report_path_class slow-to-slow $slow_clock $slow_clock $output_dir]
set fast_fast [report_path_class fast-to-fast $fast_clock $fast_clock $output_dir]
set slow_fast [report_path_class slow-to-fast $slow_clock $fast_clock $output_dir]
set fast_slow [report_path_class fast-to-slow $fast_clock $slow_clock $output_dir]
report_timing -delay_type max -from $broadcast_source -max_paths 100 -file [file join $output_dir broadcast-prebuf-setup-top100.rpt]
report_utilization -pblocks pblock_half2x_broadcast_prebuf -file [file join $output_dir broadcast-softgroup-utilization.rpt]
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
puts $fd "clock_topology=mmcm_fast_plus_bufgce_div_v1"
puts $fd "common_mmcm_root_net=$root_net"
puts $fd "broadcast_softgroup_cell_count=[llength $broadcast_cells]"
puts $fd "broadcast_softgroup_range=SLICE_X20Y60:SLICE_X48Y125"
puts $fd "opt_directive=Explore"
puts $fd "place_directive=AltSpreadLogic_high"
puts $fd "physopt_directive=AggressiveExplore"
puts $fd "incremental_reference_used=false"
puts $fd "setup_wns_ns=[get_property SLACK $setup]"
puts $fd "hold_whs_ns=[get_property SLACK $hold]"
foreach {label values} [list slow_to_slow $slow_slow fast_to_fast $fast_fast slow_to_fast $slow_fast fast_to_slow $fast_slow] {
    puts $fd "path_class.$label.setup_slack_ns=[lindex $values 0]"
    puts $fd "path_class.$label.hold_slack_ns=[lindex $values 1]"
}
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
