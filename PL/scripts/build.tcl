# Build and sign off one project. No hardware/PS initialization operations.
set_param general.maxThreads 8
set root [file normalize [file join [file dirname [info script]] ..]]
if {$argc == 0} {set argv [list $root/project-final-008]; set argc 1}
set project_dir [file normalize [lindex $argv 0]]
set synth_only [expr {$argc > 1 && [lindex $argv 1] eq "synth-only"}]
if {![file exists $project_dir/cnn_rtl.xpr]} {
    source $root/scripts/create_project.tcl
} else {open_project $project_dir/cnn_rtl.xpr}
proc verify_capture {capture} {
    set fd [open $capture/SHA256SUMS.txt];set hashes [read $fd];close $fd
    foreach line [split $hashes \n] {
        if {[string trim $line] eq ""} {continue}
        if {![regexp {^([a-fA-F0-9]{64})  (.+)$} $line -> expected relative]} {error "Malformed capture hash line"}
        set digest [string trim [lindex [split [exec certutil -hashfile $capture/$relative SHA256] \n] 1]]
        regsub -all { } $digest {} digest
        if {[string tolower $digest] ne [string tolower $expected]} {error "Snapshot modified: $relative"}
    }
}
set capture $project_dir/source_snapshot
if {![file exists $capture/SHA256SUMS.txt]} {
    if {!$synth_only} {error "Full signoff requires immutable source_snapshot; create a fresh project"}
    puts "DIAGNOSTIC_ONLY_LIVE_SOURCES"
} else {
    verify_capture $capture
}
set out [file join $root reports platform [file tail $project_dir]]
file mkdir $out
file delete -force $out/signoff.txt $out/route_receipt.json
if {[get_property NEEDS_REFRESH [get_runs synth_1]]} {reset_run synth_1}
if {![string match *Complete* [get_property STATUS [get_runs synth_1]]]} {
    launch_runs synth_1 -jobs 4
    wait_on_run synth_1
}
if {[get_property PROGRESS [get_runs synth_1]] ne "100%" || ![string match *Complete* [get_property STATUS [get_runs synth_1]]]} {error "Synthesis failed: [get_property STATUS [get_runs synth_1]]"}
if {[file exists $capture/SHA256SUMS.txt]} {verify_capture $capture}
open_run synth_1
write_checkpoint -force $out/synth.dcp
report_utilization -hierarchical -file $out/synth_utilization.rpt
report_utilization -file $out/synth_utilization_flat.rpt
if {$synth_only} {
    report_timing_summary -delay_type min_max -report_unconstrained -file $out/synth_timing_summary.rpt
    report_timing -delay_type max -max_paths 10 -file $out/synth_worst_setup.rpt
    foreach {label period_from period_to} {slow_slow 5.0 5.0 slow_fast 5.0 2.5 fast_slow 2.5 5.0 fast_fast 2.5 2.5} {
        set from {}; set to {}
        foreach clock [get_clocks] {
            set period [get_property PERIOD $clock]
            if {abs($period-$period_from)<0.01} {lappend from $clock}
            if {abs($period-$period_to)<0.01} {lappend to $clock}
        }
        if {[llength $from] == 0 || [llength $to] == 0} {error "Missing synthesis clock group: $label"}
        report_timing -from $from -to $to -delay_type max -max_paths 10 -file $out/synth_${label}_setup.rpt
    }
    report_cdc -details -file $out/synth_cdc.rpt
    puts "RTL_SYNTHESIS_COMPLETE_RESOURCE_AUDIT_REQUIRED"
    close_project
    exit 0
}
set fd [open $out/synth_utilization_flat.rpt];set usage [read $fd];close $fd
foreach {label pattern capacity} {
    LUT {\| CLB LUTs\*? +\| +([0-9]+)} 70560
    FF {\| CLB Registers +\| +([0-9]+)} 141120
    BRAM36_equiv {\| Block RAM Tile +\| +([0-9]+(?:\.[0-9]+)?)} 216
    DSP {\| DSPs +\| +([0-9]+)} 360
} {
    if {![regexp $pattern $usage -> count] || $count > $capacity} {error "Device resource fit failed: $label $count/$capacity"}
}
close_design
if {[get_property STRATEGY [get_runs impl_1]] ne "Vivado Implementation Defaults"} {
    set_property STRATEGY {Vivado Implementation Defaults} [get_runs impl_1]
}
set_property STEPS.PHYS_OPT_DESIGN.IS_ENABLED true [get_runs impl_1]
set_property STEPS.POST_ROUTE_PHYS_OPT_DESIGN.IS_ENABLED true [get_runs impl_1]
set_property STEPS.POST_ROUTE_PHYS_OPT_DESIGN.ARGS.DIRECTIVE AggressiveExplore [get_runs impl_1]
set implementation_step {phys_opt_design (Post-Route)}
if {[get_property NEEDS_REFRESH [get_runs impl_1]]} {reset_run impl_1}
if {![string match "*${implementation_step}*Complete*" [get_property STATUS [get_runs impl_1]]] && ![string match {*write_bitstream*Complete*} [get_property STATUS [get_runs impl_1]]]} {
    launch_runs impl_1 -to_step $implementation_step -jobs 4
    wait_on_run impl_1
}
if {[get_property PROGRESS [get_runs impl_1]] ne "100%" || ![string match *Complete* [get_property STATUS [get_runs impl_1]]]} {error "Implementation failed: [get_property STATUS [get_runs impl_1]]"}
open_run impl_1
update_timing
write_checkpoint -force $out/routed.dcp
report_utilization -hierarchical -file $out/routed_utilization_hierarchical.rpt
report_utilization -file $out/routed_utilization.rpt
set dsp_fd [open $out/dsp_register_audit.csv w]
puts $dsp_fd "cell,clock,AREG,BREG,CREG,MREG,PREG"
set pw_dsp_count 0;set pw_preg1_count 0
foreach dsp [get_cells -hier -filter {REF_NAME == DSP48E2}] {
    set name [get_property NAME $dsp]
    set clock [get_clocks -of_objects [get_pins $dsp/CLK]]
    set row [list $name $clock]
    foreach prop {AREG BREG CREG MREG PREG} {lappend row [get_property $prop $dsp]}
    puts $dsp_fd [join $row ,]
    if {[string match {*half_dot*} $name]} {
        incr pw_dsp_count
        if {[get_property PREG $dsp] == 1} {incr pw_preg1_count}
    }
}
close $dsp_fd
set dir_fd [open $out/implementation_settings.txt w]
foreach prop {STRATEGY STEPS.OPT_DESIGN.ARGS.DIRECTIVE STEPS.PLACE_DESIGN.ARGS.DIRECTIVE STEPS.PHYS_OPT_DESIGN.ARGS.DIRECTIVE STEPS.ROUTE_DESIGN.ARGS.DIRECTIVE STEPS.POST_ROUTE_PHYS_OPT_DESIGN.ARGS.DIRECTIVE} {
    puts $dir_fd "$prop=[get_property $prop [get_runs impl_1]]"
}
puts $dir_fd "pw_dsp_count=$pw_dsp_count; pw_preg1_count=$pw_preg1_count; native retiming allowed; inspect runme.log transformations"
close $dir_fd
report_timing_summary -delay_type min_max -report_unconstrained -check_timing_verbose -file $out/timing_summary.rpt
report_pulse_width -file $out/pulse_width.rpt
report_clock_interaction -file $out/clock_interaction.rpt
report_clocks -file $out/clocks.rpt
report_exceptions -file $out/exceptions.rpt
write_xdc -force -type timing -constraints valid $out/timing_constraints.xdc
set fd [open $out/timing_constraints.xdc];set constraints [read $fd];close $fd
set scope ""
set allowed_reset_exceptions 0
foreach line [split $constraints \n] {
    set line [string trim $line]
    if {[regexp {^current_instance(?: -quiet)?(?: (.+))?$} $line -> instance]} {set scope $instance}
    if {![regexp {^(set_false_path|set_multicycle_path|set_max_delay|set_min_delay|set_clock_groups|set_disable_timing)([ \t]|$)} $line -> command]} {continue}
    if {$command ne "set_false_path"} {error "Unapproved timing exception: $line"}
    set standard_reset_scope [regexp {/(data_dwidth|platform_reset|core_reset|fast_core_reset|shutdown_[0-5])/} $scope]
    set standard_reset_target [expr {
        [regexp {^set_false_path -through \[get_ports -scoped_to_current_instance -no_traverse src_arst\]$} $line] ||
        [regexp {^set_false_path -to \[get_cells \{syncstages_ff_reg\[0\]\}\]$} $line]
    }]
    if {!$standard_reset_scope || !$standard_reset_target} {error "Unapproved false-path scope $scope: $line"}
    incr allowed_reset_exceptions
}
set fd [open $out/exception_review.txt w]
puts $fd "allowed_standard_IP_reset_exceptions=$allowed_reset_exceptions; unapproved_data_or_clock_exceptions=0"
close $fd
report_cdc -details -file $out/cdc.rpt
set fd [open $out/cdc.rpt];set cdc_text [read $fd];close $fd
if {![string match {*All paths are Safely Timed.*} $cdc_text]} {
    error "CDC requires explicit path-by-path review; report is not safely timed"
}
set fd [open $out/cdc_review.txt w]
puts $fd "unsafe_reported_paths=0; all clocks safely timed; check_timing and four related-clock groups also required"
close $fd
report_drc -ruledecks default -no_waivers -file $out/drc.rpt
report_route_status -file $out/route_status.rpt
check_timing -verbose -file $out/check_timing.rpt
array set class_slack {}
set slow [get_clocks -of_objects [get_pins -hier -filter {NAME =~ */half2x_clock_tree/inst/driver_job_bufgce_div/O}]]
set fast [get_clocks -of_objects [get_pins -hier -filter {NAME =~ */half2x_clock_tree/inst/pw_local_bufgce_div/O}]]
# Resolve actual handwritten primitive names without assuming clock labels.
if {[llength $slow] == 0 || [llength $fast] == 0} {
    set slow {}; set fast {}
    foreach clock [get_clocks] {
        set period [get_property PERIOD $clock]
        if {abs($period-5.0)<0.01} {lappend slow $clock}
        if {abs($period-2.5)<0.01} {lappend fast $clock}
    }
}
if {[llength $slow] == 0 || [llength $fast] == 0} {error "200/400 MHz related clocks missing"}
foreach {label from to} [list slow_slow $slow $slow slow_fast $slow $fast fast_slow $fast $slow fast_fast $fast $fast] {
    report_timing -from $from -to $to -delay_type min_max -max_paths 20 -file $out/timing_${label}.rpt
}
foreach {label from to} [list slow_slow $slow $slow slow_fast $slow $fast fast_slow $fast $slow fast_fast $fast $fast] {
    foreach delay {max min} {
        set paths [get_timing_paths -quiet -from $from -to $to -delay_type $delay -max_paths 1]
        if {[llength $paths] != 1} {error "Missing related clock path: $label $delay"}
        foreach path $paths {
            set class_slack(${label}_${delay}) [get_property SLACK $path]
            if {[get_property SLACK $path] < 0} {error "Related clock timing failed: $label $delay"}
        }
    }
}
foreach delay {max min} {
    set paths [get_timing_paths -quiet -delay_type $delay -max_paths 1]
    if {[llength $paths] != 1 || [get_property SLACK $paths] < 0} {error "Global $delay timing failure"}
}
set fd [open $out/pulse_width.rpt];set pulse [read $fd];close $fd
set checks 0
foreach line [split $pulse \n] {
    if {[regexp {[ \t](-?[0-9]+\.[0-9]+)[ \t]+(-?[0-9]+\.[0-9]+)[ \t]+(-?[0-9]+\.[0-9]+)[ \t]+[A-Za-z0-9_/-]+[ \t]+} $line -> required actual slack]} {
        incr checks
        if {$slack < 0} {error "Pulse-width failure: $slack"}
    }
}
if {$checks == 0} {error "No parseable pulse-width checks"}
set fd [open $out/check_timing.rpt];set timing_check [read $fd];close $fd
set categories 0
set check_timing_issues 0
foreach line [split $timing_check \n] {
    if {[regexp {^[0-9]+\. checking [^(]+\(([0-9]+)\)} [string trim $line] -> count]} {
        incr categories
        incr check_timing_issues $count
        if {$count != 0} {error "check_timing issue: $line"}
    }
}
if {$categories < 12} {error "Incomplete check_timing report"}
set violations [get_drc_violations -quiet -filter {SEVERITY == Error || SEVERITY == "Critical Warning"}]
if {[llength $violations]} {error "DRC violations: $violations"}
set fd [open $out/route_status.rpt];set route [read $fd];close $fd
foreach line [split $route \n] {
    foreach {route_label label} {routable_nets {routable nets} fully_routed_nets {fully routed nets} routing_errors {nets with routing errors} explicit_unrouted {unrouted nets} partially_routed {partially routed nets}} {
        if {[string first "# of $label" $line] >= 0} {
            if {[info exists route_counts($route_label)]} {error "Duplicate route count: $label"}
            set pattern [format {^[ \t]*# of %s\.+[ \t]*:[ \t]*([0-9]+)[ \t]*:[ \t\r]*$} $label]
            if {![regexp $pattern $line -> count]} {error "Malformed route count: $line"}
            scan $count %d count
            set route_counts($route_label) $count
        }
    }
}
foreach required {routable_nets fully_routed_nets routing_errors} {
    if {![info exists route_counts($required)]} {error "Missing route count: $required"}
}
set route_counts(unrouted_nets) [expr {$route_counts(routable_nets)-$route_counts(fully_routed_nets)}]
if {$route_counts(unrouted_nets) < 0} {error "Fully routed count exceeds routable count"}
if {[info exists route_counts(explicit_unrouted)] && $route_counts(explicit_unrouted) != $route_counts(unrouted_nets)} {error "Contradictory unrouted count"}
if {[info exists route_counts(partially_routed)] && $route_counts(partially_routed) > $route_counts(unrouted_nets)} {error "Contradictory partially routed count"}
if {$route_counts(unrouted_nets) != 0 || $route_counts(routing_errors) != 0} {error "Route incomplete or routing errors"}
if {[llength [get_debug_cores -quiet]]} {error "Unexpected debug cores; baseline is release-no-ila"}
set fd [open $out/timing_summary.rpt];set timing [read $fd];close $fd
if {[regexp -nocase {There are ([1-9][0-9]*) (register/latch pins with no clock|internal endpoints which are not constrained|unconstrained internal endpoints)} $timing]} {error "Unconstrained endpoints"}
verify_capture $capture
set fd [open $out/signoff.txt w];puts $fd "PASS: routed setup/hold/pulse, four related-clock groups, DRC and route status";close $fd



# Machine-readable receipt only after every signoff gate and post-run source hash.
proc sha256_file {path} {
    set digest [string trim [lindex [split [exec certutil -hashfile $path SHA256] \n] 1]]
    regsub -all { } $digest {} digest
    if {![regexp {^[a-fA-F0-9]{64}$} $digest]} {error "Cannot hash artifact $path"}
    return [string tolower $digest]
}
proc json_string {value} {
    if {[regexp {["\\\n\r]} $value]} {error "Unexpected JSON control character in $value"}
    return [format {"%s"} $value]
}
proc resource_count {text pattern} {
    if {![regexp $pattern $text -> count]} {error "Resource count missing: $pattern"}
    return $count
}
set fd [open $out/routed_utilization.rpt];set usage [read $fd];close $fd
set lut [resource_count $usage {\| CLB LUTs\*? +\| +([0-9]+)}]
set ff [resource_count $usage {\| CLB Registers +\| +([0-9]+)}]
set bram [resource_count $usage {\| Block RAM Tile +\| +([0-9]+(?:\.[0-9]+)?)}]
set dsp [resource_count $usage {\| DSPs +\| +([0-9]+)}]
if {$lut > 51334 || $ff > 87644 || $bram > 162 || $dsp > 214} {error "Post-route resource baseline exceeded: LUT=$lut FF=$ff BRAM=$bram DSP=$dsp"}
if {$allowed_reset_exceptions != 9} {error "Expected exactly nine standard-IP reset exceptions"}
set summary_row {};set row_state 0
foreach line [split $timing \n] {
    if {$row_state == 0 && [string match {*WNS(ns)*TNS(ns)*} $line]} {set row_state 1;continue}
    if {$row_state == 1} {set row_state 2;continue}
    if {$row_state == 2} {set summary_row [regexp -all -inline {\S+} $line];break}
}
if {[llength $summary_row] != 12} {error "Cannot parse global timing summary"}
lassign $summary_row wns tns setup_failing setup_total whs ths hold_failing hold_total wpws tpws pulse_failing pulse_total
if {$tns != 0 || $ths != 0 || $setup_failing != 0 || $hold_failing != 0 || $pulse_failing != 0 || $wns < 0 || $whs < 0 || $wpws < 0} {error "Global timing totals not clean"}
set relative_project [string range $project_dir [expr {[string length $root]+1}] end]
set fields {}
lappend fields {  "status": "ROUTED_SIGNOFF_PASS"} {  "stage": "post_route"} {  "part": "xazu3eg-sfvc784-1-i"}
lappend fields [format {  "project_relative": %s} [json_string $relative_project]]
lappend fields [format {  "source_snapshot_sha256": "%s"} [sha256_file $capture/SHA256SUMS.txt]]
lappend fields [format {  "source_snapshot_SHA256SUMS_sha256": "%s"} [sha256_file $capture/SHA256SUMS.txt]]
lappend fields [format {  "route_dcp_sha256": "%s"} [sha256_file $out/routed.dcp]]
lappend fields [format {  "resources": {"lut": %s, "ff": %s, "bram36_equivalent": %s, "dsp": %s}} $lut $ff $bram $dsp]
lappend fields [format {  "timing": {"wns_ns": %s, "tns_ns": %s, "whs_ns": %s, "ths_ns": %s, "wpws_ns": %s}} $wns $tns $whs $ths $wpws]
lappend fields [format {  "route": {"unrouted_nets": %s, "routing_errors": %s}} $route_counts(unrouted_nets) $route_counts(routing_errors)]
lappend fields {  "checks": {"check_timing": true, "cdc": true, "drc": true, "related_clocks": true, "exceptions": true}}
set drc_errors [llength [get_drc_violations -quiet -filter {SEVERITY == Error}]]
set drc_critical [llength [get_drc_violations -quiet -filter {SEVERITY == "Critical Warning"}]]
set debug_count [llength [get_debug_cores -quiet]]
lappend fields [format {  "counts": {"check_timing_categories": %s, "check_timing_issues": %s, "drc_errors": %s, "drc_critical_warnings": %s, "cdc_unsafe_paths": 0, "allowed_reset_exceptions": %s, "debug_cores": %s, "unconstrained_internal_endpoints": 0, "unapproved_exceptions": 0, "pw_dsp_count": %s, "pw_preg1_count": %s}} $categories $check_timing_issues $drc_errors $drc_critical $allowed_reset_exceptions $debug_count $pw_dsp_count $pw_preg1_count]
set groups {}
foreach label {slow_slow slow_fast fast_slow fast_fast} {
    lappend groups [format {    "%s": {"setup_ns": %s, "hold_ns": %s}} $label $class_slack(${label}_max) $class_slack(${label}_min)]
}
lappend fields [format {  "related_clock_groups": {
%s
  }} [join $groups ",\n"]]
lappend fields [format {  "impl_run": {"status": %s, "progress": %s, "strategy": %s, "post_route_directive": %s, "final_step": "phys_opt_design (Post-Route)"}} [json_string [get_property STATUS [get_runs impl_1]]] [json_string [get_property PROGRESS [get_runs impl_1]]] [json_string [get_property STRATEGY [get_runs impl_1]]] [json_string [get_property STEPS.POST_ROUTE_PHYS_OPT_DESIGN.ARGS.DIRECTIVE [get_runs impl_1]]]]
set artifacts {}
foreach {role filename} {
    route_dcp routed.dcp utilization routed_utilization.rpt timing timing_summary.rpt route_status route_status.rpt
    check_timing check_timing.rpt cdc cdc.rpt drc drc.rpt pulse_width pulse_width.rpt clocks clocks.rpt
    exceptions exceptions.rpt exception_review exception_review.txt cdc_review cdc_review.txt
    slow_slow timing_slow_slow.rpt slow_fast timing_slow_fast.rpt fast_slow timing_fast_slow.rpt fast_fast timing_fast_fast.rpt
    constraints timing_constraints.xdc signoff signoff.txt
    dsp_registers dsp_register_audit.csv implementation_settings implementation_settings.txt
    build_script build.tcl.executed.tcl
} {
    set path $out/$filename
    if {![file isfile $path]} {error "Missing signoff artifact $path"}
    lappend artifacts [format {    {"role": %s, "path": %s, "sha256": "%s"}} [json_string $role] [json_string [string range $path [expr {[string length $root]+1}] end]] [sha256_file $path]]
}
lappend fields [format {  "artifacts": [
%s
  ]} [join $artifacts ",\n"]]
set fd [open $out/route_receipt.json w]
puts $fd [format "{\n%s\n}" [join $fields ",\n"]]
close $fd
puts "RTL_ROUTED_SIGNOFF_RECEIPT $out/route_receipt.json"


# Optional file exports after routed signoff; no hardware connection or PS init.
set export_status [open $out/file_exports.txt w]
if {[catch {write_bitstream -force $out/cnn_rtl.bit} export_error]} {
    puts $export_status "bitstream=FAILED; $export_error"
} else {
    puts $export_status "bitstream=CREATED"
    if {[catch {
        if {[get_property STATUS [get_runs impl_1]] ne "write_bitstream Complete!"} {
            launch_runs impl_1 -to_step write_bitstream -jobs 4
            wait_on_run impl_1
        }
        if {[get_property PROGRESS [get_runs impl_1]] ne "100%" || [get_property STATUS [get_runs impl_1]] ne "write_bitstream Complete!"} {error "Native bitstream run incomplete"}
        set native_bit [file join [get_property DIRECTORY [get_runs impl_1]] [get_property TOP [get_filesets sources_1]].bit]
        if {![file isfile $native_bit] || [file size $native_bit] <= 0} {error "Native bitstream file missing or empty"}
        file copy -force $native_bit $out/cnn_rtl.bit
        write_hw_platform -fixed -include_bit -force -file $out/cnn_rtl.xsa
    } xsa_error]} {
        puts $export_status "xsa=FAILED; $xsa_error"
    } else {puts $export_status "xsa=CREATED"}
}
close $export_status

