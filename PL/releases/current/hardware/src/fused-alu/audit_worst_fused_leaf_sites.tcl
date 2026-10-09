if {$argc != 2} {
    error "usage: audit_worst_fused_leaf_sites.tcl <dcp> <report>"
}
set dcp_path [lindex $argv 0]
set report_path [lindex $argv 1]
open_checkpoint $dcp_path

set leaf_pat {*/p_anonymous_namespace_pointwise_pair_expand_1_U0/*/grp_cnn_v10_pw_dsp16_fu_999/fused_half2x/half_dot/*/stage*/dsp_i}
set leaf_dsps [lsort [get_cells -hier -quiet -filter "REF_NAME == DSP48E2 && NAME =~ $leaf_pat"]]
if {[llength $leaf_dsps] != 8} {
    error "expected 8 DSPs in worst fused leaf, got [llength $leaf_dsps]"
}

set fh [open $report_path w]
puts $fh "worst_leaf_dsp_count=[llength $leaf_dsps]"
foreach c $leaf_dsps {
    set loc [get_property LOC $c]
    set site [get_sites -quiet $loc]
    set cr [get_clock_regions -quiet -of_objects $site]
    puts $fh "cell=[get_property NAME $c] loc=$loc clock_region=$cr preg=[get_property PREG $c] areg=[get_property AREG $c] breg=[get_property BREG $c] mreg=[get_property MREG $c]"
}

foreach cr [lsort -unique [get_clock_regions -quiet -of_objects [get_sites -quiet -of_objects $leaf_dsps]]] {
    puts $fh "clock_region=$cr"
}

set nearby [lsort [get_cells -hier -quiet -filter {REF_NAME == DSP48E2 && LOC =~ DSP48E2_X0Y* || REF_NAME == DSP48E2 && LOC =~ DSP48E2_X1Y*}]]
foreach c $nearby {
    set loc [get_property LOC $c]
    if {[regexp {DSP48E2_X[01]Y([0-9]+)} $loc -> y] && $y >= 15 && $y <= 55} {
        puts $fh "nearby=$loc cell=[get_property NAME $c]"
    }
}
close $fh
close_design
exit 0
