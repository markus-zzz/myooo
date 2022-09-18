#!/bin/bash

for tpath in ../thirdparty/riscv-tests/isa/rv32ui/*.S; do
  echo $tpath;
  tname=$(basename $tpath .S)
  clang --target=riscv64-unknown-elf -mabi=ilp32 -march=rv32i -o $tname.out  $tpath -I. -I../thirdparty/riscv-tests/isa/macros/scalar/ -nostdlib -Wl,--build-id=none,-Bstatic,-T,sections.lds
  llvm-objcopy --only-section=.mem --output-target=binary $tname.out $tname.bin
done
