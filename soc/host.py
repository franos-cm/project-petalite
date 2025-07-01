#!/usr/bin/env python3
import os
from functools import partial
from typing import Callable

from migen.genlib.io import CRG

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
        sys_clk_freq: int,
        platform_factory: Callable[[], GenericPlatform],
        debug: bool = False,
        host_rom_init: str | list = [],
        core_rom_init: str | list = [],
        platform_passthrough: bool = True,
    ):

        # ---------------- Custom params --------------------
        self.platform_instance = platform_factory()
        self.is_simulated = isinstance(self.platform_instance, SimPlatform)
        self.clk_signal = self.platform_instance.request("sys_clk")
        self.platform_passthrough = platform_passthrough

        # ----------- Instantiate base SoC ------------------
        SoCCore.__init__(
            self,
            # System specs
            self.platform_instance,
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
        self.add_petalite_core(
            platform_factory=platform_factory,
            core_rom_init=core_rom_init,
        )

        if debug:
            self.comb += self.platform_instance.trace.eq(1)

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
        self: SoCCore,
        platform_factory: Callable[[], GenericPlatform],
        core_rom_init: str | list = [],
    ):
        # Add bus master interfaces
        petalite_reader = wishbone.Interface(data_width=64)
        petalite_writer = wishbone.Interface(data_width=64)
        self.bus.add_master(name="petalite_reader", master=petalite_reader)
        self.bus.add_master(name="petalite_writer", master=petalite_writer)

        platform = (
            self.platform_instance if self.platform_passthrough else platform_factory()
        )

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


def get_platform(io_json, rtl_dir_path, is_simulated):
    if is_simulated:
        return PetaliteSimPlatform(io_path=io_json, rtl_dir_path=rtl_dir_path)
    return None


def main():
    # TODO: check LitePCIeSoC
    args = host_arg_parser()

    # Platform definition. NOTE: hacky way to be able to compile both accelerator and host using the same platform (copied twice)
    platform_factory = partial(
        get_platform,
        io_json=args.io_json,
        rtl_dir_path=args.rtl_dir_path,
        is_simulated=args.sim,
    )

    # SoC definition
    soc = EmbeddedHost(
        platform_factory=platform_factory,
        sys_clk_freq=args.sys_clk_freq,
        host_rom_init=args.host_firmware,
        core_rom_init=args.petalite_firmware,
        platform_passthrough=not args.compile_petalite_software,
    )

    # Host Building stage
    if args.compile_petalite_software:
        petalite_soc = soc.petalite
        petalite_builder = Builder(
            soc=petalite_soc,
            output_dir=os.path.join(args.build_dir, "petalite"),
            compile_gateware=False,
        )

    host_builder = Builder(
        soc=soc,
        output_dir=os.path.join(args.build_dir, "host"),
        compile_gateware=args.compile_gateware,
    )

    if args.sim:
        sim_config = SimConfig()
        sim_config.add_clocker("sys_clk", freq_hz=args.sys_clk_freq)
        sim_config.add_module("serial2console", "serial")

        print("\nBuilding Petalite Core...\n")
        petalite_builder.build()
        print("\nBuilding Host...\n")
        host_builder.build(
            run=args.load,
            sim_config=sim_config,
            interactive=False,  # TODO: revise this
            pre_run_callback=(
                (lambda vns: generate_gtkw_savefile(host_builder, vns, True))
                if args.debug
                else None
            ),
            trace=args.debug,
            trace_fst=args.debug,
        )

    else:
        platform = soc.platform_instance
        print("\nBuilding Petalite Core...\n")
        petalite_builder.build(**platform.get_argdict(platform.toolchain, {}))
        print("\nBuilding Host...\n")
        host_builder.build(**platform.get_argdict(platform.toolchain, {}))

        if args.load:
            prog = platform.create_programmer()
            prog.load_bitstream(
                host_builder.get_bitstream_filename(mode="sram"), device=1
            )


if __name__ == "__main__":
    main()
