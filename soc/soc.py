#!/usr/bin/env python3
from migen.genlib.io import CRG

from litex.soc.cores import dna
from litex.soc.integration.builder import Builder
from litex.soc.integration.soc_core import SoCCore
from litex.soc.interconnect.csr import CSRStorage

from litex.build.sim import SimPlatform
from litex.build.sim.config import SimConfig
from litex.build.generic_platform import GenericPlatform

from dilithium import Dilithium
from stream_bridge import CSRToStreamBridge, StreamToCSRBridge
from fpga_platform import PetaliteSimPlatform
from utils import arg_parser


class ProjectPetalite(SoCCore):
    def __init__(
        self,
        platform: GenericPlatform,
        sys_clk_freq: int,
        comm_protocol: str,
        integrated_rom_init: str = None,
    ):

        # SoC with CPU
        SoCCore.__init__(
            self,
            # System specs
            platform,
            ident="Project Petalite",
            ident_version=True,
            # CPU specs
            cpu_type="vexriscv",
            cpu_variant="standard",
            # cpu_type="rocket",
            # cpu_variant="small",
            clk_freq=sys_clk_freq,
            # Communication with terminal
            with_uart=False,
            # Memory specs
            integrated_rom_size=0x1_0000,
            integrated_rom_init=integrated_rom_init if integrated_rom_init else [],
            # integrated_main_ram_size=0x1_0000, TODO: cant use main_ram because of SBI...
        )
        self.is_simulated = isinstance(platform, SimPlatform)
        with_dram = self.integrated_main_ram_size == 0

        # CRG ---------------------------------------------------
        if not self.is_simulated:
            pass
        else:
            self.crg = CRG(platform.request("sys_clk"))

        # FPGA identification -----------------------------------
        if not self.is_simulated:
            self.submodules.dna = dna.DNA()
            self.add_csr("dna")

        self.add_comm_capability(comm_protocol=comm_protocol)
        self.add_dilithium()

    def add_comm_capability(self: SoCCore, comm_protocol: str):
        if comm_protocol == "uart":
            if self.is_simulated:
                self.add_uart(uart_name="sim")
            else:
                self.add_uart(uart_name="serial")
        elif comm_protocol == "pcie":
            pass

    def add_dilithium(self: SoCCore):
        # For now, Dilithium without DMA
        self.submodules.csr_to_stream_bridge = CSRToStreamBridge(data_width=64)
        self.submodules.stream_to_csr_bridge = StreamToCSRBridge(data_width=64)
        self.submodules.dilithium = Dilithium()

        self.start = CSRStorage(1)
        self.mode = CSRStorage(2)
        self.sec_lvl = CSRStorage(3)

        self.comb += [
            self.csr_to_stream_bridge.stream.connect(self.dilithium.sink),
            self.stream_to_csr_bridge.stream.connect(self.dilithium.source),
            self.dilithium.start.eq(self.start.storage),
            self.dilithium.mode.eq(self.mode.storage),
            self.dilithium.sec_lvl.eq(self.sec_lvl.storage),
        ]


def main():
    args = arg_parser()

    # Platform definition
    platform = PetaliteSimPlatform(io_path=args.io_json) if args.sim else None
    platform.add_dilithium_src(path=args.rtl_dir_path)

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

    if args.sim:
        sim_config = SimConfig()
        sim_config.add_clocker("sys_clk", freq_hz=args.sys_clk_freq)
        if args.comm == "uart":
            sim_config.add_module("serial2console", "serial")
        elif args.comm == "pcie":
            pass

        builder.build(
            run=args.load,
            sim_config=sim_config,
            interactive=False,
        )

    else:
        builder.build(**platform.get_argdict(platform.toolchain, {}))

        if args.load:
            prog = platform.create_programmer()
            prog.load_bitstream(builder.get_bitstream_filename(mode="sram"), device=1)


if __name__ == "__main__":
    main()
