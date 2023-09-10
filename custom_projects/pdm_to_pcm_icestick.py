#!/usr/bin/env python3
#
# Copyright (c) 2021-2022 Henry Dang <henrydang.@xxxx.com>
# SPDX-License-Identifier: BSD-2-Clause
#

import os
import sys
import argparse

sys.path.append('../')

from migen import *
from migen.fhdl import verilog

from litex.build.generic_platform import *
from litex.build.lattice import programmer
from custom_boards.platforms import icestick

from custom_ipcores.pdm import *

_ext_io = [
    ("i2s", 0,
        Subsignal("sck", Pins("112")), # J1 03
        Subsignal("ws",  Pins("113")), # J1 04
        Subsignal("so",  Pins("114")), # J1 05
        IOStandard("LVCMOS33"),
    ),
    ("pdm", 0,
        Subsignal("sck", Pins("115")), # J1 06
        Subsignal("dat", Pins("116")), # J1 07
        Subsignal("sel", Pins("117")), # J1 08
        IOStandard("LVCMOS33"),
    ),
    ("leds", 0,
        Subsignal("data", Pins("99 98 97 96 95"), IOStandard("LVCMOS33")),
    )
]

class CRG(Module):
    def __init__(self, platform):

        self.clock_domains.cd_sys = ClockDomain(reset_less=True)

        self.lock = Signal()
        clk12 = platform.request("clk12")

        # FIXME: Use PLL, increase system clock to 32 MHz, pending nextpnr
        # fixes.
        # Fout = Fin x (DIVF + 1) / (2^DIVQ x (DIVR + 1))
        # self.specials += \
            # Instance("SB_PLL40_2_PAD",
                # p_FEEDBACK_PATH="SIMPLE",
                # p_DIVR=0,    # 0
                # p_DIVF=1,    # 1
                # p_DIVQ=1,    # 1
                # p_FILTER_RANGE=0b010,
                # i_RESETB=1,
                # i_BYPASS=0,
                # i_PACKAGEPIN=clk12,
                # o_PLLOUTGLOBALA=self.cd_sys.clk,
            # )

        # Use PLL, increase system clock to 48 MHz
        # Fout = Fin x (DIVF + 1) / (2^DIVQ x (DIVR + 1))
        self.specials += Instance("SB_PLL40_CORE",
                            p_FEEDBACK_PATH = "SIMPLE",
                            p_PLLOUT_SELECT = "GENCLK",
                            p_DIVR          = 0,
                            p_DIVF          = 7,
                            p_DIVQ          = 1,
                            p_FILTER_RANGE  = 1,
                            o_LOCK          = self.lock,
                            i_RESETB        = 1,
		                    i_BYPASS        = 0,
		                    i_REFERENCECLK  = clk12,
		                    o_PLLOUTCORE    = self.cd_sys.clk
                        )

        # Platform clock constrain
        platform.add_period_constraint(clk12, 1e9/12e6)
        platform.add_period_constraint(self.cd_sys.clk, 1e9/48e6)

class Demo(Module):
    def __init__(self, platform):

        self.submodules.crg = crg = CRG(platform)

        user_led = platform.request("leds", 0)
        i2s_pads = platform.request("i2s", 0)
        pdm_pads = platform.request("pdm", 0)

        # pdm to pcm module
        self.submodules.pdm_pcm = pdm_pcm = PDM_TO_PCM(sys_clk_freq=48e6, fs_in=2400e3, M=5, R=50, dw=16, scale_factor=6e3)

        # Connect the I2S IOs
        self.comb += [
            If(crg.lock,
                pdm_pcm.ena.eq(1),
            ),
            user_led.data.eq(~pdm_pcm.buff[8:13]),
            i2s_pads.sck.eq(pdm_pcm.i2s_sck),
            i2s_pads.ws.eq(pdm_pcm.i2s_ws),
            i2s_pads.so.eq(pdm_pcm.i2s_so),
            pdm_pads.sck.eq(pdm_pcm.pdm_clk),
            pdm_pads.sel.eq(pdm_pcm.pdm_sel),
            pdm_pcm.pdm_dat.eq(pdm_pads.dat)
        ]

# Build --------------------------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="PDM to PCM demo on icestick")
    parser.add_argument("--build",     action="store_true", help="Build bitstream")
    parser.add_argument("--load",      action="store_true", help="Load bitstream (to SRAM)")
    parser.add_argument("--flash",     action="store_true", help="Flash bitstream (to SPI flash)")
    args = parser.parse_args()

    if args.build:
        build_dir = os.path.join("build", "icestick")
        build_name="icestick"
        platform = icestick.Platform(toolchain="icestorm")
        platform.add_extension(_ext_io)
        dut = Demo(platform)
        platform.build(dut, build_dir=build_dir, build_name=build_name)

    if args.load:
        print("An unmodified iCEstick can only be programmed via the serial flash.")
        print("Direct programming of the SRAM is not supported. For direct SRAM")
        print("programming the flash chip and one zero ohm resistor must be desoldered")
        print("and the FT2232H SI pin must be connected to the iCE SPI_SI pin, as shown")
        print("in this picture: http://www.clifford.at/gallery/2014-elektronik/IMG_20141115_183838")

    if args.flash:
        os.system("iceprog build/icestick/icestick.bin")

if __name__ == "__main__":
    main()