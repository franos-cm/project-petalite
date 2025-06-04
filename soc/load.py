#!/usr/bin/env python3
from migen import ClockDomain, Signal, ClockSignal, ResetSignal
from migen.genlib.io import CRG

from litex.soc.cores import dna
from litex.soc.cores.led import LedChaser
from litex.soc.cores.clock import S7PLL
from litex.soc.integration.builder import Builder
from litex.soc.integration.soc_core import SoCCore
from litex.soc.integration.soc import LiteXModule
from litex.soc.interconnect.csr import CSRStorage

from litex.build.sim import SimPlatform
from litex.build.sim.config import SimConfig
from litex.build.generic_platform import GenericPlatform
from litex_boards.platforms import digilent_zybo_z7

from dilithium import Dilithium
from stream_bridge import CSRToStreamBridge, StreamToCSRBridge
from platform import PetaliteSimPlatform
from soc import ProjectPetalite
from utils import arg_parser


def main():
    # Platform definition
    platform = digilent_zybo_z7.Platform(variant="z7-20")
    platform.add_source_dir(path=args.rtl_dir_path)

    # SoC definition
    soc = ProjectPetalite(
        platform=platform,
        sys_clk_freq=args.sys_clk_freq,
        comm_protocol=args.comm,
        integrated_rom_init=args.firmware,
    )

    # Building stage
    builder = Builder(
        soc=soc, output_dir=args.build_dir, compile_gateware=args.compile_gateware
    )

    prog = platform.create_programmer()
    prog.load_bitstream(builder.get_bitstream_filename(mode="sram"), device=1)


if __name__ == "__main__":
    main()
