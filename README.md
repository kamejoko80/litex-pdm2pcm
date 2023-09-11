# Design a PDM to PCM converter and implement it on an FPGA.

In this project, we implement a simple PDM to PCM converter (PDM2PCM) based on the Migen FHDL library and Litex framework. We've utilized the CIC filter as a primary component and provided source code support for flexible input parameter adjustment.
In addition, the simulation part illustrates how to verify the results of a design, and finally, deploy it onto a specific FPGA hardware platform for demostration.

# Host PC Build System Requirements

```shell
• Ubuntu 18.04 LTS or later.
• Python 3.x

$ sudo apt install build-essential device-tree-compiler wget git python3-setuptools python3-pip libftdi* libboost-all-dev
$ sudo apt-get install libeigen3-dev aptitude clang tcl tcl8.6-dev libreadline-dev flex bison gcc-multilib g++-multilib
$ pip3 install numpy matplotlib scipy
```

## Installing Verilator (only needed for simulation)

```shell
$ sudo apt install verilator
$ sudo apt install libevent-dev libjson-c-dev
$ sudo apt install gtkwave
```

## Install iCE40 toolchains

```shell
$ mkdir toolchains
$ cd toolchains
$ git clone --recurse-submodules https://github.com/YosysHQ/icestorm.git
$ cd icestorm
$ make -j$(nproc)
$ sudo make install
```

## Intsall NextPNR (In somecase you need to build cmake (new version from source))

```shell
$ tar -xvf v3.20.1.tar.gz
$ CMake-3.20.1
$ ./bootstrap
$ ./configure
$ make -j$(nproc)
```

## Install libtrellis

```shell
$ cd toolchains
$ git clone --recursive https://github.com/YosysHQ/prjtrellis
$ cd prjtrellis/libtrellis
$ cmake -DCMAKE_INSTALL_PREFIX=/usr/local .
$ make -j$(nproc)
$ sudo make install
```

```shell
$ cd toolchains
$ git clone --recurse-submodules https://github.com/YosysHQ/nextpnr
$ cd nextpnr
$ cmake -DARCH="ice40;ecp5" -DCMAKE_INSTALL_PREFIX=/usr/local .
$ make -j$(nproc)
$ sudo make install
```

## Install nextpnr-xilinx (experiment)

```shell
https://github.com/gatecat/nextpnr-xilinx
```

## Intsall yosys

```shell
$ cd toolchains
$ git clone --recurse-submodules https://github.com/YosysHQ/yosys.git yosys
$ cd yosys
$ make -j$(nproc)
$ sudo make install
```

## Install Project Build Environment

```shell
$ mkdir workdir
$ cd workdir
$ git clone https://github.com/kamejoko80/litex-pdm2pcm.git
$ cd litex-pdm2pcm
$ chmod a+x litex_setup.py
$ ./litex_setup.py dev init install --user
```

## Project Folder Structure

1. Build environment structure is oganized as below:

```shell
.
+-- workdir
¦   +-- litex
¦   +-- litex-boards
¦   +-- litex-pdm2pcm
¦   +-- migen
+-- toolchains
    +-- icestorm
    +-- nextpnr
    +-- prjtrellis
    +-- yosys
```

```shell
• litex : A colection of Litex's libraries.
• litex-boards : Defined different FPGA HW platforms.
• migen : Mignen FHDL library.
• toolchains : Open source verilog HDL synthesizer (yosys), place and router (nextpnr) ...
```

2. Project folder structure:

```shell
.
+-- LICENSE
+-- README.md
+-- custom_boards
¦   +-- platforms
¦       +-- icestick.py
+-- custom_ipcores
¦   +-- pdm.py
+-- custom_projects
¦   +-- pdm_to_pcm_icestick.py
+-- litex_setup.py
```

```python
• custom_boards   : Defined custom FPGA HW platform.
• custom_ipcores  : Custom FHDL ipcore source code.
• custom_projects : Custom FPGA project.
```

# How Does It Work?
PDM is a digital audio representation that represents audio as a stream of 1s and 0s, where the density of 1s in a time interval represents the amplitude of the audio signal. It's typically used in digital microphones. Each rising or falling edge of the PDM signal represents a change in the audio waveform. Before converting PDM to PCM, it's common to apply a low-pass filter to the PDM data. This filter helps remove high-frequency noise and smooth out the signal. The specifics of the filter design depend on your hardware and requirements. PDM data is usually sampled at a very high rate (often in the megahertz range), which is much higher than the typical audio sample rate (e.g., 44.1 kHz for CD-quality audio). Decimation is the process of reducing the sample rate of the PDM data to match the target PCM sample rate. CIC filter has 2 above characteristics and there are some advantages such as high performance, resource, and power efficiency... Furthermore, it does not require complex operations, including multiplication, division, and floating-point coefficients, so it is definitely suitable for FPGA applications. Refer to [this link](https://www.dsprelated.com/showarticle/1337.php) for the details of how the CIC filter circuit works.

In the project, the CIC filter has been implemented as the below block diagram:

```python
I/O signals:

• input     : PDM signal input (one-bit data)
• sys_clock : FPGA sync clock input.
• fs        : Signal input sample frequency.
• output    : PCM signal output (n-bit data)
• valid     : Pulse indicates that the output signal is valid.

Parameters:

• M         : Number of stages.
• R         : Decimation ratio.
• W         : Output data width.

###################################################################################################################
#
# CONFIGURABLE CIC FILTER IMPLEMENTATION WITH A SEPARATED SAMPLING FREQUENCY INPUT
#
# Block diagram:
#                                 Integrators                     Decimator              Combs
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
```

The below block diagram shows how all components are connected together, PDM data input from DMIC (I used Merry 88D201020001). Depending on pdm_sel, the PDM output data is valid at the rising/falling edge of pdm_clk.
PCM output is connected directly to the I2S module. The sampling frequency can be defined in module PDM_TO_PCM(), value is about 1.5MHz - 2.4MHz. The output I2S signals can be connected with a simple DAC IC such as MAX98357A. 
The CIC includes 2's complement integer add/subtract, to ensure that the output does not overflow, its bit width needs to satisfy the following condition:

```python
nbit = 1 + math.ceil(M * math.log2(R))
```

In general, the bit width of I2S input is 8, 16, and 24 so we need to scale down the CIC output before feeding the PCM data into the I2S module. It is simply defined by a scale_factor parameter:

```python
self.sync += [
    If(cic.valid,
        buff.eq(cic.output >> math.ceil(math.log2(scale_factor))),
        i2s_pulse_ena.eq(1),
    ),
   ...

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
```

# Simulation

Let's start to simulate and verify the design. First, modify the main function (in pdm.py) as below:

```
dut = CIC_FILTER(M=3, R=64, W=8)
run_simulation(dut, CIC_FILTER_TB(dut), clocks={"sys": int(1e9/6400e3)}, vcd_name="CIC_FILTER.vcd")
```

Parameter descriptions:

```python
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

The input signal includes some frequency components and white noise,
the input sampling frequency is fs_in = 640KHz, output sampling frequency = fs_in/R = 10KHz.

```

Execute the below commands to run the simulation:

```shell
$ cd workdir/litex-pdm2pcm/custom_ipcores
$ python3 pdm.py
```

![Frequency response](/picture/simulation_1_1.png "Frequency response")


The output response shows that higher-frequency components (> 5Khz) have been removed completely. 
Also, there is a .vcd file has been generated as a result of simulation command, We can verify the details of the internal signals as well.

```shell
$ gtkwave CIC_FILTER.vcd
```

![Simulation waveform](/picture/simulation_1_2.png "Simulation waveform")

To verify the actual HW design, let's go with the simulation test bench below:  

```python
dut = PDM_TO_PCM(sys_clk_freq=96000e3, fs_in=2400e3, M=5, R=50, dw=16, scale_factor=1e6)
run_simulation(dut, PDM_TO_PCM_TB(dut, sys_clk_freq=96000e3, fs_in=2400e3, M=5, R=50, dw=16, scale_factor=1e6), clocks={"sys": int(1e9/96000e3)}, vcd_name="PDM_TO_PCM.vcd")
```

The parameters are set closely to real-world conditions:

```python
• sys_clk_freq  : FPGA sync frequency = 96MHz
• fs_in         : PDM oversampling rate = 2.4MHz (pdm_clk)
• M             : CIC stages = 5
• R             : Decimation ratio = 50 => fs_out = 48KHz
• dw            : 16 bit PCM data output
• scale_factor  : scale_factor = 1e6 
```

The input includes some sinusoidal frequency components 5KHz, 10KHz, 15KHz, and 50KHz, background noise is also added.
The test bench function PDM_TO_PCM_TB() converts input to the PDM data before feeding into the CIC filter, in result We have the input/output as below:

![Time domain waveform](/picture/simulation_2_1.png "Input/Output signal waveform")

With CIC stage = 5, we have a better filter output, not only higher-frequency but also background noise has been removed completely.

![Frequency domain response](/picture/simulation_2_2.png "Input/Output frequency response")

Finally, the internal signal waveform can be verified from the PDM_TO_PCM.vcd file.

![Signal wavefrom](/picture/simulation_2_3.png "Signal waveform")

# Reference links:

https://www.koheron.com/blog/2016/09/27/pulse-density-modulation

https://en.wikipedia.org/wiki/Pulse-density_modulation

https://www.dsprelated.com/showarticle/1337.php

https://www.gaussianwaves.com/2020/01/how-to-plot-fft-in-python-fft-of-basic-signals-sine-and-cosine-waves/

https://matplotlib.org/stable/gallery/subplots_axes_and_figures/subplots_demo.html

