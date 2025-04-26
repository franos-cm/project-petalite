#!/usr/bin/env python3

# from migen import *

from migen.genlib.io import CRG

from litex.build.xilinx import XilinxPlatform
from litex.build.generic_platform import IOStandard, Pins, Subsignal

from litex.soc.cores import dna
from liteeth.phy.rmii import LiteEthPHYRMII
from liteeth.phy.model import LiteEthPHYModel

from litex.soc.integration.soc_core import SoCCore
from litex.soc.integration.builder import Builder
from litex.build.sim import SimPlatform
from litex.build.sim.config import SimConfig


# Platforms -----------------------------------------------------------------------------------------
class Platform(XilinxPlatform):
    default_clk_name = "sys_clk"
    # default_clk_period = 1e9 / 100e6

    def __init__(self, io):
        XilinxPlatform.__init__(self, "xc7a100t-csg324-1", io, toolchain="vivado")


class SimulatedPlatform(SimPlatform):
    default_clk_name = "sys_clk"

    def __init__(self, io):
        SimPlatform.__init__(self, "SIM", io)


# Design -------------------------------------------------------------------------------------------
class ProjectPetalite(SoCCore):
    def __init__(self, platform: Platform, sys_clk_freq: int):

        # SoC with CPU
        SoCCore.__init__(
            self,
            platform,
            cpu_type="rocket",
            cpu_variant="medium",
            clk_freq=sys_clk_freq,
            ident="Project Petalite",
            ident_version=True,
            # Uart seems necessary
            with_uart=True,
            uart_name="sim",
            # Why overwrite this?
            integrated_rom_size=0x1_0000,
            # TODO: cant use main_ram because of SBI...
            # integrated_main_ram_size=0x1_0000,
        )

        # Clock Reset Generation
        self.submodules.crg = CRG(
            platform.request("sys_clk"), ~platform.request("cpu_reset")
        )

        # FPGA identification
        if not isinstance(platform, SimPlatform):
            self.submodules.dna = dna.DNA()
            self.add_csr("dna")

        # Ethernet Physical Core.
        # Decide which core to use according to board
        # TODO: stop simulating
        # self.submodules.ethphy = LiteEthPHYRMII(
        #     clock_pads=self.platform.request("eth_clocks"),
        #     pads=self.platform.request("eth"),
        # )
        self.ethphy = LiteEthPHYModel(self.platform.request("eth", 0))
        self.add_csr("ethphy")

        # Connecting ethernet communication to Wishbone bus
        self.add_etherbone(
            phy=self.ethphy,
            # Etherbone params
            ip_address="192.168.1.50",
            mac_address=0x10E2D5000001,
            # Ethernet MAC params...
            # TODO: change this if full networking is needed
            with_ethmac=False,
        )


def main():
    # TODO: Change IO in future according to board... maybe even use jsons to parametrize
    _io = [
        ("sys_clk", 0, Pins("E3"), IOStandard("LVCMOS33")),
        ("cpu_reset", 0, Pins("C12"), IOStandard("LVCMOS33")),
        # Ethernet (Stream Endpoint).
        (
            "eth_clocks",
            0,
            Subsignal("tx", Pins(1)),
            Subsignal("rx", Pins(1)),
        ),
        (
            "eth",
            0,
            Subsignal("source_valid", Pins(1)),
            Subsignal("source_ready", Pins(1)),
            Subsignal("source_data", Pins(8)),
            Subsignal("sink_valid", Pins(1)),
            Subsignal("sink_ready", Pins(1)),
            Subsignal("sink_data", Pins(8)),
        ),
        # Serial.
        (
            "serial",
            0,
            Subsignal("source_valid", Pins(1)),
            Subsignal("source_ready", Pins(1)),
            Subsignal("source_data", Pins(8)),
            Subsignal("sink_valid", Pins(1)),
            Subsignal("sink_ready", Pins(1)),
            Subsignal("sink_data", Pins(8)),
        ),
    ]

    sys_clk_freq = int(100e6)

    # Instantiate the platform and SoC
    platform = SimulatedPlatform(_io)
    soc = ProjectPetalite(platform=platform, sys_clk_freq=sys_clk_freq)

    # Build the SoC
    builder = Builder(soc, output_dir="build", compile_gateware=False)

    sim_config = SimConfig()
    sim_config.add_clocker("sys_clk", freq_hz=sys_clk_freq)

    builder.build(run=False, sim_config=sim_config)


if __name__ == "__main__":
    main()
