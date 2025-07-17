#!/usr/bin/env python3
from typing import Optional

from migen import ClockDomain, Signal
from migen.genlib.io import CRG

from migen import *
from migen.genlib.io import CRG
from litex.soc.interconnect.wishbone import SRAM
from litex.soc.integration.soc import SoCRegion
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
from csr_mailbox import PetaliteMailbox
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
        clk_domain_name: str,
        trace: bool = False,
        host_bus_interfaces: Optional[HostBusInterfaces] = None,
        integrated_rom_init: str | list = [],
    ):

        # ---------------- Custom params --------------------
        self.platform_instance = platform
        self.is_simulated = isinstance(platform, SimPlatform)
        self.core_type = core_type
        self.host_bus_interfaces = host_bus_interfaces
        self.clk_domain_name = clk_domain_name

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
        # uart_pads = self.platform_instance.request("serial", 0)
        # self.add_uart(uart_name="sim")

        if self.core_type != CoreType.EMBEDDED:
            self.add_id()

        if trace:
            self.comb += self.platform_instance.trace.eq(1)

        self.heartbeat = Signal()
        self.sync += self.heartbeat.eq(~self.heartbeat)

        self.add_debug_mem()

    def get_memories(self):
        # Hide inner memory regions from the outer SoC
        return [] if self.core_type == CoreType.EMBEDDED else super().get_memories()

    def setup_clk(self: SoCCore):
        if self.core_type == CoreType.EMBEDDED:
            self.clock_domains.cd_sys = ClockDomain(self.clk_domain_name)
        elif self.is_simulated:
            self.crg = CRG(self.platform_instance.request("sys_clk"))

    def add_id(self: SoCCore):
        if not self.is_simulated:
            self.submodules.dna = DNA()
            self.add_csr("dna")

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

            # Create petalite's side of mailbox
            self.add_mailbox()

            # self.add_etherbone_bridge()

        elif self.core_type == CoreType.PCIE_DEVICE:
            pass
        elif self.core_type == CoreType.HOST:
            if self.is_simulated:
                self.add_uart(uart_name="sim")
            else:
                self.add_uart(uart_name="serial")
        else:
            raise RuntimeError()

    def add_mailbox(self: SoCCore):
        # Create petalite's mailbox
        self.submodules.mailbox = PetaliteMailbox()

        # ONLY add petalite's CSRs to petalite
        self.add_csr("mailbox")
        # Manually add CSRs to petalite's CSR space

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

    def add_etherbone_bridge(self: SoCCore):
        from liteeth.phy.model import LiteEthPHYModel
        from liteeth.common import convert_ip

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

    def add_debug_mem1(
        self: SoCCore,
    ):
        # Debug memory
        self.debug_mem = Memory(32, 16, init=[0] * 16)
        debug_port = self.debug_mem.get_port(write_capable=True)
        self.submodules.debug_port = debug_port

        self.bus.add_slave("debug", debug_port, SoCRegion(size=64))

        # Only export specific locations you care about
        self.debug_word0 = Signal(32)  # Just first word
        self.debug_word1 = Signal(32)  # Just second word

        # Read ports for specific addresses
        read_port0 = self.debug_mem.get_port()
        read_port1 = self.debug_mem.get_port()
        self.submodules.read_port0 = read_port0
        self.submodules.read_port1 = read_port1

        self.comb += [
            read_port0.adr.eq(0),  # Always read address 0
            read_port1.adr.eq(1),  # Always read address 1
            self.debug_word0.eq(read_port0.dat_r),
            self.debug_word1.eq(read_port1.dat_r),
        ]

    def add_debug_mem(self: SoCCore):
        size = 64  # bytes (16 × 32-bit words)

        # 1) Wishbone-facing RAM
        self.submodules.debug_ram = SRAM(
            size, init=[0] * 16
        )  # or SRAM(size, init=[0]*16)
        self.bus.add_slave(
            "debug",
            self.debug_ram.bus,
            SoCRegion(origin=0x3000_0000, size=size, cached=False),
        )

        # 2) Internal read ports (for the waveform/trace taps)
        rp0 = self.debug_ram.mem.get_port()  # ← NOTE: .mem, not .port
        rp1 = self.debug_ram.mem.get_port()
        self.specials += rp0, rp1  # keep the ports!

        self.debug_word0 = Signal(32)
        self.debug_word1 = Signal(32)

        self.comb += [rp0.adr.eq(0), rp1.adr.eq(1)]  # constant addresses
        self.sync += [self.debug_word0.eq(rp0.dat_r), self.debug_word1.eq(rp1.dat_r)]


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
                if args.trace
                else None
            ),
            trace=args.trace,
            trace_fst=args.trace,
        )

    else:
        builder.build(**platform.get_argdict(platform.toolchain, {}))

        if args.load:
            prog = platform.create_programmer()
            prog.load_bitstream(builder.get_bitstream_filename(mode="sram"), device=1)


if __name__ == "__main__":
    main()
