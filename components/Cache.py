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

from components.Utils import *

cfgAddrOffsetBits = 5
cfgAddrIndexBits = 6
cfgAddrTagBits = 32 - cfgAddrOffsetBits - cfgAddrIndexBits

AddrTypeLayout = data.StructLayout({
    "offset": unsigned(cfgAddrOffsetBits),
    "index": unsigned(cfgAddrIndexBits),
    "tag": unsigned(cfgAddrTagBits)
})

TagMemEntryTypeLayout = data.StructLayout({"valid": unsigned(1), "dirty": unsigned(1), "tag": unsigned(cfgAddrTagBits)})


class Cache(Elaboratable):

  def __init__(self):
    # CPU IF
    self.i_cpu_addr = Signal(32)
    self.i_cpu_data = Signal(32)
    self.i_cpu_wsel = Signal(4)
    self.i_cpu_we = Signal()
    self.i_cpu_valid = Signal()
    self.o_cpu_rdy = Signal()
    self.o_cpu_data = Signal(32)
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

    u_mem_rp = []
    u_mem_wp = []
    for idx in range(4):
      mem = Memory(width=8, depth=2**(cfgAddrIndexBits + cfgAddrOffsetBits - 2))
      mem_rp = mem.read_port(domain='comb')
      mem_wp = mem.write_port()
      u_mem_rp.append(mem_rp)
      u_mem_wp.append(mem_wp)
      m.submodules += [mem_rp, mem_wp]

    i_cpu_addr_r = Signal(32)
    cpu_addr = Signal(AddrTypeLayout)
    m.d.comb += cpu_addr.eq(self.i_cpu_addr)
    cpu_addr_r = Signal(AddrTypeLayout)
    m.d.comb += cpu_addr_r.eq(i_cpu_addr_r)

    tag_mem = Array([Signal(TagMemEntryTypeLayout) for _ in range(2**cfgAddrIndexBits)])
    tag = tag_mem[cpu_addr.index]
    tag_r = tag_mem[cpu_addr_r.index]

    addr_cntr = Signal(cfgAddrOffsetBits - 2)

    cpu_mem_idx = Cat(cpu_addr.offset[2:], cpu_addr.index)
    bus_mem_idx = Cat(addr_cntr, cpu_addr_r.index)

    u_mem_rp_data32 = Cat(u_mem_rp[0].data, u_mem_rp[1].data, u_mem_rp[2].data, u_mem_rp[3].data)

    with m.FSM(reset='idle') as fsm:

      with m.State('idle'):
        with m.If(self.i_cpu_valid):
          with m.If(self.i_cpu_addr[31]):  # Cache bypass.
            m.next = 'bypass-write-0'
          with m.Elif(tag.valid & (tag.tag == cpu_addr.tag)):  # Cache HIT.
            for idx in range(4):
              m.d.comb += u_mem_rp[idx].addr.eq(cpu_mem_idx)
            m.d.comb += [self.o_cpu_data.eq(u_mem_rp_data32), self.o_cpu_rdy.eq(1)]
            with m.If(self.i_cpu_we):
              m.d.sync += tag.dirty.eq(1)
              for idx in range(4):
                m.d.comb += [
                    u_mem_wp[idx].addr.eq(cpu_mem_idx), u_mem_wp[idx].data.eq(self.i_cpu_data[8 * idx:8 * (idx + 1)])
                ]
                with m.If(self.i_cpu_wsel[idx]):
                  m.d.comb += [u_mem_wp[idx].en.eq(1)]
          with m.Else():  # Cache MISS.
            m.d.sync += [i_cpu_addr_r.eq(self.i_cpu_addr), addr_cntr.eq(0)]
            with m.If(tag.valid & tag.dirty):
              m.next = 'writeback-0'
            with m.Else():
              m.next = 'allocate-0'

      with m.State('writeback-0'):
        for idx in range(4):
          m.d.comb += u_mem_rp[idx].addr.eq(bus_mem_idx)
        m.d.comb += [
            self.o_wb_cyc.eq(1),
            self.o_wb_stb.eq(1),
            self.o_wb_we.eq(1),
            self.o_wb_sel.eq(0b1111),
            self.o_wb_adr.eq(Cat(Const(0, 2), addr_cntr, cpu_addr_r.index, tag_r.tag)),
            self.o_wb_dat.eq(u_mem_rp_data32)
        ]
        with m.If(self.i_wb_ack):
          m.d.sync += [addr_cntr.eq(addr_cntr + 1)]
          with m.If(addr_cntr == 2**(cfgAddrOffsetBits - 2) - 1):
            m.d.sync += [tag_r.dirty.eq(0), tag_r.valid.eq(0)]
            m.next = 'allocate-0'

      with m.State('allocate-0'):
        m.d.comb += [
            self.o_wb_cyc.eq(1),
            self.o_wb_stb.eq(1),
            self.o_wb_adr.eq(Cat(Const(0, 2), addr_cntr, cpu_addr_r.index, cpu_addr_r.tag))
        ]
        with m.If(self.i_wb_ack):
          for idx in range(4):
            m.d.comb += [
                u_mem_wp[idx].addr.eq(bus_mem_idx), u_mem_wp[idx].data.eq(self.i_wb_dat[8 * idx:8 * (idx + 1)]),
                u_mem_wp[idx].en.eq(1)
            ]
          m.d.sync += [addr_cntr.eq(addr_cntr + 1)]
          with m.If(addr_cntr == 2**(cfgAddrOffsetBits - 2) - 1):
            m.d.sync += [tag_r.tag.eq(cpu_addr_r.tag), tag_r.valid.eq(1)]
            m.next = 'idle'

      with m.State('bypass-write-0'):
        m.d.comb += [
            self.o_wb_cyc.eq(1),
            self.o_wb_stb.eq(1),
            self.o_wb_we.eq(1),
            self.o_wb_sel.eq(0b1111),
            self.o_wb_adr.eq(self.i_cpu_addr),
            self.o_wb_dat.eq(self.i_cpu_data)
        ]
        with m.If(self.i_wb_ack):
          m.d.comb += self.o_cpu_rdy.eq(1)
          m.next = 'idle'

    return m


class SlowMemory(Elaboratable):

  def __init__(self, initBin):
    self.initBin = initBin
    # BUS IF
    self.i_wb_adr = Signal(32)
    self.i_wb_dat = Signal(32)
    self.o_wb_dat = Signal(32)
    self.i_wb_sel = Signal(4)
    self.i_wb_cti = Signal(3)
    self.i_wb_we = Signal()
    self.i_wb_stb = Signal()
    self.i_wb_cyc = Signal()
    self.o_wb_ack = Signal()

  def elaborate(self, platform):
    m = Module()

    u_mem = Memory(width=32, depth=2048, init=readMemInit(self.initBin, 4))
    m.submodules.u_mem_rp = u_mem_rp = u_mem.read_port(domain='comb')
    m.submodules.u_mem_wp = u_mem_wp = u_mem.write_port()

    with m.If(self.i_wb_cyc & self.i_wb_stb):
      m.d.comb += self.o_wb_ack.eq(1)
      with m.If(self.i_wb_we):
        m.d.comb += [u_mem_wp.data.eq(self.i_wb_dat), u_mem_wp.addr.eq(self.i_wb_adr[2:]), u_mem_wp.en.eq(1)]
      with m.Else():
        m.d.comb += [self.o_wb_dat.eq(u_mem_rp.data), u_mem_rp.addr.eq(self.i_wb_adr[2:])]
    return m


class Top(Elaboratable):

  def __init__(self):
    pass

  def elaborate(self, platform):
    m = Module()

    m.submodules.u_cache = u_cache = Cache()
    m.submodules.u_mem = u_mem = SlowMemory()

    m.d.comb += [
        u_mem.i_wb_adr.eq(u_cache.o_wb_adr),
        u_mem.i_wb_dat.eq(u_cache.o_wb_dat),
        u_mem.i_wb_sel.eq(u_cache.o_wb_sel),
        u_mem.i_wb_cti.eq(u_cache.o_wb_cti),
        u_mem.i_wb_we.eq(u_cache.o_wb_we),
        u_mem.i_wb_stb.eq(u_cache.o_wb_stb),
        u_mem.i_wb_cyc.eq(u_cache.o_wb_cyc),
        u_cache.i_wb_dat.eq(u_mem.o_wb_dat),
        u_cache.i_wb_ack.eq(u_mem.o_wb_ack)
    ] # yapf: disable

    cntr = Signal(5)

    with m.FSM(reset='s0') as fsm:
      with m.State('s0'):
        m.d.comb += [
            u_cache.i_cpu_addr.eq(0x2c),
            u_cache.i_cpu_data.eq(0xdeafbeef),
            u_cache.i_cpu_we.eq(1),
            u_cache.i_cpu_valid.eq(1)
        ]
        with m.If(u_cache.o_cpu_rdy):
          m.next = 's1'

      with m.State('s1'):
        m.d.comb += [u_cache.i_cpu_addr.eq(0x20 + cntr), u_cache.i_cpu_valid.eq(1)]
        with m.If(u_cache.o_cpu_rdy):
          m.d.sync += cntr.eq(cntr + 4)
          with m.If(cntr == 2**5 - 4):
            m.next = 's2'

      with m.State('s2'):
        m.d.comb += [
            u_cache.i_cpu_addr.eq(2**(cfgAddrIndexBits + cfgAddrOffsetBits) + 0x20 + cntr),
            u_cache.i_cpu_valid.eq(1)
        ]
        with m.If(u_cache.o_cpu_rdy):
          m.d.sync += cntr.eq(cntr + 4)
          with m.If(cntr == 2**5 - 4):

            m.next = 's2'

    return m


from amaranth.sim import Simulator

if __name__ == "__main__":
  dut = Top()
  sim = Simulator(dut)
  sim.add_clock(1e-6)  # 1 MHz

  def bench():
    for idx in range(2500):
      yield

  sim.add_sync_process(bench)
  with sim.write_vcd("cache.vcd"):
    sim.run()
