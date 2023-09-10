# litex-pdm2pcm

In this project, we implement a simple PDM to PCM converter (PDM2PCM) based on the Migen FHDL library and Litex framework. We've utilized the CIC filter as a primary component and provided source code support for flexible input parameter adjustment.
In addition, the simulation part illustrates how to verify the results of a design, and finally, deploy it onto a specific FPGA hardware platform for demostration.

# Host PC Build System Requirements

• Ubuntu 18.04 LTS or later.
• Python 3.x

```
$ sudo apt install build-essential device-tree-compiler wget git python3-setuptools python3-pip libftdi* libboost-all-dev
$ sudo apt-get install libeigen3-dev aptitude clang tcl tcl8.6-dev libreadline-dev flex bison gcc-multilib g++-multilib
$ pip3 install numpy matplotlib scipy
```

## Installing Verilator (only needed for simulation)

```
$ sudo apt install verilator
$ sudo apt install libevent-dev libjson-c-dev
$ sudo apt install gtkwave
```

## Install iCE40 toolchains

```
$ mkdir toolchains
$ cd toolchains
$ git clone --recurse-submodules https://github.com/YosysHQ/icestorm.git
$ cd icestorm
$ make -j$(nproc)
$ sudo make install
```

## Intsall NextPNR (In somecase you need to build cmake (new version from source))

```
$ tar -xvf v3.20.1.tar.gz
$ CMake-3.20.1
$ ./bootstrap
$ ./configure
$ make -j$(nproc)
```

## Install libtrellis

```
$ cd toolchains
$ git clone --recursive https://github.com/YosysHQ/prjtrellis
$ cd prjtrellis/libtrellis
$ cmake -DCMAKE_INSTALL_PREFIX=/usr/local .
$ make -j$(nproc)
$ sudo make install
```

```
$ cd toolchains
$ git clone --recurse-submodules https://github.com/YosysHQ/nextpnr
$ cd nextpnr
$ cmake -DARCH="ice40;ecp5" -DCMAKE_INSTALL_PREFIX=/usr/local .
$ make -j$(nproc)
$ sudo make install
```

## Install nextpnr-xilinx (experiment)

```
https://github.com/gatecat/nextpnr-xilinx
```

## Intsall yosys

```
$ cd toolchains
$ git clone --recurse-submodules https://github.com/YosysHQ/yosys.git yosys
$ cd yosys
$ make -j$(nproc)
$ sudo make install
```

## Install Project Build Environment

```
$ mkdir workdir
$ cd workdir
$ git clone https://github.com/kamejoko80/litex-pdm2pcm.git
$ cd litex-pdm2pcm
$ chmod a+x litex_setup.py
$ ./litex_setup.py dev init install --user
```

## Project Folder Structure

1. Build environment structure is oganized as below:

```
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

• litex : A colection of Litex's libraries.

• litex-boards : Defined different FPGA HW platforms.

• migen : Mignen FHDL library.

• toolchains : Open source verilog HDL synthesizer (yosys), place and router (nextpnr) ...

2. Project folder structure:

```
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

• custom_boards   : Defined custom FPGA HW platform.

• custom_ipcores  : Custom FHDL ipcore source code.

• custom_projects : Custom FPGA project.

# How Does It Work?

The main component of PDM2PCM is the CIC filter. CIC filter has some advantages such as high performance, resource, and power efficiency... Furthermore, it does not require complex operations, including multiplication, division, and floating-point coefficients.
In this project, we don't go into the details of how the CIC filter circuit works, so you can refer to [this link](https://www.dsprelated.com/showarticle/1337.php) for more information.

# Simulation


# Reference links:
  https://www.koheron.com/blog/2016/09/27/pulse-density-modulation
  https://en.wikipedia.org/wiki/Pulse-density_modulation
  https://www.dsprelated.com/showarticle/1337.php
  https://www.gaussianwaves.com/2020/01/how-to-plot-fft-in-python-fft-of-basic-signals-sine-and-cosine-waves/
  https://matplotlib.org/stable/gallery/subplots_axes_and_figures/subplots_demo.html
