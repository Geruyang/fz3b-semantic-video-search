.syntax unified
.cpu cortex-r5
.arm
.section .vectors,"ax"
.global _start
_start:
    b reset
    b .
    b .
    b .
    b .
    b .
    b .
    b .
.section .text
reset:
    cpsid if
    cps #0x13
    ldr sp, =0xfff0
    ldr r0, =__bss_start
    ldr r1, =__bss_end
    mov r2, #0
1:  cmp r0, r1
    strlo r2, [r0], #4
    blo 1b
    bl main
    b .
