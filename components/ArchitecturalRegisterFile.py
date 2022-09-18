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


class ArchitecturalRegisterFile(Elaboratable):

  def __init__(self):
    # Ports
    self.i_rd1_idx = Signal(5)
    self.o_rd1_data = Signal(32)
    self.i_rd2_idx = Signal(5)
    self.o_rd2_data = Signal(32)
    self.i_wr_we = Signal()
    self.i_wr_idx = Signal(5)
    self.i_wr_data = Signal(32)

  def elaborate(self, platform):
    m = Module()

    self.regs = regs = Array([Signal(32) for _ in range(32)])

    with m.If(self.i_wr_we & (self.i_wr_idx != 0)):
      m.d.sync += regs[self.i_wr_idx].eq(self.i_wr_data)

    m.d.comb += [self.o_rd1_data.eq(regs[self.i_rd1_idx]), self.o_rd2_data.eq(regs[self.i_rd2_idx])]

    return m
