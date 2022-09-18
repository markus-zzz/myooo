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


class RTypeInstrType(data.Struct):
  opcode: unsigned(7)
  rd: unsigned(5)
  funct3: unsigned(3)
  rs1: unsigned(5)
  rs2: unsigned(5)
  funct7: unsigned(7)


class UTypeInstrType(data.Struct):
  opcode: unsigned(7)
  rd: unsigned(5)
  imm: unsigned(20)


class ITypeInstrType(data.Struct):
  opcode: unsigned(7)
  rd: unsigned(5)
  funct3: unsigned(3)
  rs1: unsigned(5)
  imm: unsigned(12)


class STypeInstrType(data.Struct):
  opcode: unsigned(7)
  imm_4_0: unsigned(5)
  funct3: unsigned(3)
  rs1: unsigned(5)
  rs2: unsigned(5)
  imm_11_5: unsigned(7)


class BTypeInstrType(data.Struct):
  opcode: unsigned(7)
  imm_11: unsigned(1)
  imm_4_1: unsigned(4)
  funct3: unsigned(3)
  rs1: unsigned(5)
  rs2: unsigned(5)
  imm_10_5: unsigned(6)
  imm_12: unsigned(1)


class JTypeInstrType(data.Struct):
  opcode: unsigned(7)
  rd: unsigned(5)
  imm_19_12: unsigned(8)
  imm_11: unsigned(1)
  imm_10_1: unsigned(10)
  imm_20: unsigned(1)


RV32I_OP_IMM = 0b0010011
RV32I_OP_LUI = 0b0110111
RV32I_OP_AUIPC = 0b0010111
RV32I_OP_OP = 0b0110011
RV32I_OP_JAL = 0b1101111
RV32I_OP_JALR = 0b1100111
RV32I_OP_BRANCH = 0b1100011
RV32I_OP_LOAD = 0b0000011
RV32I_OP_STORE = 0b0100011
RV32I_OP_MISC_MEM = 0b0001111
RV32I_OP_SYSTEM = 0b1110011
