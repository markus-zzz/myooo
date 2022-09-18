# Copyright 2022 Markus Lavin (https://www.zzzconsulting.se/).
#
# This source describes Open Hardware and is licensed under the CERN-OHL-P v2.
#
# You may redistribute and modify this documentation and make products using it
# under the terms of the CERN-OHL-P v2 (https:/cern.ch/cern-ohl).  This
# documentation is distributed WITHOUT ANY EXPRESS OR IMPLIED WARRANTY,
# INCLUDING OF MERCHANTABILITY, SATISFACTORY QUALITY AND FITNESS FOR A
# PARTICULAR PURPOSE. Please see the CERN-OHL-P v2 for applicable conditions.

from amaranth.back import verilog
from myooo import MyOoO
import sys
import os

if __name__ == "__main__":

  u_myooo = MyOoO()

  u_myooo_ports = [
      # WishBone
      u_myooo.o_wb_adr,
      u_myooo.o_wb_dat,
      u_myooo.o_wb_sel,
      u_myooo.o_wb_cti,
      u_myooo.o_wb_we,
      u_myooo.o_wb_stb,
      u_myooo.o_wb_cyc,
      u_myooo.i_wb_dat,
      u_myooo.i_wb_ack,
      # Misc
      u_myooo.o_ebreak
  ]

  with open("myooo.v", "w") as f:
    f.write(verilog.convert(u_myooo, ports=u_myooo_ports))
