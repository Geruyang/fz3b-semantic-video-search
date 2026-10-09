# Re-place the frozen fused-ALU post-opt checkpoint while preserving only the
# 32 stage-3 DSP primitives.  The prior placement proved that the Advanced
# Flow placer moved ten PREGs into fabric.  This bounded candidate prevents
# that transformation without changing RTL, arithmetic, clocks, or timing
# exceptions.  It does not route, write a bitstream, or access hardware.

if {$argc != 3} {
    error "usage: place_cnn_pipeline_v10_half2x_fused_alu_partial_repair_worst_leaf.tcl <known_good_post_place_dcp> <expected_sha256> <output_dir>"
}
lassign $argv post_opt_dcp expected_sha output_dir
set post_opt_dcp [file normalize $post_opt_dcp]
set output_dir [file normalize $output_dir]
if {![file isfile $post_opt_dcp]} {error "Missing post-opt DCP: $post_opt_dcp"}
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
proc require_preg_one {cells label expected_count} {
    if {[llength $cells] != $expected_count} {error "$label count mismatch: [llength $cells] != $expected_count"}
    set preg_zero {}
    foreach cell $cells {
        if {[get_property PREG $cell] != 1} {lappend preg_zero $cell}
    }
    if {[llength $preg_zero] != 0} {error "$label contains PREG!=1 cells: $preg_zero"}
}
proc report_path_class {label from_clock to_clock output_dir} {
    set setup [get_timing_paths -quiet -delay_type max -from $from_clock -to $to_clock -max_paths 100]
    set hold [get_timing_paths -quiet -delay_type min -from $from_clock -to $to_clock -max_paths 100]
    if {[llength $setup] == 0 || [llength $hold] == 0} {error "Missing real timed path class $label"}
    report_timing -delay_type max -from $from_clock -to $to_clock -max_paths 100 -file [file join $output_dir "$label-setup-top100.rpt"]
    report_timing -delay_type min -from $from_clock -to $to_clock -max_paths 100 -file [file join $output_dir "$label-hold-top100.rpt"]
    return [list [get_property SLACK [lindex $setup 0]] [get_property SLACK [lindex $hold 0]]]
}

if {[sha256_file $post_opt_dcp] ne [string tolower $expected_sha]} {error "Post-opt DCP SHA mismatch"}
foreach stale {half2x-partial-repair-post-place.dcp half2x-partial-repair-post-physopt.dcp partial-repair-place-status.rpt} {
    if {[file exists [file join $output_dir $stale]]} {error "Output result already exists: $stale"}
}
set_param general.maxThreads 16
open_checkpoint $post_opt_dcp
if {[get_property PART [current_design]] ne "xazu3eg-sfvc784-1-i"} {error "Unexpected target part"}

set master_name clk_pl_1
set slow_name half2x_clock_tree_driver_job_clk_200
set fast_name clock_wiz_clk_out1
set master [require_clock $master_name 10.0 0 ""]
set fast [require_clock $fast_name 2.5 1 $master_name]
set slow [require_clock $slow_name 5.0 1 $fast_name]
set unresolved [get_cells -quiet -hier -filter {IS_BLACKBOX == 1 && REF_NAME != DSP48E2}]
if {[llength $unresolved] != 0} {error "Unresolved custom blackboxes: $unresolved"}
set half2x_cells [get_cells -quiet -hier -filter {ORIG_REF_NAME == cnn_v10_pw_dsp16_half2x_fused_alu || REF_NAME =~ *cnn_v10_pw_dsp16_half2x_fused_alu*}]
if {[llength $half2x_cells] != 16} {error "Expected 16 fused half2x units, found [llength $half2x_cells]"}

set all_fused_dsps [get_cells -quiet -hier -filter {REF_NAME == DSP48E2 && NAME =~ *fused_half2x/half_dot/chain*/stage*/dsp_i}]
set chain0_stage3 [get_cells -quiet -hier -filter {REF_NAME == DSP48E2 && NAME =~ *fused_half2x/half_dot/chain0/stage3/dsp_i}]
set chain1_stage3 [get_cells -quiet -hier -filter {REF_NAME == DSP48E2 && NAME =~ *fused_half2x/half_dot/chain1/stage3/dsp_i}]
set protected_dsps [concat $chain0_stage3 $chain1_stage3]
require_preg_one $all_fused_dsps "post-opt all fused DSPs" 128
require_preg_one $chain0_stage3 "post-opt chain0 stage3 DSPs" 16
require_preg_one $chain1_stage3 "post-opt chain1 stage3 DSPs" 16
if {[lsearch -exact [list_property [lindex $protected_dsps 0]] DONT_TOUCH] < 0} {error "DSP cell does not expose DONT_TOUCH"}
set_property DONT_TOUCH TRUE $protected_dsps
set dont_touch_count 0
foreach cell $protected_dsps {
    if {[get_property DONT_TOUCH $cell]} {incr dont_touch_count}
}
if {$dont_touch_count != 32} {error "DONT_TOUCH readback count mismatch: $dont_touch_count"}

# Only the single evidence-proven failing leaf crosses clock regions.  Keep its
# eight DSPs in the less-dense southern clock region without fixing sites or
# constraining its fabric logic.  The pblock is soft and does not exclude other
# placement, so the placer retains freedom within the region.
set worst_leaf_dsps [get_cells -quiet -hier -filter {REF_NAME == DSP48E2 && NAME =~ */p_anonymous_namespace_pointwise_pair_expand_1_U0/*/grp_cnn_v10_pw_dsp16_fu_999/fused_half2x/half_dot/chain*/stage*/dsp_i}]
if {[llength $worst_leaf_dsps] != 8} {error "Expected 8 DSPs in the failing fused leaf, got [llength $worst_leaf_dsps]"}
set local_region [get_clock_regions -quiet X0Y0]
if {[llength $local_region] != 1} {error "Expected clock region X0Y0"}
create_pblock pblock_fused_leaf_fu_999_local
resize_pblock [get_pblocks pblock_fused_leaf_fu_999_local] -add {CLOCKREGION_X0Y0}
add_cells_to_pblock [get_pblocks pblock_fused_leaf_fu_999_local] $worst_leaf_dsps
set_property IS_SOFT TRUE [get_pblocks pblock_fused_leaf_fu_999_local]

# Freeze the same proven common-root clock topology.
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

set constraints_before [file join $output_dir timing-constraints-before-place.xdc]
write_xdc -force -type timing -constraints valid $constraints_before

# Retain the same placement/physical directives as the evidence-bearing prior
# candidate.  Only the exact 32 stage-3 DSP cells carry DONT_TOUCH.
# Preserve the evidence-bearing placement and reopen only the failing leaf DSPs.
# A normal place_design call is required to place the eight explicitly unplaced
# DSPs; all remaining placed cells are the legal partial-placement starting
# point.  The separate post-place pass then performs bounded cleanup.
array set input_dsp_locs {}
foreach cell [get_cells -quiet -hier -filter {REF_NAME == DSP48E2}] {
    set input_dsp_locs([get_property NAME $cell]) [get_property LOC $cell]
}
set target_names {}
foreach cell $worst_leaf_dsps {lappend target_names [get_property NAME $cell]}
unplace_cell $worst_leaf_dsps
place_design -directive Explore -net_delay_weight high
place_design -post_place_opt
set place_dcp [file join $output_dir half2x-partial-repair-post-place.dcp]
write_checkpoint -force $place_dcp
set all_fused_dsps [get_cells -quiet -hier -filter {REF_NAME == DSP48E2 && NAME =~ *fused_half2x/half_dot/chain*/stage*/dsp_i}]
set chain0_stage3 [get_cells -quiet -hier -filter {REF_NAME == DSP48E2 && NAME =~ *fused_half2x/half_dot/chain0/stage3/dsp_i}]
set chain1_stage3 [get_cells -quiet -hier -filter {REF_NAME == DSP48E2 && NAME =~ *fused_half2x/half_dot/chain1/stage3/dsp_i}]
require_preg_one $all_fused_dsps "post-place all fused DSPs" 128
require_preg_one $chain0_stage3 "post-place chain0 stage3 DSPs" 16
require_preg_one $chain1_stage3 "post-place chain1 stage3 DSPs" 16

phys_opt_design -directive AggressiveExplore
set physopt_dcp [file join $output_dir half2x-partial-repair-post-physopt.dcp]
write_checkpoint -force $physopt_dcp
set all_fused_dsps [get_cells -quiet -hier -filter {REF_NAME == DSP48E2 && NAME =~ *fused_half2x/half_dot/chain*/stage*/dsp_i}]
set chain0_stage3 [get_cells -quiet -hier -filter {REF_NAME == DSP48E2 && NAME =~ *fused_half2x/half_dot/chain0/stage3/dsp_i}]
set chain1_stage3 [get_cells -quiet -hier -filter {REF_NAME == DSP48E2 && NAME =~ *fused_half2x/half_dot/chain1/stage3/dsp_i}]
require_preg_one $all_fused_dsps "post-physopt all fused DSPs" 128
require_preg_one $chain0_stage3 "post-physopt chain0 stage3 DSPs" 16
require_preg_one $chain1_stage3 "post-physopt chain1 stage3 DSPs" 16

set timing_summary [file join $output_dir post-physopt-timing.rpt]
set congestion_report [file join $output_dir post-physopt-congestion.rpt]
report_timing_summary -delay_type min_max -report_unconstrained -check_timing_verbose -file $timing_summary
report_pulse_width -file [file join $output_dir post-physopt-pulse-width.rpt]
check_timing -verbose -file [file join $output_dir post-physopt-check-timing.rpt]
report_clock_interaction -file [file join $output_dir post-physopt-clock-interaction.rpt]
report_utilization -hierarchical -hierarchical_depth 8 -file [file join $output_dir post-physopt-utilization-hierarchical.rpt]
report_design_analysis -congestion -file $congestion_report
report_drc -file [file join $output_dir post-physopt-drc.rpt]
report_methodology -file [file join $output_dir post-physopt-methodology.rpt]
report_route_status -file [file join $output_dir post-physopt-route-status.rpt]
report_qor_suggestions -of_objects [get_qor_suggestions] -file [file join $output_dir post-physopt-qor-application.rpt]

set master_after [require_clock $master_name 10.0 0 ""]
set fast_after [require_clock $fast_name 2.5 1 $master_name]
set slow_after [require_clock $slow_name 5.0 1 $fast_name]
set constraints_after [file join $output_dir timing-constraints-post-physopt.xdc]
write_xdc -force -type timing -constraints valid $constraints_after
set exceptions_before [timing_exception_commands $constraints_before]
set exceptions_after [timing_exception_commands $constraints_after]
set new_exception_count 0
foreach exception $exceptions_after {
    if {[lsearch -exact $exceptions_before $exception] < 0} {incr new_exception_count}
}
set slow_slow [report_path_class slow-to-slow $slow_after $slow_after $output_dir]
set fast_fast [report_path_class fast-to-fast $fast_after $fast_after $output_dir]
set slow_fast [report_path_class slow-to-fast $slow_after $fast_after $output_dir]
set fast_slow [report_path_class fast-to-slow $fast_after $slow_after $output_dir]

set setup [get_timing_paths -quiet -delay_type max -max_paths 1]
set hold [get_timing_paths -quiet -delay_type min -max_paths 1]
if {[llength $setup] != 1 || [llength $hold] != 1} {error "Expected setup and hold paths"}
set severe_drc [get_drc_violations -quiet -filter {SEVERITY == Error || SEVERITY == "Critical Warning"}]
set blocking_drc {}
foreach violation $severe_drc {
    if {![string match "RTSTAT-13*" [get_property NAME $violation]]} {lappend blocking_drc $violation}
}
set congestion_fd [open $congestion_report r]
set congestion_text [read $congestion_fd]
close $congestion_fd
set maximum_congestion_level 0
foreach line [split $congestion_text \n] {
    if {[regexp {^\|[ \t]*(North|South|East|West)[ \t]*\|[ \t]*(Short|Long|Global)[ \t]*\|[ \t]*([0-9]+)[ \t]*\|} $line -> direction type level] && $level > $maximum_congestion_level} {
        set maximum_congestion_level $level
    }
}

set fd [open [file join $output_dir partial-repair-place-status.rpt] w]
puts $fd "status=HALF2X_FUSED_ALU_PARTIAL_REPAIR_WORST_LEAF_PLACE_COMPLETE"
puts $fd "input_post_opt_dcp_sha256=[sha256_file $post_opt_dcp]"
puts $fd "post_place_dcp_sha256=[sha256_file $place_dcp]"
puts $fd "post_physopt_dcp_sha256=[sha256_file $physopt_dcp]"
puts $fd "protected_stage3_dsp_count=32"
puts $fd "all_fused_dsp_count=[llength $all_fused_dsps]"
puts $fd "post_physopt_all_fused_dsp_preg1_count=128"
puts $fd "post_physopt_chain0_stage3_preg1_count=16"
puts $fd "post_physopt_chain1_stage3_preg1_count=16"
puts $fd "setup_wns_ns=[get_property SLACK $setup]"
puts $fd "hold_whs_ns=[get_property SLACK $hold]"
puts $fd "slow_to_slow_setup_wns_ns=[lindex $slow_slow 0]"
puts $fd "slow_to_slow_hold_whs_ns=[lindex $slow_slow 1]"
puts $fd "fast_to_fast_setup_wns_ns=[lindex $fast_fast 0]"
puts $fd "fast_to_fast_hold_whs_ns=[lindex $fast_fast 1]"
puts $fd "slow_to_fast_setup_wns_ns=[lindex $slow_fast 0]"
puts $fd "slow_to_fast_hold_whs_ns=[lindex $slow_fast 1]"
puts $fd "fast_to_slow_setup_wns_ns=[lindex $fast_slow 0]"
puts $fd "fast_to_slow_hold_whs_ns=[lindex $fast_slow 1]"
puts $fd "maximum_congestion_level=$maximum_congestion_level"
puts $fd "new_timing_exception_count=$new_exception_count"
puts $fd "severe_drc_count=[llength $severe_drc]"
puts $fd "blocking_drc_count=[llength $blocking_drc]"
puts $fd "localized_leaf_dsp_count=[llength $worst_leaf_dsps]"
puts $fd "localized_clock_region=X0Y0"
puts $fd "route_launched=false"
puts $fd "hardware_programmed=false"
close $fd

if {$new_exception_count != 0} {error "Placement introduced new timing exceptions"}
if {[get_property SLACK $setup] < 0 || [llength $blocking_drc] != 0} {error "Placement failed setup or blocking DRC gate"}
puts "HALF2X_FUSED_ALU_PARTIAL_REPAIR_WORST_LEAF_PLACE_COMPLETE setup=[get_property SLACK $setup] hold=[get_property SLACK $hold] max_congestion=$maximum_congestion_level"
close_design
exit 0

