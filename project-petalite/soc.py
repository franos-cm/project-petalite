#!/usr/bin/env python3
from migen import ClockDomain, Signal, ClockSignal, ResetSignal
from migen.genlib.io import CRG

from litex.soc.cores import dna
from litex.soc.cores.led import LedChaser
from litex.soc.cores.clock import S7PLL, S7IDELAYCTRL
from litex.soc.integration.builder import Builder
from litex.soc.integration.soc_core import SoCCore
from litex.soc.integration.soc import LiteXModule
from litex.soc.interconnect.csr import CSRStorage

from litedram.phy import s7ddrphy
from litedram.modules import MT41K128M16
from liteeth.phy.mii import LiteEthPHYMII

from litex.build.sim import SimPlatform
from litex.build.sim.config import SimConfig
from litex.build.generic_platform import GenericPlatform
from litex_boards.platforms import digilent_arty

from dilithium import Dilithium
from stream_bridge import CSRToStreamBridge, StreamToCSRBridge
from fpga_platform import PetaliteSimPlatform
from utils import arg_parser


# SoC Design -------------------------------------------------------------------------------------------


class _CRG(LiteXModule):
    def __init__(self, platform, sys_clk_freq, with_dram=True, with_rst=True):
        self.rst = Signal()
        self.cd_sys = ClockDomain()
        self.cd_eth = ClockDomain()
        if with_dram:
            self.cd_sys4x = ClockDomain()
            self.cd_sys4x_dqs = ClockDomain()
            self.cd_idelay = ClockDomain()

        # # #

        # Clk/Rst.
        clk100 = platform.request("clk100")
        rst = ~platform.request("cpu_reset") if with_rst else 0

        # PLL.
        self.pll = pll = S7PLL(speedgrade=-1)
        self.comb += pll.reset.eq(rst | self.rst)
        pll.register_clkin(clk100, 100e6)
        pll.create_clkout(self.cd_sys, sys_clk_freq)
        pll.create_clkout(self.cd_eth, 25e6)
        self.comb += platform.request("eth_ref_clk").eq(self.cd_eth.clk)
        platform.add_false_path_constraints(
            self.cd_sys.clk, pll.clkin
        )  # Ignore sys_clk to pll.clkin path created by SoC's rst.
        if with_dram:
            pll.create_clkout(self.cd_sys4x, 4 * sys_clk_freq)
            pll.create_clkout(self.cd_sys4x_dqs, 4 * sys_clk_freq, phase=90)
            pll.create_clkout(self.cd_idelay, 200e6)

        # IdelayCtrl.
        if with_dram:
            self.idelayctrl = S7IDELAYCTRL(self.cd_idelay)


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
            cpu_type="picorv32",
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
            self.crg = _CRG(platform, sys_clk_freq, with_dram)
        else:
            self.crg = CRG(platform.request("sys_clk"))

        if not self.integrated_main_ram_size:
            self.ddrphy = s7ddrphy.A7DDRPHY(
                platform.request("ddram"),
                memtype="DDR3",
                nphases=4,
                sys_clk_freq=sys_clk_freq,
            )
            self.add_sdram(
                "sdram",
                phy=self.ddrphy,
                module=MT41K128M16(sys_clk_freq, "1:4"),
                l2_cache_size=8192,
            )

        # FPGA identification -----------------------------------
        if not self.is_simulated:
            self.submodules.dna = dna.DNA()
            self.add_csr("dna")

        self.add_comm_capability(comm_protocol=comm_protocol)
        # self.add_dilithium()

        self.leds = LedChaser(
            pads=platform.request_all("user_led"), sys_clk_freq=sys_clk_freq
        )

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

    # TODO: extend this once Im using the hardcore, see arty z7 target.
    # def finalize(self, *args, **kwargs):
    #     super(ProjectPetalite, self).finalize(*args, **kwargs)
    #     if self.cpu_type != "zynq7000":
    #         return


def main():
    args = arg_parser()

    # Platform definition
    platform = (
        PetaliteSimPlatform(io_path=args.io_json)
        if args.sim
        else digilent_arty.Platform(variant="a7-100")
    )
    # platform.add_source_dir(path=args.rtl_dir_path)
    # platform.add_extension(digilent_arty._sdcard_pmod_io)

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
