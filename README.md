# [WIP] MyOoO - My Out of Order RISC-V CPU [WIP] #

This is my go at designing an out-of-order RISC-V (RV32I) CPU for educational
purposes. The chosen language for the implementation is [Amaranth
HDL](https://github.com/amaranth-lang/amaranth) and the current target is
simulation only though the code in theory should be synthesizable. For a FPGA
target I imagine that some effort would need to be spent to add pipeline stages
and rebalance signals paths as well as well as more thoroughly consider the
number of access ports on certain resources.

## Setup Amaranth

The implementation makes heavy use of a currently unreleased Amaranth library
for handling aggregate data structures found in [[RFC] Aggregate data structure
library #693](https://github.com/amaranth-lang/amaranth/issues/693). The
following instructions (slightly modified from the [official install
guide](https://amaranth-lang.org/docs/amaranth/latest/install.html)) should set
up a working environment

```
$ git clone https://github.com/amaranth-lang/amaranth
$ cd amaranth
$ git checkout rfc-issue-693
$ pip3 install --user --editable '.[builtin-yosys]'
```

## Get RISC-V ISA tests

The repository contains a sub-module of the official RISC-V ISA test for RV32I
instruction set (among all the others). Make sure that it was properly fetched.

```
$ git submodule update --init --recursive
```

Then prepare a memory image (`*.bin`) for each of the tests.

```
$ pushd tests-riscv/
$ ./build-all.sh
$ popd
```

## Simulation (Amaranth)

To run the test-suite with Amaranth's built in RTL simulator (convenient but a
bit slow).

```
$ python3 myooo-tester.py tests-riscv/*.bin
```

## Simulation (Verilator)

To run the Verilator based simulation one needs to first build the simulator
executable (which itself is quite slow).

```
$ ./build-myooo-verilator.sh
```

Running the actual simulation is now much faster.

```
$ ./myooo-sim tests-riscv/*.bin
```
