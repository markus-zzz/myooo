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
from components.Cache import *
from components.Utils import *


@unique
class LSQType(Enum):
  LOAD = auto()
  STORE = auto()
  FENCE = auto()


@unique
class LSQSize(Enum):
  BYTE = auto()
  HALF = auto()
  WORD = auto()


@unique
class LSQStatus(Enum):
  INVALID = auto()
  ALLOCATED = auto()
  DONE = auto()
  COMMITTED = auto()


class LoadStoreQueueEntry(data.Struct):
  type: LSQType

  addr_valid: unsigned(1)
  addr_robidx: unsigned(3)
  addr_offset: unsigned(12)
  addr: unsigned(32)

  data_valid: unsigned(1)
  data_robidx: unsigned(3)
  data: unsigned(32)

  size: LSQSize
  signed: unsigned(1)

  robidx: unsigned(3)

  status: LSQStatus


class LoadStoreQueue(Elaboratable):

  def __init__(self):
    # Broadcast.
    self.i_broadcast = BroadcastBusType()
    self.o_broadcast = BroadcastBusType()
    # Allocate.
    self.o_issue_rdy = Signal()
    self.o_issue_idx = Signal(2)
    self.i_issue = LoadStoreQueueEntry()
    self.i_issue_en = Signal()
    # Commit.
    self.i_commit_idx = Signal(2)
    self.i_commit_en = Signal()
    # Flush.
    self.i_flush_en = Signal()
    # BUS IF
    self.o_wb_adr = Signal(32)
    self.o_wb_dat = Signal(32)
    self.i_wb_dat = Signal(32)
    self.o_wb_sel = Signal(4)
    self.o_wb_cti = Signal(3)
    self.o_wb_we = Signal()
    self.o_wb_stb = Signal()
    self.o_wb_cyc = Signal()
    self.i_wb_ack = Signal()

  def elaborate(self, platform):
    m = Module()

    m.submodules.u_dcache = u_dcache = Cache()

    m.d.comb += [
        self.o_wb_adr.eq(u_dcache.o_wb_adr),
        self.o_wb_dat.eq(u_dcache.o_wb_dat),
        self.o_wb_sel.eq(u_dcache.o_wb_sel),
        self.o_wb_cti.eq(u_dcache.o_wb_cti),
        self.o_wb_we.eq(u_dcache.o_wb_we),
        self.o_wb_stb.eq(u_dcache.o_wb_stb),
        self.o_wb_cyc.eq(u_dcache.o_wb_cyc),
        u_dcache.i_wb_dat.eq(self.i_wb_dat),
        u_dcache.i_wb_ack.eq(self.i_wb_ack)
    ] # yapf: disable

    lsq = Array([LoadStoreQueueEntry() for _ in range(4)])
    rp = Signal(3)
    wp = Signal(3)
    empty = Signal()
    full = Signal()

    m.d.comb += empty.eq((rp[0:2] == wp[0:2]) & (rp[2] == wp[2]))
    m.d.comb += full.eq((rp[0:2] == wp[0:2]) & (rp[2] != wp[2]))

    # Allocate.
    m.d.comb += [self.o_issue_rdy.eq(~full), self.o_issue_idx.eq(wp)]
    lsq_wp = lsq[wp[0:2]]
    with m.If(~full & self.i_issue_en):
      m.d.sync += [lsq_wp.eq(self.i_issue), lsq_wp.status.eq(LSQStatus.ALLOCATED), wp.eq(wp + 1)]
      # If broadcast happens at the same time as issue then check no valid operands and possibly override.
      with m.If(self.i_broadcast.valid & ~self.i_issue.addr_valid
                & (self.i_issue.addr_robidx == self.i_broadcast.robIdx)):
        m.d.sync += [lsq_wp.addr.eq(self.i_broadcast.data), lsq_wp.addr_valid.eq(1)]
      with m.If(self.i_broadcast.valid & ~self.i_issue.data_valid
                & (self.i_issue.data_robidx == self.i_broadcast.robIdx)):
        m.d.sync += [lsq_wp.data.eq(self.i_broadcast.data), lsq_wp.data_valid.eq(1)]

    # Generate broadcast bus monitoring logic.
    for lsqe in lsq:
      with m.If(self.i_broadcast.valid & (lsqe.status == LSQStatus.ALLOCATED) & ~lsqe.addr_valid
                & (lsqe.addr_robidx == self.i_broadcast.robIdx)):
        m.d.sync += [lsqe.addr.eq(self.i_broadcast.data), lsqe.addr_valid.eq(1)]
      with m.If(self.i_broadcast.valid & (lsqe.status == LSQStatus.ALLOCATED) & ~lsqe.data_valid
                & (lsqe.data_robidx == self.i_broadcast.robIdx)):
        m.d.sync += [lsqe.data.eq(self.i_broadcast.data), lsqe.data_valid.eq(1)]

    lsq_rp = lsq[rp[0:2]]
    with m.If(~empty & ~self.i_flush_en & (lsq_rp.status == LSQStatus.ALLOCATED)):
      addr = lsq_rp.addr + lsq_rp.addr_offset.as_signed()
      with m.If((lsq_rp.type == LSQType.LOAD) & lsq_rp.addr_valid):
        m.d.comb += [u_dcache.i_cpu_addr.eq(addr), u_dcache.i_cpu_valid.eq(1)]
        with m.If(u_dcache.o_cpu_rdy):
          m.d.comb += [self.o_broadcast.valid.eq(1), self.o_broadcast.robIdx.eq(lsq_rp.robidx)]
          m.d.sync += [lsq_rp.status.eq(LSQStatus.INVALID), rp.eq(rp + 1)]
          with m.Switch(lsq_rp.size):
            with m.Case(LSQSize.BYTE):
              data = u_dcache.o_cpu_data.word_select(addr[0:2], 8)
              m.d.comb += self.o_broadcast.data.eq(Mux(lsq_rp.signed, 0 + data.as_signed(), data))
            with m.Case(LSQSize.HALF):
              data = u_dcache.o_cpu_data.word_select(addr[1], 16)
              m.d.comb += self.o_broadcast.data.eq(Mux(lsq_rp.signed, 0 + data.as_signed(), data))
            with m.Case(LSQSize.WORD):
              m.d.comb += self.o_broadcast.data.eq(u_dcache.o_cpu_data)
      with m.Elif((lsq_rp.type == LSQType.STORE) & lsq_rp.addr_valid & lsq_rp.data_valid):
        m.d.comb += [self.o_broadcast.valid.eq(1), self.o_broadcast.robIdx.eq(lsq_rp.robidx)]
        m.d.sync += [lsq_rp.status.eq(LSQStatus.DONE)]
      with m.Elif((lsq_rp.type == LSQType.FENCE)):
        m.d.comb += [self.o_broadcast.valid.eq(1), self.o_broadcast.robIdx.eq(lsq_rp.robidx)]
        m.d.sync += [lsq_rp.status.eq(LSQStatus.INVALID), rp.eq(rp + 1)]
    with m.Elif(~empty & ~self.i_flush_en & (lsq_rp.status == LSQStatus.COMMITTED)):
      addr = lsq_rp.addr + lsq_rp.addr_offset.as_signed()
      with m.Switch(lsq_rp.size):
        with m.Case(LSQSize.BYTE):
          # XXX: Repl and aggregate data structure fields cause problems in RTLIL generation (for Verilog) for some reason.
          # m.d.comb += [u_dcache.i_cpu_wsel.eq(0b1 << addr[0:2]), u_dcache.i_cpu_data.eq(Repl(lsq_rp.data[0:8], 4))]
          m.d.comb += [
              u_dcache.i_cpu_wsel.eq(0b1 << addr[0:2]),
              u_dcache.i_cpu_data.eq(Cat(lsq_rp.data[0:8], lsq_rp.data[0:8], lsq_rp.data[0:8], lsq_rp.data[0:8]))
          ]
          pass
        with m.Case(LSQSize.HALF):
          m.d.comb += [
              u_dcache.i_cpu_wsel.eq(Mux(addr[1], 0b1100, 0b0011)),
              # u_dcache.i_cpu_data.eq(Repl(lsq_rp.data[0:16], 2))
              u_dcache.i_cpu_data.eq(Cat(lsq_rp.data[0:16], lsq_rp.data[0:16]))
          ]
        with m.Case(LSQSize.WORD):
          m.d.comb += [u_dcache.i_cpu_wsel.eq(0b1111), u_dcache.i_cpu_data.eq(lsq_rp.data)]
      m.d.comb += [u_dcache.i_cpu_addr.eq(addr), u_dcache.i_cpu_we.eq(1), u_dcache.i_cpu_valid.eq(1)]
      with m.If(u_dcache.o_cpu_rdy):
        m.d.sync += [lsq_rp.status.eq(LSQStatus.INVALID), rp.eq(rp + 1)]

    with m.If(self.i_commit_en):
      lsq_p = lsq[self.i_commit_idx]
      m.d.sync += lsq_p.status.eq(LSQStatus.COMMITTED)

    with m.If(self.i_flush_en):
      for lsqe in lsq:
        m.d.sync += lsqe.status.eq(LSQStatus.INVALID)
      m.d.sync += wp.eq(rp)

    for idx in range(len(lsq)):
      addDebugSignals(m, lsq[idx], name='lsq{}'.format(idx))
    addDebugSignals(m, self.o_broadcast)
    addDebugSignals(m, self.i_issue)

    return m
