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


class ExecutionUnit(Elaboratable):

  def __init__(self):
    self.o_dispatch_rdy = Signal()
    self.i_dispatch_en = Signal()
    self.i_dispatch_uop = MicroOperationType()
    self.o_broadcast = BroadcastBusType()
    self.i_flush_en = Signal()
    self.i_halt_en = Signal()

  def elaborate(self, platform):
    m = Module()

    m.d.comb += self.o_dispatch_rdy.eq(~self.i_halt_en)

    pipe = Array([MicroOperationType() for _ in range(4)])
    with m.If(~self.i_halt_en):
      m.d.sync += [
          pipe[0].eq(Mux(self.i_dispatch_en, self.i_dispatch_uop, 0)), pipe[1].eq(pipe[0]), pipe[2].eq(pipe[1]),
          pipe[3].eq(pipe[2])
      ]

    m.d.comb += [self.o_broadcast.valid.eq(0), self.o_broadcast.robIdx.eq(0), self.o_broadcast.data.eq(0)]

    with m.Switch(pipe[3].opcode):
      with m.Case(uOPOpcode.LUI):
        m.d.comb += [
            self.o_broadcast.valid.eq(pipe[3].valid),
            self.o_broadcast.robIdx.eq(pipe[3].robidx),
            self.o_broadcast.data.eq(pipe[3].op1)
        ]
      with m.Case(uOPOpcode.ADD):
        m.d.comb += [
            self.o_broadcast.valid.eq(pipe[3].valid),
            self.o_broadcast.robIdx.eq(pipe[3].robidx),
            self.o_broadcast.data.eq(pipe[3].op1 + pipe[3].op2)
        ]
      with m.Case(uOPOpcode.SUB):
        m.d.comb += [
            self.o_broadcast.valid.eq(pipe[3].valid),
            self.o_broadcast.robIdx.eq(pipe[3].robidx),
            self.o_broadcast.data.eq(pipe[3].op1 - pipe[3].op2)
        ]
      with m.Case(uOPOpcode.SLL):
        m.d.comb += [
            self.o_broadcast.valid.eq(pipe[3].valid),
            self.o_broadcast.robIdx.eq(pipe[3].robidx),
            self.o_broadcast.data.eq(pipe[3].op1 << pipe[3].op2[0:5])
        ]
      with m.Case(uOPOpcode.SLT):  # XXX: signed
        m.d.comb += [
            self.o_broadcast.valid.eq(pipe[3].valid),
            self.o_broadcast.robIdx.eq(pipe[3].robidx),
            self.o_broadcast.data.eq(Mux(pipe[3].op1.as_signed() < pipe[3].op2.as_signed(), 1, 0))
        ]
      with m.Case(uOPOpcode.SLTU):  # XXX: unsigned
        m.d.comb += [
            self.o_broadcast.valid.eq(pipe[3].valid),
            self.o_broadcast.robIdx.eq(pipe[3].robidx),
            self.o_broadcast.data.eq(Mux(pipe[3].op1 < pipe[3].op2, 1, 0))
        ]
      with m.Case(uOPOpcode.XOR):
        m.d.comb += [
            self.o_broadcast.valid.eq(pipe[3].valid),
            self.o_broadcast.robIdx.eq(pipe[3].robidx),
            self.o_broadcast.data.eq(pipe[3].op1 ^ pipe[3].op2)
        ]
      with m.Case(uOPOpcode.SRL):
        m.d.comb += [
            self.o_broadcast.valid.eq(pipe[3].valid),
            self.o_broadcast.robIdx.eq(pipe[3].robidx),
            self.o_broadcast.data.eq(pipe[3].op1 >> pipe[3].op2[0:5])
        ]
      with m.Case(uOPOpcode.SRA):  # XXX: arithmetic
        m.d.comb += [
            self.o_broadcast.valid.eq(pipe[3].valid),
            self.o_broadcast.robIdx.eq(pipe[3].robidx),
            self.o_broadcast.data.eq(pipe[3].op1.as_signed() >> pipe[3].op2[0:5])
        ]
      with m.Case(uOPOpcode.OR):
        m.d.comb += [
            self.o_broadcast.valid.eq(pipe[3].valid),
            self.o_broadcast.robIdx.eq(pipe[3].robidx),
            self.o_broadcast.data.eq(pipe[3].op1 | pipe[3].op2)
        ]
      with m.Case(uOPOpcode.AND):
        m.d.comb += [
            self.o_broadcast.valid.eq(pipe[3].valid),
            self.o_broadcast.robIdx.eq(pipe[3].robidx),
            self.o_broadcast.data.eq(pipe[3].op1 & pipe[3].op2)
        ]

      with m.Case(uOPOpcode.BEQ):
        m.d.comb += [
            self.o_broadcast.valid.eq(pipe[3].valid),
            self.o_broadcast.robIdx.eq(pipe[3].robidx),
            self.o_broadcast.data.eq(Mux(pipe[3].op1 == pipe[3].op2, (pipe[3].imm << 1).as_signed(), 4))
        ]
      with m.Case(uOPOpcode.BNE):
        m.d.comb += [
            self.o_broadcast.valid.eq(pipe[3].valid),
            self.o_broadcast.robIdx.eq(pipe[3].robidx),
            self.o_broadcast.data.eq(Mux(pipe[3].op1 != pipe[3].op2, (pipe[3].imm << 1).as_signed(), 4))
        ]
      with m.Case(uOPOpcode.BLT):
        m.d.comb += [
            self.o_broadcast.valid.eq(pipe[3].valid),
            self.o_broadcast.robIdx.eq(pipe[3].robidx),
            self.o_broadcast.data.eq(
                Mux(pipe[3].op1.as_signed() < pipe[3].op2.as_signed(), (pipe[3].imm << 1).as_signed(), 4))
        ]
      with m.Case(uOPOpcode.BGE):
        m.d.comb += [
            self.o_broadcast.valid.eq(pipe[3].valid),
            self.o_broadcast.robIdx.eq(pipe[3].robidx),
            self.o_broadcast.data.eq(
                Mux(pipe[3].op1.as_signed() >= pipe[3].op2.as_signed(), (pipe[3].imm << 1).as_signed(), 4))
        ]
      with m.Case(uOPOpcode.BLTU):
        m.d.comb += [
            self.o_broadcast.valid.eq(pipe[3].valid),
            self.o_broadcast.robIdx.eq(pipe[3].robidx),
            self.o_broadcast.data.eq(
                Mux(pipe[3].op1.as_unsigned() < pipe[3].op2.as_unsigned(), (pipe[3].imm << 1).as_signed(), 4))
        ]
      with m.Case(uOPOpcode.BGEU):
        m.d.comb += [
            self.o_broadcast.valid.eq(pipe[3].valid),
            self.o_broadcast.robIdx.eq(pipe[3].robidx),
            self.o_broadcast.data.eq(
                Mux(pipe[3].op1.as_unsigned() >= pipe[3].op2.as_unsigned(), (pipe[3].imm << 1).as_signed(), 4))
        ]

      with m.Case(uOPOpcode.EBREAK):
        m.d.comb += [
            self.o_broadcast.valid.eq(pipe[3].valid),
            self.o_broadcast.robIdx.eq(pipe[3].robidx),
            self.o_broadcast.data.eq(0)
        ]

    # Flush (highest priority).
    with m.If(self.i_flush_en):
      for idx in range(4):
        m.d.sync += pipe[idx].valid.eq(0)

    addDebugSignals(m, pipe[3], name='pipe3')
    addDebugSignals(m, self.i_dispatch_uop)

    return m
