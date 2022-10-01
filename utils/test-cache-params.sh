#!/bin/bash
for ((i=1;i<=6;i++));
do
  echo "=================================="
  echo "Testing with cfgAddrIndexBits = $i"
  echo "----------------------------------"
  sed -i "s/^cfgAddrIndexBits = [0-9]$/cfgAddrIndexBits = $i/" components/Cache.py
  git diff
  time ./build-myooo-verilator.sh
  time ./myooo-sim tests-riscv/*.bin
done
