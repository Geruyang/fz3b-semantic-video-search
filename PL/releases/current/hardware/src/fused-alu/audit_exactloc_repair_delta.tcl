if {$argc != 3} {
    error "usage: audit_exactloc_repair_delta.tcl <baseline_dcp> <candidate_dcp> <report>"
}
lassign $argv baseline_dcp candidate_dcp report_path

proc fused_dsp_cells {} {
    return [lsort [get_cells -quiet -hier -filter {REF_NAME == DSP48E2 && NAME =~ *fused_half2x/half_dot/chain*/stage*/dsp_i}]]
}
proc is_target_leaf {name} {
    return [string match "*/p_anonymous_namespace_pointwise_pair_expand_1_U0/*/grp_cnn_v10_pw_dsp16_fu_999/fused_half2x/*" $name]
}

open_checkpoint $baseline_dcp
set baseline_cells [fused_dsp_cells]
if {[llength $baseline_cells] != 128} {error "Expected 128 fused DSPs in baseline, got [llength $baseline_cells]"}
array set baseline_loc {}
foreach cell $baseline_cells {
    set baseline_loc([get_property NAME $cell]) [get_property LOC $cell]
}
close_design

open_checkpoint $candidate_dcp
set candidate_cells [fused_dsp_cells]
if {[llength $candidate_cells] != 128} {error "Expected 128 fused DSPs in candidate, got [llength $candidate_cells]"}

set target_moves {}
set non_target_moves {}
set duplicate_sites {}
array set site_owner {}
set preg_one_count 0
foreach cell $candidate_cells {
    set name [get_property NAME $cell]
    set loc [get_property LOC $cell]
    if {$loc eq ""} {error "Candidate fused DSP is unplaced: $name"}
    if {[info exists site_owner($loc)]} {
        lappend duplicate_sites "$loc:$site_owner($loc):$name"
    } else {
        set site_owner($loc) $name
    }
    if {[get_property PREG $cell] == 1} {incr preg_one_count}
    if {![info exists baseline_loc($name)]} {error "Candidate fused DSP is absent from baseline: $name"}
    if {$baseline_loc($name) ne $loc} {
        set movement "$name old=$baseline_loc($name) new=$loc"
        if {[is_target_leaf $name]} {
            lappend target_moves $movement
        } else {
            lappend non_target_moves $movement
        }
    }
}

set c0_cells [lsort [get_cells -hier -quiet -filter {REF_NAME == DSP48E2 && NAME =~ */fused_half2x/half_dot/chain0/stage3/dsp_i}]]
if {[llength $c0_cells] != 16} {error "Expected 16 chain0 stage3 DSPs, got [llength $c0_cells]"}
set pair_lines {}
set pair_negative_count 0
set pair_missing_count 0
foreach c0 $c0_cells {
    set n0 [get_property NAME $c0]
    set n1 [string map {/chain0/ /chain1/} $n0]
    set c1 [get_cells -quiet $n1]
    if {[llength $c1] != 1} {error "Expected one paired chain1 cell for $n0"}
    set p0 [get_pins -quiet "$n0/P"]
    set cpin [get_pins -quiet "$n1/C"]
    set paths [get_timing_paths -quiet -delay_type max -from $p0 -to $cpin -max_paths 1 -nworst 1]
    if {[llength $paths] != 1} {
        incr pair_missing_count
        lappend pair_lines "pair=$n0|$n1 loc0=[get_property LOC $c0] loc1=[get_property LOC $c1] slack=NA datapath_delay=NA"
    } else {
        set slack [get_property SLACK $paths]
        if {$slack < 0} {incr pair_negative_count}
        lappend pair_lines "pair=$n0|$n1 loc0=[get_property LOC $c0] loc1=[get_property LOC $c1] slack=$slack datapath_delay=[get_property DATAPATH_DELAY $paths]"
    }
}

set fh [open $report_path w]
puts $fh "status=EXACTLOC_REPAIR_DELTA_AUDIT_COMPLETE"
puts $fh "baseline_fused_dsp_count=[llength $baseline_cells]"
puts $fh "candidate_fused_dsp_count=[llength $candidate_cells]"
puts $fh "candidate_preg1_count=$preg_one_count"
puts $fh "target_moved_dsp_count=[llength $target_moves]"
puts $fh "non_target_moved_dsp_count=[llength $non_target_moves]"
puts $fh "duplicate_site_count=[llength $duplicate_sites]"
puts $fh "pair_count=[llength $pair_lines]"
puts $fh "pair_negative_count=$pair_negative_count"
puts $fh "pair_missing_count=$pair_missing_count"
foreach movement $target_moves {puts $fh "target_move=$movement"}
foreach movement $non_target_moves {puts $fh "non_target_move=$movement"}
foreach duplicate $duplicate_sites {puts $fh "duplicate_site=$duplicate"}
foreach line $pair_lines {puts $fh $line}
close $fh

if {$preg_one_count != 128 || [llength $target_moves] != 8 || [llength $non_target_moves] != 0 ||
    [llength $duplicate_sites] != 0 || $pair_negative_count != 0 || $pair_missing_count != 0} {
    error "Exact-location delta audit gate failed"
}
close_design
exit 0
