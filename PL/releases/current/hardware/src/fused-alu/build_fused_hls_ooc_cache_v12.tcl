# Official Vivado IP OOC synthesis and remote-cache export for fused half2x HLS IP v1.2.
if {$argc != 7 && $argc != 8} {error "usage: build_fused_hls_ooc_cache_v12.tcl INPUT_IP WORK_DIR EVIDENCE_DIR CACHE_DIR OLD_CACHE_ID V11_CACHE_ID RTL_DIGEST ?IDENTITY_ONLY?"}
lassign $argv input_ip work_dir evidence_dir cache_dir old_cache_id v11_cache_id rtl_digest identity_only
if {$identity_only eq {}} {set identity_only 0}
foreach n {input_ip work_dir evidence_dir cache_dir} {set $n [file normalize [set $n]]}
file mkdir $work_dir; file mkdir $evidence_dir; file mkdir $cache_dir
set pkg [file join $work_dir hls-ip-fused-cache-identity]
file delete -force $pkg
file copy -force $input_ip $pkg
set component [file join $pkg component.xml]
if {![file isfile $component]} {error "missing component.xml: $component"}

# Use IP Packager for the legal IP-XACT identity change.  Version 1.2 is
# intentionally distinct from the historical 1.0 and the rejected 1.1 cache.
create_project -in_memory fused_cache_identity -part xazu3eg-sfvc784-1-i
ipx::open_core $component
set core [ipx::current_core]
set old_revision [get_property core_revision $core]
set new_revision [expr {wide($old_revision) + 1}]
set_property core_revision $new_revision $core
set_property version 1.2 $core
set_property description "cnn_v10 fused half2x v1.2; canonical_rtl_digest=$rtl_digest; clocks=ap_clk_5ns,pw_fast_clk_2p5ns" $core
ipx::save_core $core
close_project

# The generated HLS package only constrained ap_clk.  The fused leaf has a
# real 400 MHz fast domain, so freeze two phase-aligned primary OOC clocks.
# Do not add clock groups, false paths, or other timing exceptions here.
set ooc_xdc [file join $pkg constraints cnn_pipeline_v10_ooc.xdc]
if {![file isfile $ooc_xdc]} {error "missing OOC XDC: $ooc_xdc"}
set xfh [open $ooc_xdc w]
puts $xfh {# Fused half2x OOC clock contract: phase-aligned 200 MHz / 400 MHz.}
puts $xfh {create_clock -name ap_clk -period 5.000 [get_ports ap_clk]}
puts $xfh {create_clock -name pw_fast_clk -period 2.500 [get_ports pw_fast_clk]}
close $xfh
file copy -force $ooc_xdc [file join $evidence_dir cnn_pipeline_v10_ooc_effective.xdc]

proc make_project_and_ip {project_dir package_dir} {
    file delete -force $project_dir
    create_project fused_hls_ooc $project_dir -part xazu3eg-sfvc784-1-i -force
    set_property target_language Verilog [current_project]
    set_property ip_repo_paths [list [file dirname $package_dir]] [current_project]
    update_ip_catalog -rebuild
    set defs [get_ipdefs -all -quiet *:hls:cnn_pipeline_v10:*]
    if {[llength $defs] != 1} {error "expected one cnn_pipeline_v10 ipdef, got [llength $defs]: $defs"}
    set vlnv [get_property VLNV [lindex $defs 0]]
    create_ip -vlnv $vlnv -module_name cnn_pipeline_v10_fused_hls_0
    return [list $vlnv [get_ips cnn_pipeline_v10_fused_hls_0]]
}

set project_dir [file join $work_dir project]
lassign [make_project_and_ip $project_dir $pkg] effective_vlnv ip
set cache_id [config_ip_cache -get_id $ip]
set identity_method version_1_2
if {$effective_vlnv ne "xilinx.com:hls:cnn_pipeline_v10:1.2"} {error "unexpected v1.2 VLNV: $effective_vlnv"}
if {$cache_id eq $old_cache_id || $cache_id eq $v11_cache_id} {
    error "fused v1.2 cache ID aliases a historical cache ID: $cache_id"
}

set idfh [open [file join $evidence_dir cache-identity.txt] w]
puts $idfh "old_cache_id=$old_cache_id"
puts $idfh "v11_cache_id=$v11_cache_id"
puts $idfh "new_cache_id=$cache_id"
puts $idfh "identity_method=$identity_method"
puts $idfh "old_core_revision=$old_revision"
puts $idfh "new_core_revision=$new_revision"
puts $idfh "effective_vlnv=$effective_vlnv"
puts $idfh "canonical_rtl_digest=$rtl_digest"
close $idfh
if {$identity_only} {
    close_project
    puts "CNN_V10_FUSED_HLS_CACHE_IDENTITY_PASS cache_id=$cache_id vlnv=$effective_vlnv method=$identity_method"
    return
}

generate_target synthesis $ip
create_ip_run $ip
set run [get_runs cnn_pipeline_v10_fused_hls_0_synth_1]
set run_strategy [get_property STRATEGY $run]
if {$run_strategy ne "Vivado Synthesis Defaults"} {error "expected default OOC synthesis strategy, got: $run_strategy"}
launch_runs $run -jobs 1
wait_on_run $run
set status [get_property STATUS $run]
set progress [get_property PROGRESS $run]
set dcp [get_property DIRECTORY $run]/cnn_pipeline_v10_fused_hls_0.dcp
if {![string match {*Complete*} $status] || $progress ne "100%" || ![file isfile $dcp]} {
    error "OOC synth incomplete: status=$status progress=$progress dcp=$dcp"
}
file copy -force $dcp [file join $evidence_dir cnn_pipeline_v10_fused_hls_0.dcp]
open_run $run
report_utilization -file [file join $evidence_dir utilization-post-synth.rpt]
report_timing_summary -delay_type min_max -max_paths 50 -file [file join $evidence_dir timing-post-synth.rpt]
set slow_clock [get_clocks -quiet ap_clk]
set fast_clock [get_clocks -quiet pw_fast_clk]
if {[llength $slow_clock] != 1 || [llength $fast_clock] != 1} {error "expected exact ap_clk and pw_fast_clk clocks"}
set slow_period [get_property PERIOD $slow_clock]
set fast_period [get_property PERIOD $fast_clock]
if {[expr {abs(double($slow_period) - 5.0)}] > 0.0001 || [expr {abs(double($fast_period) - 2.5)}] > 0.0001} {
    error "OOC clock period mismatch: ap_clk=$slow_period pw_fast_clk=$fast_period"
}
report_clocks -file [file join $evidence_dir report-clocks.rpt]
report_clock_interaction -delay_type min_max -file [file join $evidence_dir report-clock-interaction.rpt]
foreach spec {
    {slow-to-slow ap_clk ap_clk}
    {fast-to-fast pw_fast_clk pw_fast_clk}
    {slow-to-fast ap_clk pw_fast_clk}
    {fast-to-slow pw_fast_clk ap_clk}
} {
    lassign $spec label from_clock to_clock
    set witness [get_timing_paths -quiet -from [get_clocks $from_clock] -to [get_clocks $to_clock] -delay_type max -max_paths 1]
    if {[llength $witness] < 1} {error "No OOC timing-path witness for $label ($from_clock -> $to_clock)"}
    report_timing -from [get_clocks $from_clock] -to [get_clocks $to_clock] -delay_type min_max -max_paths 100 -file [file join $evidence_dir timing-$label.rpt]
}
set cfh [open [file join $evidence_dir clock-contract.rpt] w]
puts $cfh "ap_clk_period_ns=$slow_period"
puts $cfh "pw_fast_clk_period_ns=$fast_period"
puts $cfh "phase_contract=aligned_primary_edges_at_t0_boundary_assumption"
puts $cfh "physical_common_root_implemented=false"
puts $cfh "final_platform_generated_clock_and_skew_signoff_required=true"
puts $cfh "async_clock_groups=none"
puts $cfh "false_paths=none"
puts $cfh "synthesis_strategy=$run_strategy"
close $cfh
close_design

set pre_generate_cache_id $cache_id
set cache_id [config_ip_cache -get_id $ip]
if {$cache_id eq $old_cache_id || $cache_id eq $v11_cache_id} {error "generated fused v1.2 cache ID aliases a historical cache ID: $cache_id"}
set idfh [open [file join $evidence_dir cache-identity-final.txt] w]
puts $idfh "old_cache_id=$old_cache_id"
puts $idfh "v11_cache_id=$v11_cache_id"
puts $idfh "pre_generate_cache_id=$pre_generate_cache_id"
puts $idfh "new_cache_id=$cache_id"
puts $idfh "effective_vlnv=$effective_vlnv"
puts $idfh "canonical_rtl_digest=$rtl_digest"
close $idfh
config_ip_cache -use_cache_location $cache_dir
config_ip_cache -import_from_project
set match [config_ip_cache -cache_has_match $ip]
config_ip_cache -report -rptfile [file join $evidence_dir ip-cache-report.rpt]
set sfh [open [file join $evidence_dir ooc-status.txt] w]
puts $sfh "run_status=$status"
puts $sfh "run_progress=$progress"
puts $sfh "dcp=$dcp"
puts $sfh "new_cache_id=$cache_id"
puts $sfh "cache_has_match=$match"
puts $sfh "effective_vlnv=$effective_vlnv"
puts $sfh "synthesis_strategy=$run_strategy"
puts $sfh "ap_clk_period_ns=$slow_period"
puts $sfh "pw_fast_clk_period_ns=$fast_period"
close $sfh
if {$match eq {}} {error "new fused cache has no match for $cache_id"}
close_project
puts "CNN_V10_FUSED_HLS_OOC_CACHE_PASS cache_id=$cache_id vlnv=$effective_vlnv"
