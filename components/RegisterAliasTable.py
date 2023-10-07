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

from components.Utils import *

RegisterAliasTableEntryLayout = data.StructLayout({
    "valid": unsigned(1),  # Entry maps to ROB not ARF.
    "robIdx": unsigned(3)  # The ROB-Idx that currently hold this register (the RAT-idx of this entry itself).
})


class RegisterAliasTable(Elaboratable):

  def __init__(self):
    # Ports
    self.i_rd1_idx = Signal(5)
    self.o_rd1_robidx = Signal(3)
    self.o_rd1_valid = Signal()

    self.i_rd2_idx = Signal(5)
    self.o_rd2_robidx = Signal(3)
    self.o_rd2_valid = Signal()

    self.i_commit_en = Signal()
    self.i_commit_idx = Signal(5)
    self.i_commit_robidx = Signal(3)

    self.i_alloc_en = Signal()
    self.i_alloc_idx = Signal(5)
    self.i_alloc_robidx = Signal(3)
    # Flush
    self.i_flush_en = Signal()

  def elaborate(self, platform):
    m = Module()

    rat = Array([Signal(RegisterAliasTableEntryLayout) for _ in range(32)])

    # Allocating a new translation has priority over commit (for a given index).
    with m.If(self.i_alloc_en & (self.i_alloc_idx != 0)):
      m.d.sync += [rat[self.i_alloc_idx].robIdx.eq(self.i_alloc_robidx), rat[self.i_alloc_idx].valid.eq(1)]
    with m.If(self.i_commit_en & (rat[self.i_commit_idx].robIdx == self.i_commit_robidx)):
      # Note that this conflict dectection essentially adds another read port (so 3 in total).
      with m.If(~self.i_alloc_en | (self.i_alloc_idx != self.i_commit_idx)):
        m.d.sync += rat[self.i_commit_idx].valid.eq(0)

    m.d.comb += [
        self.o_rd1_robidx.eq(rat[self.i_rd1_idx].robIdx),
        self.o_rd1_valid.eq(rat[self.i_rd1_idx].valid),
        self.o_rd2_robidx.eq(rat[self.i_rd2_idx].robIdx),
        self.o_rd2_valid.eq(rat[self.i_rd2_idx].valid)
    ]

    # Flush (highest priority).
    with m.If(self.i_flush_en):
      for rate in rat:
        m.d.sync += rate.valid.eq(0)

    for idx in range(len(rat)):
      addDebugSignals(m, rat[idx], name='rat{}'.format(idx))

    return m
