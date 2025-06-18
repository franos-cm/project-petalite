#!/usr/bin/env python3
from migen.genlib.io import CRG

from litex.soc.cores import dna
from litex.soc.cores.dma import WishboneDMAReader, WishboneDMAWriter
from litex.soc.integration.builder import Builder
from litex.soc.integration.soc_core import SoCCore
from litex.soc.interconnect.csr import CSRStorage
from litex.soc.interconnect import wishbone

from litex.build.sim import SimPlatform
from litex.build.sim.config import SimConfig
from litex.build.generic_platform import GenericPlatform

from dilithium import Dilithium
from fpga_platform import PetaliteSimPlatform
from utils import arg_parser, generate_gtkw_savefile


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
            # cpu_type="vexriscv",
            # cpu_variant="standard",
            # For now, necessary since its 64 bits
            cpu_type="rocket",
            cpu_variant="small",
            bus_data_width=64,
            clk_freq=sys_clk_freq,
            # Communication with terminal
            with_uart=False,
            # Memory specs
            integrated_rom_size=131072,
            integrated_sram_size=8192,
            integrated_rom_init=integrated_rom_init if integrated_rom_init else [],
            # integrated_main_ram_size=0x1_0000,  # TODO: cant use main_ram because of SBI...
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

        self.comb += platform.trace.eq(1)
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
        # Add bus masters
        wb_dilithium_reader = wishbone.Interface(
            data_width=64,  # adr_width=32, addressing="byte"
        )
        wb_dilithium_writer = wishbone.Interface(
            data_width=64,  # adr_width=32, addressing="byte"
        )
        self.bus.add_master(name="dilithium_reader", master=wb_dilithium_reader)
        self.bus.add_master(name="dilithium_writer", master=wb_dilithium_writer)

        self.submodules.dilithium_reader = WishboneDMAReader(
            wb_dilithium_reader, with_csr=True
        )
        self.submodules.dilithium_writer = WishboneDMAWriter(
            wb_dilithium_writer, with_csr=True
        )
        self.add_csr("dilithium_reader")
        self.add_csr("dilithium_writer")

        self.start = CSRStorage(1)
        self.mode = CSRStorage(2)
        self.sec_lvl = CSRStorage(3)
        self.add_csr("start")
        self.add_csr("mode")
        self.add_csr("sec_lvl")

        self.submodules.dilithium = Dilithium()

        self.comb += [
            self.dilithium_reader.source.connect(self.dilithium.sink),
            self.dilithium.source.connect(self.dilithium_writer.sink),
            self.dilithium.start.eq(self.start.storage),
            self.dilithium.mode.eq(self.mode.storage),
            self.dilithium.sec_lvl.eq(self.sec_lvl.storage),
        ]


def main():
    # TODO: check LitePCIeSoC
    args = arg_parser()

    # Platform definition
    platform = PetaliteSimPlatform(io_path=args.io_json) if args.sim else None
    platform.add_dilithium_src(top_level_dir_path=args.rtl_dir_path)

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

        def pre_run_callback(vns):
            generate_gtkw_savefile(builder, vns, True)

        builder.build(
            run=args.load,
            sim_config=sim_config,
            interactive=False,
            pre_run_callback=pre_run_callback,
            # Turn this into a param
            trace=True,
            trace_fst=True,
        )

    else:
        builder.build(**platform.get_argdict(platform.toolchain, {}))

        if args.load:
            prog = platform.create_programmer()
            prog.load_bitstream(builder.get_bitstream_filename(mode="sram"), device=1)


if __name__ == "__main__":
    main()
