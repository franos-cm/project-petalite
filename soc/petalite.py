#!/usr/bin/env python3
from migen.genlib.io import CRG

from litex.soc.cores.dna import DNA
from litex.soc.cores.dma import WishboneDMAReader, WishboneDMAWriter
from litex.soc.integration.builder import Builder
from litex.soc.integration.soc_core import SoCCore
from litex.soc.interconnect import wishbone

from litex.build.sim import SimPlatform
from litex.build.sim.config import SimConfig
from litex.build.generic_platform import GenericPlatform

from liteeth.phy.model import LiteEthPHYModel
from liteeth.common import convert_ip

from dilithium import Dilithium
from platforms import PetaliteSimPlatform
from helpers import arg_parser, generate_gtkw_savefile, CommProtocol


class PetaliteCore(SoCCore):
    is_simulated: bool

    def __init__(
        self,
        comm_protocol: CommProtocol,
        platform: GenericPlatform,
        sys_clk_freq: int,
        integrated_rom_init: str | list = [],
        clk_domain_name: str = None,
        debug_bridge: bool = False,
        trace: bool = False,
    ):
        self.platform_instance = platform
        self.is_simulated = isinstance(platform, SimPlatform)
        self.clk_domain_name = clk_domain_name
        self.comm_protocol = comm_protocol

        # SoC with CPU
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
        self.add_id()
        self.add_io()
        self.add_dilithium()
        if debug_bridge:
            self.add_etherbone_bridge()

        # Simulation debugging ----------------------------------------------------------------------
        if trace:
            trace_reset_on = True
            self.platform_instance.add_debug(self, reset=1 if trace_reset_on else 0)
        else:
            self.comb += self.platform_instance.trace.eq(1)

    def setup_clk(self: SoCCore):
        if self.is_simulated:
            self.crg = CRG(self.platform_instance.request("sys_clk"))

    def add_id(self: SoCCore):
        if not self.is_simulated:
            self.submodules.dna = DNA()
            self.add_csr("dna")

    def add_io(self: SoCCore):
        if self.comm_protocol == CommProtocol.PCIE:
            pass
        elif self.comm_protocol == CommProtocol.UART:
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
        self.add_csr("dilithium_reader")
        self.add_csr("dilithium_writer")

        self.submodules.dilithium = Dilithium()
        self.add_csr("dilithium")
        self.comb += [
            self.dilithium_reader.source.connect(self.dilithium.sink),
            self.dilithium.source.connect(self.dilithium_writer.sink),
        ]

        # Add memory region for sig and pk
        # NOTE: this puts the buffer inside of IO region
        # I guess thats not ideal... but otherwise, the CPU was unable
        # to access the given mem position, like 0x83000000.
        # We also had to add an extra param to the add_ram method to account for that.
        self.add_ram(
            "dilithium_buffer",
            origin=0x30000000,
            size=0x2000,
            mode="rw",
            custom=True,
        )

    def add_etherbone_bridge(self: SoCCore):
        self.ethphy = LiteEthPHYModel(self.platform.request("eth", 0))
        self.add_constant("HW_PREAMBLE_CRC")

        self.add_etherbone(
            phy=self.ethphy,
            # Etherbone Parameters.
            ip_address=convert_ip("192.168.1.50"),
            mac_address=0x10E2D5000001,
            data_width=8,
            # Ethernet Parameters.
            with_ethmac=False,
            ethmac_address=0x10E2D5000000,
            ethmac_local_ip="192.168.1.50",
            ethmac_remote_ip="192.168.1.100",
        )


def main():
    # TODO: check LitePCIeSoC
    args = arg_parser()

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
        comm_protocol=args.comm,
        integrated_rom_init=args.firmware,
        trace=args.trace,
        debug_bridge=args.debug_bridge,
    )

    # Building stage
    builder = Builder(
        soc=soc, output_dir=args.build_dir, compile_gateware=args.compile_gateware
    )

    if args.sim:
        sim_config = SimConfig()
        sim_config.add_clocker("sys_clk", freq_hz=args.sys_clk_freq)
        if args.comm == CommProtocol.UART:
            sim_config.add_module("serial2tcp", ("serial", 0), args={"port": 4327})

        if args.debug_bridge:
            sim_config.add_module(
                "ethernet", "eth", args={"interface": "tap0", "ip": "192.168.1.100"}
            )

        builder.build(
            run=args.load,
            sim_config=sim_config,
            interactive=False,
            pre_run_callback=(
                (lambda vns: generate_gtkw_savefile(builder, vns, True))
                if args.trace
                else None
            ),
            trace=args.trace,
            trace_fst=args.trace,
            trace_start=18_850_000_000 if args.trace else None,  # (in ns)
        )

    else:
        builder.build(**platform.get_argdict(platform.toolchain, {}))

        if args.load:
            prog = platform.create_programmer()
            prog.load_bitstream(builder.get_bitstream_filename(mode="sram"), device=1)


if __name__ == "__main__":
    main()
