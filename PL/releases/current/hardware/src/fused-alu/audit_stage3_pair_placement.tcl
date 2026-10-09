if {$argc != 2} {
    error "usage: audit_stage3_pair_placement.tcl <dcp> <report>"
}
set dcp_path [lindex $argv 0]
set report_path [lindex $argv 1]
open_checkpoint $dcp_path

set c0_cells [lsort [get_cells -hier -quiet -filter {REF_NAME == DSP48E2 && NAME =~ */fused_half2x/half_dot/chain0/stage3/dsp_i}]]
if {[llength $c0_cells] != 16} {
    error "expected 16 chain0 stage3 DSPs, got [llength $c0_cells]"
}

set fh [open $report_path w]
puts $fh "chain0_stage3_count=[llength $c0_cells]"
foreach c0 $c0_cells {
    set n0 [get_property NAME $c0]
    set n1 [string map {/chain0/ /chain1/} $n0]
    set c1 [get_cells -quiet $n1]
    if {[llength $c1] != 1} {
        close $fh
        error "expected one paired chain1 cell for $n0, got [llength $c1]"
    }
    set s0 [get_property LOC $c0]
    set s1 [get_property LOC $c1]
    set p0 [get_pins -quiet "$n0/P"]
    set cpin [get_pins -quiet "$n1/C"]
    set tps [get_timing_paths -quiet -delay_type max -from $p0 -to $cpin -max_paths 1 -nworst 1]
    if {[llength $tps] == 1} {
        set slack [get_property SLACK $tps]
        set datapath [get_property DATAPATH_DELAY $tps]
    } else {
        set slack NA
        set datapath NA
    }
    puts $fh "pair=$n0|$n1 loc0=$s0 loc1=$s1 preg0=[get_property PREG $c0] preg1=[get_property PREG $c1] slack=$slack datapath_delay=$datapath"
}
close $fh
close_design
exit 0
