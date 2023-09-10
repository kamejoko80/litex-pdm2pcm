#!/usr/bin/env python3
#
# Copyright (c) 2021-2022 Henry Dang <henrydang.@xxxx.com>
# SPDX-License-Identifier: BSD-2-Clause
#

import os
import sys
import math
import random
import struct

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import scipy.fftpack
from scipy.fftpack import fft,fftshift

sys.path.append('../')

from migen import *
from migen.fhdl import verilog
from migen.fhdl.tools import *

from litex.build.generic_platform import *
from litex.build.sim import SimPlatform
from litex.build.sim.config import SimConfig

# IOs ----------------------------------------------------------------------

# Constant -----------------------------------------------------------------

pi = 3.141592653589793

# Functions ----------------------------------------------------------------

def pdm(x):
    n = len(x)
    y = np.zeros(n)
    error = np.zeros(n+1)

    print("n = " + str(n))

    for i in range(n):

        if x[i] >= error[i]:
            y[i] = 1
        else:
            y[i] = 0

        error[i+1] = y[i] - x[i] + error[i]

    return y, error[0:n]

def plot_demo_pdm():
    # Run simulation by software
    n = 100
    fclk = 250e6 # clock frequency (Hz)
    t = np.arange(n) / fclk
    f_sin = 5e6 # sine frequency (Hz)

    x = 0.5 + 0.4 * np.sin(2*np.pi*f_sin*t)
    y, error = pdm(x)

    plt.plot(1e9*t, x, label='input signal')
    plt.step(1e9*t, y, label='pdm signal',  linewidth=2.0)
    plt.step(1e9*t, error, label='error')
    plt.xlabel('Time (ns)')
    plt.ylim(-0.05,1.05)
    plt.legend()
    plt.show()

# Platform -----------------------------------------------------------------

# Classes, modules definition ----------------------------------------------

class EdgeDetector(Module):
    def __init__(self):
        self.i   = Signal() # Signal input
        self.r   = Signal() # Rising edge detect
        self.f   = Signal() # Falling edge detect
        self.cnt = Signal(2)

        self.comb += [
            self.r.eq(self.cnt == 1),
            self.f.eq(self.cnt == 2),
        ]

        self.sync += [
            self.cnt[1].eq(self.cnt[0]),
            self.cnt[0].eq(self.i),
        ]

###################################################################################################################
#
# CONFIGURABLE CIC FILTER IMPLEMENTATION WITH A SEPARATED SAMPLING FREQUENCY INPUT
#
# Block diagram:
#                                 Integrators                    Decimator              Combs
#                         _____________/\____________              __/\___     ___________/\___________
#                        /                           \            /       \   /                        \
#              ____                                                 _____
#  input      |    |           intg[0]          intg[M-1]          |     |    comb[0]            comb[M-1]     output
#  ------>----|buff|--->(+)-------O---->...(+)-------O-------------| ↓R  |-------O---->(+)........---O---->(+)------>
#             |    |     |      __|__       |      __|__           |_____|     __|__    |-         __|__    |-
#          |->|____|     |     |     |      |     |     |            | |      |     |   |         |     |   |
#          |             ^     | Z-1 |      ^     | Z-1 |            | |      | Z-1 |   ^         | Z-1 |   ^
#          |             |  |->|_____|      |  |->|_____|            | | |--->|_____|   |  |----->|_____|   |
#          |             |  |     |         |  |     |               | | |       |      |  |         |      |
#          |             |__|_____|di[0]    |__|_____|di[M-1]        | | | dc[0] |______|  | dc[M-1] |______|
#          |                |                  |                     | | |                 |
#          O----------------O------------------O                     | | O-----------------O
#                           |                                        | |                   |                     valid
#  sys_clk  _____           |                                        | O-------------------|------------------------->
#  --------|     |          |                                        |                     |
#  fs      |  &  |----------O shift_1                                | ena      _____      |
#  --------|_____|                                                   O---------|     |     |
#                                                                      sys_clk |  &  |-----O shift_2
#                                                                    ----------|_____|
# Pulse diagram:
#                     _   _   _   _   _   _   _   _   _   _   _   _   _   _   _   _   _   _   _   _   _
#           sys_clk _| |_| |_| |_| |_| |_| |_| |_| |_| |_| |_| |_| |_| |_| |_| |_| |_| |_| |_| |_| |_| |_
#                             ___             ___             ___             ___             ___
#           fs      _________|   |___________|   |____...____|   |___________|   |___________|   |_______
#                                ↑               ↑               ↑               ↑               ↑
#                       cnt      0               1              R-1              0               1
#                                    sample[0]       sample[1]       sample[R-1]
#                                                                                 ___
#           shift_2 _____________________________________________________________|   |_______________
#                                                                                     ___
#           valid   _________________________________________________________________|   |___________
#                                                                                    ↑
#                                                                               valid output
#
###################################################################################################################

class CIC_FILTER(Module):
    def __init__(self, M=5, R=64, W=8):

        # Caculate nbit
        nbit = W + math.ceil(M * math.log2(R))
        MIN  = -1 * pow(2, nbit - 1)
        MAX  = pow(2, nbit-1) - 1

        # Interface
        self.input  = input  = Signal(min=MIN, max=MAX)
        self.output = output = Signal(min=MIN, max=MAX)
        self.fs     = fs     = Signal()
        self.valid  = valid  = Signal()

        cnt   = Signal(max=R+1)
        ena   = Signal()
        buff  = Signal(min=MIN, max=MAX)

        intg = Array(Signal(min=MIN, max=MAX) for i in range(M))
        di   = Array(Signal(min=MIN, max=MAX) for i in range(M))
        comb = Array(Signal(min=MIN, max=MAX) for i in range(M))
        dc   = Array(Signal(min=MIN, max=MAX) for i in range(M))

        print("nbit = " + str(len(input)))

        self.comb += [
            intg[0].eq(buff + di[0]),
            output.eq(comb[M-1] - dc[M-1]),
        ]

        self.sync += [
            valid.eq(ena),
            If(ena,
                comb[0].eq(intg[M-1])
            ),
            If(fs,
                buff.eq(input),
                If(cnt < (R-1),
                    cnt.eq(cnt + 1),
                    ena.eq(0)
                ).Else( # cnt == (R-1)
                    ena.eq(1),
                    cnt.eq(0)
                ),
            ).Else(
                ena.eq(0)
            ),
        ]

        for i in range(M):
            self.sync += If(fs, di[i].eq(intg[i]))
            self.sync += If(ena, dc[i].eq(comb[i]))

        for i in range(1, M):
            self.comb += intg[i].eq(intg[i-1] + di[i])
            self.comb += comb[i].eq(comb[i-1] - dc[i-1])

###################################################################################################################
#
# PDM TO PCM CONVERTER
#
# Block diagram:
#                                           ____________             _______
#                                   input  |            |  output   |       |
#    pdm_dat  --->-------------------------|            |---------->|       |-------> i2s_sck
#                                       fs | CIC_FILTER |  valid    |  I2S  |-------> i2s_ws
#                                     o----|            |---------->|       |-------> i2s_so
#                                     |    |____________|           |_______|
#                      _________      |
#    sys_clk ---->----|         |-----o
#                     | CLK_GEN |---------------------------------------------------> pdm_clk
#    ena     ---->----|_________|---------------------------------------------------> pdm_sel
#
#
# Pulse diagram:
#                        _   _   _   _   _   _   _   _   _   _   _   _   _   _   _   _   _   _   _   _
#    sys_clk           _| |_| |_| |_| |_| |_| |_| |_| |_| |_| |_| |_| |_| |_| |_| |_| |_| |_| |_| |_| |_
#                           ↑   ↑           ↑
#                      cnt  0   1 ...      N-1
#                            ___             ___             ___             ___             ___
#    fs                _____|   |___________|   |___________|   |___________|   |___________|   |_______
#                            _______         _______         _______         _______         _______
#    pdm_clk (drive_f) _____|       |_______|       |_______|       |_______|       |_______|       |___
#                      _____         _______         _______         _______         _______         ___
#    pdm_clk (drive_r)      |_______|       |_______|       |_______|       |_______|       |_______|
#
#
#
###################################################################################################################

class PDM_TO_PCM(Module):
    def __init__(self, sys_clk_freq=100e3, fs_in=1e3, M=3, R=64, dw=16, scale_factor=100, pdm_clk_drive_f=True):

        # Caculate nbit
        nbit    = 1 + math.ceil(M * math.log2(R))
        MIN     = -1 * pow(2, nbit - 1)
        MAX     = pow(2, nbit-1) - 1
        I2S_MIN = -1 * pow(2, dw - 1)
        I2S_MAX = pow(2, dw-1) - 1
        N       = int(sys_clk_freq/fs_in)
        K       = int((N*R)/(4*dw))

        print("N = " + str(N))
        print("K = " + str(N))

        # Interface signals
        self.pdm_clk = pdm_clk  = Signal()
        self.pdm_dat = pdm_dat  = Signal()
        self.pdm_sel = pdm_sel  = Signal()
        self.i2s_sck = i2s_sck  = Signal()
        self.i2s_ws  = i2s_ws   = Signal()
        self.i2s_so  = i2s_so   = Signal()
        self.ena     = ena      = Signal()

        # Expose outside for debugging
        self.fs      = fs       = Signal()
        self.buff    = buff     = Signal(min=I2S_MIN, max=I2S_MAX)

        # Modules
        self.submodules.cic = cic = CIC_FILTER(M=M, R=R, W=1)
        self.submodules.edt = edt = ResetInserter()(EdgeDetector())

        # Internal signals
        buff_r        = Signal(min=I2S_MIN, max=I2S_MAX)
        buff_l        = Signal(min=I2S_MIN, max=I2S_MAX)
        is_right_chan = Signal()
        cnt           = Signal(max=N+1)
        br_cnt        = Signal(max=K+1)
        pulse_cnt     = Signal(8)
        i2s_pulse_ena = Signal()
        pdm_clk_drive = Signal()

        if pdm_clk_drive_f == True:
            self.comb += [
                pdm_sel.eq(0),
                pdm_clk.eq(pdm_clk_drive)
            ]
        else:
            self.comb += [
                pdm_sel.eq(1),
                pdm_clk.eq(~pdm_clk_drive)
            ]

        self.comb += [
            edt.reset.eq(~ena),
            edt.i.eq(i2s_sck),
            cic.input[0].eq(pdm_dat),
            cic.fs.eq(fs),
            If(is_right_chan,
                i2s_so.eq(buff_r[dw-1]), # MSB
            ).Else(
                i2s_so.eq(buff_l[dw-1]), # MSB
            )
        ]

        self.sync += [
            If(cic.valid,
                buff.eq(cic.output >> math.ceil(math.log2(scale_factor))),
                i2s_pulse_ena.eq(1),
            ),

            If(i2s_pulse_ena,
                If(br_cnt < (K-1),
                    br_cnt.eq(br_cnt + 1),
                ).Else(
                    i2s_sck.eq(~i2s_sck),
                    br_cnt.eq(0),
                    If(pulse_cnt < 2*dw-1,
                        pulse_cnt.eq(pulse_cnt + 1),
                    ).Else(
                        i2s_ws.eq(~i2s_ws),
                        pulse_cnt.eq(0),
                    )
                ),
                If(edt.f,
                    If(pulse_cnt == 2,
                        If(i2s_ws,
                            buff_r.eq(buff),
                            is_right_chan.eq(1)
                        ).Else(
                            buff_l.eq(buff),
                            is_right_chan.eq(0)
                        )
                    ).Else(
                        If(is_right_chan,
                            buff_r.eq(buff_r << 1),
                        ).Else(
                            buff_l.eq(buff_l << 1),
                        )
                    )
                ),
            )
        ]

        self.sync += [
            If(ena,
                If(cnt < (N-1),
                    cnt.eq(cnt + 1),
                    fs.eq(0),
                    If(cnt == (int(N/2)-1),
                        pdm_clk_drive.eq(0),
                    )
                ).Else(
                    fs.eq(1),
                    pdm_clk_drive.eq(1),
                    cnt.eq(0)
                )
            ).Else(
                fs.eq(0),
                pdm_clk_drive.eq(0),
                i2s_pulse_ena.eq(0)
            )
        ]

# Test bench functions -----------------------------------------------------

def CIC_FILTER_TB(dut):

    np.random.seed(0xBABECAFE)

    # CIC filter parameters
    M = 3  # number of stage
    R = 64 # decimination

    gain = (R * 1) ** M

    # signal frequency
    f1 = 100   # Hz
    f2 = 4e3   # Hz
    f3 = 50e3  # Hz
    f4 = 100e3 # Hz
    a  = 2

    # number of sample points
    # N should be multiple of R and N/R should be 2^m
    N = R * 1024

    # sample frequency and sample spacing
    # clocks = {"sys": int(1e9/640e3)}
    fs_in = 640e3
    K = 10 # fclk / fs_in ratio

    # Calculate parameter don't touch
    fclk = fs_in * K # 6400e3
    T = 1.0 / fs_in

    # Number of fclk cycle
    J = (N + 1) * K

    signal_in = []
    signal_out = []

    cnt = 0
    i = 0

    for cycle in range(J):
        if cnt < (K-1):
            cnt = cnt + 1
            yield dut.fs.eq(0)
        else:
            cnt = 0
            # Calculate input signal
            f = 0
            f += 10 * random.randint(-10000 , 10000) / 10000 # noise
            f += a * np.sin(2.0 * np.pi * f1 * i * T)
            f += a * np.sin(2.0 * np.pi * f2 * i * T)
            f += a * np.sin(2.0 * np.pi * f3 * i * T)
            f += a * np.sin(2.0 * np.pi * f4 * i * T)
            i = i + 1
            signal_in.append(f)
            yield dut.fs.eq(1)
            yield dut.input.eq(int(f))

        if (yield dut.valid) == 1:
            output = yield dut.output
            signal_out.append(output/gain)
        yield

    NFFT = len(signal_in) # NFFT-point DFT
    print("fs = " + str(fs_in))
    print("NFFT = " + str(NFFT))
    FL = -120e3
    FH = 120e3
    STEP = 20e3
    X = fftshift(fft(signal_in, NFFT)) # compute DFT using FFT
    fig, ax = plt.subplots(nrows=1, ncols=1) # create figure handle
    fVals = np.arange(start = -NFFT/2, stop = NFFT/2)*fs_in/NFFT # DFT Sample points
    ax.plot(fVals, np.abs(X))
    ax.set_title('Frequency domain input signal')
    ax.set_xlabel('Normalized Frequency(Hz)')
    ax.set_ylabel('DFT Values');
    ax.autoscale(enable=True, axis='x', tight=True)
    ax.set_xlim(FL, FH)
    ax.set_xticks(np.arange(FL, FH + STEP, STEP))
    plt.grid()

    NFFT = len(signal_out) # NFFT-point DFT
    fs = int(fs_in/R)
    print("fs = " + str(fs))
    print("NFFT = " + str(NFFT))
    FL = -1*int(fs/2)
    FH = int(fs/2)
    STEP = 1e3
    X = fftshift(fft(signal_out, NFFT)) # compute DFT using FFT
    fig, ax = plt.subplots(nrows=1, ncols=1) # create figure handle
    fVals = np.arange(start = -NFFT/2, stop = NFFT/2)*fs/NFFT # DFT Sample points
    ax.plot(fVals, np.abs(X))
    ax.set_title('Frequency domain output signal')
    ax.set_xlabel('Normalized Frequency(Hz)')
    ax.set_ylabel('DFT Values');
    ax.autoscale(enable=True, axis='x', tight=True)
    ax.set_xlim(FL, FH)
    ax.set_xticks(np.arange(FL, FH + STEP, STEP))
    plt.grid()

    plt.show()

def PDM_TO_PCM_TB(dut, sys_clk_freq=100e3, fs_in=1e3, M=3, R=64, dw=16, scale_factor=100):

    print("Running simulation, please be patient!")

    np.random.seed(0xBABECAFE)

    gain = (R * 1) ** M
    print("Gain = " + str(gain))

    # signal frequency
    f1 = 5e3  # Hz
    f2 = 10e3 # Hz
    f3 = 15e3 # Hz
    f4 = 50e3 # Hz

    # Calculate parameter don't touch
    K = int(sys_clk_freq/fs_in)
    T = 1.0 / fs_in
    print("K = " + str(K))

    # number of input sample points
    # N should be multiple of R and N/R should be 2^m
    N = R * 256

    # Number of fclk cycle
    J = (N + 1) * K

    # Prepare PDM data
    t = np.arange(N) / fs_in
    x  = 0.3 * random.randint(-10000 , 10000) / 10000 # noise
    x += 0.5 + 0.2 * np.sin(2.0 * np.pi * f1 * t)
    x += 0.2 * np.sin(2.0 * np.pi * f2 * t)
    x += 0.2 * np.sin(2.0 * np.pi * f3 * t)
    x += 0.2 * np.sin(2.0 * np.pi * f4 * t)
    y, error = pdm(x)

    signal_out = []
    i = 0

    for cycle in range(J):

        if cycle == 1:
            yield dut.ena.eq(1)

        if (yield dut.fs) == 1:
            if y[i] != 0:
                yield dut.pdm_dat.eq(1)
            else:
                yield dut.pdm_dat.eq(0)
            i = i + 1

        if (yield dut.cic.valid) == 1:
            output = yield dut.cic.output
            signal_out.append(output/scale_factor)

        yield

    # Display time domain signal input
    L = len(y)
    fig, ax = plt.subplots(nrows=1, ncols=1) # create figure handle
    tVals = np.arange(start = 0, stop = L)
    ax.plot(tVals, y, 'tab:orange')
    ax.set_title('Time domain input signal')
    ax.set_xlabel('Time(s)')
    ax.set_ylabel('Values');
    ax.autoscale(enable=True, axis='x', tight=True)
    ax.set_xlim(0, 400)
    ax.set_xticks(np.arange(0, 400 + 50, 50))
    plt.grid()

    # Display time domain signal output
    L = len(signal_out)
    fig, ax = plt.subplots(nrows=1, ncols=1) # create figure handle
    tVals = np.arange(start = 0, stop = L)
    ax.plot(tVals, signal_out, 'tab:green')
    ax.set_title('Time domain output signal')
    ax.set_xlabel('Time(s)')
    ax.set_ylabel('Values');
    ax.autoscale(enable=True, axis='x', tight=True)
    ax.set_xlim(0, 200)
    ax.set_xticks(np.arange(0, 200 + 10, 10))
    plt.grid()

    # Display frequency domain signal input
    NFFT = len(y) # NFFT-point DFT
    if NFFT >= 512:
        NFFT = 512
    fs = int(fs_in)
    print("fs = " + str(fs))
    print("NFFT = " + str(NFFT))
    FL = -1*int(fs/2)
    FH = int(fs/2)
    STEP = 200e3
    X = fftshift(fft(y, NFFT)) # compute DFT using FFT
    fig, ax = plt.subplots(nrows=1, ncols=1) # create figure handle
    fVals = np.arange(start = -NFFT/2, stop = NFFT/2)*fs/NFFT # DFT Sample points
    ax.plot(fVals, np.abs(X), 'tab:blue')
    ax.set_title('Frequency domain input signal')
    ax.set_xlabel('Normalized Frequency(Hz)')
    ax.set_ylabel('DFT Values');
    ax.autoscale(enable=True, axis='x', tight=True)
    ax.set_xlim(FL, FH)
    ax.set_xticks(np.arange(FL, FH + STEP, STEP))
    ax.xaxis.set_major_formatter(mtick.FormatStrFormatter('%.1e'))
    plt.grid()

    # Display frequency domain signal output
    NFFT = len(signal_out) # NFFT-point DFT
    fs = int(fs_in/R)
    print("fs = " + str(fs))
    print("NFFT = " + str(NFFT))
    FL = -1*int(fs/2)
    FH = int(fs/2)
    STEP = 10e3
    X = fftshift(fft(signal_out, NFFT)) # compute DFT using FFT
    fig, ax = plt.subplots(nrows=1, ncols=1) # create figure handle
    fVals = np.arange(start = -NFFT/2, stop = NFFT/2)*fs/NFFT # DFT Sample points
    ax.plot(fVals, np.abs(X), 'tab:red')
    ax.set_title('Frequency domain output signal')
    ax.set_xlabel('Normalized Frequency(Hz)')
    ax.set_ylabel('DFT Values');
    ax.autoscale(enable=True, axis='x', tight=True)
    ax.set_xlim(FL, FH)
    ax.set_xticks(np.arange(FL, FH + STEP, STEP))
    ax.xaxis.set_major_formatter(mtick.FormatStrFormatter('%.1e'))
    plt.grid()

    plt.show()

# main function ------------------------------------------------------------

if __name__ == "__main__":

    # # Simulate PDM and display the waveform
    # plot_demo_pdm()

    # dut = CIC_FILTER(M=3, R=64, W=8)
    # run_simulation(dut, CIC_FILTER_TB(dut), clocks={"sys": int(1e9/6400e3)}, vcd_name="CIC_FILTER.vcd")

    dut = PDM_TO_PCM(sys_clk_freq=96000e3, fs_in=2400e3, M=5, R=50, dw=16, scale_factor=1e6)
    run_simulation(dut, PDM_TO_PCM_TB(dut, sys_clk_freq=96000e3, fs_in=2400e3, M=5, R=50, dw=16, scale_factor=1e6), clocks={"sys": int(1e9/96000e3)}, vcd_name="PDM_TO_PCM.vcd")

