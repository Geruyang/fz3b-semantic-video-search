# Official Vivado IP OOC synthesis and remote-cache export for fused half2x HLS IP.
if {$argc != 6 && $argc != 7} {error "usage: build_fused_hls_ooc_cache.tcl INPUT_IP WORK_DIR EVIDENCE_DIR CACHE_DIR OLD_CACHE_ID RTL_DIGEST ?IDENTITY_ONLY?"}
lassign $argv input_ip work_dir evidence_dir cache_dir old_cache_id rtl_digest identity_only
if {$identity_only eq {}} {set identity_only 0}
foreach n {input_ip work_dir evidence_dir cache_dir} {set $n [file normalize [set $n]]}
file mkdir $work_dir; file mkdir $evidence_dir; file mkdir $cache_dir
set pkg [file join $work_dir hls-ip-fused-cache-identity]
file delete -force $pkg
file copy -force $input_ip $pkg
set component [file join $pkg component.xml]
if {![file isfile $component]} {error "missing component.xml: $component"}

# Use IP Packager rather than hand-editing XML. Preserve the public VLNV first;
# only fall back to a version bump if core_revision alone does not alter get_id.
create_project -in_memory fused_cache_identity -part xazu3eg-sfvc784-1-i
ipx::open_core $component
set core [ipx::current_core]
set old_revision [get_property core_revision $core]
set new_revision [expr {wide($old_revision) + 1}]
set_property core_revision $new_revision $core
set_property description "cnn_v10 fused half2x; canonical_rtl_digest=$rtl_digest" $core
ipx::save_core $core
close_project

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
set identity_method core_revision
if {$cache_id eq $old_cache_id} {
    close_project
    file delete -force $project_dir
    create_project -in_memory fused_cache_version -part xazu3eg-sfvc784-1-i
    ipx::open_core $component
    set core [ipx::current_core]
    set_property version 1.1 $core
    ipx::save_core $core
    close_project
    lassign [make_project_and_ip $project_dir $pkg] effective_vlnv ip
    set cache_id [config_ip_cache -get_id $ip]
    set identity_method version_1_1_fallback
}
if {$cache_id eq $old_cache_id} {error "fused cache ID still aliases old cache ID $old_cache_id"}

set idfh [open [file join $evidence_dir cache-identity.txt] w]
puts $idfh "old_cache_id=$old_cache_id"
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
set_property strategy Flow_PerfOptimized_high $run
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
close_design

set pre_generate_cache_id $cache_id
set cache_id [config_ip_cache -get_id $ip]
if {$cache_id eq $old_cache_id} {error "generated fused IP cache ID aliases old cache ID $old_cache_id"}
set idfh [open [file join $evidence_dir cache-identity-final.txt] w]
puts $idfh "old_cache_id=$old_cache_id"
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
close $sfh
if {$match eq {}} {error "new fused cache has no match for $cache_id"}
close_project
puts "CNN_V10_FUSED_HLS_OOC_CACHE_PASS cache_id=$cache_id vlnv=$effective_vlnv"
