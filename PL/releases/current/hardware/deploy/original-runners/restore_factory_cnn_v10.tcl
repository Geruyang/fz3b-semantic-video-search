# Restore the exact saved factory PL image without resetting PS.
if {$argc != 1} {error "Need exact factory native bin"}
set restore [lindex $argv 0]
if {![file isfile $restore]} {error "Missing exact factory native bin: $restore"}
proc stamp {message} {puts "[clock format [clock seconds] -gmt 1 -format {%Y-%m-%dT%H:%M:%SZ}] $message";flush stdout}
proc config_ok {device stage} {
    refresh_hw_device $device
    foreach {property expected} {
        {REGISTER.CONFIG_STATUS.BIT[00]_CRC_ERROR} 0 {REGISTER.CONFIG_STATUS.BIT[04]_END_OF_STARTUP_(EOS)_STATUS} 1
        {REGISTER.CONFIG_STATUS.BIT[13]_DONE_INTERNAL_SIGNAL_STATUS} 1 {REGISTER.CONFIG_STATUS.BIT[14]_DONE_PIN} 1
        {REGISTER.CONFIG_STATUS.BIT[15]_IDCODE_ERROR} 0 {REGISTER.CONFIG_STATUS.BIT[16]_SECURITY_ERROR} 0
        {REGISTER.CONFIG_STATUS.BIT[27]_SECURITY_AUTH_ERROR} 0 {REGISTER.CONFIG_STATUS.BIT[29]_BAD_PACKET_ERROR} 0
    } {set value [get_property $property $device];stamp "$stage $property=$value";if {$value != $expected} {error "Unexpected $property=$value"}}
}
set connected 0;set opened 0;set target {};set old_frequency {}
open_hw_manager
set rc [catch {
    stamp "CNN_V10_FACTORY_RESTORE_BEGIN VIVADO=[version -short] FILE=$restore mpsoc_reset=no"
    connect_hw_server -url localhost:3121;set connected 1
    set targets [get_hw_targets];set expected "localhost:3121/xilinx_tcf/Digilent/210251190311"
    if {[llength $targets] != 1 || [lindex $targets 0] ne $expected} {error "Exact target changed: $targets"}
    set target [lindex $targets 0];set old_frequency [get_property PARAM.FREQUENCY $target];set_property PARAM.FREQUENCY 5000000 $target
    open_hw_target $target;set opened 1
    set devices [get_hw_devices xczu3_0 -of_objects $target];if {[llength $devices] != 1} {error "PL device not unique"}
    set device [lindex $devices 0];if {[get_property IDCODE_HEX $device] ne "14710093"} {error "IDCODE changed"}
    set_property PROBES.FILE {} $device;set_property FULL_PROBES.FILE {} $device;set_property PROGRAM.FILE $restore $device
    program_hw_devices -mpsoc_reset no $device
    config_ok $device FACTORY;refresh_hw_device $device
    stamp "CNN_V10_FACTORY_DEBUG_CORES=[llength [get_hw_ilas -quiet -of_objects $device]]"
    stamp "CNN_V10_FACTORY_RESTORE_OK mpsoc_reset=no"
} message options]
if {$rc} {stamp "CNN_V10_FACTORY_RESTORE_ERROR MESSAGE=$message";puts stderr [dict get $options -errorinfo]}
if {$old_frequency ne {}} {if {[catch {set_property PARAM.FREQUENCY $old_frequency $target}]} {set rc 9}}
if {$opened} {if {[catch {close_hw_target $target}]} {set rc 10}}
if {$connected} {if {[catch {disconnect_hw_server}]} {set rc 10}}
if {[catch {close_hw_manager}]} {set rc 10}
stamp "CNN_V10_FACTORY_RESTORE_END RC=$rc FACTORY_RESTORED=[expr {!$rc}]"
exit $rc
