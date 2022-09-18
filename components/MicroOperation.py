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

# uOPs - meaning operations for the micro-architecture


@unique
class uOPOpcode(Enum):
  LUI = auto()  # XXX: Could be ADD?
  #  AUIPC = auto()
  #  JAL = auto()
  JALR = auto()
  BEQ = auto()
  BNE = auto()
  BLT = auto()
  BGE = auto()
  BLTU = auto()
  BGEU = auto()
  LB = auto()
  LH = auto()
  LW = auto()
  LBU = auto()
  LHU = auto()
  SB = auto()
  SH = auto()
  SW = auto()
  #  ADDI = auto()
  #  SLTI = auto()
  #  SLTIU = auto()
  #  XORI = auto()
  #  ORI = auto()
  #  ANDI = auto()
  #  SLLI = auto()
  #  SRLI = auto()
  #  SRAI = auto()
  ADD = auto()
  SUB = auto()
  SLL = auto()
  SLT = auto()
  SLTU = auto()
  XOR = auto()
  SRL = auto()
  SRA = auto()
  OR = auto()
  AND = auto()
  FENCE = auto()
  ECALL = auto()
  EBREAK = auto()


class MicroOperationType(data.Struct):
  robidx: unsigned(3)
  imm: unsigned(12)
  op2: unsigned(32)
  op1: unsigned(32)
  opcode: uOPOpcode
  valid: unsigned(1)
