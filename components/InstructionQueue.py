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
from amaranth.lib import data

InstructionQueueEntryLayout = data.StructLayout({
    "instr": unsigned(32),
    "pc": unsigned(32)  # PC of the corresponding instruction.
})


class InstructionQueue(Elaboratable):

  def __init__(self):
    # Write.
    self.o_w_rdy = Signal()
    self.i_w_data = Signal(InstructionQueueEntryLayout)
    self.i_w_en = Signal()
    # Read.
    self.o_r_rdy = Signal()
    self.o_r_data = Signal(InstructionQueueEntryLayout)
    self.i_r_en = Signal()
    # Flush.
    self.i_flush_en = Signal()

  def elaborate(self, platform):
    m = Module()

    iq = Array([Signal(InstructionQueueEntryLayout) for _ in range(8)])
    rp = Signal(4)
    wp = Signal(4)
    empty = Signal()
    full = Signal()

    m.d.comb += empty.eq((rp[0:3] == wp[0:3]) & (rp[3] == wp[3]))
    m.d.comb += full.eq((rp[0:3] == wp[0:3]) & (rp[3] != wp[3]))

    # Write
    m.d.comb += [self.o_w_rdy.eq(~full)]
    with m.If(~full & self.i_w_en):
      m.d.sync += [iq[wp[0:3]].eq(self.i_w_data), wp.eq(wp + 1)]
    # Read.
    m.d.comb += [self.o_r_data.eq(iq[rp[0:3]]), self.o_r_rdy.eq(~empty)]
    with m.If(~empty & self.i_r_en):
      m.d.sync += [rp.eq(rp + 1)]

    with m.If(self.i_flush_en):
      m.d.sync += wp.eq(rp)

    return m
