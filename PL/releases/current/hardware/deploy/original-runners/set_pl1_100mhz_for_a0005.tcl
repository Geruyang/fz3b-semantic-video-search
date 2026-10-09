# A0005 board transaction: move the otherwise idle PL1 branch from its
# factory-gated value to the already qualified 100 MHz setting and leave it
# running for the immediately following PL-only download.  Run only while the
# network owner holds the reviewed IOPLL lease and has issued a fresh READY.
# Official XSDB memory service only; no halt, reset, download, AIB or force.
set PL0_REF_CTRL 0xFF5E00C0
set PL1_REF_CTRL 0xFF5E00C4
set PL2_REF_CTRL 0xFF5E00C8
set PL3_REF_CTRL 0xFF5E00CC
set IOPLL_CTRL   0xFF5E0020
set RPLL_CTRL    0xFF5E0030
set PLL_STATUS   0xFF5E0040
set DDR_CTRL     0xFD1A0080
set EXPECTED_PL0 0x01010802
set EXPECTED_PL1 0x00052000
set EXPECTED_PL2 0x00052000
set EXPECTED_PL3 0x00052000
set PL1_TARGET_GATED 0x00010F00
set PL1_TARGET_ENABLED 0x01010F00
set EXPECTED_IOPLL 0x00015A00
set EXPECTED_RPLL 0x00013000
set EXPECTED_DDR 0x01000200
set EXPECTED_PLL_STATUS 0x0000001B

proc read32 {name addr} {
    set word [lindex [mrd -value -size w $addr 1] 0]
    puts [format "READ_OK name=%s addr=0x%08X value=0x%08X" $name $addr $word]
    return $word
}
proc write32 {name addr value} {
    puts [format "WRITE_BEGIN name=%s addr=0x%08X value=0x%08X" $name $addr $value]
    mwr -bypass-cache-sync -size w $addr $value
    puts [format "WRITE_RETURN name=%s addr=0x%08X value=0x%08X" $name $addr $value]
}
proc read_twice_exact {name addr expected} {
    set a [read32 "${name}_1" $addr]
    after 1
    set b [read32 "${name}_2" $addr]
    if {$a != $expected || $b != $expected} {
        error [format "%s mismatch expected=0x%08X actual=0x%08X/0x%08X" $name $expected $a $b]
    }
}
proc fixed_state_exact {tag} {
    read_twice_exact "${tag}_PL0" $::PL0_REF_CTRL $::EXPECTED_PL0
    read_twice_exact "${tag}_PL2" $::PL2_REF_CTRL $::EXPECTED_PL2
    read_twice_exact "${tag}_PL3" $::PL3_REF_CTRL $::EXPECTED_PL3
    read_twice_exact "${tag}_IOPLL" $::IOPLL_CTRL $::EXPECTED_IOPLL
    read_twice_exact "${tag}_RPLL" $::RPLL_CTRL $::EXPECTED_RPLL
    read_twice_exact "${tag}_DDR" $::DDR_CTRL $::EXPECTED_DDR
    read_twice_exact "${tag}_PLL_STATUS" $::PLL_STATUS $::EXPECTED_PLL_STATUS
}

connect -url tcp:localhost:3121
puts "XSDB_A0005_PL1_100MHZ_HOLD_BEGIN HALT=0 RESET=0 DOWNLOAD=0 FORCE=0 AIB=0"
set a53_pre [targets -filter {name == "Cortex-A53 #0"} -target-properties]
puts "A53_PRE=$a53_pre"
if {[string first {state_reason Running} $a53_pre] < 0} {disconnect; error "A53 #0 is not Running before transaction"}
targets -set -filter {target_id == 4}
set active_target [targets]
if {![regexp {(^|\n)[[:space:]]*4\*?[[:space:]]+PSU([[:space:]]|$)} $active_target]} {disconnect; error "Active target is not target_id 4 PSU/DAP"}
fixed_state_exact ENTRY
read_twice_exact ENTRY_PL1 $PL1_REF_CTRL $EXPECTED_PL1

set txn_rc [catch {
    write32 PL1_TARGET_GATED $PL1_REF_CTRL $PL1_TARGET_GATED
    read_twice_exact TARGET_GATED $PL1_REF_CTRL $PL1_TARGET_GATED
    write32 PL1_TARGET_ENABLED $PL1_REF_CTRL $PL1_TARGET_ENABLED
    read_twice_exact TARGET_ENABLED $PL1_REF_CTRL $PL1_TARGET_ENABLED
    after 50
    fixed_state_exact TARGET_HOLD
    read_twice_exact TARGET_HOLD_PL1 $PL1_REF_CTRL $PL1_TARGET_ENABLED
    set a53_post [targets -filter {name == "Cortex-A53 #0"} -target-properties]
    puts "A53_POST=$a53_post"
    if {[string first {state_reason Running} $a53_post] < 0} {error "A53 #0 is not Running after transaction"}
} txn_error txn_opts]
if {$txn_rc} {
    puts "TRANSACTION_ERROR=$txn_error"
    set cleanup_errors {}
    set restore_rc [catch {
        write32 PL1_RESTORE_AFTER_ERROR $PL1_REF_CTRL $EXPECTED_PL1
        read_twice_exact RESTORE_AFTER_ERROR $PL1_REF_CTRL $EXPECTED_PL1
        fixed_state_exact CLEANUP
    } restore_error restore_opts]
    if {$restore_rc} {
        lappend cleanup_errors "PL1:$restore_error"
        puts "QUARANTINE_PL1_RESTORE_NOT_CONFIRMED"
    }
    set a53_fail [targets -filter {name == "Cortex-A53 #0"} -target-properties]
    puts "A53_AFTER_ERROR=$a53_fail"
    puts "CLEANUP_ERRORS=$cleanup_errors"
    disconnect
    error "A0005 PL1 hold transaction failed; cleanup_errors=$cleanup_errors"
}
puts "READY_PL1_100MHZ_HELD PL1=0x01010F00 PL0_UNCHANGED=1 HALT=0 RESET=0 DOWNLOAD=0 FORCE=0 AIB=0"
disconnect
exit
