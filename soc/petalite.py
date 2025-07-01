#!/usr/bin/env python3
from typing import Optional

from migen import ClockDomain, Instance
from migen.genlib.io import CRG

from litex.soc.cores.dna import DNA
from litex.soc.cores.dma import WishboneDMAReader, WishboneDMAWriter
from litex.soc.integration.builder import Builder
from litex.soc.integration.soc_core import SoCCore
from litex.soc.interconnect.csr import CSRStorage
from litex.soc.interconnect import wishbone
from litex.build.sim import SimPlatform
from litex.build.sim.config import SimConfig
from litex.build.generic_platform import GenericPlatform

from dilithium import Dilithium
from platforms import PetaliteSimPlatform
from helpers import (
    CoreType,
    HostBusInterfaces,
    petalite_arg_parser,
    generate_gtkw_savefile,
)


class PetaliteCore(SoCCore):
    is_simulated: bool
    core_type: CoreType
    host_bus_interfaces: HostBusInterfaces | None

    def __init__(
        self,
        core_type: CoreType,
        platform: GenericPlatform,
        sys_clk_freq: int,
        debug: bool = False,
        host_bus_interfaces: Optional[HostBusInterfaces] = None,
        integrated_rom_init: str | list = [],
    ):

        # ---------------- Custom params --------------------
        self.is_simulated = isinstance(platform, SimPlatform)
        self.core_type = core_type
        self.host_bus_interfaces = host_bus_interfaces

        # Instantiate base SoC
        SoCCore.__init__(
            self,
            # System specs
            platform,
            ident="Petalite Core",
            ident_version=True,
            # CPU specs
            cpu_type="rocket",
            cpu_variant="small",
            bus_data_width=64,
            clk_freq=sys_clk_freq,
            # Communication
            with_uart=False,
            # Memory specs
            integrated_rom_size=0x20000,
            integrated_sram_size=0x2000,
            integrated_rom_init=integrated_rom_init,
            # integrated_main_ram_size=0x1_0000,  # TODO: cant use main_ram because of SBI...
        )

        self.setup_clk()
        # self.add_dilithium()
        self.add_io()
        if self.core_type != CoreType.EMBEDDED:
            self.add_id()

        if debug:
            self.comb += self.platform.trace.eq(1)

    def get_memories(self):
        # Hide inner BRAMs from the outer SoC
        return [] if self.core_type == CoreType.EMBEDDED else super().get_memories()

    def add_id(self: SoCCore):
        if not self.is_simulated:
            self.submodules.dna = DNA()
            self.add_csr("dna")

    def setup_clk(self: SoCCore):
        if self.core_type == CoreType.EMBEDDED:
            self.clock_domains.cd_sys = ClockDomain("sys")
        elif self.is_simulated:
            self.crg = CRG(self.platform.request("sys_clk"))

    def add_io(self: SoCCore):
        if self.core_type == CoreType.EMBEDDED:
            # ------------------- DMA -------------------
            assert (
                self.host_bus_interfaces is not None
            ), "If core is embedded, host bus interfaces need to be provided"
            host_reader_interface, host_writer_interface = self.host_bus_interfaces

            self.submodules.host_reader = WishboneDMAReader(
                host_reader_interface, with_csr=True
            )
            self.submodules.host_writer = WishboneDMAWriter(
                host_writer_interface, with_csr=True
            )
            self.add_csr("host_reader")
            self.add_csr("host_writer")

            # ------------------- CSRs -------------------
            # Host → Petalite
            self.cmd_value = CSRStorage(32)
            self.cmd_valid = CSRStorage(1)
            self.cmd_ack = CSRStorage(1)
            self.add_csr("cmd_value")
            self.add_csr("cmd_valid")
            self.add_csr("cmd_ack")

            # Petalite → Host
            self.rsp_value = CSRStorage(32)
            self.rsp_valid = CSRStorage(1)
            self.rsp_ack = CSRStorage(1)
            self.add_csr("rsp_value")
            self.add_csr("rsp_valid")
            self.add_csr("rsp_ack")

        elif self.core_type == CoreType.PCIE_DEVICE:
            pass
        elif self.core_type == CoreType.HOST:
            if self.is_simulated:
                self.add_uart(uart_name="sim")
            else:
                self.add_uart(uart_name="serial")
        else:
            raise RuntimeError()

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
        # TODO: Do I need this csr if Im alrady doing with_csr?
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
    args = petalite_arg_parser()

    # Platform definition
    platform = (
        PetaliteSimPlatform(io_path=args.io_json, rtl_dir_path=args.rtl_dir_path)
        if args.sim
        else None
    )

    # SoC definition
    soc = PetaliteCore(
        platform=platform,
        sys_clk_freq=args.sys_clk_freq,
        core_type=args.type,
        integrated_rom_init=args.firmware,
    )

    # Building stage
    builder = Builder(
        soc=soc, output_dir=args.build_dir, compile_gateware=args.compile_gateware
    )

    if args.sim:
        sim_config = SimConfig()
        sim_config.add_clocker("sys_clk", freq_hz=args.sys_clk_freq)
        if args.type == CoreType.HOST:
            sim_config.add_module("serial2console", "serial")

        builder.build(
            run=args.load,
            sim_config=sim_config,
            interactive=False,  # TODO: revise this
            pre_run_callback=(
                (lambda vns: generate_gtkw_savefile(builder, vns, True))
                if args.debug
                else None
            ),
            trace=args.debug,
            trace_fst=args.debug,
        )

    else:
        builder.build(**platform.get_argdict(platform.toolchain, {}))

        if args.load:
            prog = platform.create_programmer()
            prog.load_bitstream(builder.get_bitstream_filename(mode="sram"), device=1)


if __name__ == "__main__":
    main()
