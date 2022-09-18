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

from components.BroadCast import *
from components.Utils import *
from components.MicroOperation import *


class ReservationStationEntry(data.Struct):
  busy: unsigned(1)  # This entry is busy.
  opcode: uOPOpcode  # The op-code.
  robIdx: unsigned(3)  # The ROB-idx corresponding to this RS entry.
  rs1Value: unsigned(32)  # The value of rs1 operand if rs1ValueValid=1.
  rs2Value: unsigned(32)  # The value of rs2 operand if rs2ValueValid=1.
  rs1ValueValid: unsigned(1)
  rs2ValueValid: unsigned(1)
  rs1RobIdx: unsigned(3)  # The ROB-idx to whose result should fill rs1Value if rs1ValueValid=0.
  rs2RobIdx: unsigned(3)  # The ROB-idx to whose result should fill rs2Value if rs2ValueValid=0.
  imm: unsigned(12)


class ReservationStation(Elaboratable):

  def __init__(self):
    # Ports
    self.i_issue_en = Signal()
    self.i_issue = ReservationStationEntry()
    self.o_issue_rdy = Signal()
    self.i_broadcast = BroadcastBusType()
    self.i_dispatch_rdy = Signal()
    self.o_dispatch_en = Signal()
    self.o_dispatch_uop = MicroOperationType()
    self.i_flush_en = Signal()

  def elaborate(self, platform):
    m = Module()

    addDebugSignals(m, self.i_issue)
    addDebugSignals(m, self.o_dispatch_uop)
    rs = Array([ReservationStationEntry() for _ in range(4)])

    # Issue side.
    all_busy = Signal(4)
    for idx in range(len(rs)):
      m.d.comb += all_busy[idx].eq(rs[idx].busy)
    m.d.comb += self.o_issue_rdy.eq(~all_busy.all())
    with m.If(0):
      pass
    for idx in range(len(rs)):
      with m.Elif(~rs[idx].busy):
        with m.If(self.i_issue_en):
          m.d.sync += [rs[idx].eq(self.i_issue), rs[idx].busy.eq(1)]
          # If broadcast happens at the same time as issue then check no valid operands and possibly override.
          with m.If(self.i_broadcast.valid & ~self.i_issue.rs1ValueValid
                    & (self.i_issue.rs1RobIdx == self.i_broadcast.robIdx)):
            m.d.sync += [rs[idx].rs1Value.eq(self.i_broadcast.data), rs[idx].rs1ValueValid.eq(1)]
          with m.If(self.i_broadcast.valid & ~self.i_issue.rs2ValueValid
                    & (self.i_issue.rs2RobIdx == self.i_broadcast.robIdx)):
            m.d.sync += [rs[idx].rs2Value.eq(self.i_broadcast.data), rs[idx].rs2ValueValid.eq(1)]

    # Generate broadcast bus monitoring logic.
    for rse in rs:
      with m.If(self.i_broadcast.valid & rse.busy & ~rse.rs1ValueValid & (rse.rs1RobIdx == self.i_broadcast.robIdx)):
        m.d.sync += [rse.rs1Value.eq(self.i_broadcast.data), rse.rs1ValueValid.eq(1)]
      with m.If(self.i_broadcast.valid & rse.busy & ~rse.rs2ValueValid & (rse.rs2RobIdx == self.i_broadcast.robIdx)):
        m.d.sync += [rse.rs2Value.eq(self.i_broadcast.data), rse.rs2ValueValid.eq(1)]

    # Dispatch.
    with m.If(self.i_dispatch_rdy):
      with m.If(0):
        pass
      for idx in range(len(rs)):
        with m.Elif(rs[idx].busy & rs[idx].rs1ValueValid & rs[idx].rs2ValueValid):
          m.d.comb += [
              self.o_dispatch_en.eq(1),
              self.o_dispatch_uop.robidx.eq(rs[idx].robIdx),
              self.o_dispatch_uop.opcode.eq(rs[idx].opcode),
              self.o_dispatch_uop.op1.eq(rs[idx].rs1Value),
              self.o_dispatch_uop.op2.eq(rs[idx].rs2Value),
              self.o_dispatch_uop.imm.eq(rs[idx].imm),
              self.o_dispatch_uop.valid.eq(1)
          ]
          m.d.sync += rs[idx].busy.eq(0)

    # Flush (highest priority)
    with m.If(self.i_flush_en):
      for rse in rs:
        m.d.sync += rse.busy.eq(0)

    for idx in range(len(rs)):
      addDebugSignals(m, rs[idx], name='rs{}'.format(idx))

    return m
