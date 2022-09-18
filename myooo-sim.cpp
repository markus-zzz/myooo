/*
 * Copyright 2022 Markus Lavin (https://www.zzzconsulting.se/).
 *
 * This source describes Open Hardware and is licensed under the CERN-OHL-P v2.
 *
 * You may redistribute and modify this documentation and make products using it
 * under the terms of the CERN-OHL-P v2 (https:/cern.ch/cern-ohl).  This
 * documentation is distributed WITHOUT ANY EXPRESS OR IMPLIED WARRANTY,
 * INCLUDING OF MERCHANTABILITY, SATISFACTORY QUALITY AND FITNESS FOR A
 * PARTICULAR PURPOSE. Please see the CERN-OHL-P v2 for applicable conditions.
 */

#include "Vtop.h"
#include "verilated.h"
#include "verilated_vcd_c.h"
#include <assert.h>
#include <memory>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

enum class RunResult { Pass, Fail, Timeout };
const char *RunResultStr[] = {"\e[1;32mPASS\e[0m", "\e[1;31mFAIL\e[0m",
                              "\e[1;35mTIMEOUT\e[0m"};

static uint8_t memory[1024 * 1024];

RunResult run_sim(const char *mem_bin_path) {
  FILE *fp = fopen(mem_bin_path, "r");
  unsigned idx = 0;
  while (true) {
    if (fread(&memory[idx++], 1, 1, fp) != 1)
      break;
  }
  fclose(fp);

  auto dut = std::make_unique<Vtop>();
  auto trace = std::make_unique<VerilatedVcdC>();
  unsigned trace_tick = 0;
  std::vector<char> uart;
  RunResult result = RunResult::Timeout;

  dut->trace(trace.get(), 99);
  trace->open("dump.vcd");

  // Apply five cycles with reset active.
  dut->rst = 1;
  for (unsigned i = 0; i < 5; i++) {
    dut->clk = 1;
    dut->eval();
    if (trace)
      trace->dump(trace_tick++);
    dut->clk = 0;
    dut->eval();
    if (trace)
      trace->dump(trace_tick++);
  }
  dut->rst = 0;

  for (unsigned i = 0; i < 2 * 2048; i++) {

    dut->clk = 1;
    dut->eval();
    if (trace)
      trace->dump(trace_tick++);

    dut->i_wb_ack = 0;
    if (dut->o_wb_cyc & dut->o_wb_stb) {
      if (0 <= dut->o_wb_adr && dut->o_wb_adr < 1024 * 1024) {
        if (dut->o_wb_we) {
          if (dut->o_wb_sel & (1 << 0))
            memory[dut->o_wb_adr + 0] = 0xff & (dut->o_wb_dat >> 0);
          if (dut->o_wb_sel & (1 << 1))
            memory[dut->o_wb_adr + 1] = 0xff & (dut->o_wb_dat >> 8);
          if (dut->o_wb_sel & (1 << 2))
            memory[dut->o_wb_adr + 2] = 0xff & (dut->o_wb_dat >> 16);
          if (dut->o_wb_sel & (1 << 3))
            memory[dut->o_wb_adr + 3] = 0xff & (dut->o_wb_dat >> 24);
          //  printf("WRITE: memory[0x%x] = 0x%08x (mask=0x%x)\n",
          //  dut->o_wb_adr, dut->o_wb_dat, dut->o_wb_sel);
        } else {
          dut->i_wb_dat =
              memory[dut->o_wb_adr + 0] << 0 | memory[dut->o_wb_adr + 1] << 8 |
              memory[dut->o_wb_adr + 2] << 16 | memory[dut->o_wb_adr + 3] << 24;
          //  printf("READ: memory[0x%x] = 0x%08x\n", dut->o_wb_adr,
          //  dut->i_wb_dat);
        }
        dut->i_wb_ack = 1;
      } else if (dut->o_wb_adr == 0x8000'0000) {
        if (dut->o_wb_we && dut->o_wb_sel == 0xf) {
          // printf("%c", (char)dut->o_wb_dat);
          uart.push_back((char)dut->o_wb_dat);
        }
        dut->i_wb_ack = 1;
      } else {
        printf("Unhandled address: 0x%x\n", dut->o_wb_adr);
      }
    }

    dut->clk = 0;
    dut->eval();
    if (trace)
      trace->dump(trace_tick++);

    if (uart.size() == 3 && uart[0] == 'O' && uart[1] == 'K' &&
        uart[2] == '\n') {
      result = RunResult::Pass;
      break;
    } else if (uart.size() == 6 && uart[0] == 'E' && uart[1] == 'R' &&
               uart[2] == 'R' && uart[3] == 'O' && uart[4] == 'R' &&
               uart[5] == '\n') {
      result = RunResult::Fail;
      break;
    }
  }

  if (trace)
    trace->flush();

  return result;
}

int main(int argc, char *argv[]) {

  // Initialize Verilators variables
  Verilated::commandArgs(argc, argv);

  Verilated::traceEverOn(true);

  for (int i = 1; i < argc; ++i) {
    auto mem_bin_path = argv[i];
    printf("%-25s : ", mem_bin_path);
    auto result = run_sim(mem_bin_path);
    printf("%s\n", RunResultStr[static_cast<int>(result)]);
  }

  return 0;
}
