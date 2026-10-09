ENTRY(_start)
MEMORY { ATCM (rwx) : ORIGIN = 0, LENGTH = 64K }
SECTIONS {
 .vectors : { KEEP(*(.vectors)) } > ATCM
 .text : { *(.text*) *(.rodata*) } > ATCM
 .data : { *(.data*) } > ATCM
 .bss (NOLOAD) : { . = ALIGN(4); __bss_start = .; *(.bss*) *(COMMON); . = ALIGN(4); __bss_end = .; } > ATCM
 /DISCARD/ : { *(.comment*) *(.ARM.exidx*) *(.ARM.extab*) }
 ASSERT(__bss_end < 0xe000, "TCM firmware collides with stack")
}
