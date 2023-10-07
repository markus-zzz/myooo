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


def readMemInit(path, chunk_size):
  init = []
  with open(path, 'rb') as f:
    while True:
      bytes = f.read(chunk_size)
      if len(bytes) == chunk_size:
        init.append(int.from_bytes(bytes, byteorder='little', signed=False))
      else:
        break
    f.close()
  return init


# Utility for generating debug signals for struct fields.
def addDebugSignals(mod, sig, name=None):
  # XXX: Also structs of structs etc.
  for a, b in sig._View__layout._fields.items():
    dbgSig = Signal(b.shape, name='{}${}'.format(sig._View__target.name, a))
    mod.d.comb += dbgSig.eq(Value.cast(sig)[b.offset:b.offset + b.width])
