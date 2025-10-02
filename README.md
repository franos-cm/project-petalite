# Overview

**Project Petalite** is a proof-of-concept for a hardware Trusted Platform Module (TPM) that implements post-quantum cryptography (PQC), specifically the CRYSTALS-Dilithium signature scheme.

Although PQC has started to become standardized — the most recent example being ML-KEM and ML-DSA, both based on the CRYSTALS suite — no such algorithm is currently a part of the official TPM specification. Therefore, investigating how those schemes could be integrated into a future version of the TPM is especially interesting.

As such, this project implements a SoC that runs a modified version of the TPM reference code, which includes new commands (and opcodes) for the Dilithium algorithm. The reason for using new commands, as opposed to including Dilithium as a parameter option for the pre-existing commands, will be explained later.

# 1. Introduction

This project originally started out as an attempt at developing a RTL core for accelerating the Dilithium algorithm. But when researching that topic, I realized this particular challenge had already been solved several times before, with as many different architectures as target devices.

With that in mind, I shifted my focus to exploring how these existing designs could be used in practical scenarios, as opposed to just validating them against minimal testbenches, like the ones offered by the authors of the designs — in the cases where testbenches were provided at all. In other words, I wanted to demonstrate how a computer could leverage those cores as dedicated crypto-processors for real cryptographic tasks.

This in turn led me to, instead of building a whole new crypto-processor out of these cores, integrating them into an existing and widely-used standard: the Trusted Platform Module.

# 2. Building and running the project

This project can be run either as a software simulation or as a synthesised design on a FPGA board. In either case, we use the Litex framework for designing and building the SoC, so we need to install it. Refer to the official Litex installation instructions, or do as follows:

1. Create a Python virtual environment:

    ``` bash
    python -m venv .venv
    source .venv/bin/activate
    ```

2. Download and install Litex, along with the Rocket CPU, and RISC-V compiler tools:

    ```
    mkdir tools && cd tools
    wget https://raw.githubusercontent.com/enjoy-digital/litex/master/litex_setup.py
    chmod +x litex_setup.py && python ./litex_setup.py --init --install --gcc=riscv --config=standard
    pip install git+https://github.com/litex-hub/pythondata-cpu-rocket.git
    ```

## 2.1. As a software simulation

Litex already has some simulation capabilities built-in, using Verilator as its backend. Install it through your package manager, or refer to the official Verilator documentation for the installation instructions.


> ℹ️ **Note**
>
> In order to be correctly elaborated, the Dilithium RTL design uses Verilator pragma commands which are available from version v5.036 onwards. If that or a later version is not available through your package manager, building from source is advised.
>


1. Make sure Verilator is installed and sourced:

    ``` bash
    which verilator
    ```

2. Run the helper script for building the SoC and its firmware:

    ``` bash
    ./scripts/build.sh --force-all
    ```

3. Finally, build the gateware and run the simulation:
    ``` bash
    python soc/petalite.py --sim --io-json=soc/data/io_sim.json --build-dir=builds/soc --compile-gateware --firmware=builds/firmware.bin --load
    ```

The simulation can be interacted with using UART tunneled over TCP. To run some sample TCP commands, try:

```
python test/tpm.py
```

## 2.2. As a FPGA design

Likewise, Litex itself does not elaborate or synthesise the designs it produces. Instead, it depends on backends to do so. Since this project originally targeted a Xilinx board (the NetFPGA-SUME), we used Vivado; refer to its official website for installing it.

1. Make sure Vivado is installed and sourced:

    ``` bash
    which vivado
    ```

2. Run the helper script for building the SoC and its firmware, targeting a real board:

    ``` bash
    ./scripts/build.sh --force-all --board
    ```

3. Build the gateware, and perform elaboration, synthesis, PnR:
    ``` bash
    python soc/petalite.py --build-dir=builds/soc --compile-gateware --firmware=builds/firmware.bin
    ```
    The output of this command is very extensive, so piping it to a log file is recommended.

4. Finally, program the board using another helper script:
    ``` bash
    ./scripts/program-board.sh builds/soc/gateware/digilent_netfpga_sume.bit
    ```

Again, the implemented design can be interacted with using UART tunneled over a USB device. To run some sample TCP commands, try:

```
python test/tpm.py --serial
```
