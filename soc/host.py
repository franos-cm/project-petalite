#!/usr/bin/env python3
from migen.genlib.io import CRG
from migen.genlib.cdc import ClockDomainsRenamer

from litex.soc.cores.dna import DNA
from litex.soc.integration.builder import Builder
from litex.soc.integration.soc_core import SoCCore
from litex.soc.interconnect import wishbone

from litex.build.sim import SimPlatform
from litex.build.sim.config import SimConfig
from litex.build.generic_platform import GenericPlatform

from platforms import PetaliteSimPlatform
from helpers import CoreType, host_arg_parser, generate_gtkw_savefile
from petalite import PetaliteCore


class EmbeddedHost(SoCCore):
    def __init__(
        self,
        platform: GenericPlatform,
        sys_clk_freq: int,
        debug: bool = False,
        host_rom_init: str | list = [],
        core_rom_init: str | list = [],
    ):

        # ---------------- Custom params --------------------
        self.is_simulated = isinstance(platform, SimPlatform)
        self.clk_signal = platform.request("sys_clk")

        # ----------- Instantiate base SoC ------------------
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
            integrated_rom_init=host_rom_init,
            # integrated_main_ram_size=0x1_0000,  # TODO: cant use main_ram because of SBI...
        )

        # self.add_id()
        self.setup_clk()
        self.add_io()
        self.add_petalite_core(core_rom_init=core_rom_init, platform=platform)

        if debug:
            self.comb += self.platform.trace.eq(1)

        print("DONE3")

    def add_id(self: SoCCore):
        if not self.is_simulated:
            self.submodules.dna = DNA()
            self.add_csr("dna")

    def setup_clk(self: SoCCore):
        if self.is_simulated:
            self.crg = CRG(self.clk_signal)
        else:
            pass

    def add_io(self: SoCCore):
        if self.is_simulated:
            self.add_uart(uart_name="sim")
        else:
            self.add_uart(uart_name="serial")

    def add_petalite_core(
        self: SoCCore, platform: GenericPlatform, core_rom_init: str | list = []
    ):
        # Add bus master interfaces
        petalite_reader = wishbone.Interface(data_width=64)
        petalite_writer = wishbone.Interface(data_width=64)
        self.bus.add_master(name="petalite_reader", master=petalite_reader)
        self.bus.add_master(name="petalite_writer", master=petalite_writer)

        petalite = PetaliteCore(
            core_type=CoreType.EMBEDDED,
            platform=platform,
            sys_clk_freq=self.clk_freq,
            host_bus_interfaces=(petalite_reader, petalite_writer),
            integrated_rom_init=core_rom_init,
        )
        self.comb += [
            petalite.cd_sys.clk.eq(self.crg.cd_sys.clk),
            petalite.cd_sys.rst.eq(self.crg.cd_sys.rst),
        ]

        self.submodules.petalite = petalite
        self.add_csr("petalite")

        print("DOOONE")

        # self.add_csr("petalite")

        print("DOOONE2")


def main():
    # TODO: check LitePCIeSoC
    args = host_arg_parser()

    # Platform definition
    platform = (
        PetaliteSimPlatform(io_path=args.io_json, rtl_dir_path=args.rtl_dir_path)
        if args.sim
        else None
    )

    # SoC definition
    soc = EmbeddedHost(
        platform=platform,
        sys_clk_freq=args.sys_clk_freq,
        host_rom_init=args.host_firmware,
        core_rom_init=args.petalite_firmware,
    )

    print("DONE4")

    # Building stage
    builder = Builder(
        soc=soc, output_dir=args.build_dir, compile_gateware=args.compile_gateware
    )

    print("DONE5")

    if args.sim:
        sim_config = SimConfig()
        sim_config.add_clocker("sys_clk", freq_hz=args.sys_clk_freq)
        sim_config.add_module("serial2console", "serial")

        print("DONE6")
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
