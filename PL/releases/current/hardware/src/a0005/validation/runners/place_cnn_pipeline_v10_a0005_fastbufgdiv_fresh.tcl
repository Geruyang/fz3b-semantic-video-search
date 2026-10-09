# Fresh, nonincremental A0005 placement from the frozen fused-IP 1.3 platform
# synthesis checkpoint.  This stage never routes, writes a bitstream, or opens
# hardware.  Checkpoints are written before report generation so an expensive
# completed stage survives a later reporting failure.

if {$argc != 5} {
    error "usage: place_cnn_pipeline_v10_a0005_fastbufgdiv_fresh.tcl SYNTH_DCP EXPECTED_DCP_SHA SYNTH_RECEIPT EXPECTED_RECEIPT_SHA OUTPUT_DIR"
}
lassign $argv synth_dcp expected_dcp_sha synth_receipt expected_receipt_sha output_dir
foreach name {synth_dcp synth_receipt output_dir} {set $name [file normalize [set $name]]}
if {![file isfile $synth_dcp]} {error "Missing A0005 post-synth DCP: $synth_dcp"}
if {![file isfile $synth_receipt]} {error "Missing A0005 platform synth receipt: $synth_receipt"}
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
    if {[expr {[get_property IS_GENERATED $clock] ? 1 : 0}] != $generated} {error "Clock $name generated classification mismatch"}
    if {abs(double([get_property PERIOD $clock]) - double($period)) > 0.000001} {error "Clock $name period mismatch"}
    if {$generated && [get_property MASTER_CLOCK $clock] ne $master_name} {error "Clock $name master mismatch"}
    return $clock
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
proc report_path_class {label from_clock to_clock output_dir} {
    set setup [get_timing_paths -quiet -from $from_clock -to $to_clock -delay_type max -max_paths 1]
    set hold [get_timing_paths -quiet -from $from_clock -to $to_clock -delay_type min -max_paths 1]
    if {[llength $setup] != 1 || [llength $hold] != 1} {error "Missing real setup/hold path for $label"}
    report_timing -from $from_clock -to $to_clock -delay_type max -max_paths 100 -file [file join $output_dir ${label}-setup-post-physopt.rpt]
    report_timing -from $from_clock -to $to_clock -delay_type min -max_paths 100 -file [file join $output_dir ${label}-hold-post-physopt.rpt]
    return [list [get_property SLACK $setup] [get_property SLACK $hold]]
}

set required_dcp_sha 879d19b56e7b50d3cb89c3c3ea0afe20df3f43c92b06af9424e3082fd34d19d0
set required_receipt_sha 0d0d67bf20b6f5a0d4c82703782bb272184811a1a14722ac887f1eb70fc72bfa
if {[string tolower $expected_dcp_sha] ne $required_dcp_sha || [sha256_file $synth_dcp] ne $required_dcp_sha} {error "A0005 post-synth DCP SHA mismatch"}
if {[string tolower $expected_receipt_sha] ne $required_receipt_sha || [sha256_file $synth_receipt] ne $required_receipt_sha} {error "A0005 platform synth receipt SHA mismatch"}
set receipt_fd [open $synth_receipt r]
set receipt_text [read $receipt_fd]
close $receipt_fd
foreach token [list \
    {"schema": "cnn-v10.5-a0005-half2x-fused-fastbufgdiv-platform-synth-only-v1"} \
    {"pass": true} \
    f8714065c490506f5e08b1738c8fe121270db2c66da9eb42d9674907102e0593 \
    ef373560fbb68e8719d5497b0d259b8a6dab734b2f88744f9d3505f8143af711 \
    19da3790f4593648 \
    {"effective_vlnv": "xilinx.com:hls:cnn_pipeline_v10:1.3"}] {
    if {[string first $token $receipt_text] < 0} {error "A0005 platform synth receipt lacks frozen binding: $token"}
}

# Record all accepted tool thread capacities, then run implementation at the
# requested supported cap of eight workers.  This nonproject invocation is the
# only implementation job.
set_param general.maxThreads 16
if {[get_param general.maxThreads] != 16} {error "general.maxThreads did not accept 16"}
set_param synth.maxThreads 8
if {[get_param synth.maxThreads] != 8} {error "synth.maxThreads did not accept 8"}
set_param general.maxThreads 8
if {[get_param general.maxThreads] != 8} {error "implementation maxThreads did not accept 8"}

open_checkpoint $synth_dcp
if {[get_property PART [current_design]] ne "xazu3eg-sfvc784-1-i"} {error "Unexpected target part"}
write_checkpoint -force [file join $output_dir a0005-opened-post-synth.dcp]

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
if {[get_property BUFGCE_DIVIDE $fast_buffer] != 1 || [get_property BUFGCE_DIVIDE $slow_buffer] != 2} {error "BUFGCE_DIV ratio mismatch"}
set fast_i [require_one [get_pins -quiet -of_objects $fast_buffer -filter {REF_PIN_NAME == I}] "fast divider I"]
set slow_i [require_one [get_pins -quiet -of_objects $slow_buffer -filter {REF_PIN_NAME == I}] "slow divider I"]
set root_net [require_one [get_nets -quiet -of_objects $fast_i] "fast divider root net"]
if {$root_net ne [require_one [get_nets -quiet -of_objects $slow_i] "slow divider root net"]} {error "BUFGCE_DIVs do not share one MMCM output"}
set root_driver [require_one [get_pins -quiet -leaf -of_objects $root_net -filter {DIRECTION == OUT}] "root clock driver"]
if {[get_property REF_PIN_NAME $root_driver] ne "CLKOUT0" || ![string match {MMCME*} [get_property REF_NAME [get_cells -of_objects $root_driver]]]} {error "BUFGCE_DIV root is not MMCM CLKOUT0"}

set fused_units [get_cells -quiet -hierarchical -filter {ORIG_REF_NAME == cnn_v10_pw_dsp16_half2x_fused_alu || REF_NAME == cnn_v10_pw_dsp16_half2x_fused_alu}]
if {[llength $fused_units] != 16} {error "Expected 16 fused half2x leaf units, found [llength $fused_units]"}
set fused_dsps [get_cells -quiet -hierarchical -filter {REF_NAME == DSP48E2 && NAME =~ *fused_half2x*}]
if {[llength $fused_dsps] != 128} {error "Expected 128 fused-leaf DSP48E2 cells, found [llength $fused_dsps]"}
set non_preg_dsps {}
foreach dsp $fused_dsps {if {[get_property PREG $dsp] != 1} {lappend non_preg_dsps $dsp}}
if {[llength $non_preg_dsps] != 0} {error "Fused DSP PREG gate failed: $non_preg_dsps"}
set unresolved [get_cells -quiet -hierarchical -filter {IS_BLACKBOX == 1 && REF_NAME != DSP48E2}]
if {[llength $unresolved] != 0} {error "Unresolved custom blackboxes: $unresolved"}

set constraints_before [file join $output_dir timing-constraints-before-place.xdc]
write_xdc -force -type timing -constraints valid $constraints_before
report_qor_suggestions -report_all_suggestions -file [file join $output_dir a0005-current-design-qor-suggestions.rpt]
write_qor_suggestions -force [file join $output_dir a0005-current-design-qor-suggestions.rqs]

# No historical RQS, LOC, pblock, or incremental reference is read here.  The
# first A0005 placement is a fresh baseline using only the current netlist.
opt_design -directive Explore
write_checkpoint -force [file join $output_dir a0005-fresh-post-opt.dcp]
place_design -directive Explore -net_delay_weight high
write_checkpoint -force [file join $output_dir a0005-fresh-post-place.dcp]
phys_opt_design -directive AggressiveExplore
set physopt_dcp [file join $output_dir a0005-fresh-post-physopt.dcp]
write_checkpoint -force $physopt_dcp

report_clocks -file [file join $output_dir clocks-post-physopt.rpt]
report_clock_interaction -file [file join $output_dir clock-interaction-post-physopt.rpt]
report_timing_summary -delay_type min_max -report_unconstrained -check_timing_verbose -file [file join $output_dir timing-summary-post-physopt.rpt]
set slow_slow [report_path_class slow200-to-slow200 $slow $slow $output_dir]
set fast_fast [report_path_class fast400-to-fast400 $fast $fast $output_dir]
set slow_fast [report_path_class slow200-to-fast400 $slow $fast $output_dir]
set fast_slow [report_path_class fast400-to-slow200 $fast $slow $output_dir]
report_pulse_width -file [file join $output_dir pulse-width-post-physopt.rpt]
report_exceptions -file [file join $output_dir timing-exceptions-post-physopt.rpt]
check_timing -verbose -file [file join $output_dir check-timing-post-physopt.rpt]
report_utilization -file [file join $output_dir utilization-post-physopt.rpt]
report_utilization -hierarchical -hierarchical_depth 12 -file [file join $output_dir utilization-hierarchical-post-physopt.rpt]
report_drc -file [file join $output_dir drc-post-physopt.rpt]
report_methodology -file [file join $output_dir methodology-post-physopt.rpt]
report_route_status -file [file join $output_dir route-status-post-physopt.rpt]
set congestion_report [file join $output_dir congestion-post-physopt.rpt]
report_design_analysis -congestion -file $congestion_report
report_qor_suggestions -report_all_suggestions -file [file join $output_dir qor-suggestions-post-physopt.rpt]

set master_after [require_clock $master_name 10.0 0 ""]
set fast_after [require_clock $fast_name 2.5 1 $master_name]
set slow_after [require_clock $slow_name 5.0 1 $fast_name]
set constraints_after [file join $output_dir timing-constraints-post-physopt.xdc]
write_xdc -force -type timing -constraints valid $constraints_after
set exceptions_before [timing_exception_commands $constraints_before]
set exceptions_after [timing_exception_commands $constraints_after]
set new_exception_count 0
foreach exception $exceptions_after {if {[lsearch -exact $exceptions_before $exception] < 0} {incr new_exception_count}}

set congestion_fd [open $congestion_report r]
set congestion_text [read $congestion_fd]
close $congestion_fd
set matched_congestion_windows 0
set maximum_congestion_level 0
set level5_or_worse_count 0
foreach line [split $congestion_text \n] {
    if {[regexp {^\|[ \t]+(North|South|East|West)[ \t]+\|[ \t]+(Global|Long|Short)[ \t]+\|[ \t]+([0-9]+)[ \t]+\|} $line -> direction type level]} {
        incr matched_congestion_windows
        if {$level > $maximum_congestion_level} {set maximum_congestion_level $level}
        if {$level >= 5} {incr level5_or_worse_count}
    }
}
if {$matched_congestion_windows == 0} {error "Congestion report contained no parseable windows"}
if {$new_exception_count != 0} {error "Placement introduced new timing exceptions"}

set setup [get_timing_paths -quiet -delay_type max -max_paths 1]
set hold [get_timing_paths -quiet -delay_type min -max_paths 1]
if {[llength $setup] != 1 || [llength $hold] != 1} {error "Missing global setup/hold path"}
set severe_drc [get_drc_violations -quiet -filter {SEVERITY == Error || SEVERITY == "Critical Warning"}]
set status [open [file join $output_dir a0005-fresh-place-status.rpt] w]
puts $status "status=A0005_FRESH_PLACE_COMPLETE"
puts $status "input_synth_dcp_sha256=[sha256_file $synth_dcp]"
puts $status "input_synth_receipt_sha256=[sha256_file $synth_receipt]"
puts $status "opened_post_synth_dcp_sha256=[sha256_file [file join $output_dir a0005-opened-post-synth.dcp]]"
puts $status "post_opt_dcp_sha256=[sha256_file [file join $output_dir a0005-fresh-post-opt.dcp]]"
puts $status "post_place_dcp_sha256=[sha256_file [file join $output_dir a0005-fresh-post-place.dcp]]"
puts $status "post_physopt_dcp_sha256=[sha256_file $physopt_dcp]"
puts $status "general_threads_supported=16"
puts $status "synth_threads_supported=8"
puts $status "implementation_threads_effective=[get_param general.maxThreads]"
puts $status "jobs=1"
puts $status "implementation_mode=fresh_nonincremental"
puts $status "historical_rqs_read=false"
puts $status "historical_exactloc_or_pblock_used=false"
puts $status "current_design_qor_suggestions_applied=false"
puts $status "opt_directive=Explore"
puts $status "place_directive=Explore"
puts $status "place_net_delay_weight=high"
puts $status "physopt_directive=AggressiveExplore"
puts $status "master_period_ns=[get_property PERIOD $master_after]"
puts $status "slow_period_ns=[get_property PERIOD $slow_after]"
puts $status "fast_period_ns=[get_property PERIOD $fast_after]"
puts $status "fused_half2x_unit_count=[llength $fused_units]"
puts $status "fused_dsp48e2_count=[llength $fused_dsps]"
puts $status "fused_dsp_preg1_count=[expr {[llength $fused_dsps] - [llength $non_preg_dsps]}]"
puts $status "unresolved_custom_blackbox_count=[llength $unresolved]"
puts $status "mmcm_m=[get_property CLKFBOUT_MULT_F $mmcm]"
puts $status "mmcm_d=[get_property DIVCLK_DIVIDE $mmcm]"
puts $status "mmcm_o_fast=[get_property CLKOUT0_DIVIDE_F $mmcm]"
puts $status "driver_job_bufgce_divide=[get_property BUFGCE_DIVIDE $slow_buffer]"
puts $status "pw_local_bufgce_divide=[get_property BUFGCE_DIVIDE $fast_buffer]"
puts $status "common_mmcm_root_net=$root_net"
puts $status "setup_wns_ns=[get_property SLACK $setup]"
puts $status "hold_whs_ns=[get_property SLACK $hold]"
foreach {label values} [list slow200_to_slow200 $slow_slow fast400_to_fast400 $fast_fast slow200_to_fast400 $slow_fast fast400_to_slow200 $fast_slow] {
    puts $status "path_class.$label.setup_slack_ns=[lindex $values 0]"
    puts $status "path_class.$label.hold_slack_ns=[lindex $values 1]"
}
puts $status "matched_congestion_windows=$matched_congestion_windows"
puts $status "maximum_congestion_level=$maximum_congestion_level"
puts $status "level5_or_worse_window_count=$level5_or_worse_count"
puts $status "severe_drc_count=[llength $severe_drc]"
puts $status "new_timing_exception_count=$new_exception_count"
puts $status "route_launched=false"
puts $status "bitstream_written=false"
puts $status "hardware_accessed=false"
close $status

puts "A0005_FRESH_PLACE_COMPLETE route=false post_physopt_dcp=$physopt_dcp"
close_design
exit 0
