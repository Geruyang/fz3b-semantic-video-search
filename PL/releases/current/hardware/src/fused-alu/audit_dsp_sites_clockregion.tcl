if {$argc != 3} {
    error "usage: audit_dsp_sites_clockregion.tcl <dcp> <clock_region> <report>"
}

set dcp_path [lindex $argv 0]
set clock_region_name [lindex $argv 1]
set report_path [lindex $argv 2]

open_checkpoint $dcp_path
set cr [get_clock_regions -quiet $clock_region_name]
if {[llength $cr] == 0 && [string match {CLOCKREGION_*} $clock_region_name]} {
    set cr [get_clock_regions -quiet [string range $clock_region_name 12 end]]
}
if {[llength $cr] != 1} {
    error "expected one clock region named $clock_region_name, got [llength $cr]"
}

set dsp_sites [lsort -dictionary [get_sites -quiet -of_objects $cr -filter {SITE_TYPE =~ DSP*}]]
if {[llength $dsp_sites] == 0} {
    error "no DSP sites found in $clock_region_name"
}

set fh [open $report_path w]
puts $fh "clock_region=$clock_region_name"
puts $fh "dsp_site_count=[llength $dsp_sites]"
foreach site $dsp_sites {
    set occupants [get_cells -quiet -of_objects $site]
    if {[llength $occupants] == 0} {
        puts $fh "site=$site occupied=false"
    } else {
        set names {}
        foreach cell $occupants {
            lappend names [get_property NAME $cell]
        }
        puts $fh "site=$site occupied=true cells=[join [lsort $names] ,]"
    }
}
close $fh
close_design
exit 0
