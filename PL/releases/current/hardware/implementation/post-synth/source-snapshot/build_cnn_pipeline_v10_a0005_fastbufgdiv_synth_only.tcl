# Offline PL-only FZV10 build.  This script deliberately never opens hardware
# manager and never sources or exports PS initialization code.
# argv: NEW_PROJECT_DIR NEW_EVIDENCE_DIR EXPORTED_HLS_IP_DIRECTORY
#       EXPECTED_COMPONENT_SHA256 COMBINED_PARAMETER_MANIFEST EXPECTED_COMBINED_SHA256
#       BOARD_INVENTORY_RECEIPT EXPECTED_BOARD_SHA256 SOURCE_MANIFEST EXPECTED_SOURCE_SHA256
#       CANDIDATE_CONTRACT EXPECTED_CONTRACT_SHA256 STRUCTURE_AUDIT EXPECTED_AUDIT_SHA256
#       HLS002_RECEIPT EXPECTED_HLS002_RECEIPT_SHA256
#       APREADY_PATCHED002_RECEIPT EXPECTED_APREADY_PATCHED002_SHA256
#       FUSED_TRANSFORM_RECEIPT EXPECTED_TRANSFORM_SHA256
#       FROZEN_STRUCTURE_RECEIPT EXPECTED_FROZEN_STRUCTURE_SHA256
#       ID_VALUE ABI_VERSION_VALUE CAPS_VALUE CANDIDATE_PL_MHZ CLOCK_CONTRACT
#       DEBUG_PROFILE NATIVE_ILA_DEPTH RUN_SCOPE
#
# CANDIDATE_PL_MHZ defaults to 120.000.  Every value, including 180/200, is an
# offline clock-wizard candidate until a matching FZ3B PS/preset, generated
# clocks, CDC/timing and live-board run prove it.  This script does not edit the
# PS DDR/MIO preset and does not assign any package or board pin.
# CLOCK_CONTRACT is one comma-separated frozen tuple:
#   PS_BD_NOMINAL_HZ,LIVE_INPUT_HZ,MMCM_M,MMCM_D,MMCM_O_SLOW,MMCM_O_FAST
# This candidate keeps the frozen logical 12/1/6/3 contract, but implements
# it as one MMCM 400 MHz output (O=3) feeding two sibling BUFGCE_DIVs:
# DIVIDE=2 for driver/job 200 MHz and DIVIDE=1 for PW-local 400 MHz.  The
# logical O_SLOW=6 is checked as 2*O_FAST; it is not a second MMCM output.
# PRIM_IN_FREQ always uses the BD nominal value, while routed STA uses the live
# input value propagated through the frozen implemented M/D/O ratio.  The live
# value is historical evidence and must be rechecked before any V10 board use.
# DEBUG_PROFILE defaults to release.  release-guard-only keeps the native guard
# ILA but omits the pipeline ILA/trace pack for a resource-qualified fit build;
# release-no-ila omits both native ILAs and the trace pack.  The twelve HLS
# traces are ap_none output signals, not AXI-Lite registers; without the
# pipeline ILA they are intentionally not observable by software.  The legacy release profile
# keeps both native ILAs, while full-master-ila additionally restores the six
# 1024-deep full-AXI monitor slots.
# Vivado 2026.1 ILA 6.2 accepts a minimum C_DATA_DEPTH of 1024, so
# NATIVE_ILA_DEPTH defaults to 1024 for both guard and 12-trace ILAs.  Larger
# values remain explicit resource-qualified debug choices.  Native .ila
# capture remains the required evidence format for every actual capture.
if {$argc != 30} {
    error "Need exactly 30 arguments for the frozen A0005 synth-only candidate"
}
lassign $argv project_dir output hls_ip_source expected_component_sha combined_manifest_source expected_combined_manifest_sha board_inventory_source expected_board_inventory_sha source_manifest_source expected_source_manifest_sha candidate_contract_source expected_candidate_contract_sha structure_audit_source expected_structure_audit_sha hls002_receipt_source expected_hls002_receipt_sha apready_receipt_source expected_apready_receipt_sha transform_receipt_source expected_transform_receipt_sha frozen_structure_receipt_source expected_frozen_structure_receipt_sha id_value abi_value caps_value candidate_mhz clock_contract debug_profile native_ila_depth run_scope
if {![regexp {^[0-9]+([.][0-9]+)?$} $candidate_mhz] || ![string is double -strict $candidate_mhz] || $candidate_mhz < 50.0 || $candidate_mhz > 250.0} {
    error "CANDIDATE_PL_MHZ must be a finite candidate in 50..250 MHz"
}
if {$debug_profile ni {release release-guard-only release-no-ila full-master-ila}} {
    error "DEBUG_PROFILE must be release, release-guard-only, release-no-ila or full-master-ila"
}
if {$native_ila_depth ni {1024 2048 4096 8192 16384 32768 65536 131072}} {
    error "NATIVE_ILA_DEPTH must be a Vivado 2026.1 ILA 6.2 supported depth"
}
if {$run_scope ne "synth-only"} {error "RUN_SCOPE must be synth-only"}
set clock_fields [split $clock_contract ,]
if {[llength $clock_fields] != 6} {error "CLOCK_CONTRACT must be BD_NOMINAL_HZ,LIVE_INPUT_HZ,MMCM_M,MMCM_D,MMCM_O_SLOW,MMCM_O_FAST"}
lassign $clock_fields expected_ps_bd_nominal_hz historical_live_input_hz expected_mmcm_m expected_mmcm_d expected_mmcm_o0 expected_mmcm_o1
foreach {label value} [list bd_nominal_hz $expected_ps_bd_nominal_hz live_input_hz $historical_live_input_hz mmcm_m $expected_mmcm_m mmcm_d $expected_mmcm_d mmcm_o0 $expected_mmcm_o0 mmcm_o1 $expected_mmcm_o1] {
    if {![regexp {^[0-9]+([.][0-9]+)?$} $value] || ![string is double -strict $value] || $value <= 0} {
        error "CLOCK_CONTRACT $label must be a positive finite number"
    }
}
set candidate_mhz [format %.6f $candidate_mhz]
set enable_full_master_ila [expr {$debug_profile eq "full-master-ila"}]
set enable_guard_ila [expr {$debug_profile ne "release-no-ila"}]
set enable_pipeline_ila [expr {$debug_profile ne "release-guard-only" && $debug_profile ne "release-no-ila"}]
set clock_wiz_nominal_input_mhz [expr {double($expected_ps_bd_nominal_hz) / 1000000.0}]
set historical_live_input_period_ns [expr {1000000000.0 / double($historical_live_input_hz)}]
if {abs(double($expected_mmcm_o0) - 2.0 * double($expected_mmcm_o1)) > 0.0005} {
    error "Fast-plus-BUFGCE_DIV topology requires logical O_SLOW=2*O_FAST"
}
set expected_ratio [expr {double($expected_mmcm_m) / (double($expected_mmcm_d) * double($expected_mmcm_o1) * 2.0)}]
set expected_nominal_output_mhz [expr {$clock_wiz_nominal_input_mhz * $expected_ratio}]
set expected_live_output_hz [expr {double($historical_live_input_hz) * $expected_ratio}]
set expected_fast_ratio [expr {double($expected_mmcm_m) / (double($expected_mmcm_d) * double($expected_mmcm_o1))}]
set expected_nominal_fast_mhz [expr {$clock_wiz_nominal_input_mhz * $expected_fast_ratio}]
set expected_live_fast_hz [expr {double($historical_live_input_hz) * $expected_fast_ratio}]
if {abs($expected_nominal_output_mhz - double($candidate_mhz)) > 0.010} {
    error "Requested candidate $candidate_mhz MHz does not match frozen nominal M/D/O output $expected_nominal_output_mhz MHz"
}
if {abs($expected_nominal_fast_mhz - (2.0 * double($candidate_mhz))) > 0.010} {
    error "Fast clock $expected_nominal_fast_mhz MHz is not exactly 2x slow candidate $candidate_mhz MHz"
}
foreach v {project_dir output hls_ip_source combined_manifest_source board_inventory_source source_manifest_source candidate_contract_source structure_audit_source hls002_receipt_source apready_receipt_source transform_receipt_source frozen_structure_receipt_source} {set $v [file normalize [set $v]]}
if {[file exists $project_dir] || [file exists $output]} {error "Project and evidence paths must be new"}
if {![file isfile [file join $hls_ip_source component.xml]]} {error "Missing HLS component.xml"}
if {![file isfile $combined_manifest_source]} {error "Missing combined parameter manifest"}
if {![file isfile $board_inventory_source]} {error "Missing fresh board inventory receipt"}
foreach {label path} [list source_manifest $source_manifest_source candidate_contract $candidate_contract_source structure_audit $structure_audit_source hls002_receipt $hls002_receipt_source apready_patched002_receipt $apready_receipt_source transform_receipt $transform_receipt_source frozen_structure_receipt $frozen_structure_receipt_source] {
    if {![file isfile $path]} {error "Missing A0005 $label"}
}
if {![regexp {^[0-9a-fA-F]{64}$} $expected_component_sha]} {error "Expected component SHA256 must be 64 hex digits"}
set expected_component_sha [string tolower $expected_component_sha]
if {![regexp {^[0-9a-fA-F]{64}$} $expected_combined_manifest_sha]} {error "Expected combined manifest SHA256 must be 64 hex digits"}
set expected_combined_manifest_sha [string tolower $expected_combined_manifest_sha]
set required_combined_manifest_sha 4a32c9373e783ac572a5d3374b316181a4d52ae9a92ec45f8b13d763ef028690
if {$expected_combined_manifest_sha ne $required_combined_manifest_sha} {
    error "Unexpected A0005 combined manifest identity $expected_combined_manifest_sha"
}
if {![regexp {^[0-9a-fA-F]{64}$} $expected_board_inventory_sha]} {error "Expected board inventory SHA256 must be 64 hex digits"}
set expected_board_inventory_sha [string tolower $expected_board_inventory_sha]
foreach {label value required} [list \
    source_manifest_sha $expected_source_manifest_sha f8714065c490506f5e08b1738c8fe121270db2c66da9eb42d9674907102e0593 \
    candidate_contract_sha $expected_candidate_contract_sha a65bdd2c50a5f1b5329350e22a67d9fb9ff4731c3517454ae524f667c5dc3f4d] {
    if {[string tolower $value] ne $required} {error "A0005 $label mismatch"}
}
if {![regexp {^[0-9a-fA-F]{64}$} $expected_structure_audit_sha]} {error "Expected structure audit SHA256 must be 64 hex digits"}
set expected_structure_audit_sha [string tolower $expected_structure_audit_sha]
if {[string tolower $expected_hls002_receipt_sha] ne "4ac9288f1aac5bc2fc1026cde28b85d8ba80c8b82145788377b48b5f65ef8317"} {error "A0005 HLS002 receipt identity mismatch"}
if {[string tolower $expected_apready_receipt_sha] ne "daad747738b8b30538842eb290faf6d6e0b0c30020a08d814a264668ee2409f6"} {error "A0005 ap_ready patched002 receipt identity mismatch"}
if {[string tolower $expected_transform_receipt_sha] ne "20e66aa3b462e7318a3b4b74565cfc417bbba5c699cdc7db242bec2330fd9457"} {error "A0005 fused transform receipt identity mismatch"}
if {[string tolower $expected_frozen_structure_receipt_sha] ne "da0e0d8dc5bcec87d9d8ff1664d9f984fea94ac37c18c5076a2e1255327a4802"} {error "A0005 frozen structure receipt identity mismatch"}
foreach {label value} [list id $id_value abi $abi_value caps $caps_value] {
    if {![regexp {^0x[0-9a-fA-F]{8}$} $value]} {error "$label must be an exact 32-bit 0x value"}
}
foreach {label value required} [list \
    id $id_value 0x465A5641 \
    abi $abi_value 0x000A0005 \
    caps $caps_value 0x00000FFF] {
    if {[string tolower $value] ne [string tolower $required]} {
        error "FZV10 $label identity mismatch: got $value expected $required"
    }
}
set id_value 0x465A5641
set abi_value 0x000A0005
set caps_value 0x00000FFF

proc sha256_file {path} {
    set value [string tolower [lindex [split [exec certutil -hashfile $path SHA256] \n] 1]]
    regsub -all { } $value {} value
    return $value
}

set experiment_src [file dirname [file normalize [info script]]]
set src [file normalize [file join $experiment_src .. .. .. ..]]
foreach name {fzv10_ddr_guard.sv fzv10_ddr_guard_bd.sv fzv4_axi_hp0_monitor.sv ps8_axi_reset.sv fzv10_trace_pack.sv} {
    if {![file isfile [file join $src $name]]} {error "Missing source $name"}
}
set rtl_hash_contract [list \
    fzv10_ddr_guard.sv 134af8682253e9c62038c5705c0ed294809eb55b20dd672114907cdc55e725d2 \
    fzv10_ddr_guard_bd.sv 47a805cc9aa463e2df3314c007c32335727e9680050351866cf20a3de7b278e1 \
    fzv4_axi_hp0_monitor.sv 813ea8311ca999b2e9a6df0135f2c0c983c0b18c27a3ff8b7db03d9bd3859247 \
    ps8_axi_reset.sv cc433ce5a3ccbad912614c3b1b006ecb823b28808946642d92bc8102a25aa66d \
    fzv10_trace_pack.sv b7dd6d7ea7a98da2bad02eb60567795b0032678ba50bc1da69eb8678a6c2e98e]
foreach {name expected_sha} $rtl_hash_contract {
    set actual_sha [sha256_file [file join $src $name]]
    if {$actual_sha ne $expected_sha} {error "Frozen platform RTL hash mismatch for $name: $actual_sha"}
}
set component_sha [sha256_file [file join $hls_ip_source component.xml]]
if {$component_sha ne $expected_component_sha} {
    error "Unexpected V10 package component.xml SHA256 $component_sha"
}
set combined_manifest_sha [sha256_file $combined_manifest_source]
if {$combined_manifest_sha ne $expected_combined_manifest_sha} {
    error "Unexpected combined parameter manifest SHA256 $combined_manifest_sha"
}
set board_inventory_sha [sha256_file $board_inventory_source]
if {$board_inventory_sha ne $expected_board_inventory_sha} {
    error "Unexpected fresh board inventory receipt SHA256 $board_inventory_sha"
}
if {[sha256_file $source_manifest_source] ne [string tolower $expected_source_manifest_sha]} {error "A0005 source manifest bytes changed"}
if {[sha256_file $candidate_contract_source] ne [string tolower $expected_candidate_contract_sha]} {error "A0005 candidate contract bytes changed"}
if {[sha256_file $structure_audit_source] ne $expected_structure_audit_sha} {error "A0005 generated RTL structure audit bytes changed"}
if {[sha256_file $hls002_receipt_source] ne [string tolower $expected_hls002_receipt_sha]} {error "A0005 HLS002 receipt bytes changed"}
if {[sha256_file $apready_receipt_source] ne [string tolower $expected_apready_receipt_sha]} {error "A0005 ap_ready patched002 receipt bytes changed"}
if {[sha256_file $transform_receipt_source] ne [string tolower $expected_transform_receipt_sha]} {error "A0005 fused transform receipt bytes changed"}
if {[sha256_file $frozen_structure_receipt_source] ne [string tolower $expected_frozen_structure_receipt_sha]} {error "A0005 frozen structure receipt bytes changed"}
set audit_fh [open $structure_audit_source r]
set audit_text [read $audit_fh]
close $audit_fh
foreach token [list {"pass": true} {"core_abi": "0x000A0005"} {"software": "sw10.5"} {"guard_caps": "0x00000fff"} $expected_combined_manifest_sha ef373560fbb68e8719d5497b0d259b8a6dab734b2f88744f9d3505f8143af711 2b541de975975b5e05060287b2052ce1dc1375b83e601e79a59b79be4dc0efdf] {
    if {[string first $token $audit_text] < 0} {error "A0005 structure audit lacks required binding: $token"}
}

file mkdir $output
set source_snapshot [file join $output source-snapshot]
file mkdir $source_snapshot
file copy -- [file normalize [info script]] [file join $source_snapshot build_cnn_pipeline_v10_a0005_fastbufgdiv_synth_only.tcl]
foreach name {fzv10_ddr_guard.sv fzv10_ddr_guard_bd.sv fzv4_axi_hp0_monitor.sv ps8_axi_reset.sv fzv10_trace_pack.sv} {
    file copy -- [file join $src $name] [file join $source_snapshot $name]
}
set clock_tree_source [file normalize [file join $experiment_src .. .. .. pw_half2x cnn_v10_half2x_clock_tree.sv]]
if {![file isfile $clock_tree_source]} {error "Missing half2x sibling BUFGCE_DIV clock tree"}
set expected_clock_tree_sha d3ab3a3197ddf76c941cc818a347ca10cc0053f6c6274adc3e9da96c5ab17c8a
if {[sha256_file $clock_tree_source] ne $expected_clock_tree_sha} {error "Half2x clock-tree source hash mismatch"}
file copy -- $clock_tree_source [file join $source_snapshot cnn_v10_half2x_clock_tree.sv]
file copy -- $combined_manifest_source [file join $source_snapshot combined-parameter-manifest.json]
file copy -- $board_inventory_source [file join $source_snapshot board-inventory-receipt.json]
file copy -- $source_manifest_source [file join $source_snapshot candidate-source-manifest.json]
file copy -- $candidate_contract_source [file join $source_snapshot candidate-contract.json]
file copy -- $structure_audit_source [file join $source_snapshot a0005-generated-rtl-structure-audit.json]
file copy -- $hls002_receipt_source [file join $source_snapshot hls002-receipt.json]
file copy -- $apready_receipt_source [file join $source_snapshot apready-patched002-receipt.json]
file copy -- $transform_receipt_source [file join $source_snapshot fused-transform-receipt.json]
file copy -- $frozen_structure_receipt_source [file join $source_snapshot frozen-structure-receipt.json]
set frozen_ip [file join $output hls-ip]
file copy -force -- $hls_ip_source $frozen_ip

set_param general.maxThreads 16
if {[get_param general.maxThreads] != 16} {error "Vivado synthesis maxThreads did not accept the requested value 16"}
set_param synth.maxThreads 8
if {[get_param synth.maxThreads] != 8} {error "Vivado synth.maxThreads did not accept the requested value 8"}
create_project cnn_pipeline_v10 $project_dir -part xazu3eg-sfvc784-1-i
# The synthesis runner may bind an official Vivado remote IP cache imported
# from the already-qualified half2x project.  This is the supported reuse path:
# no DCP is copied into a run directory and the HLS cache hit is checked both
# before and after synth_1.
set shared_cache {}
set require_hls_cache_reuse 0
if {[info exists ::env(FZV10_IP_CACHE_DIR)] && $::env(FZV10_IP_CACHE_DIR) ne {}} {
    set shared_cache [file normalize $::env(FZV10_IP_CACHE_DIR)]
    if {![file isdirectory $shared_cache]} {error "Bound Vivado IP cache directory does not exist: $shared_cache"}
    config_ip_cache -use_cache_location $shared_cache
}
if {[info exists ::env(FZV10_REQUIRE_HLS_CACHE_REUSE)] && $::env(FZV10_REQUIRE_HLS_CACHE_REUSE) eq "1"} {
    set require_hls_cache_reuse 1
    if {$shared_cache eq {}} {error "HLS cache reuse was required without FZV10_IP_CACHE_DIR"}
}
set_property ip_repo_paths [list $frozen_ip] [current_project]
update_ip_catalog
if {[llength [get_ipdefs -all xilinx.com:hls:cnn_pipeline_v10:1.3]] != 1} {error "Frozen fused HLS IP package v1.3 not unique"}

add_files [list \
    [file join $source_snapshot fzv10_ddr_guard.sv] \
    [file join $source_snapshot fzv10_ddr_guard_bd.sv] \
    [file join $source_snapshot fzv4_axi_hp0_monitor.sv] \
    [file join $source_snapshot ps8_axi_reset.sv] \
    [file join $source_snapshot fzv10_trace_pack.sv] \
    [file join $source_snapshot cnn_v10_half2x_clock_tree.sv]]
update_compile_order -fileset sources_1

create_bd_design cnn_pipeline_v10_shell
# This PS property dictionary is intentionally the V6/build007 baseline.  Do
# not add or tune DDR, MIO, FCLK or board preset properties in this candidate.
set ps [create_bd_cell -type ip -vlnv xilinx.com:ip:zynq_ultra_ps_e:3.5 ps]
set_property -dict [list \
    CONFIG.PSU__USE__M_AXI_GP0 1 \
    CONFIG.PSU__MAXIGP0__DATA_WIDTH 32 \
    CONFIG.PSU__USE__M_AXI_GP1 0 \
    CONFIG.PSU__USE__M_AXI_GP2 0 \
    CONFIG.PSU__USE__S_AXI_GP0 0 \
    CONFIG.PSU__USE__S_AXI_GP1 0 \
    CONFIG.PSU__USE__S_AXI_GP2 1 \
    CONFIG.PSU__SAXIGP2__DATA_WIDTH 64 \
    CONFIG.PSU__USE__S_AXI_GP3 0 \
    CONFIG.PSU__USE__S_AXI_GP4 0 \
    CONFIG.PSU__USE__S_AXI_GP5 0 \
    CONFIG.PSU__USE__S_AXI_GP6 0 \
    CONFIG.PSU__USE__IRQ0 0 \
    CONFIG.PSU__USE__IRQ1 0 \
    CONFIG.PSU__FPGA_PL0_ENABLE 1 \
    CONFIG.PSU__FPGA_PL1_ENABLE 1 \
    CONFIG.PSU__FPGA_PL2_ENABLE 0 \
    CONFIG.PSU__FPGA_PL3_ENABLE 0 \
    CONFIG.PSU__DDRC__ROW_ADDR_COUNT 15 \
    CONFIG.PSU__DDRC__DEVICE_CAPACITY {4096 MBits} \
    CONFIG.PSU__DDR_HIGH_ADDRESS_GUI_ENABLE 1] $ps
foreach {prop expected} {
    CONFIG.PSU__SAXIGP2__DATA_WIDTH 64
    CONFIG.PSU__HIGH_ADDRESS__ENABLE 1
    CONFIG.PSU__DDR_HIGH_ADDRESS_GUI_ENABLE 1
    CONFIG.PSU__DDRC__ROW_ADDR_COUNT 15
    CONFIG.PSU__DDRC__DEVICE_CAPACITY {4096 MBits}
} {
    if {[get_property $prop $ps] ne $expected} {error "PS address-model property $prop mismatch"}
}

set hls [create_bd_cell -type ip -vlnv xilinx.com:hls:cnn_pipeline_v10:1.3 hls]
set guard [create_bd_cell -type module -reference fzv10_ddr_guard_bd guard]
set_property -dict [list CONFIG.ID_VALUE $id_value CONFIG.ABI_VERSION_VALUE $abi_value CONFIG.CAPS_VALUE $caps_value] $guard
set monitor [create_bd_cell -type module -reference fzv4_axi_hp0_monitor hp0_monitor]
set reset [create_bd_cell -type module -reference ps8_axi_reset reset]
set selected_ps_pl_clock_index 1
set selected_ps_pl_clock_pin ps/pl_clk1
set selected_ps_pl_clock_name clk_pl_1
set selected_ps_pl_freq_hz [get_property CONFIG.FREQ_HZ [get_bd_pins $selected_ps_pl_clock_pin]]
if {![string is integer -strict $selected_ps_pl_freq_hz] || $selected_ps_pl_freq_hz <= 0} {
    error "PS $selected_ps_pl_clock_pin does not expose a usable nominal CONFIG.FREQ_HZ"
}
set ps_bd_nominal_selected_mhz [format %.6f [expr {double($selected_ps_pl_freq_hz) / 1000000.0}]]
if {abs(double($selected_ps_pl_freq_hz) - double($expected_ps_bd_nominal_hz)) > 1.0} {
    error "Half2x PS model metadata drift on $selected_ps_pl_clock_pin: expected $expected_ps_bd_nominal_hz Hz, got $selected_ps_pl_freq_hz Hz"
}
set clock_wiz [create_bd_cell -type ip -vlnv xilinx.com:ip:clk_wiz:6.0 clock_wiz]
set_property -dict [list \
    CONFIG.PRIM_SOURCE No_buffer \
    CONFIG.PRIM_IN_FREQ $ps_bd_nominal_selected_mhz \
    CONFIG.NUM_OUT_CLKS 1 \
    CONFIG.CLKOUT1_REQUESTED_OUT_FREQ [expr {2.0 * double($candidate_mhz)}] \
    CONFIG.CLKOUT1_DRIVES No_buffer \
    CONFIG.USE_LOCKED true \
    CONFIG.USE_RESET false] $clock_wiz
set configured_clock_wiz_input_mhz [get_property CONFIG.PRIM_IN_FREQ $clock_wiz]
if {abs(double($configured_clock_wiz_input_mhz) - double($ps_bd_nominal_selected_mhz)) > 0.0000005} {
    error "Clock wizard PRIM_IN_FREQ does not match connected PS pin metadata"
}
foreach {label property expected} [list \
    M CONFIG.MMCM_CLKFBOUT_MULT_F $expected_mmcm_m \
    D CONFIG.MMCM_DIVCLK_DIVIDE $expected_mmcm_d \
    O_FAST CONFIG.MMCM_CLKOUT0_DIVIDE_F $expected_mmcm_o1] {
    set configured [get_property $property $clock_wiz]
    if {abs(double($configured) - double($expected)) > 0.0005} {
        error "Clock wizard auto-selected $label=$configured differs from frozen clock contract $expected"
    }
}
if {[get_property CONFIG.CLKOUT1_DRIVES $clock_wiz] ne "No_buffer"} {
    error "Clock Wizard must expose the raw MMCM fast output directly to the sibling BUFGCE_DIV inputs"
}
set clock_tree [create_bd_cell -type module -reference cnn_v10_half2x_clock_tree half2x_clock_tree]
set pw_local_bd_hz [get_property CONFIG.FREQ_HZ [get_bd_pins clock_wiz/clk_out1]]
set driver_job_bd_hz [expr {$pw_local_bd_hz / 2}]
set expected_pw_local_bd_hz [expr {4 * $selected_ps_pl_freq_hz}]
if {$pw_local_bd_hz != $expected_pw_local_bd_hz || $driver_job_bd_hz != ($expected_pw_local_bd_hz / 2)} {
    error "Clock-tree BD metadata does not match the frozen 99,999,001 Hz PS model"
}
# Module-reference clock outputs otherwise default to 10 MHz in IP Integrator.
# Propagate the real 1x/2x metadata before any AXI clock is connected so
# validate_bd_design checks the new clock topology instead of comparing every
# AXI endpoint against that fallback value.
foreach {pin hz} [list \
    half2x_clock_tree/root_clk_400 $pw_local_bd_hz \
    half2x_clock_tree/driver_job_clk_200 $driver_job_bd_hz \
    half2x_clock_tree/pw_local_clk_400 $pw_local_bd_hz] {
    if {[get_property CONFIG.FREQ_HZ [get_bd_pins $pin]] != $hz} {
        error "Clock-tree BD frequency metadata mismatch on $pin"
    }
}
set platform_reset [create_bd_cell -type ip -vlnv xilinx.com:ip:proc_sys_reset:5.0 platform_reset]
set_property CONFIG.C_AUX_RESET_HIGH 0 $platform_reset
set core_reset [create_bd_cell -type ip -vlnv xilinx.com:ip:proc_sys_reset:5.0 core_reset]
set_property CONFIG.C_AUX_RESET_HIGH 0 $core_reset
set fast_core_reset [create_bd_cell -type ip -vlnv xilinx.com:ip:proc_sys_reset:5.0 fast_core_reset]
set_property CONFIG.C_AUX_RESET_HIGH 0 $fast_core_reset

set ctrl_xbar [create_bd_cell -type ip -vlnv xilinx.com:ip:axi_interconnect:2.1 ctrl_xbar]
set_property -dict [list CONFIG.NUM_SI 1 CONFIG.NUM_MI 2 CONFIG.XBAR_DATA_WIDTH 32] $ctrl_xbar
# Use the official direction-aware AXI Crossbar directly instead of the
# axi_interconnect appcore.  The appcore erased the read-only/write-only HLS
# endpoint modes at the six bidirectional shutdown boundaries and therefore
# generated both channel transactors and six bidirectional MMUs.  Explicit
# crossbar connectivity is a supported IP parameter and removes those unused
# transactors without changing the six shutdown managers or the software ABI.
set data_xbar [create_bd_cell -type ip -vlnv xilinx.com:ip:axi_crossbar:2.1 data_xbar]
set_property -dict [list \
    CONFIG.NUM_SI 6 CONFIG.NUM_MI 1 CONFIG.ADDR_RANGES 2 \
    CONFIG.ADDR_WIDTH 64 CONFIG.DATA_WIDTH 128 CONFIG.ID_WIDTH 4 \
    CONFIG.PROTOCOL AXI4 CONFIG.CONNECTIVITY_MODE SAMD \
    CONFIG.M00_A00_BASE_ADDR 0x0000000040000000 CONFIG.M00_A00_ADDR_WIDTH 30 \
    CONFIG.M00_A01_BASE_ADDR 0x0000000800000000 CONFIG.M00_A01_ADDR_WIDTH 30 \
    CONFIG.M00_READ_ISSUING 16 CONFIG.M00_WRITE_ISSUING 16 \
    CONFIG.M00_S00_READ_CONNECTIVITY 1 CONFIG.M00_S00_WRITE_CONNECTIVITY 0 \
    CONFIG.M00_S01_READ_CONNECTIVITY 1 CONFIG.M00_S01_WRITE_CONNECTIVITY 0 \
    CONFIG.M00_S02_READ_CONNECTIVITY 1 CONFIG.M00_S02_WRITE_CONNECTIVITY 0 \
    CONFIG.M00_S03_READ_CONNECTIVITY 0 CONFIG.M00_S03_WRITE_CONNECTIVITY 1 \
    CONFIG.M00_S04_READ_CONNECTIVITY 1 CONFIG.M00_S04_WRITE_CONNECTIVITY 0 \
    CONFIG.M00_S05_READ_CONNECTIVITY 0 CONFIG.M00_S05_WRITE_CONNECTIVITY 1] $data_xbar
# HP0 is 64 bits while every HLS data master is 128 bits.  Keep one official
# shared width converter after arbitration; it must remain READ_WRITE because
# the aggregate link carries both the read-only and write-only clients.
set data_dwidth [create_bd_cell -type ip -vlnv xilinx.com:ip:axi_dwidth_converter:2.1 data_dwidth]
set_property -dict [list \
    CONFIG.PROTOCOL AXI4 CONFIG.READ_WRITE_MODE READ_WRITE \
    CONFIG.ADDR_WIDTH 64 CONFIG.SI_DATA_WIDTH 128 CONFIG.MI_DATA_WIDTH 64 \
    CONFIG.SI_ID_WIDTH 4 CONFIG.PACKING_LEVEL 1] $data_dwidth

set shutdowns {}
for {set i 0} {$i < 6} {incr i} {
    set sd [create_bd_cell -type ip -vlnv xilinx.com:ip:dfx_axi_shutdown_manager:1.0 shutdown_$i]
    set_property -dict [list \
        CONFIG.CTRL_INTERFACE_TYPE 0 \
        CONFIG.RP_IS_MASTER true \
        CONFIG.DP_PROTOCOL AXI4MM \
        CONFIG.DP_AXI_ADDR_WIDTH 64 \
        CONFIG.DP_AXI_DATA_WIDTH 128 \
        CONFIG.DP_AXI_ID_WIDTH 1 \
        CONFIG.DP_AXI_AWUSER_WIDTH 1 \
        CONFIG.DP_AXI_ARUSER_WIDTH 1 \
        CONFIG.DP_AXI_WUSER_WIDTH 1 \
        CONFIG.DP_AXI_RUSER_WIDTH 1 \
        CONFIG.DP_AXI_BUSER_WIDTH 1 \
        CONFIG.RESET_ACTIVE_LEVEL 0] $sd
    lappend shutdowns $sd
}

set req_slices {}
for {set i 0} {$i < 6} {incr i} {
    set sl [create_bd_cell -type ip -vlnv xilinx.com:ip:xlslice:1.0 req_slice_$i]
    set_property -dict [list CONFIG.DIN_WIDTH 6 CONFIG.DIN_FROM $i CONFIG.DIN_TO $i CONFIG.DOUT_WIDTH 1] $sl
    lappend req_slices $sl
}
set ack_all [create_bd_cell -type ip -vlnv xilinx.com:ip:xlconcat:2.1 ack_all]
set ack_rd  [create_bd_cell -type ip -vlnv xilinx.com:ip:xlconcat:2.1 ack_rd]
set ack_wr  [create_bd_cell -type ip -vlnv xilinx.com:ip:xlconcat:2.1 ack_wr]
foreach c [list $ack_all $ack_rd $ack_wr] {set_property CONFIG.NUM_PORTS 6 $c}
set const_zero [create_bd_cell -type ip -vlnv xilinx.com:ip:xlconstant:1.1 const_zero]
set_property -dict [list CONFIG.CONST_WIDTH 1 CONFIG.CONST_VAL 0] $const_zero
set const_one [create_bd_cell -type ip -vlnv xilinx.com:ip:xlconstant:1.1 const_one]
set_property -dict [list CONFIG.CONST_WIDTH 1 CONFIG.CONST_VAL 1] $const_one

# The six safety shutdown cells intentionally remain bidirectional while the
# downstream official AXI Crossbar uses explicit read/write connectivity
# masks.  Vivado reports that exact boundary, and the pre-existing USER-width
# adapters, as warnings.  Do not configure the whole BD 41-237 ID: validation
# and generation logs are audited below against exact message bodies so a new
# frequency, direction, or width mismatch remains fatal.

connect_bd_intf_net [get_bd_intf_pins ps/M_AXI_HPM0_FPD] [get_bd_intf_pins ctrl_xbar/S00_AXI]
connect_bd_intf_net [get_bd_intf_pins ctrl_xbar/M00_AXI] [get_bd_intf_pins hls/s_axi_control]
connect_bd_intf_net [get_bd_intf_pins ctrl_xbar/M01_AXI] [get_bd_intf_pins guard/S_AXI]
# ABI order is fixed across shutdown request/ACK, address maps, ILA slots and
# software: param1, param2, A read, A write, B read, B write.
set hls_ifaces {m_axi_g_param1 m_axi_g_param2 m_axi_g_act_a_r m_axi_g_act_a_w m_axi_g_act_b_r m_axi_g_act_b_w}
set hls_modes {READ_ONLY READ_ONLY READ_ONLY WRITE_ONLY READ_ONLY WRITE_ONLY}
for {set i 0} {$i < 6} {incr i} {
    set hls_pin [get_bd_intf_pins hls/[lindex $hls_ifaces $i]]
    if {[llength $hls_pin] != 1} {error "Missing V10 HLS master index $i"}
    set expected_mode [lindex $hls_modes $i]
    foreach {prop expected} [list CONFIG.ADDR_WIDTH 64 CONFIG.DATA_WIDTH 128 CONFIG.ID_WIDTH 1 CONFIG.READ_WRITE_MODE $expected_mode] {
        if {[get_property $prop $hls_pin] ne $expected} {error "V10 HLS master $i property $prop mismatch"}
    }
    set sd [lindex $shutdowns $i]
    set sd_slave_pin [get_bd_intf_pins $sd/S_AXI]
    set sd_master_pin [get_bd_intf_pins $sd/M_AXI]
    set xbar_slave_pin [get_bd_intf_pins data_xbar/S0${i}_AXI]
    connect_bd_intf_net $hls_pin $sd_slave_pin
    connect_bd_intf_net $sd_master_pin $xbar_slave_pin
}
connect_bd_intf_net [get_bd_intf_pins data_xbar/M00_AXI] [get_bd_intf_pins data_dwidth/S_AXI]
connect_bd_intf_net [get_bd_intf_pins data_dwidth/M_AXI] [get_bd_intf_pins ps/S_AXI_HP0_FPD]
set hp0_net [get_bd_intf_nets -of_objects [get_bd_intf_pins data_dwidth/M_AXI]]
connect_bd_intf_net -intf_net $hp0_net \
    [get_bd_intf_pins data_dwidth/M_AXI] [get_bd_intf_pins hp0_monitor/MON_AXI]

connect_bd_net [get_bd_pins guard/shutdown_request] {*}[lmap sl $req_slices {get_bd_pins $sl/Din}]
for {set i 0} {$i < 6} {incr i} {
    set sd [lindex $shutdowns $i]
    set sl [lindex $req_slices $i]
    connect_bd_net [get_bd_pins $sl/Dout] [get_bd_pins $sd/request_shutdown]
    connect_bd_net [get_bd_pins $sd/in_shutdown] [get_bd_pins ack_all/In$i]
    connect_bd_net [get_bd_pins $sd/rd_in_shutdown] [get_bd_pins ack_rd/In$i]
    connect_bd_net [get_bd_pins $sd/wr_in_shutdown] [get_bd_pins ack_wr/In$i]
}
connect_bd_net [get_bd_pins ack_all/dout] [get_bd_pins guard/shutdown_ack]
connect_bd_net [get_bd_pins ack_rd/dout] [get_bd_pins guard/shutdown_rd_ack]
connect_bd_net [get_bd_pins ack_wr/dout] [get_bd_pins guard/shutdown_wr_ack]

foreach name {down_ar_fire down_r_fire down_rlast_fire down_rresp down_aw_fire down_wlast_fire down_b_fire down_bresp} {
    connect_bd_net [get_bd_pins hp0_monitor/$name] [get_bd_pins guard/$name]
}
connect_bd_net [get_bd_pins guard/hls_ap_start] [get_bd_pins hls/ap_start]
connect_bd_net [get_bd_pins hls/ap_done] [get_bd_pins guard/hls_ap_done]
connect_bd_net [get_bd_pins hls/ap_idle] [get_bd_pins guard/hls_ap_idle]
connect_bd_net [get_bd_pins hls/ap_ready] [get_bd_pins guard/hls_ap_ready]
connect_bd_net [get_bd_pins hls/protocol_error] [get_bd_pins guard/hls_protocol_error]
connect_bd_net [get_bd_pins hls/protocol_error_ap_vld] [get_bd_pins guard/hls_protocol_error_ap_vld]

# The PS HPM0 and HP0 ACLK pins are PL clock inputs.  V6/build007 drove both
# from a single PS PL output, proving they can share one PL clock domain.  This candidate
# selects the independently gated PL1 branch and inserts one clock wizard after pl_clk1 and keeps HPM0, HP0 and every PL AXI
# endpoint on the common DIVIDE=2 driver/job clock; no AXI CDC is implicit.
connect_bd_net [get_bd_pins $selected_ps_pl_clock_pin] [get_bd_pins clock_wiz/clk_in1]
connect_bd_net [get_bd_pins clock_wiz/clk_out1] [get_bd_pins half2x_clock_tree/root_clk_400]
connect_bd_net [get_bd_pins half2x_clock_tree/driver_job_clk_200] \
    [get_bd_pins ps/maxihpm0_fpd_aclk] [get_bd_pins ps/saxihp0_fpd_aclk] \
    [get_bd_pins ctrl_xbar/ACLK] [get_bd_pins ctrl_xbar/S00_ACLK] \
    [get_bd_pins ctrl_xbar/M00_ACLK] [get_bd_pins ctrl_xbar/M01_ACLK] \
    [get_bd_pins data_xbar/aclk] \
    [get_bd_pins data_dwidth/s_axi_aclk] \
    [get_bd_pins hls/ap_clk] [get_bd_pins guard/clk] [get_bd_pins reset/clk] \
    [get_bd_pins hp0_monitor/clk] [get_bd_pins platform_reset/slowest_sync_clk] \
    [get_bd_pins core_reset/slowest_sync_clk]
connect_bd_net [get_bd_pins half2x_clock_tree/pw_local_clk_400] \
    [get_bd_pins hls/pw_fast_clk] [get_bd_pins fast_core_reset/slowest_sync_clk]
foreach sd $shutdowns {connect_bd_net [get_bd_pins half2x_clock_tree/driver_job_clk_200] [get_bd_pins $sd/clk]}
connect_bd_net [get_bd_pins ps/pl_resetn0] [get_bd_pins reset/ps_resetn]
connect_bd_net [get_bd_pins reset/rst] [get_bd_pins platform_reset/ext_reset_in]
connect_bd_net [get_bd_pins clock_wiz/locked] \
    [get_bd_pins platform_reset/dcm_locked] [get_bd_pins core_reset/dcm_locked] \
    [get_bd_pins fast_core_reset/dcm_locked]
connect_bd_net [get_bd_pins const_zero/dout] \
    [get_bd_pins platform_reset/mb_debug_sys_rst] [get_bd_pins core_reset/mb_debug_sys_rst] \
    [get_bd_pins fast_core_reset/mb_debug_sys_rst]
connect_bd_net [get_bd_pins const_one/dout] [get_bd_pins platform_reset/aux_reset_in]
connect_bd_net [get_bd_pins platform_reset/peripheral_reset] [get_bd_pins guard/rst]
connect_bd_net [get_bd_pins platform_reset/peripheral_aresetn] \
    [get_bd_pins ctrl_xbar/ARESETN] [get_bd_pins ctrl_xbar/S00_ARESETN] \
    [get_bd_pins ctrl_xbar/M00_ARESETN] [get_bd_pins ctrl_xbar/M01_ARESETN] \
    [get_bd_pins data_xbar/aresetn] \
    [get_bd_pins data_dwidth/s_axi_aresetn] \
    [get_bd_pins hp0_monitor/resetn]
foreach sd $shutdowns {connect_bd_net [get_bd_pins platform_reset/peripheral_aresetn] [get_bd_pins $sd/resetn]}
connect_bd_net [get_bd_pins guard/core_reset_req] \
    [get_bd_pins core_reset/ext_reset_in] [get_bd_pins fast_core_reset/ext_reset_in]
connect_bd_net [get_bd_pins platform_reset/peripheral_aresetn] \
    [get_bd_pins fast_core_reset/aux_reset_in]
# Release the fast-domain synchronizer before the HLS/slow-domain synchronizer.
# This makes a slow-first reset release structurally impossible: the slow
# domain cannot accept a dot-product request while the fast half engine is
# still reset.  Both domains still assert from the same guard request.
connect_bd_net [get_bd_pins fast_core_reset/peripheral_aresetn] \
    [get_bd_pins core_reset/aux_reset_in]
connect_bd_net [get_bd_pins core_reset/peripheral_aresetn] [get_bd_pins hls/ap_rst_n] [get_bd_pins guard/core_reset_feedback_aresetn]
connect_bd_net [get_bd_pins fast_core_reset/peripheral_reset] [get_bd_pins hls/pw_fast_rst]

set hls_ctrl_seg [get_bd_addr_segs -of_objects [get_bd_intf_pins hls/s_axi_control]]
set guard_ctrl_seg [get_bd_addr_segs -of_objects [get_bd_intf_pins guard/S_AXI]]
if {[llength $hls_ctrl_seg] != 1 || [llength $guard_ctrl_seg] != 1} {error "Control register segments not unique"}
create_bd_addr_seg -range 64K -offset 0xA4000000 [get_bd_addr_spaces ps/Data] [lindex $hls_ctrl_seg 0] HLS_A400_64K
create_bd_addr_seg -range 64K -offset 0xA4010000 [get_bd_addr_spaces ps/Data] [lindex $guard_ctrl_seg 0] GUARD_A401_64K

set low_target [get_bd_addr_segs ps/SAXIGP2/HP0_DDR_LOW]
set high_target [get_bd_addr_segs ps/SAXIGP2/HP0_DDR_HIGH]
if {[llength $low_target] != 1 || [llength $high_target] != 1} {error "Both HP0 DDR target segments are required"}
set ddr_segment_count 0
for {set i 0} {$i < 6} {incr i} {
    set space [get_bd_addr_spaces -of_objects [get_bd_intf_pins hls/[lindex $hls_ifaces $i]]]
    if {[llength $space] != 1} {error "HLS master address space is not unique for index $i"}
    # IP Integrator requires a single coherent mapping per related DDR slave.
    # Decode the containing 1-GiB aperture; the driver contract is the stricter
    # [0x40000000,0x7ff00000) lease and never supplies the final 1 MiB to HLS.
    create_bd_addr_seg -range 1G -offset 0x40000000 $space $low_target DDR_LOW_$i
    create_bd_addr_seg -range 1G -offset 0x800000000 $space $high_target DDR_HIGH_$i
    incr ddr_segment_count 2
}
if {$ddr_segment_count != 12} {error "Expected exactly 12 V10 DDR address segments"}

# Full AXI capture is intentionally absent from the default release profile.
# Six 1024-deep monitor slots can consume the remaining BRAM headroom.  Enable
# only with DEBUG_PROFILE=full-master-ila after a resource-qualified build.
if {$enable_full_master_ila} {
    set sys_ila [create_bd_cell -type ip -vlnv xilinx.com:ip:system_ila:1.1 ila_masters]
    set_property -dict [list CONFIG.C_MON_TYPE INTERFACE CONFIG.C_NUM_MONITOR_SLOTS 6 CONFIG.C_NUM_OF_PROBES 1 CONFIG.C_DATA_DEPTH 1024 CONFIG.C_EN_STRG_QUAL 1] $sys_ila
    connect_bd_net [get_bd_pins half2x_clock_tree/driver_job_clk_200] [get_bd_pins ila_masters/clk]
    connect_bd_net [get_bd_pins platform_reset/peripheral_aresetn] [get_bd_pins ila_masters/resetn]
    for {set i 0} {$i < 6} {incr i} {
        set hls_net [get_bd_intf_nets -of_objects [get_bd_intf_pins hls/[lindex $hls_ifaces $i]]]
        connect_bd_intf_net -intf_net $hls_net \
            [get_bd_intf_pins hls/[lindex $hls_ifaces $i]] [get_bd_intf_pins ila_masters/SLOT_${i}_AXI]
    }
}

if {$enable_guard_ila} {
    set ila [create_bd_cell -type ip -vlnv xilinx.com:ip:ila:6.2 ila_guard]
    set widths {32 32 32 32 1 1 1}
    set ila_props [list CONFIG.C_MONITOR_TYPE Native CONFIG.C_NUM_OF_PROBES 7 CONFIG.C_DATA_DEPTH $native_ila_depth CONFIG.C_EN_STRG_QUAL true CONFIG.C_ADV_TRIGGER false]
    set idx 0
    foreach width $widths {lappend ila_props CONFIG.C_PROBE${idx}_WIDTH $width; incr idx}
    set_property -dict $ila_props $ila
    connect_bd_net [get_bd_pins half2x_clock_tree/driver_job_clk_200] [get_bd_pins ila_guard/clk]
    set probes {reset/heartbeat guard/debug_status guard/debug_error_flags hls/protocol_error guard/safe_to_reset guard/poisoned guard/core_reset_feedback_aresetn}
    set idx 0
    foreach p $probes {connect_bd_net [get_bd_pins ila_guard/probe$idx] [get_bd_pins $p]; incr idx}
}

# A dedicated native ILA proves that different physical stages carry different
# block IDs concurrently.  A 1024-sample triggered window is sufficient because
# each trace holds its current block/row/phase state while active.  The HLS trace
# contract only uses valid[31], block[20:16], row[13:8], and phase[5:0]; the
# omitted bits are zero for every legal trace value.  Pack those fields without
# decoding phase values to reduce the 12-probe capture payload from 384 to 216
# bits while retaining a lossless reconstruction for the frozen trace contract.
if {$enable_pipeline_ila} {
    set trace_pack [create_bd_cell -type module -reference fzv10_trace_pack trace_pack]
    set pipeline_ila [create_bd_cell -type ip -vlnv xilinx.com:ip:ila:6.2 ila_pipeline]
    set pipeline_props [list CONFIG.C_MONITOR_TYPE Native CONFIG.C_NUM_OF_PROBES 12 \
        CONFIG.C_DATA_DEPTH $native_ila_depth CONFIG.C_EN_STRG_QUAL true CONFIG.C_ADV_TRIGGER false]
    for {set i 0} {$i < 12} {incr i} {lappend pipeline_props CONFIG.C_PROBE${i}_WIDTH 18}
    set_property -dict $pipeline_props $pipeline_ila
    connect_bd_net [get_bd_pins half2x_clock_tree/driver_job_clk_200] [get_bd_pins ila_pipeline/clk]
    set trace_pins {trace_a_feed trace_a_dw3 trace_a_dw7 trace_a_pw1 trace_a_pw2 trace_a_write trace_b_feed trace_b_dw3 trace_b_dw7 trace_b_pw1 trace_b_pw2 trace_b_write}
    for {set i 0} {$i < 12} {incr i} {
        set trace_name [lindex $trace_pins $i]
        set packed_name [string map {trace_ packed_} $trace_name]
        connect_bd_net [get_bd_pins hls/$trace_name] [get_bd_pins trace_pack/$trace_name]
        connect_bd_net [get_bd_pins trace_pack/$packed_name] [get_bd_pins ila_pipeline/probe$i]
    }
}

# Static BD clock/reset audit.  Both PS AXI clock pins are inputs and are legal
# consumers of the same clock-wizard output.  This proves topology only; it does
# not prove that the selected candidate frequency works on the user's board.
foreach p {ps/maxihpm0_fpd_aclk ps/saxihp0_fpd_aclk} {
    set pin [get_bd_pins $p]
    if {[llength $pin] != 1 || [get_property DIR $pin] ne "I" || [get_property TYPE $pin] ne "clk"} {
        error "$p is not the expected PS AXI clock input"
    }
}
set candidate_clock_net [get_bd_nets -of_objects [get_bd_pins half2x_clock_tree/driver_job_clk_200]]
if {[llength $candidate_clock_net] != 1} {error "Candidate clock net is not unique"}
set fast_clock_net [get_bd_nets -of_objects [get_bd_pins half2x_clock_tree/pw_local_clk_400]]
if {[llength $fast_clock_net] != 1 || [lindex $fast_clock_net 0] eq [lindex $candidate_clock_net 0]} {
    error "Related fast clock net is absent or aliases the slow clock net"
}
set same_domain_pins {
    ps/maxihpm0_fpd_aclk ps/saxihp0_fpd_aclk hls/ap_clk
    ctrl_xbar/ACLK ctrl_xbar/S00_ACLK ctrl_xbar/M00_ACLK ctrl_xbar/M01_ACLK
    data_xbar/aclk data_dwidth/s_axi_aclk
    guard/clk hp0_monitor/clk reset/clk platform_reset/slowest_sync_clk
    core_reset/slowest_sync_clk
}
for {set i 0} {$i < 6} {incr i} {lappend same_domain_pins shutdown_$i/clk}
if {$enable_full_master_ila} {lappend same_domain_pins ila_masters/clk}
if {$enable_guard_ila} {lappend same_domain_pins ila_guard/clk}
if {$enable_pipeline_ila} {lappend same_domain_pins ila_pipeline/clk}
foreach p $same_domain_pins {
    set nets [get_bd_nets -of_objects [get_bd_pins $p]]
    if {[llength $nets] != 1 || [lindex $nets 0] ne [lindex $candidate_clock_net 0]} {
        error "Candidate single-clock-domain mismatch at $p"
    }
}
foreach p {hls/pw_fast_clk fast_core_reset/slowest_sync_clk} {
    set nets [get_bd_nets -of_objects [get_bd_pins $p]]
    if {[llength $nets] != 1 || [lindex $nets 0] ne [lindex $fast_clock_net 0]} {
        error "Half2x fast-clock mismatch at $p"
    }
}
set fast_reset_net [get_bd_nets -of_objects [get_bd_pins fast_core_reset/peripheral_reset]]
set hls_fast_reset_net [get_bd_nets -of_objects [get_bd_pins hls/pw_fast_rst]]
if {[llength $fast_reset_net] != 1 || $fast_reset_net ne $hls_fast_reset_net} {
    error "Half2x fast reset is not driven by the fast-domain reset synchronizer"
}
set fast_ready_net [get_bd_nets -of_objects [get_bd_pins fast_core_reset/peripheral_aresetn]]
set slow_aux_net [get_bd_nets -of_objects [get_bd_pins core_reset/aux_reset_in]]
if {[llength $fast_ready_net] != 1 || $fast_ready_net ne $slow_aux_net} {
    error "Slow core reset release is not sequenced after fast reset release"
}
set locked_net [get_bd_nets -of_objects [get_bd_pins clock_wiz/locked]]
foreach p {platform_reset/dcm_locked core_reset/dcm_locked fast_core_reset/dcm_locked} {
    set nets [get_bd_nets -of_objects [get_bd_pins $p]]
    if {[llength $nets] != 1 || [lindex $nets 0] ne [lindex $locked_net 0]} {
        error "Clock-wizard locked does not gate reset release at $p"
    }
}

set fd [open [file join $output clock-domain-candidate.rpt] w]
puts $fd "status=offline_candidate_not_board_verified"
puts $fd "candidate_requested_mhz=$candidate_mhz"
puts $fd "clock_contract=$clock_contract"
puts $fd "selected_ps_pl_clock_index=$selected_ps_pl_clock_index"
puts $fd "selected_ps_pl_clock_pin=$selected_ps_pl_clock_pin"
puts $fd "selected_ps_pl_clock_name=$selected_ps_pl_clock_name"
puts $fd "ps_bd_nominal_hz=$selected_ps_pl_freq_hz"
puts $fd "clock_wizard_prim_in_freq_mhz=$configured_clock_wiz_input_mhz"
puts $fd "historical_live_input_hz=$historical_live_input_hz"
puts $fd "historical_live_input_used_as_candidate_sta_assumption=true"
puts $fd "historical_live_input_is_current_board_proof=false"
puts $fd "live_pl1_target_raw_candidate=0x01010F00"
puts $fd "live_pl0_preserved_raw=0x01010802"
puts $fd "fresh_board_inventory_receipt_sha256=$board_inventory_sha"
puts $fd "expected_mmcm_m=$expected_mmcm_m"
puts $fd "expected_mmcm_d=$expected_mmcm_d"
puts $fd "clock_topology=mmcm_fast_plus_bufgce_div_v1"
puts $fd "logical_slow_equivalent_mmcm_divide=$expected_mmcm_o0"
puts $fd "expected_mmcm_fast_output_divide=$expected_mmcm_o1"
puts $fd "driver_job_bufgce_divide=2"
puts $fd "pw_local_bufgce_divide=1"
puts $fd "expected_live_output_hz=$expected_live_output_hz"
puts $fd "expected_live_fast_hz=$expected_live_fast_hz"
puts $fd "candidate_clock_net=$candidate_clock_net"
puts $fd "half2x_fast_clock_net=$fast_clock_net"
puts $fd "half2x_shared_mmcm_related_ratio=2"
puts $fd "half2x_sibling_bufgce_div_clocks=true"
puts $fd "half2x_clock_tree_continuous_enable=true"
puts $fd "half2x_consumer_reset_gated_by_mmcm_locked=true"
puts $fd "half2x_reset_release_order=fast_then_slow"
puts $fd "hpm0_hp0_hls_interconnect_shutdown_guard_monitor_same_domain=true"
puts $fd "clock_wizard_locked_gates_platform_slow_and_fast_core_reset=true"
puts $fd "vivado_validate_bd_design_invoked=true"
puts $fd "full_bd_gate=validate_bd_design_plus_exact_BD41_237_whitelist_plus_generate_target_plus_synthesis"
puts $fd "validate_skip_reason=none"
puts $fd "ps_ddr_mio_or_preset_changed=false"
puts $fd "board_pins_or_partpins_assigned=false"
puts $fd "debug_profile=$debug_profile"
puts $fd "full_master_system_ila_enabled=$enable_full_master_ila"
puts $fd "guard_native_ila_enabled=$enable_guard_ila"
puts $fd "pipeline_native_ila_enabled=$enable_pipeline_ila"
puts $fd "native_guard_and_trace_ila_depth=$native_ila_depth"
puts $fd "synthesis_threads_requested=16"
puts $fd "synth_design_threads_requested=8"
puts $fd "vivado_launch_jobs=8"
if {$debug_profile eq "release-no-ila"} {
    puts $fd "actual_capture_contract=no native ILA capture; 12 ap_none trace outputs are unconnected and not MMIO-readable"
} else {
    puts $fd "actual_capture_contract=save native Vivado .ila; .ltx is probe definition only"
}
puts $fd "TODO=require a fresh PL1 100 MHz raw/CCF proof before programming; historical PL0 inventory is not PL1 proof"
puts $fd "TODO=accept candidate frequency only after implemented M/D/O, generated-clock STA, CDC, timing and bus-skew gates"
close $fd

# The frozen A0005 candidate used the same six bidirectional DFX shutdown
# cells in front of a direction-pruned official AXI Crossbar.  Preserve the
# original BD messages and accept only the exact, reviewed metadata warnings;
# any new BD 41-237 body (especially FREQ_HZ) fails closed.
set expected_bd_41_237_messages {}
for {set i 0} {$i < 6} {incr i} {
    set mode [lindex $hls_modes $i]
    lappend expected_bd_41_237_messages [format {Bus Interface property READ_WRITE_MODE does not match between /data_xbar/S0%d_AXI(%s) and /shutdown_%d/M_AXI(READ_WRITE)} $i $mode $i]
    foreach user_prop {AWUSER_WIDTH ARUSER_WIDTH WUSER_WIDTH RUSER_WIDTH BUSER_WIDTH} {
        lappend expected_bd_41_237_messages [format {Bus Interface property %s does not match between /shutdown_%d/S_AXI(1) and /hls/%s(0)} $user_prop $i [lindex $hls_ifaces $i]]
    }
}
foreach user_prop {AWUSER_WIDTH ARUSER_WIDTH} {
    lappend expected_bd_41_237_messages [format {Bus Interface property %s does not match between /ctrl_xbar/s00_couplers/auto_pc/S_AXI(0) and /ps/M_AXI_HPM0_FPD(16)} $user_prop]
}
foreach user_prop {AWUSER_WIDTH ARUSER_WIDTH WUSER_WIDTH RUSER_WIDTH BUSER_WIDTH} {
    lappend expected_bd_41_237_messages [format {Bus Interface property %s does not match between /data_dwidth/S_AXI(0) and /data_xbar/M00_AXI(1)} $user_prop]
}
foreach user_prop {AWUSER_WIDTH ARUSER_WIDTH} {
    lappend expected_bd_41_237_messages [format {Bus Interface property %s does not match between /ps/S_AXI_HP0_FPD(1) and /data_dwidth/M_AXI(0)} $user_prop]
    lappend expected_bd_41_237_messages [format {Bus Interface property %s does not match between /hp0_monitor/MON_AXI(1) and /data_dwidth/M_AXI(0)} $user_prop]
}
set bd_warning_whitelist [file join $output bd-41-237-whitelist.txt]
set fd [open $bd_warning_whitelist w]
foreach message $expected_bd_41_237_messages {puts $fd $message}
close $fd
validate_bd_design
for {set i 0} {$i < 6} {incr i} {
    set expected_mode [lindex $hls_modes $i]
    set hls_pin [get_bd_intf_pins hls/[lindex $hls_ifaces $i]]
    set actual_mode [get_property CONFIG.READ_WRITE_MODE $hls_pin]
    if {$actual_mode ne $expected_mode} {
        error "V10 HLS data master $i direction mismatch expected=$expected_mode actual=$actual_mode"
    }
    foreach pin [list [get_bd_intf_pins shutdown_${i}/S_AXI] [get_bd_intf_pins shutdown_${i}/M_AXI]] {
        if {[get_property CONFIG.READ_WRITE_MODE $pin] ne "READ_WRITE"} {
            error "shutdown_$i safety shell unexpectedly lost bidirectional AXI coverage"
        }
    }
}
# Verify the direct official crossbar parameters rather than relying on HLS
# endpoint metadata that cannot propagate through a bidirectional shutdown IP.
# Read-only clients are SI 0/1/2/4 (mask 0x17), while write-only clients are
# SI 3/5 (mask 0x28).
set expected_read_connectivity {1 1 1 0 1 0}
set expected_write_connectivity {0 0 0 1 0 1}
for {set i 0} {$i < 6} {incr i} {
    set rp CONFIG.M00_S0${i}_READ_CONNECTIVITY
    set wp CONFIG.M00_S0${i}_WRITE_CONNECTIVITY
    set actual_r [get_property $rp $data_xbar]
    set actual_w [get_property $wp $data_xbar]
    if {$actual_r != [lindex $expected_read_connectivity $i] || $actual_w != [lindex $expected_write_connectivity $i]} {
        error "data_xbar SI$i connectivity mismatch read=$actual_r write=$actual_w"
    }
}
foreach {prop expected} {
    CONFIG.NUM_SI 6 CONFIG.NUM_MI 1 CONFIG.ADDR_RANGES 2
    CONFIG.ADDR_WIDTH 64 CONFIG.DATA_WIDTH 128 CONFIG.ID_WIDTH 4
    CONFIG.M00_A00_BASE_ADDR 0x0000000040000000 CONFIG.M00_A00_ADDR_WIDTH 30
    CONFIG.M00_A01_BASE_ADDR 0x0000000800000000 CONFIG.M00_A01_ADDR_WIDTH 30
} {
    if {[get_property $prop $data_xbar] ne $expected} {
        error "data_xbar property $prop mismatch expected=$expected actual=[get_property $prop $data_xbar]"
    }
}
foreach {prop expected} {
    CONFIG.PROTOCOL AXI4 CONFIG.READ_WRITE_MODE READ_WRITE
    CONFIG.ADDR_WIDTH 64 CONFIG.SI_DATA_WIDTH 128 CONFIG.MI_DATA_WIDTH 64
    CONFIG.SI_ID_WIDTH 4
} {
    if {[get_property $prop $data_dwidth] ne $expected} {
        error "data_dwidth property $prop mismatch expected=$expected actual=[get_property $prop $data_dwidth]"
    }
}
save_bd_design
write_bd_tcl [file join $output exact-bd.tcl]
set fd [open [file join $output address-map.rpt] w]
foreach space [get_bd_addr_spaces] {
    puts $fd "SPACE $space"
    foreach seg [get_bd_addr_segs -of_objects $space] {puts $fd "  $seg OFFSET=[get_property OFFSET $seg] RANGE=[get_property RANGE $seg]"}
}
close $fd
set fd [open [file join $output interface-widths.rpt] w]
foreach p {
    hls/m_axi_g_param1 hls/m_axi_g_param2 hls/m_axi_g_act_a_r
    hls/m_axi_g_act_a_w hls/m_axi_g_act_b_r hls/m_axi_g_act_b_w
    shutdown_0/S_AXI shutdown_0/M_AXI shutdown_1/S_AXI shutdown_1/M_AXI
    shutdown_2/S_AXI shutdown_2/M_AXI shutdown_3/S_AXI shutdown_3/M_AXI
    shutdown_4/S_AXI shutdown_4/M_AXI shutdown_5/S_AXI shutdown_5/M_AXI
    data_xbar/S00_AXI data_xbar/S01_AXI data_xbar/S02_AXI
    data_xbar/S03_AXI data_xbar/S04_AXI data_xbar/S05_AXI
    data_xbar/M00_AXI data_dwidth/S_AXI data_dwidth/M_AXI
    hp0_monitor/MON_AXI ps/S_AXI_HP0_FPD
} {
    set x [get_bd_intf_pins $p]
    puts $fd "$p ADDR=[get_property CONFIG.ADDR_WIDTH $x] DATA=[get_property CONFIG.DATA_WIDTH $x] ID=[get_property CONFIG.ID_WIDTH $x] MODE=[get_property CONFIG.READ_WRITE_MODE $x] MODE_SRC=[get_property CONFIG.READ_WRITE_MODE.VALUE_SRC $x]"
}
close $fd
set fd [open [file join $output v10-abi-wiring.rpt] w]
puts $fd "master_order=param1,param2,act_a_r,act_a_w,act_b_r,act_b_w"
puts $fd "shutdown_request_width=6"
puts $fd "shutdown_ack_register_layout=all\[5:0\]|read\[11:6\]|write\[17:12\]"
puts $fd "shutdown_complete_safe_value=0x0003ffff"
puts $fd "data_xbar_num_si=6"
puts $fd "data_xbar_si_modes=[join $hls_modes ,]"
puts $fd "data_fabric=official_axi_crossbar_plus_axi_dwidth_converter"
puts $fd "data_xbar_read_connectivity_mask=0x17"
puts $fd "data_xbar_write_connectivity_mask=0x28"
puts $fd "data_xbar_per_si_mmu_count=0"
puts $fd "data_dwidth_si_bits=128"
puts $fd "data_dwidth_mi_bits=64"
puts $fd "ddr_low_segments=6"
puts $fd "ddr_high_segments=6"
puts $fd "pipeline_trace_mmio_registers=0"
puts $fd "platform_trace_mmio_register_count=0"
puts $fd "hls_ap_none_trace_port_count=12"
puts $fd "trace_outputs_connected=[expr {$enable_pipeline_ila ? {true} : {false}}]"
puts $fd "pipeline_trace_transport=ap_none_output"
puts $fd "pipeline_trace_native_ila_enabled=$enable_pipeline_ila"
puts $fd "pipeline_trace_native_ila_probes=[expr {$enable_pipeline_ila ? 12 : 0}]"
puts $fd "pipeline_trace_source_width=32"
puts $fd "pipeline_trace_capture_width=18"
puts $fd "pipeline_trace_capture_layout=valid31|block20:16|row13:8|phase5:0"
puts $fd "pipeline_trace_reconstruction_zero_fields=30:21,15:14,7:6"
puts $fd "native_ila_depth=$native_ila_depth"
puts $fd "full_master_system_ila_enabled=$enable_full_master_ila"
puts $fd "guard_native_ila_enabled=$enable_guard_ila"
puts $fd "debug_profile=$debug_profile"
puts $fd "guard_id=$id_value"
puts $fd "guard_abi=$abi_value"
puts $fd "guard_caps=$caps_value"
close $fd
generate_target all [get_files cnn_pipeline_v10_shell.bd]
add_files [make_wrapper -files [get_files cnn_pipeline_v10_shell.bd] -top]
set_property top cnn_pipeline_v10_shell_wrapper [get_filesets sources_1]
update_compile_order -fileset sources_1

# Record the exact Vivado cache identity before any synthesis can start.  The
# HLS component must have one remote-cache match when reuse is required.
set cache_preflight [file join $output ip-cache-preflight.rpt]
set cache_preflight_fh [open $cache_preflight w]
puts $cache_preflight_fh "cache_directory=$shared_cache"
puts $cache_preflight_fh "hls_cache_reuse_required=$require_hls_cache_reuse"
set hls_cache_objects {}
foreach ip [lsort [get_ips -quiet]] {
    set ip_name [get_property NAME $ip]
    set ip_vlnv [get_property IPDEF $ip]
    set cache_id [config_ip_cache -get_id $ip]
    set cache_match [config_ip_cache -cache_has_match $ip]
    puts $cache_preflight_fh "ip=$ip_name vlnv=$ip_vlnv cache_id=$cache_id cache_has_match=$cache_match"
    if {[string match {*:hls:cnn_pipeline_v10:*} $ip_vlnv]} {lappend hls_cache_objects $ip}
}
if {[llength $hls_cache_objects] != 1} {
    close $cache_preflight_fh
    error "Expected exactly one cnn_pipeline_v10 HLS IP cache object, got [llength $hls_cache_objects]"
}
set hls_cache_match [config_ip_cache -cache_has_match [lindex $hls_cache_objects 0]]
if {![info exists ::env(FZV10_EXPECTED_HLS_CACHE_ID)] || ![regexp {^[0-9a-f]{16}$} $::env(FZV10_EXPECTED_HLS_CACHE_ID)]} {
    error "A0005 expected HLS cache ID was not supplied by the runner"
}
set expected_fused_hls_cache_id $::env(FZV10_EXPECTED_HLS_CACHE_ID)
if {$expected_fused_hls_cache_id in {bb03f320fa66fdbd f9f312cb538ccb2e 3ee230f7a9b2909b}} {
    error "A0005 platform synthesis refuses a historical A0004 HLS cache ID"
}
set hls_cache_id [config_ip_cache -get_id [lindex $hls_cache_objects 0]]
puts $cache_preflight_fh "expected_fused_hls_cache_id=$expected_fused_hls_cache_id"
puts $cache_preflight_fh "hls_cache_id=$hls_cache_id"
puts $cache_preflight_fh "hls_cache_has_match=$hls_cache_match"
close $cache_preflight_fh
if {$hls_cache_id ne $expected_fused_hls_cache_id} {
    error "Fused HLS cache identity mismatch: got $hls_cache_id expected $expected_fused_hls_cache_id"
}
if {$require_hls_cache_reuse && $hls_cache_match eq {}} {
    error "Qualified cnn_pipeline_v10 HLS IP has no official remote-cache match"
}

# Keep the Clocking Wizard's PRIM_IN_FREQ at the PS BD nominal metadata, but
# analyze the master clock using the separately frozen historical live-input
# contract.  This does not change the PS FCLK or claim the value is current.
set measured_xdc [file join $output offline-pl1-100mhz-candidate-sta.xdc]
set fd [open $measured_xdc w]
puts $fd [format {create_clock -period %.9f -waveform {0 %.9f} -name clk_pl_1 [get_pins [get_property SOURCE_PINS [get_clocks clk_pl_1]]]} \
    $historical_live_input_period_ns [expr {$historical_live_input_period_ns / 2.0}]]
close $fd
add_files -fileset constrs_1 $measured_xdc
set_property PROCESSING_ORDER LATE [get_files $measured_xdc]
if {[info exists ::env(FZV10_VALIDATE_ONLY)] && $::env(FZV10_VALIDATE_ONLY) eq "1"} {
    set fd [open [file join $output validate-only-run-status.rpt] w]
    puts $fd "scope=bd_generation_and_metadata_validation_only"
    puts $fd "launch_synth_or_impl=false"
    puts $fd "synthesis_threads_requested=16"
    puts $fd "synth_design_threads_requested=8"
    puts $fd "vivado_launch_jobs=8"
    foreach run [get_runs] {
        set run_status [get_property STATUS $run]
        set run_progress [get_property PROGRESS $run]
        puts $fd "run=$run status=$run_status progress=$run_progress"
        if {$run_progress ne "0%"} {
            close $fd
            error "Validate-only mode found an executed run: $run status=$run_status progress=$run_progress"
        }
    }
    close $fd
    close_project
    exit 0
}

set parent_process_id [pid]
set synth_run [get_runs synth_1]
set child_thread_evidence [file join $output synth-child-thread-readback.txt]
set child_thread_parameter_report [file join $output synth-child-thread-parameters.rpt]
set child_thread_pre_hook [file join $output synth-child-thread-prehook.tcl]
set hook_fh [open $child_thread_pre_hook w]
puts $hook_fh {set_param general.maxThreads 16}
puts $hook_fh {set_param synth.maxThreads 8}
puts $hook_fh {if {[get_param general.maxThreads] != 16} {error {child general.maxThreads readback mismatch}}}
puts $hook_fh {if {[get_param synth.maxThreads] != 8} {error {child synth.maxThreads readback mismatch}}}
puts $hook_fh [list set child_thread_evidence $child_thread_evidence]
puts $hook_fh [list set child_thread_parameter_report $child_thread_parameter_report]
puts $hook_fh {set child_thread_fh [open $child_thread_evidence w]}
puts $hook_fh {puts $child_thread_fh "scope=synth_design_child_pre_hook"}
puts $hook_fh {puts $child_thread_fh "child_process_id=[pid]"}
puts $hook_fh {puts $child_thread_fh "general_threads_readback=[get_param general.maxThreads]"}
puts $hook_fh {puts $child_thread_fh "synth_threads_readback=[get_param synth.maxThreads]"}
puts $hook_fh {puts $child_thread_fh "effective_algorithm_threads_proven=false"}
puts $hook_fh {close $child_thread_fh}
puts $hook_fh {report_param -file $child_thread_parameter_report {general.maxThreads}}
puts $hook_fh {report_param -append -file $child_thread_parameter_report {synth.maxThreads}}
puts $hook_fh {puts "CNN_V10_PLATFORM_SYNTH_CHILD_THREADS general=[get_param general.maxThreads] synth=[get_param synth.maxThreads] pid=[pid]"}
close $hook_fh
set_property STEPS.SYNTH_DESIGN.TCL.PRE $child_thread_pre_hook $synth_run
launch_runs synth_1 -jobs 8
wait_on_run synth_1
if {![string match {*Complete*} [get_property STATUS [get_runs synth_1]]]} {error "Synthesis failed"}
set cache_post [file join $output ip-cache-post-synth.rpt]
set cache_post_fh [open $cache_post w]
puts $cache_post_fh "cache_directory=$shared_cache"
puts $cache_post_fh "hls_cache_reuse_required=$require_hls_cache_reuse"
set hls_cache_used [config_ip_cache -cache_was_used [lindex $hls_cache_objects 0]]
puts $cache_post_fh "hls_cache_was_used=$hls_cache_used"
foreach ip [lsort [get_ips -quiet]] {
    puts $cache_post_fh "ip=[get_property NAME $ip] cache_id=[config_ip_cache -get_id $ip] cache_was_used=[config_ip_cache -cache_was_used $ip]"
}
close $cache_post_fh
if {$require_hls_cache_reuse && !$hls_cache_used} {
    error "Qualified cnn_pipeline_v10 HLS IP cache entry was not used by synthesis"
}
if {![file isfile $child_thread_evidence]} {error "Synthesis child did not write thread readback evidence"}
set child_thread_fh [open $child_thread_evidence r]
set child_thread_text [read $child_thread_fh]
close $child_thread_fh
foreach required_line {scope=synth_design_child_pre_hook general_threads_readback=16 synth_threads_readback=8} {
    if {[string first $required_line $child_thread_text] < 0} {error "Synthesis child thread evidence is missing: $required_line"}
}
if {![regexp {child_process_id=([0-9]+)} $child_thread_text ignored child_process_id] || $child_process_id == $parent_process_id} {
    error "Synthesis PRE hook did not run in a distinct child Vivado process"
}
set_param general.maxThreads 16
if {[get_param general.maxThreads] != 16} {error "Vivado post-synthesis maxThreads readback mismatch"}
open_run synth_1
# Preserve the expensive synthesis result before any report or metadata gate.
write_checkpoint -force [file join $output cnn-pipeline-v10-candidate-post-synth.dcp]
set master_clock [get_clocks -quiet $selected_ps_pl_clock_name]
if {[llength $master_clock] != 1 || abs([get_property PERIOD $master_clock] - $historical_live_input_period_ns) > 0.001} {
    error "Historical live-input STA contract is missing or does not match $selected_ps_pl_clock_name"
}
if {[llength [get_ports]] != 0} {error "Unexpected external PL pins"}
report_utilization -file [file join $output post-synth-utilization.rpt]
report_timing_summary -file [file join $output post-synth-timing.rpt]
if {$run_scope eq "synth-only"} {
    set fd [open [file join $output synth-only-run-status.rpt] w]
    puts $fd "scope=post_synthesis_resource_and_timing_validation_only"
    puts $fd "implementation_launched=false"
    puts $fd "combined_parameter_manifest_sha256=$combined_manifest_sha"
    puts $fd "source_manifest_sha256=[sha256_file $source_manifest_source]"
    puts $fd "candidate_contract_sha256=[sha256_file $candidate_contract_source]"
    puts $fd "structure_audit_sha256=$expected_structure_audit_sha"
    puts $fd "hls002_receipt_sha256=[sha256_file $hls002_receipt_source]"
    puts $fd "apready_patched002_receipt_sha256=[sha256_file $apready_receipt_source]"
    puts $fd "fused_transform_receipt_sha256=[sha256_file $transform_receipt_source]"
    puts $fd "frozen_structure_receipt_sha256=[sha256_file $frozen_structure_receipt_source]"
    close $fd
    close_project
    puts "CNN_PIPELINE_V10_SYNTH_ONLY_COMPLETE_OFFLINE_CANDIDATE"
    exit 0
}
