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

from liteeth.phy.model import LiteEthPHYModel
from liteeth.common import convert_ip

from litespi.phy.model import LiteSPIPHYModel
from litespi.modules import S25FL128L
from litespi.opcodes import SpiNorFlashOpCodes as Codes

from dilithium import Dilithium
from platforms import PetaliteSimPlatform
from helpers import arg_parser, generate_gtkw_savefile, CommProtocol


class PetaliteCore(SoCCore):
    is_simulated: bool

    def __init__(
        self,
        platform: GenericPlatform,
        sys_clk_freq: int,
        comm_protocol: CommProtocol,
        integrated_rom_init: str = None,
        nvm_mem_init: str = None,
        debug_bridge: bool = False,
        trace: bool = False,
    ):
        self.platform_instance = platform
        self.is_simulated = isinstance(platform, SimPlatform)
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
        else:
            self.comb += self.platform_instance.trace.eq(1)

    def setup_clk(self: SoCCore):
        if self.is_simulated:
            self.crg = CRG(self.platform_instance.request("sys_clk"))

    def setup_mem_map(self: SoCCore):
        # Simple IO memory bump-allocator
        self._io_base = 0x3000_0000  # start of your IO window
        self._io_limit = 0x3001_0000  # optional safety limit (64 KiB here)
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
                size=4 * 1024,
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
            size=10 * 1024,  # NOTE: 10 kB for sim, but final design could have 8 kB
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
            trace_start=18_800_000_000 if args.trace else 0,  # (in ns)
        )

    else:
        builder.build(**platform.get_argdict(platform.toolchain, {}))

        if args.load:
            prog = platform.create_programmer()
            prog.load_bitstream(builder.get_bitstream_filename(mode="sram"), device=1)


if __name__ == "__main__":
    main()
