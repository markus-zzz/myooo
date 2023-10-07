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

from enum import Enum, unique, auto

from components.BroadCast import *
from components.Utils import *


@unique
class ROBType(Enum):
  OTHER = auto()
  BRANCH = auto()
  EBREAK = auto()
  STORE = auto()
  FENCE = auto()
  BRANCH2 = auto()


ReOrderBufferEntryLayout = data.StructLayout({
    "done": unsigned(1),  # The ROB-entry is done and ready to be committed.
    "type": ROBType,
    "lsqidx": unsigned(2),  # For STORE this is index into LSQ.
    "rd": unsigned(5),  # The destination register idx to commit to.
    "rdValue": unsigned(32),  # The contents to write to rd.
    "pc": unsigned(32)  # PC of the corresponding instruction.
})


class ReOrderBuffer(Elaboratable):

  def __init__(self):
    # Broadcast.
    self.i_broadcast = Signal(BroadcastBusTypeLayout)
    # Allocate.
    self.o_alloc_rdy = Signal()
    self.o_alloc_idx = Signal(3)
    self.i_alloc_rd = Signal(5)
    self.i_alloc_pc = Signal(32)
    self.i_alloc_type = Signal(ROBType)
    self.i_alloc_lsqidx = Signal(2)
    self.i_alloc_en = Signal()
    # Commit.
    self.o_commit_rdy = Signal()
    self.o_commit = Signal(ReOrderBufferEntryLayout)
    self.o_commit_robidx = Signal(3)
    self.i_commit_en = Signal()
    # Flush.
    self.i_flush_en = Signal()
    # Read rd.
    self.i_rd1_idx = Signal(3)
    self.o_rd1_data = Signal(32)
    self.o_rd1_valid = Signal()
    self.i_rd2_idx = Signal(3)
    self.o_rd2_data = Signal(32)
    self.o_rd2_valid = Signal()

  def elaborate(self, platform):
    m = Module()

    rob = Array([Signal(ReOrderBufferEntryLayout) for _ in range(8)])
    rp = Signal(3)
    wp = Signal(3)
    rp_ = Signal(4)
    wp_ = Signal(4)
    empty = Signal()
    full = Signal()

    m.d.comb += [
        rp.eq(rp_[0:3]),
        wp.eq(wp_[0:3]),
        self.o_rd1_data.eq(rob[self.i_rd1_idx].rdValue),
        self.o_rd1_valid.eq(rob[self.i_rd1_idx].done),
        self.o_rd2_data.eq(rob[self.i_rd2_idx].rdValue),
        self.o_rd2_valid.eq(rob[self.i_rd2_idx].done)
    ]

    m.d.comb += empty.eq((rp_[0:3] == wp_[0:3]) & (rp_[3] == wp_[3]))
    m.d.comb += full.eq((rp_[0:3] == wp_[0:3]) & (rp_[3] != wp_[3]))
    # Broadcast.
    with m.If(self.i_broadcast.valid):
      m.d.sync += [
          rob[self.i_broadcast.robIdx].done.eq(1), rob[self.i_broadcast.robIdx].rdValue.eq(self.i_broadcast.data)
      ]
    # Allocate.
    m.d.comb += [self.o_alloc_rdy.eq(~full), self.o_alloc_idx.eq(wp)]
    with m.If(~full & self.i_alloc_en):
      m.d.sync += [
          rob[wp].done.eq(0), rob[wp].rd.eq(self.i_alloc_rd), rob[wp].pc.eq(self.i_alloc_pc),
          rob[wp].type.eq(self.i_alloc_type), rob[wp].lsqidx.eq(self.i_alloc_lsqidx),
          wp_.eq(wp_ + 1)
      ]
    # Commit.
    m.d.comb += [self.o_commit.eq(rob[rp]), self.o_commit_robidx.eq(rp), self.o_commit_rdy.eq(~empty & rob[rp].done)]
    with m.If(~empty & self.i_commit_en):
      m.d.sync += [rp_.eq(rp_ + 1)]

    with m.If(self.i_flush_en):
      m.d.sync += wp_.eq(rp_)

    addDebugSignals(m, self.o_commit)

    return m
