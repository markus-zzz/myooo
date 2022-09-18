MEMORY {
  MEM : ORIGIN = 0K, LENGTH = 8K
}

SECTIONS {
  .mem : {
    . = 0x000000;
    start*(.text);
    *(.text);
    end = .;
    . = ALIGN(4);
    . += 16;
    *(.data);
    end = .;
    . = ALIGN(4);
  } > MEM
}
