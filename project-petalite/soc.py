#!/usr/bin/env python3

from migen import Instance
from migen.genlib.io import CRG

from litex.soc.cores import dna
from litex.soc.cores.dma import WishboneDMAReader, WishboneDMAWriter
from litex.soc.integration.builder import Builder
from litex.soc.integration.soc_core import SoCCore
from litex.soc.interconnect.csr import CSR, CSRStorage

from litex.build.sim import SimPlatform
from litex.build.sim.config import SimConfig
from litex.build.xilinx import XilinxPlatform
from litex.build.generic_platform import IOStandard, Pins, Subsignal

import argparse
import json

from .dilithium import Dilithium
from .stream_bridge import CSRStreamBridge


def str_to_int(s):
    try:
        f = float(s)
    except ValueError:
        raise argparse.ArgumentTypeError(f"Value '{s}' is not a number.")

    if not f.is_integer():
        raise argparse.ArgumentTypeError(f"Value '{s}' is not an integer value.")

    return int(f)


def load_io_from_json(json_path):
    def int_or_str(s):
        try:
            return int(s)
        except ValueError:
            return s

    with open(json_path, "r") as f:
        raw_io_data = json.load(f)

    parsed_io_array = []
    for raw_entry in raw_io_data:
        parsed_entry = [raw_entry["name"], raw_entry["index"]]

        if "subsignals" in raw_entry:
            subsignals = [
                Subsignal(name, Pins(int_or_str(signal["pins"])))
                for name, signal in raw_entry["subsignals"].items()
            ]
            parsed_entry.extend(subsignals)

        else:
            parsed_entry.append(Pins(int_or_str(raw_entry["pins"])))

        if raw_entry.get("iostandard"):
            parsed_entry.append(IOStandard(raw_entry["iostandard"]))

        parsed_io_array.append(tuple(parsed_entry))

    return parsed_io_array


def arg_parser():
    parser = argparse.ArgumentParser(description="Project Petalite SoC")
    parser.add_argument(
        "--io-json",
        type=str,
        required=True,
        help="Path to the io json config.",
    )
    parser.add_argument(
        "--sys-clk-freq",
        type=str_to_int,
        default=1e6,
        help="System clock frequency",
    )
    parser.add_argument(
        "--build-dir",
        type=str,
        default="./build",
        help="Path to the build dir.",
    )
    parser.add_argument(
        "--only-build",
        action="store_true",
        default=False,
        help="Only build the SoC without running the simulation.",
    )
    parser.add_argument(
        "--firmware",
        type=str,
        help="Path to the firmware binary file. Required if --only_build is not set.",
    )
    parser.add_argument(
        "--comm",
        type=str,
        default="uart",
        help="Communication protocol",
    )
    parser.add_argument(
        "--rtl_dir_path",
        type=str,
        default="./dilithium/rtl_src",
        help="Directory path for custom cores",
    )

    args = parser.parse_args()
    if not args.only_build and not args.firmware:
        parser.error("--firmware is required when --only_build is not set.")
    if args.only_build and args.firmware:
        parser.error("--firmware is ignored when --only_build is set.")

    return args


# Platforms -----------------------------------------------------------------------------------------
class Platform(XilinxPlatform):
    default_clk_name = "sys_clk"

    def __init__(self, io):
        XilinxPlatform.__init__(self, "xc7a100t-csg324-1", io, toolchain="vivado")


class SimulatedPlatform(SimPlatform):
    def __init__(self, io):
        SimPlatform.__init__(self, "SIM", io)

    def add_rtl_sources(self, path: str):
        self.add_source_dir(path=path)


# SoC Design -------------------------------------------------------------------------------------------
class ProjectPetalite(SoCCore):
    def __init__(
        self,
        platform: Platform,
        sys_clk_freq: int,
        # Necessary for Ethernet... delete if comm changes
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
            cpu_type="rocket",
            cpu_variant="small",
            clk_freq=sys_clk_freq,
            # Communication with terminal
            with_uart=False,
            # Memory specs
            integrated_rom_size=0x1_0000,
            integrated_rom_init=integrated_rom_init if integrated_rom_init else [],
            # integrated_main_ram_size=0x1_0000, TODO: cant use main_ram because of SBI...
        )

        # Clock Reset Generation
        self.submodules.crg = CRG(
            platform.request("sys_clk"),
            # TODO: necessary when targeting real board
            # ~platform.request("cpu_reset")
        )

        # FPGA identification
        if not isinstance(platform, SimPlatform):
            self.submodules.dna = dna.DNA()
            self.add_csr("dna")

        self.add_comm_capability(comm_protocol=comm_protocol)
        self.add_dilithium()

    def add_comm_capability(self: SoCCore, comm_protocol: str):
        if comm_protocol == "uart":
            self.add_uart(uart_name="sim")

        elif comm_protocol == "pcie":
            pass

    def add_dilithium(self: SoCCore):
        # For now, Dilithium without DMA
        self.submodules.stream_bridge = CSRStreamBridge(data_width=64)
        self.submodules.dilithium = Dilithium()

        self.start = CSRStorage(1)
        self.mode = CSRStorage(2)
        self.sec_lvl = CSRStorage(3)

        self.comb += [self.stream_bridge.source.connect(self.dilithium.sink)]
        self.comb += [
            self.dilithium.start.eq(self.start.storage),
            self.dilithium.mode.eq(self.mode.storage),
            self.dilithium.sec_lvl.eq(self.sec_lvl.storage),
        ]


def main():
    args = arg_parser()

    io = load_io_from_json(args.io_json)
    sys_clk_freq = int(args.sys_clk_freq)

    platform = SimulatedPlatform(io)
    platform.add_rtl_sources(path=args.rtl_dir_path)

    soc = ProjectPetalite(
        platform=platform,
        sys_clk_freq=sys_clk_freq,
        comm_protocol=args.comm,
        integrated_rom_init=args.firmware,
    )

    sim_config = SimConfig()
    sim_config.add_clocker("sys_clk", freq_hz=sys_clk_freq)

    if args.comm == "uart":
        sim_config.add_module("serial2console", "serial")
    elif args.comm == "ethernet":
        sim_config.add_module(
            "ethernet", "eth", args={"interface": "tap0", "ip": args.remote_ip}
        )

    builder = Builder(
        soc, output_dir=args.build_dir, compile_gateware=(not args.only_build)
    )

    # TODO: sim is considerably slower than an equal configuration on litex_sim... investigate why
    builder.build(
        run=(not args.only_build),
        sim_config=sim_config,
        interactive=False,
    )


if __name__ == "__main__":
    main()
