# Copyright 2022 Markus Lavin (https://www.zzzconsulting.se/).
#
# This source describes Open Hardware and is licensed under the CERN-OHL-P v2.
#
# You may redistribute and modify this documentation and make products using it
# under the terms of the CERN-OHL-P v2 (https:/cern.ch/cern-ohl).  This
# documentation is distributed WITHOUT ANY EXPRESS OR IMPLIED WARRANTY,
# INCLUDING OF MERCHANTABILITY, SATISFACTORY QUALITY AND FITNESS FOR A
# PARTICULAR PURPOSE. Please see the CERN-OHL-P v2 for applicable conditions.

from amaranth import *
from amaranth.sim import Simulator
from myooo import MyOoO
import sys
import os
import tempfile

from components.Utils import *
from components.Cache import *


class Top(Elaboratable):

  def __init__(self, memInitBin):
    self.memInitBin = memInitBin
    self.o_ebreak = Signal()

  def elaborate(self, platform):
    m = Module()

    m.submodules.u_myooo = u_myooo = MyOoO()
    m.submodules.u_mem = u_mem = SlowMemory(self.memInitBin)
    self.u_myooo = u_myooo

    m.d.comb += [
        # WishBone IF
        u_mem.i_wb_adr.eq(u_myooo.o_wb_adr),
        u_mem.i_wb_dat.eq(u_myooo.o_wb_dat),
        u_mem.i_wb_sel.eq(u_myooo.o_wb_sel),
        u_mem.i_wb_cti.eq(u_myooo.o_wb_cti),
        u_mem.i_wb_we.eq(u_myooo.o_wb_we),
        u_mem.i_wb_stb.eq(u_myooo.o_wb_stb),
        u_mem.i_wb_cyc.eq(u_myooo.o_wb_cyc),
        u_myooo.i_wb_dat.eq(u_mem.o_wb_dat),
        u_myooo.i_wb_ack.eq(u_mem.o_wb_ack),
        # Misc
        self.o_ebreak.eq(u_myooo.o_ebreak)
    ] # yapf: disable
    return m


def run_test(inputBinPath):

  dut = Top(memInitBin='{}'.format(inputBinPath))
  failed = False
  cycles = 0

  def bench():
    # Simulate for at most N cycles or until EBREAK occurs.
    nonlocal cycles
    for idx in range(2*2500):
      yield
      cycles = idx + 1
      ebreak = yield dut.o_ebreak
      if ebreak:
        #print('ebreak')
        break

    nonlocal failed
    failed = False
    x11 = yield dut.u_myooo.u_arf.regs[11]
    x12 = yield dut.u_myooo.u_arf.regs[12]
    x13 = yield dut.u_myooo.u_arf.regs[13]
    if x11 != ord('O') or x12 != ord('K') or x13 != ord('\n'):
      failed = True
      for idx in range(len(dut.u_myooo.u_arf.regs)):
        r = yield dut.u_myooo.u_arf.regs[idx]
        print('  x{} = {}'.format(idx, hex(r)))

  sim = Simulator(dut)
  sim.add_clock(1e-6)  # 1 MHz
  sim.add_sync_process(bench)
  with sim.write_vcd("myooo.vcd"):
    sim.run()

  return not (failed), cycles


if __name__ == "__main__":
  total = 0
  passed = 0
  for input in sys.argv[1:]:
    print('============= {} ============='.format(input))
    total += 1
    test_pass, test_cycles = run_test(input)
    if test_pass:
      passed += 1
      print(' [PASS] cycles={}'.format(test_cycles))
    else:
      print(' [FAIL] cycles={}'.format(test_cycles))

  print('---({}/{})---'.format(passed, total))
