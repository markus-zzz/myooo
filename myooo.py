# Copyright 2022 Markus Lavin (https://www.zzzconsulting.se/).
#
# This source describes Open Hardware and is licensed under the CERN-OHL-P v2.
#
# You may redistribute and modify this documentation and make products using it
# under the terms of the CERN-OHL-P v2 (https:/cern.ch/cern-ohl).  This
# documentation is distributed WITHOUT ANY EXPRESS OR IMPLIED WARRANTY,
# INCLUDING OF MERCHANTABILITY, SATISFACTORY QUALITY AND FITNESS FOR A
# PARTICULAR PURPOSE. Please see the CERN-OHL-P v2 for applicable conditions.

# MyOoO - My Out of Order CPU
#
# yapf --in-place --recursive --style="{indent_width: 2, column_limit: 120}" myooo.py

from amaranth import *
from amaranth.lib import data
from amaranth.lib.fifo import SyncFIFO
import pdb

from components.RV32I import *
from components.Utils import *
from components.InstructionQueue import *
from components.ReservationStation import *
from components.RegisterAliasTable import *
from components.ReOrderBuffer import *
from components.ArchitecturalRegisterFile import *
from components.MicroOperation import *
from components.ExecutionUnit import *
from components.LoadStoreQueue import *
from components.Cache import *


class MyOoO(Elaboratable):

  def __init__(self):
    self.o_ebreak = Signal()
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

    m.submodules.u_iq = u_iq = InstructionQueue()
    m.submodules.u_arf = u_arf = ArchitecturalRegisterFile()
    m.submodules.u_rat = u_rat = RegisterAliasTable()
    m.submodules.u_rs = u_rs = ReservationStation()
    m.submodules.u_rob = u_rob = ReOrderBuffer()
    m.submodules.u_eu = u_eu = ExecutionUnit()
    m.submodules.u_lsq = u_lsq = LoadStoreQueue()
    m.submodules.u_icache = u_icache = Cache()
    self.u_arf = u_arf

    with m.If(u_lsq.o_wb_cyc):
      m.d.comb += [
          self.o_wb_adr.eq(u_lsq.o_wb_adr),
          self.o_wb_dat.eq(u_lsq.o_wb_dat),
          self.o_wb_sel.eq(u_lsq.o_wb_sel),
          self.o_wb_cti.eq(u_lsq.o_wb_cti),
          self.o_wb_we.eq(u_lsq.o_wb_we),
          self.o_wb_stb.eq(u_lsq.o_wb_stb),
          self.o_wb_cyc.eq(u_lsq.o_wb_cyc),
          u_lsq.i_wb_dat.eq(self.i_wb_dat),
          u_lsq.i_wb_ack.eq(self.i_wb_ack)
      ] # yapf: disable
    with m.Else():
      m.d.comb += [
          self.o_wb_adr.eq(u_icache.o_wb_adr),
          self.o_wb_dat.eq(u_icache.o_wb_dat),
          self.o_wb_sel.eq(u_icache.o_wb_sel),
          self.o_wb_cti.eq(u_icache.o_wb_cti),
          self.o_wb_we.eq(u_icache.o_wb_we),
          self.o_wb_stb.eq(u_icache.o_wb_stb),
          self.o_wb_cyc.eq(u_icache.o_wb_cyc),
          u_icache.i_wb_dat.eq(self.i_wb_dat),
          u_icache.i_wb_ack.eq(self.i_wb_ack)
      ] # yapf: disable

    broadcast = Signal(BroadcastBusTypeLayout)
    m.d.comb += [u_rob.i_broadcast.eq(broadcast), u_rs.i_broadcast.eq(broadcast), u_lsq.i_broadcast.eq(broadcast)]

    flush = Signal()
    m.d.comb += [
        flush.eq(0),  # XXX: Is this needed or are unassigned comb signals 0 by default? Need to check the spec!!!
        u_iq.i_flush_en.eq(flush),
        u_rob.i_flush_en.eq(flush),
        u_rat.i_flush_en.eq(flush),
        u_rs.i_flush_en.eq(flush),
        u_eu.i_flush_en.eq(flush),
        u_lsq.i_flush_en.eq(flush)
    ]

    #
    # FETCH
    #
    PC = Signal(32)
    m.d.comb += [u_icache.i_cpu_addr.eq(PC), u_icache.i_cpu_valid.eq(1)]
    fetch_b = Signal(BTypeInstrTypeLayout)
    m.d.comb += fetch_b.eq(u_icache.o_cpu_data)
    fetch_j = Signal(JTypeInstrTypeLayout)
    m.d.comb += fetch_j.eq(u_icache.o_cpu_data)
    with m.If(u_icache.o_cpu_rdy & u_iq.o_w_rdy & ~flush):
      m.d.comb += [u_iq.i_w_data.instr.eq(u_icache.o_cpu_data), u_iq.i_w_data.pc.eq(PC), u_iq.i_w_en.eq(1)]
      with m.Switch(fetch_b.opcode):
        with m.Case(RV32I_OP_BRANCH):
          # XXX: For now predict all branches as taken.
          m.d.sync += PC.eq(
              PC +
              Cat(Const(0, unsigned(1)), fetch_b.imm_4_1, fetch_b.imm_10_5, fetch_b.imm_11, fetch_b.imm_12).as_signed())
        with m.Case(RV32I_OP_JAL):
          m.d.sync += PC.eq(PC + Cat(Const(0, unsigned(1)), fetch_j.imm_10_1, fetch_j.imm_11, fetch_j.imm_19_12,
                                     fetch_j.imm_20).as_signed())
        with m.Default():
          m.d.sync += PC.eq(PC + 4)

    #
    # ISSUE
    #

    jalr_ongoing = Signal()
    jalr_a = Signal(32)
    jalr_b = Signal()
    jalr_c = Signal(3)

    # Feed IQ from outside.
    instr_r = Signal(RTypeInstrTypeLayout)
    m.d.comb += instr_r.eq(u_iq.o_r_data.instr)
    instr_u = Signal(UTypeInstrTypeLayout)
    m.d.comb += instr_u.eq(u_iq.o_r_data.instr)
    instr_i = Signal(ITypeInstrTypeLayout)
    m.d.comb += instr_i.eq(u_iq.o_r_data.instr)
    instr_s = Signal(STypeInstrTypeLayout)
    m.d.comb += instr_s.eq(u_iq.o_r_data.instr)
    instr_b = Signal(BTypeInstrTypeLayout)
    m.d.comb += instr_b.eq(u_iq.o_r_data.instr)
    instr_j = Signal(JTypeInstrTypeLayout)
    m.d.comb += instr_j.eq(u_iq.o_r_data.instr)

    m.d.comb += [
        u_rob.i_alloc_rd.eq(instr_r.rd),
        u_rob.i_alloc_pc.eq(u_iq.o_r_data.pc),
        u_rob.i_alloc_type.eq(ROBType.OTHER),
        u_rs.i_issue.opcode.eq(instr_r.opcode),
        u_rs.i_issue.robIdx.eq(u_rob.o_alloc_idx),
    ]

    # Drive alloc port of RAT.
    m.d.comb += [
        u_rat.i_alloc_idx.eq(instr_r.rd),  # Map rd rd robidx
        u_rat.i_alloc_robidx.eq(u_rob.o_alloc_idx),
        u_rob.i_rd1_idx.eq(u_rat.o_rd1_robidx),
        u_rob.i_rd2_idx.eq(u_rat.o_rd2_robidx)
    ]

    with m.Switch(instr_r.opcode):
      with m.Case(RV32I_OP_LUI):
        m.d.comb += [
            u_rs.i_issue.rs1Value.eq(instr_u.imm << 12),
            u_rs.i_issue.rs2Value.eq(0),
            u_rs.i_issue.rs1ValueValid.eq(1),
            u_rs.i_issue.rs2ValueValid.eq(1),
            u_rs.i_issue.rs1RobIdx.eq(0),
            u_rs.i_issue.rs2RobIdx.eq(0),
            u_rob.i_alloc_rd.eq(instr_u.rd)
        ]
        m.d.comb += u_rs.i_issue.opcode.eq(uOPOpcode.LUI)

        with m.If(u_iq.o_r_rdy & ~flush & u_rob.o_alloc_rdy & u_rs.o_issue_rdy):
          m.d.comb += [
              u_iq.i_r_en.eq(1),  # Consume the IQ entry.
              u_rs.i_issue_en.eq(1),  # Strobe RS to add issue.
              u_rob.i_alloc_en.eq(1),  # Strobe ROB to allocate entry.
              u_rat.i_alloc_en.eq(1)  # Strobe RAT to allocate entry.
          ]

      with m.Case(RV32I_OP_AUIPC):
        m.d.comb += [
            u_rs.i_issue.rs1Value.eq(instr_u.imm << 12),
            u_rs.i_issue.rs2Value.eq(u_iq.o_r_data.pc),
            u_rs.i_issue.rs1ValueValid.eq(1),
            u_rs.i_issue.rs2ValueValid.eq(1),
            u_rs.i_issue.rs1RobIdx.eq(0),
            u_rs.i_issue.rs2RobIdx.eq(0),
            u_rob.i_alloc_rd.eq(instr_u.rd)
        ]
        m.d.comb += u_rs.i_issue.opcode.eq(uOPOpcode.ADD)

        with m.If(u_iq.o_r_rdy & ~flush & u_rob.o_alloc_rdy & u_rs.o_issue_rdy):
          m.d.comb += [
              u_iq.i_r_en.eq(1),  # Consume the IQ entry.
              u_rs.i_issue_en.eq(1),  # Strobe RS to add issue.
              u_rob.i_alloc_en.eq(1),  # Strobe ROB to allocate entry.
              u_rat.i_alloc_en.eq(1)  # Strobe RAT to allocate entry.
          ]

      with m.Case(RV32I_OP_JAL):
        m.d.comb += [
            u_rs.i_issue.rs1Value.eq(4),
            u_rs.i_issue.rs2Value.eq(u_iq.o_r_data.pc),
            u_rs.i_issue.rs1ValueValid.eq(1),
            u_rs.i_issue.rs2ValueValid.eq(1),
            u_rs.i_issue.rs1RobIdx.eq(0),
            u_rs.i_issue.rs2RobIdx.eq(0),
            u_rob.i_alloc_rd.eq(instr_j.rd)
        ]
        m.d.comb += u_rs.i_issue.opcode.eq(uOPOpcode.ADD)

        with m.If(u_iq.o_r_rdy & ~flush & u_rob.o_alloc_rdy & u_rs.o_issue_rdy):
          m.d.comb += [
              u_iq.i_r_en.eq(1),  # Consume the IQ entry.
              u_rs.i_issue_en.eq(1),  # Strobe RS to add issue.
              u_rob.i_alloc_en.eq(1),  # Strobe ROB to allocate entry.
              u_rat.i_alloc_en.eq(1)  # Strobe RAT to allocate entry.
          ]

      with m.Case(RV32I_OP_JALR):
        # Use rs1 to index both RAT and ARF.
        m.d.comb += [
            u_arf.i_rd1_idx.eq(instr_i.rs1),
            u_rat.i_rd1_idx.eq(instr_i.rs1),
        ]
        with m.If(~jalr_ongoing):
          m.d.comb += [
              u_rs.i_issue.rs1Value.eq(4),
              u_rs.i_issue.rs2Value.eq(u_iq.o_r_data.pc),
              u_rs.i_issue.rs1ValueValid.eq(1),
              u_rs.i_issue.rs2ValueValid.eq(1),
              u_rs.i_issue.rs1RobIdx.eq(0),
              u_rs.i_issue.rs2RobIdx.eq(0),
              u_rob.i_alloc_rd.eq(instr_i.rd)
          ]
          m.d.comb += u_rs.i_issue.opcode.eq(uOPOpcode.ADD)
          m.d.sync += [
              jalr_a.eq(Mux(u_rat.o_rd1_valid, u_rob.o_rd1_data, u_arf.o_rd1_data)),
              jalr_b.eq(~u_rat.o_rd1_valid | u_rob.o_rd1_valid),
              jalr_c.eq(u_rat.o_rd1_robidx)
          ]
          # Override if broadcast
          with m.If(broadcast.valid & ~(~u_rat.o_rd1_valid | u_rob.o_rd1_valid)
                    & (u_rat.o_rd1_robidx == broadcast.robIdx)):
            m.d.sync += [jalr_a.eq(broadcast.data), jalr_b.eq(1)]
        with m.Else():
          m.d.comb += [
              u_rs.i_issue.rs1Value.eq(jalr_a),
              u_rs.i_issue.rs1ValueValid.eq(jalr_b),
              u_rs.i_issue.rs2Value.eq(instr_i.imm.as_signed()),
              u_rs.i_issue.rs2ValueValid.eq(1),
              u_rs.i_issue.rs1RobIdx.eq(jalr_c),
              u_rs.i_issue.rs2RobIdx.eq(0),
              u_rob.i_alloc_type.eq(ROBType.BRANCH2),
              u_rob.i_alloc_rd.eq(0)
          ]
          m.d.comb += u_rs.i_issue.opcode.eq(uOPOpcode.ADD)
          # Override if broadcast
          with m.If(broadcast.valid & ~jalr_b & (jalr_c == broadcast.robIdx)):
            m.d.sync += [jalr_a.eq(broadcast.data), jalr_b.eq(1)]

        with m.If(u_iq.o_r_rdy & ~flush & u_rob.o_alloc_rdy & u_rs.o_issue_rdy):
          m.d.sync += jalr_ongoing.eq(~jalr_ongoing)
          m.d.comb += [
              u_iq.i_r_en.eq(jalr_ongoing),  # Consume the IQ entry.
              u_rs.i_issue_en.eq(1),  # Strobe RS to add issue.
              u_rob.i_alloc_en.eq(1),  # Strobe ROB to allocate entry.
              u_rat.i_alloc_en.eq(~jalr_ongoing)  # Strobe RAT to allocate entry.
          ]

      with m.Case(RV32I_OP_IMM):
        # Use rs1 to index both RAT and ARF.
        m.d.comb += [
            u_arf.i_rd1_idx.eq(instr_i.rs1),
            u_rat.i_rd1_idx.eq(instr_i.rs1),
        ]
        # Drive issue port of RS.
        m.d.comb += [
            u_rs.i_issue.rs1Value.eq(Mux(u_rat.o_rd1_valid, u_rob.o_rd1_data, u_arf.o_rd1_data)),
            u_rs.i_issue.rs2Value.eq(instr_i.imm.as_signed()),
            u_rs.i_issue.rs1ValueValid.eq(~u_rat.o_rd1_valid | u_rob.o_rd1_valid),
            u_rs.i_issue.rs2ValueValid.eq(1),
            u_rs.i_issue.rs1RobIdx.eq(u_rat.o_rd1_robidx),
            u_rob.i_alloc_rd.eq(instr_i.rd)
        ]
        with m.Switch(instr_i.funct3):
          with m.Case(0b000):  # ADDI
            m.d.comb += u_rs.i_issue.opcode.eq(uOPOpcode.ADD)
          with m.Case(0b010):  # SLTI
            m.d.comb += u_rs.i_issue.opcode.eq(uOPOpcode.SLT)
          with m.Case(0b011):  # SLTIU
            m.d.comb += u_rs.i_issue.opcode.eq(uOPOpcode.SLTU)
          with m.Case(0b100):  # XORI
            m.d.comb += u_rs.i_issue.opcode.eq(uOPOpcode.XOR)
          with m.Case(0b110):  # ORI
            m.d.comb += u_rs.i_issue.opcode.eq(uOPOpcode.OR)
          with m.Case(0b111):  # ANDI
            m.d.comb += u_rs.i_issue.opcode.eq(uOPOpcode.AND)
          with m.Case(0b001):  # SLLI
            m.d.comb += u_rs.i_issue.opcode.eq(uOPOpcode.SLL)
          with m.Case(0b101):  # SRLI or SRAI
            with m.If(instr_i.imm[10]):
              m.d.comb += u_rs.i_issue.opcode.eq(uOPOpcode.SRA)
            with m.Else():
              m.d.comb += u_rs.i_issue.opcode.eq(uOPOpcode.SRL)

        with m.If(u_iq.o_r_rdy & ~flush & u_rob.o_alloc_rdy & u_rs.o_issue_rdy):
          m.d.comb += [
              u_iq.i_r_en.eq(1),  # Consume the IQ entry.
              u_rs.i_issue_en.eq(1),  # Strobe RS to add issue.
              u_rob.i_alloc_en.eq(1),  # Strobe ROB to allocate entry.
              u_rat.i_alloc_en.eq(1)  # Strobe RAT to allocate entry.
          ]

      with m.Case(RV32I_OP_OP):
        # Use rs1 and rs2 to index both RAT and ARF.
        m.d.comb += [
            u_arf.i_rd1_idx.eq(instr_r.rs1),
            u_arf.i_rd2_idx.eq(instr_r.rs2),
            u_rat.i_rd1_idx.eq(instr_r.rs1),
            u_rat.i_rd2_idx.eq(instr_r.rs2)
        ]
        # Drive issue port of RS.
        m.d.comb += [
            u_rs.i_issue.rs1Value.eq(Mux(u_rat.o_rd1_valid, u_rob.o_rd1_data, u_arf.o_rd1_data)),
            u_rs.i_issue.rs2Value.eq(Mux(u_rat.o_rd2_valid, u_rob.o_rd2_data, u_arf.o_rd2_data)),
            u_rs.i_issue.rs1ValueValid.eq(~u_rat.o_rd1_valid | u_rob.o_rd1_valid),
            u_rs.i_issue.rs2ValueValid.eq(~u_rat.o_rd2_valid | u_rob.o_rd2_valid),
            u_rs.i_issue.rs1RobIdx.eq(u_rat.o_rd1_robidx),
            u_rs.i_issue.rs2RobIdx.eq(u_rat.o_rd2_robidx),
            u_rob.i_alloc_rd.eq(instr_r.rd)
        ]

        with m.Switch(Cat(instr_r.funct3, instr_r.funct7)):
          with m.Case(0b0000000_000):  # ADD
            m.d.comb += u_rs.i_issue.opcode.eq(uOPOpcode.ADD)
          with m.Case(0b0100000_000):  # SUB
            m.d.comb += u_rs.i_issue.opcode.eq(uOPOpcode.SUB)
          with m.Case(0b0000000_001):  # SLL
            m.d.comb += u_rs.i_issue.opcode.eq(uOPOpcode.SLL)
          with m.Case(0b0000000_010):  # SLT
            m.d.comb += u_rs.i_issue.opcode.eq(uOPOpcode.SLT)
          with m.Case(0b0000000_011):  # SLTU
            m.d.comb += u_rs.i_issue.opcode.eq(uOPOpcode.SLTU)
          with m.Case(0b0000000_100):  # XOR
            m.d.comb += u_rs.i_issue.opcode.eq(uOPOpcode.XOR)
          with m.Case(0b0000000_101):  # SRL
            m.d.comb += u_rs.i_issue.opcode.eq(uOPOpcode.SRL)
          with m.Case(0b0100000_101):  # SRA
            m.d.comb += u_rs.i_issue.opcode.eq(uOPOpcode.SRA)
          with m.Case(0b0000000_110):  # OR
            m.d.comb += u_rs.i_issue.opcode.eq(uOPOpcode.OR)
          with m.Case(0b0000000_111):  # AND
            m.d.comb += u_rs.i_issue.opcode.eq(uOPOpcode.AND)

        with m.If(u_iq.o_r_rdy & ~flush & u_rob.o_alloc_rdy & u_rs.o_issue_rdy):
          m.d.comb += [
              u_iq.i_r_en.eq(1),  # Consume the IQ entry.
              u_rs.i_issue_en.eq(1),  # Strobe RS to add issue.
              u_rob.i_alloc_en.eq(1),  # Strobe ROB to allocate entry.
              u_rat.i_alloc_en.eq(1)  # Strobe RAT to allocate entry.
          ]

      with m.Case(RV32I_OP_LOAD):
        # Use rs1 to index both RAT and ARF.
        m.d.comb += [u_arf.i_rd1_idx.eq(instr_i.rs1), u_rat.i_rd1_idx.eq(instr_i.rs1)]
        # Drive issue port of LSQ.
        m.d.comb += [
            u_lsq.i_issue.type.eq(LSQType.LOAD),
            u_lsq.i_issue.addr.eq(Mux(u_rat.o_rd1_valid, u_rob.o_rd1_data, u_arf.o_rd1_data)),
            u_lsq.i_issue.addr_valid.eq(~u_rat.o_rd1_valid | u_rob.o_rd1_valid),
            u_lsq.i_issue.addr_robidx.eq(u_rat.o_rd1_robidx),
            u_lsq.i_issue.addr_offset.eq(instr_i.imm),
            u_lsq.i_issue.robidx.eq(u_rob.o_alloc_idx),
            u_rob.i_alloc_rd.eq(instr_i.rd),
        ]

        with m.Switch(instr_i.funct3):
          with m.Case(0b000):  # BYTE
            m.d.comb += [u_lsq.i_issue.size.eq(LSQSize.BYTE), u_lsq.i_issue.signed.eq(1)]
          with m.Case(0b001):  # HALF
            m.d.comb += [u_lsq.i_issue.size.eq(LSQSize.HALF), u_lsq.i_issue.signed.eq(1)]
          with m.Case(0b010):  # WORD
            m.d.comb += [u_lsq.i_issue.size.eq(LSQSize.WORD), u_lsq.i_issue.signed.eq(1)]
          with m.Case(0b100):  # BYTE unsigned
            m.d.comb += [u_lsq.i_issue.size.eq(LSQSize.BYTE), u_lsq.i_issue.signed.eq(0)]
          with m.Case(0b101):  # HALF unsigned
            m.d.comb += [u_lsq.i_issue.size.eq(LSQSize.HALF), u_lsq.i_issue.signed.eq(0)]

        with m.If(u_iq.o_r_rdy & ~flush & u_rob.o_alloc_rdy & u_lsq.o_issue_rdy):
          m.d.comb += [
              u_iq.i_r_en.eq(1),  # Consume the IQ entry.
              u_lsq.i_issue_en.eq(1),  # Strobe LSQ to add issue.
              u_rob.i_alloc_en.eq(1),  # Strobe ROB to allocate entry.
              u_rat.i_alloc_en.eq(1)  # Strobe RAT to allocate entry.
          ]

      with m.Case(RV32I_OP_STORE):
        # Use rs1 to index both RAT and ARF.
        m.d.comb += [
            u_arf.i_rd1_idx.eq(instr_s.rs1),
            u_rat.i_rd1_idx.eq(instr_s.rs1),
            u_arf.i_rd2_idx.eq(instr_s.rs2),
            u_rat.i_rd2_idx.eq(instr_s.rs2)
        ]
        # Drive issue port of LSQ.
        m.d.comb += [
            u_lsq.i_issue.type.eq(LSQType.STORE),
            u_lsq.i_issue.addr.eq(Mux(u_rat.o_rd1_valid, u_rob.o_rd1_data, u_arf.o_rd1_data)),
            u_lsq.i_issue.addr_valid.eq(~u_rat.o_rd1_valid | u_rob.o_rd1_valid),
            u_lsq.i_issue.addr_robidx.eq(u_rat.o_rd1_robidx),
            u_lsq.i_issue.addr_offset.eq(Cat(instr_s.imm_4_0, instr_s.imm_11_5)),
            u_lsq.i_issue.data.eq(Mux(u_rat.o_rd2_valid, u_rob.o_rd2_data, u_arf.o_rd2_data)),
            u_lsq.i_issue.data_valid.eq(~u_rat.o_rd2_valid | u_rob.o_rd2_valid),
            u_lsq.i_issue.data_robidx.eq(u_rat.o_rd2_robidx),
            u_lsq.i_issue.robidx.eq(u_rob.o_alloc_idx),
            u_rob.i_alloc_rd.eq(0),
            u_rob.i_alloc_lsqidx.eq(u_lsq.o_issue_idx),
            u_rob.i_alloc_type.eq(ROBType.STORE),
        ]

        with m.Switch(instr_s.funct3):
          with m.Case(0b000):  # BYTE
            m.d.comb += u_lsq.i_issue.size.eq(LSQSize.BYTE)
          with m.Case(0b001):  # HALF
            m.d.comb += u_lsq.i_issue.size.eq(LSQSize.HALF)
          with m.Case(0b010):  # WORD
            m.d.comb += u_lsq.i_issue.size.eq(LSQSize.WORD)

        with m.If(u_iq.o_r_rdy & ~flush & u_rob.o_alloc_rdy & u_lsq.o_issue_rdy):
          m.d.comb += [
              u_iq.i_r_en.eq(1),  # Consume the IQ entry.
              u_lsq.i_issue_en.eq(1),  # Strobe LSQ to add issue.
              u_rob.i_alloc_en.eq(1),  # Strobe ROB to allocate entry.
          ]

      with m.Case(RV32I_OP_MISC_MEM):
        # Drive issue port of LSQ.
        m.d.comb += [
            u_lsq.i_issue.type.eq(LSQType.FENCE),
            u_lsq.i_issue.robidx.eq(u_rob.o_alloc_idx),
            u_rob.i_alloc_rd.eq(0),
            u_rob.i_alloc_lsqidx.eq(u_lsq.o_issue_idx),
            u_rob.i_alloc_type.eq(ROBType.FENCE),
        ]

        with m.If(u_iq.o_r_rdy & ~flush & u_rob.o_alloc_rdy & u_lsq.o_issue_rdy):
          m.d.comb += [
              u_iq.i_r_en.eq(1),  # Consume the IQ entry.
              u_lsq.i_issue_en.eq(1),  # Strobe LSQ to add issue.
              u_rob.i_alloc_en.eq(1),  # Strobe ROB to allocate entry.
          ]

      with m.Case(RV32I_OP_BRANCH):
        # Use rs1 and rs2 to index both RAT and ARF.
        m.d.comb += [
            u_arf.i_rd1_idx.eq(instr_b.rs1),
            u_arf.i_rd2_idx.eq(instr_b.rs2),
            u_rat.i_rd1_idx.eq(instr_b.rs1),
            u_rat.i_rd2_idx.eq(instr_b.rs2)
        ]
        # Drive issue port of RS.
        m.d.comb += [
            u_rs.i_issue.rs1Value.eq(Mux(u_rat.o_rd1_valid, u_rob.o_rd1_data, u_arf.o_rd1_data)),
            u_rs.i_issue.rs2Value.eq(Mux(u_rat.o_rd2_valid, u_rob.o_rd2_data, u_arf.o_rd2_data)),
            u_rs.i_issue.rs1ValueValid.eq(~u_rat.o_rd1_valid | u_rob.o_rd1_valid),
            u_rs.i_issue.rs2ValueValid.eq(~u_rat.o_rd2_valid | u_rob.o_rd2_valid),
            u_rs.i_issue.rs1RobIdx.eq(u_rat.o_rd1_robidx),
            u_rs.i_issue.rs2RobIdx.eq(u_rat.o_rd2_robidx),
            u_rs.i_issue.imm.eq(Cat(instr_b.imm_4_1, instr_b.imm_10_5, instr_b.imm_11, instr_b.imm_12)),
            u_rob.i_alloc_rd.eq(0),
            u_rob.i_alloc_type.eq(ROBType.BRANCH),
        ]

        with m.Switch(instr_b.funct3):
          with m.Case(0b000):  # BEQ
            m.d.comb += u_rs.i_issue.opcode.eq(uOPOpcode.BEQ)
          with m.Case(0b001):  # BNE
            m.d.comb += u_rs.i_issue.opcode.eq(uOPOpcode.BNE)
          with m.Case(0b100):  # BLT
            m.d.comb += u_rs.i_issue.opcode.eq(uOPOpcode.BLT)
          with m.Case(0b101):  # BGE
            m.d.comb += u_rs.i_issue.opcode.eq(uOPOpcode.BGE)
          with m.Case(0b110):  # BLTU
            m.d.comb += u_rs.i_issue.opcode.eq(uOPOpcode.BLTU)
          with m.Case(0b111):  # BGEU
            m.d.comb += u_rs.i_issue.opcode.eq(uOPOpcode.BGEU)

        with m.If(u_iq.o_r_rdy & ~flush & u_rob.o_alloc_rdy & u_rs.o_issue_rdy):
          m.d.comb += [
              u_iq.i_r_en.eq(1),  # Consume the IQ entry.
              u_rs.i_issue_en.eq(1),  # Strobe RS to add issue.
              u_rob.i_alloc_en.eq(1)  # Strobe ROB to allocate entry.
          ]

      with m.Case(RV32I_OP_SYSTEM):
        # Drive issue port of RS.
        m.d.comb += [
            u_rs.i_issue.rs1ValueValid.eq(1),
            u_rs.i_issue.rs2ValueValid.eq(1),
            u_rs.i_issue.opcode.eq(uOPOpcode.EBREAK),
            u_rob.i_alloc_type.eq(ROBType.EBREAK),
        ]

        with m.If(u_iq.o_r_rdy & ~flush & u_rob.o_alloc_rdy & u_rs.o_issue_rdy):
          m.d.comb += [
              u_iq.i_r_en.eq(1),  # Consume the IQ entry.
              u_rs.i_issue_en.eq(1),  # Strobe RS to add issue.
              u_rob.i_alloc_en.eq(1)  # Strobe ROB to allocate entry.
          ]

    with m.If(flush):
      m.d.sync += jalr_ongoing.eq(0)

    #
    # Commit
    #
    prev_branch_target = Signal(32)
    prev_branch_valid = Signal()
    mispredict = Signal()

    with m.If(u_rob.o_commit_rdy):
      m.d.comb += u_rob.i_commit_en.eq(~flush)
      with m.If(u_rob.o_commit.type == ROBType.OTHER):  #XXX: Should be called normal or value produceing?
        m.d.comb += [
            u_rat.i_commit_idx.eq(u_rob.o_commit.rd),
            u_rat.i_commit_robidx.eq(u_rob.o_commit_robidx),
            u_rat.i_commit_en.eq(~flush),
            u_arf.i_wr_idx.eq(u_rob.o_commit.rd),
            u_arf.i_wr_data.eq(u_rob.o_commit.rdValue),
            u_arf.i_wr_we.eq(~flush),
        ]
      with m.If(prev_branch_valid & (prev_branch_target != u_rob.o_commit.pc)):
        m.d.comb += mispredict.eq(1)
        # Restart PC at real branch target.
        m.d.sync += PC.eq(prev_branch_target)
        # Flush everything.
        m.d.comb += flush.eq(1)

      m.d.sync += prev_branch_valid.eq(0)
      with m.If((u_rob.o_commit.type == ROBType.BRANCH) & ~mispredict):
        m.d.sync += [prev_branch_target.eq(u_rob.o_commit.pc + u_rob.o_commit.rdValue), prev_branch_valid.eq(1)]
        m.d.comb += u_arf.i_wr_we.eq(0)

      with m.If((u_rob.o_commit.type == ROBType.BRANCH2) & ~mispredict):
        m.d.sync += [
            prev_branch_target.eq(Cat(Const(0, unsigned(1)), u_rob.o_commit.rdValue[1:32])),
            prev_branch_valid.eq(1)
        ]
        m.d.comb += u_arf.i_wr_we.eq(0)

      with m.If(u_rob.o_commit.type == ROBType.EBREAK):
        m.d.comb += self.o_ebreak.eq(1)

      with m.If(u_rob.o_commit.type == ROBType.STORE):
        m.d.comb += [u_lsq.i_commit_en.eq(1), u_lsq.i_commit_idx.eq(u_rob.o_commit.lsqidx)]

    # Execution Unit
    m.d.comb += [
        u_rs.i_dispatch_rdy.eq(u_eu.o_dispatch_rdy),
        u_eu.i_dispatch_en.eq(u_rs.o_dispatch_en),
        u_eu.i_dispatch_uop.eq(u_rs.o_dispatch_uop),
        u_eu.i_halt_en.eq(u_lsq.o_broadcast.valid)
    ]

    # Broadcast arbitration.
    m.d.comb += broadcast.eq(Mux(u_lsq.o_broadcast.valid, u_lsq.o_broadcast, u_eu.o_broadcast))

    addDebugSignals(m, broadcast)
    addDebugSignals(m, u_rob.o_commit)
    addDebugSignals(m, fetch_b)
    addDebugSignals(m, instr_r, 'instr_b')

    return m
