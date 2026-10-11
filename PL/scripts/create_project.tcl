# Official Vivado Project Mode; source-only offline PL build.
set root [file normalize [file join [file dirname [info script]] ..]]
if {[version -short] ne "2026.1"} {error "Vivado 2026.1 required"}
set project_dir [file join $root project-final-008]
if {$argc > 0} {set project_dir [file normalize [lindex $argv 0]]}
# Each project compiles an immutable capture, including the BD connection recipe.
set source_root $root
if {$argc > 1} {set source_root [file normalize [lindex $argv 1]]}
set capture [file join $project_dir source_snapshot]
file mkdir $capture
foreach directory {rtl platform constraints} {
    if {[file exists $capture/$directory]} {error "Snapshot already exists; choose a new project directory: $capture"}
    file copy $source_root/$directory $capture/$directory
}
set report_dir [file join $root reports platform [file tail $project_dir]]
file mkdir $report_dir
create_project cnn_rtl $project_dir -part xazu3eg-sfvc784-1-i -force
set_property target_language Verilog [current_project]
set_property simulator_language Mixed [current_project]
set_property XPM_LIBRARIES {XPM_CDC XPM_MEMORY XPM_FIFO} [current_project]
set sources [concat [glob $capture/rtl/*.sv] [glob -nocomplain $capture/rtl/*.v] [glob $capture/platform/*.sv]]
set audit [open $report_dir/source_audit.txt w]
set hashes [open $capture/SHA256SUMS.txt w]
foreach source $sources {
    if {![string match "$capture/*" [file normalize $source]]} {error "Nonlocal source: $source"}
    set fd [open $source r]; set content [read $fd]; close $fd
    if {[regexp -nocase {CORE_GENERATION_INFO|hls_ip_|module[[:space:]]+cnn_pipeline_v10|synthesis[[:space:]]+translate_off} $content]} {error "Generated HLS / behavioral source rejected: $source"}
    puts $audit $source
    set digest [string trim [lindex [split [exec certutil -hashfile $source SHA256] \n] 1]]
    regsub -all { } $digest {} digest
    if {![regexp {^[a-fA-F0-9]{64}$} $digest]} {error "Cannot hash source $source"}
    puts $hashes "$digest  [string range $source [expr {[string length $capture]+1}] end]"
}
close $audit
foreach source [concat [glob $capture/constraints/*] [list $capture/platform/create_bd.tcl]] {
    set digest [string trim [lindex [split [exec certutil -hashfile $source SHA256] \n] 1]]
    regsub -all { } $digest {} digest
    if {![regexp {^[a-fA-F0-9]{64}$} $digest]} {error "Cannot hash $source"}
    puts $hashes "$digest  [string range $source [expr {[string length $capture]+1}] end]"
}
close $hashes
add_files -norecurse $sources
set_property file_type SystemVerilog [get_files *.sv]
set_property USED_IN_SIMULATION false [get_files $capture/rtl/cnn_rtl_bd.sv]
add_files -fileset constrs_1 -norecurse $capture/constraints/platform.xdc
update_compile_order -fileset sources_1
source $capture/platform/create_bd.tcl
foreach {prop expected} {CONFIG.MMCM_CLKFBOUT_MULT_F 12.000 CONFIG.MMCM_DIVCLK_DIVIDE 1 CONFIG.MMCM_CLKOUT0_DIVIDE_F 3.000} {
    set actual [get_property $prop [get_bd_cells clock_wiz]]
    if {abs(double($actual)-double($expected)) > 0.0005} {error "Clock Wizard ratio mismatch: $prop=$actual"}
}
set bd [get_files */cnn_rtl_platform.bd]
if {[llength $bd] != 1} {error "Platform BD not created"}
validate_bd_design
save_bd_design
generate_target all $bd
set wrapper [make_wrapper -files $bd -top]
add_files -norecurse $wrapper
set_property top cnn_rtl_platform_wrapper [current_fileset]
update_compile_order -fileset sources_1
foreach ip [get_ips] {
    if {[string match -nocase *hls* [get_property IPDEF $ip]]} {error "HLS IP prohibited: $ip"}
}
report_ip_status -file $report_dir/ip_status.rpt
write_bd_tcl -force $report_dir/actual_bd.tcl
puts "RTL_PLATFORM_CREATED [get_property NAME [current_project]]"
