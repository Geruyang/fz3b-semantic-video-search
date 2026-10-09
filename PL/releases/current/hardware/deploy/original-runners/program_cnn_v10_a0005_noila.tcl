# Official Vivado Hardware Manager PL-only programming for the A0005
# release-no-ILA image, with an exact native factory fallback.
# args: exact_bit exact_factory_native_bin new_output_directory
if {$argc != 3} {error "Need bit, native factory bin, output directory"}
lassign $argv bit restore output
foreach input [list $bit $restore] {
    if {![file isfile $input]} {error "Missing exact input: $input"}
}
if {[file exists $output]} {error "Evidence directory must be new: $output"}
file mkdir $output

proc stamp {message} {
    puts "[clock format [clock seconds] -gmt 1 -format {%Y-%m-%dT%H:%M:%SZ}] $message"
    flush stdout
}
proc config_ok {device stage} {
    refresh_hw_device $device
    foreach {property expected} {
        {REGISTER.CONFIG_STATUS.BIT[00]_CRC_ERROR} 0
        {REGISTER.CONFIG_STATUS.BIT[04]_END_OF_STARTUP_(EOS)_STATUS} 1
        {REGISTER.CONFIG_STATUS.BIT[13]_DONE_INTERNAL_SIGNAL_STATUS} 1
        {REGISTER.CONFIG_STATUS.BIT[14]_DONE_PIN} 1
        {REGISTER.CONFIG_STATUS.BIT[15]_IDCODE_ERROR} 0
        {REGISTER.CONFIG_STATUS.BIT[16]_SECURITY_ERROR} 0
        {REGISTER.CONFIG_STATUS.BIT[27]_SECURITY_AUTH_ERROR} 0
        {REGISTER.CONFIG_STATUS.BIT[29]_BAD_PACKET_ERROR} 0
    } {
        if {[lsearch -exact [list_property $device] $property] < 0} {
            error "Required status missing: $property"
        }
        set value [get_property $property $device]
        stamp "$stage $property=$value"
        if {$value != $expected} {error "Unexpected configuration $property=$value"}
    }
}
proc factory_restore {device restore} {
    stamp "FACTORY_RESTORE_BEGIN mpsoc_reset=no"
    set_property PROBES.FILE {} $device
    set_property FULL_PROBES.FILE {} $device
    set_property PROGRAM.FILE $restore $device
    program_hw_devices -mpsoc_reset no $device
    config_ok $device FACTORY
    stamp FACTORY_RESTORE_OK
}

set connected 0
set opened 0
set modified 0
set restored 0
set target {}
set old_frequency {}
open_hw_manager
set rc [catch {
    stamp "CNN_V10_A0005_NOILA_PROGRAM_BEGIN VIVADO=[version -short] BIT=$bit mpsoc_reset=no"
    connect_hw_server -url localhost:3121
    set connected 1
    set targets [get_hw_targets]
    set expected "localhost:3121/xilinx_tcf/Digilent/210251190311"
    if {[llength $targets] != 1 || [lindex $targets 0] ne $expected} {
        error "Exact target changed: $targets"
    }
    set target [lindex $targets 0]
    set old_frequency [get_property PARAM.FREQUENCY $target]
    set_property PARAM.FREQUENCY 5000000 $target
    if {[get_property PARAM.FREQUENCY $target] != 5000000} {error "JTAG frequency mismatch"}
    open_hw_target $target
    set opened 1
    set devices [get_hw_devices xczu3_0 -of_objects $target]
    if {[llength $devices] != 1} {error "Exact PL device not unique: $devices"}
    set device [lindex $devices 0]
    if {[get_property IDCODE_HEX $device] ne "14710093"} {error "IDCODE changed"}
    config_ok $device BEFORE
    set_property PROBES.FILE {} $device
    set_property FULL_PROBES.FILE {} $device
    set_property PROGRAM.FILE $bit $device
    set modified 1
    program_hw_devices -mpsoc_reset no $device
    config_ok $device V10_A0005
    refresh_hw_device $device
    set ilas [get_hw_ilas -quiet -of_objects $device]
    if {[llength $ilas] != 0} {error "release-no-ila image exposed unexpected ILAs: $ilas"}
    stamp "CNN_V10_A0005_NOILA_PROGRAM_OK ILA_COUNT=0 MODIFIED=1 FACTORY_RESTORED=0"
} message options]
if {$rc} {
    stamp "CNN_V10_A0005_NOILA_PROGRAM_ERROR MESSAGE=$message"
    puts stderr [dict get $options -errorinfo]
    if {$modified} {
        set recovery [catch {factory_restore $device $restore; set restored 1} recovery_message recovery_options]
        if {$recovery} {
            stamp "DO_NOT_BIND RESTORE_FAILED=$recovery_message"
            puts stderr [dict get $recovery_options -errorinfo]
            set rc 8
        }
    }
}
if {$old_frequency ne {}} {
    if {[catch {set_property PARAM.FREQUENCY $old_frequency $target}]} {set rc 9}
}
if {$opened} {if {[catch {close_hw_target $target}]} {set rc 10}}
if {$connected} {if {[catch {disconnect_hw_server}]} {set rc 10}}
if {[catch {close_hw_manager}]} {set rc 10}
stamp "CNN_V10_A0005_NOILA_PROGRAM_END RC=$rc MODIFIED=$modified FACTORY_RESTORED=$restored"
exit $rc
