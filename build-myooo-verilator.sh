#!/bin/bash

set -e

OBJ_DIR=obj_dir_myooo
rm -rf $OBJ_DIR

echo "Amaranth HDL..."
python3 myooo-verilog.py
echo "Verilator..."
verilator -trace -cc myooo.v +1364-2005ext+v --top-module top -Wno-fatal --Mdir $OBJ_DIR

VERILATOR_ROOT=/usr/share/verilator/
cd $OBJ_DIR; make -f Vtop.mk; cd ..
g++ -std=c++14 myooo-sim.cpp $OBJ_DIR/Vtop__ALL.a -I$OBJ_DIR -I $VERILATOR_ROOT/include/ -I $VERILATOR_ROOT/include/vltstd $VERILATOR_ROOT/include/verilated.cpp $VERILATOR_ROOT/include/verilated_vcd_c.cpp -Werror -o myooo-sim -O3
