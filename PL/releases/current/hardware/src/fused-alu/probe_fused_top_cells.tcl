if {$argc != 2} {error "usage: probe_fused_top_cells.tcl <dcp> <output>"}
lassign $argv dcp output
open_checkpoint [file normalize $dcp]
set fd [open [file normalize $output] w]
foreach c [get_cells -hierarchical -filter {NAME =~ *pw_dsp* || REF_NAME =~ *pw* || ORIG_REF_NAME =~ *pw*}] {
    puts $fd "[get_property NAME $c]|[get_property REF_NAME $c]|[get_property ORIG_REF_NAME $c]"
}
close $fd
close_design
