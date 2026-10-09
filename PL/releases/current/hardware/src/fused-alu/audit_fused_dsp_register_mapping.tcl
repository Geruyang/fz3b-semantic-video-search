# Read-only comparison of the fused half2x DSP register mapping across saved
# implementation checkpoints.  No design mutation or checkpoint write occurs.

if {$argc < 3 || ($argc % 2) != 1} {
    error "usage: audit_fused_dsp_register_mapping.tcl <output_file> <label> <dcp>..."
}
set output_file [file normalize [lindex $argv 0]]
set fd [open $output_file w]

proc safe_prop {object property} {
    if {[catch {get_property $property $object} value]} {return "NA"}
    if {$value eq ""} {return "NA"}
    return $value
}

for {set index 1} {$index < $argc} {incr index 2} {
    set label [lindex $argv $index]
    set dcp [file normalize [lindex $argv [expr {$index + 1}]]]
    if {![file isfile $dcp]} {error "Missing DCP: $dcp"}
    open_checkpoint $dcp
    puts $fd "BEGIN_STAGE label=$label dcp=$dcp"

    set chain0 [lsort [get_cells -quiet -hier -filter {REF_NAME == DSP48E2 && NAME =~ *fused_half2x/half_dot/chain0/stage3/dsp_i}]]
    set chain1 [lsort [get_cells -quiet -hier -filter {REF_NAME == DSP48E2 && NAME =~ *fused_half2x/half_dot/chain1/stage3/dsp_i}]]
    set value_regs [lsort [get_cells -quiet -hier -filter {NAME =~ *fused_half2x/half_dot/chain0/value3_d3_reg*}]]
    puts $fd "COUNTS chain0_stage3=[llength $chain0] chain1_stage3=[llength $chain1] chain0_value3_regs=[llength $value_regs]"
    foreach {group cells} [list chain0 $chain0 chain1 $chain1] {
        foreach cell $cells {
            puts $fd "DSP group=$group name=$cell AREG=[safe_prop $cell AREG] BREG=[safe_prop $cell BREG] ACASCREG=[safe_prop $cell ACASCREG] BCASCREG=[safe_prop $cell BCASCREG] MREG=[safe_prop $cell MREG] CREG=[safe_prop $cell CREG] PREG=[safe_prop $cell PREG] OPMODEREG=[safe_prop $cell OPMODEREG] LOC=[safe_prop $cell LOC] IS_LOC_FIXED=[safe_prop $cell IS_LOC_FIXED]"
        }
    }
    foreach cell $value_regs {
        puts $fd "VALUE_REG name=$cell ref=[safe_prop $cell REF_NAME] LOC=[safe_prop $cell LOC] IS_LOC_FIXED=[safe_prop $cell IS_LOC_FIXED]"
    }
    puts $fd "END_STAGE label=$label"
    close_design
}
close $fd
puts "FUSED_DSP_REGISTER_AUDIT_PASS output=$output_file"
exit 0
