#!/usr/bin/env python3
from migen.genlib.io import CRG

from litex.soc.cores.dna import DNA
from litex.soc.cores.dma import WishboneDMAReader, WishboneDMAWriter
from litex.soc.integration.builder import Builder
from litex.soc.integration.soc_core import SoCCore
from litex.soc.integration.common import get_mem_data
from litex.soc.interconnect import wishbone

from litex.build.sim import SimPlatform
from litex.build.sim.config import SimConfig
from litex.build.generic_platform import GenericPlatform
from litex_boards.platforms import digilent_netfpga_sume

from liteeth.phy.model import LiteEthPHYModel
from liteeth.common import convert_ip

from litespi.phy.model import LiteSPIPHYModel
from litespi.modules import S25FL128L
from litespi.opcodes import SpiNorFlashOpCodes as Codes

from dilithium import Dilithium, add_dilithium_src
from platforms import PetaliteSimPlatform
from helpers import arg_parser, generate_gtkw_savefile, CommProtocol, KBYTE


from migen import *
from litex.gen import *
from litex.soc.cores.clock import *
from litedram.modules import MT8KTF51264
from litedram.phy import s7ddrphy


class _CRG(LiteXModule):
    def __init__(self, platform, sys_clk_freq):
        self.rst = Signal()
        self.cd_sys = ClockDomain()
        self.cd_sys4x = ClockDomain()
        self.cd_idelay = ClockDomain()
        self.cd_sfp = ClockDomain()

        self.pll = pll = S7PLL(speedgrade=-2)
        self.comb += pll.reset.eq(platform.request("cpu_reset_n") | self.rst)
        pll.register_clkin(platform.request("clk200"), 200e6)
        pll.create_clkout(self.cd_sys, sys_clk_freq)
        pll.create_clkout(self.cd_sys4x, 4 * sys_clk_freq)
        pll.create_clkout(self.cd_idelay, 200e6)
        pll.create_clkout(self.cd_sfp, 200e6)

        platform.add_false_path_constraints(self.cd_sys.clk, pll.clkin)

        self.idelayctrl = S7IDELAYCTRL(self.cd_idelay)


class PetaliteCore(SoCCore):
    is_simulated: bool

    def __init__(
        self,
        platform: GenericPlatform,
        sys_clk_freq: int,
        comm_protocol: CommProtocol,
        integrated_rom_path: str = None,
        nvm_mem_init: str = None,
        debug_bridge: bool = False,
        trace: bool = False,
    ):
        self.platform_instance = platform
        self.is_simulated = isinstance(platform, SimPlatform)
        self.sys_clk_freq = sys_clk_freq
        self.comm_protocol = comm_protocol
        self.bus_data_width = 64

        # In theory, we could pass the integrated_rom_init to the SoC intiializer
        # In practice, there is a bug by which if you do that, the size of the ROM is incorrectly calculated
        # So for now we pass the integrated_rom_init as a list of the instructions, but we should do a Litex PR for that
        # For that, we need do know the data_width and endianness of the CPU a priori, which is fine,
        # as long as we remember to change it if we switch CPUs
        integrated_rom_data = (
            get_mem_data(integrated_rom_path, data_width=64, endianness="little")
            if integrated_rom_path
            else []
        )

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
            # Memory specs, considering full TPM firmware
            # Increase SRAM size if we need more heap/stack mem
            integrated_rom_size=210 * KBYTE,
            integrated_sram_size=128 * KBYTE,
            integrated_rom_init=integrated_rom_data,
            # integrated_main_ram_size=0x1_0000,  # TODO: cant use main_ram because of SBI...
        )

        self.setup_mem_map()
        self.setup_clk()

        self.add_id()
        self.add_io()
        # self.add_nvm_mem(nvm_mem_init=nvm_mem_init)
        self.add_dilithium()
        if self.is_simulated:
            self.add_config("SIM")
        if debug_bridge:
            self.add_etherbone_bridge()

        # Simulation debugging ----------------------------------------------------------------------
        if trace:
            trace_reset_on = True
            self.platform_instance.add_debug(self, reset=1 if trace_reset_on else 0)
        elif self.is_simulated:
            self.comb += self.platform_instance.trace.eq(1)

        # SUME stuff ----------------------------------------------------------------------
        if not self.is_simulated and not self.integrated_main_ram_size:
            self.ddrphy = s7ddrphy.V7DDRPHY(
                platform.request("ddram"),
                memtype="DDR3",
                nphases=4,
                sys_clk_freq=sys_clk_freq,
            )
            self.add_sdram(
                "sdram",
                phy=self.ddrphy,
                module=MT8KTF51264(sys_clk_freq, "1:4"),
                size=0x40000000,
                l2_cache_size=8192,
            )

    def setup_clk(self: SoCCore):
        if self.is_simulated:
            self.crg = CRG(self.platform_instance.request("sys_clk"))
        else:
            self.crg = _CRG(self.platform, self.sys_clk_freq)

    def setup_mem_map(self: SoCCore):
        # Simple IO memory bump-allocator
        # TODO: revise this IO start address, because it probably
        #       assumes changing the default Rocket memory map
        self._io_base = 0x4100_0000  # start of your IO window
        self._io_limit = 0x4200_0000  # optional safety limit (64 KiB here)
        self._io_cur = self._io_base

    def add_io_buffer(
        self,
        name: str,
        size: int,
        *,
        custom: bool = True,
        mode: str = "rw",
        **ram_kwargs,
    ):
        def _next_pow2(x: int) -> int:
            return 1 << (x - 1).bit_length()

        # LiteX requires origin aligned to size rounded up to next power-of-two.
        size_pow2 = _next_pow2(size)
        required_al = max(8, size_pow2)  # keep at least 8-byte alignment

        origin = (self._io_cur + (required_al - 1)) & ~(required_al - 1)
        end = origin + size_pow2

        if self._io_limit is not None and end > self._io_limit:
            raise ValueError(
                f"IO space exhausted adding '{name}': need 0x{size_pow2:X} at 0x{origin:X}, "
                f"limit 0x{self._io_limit:X}"
            )

        # You can pass the original 'size' (LiteX will log that it rounded),
        # or pass size_pow2 to avoid the "rounded internally" info. Both are fine.
        self.add_ram(
            name, origin=origin, size=size, custom=custom, mode=mode, **ram_kwargs
        )

        self._io_cur = end
        return origin

    def add_id(self: SoCCore):
        if not self.is_simulated:
            self.submodules.dna = DNA()
            self.add_csr("dna")

    def add_io(self: SoCCore):
        if self.comm_protocol == CommProtocol.PCIE:
            pass
        elif self.comm_protocol == CommProtocol.UART:
            self.add_uart(uart_name="sim" if self.is_simulated else "serial")
            # Add io buffers for receiving commands
            self.add_io_buffer(
                name="tpm_cmd_buffer",
                size=4 * KBYTE,
                mode="rw",
                custom=True,
            )
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
        # TODO: check this IO region stuff later
        # NOTE: this puts the buffer inside of IO region
        # I guess thats not ideal... but otherwise, the CPU was unable
        # to access the given mem position, like 0x83000000.
        # We also had to add an extra param to the add_ram method to account for that.
        self.add_io_buffer(
            name="dilithium_buffer",
            size=10 * KBYTE,  # NOTE: 10 kB for sim, but final design could have 8 kB
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

    def add_nvm_mem(self, nvm_mem_init: str):
        # TODO: is it really big endianness?
        spi_flash_init = get_mem_data(nvm_mem_init, endianness="big")
        spiflash_module = S25FL128L(Codes.READ_1_1_4)
        self.spiflash_phy = LiteSPIPHYModel(spiflash_module, init=spi_flash_init)
        self.add_spi_flash(
            phy=self.spiflash_phy,
            mode="4x",
            module=spiflash_module,
            with_master=True,
        )


def main():
    args = arg_parser()

    # Platform definition
    platform = (
        PetaliteSimPlatform(io_path=args.io_json)
        if args.sim
        else digilent_netfpga_sume.Platform()
    )
    add_dilithium_src(platform=platform, top_level_dir_path=args.rtl_dir_path)

    # SoC definition
    soc = PetaliteCore(
        platform=platform,
        sys_clk_freq=args.sys_clk_freq,
        comm_protocol=args.comm,
        integrated_rom_path=args.firmware,
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
            # Basic args
            sim_config=sim_config,
            run=args.load,
            # Tracing
            trace=args.trace,
            trace_fst=args.trace,
            trace_start=args.trace_start if args.trace else 0,
            pre_run_callback=(
                (lambda vns: generate_gtkw_savefile(builder, vns, True))
                if args.trace
                else None
            ),
            # Verilator optimizations
            threads=8,  # runtime threads for Verilator
            jobs=8,  # compile parallelism
            opt_level="O3",
            interactive=True,
            coverage=False,
            video=False,
        )

    else:
        builder.build(**platform.get_argdict(platform.toolchain, {}))

        if args.load:
            prog = platform.create_programmer()
            prog.load_bitstream(builder.get_bitstream_filename(mode="sram"))


if __name__ == "__main__":
    main()
