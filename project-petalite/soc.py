#!/usr/bin/env python3

# from migen import *

from migen.genlib.io import CRG


from litex.soc.cores import dna
from litex.soc.integration.soc_core import SoCCore
from litex.soc.integration.builder import Builder
from litex.build.sim import SimPlatform
from litex.build.sim.config import SimConfig
from litex.build.xilinx import XilinxPlatform
from litex.build.generic_platform import IOStandard, Pins, Subsignal

from liteeth.phy.rmii import LiteEthPHYRMII
from liteeth.phy.model import LiteEthPHYModel
from liteeth.common import convert_ip

import argparse
import json


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
        "--local-ip",
        type=str,
        default="192.168.1.50",
        help="Local ip for ethernet",
    )
    parser.add_argument(
        "--remote-ip",
        type=str,
        default="192.168.1.100",
        help="Remote ip for ethernet",
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


# SoC Design -------------------------------------------------------------------------------------------
class ProjectPetalite(SoCCore):
    def __init__(
        self,
        platform: Platform,
        sys_clk_freq: int,
        # Necessary for Ethernet... delete if comm changes
        local_ip: int,
        remote_ip: int,
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
            with_uart=True,
            uart_name="sim",
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

        # Ethernet Physical Core.
        # TODO: stop simulating, and use core according to board
        # self.ethphy = LiteEthPHYRMII(
        #     clock_pads=self.platform.request("eth_clocks"),
        #     pads=self.platform.request("eth"),
        # )
        self.submodules.ethphy = LiteEthPHYModel(self.platform.request("eth", 0))
        self.add_csr("ethphy")

        # Connecting ethernet communication to Wishbone bus
        self.add_etherbone(
            phy=self.ethphy,
            # Ethernet physical params
            ip_address=convert_ip(local_ip) + 1,
            mac_address=0x10E2D5000001,
            # Ethernet MAC params
            with_ethmac=True,
            ethmac_address=0x10E2D5000000,
            ethmac_local_ip=local_ip,
            ethmac_remote_ip=remote_ip,
        )


def main():
    args = arg_parser()

    io = load_io_from_json(args.io_json)
    sys_clk_freq = int(args.sys_clk_freq)

    platform = SimulatedPlatform(io)
    soc = ProjectPetalite(
        platform=platform,
        sys_clk_freq=sys_clk_freq,
        local_ip=args.local_ip,
        remote_ip=args.remote_ip,
        integrated_rom_init=args.firmware,
    )

    sim_config = SimConfig()
    sim_config.add_module("serial2console", "serial")
    sim_config.add_clocker("sys_clk", freq_hz=sys_clk_freq)
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
