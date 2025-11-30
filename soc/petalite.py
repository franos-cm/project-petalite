from migen import Signal, ClockDomainsRenamer
from migen.genlib.cdc import PulseSynchronizer, MultiReg
from litex.soc.cores.dma import WishboneDMAReader, WishboneDMAWriter
from litex.soc.integration.soc_core import SoCCore
from litex.soc.integration.common import get_mem_data
from litex.soc.interconnect import wishbone
from litex.build.generic_platform import GenericPlatform
from litex.build.sim import SimPlatform

from cores import Dilithium, PowerBridge, PowerController
from utils import CommProtocol, KBYTE


class PetaliteCore(SoCCore):
    is_simulated: bool
    platform: GenericPlatform
    comm_protocol: CommProtocol
    bus_data_width: int
    sys_clk_freq: int
    dilithium_zetas_path: str

    def __init__(
        self,
        platform: GenericPlatform,
        sys_clk_freq: int,
        comm_protocol: CommProtocol,
        dilithium_zetas_path: str,
        integrated_rom_path: str = None,
        nvm_mem_init: str = None,
        debug_bridge: bool = False,
        trace: bool = False,
    ):
        # Define some base attributes that are useful
        self.bus_data_width = 64
        self.is_simulated = isinstance(platform, SimPlatform)
        self.sys_clk_freq = sys_clk_freq
        self.comm_protocol = comm_protocol
        self.dilithium_zetas_path = dilithium_zetas_path
        self.setup_buffer_allocator()

        # NOTE: In theory, we could pass the integrated_rom_init param to the SoC intiializer
        #       In practice, there is a bug by which if you do that, the size of the ROM is incorrectly calculated
        #       So for now we pass the integrated_rom_init as a list of the instructions, which makes it work.
        #       For that, we need do know the data_width and endianness of the CPU a priori, which is fine,
        #       as long as we remember to change it if we switch CPUs
        integrated_rom_data = (
            get_mem_data(
                integrated_rom_path, data_width=self.bus_data_width, endianness="little"
            )
            if integrated_rom_path
            else []
        )

        # Base SoC declaration ---------------------------------------------------------
        SoCCore.__init__(
            self,
            # System specs
            platform,
            ident="Petalite Core",
            ident_version=True,
            # CPU specs
            cpu_type="rocket",
            cpu_variant="small",
            bus_data_width=self.bus_data_width,
            clk_freq=sys_clk_freq,
            # Communication
            with_uart=False,
            # Memory specs, considering full TPM firmware
            integrated_rom_size=256 * KBYTE,
            integrated_sram_size=224 * KBYTE, # Increase SRAM size if we need more heap/stack mem
            integrated_rom_init=integrated_rom_data,
        )

        # Add cores to SoC ----------------------------------------------------------------
        self.add_crg()
        self.add_id()
        self.add_io()
        self.add_trng()
        self.add_dilithium()
        if debug_bridge:
            self.add_etherbone_bridge()

        # Simulation debugging ------------------------------------------------------------
        # TODO: revise why we need to do this, and what it means
        if trace:
            self.platform.add_debug(self, reset=1)
        elif self.is_simulated:
            self.comb += self.platform.trace.eq(1)

        # SUME stuff ----------------------------------------------------------------------
        # TODO: check if these are the right conditions to check
        if not self.is_simulated and not self.integrated_main_ram_size:
            from litedram.modules import MT8KTF51264
            from litedram.phy import s7ddrphy

            self.ddrphy = s7ddrphy.V7DDRPHY(
                self.platform.request("ddram"),
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

    def setup_buffer_allocator(self):
        # Simple IO memory bump-allocator
        # TODO: revise this IO start address, because it probably
        #       assumes changing the default Rocket memory map
        self._io_base = 0x4100_0000  # start of your IO window
        self._io_limit = 0x4200_0000  # optional safety limit (64 KiB here)
        self._io_cur = self._io_base

    def add_buffer(
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

        self.add_ram(
            name, origin=origin, size=size, custom=custom, mode=mode, **ram_kwargs
        )

        self._io_cur = end
        return origin

    def add_crg(self):
        # Add a CRG with two clock domains, a sys one and another that is always on
        # The two domains then need some extra structure to communicate properly
        if self.is_simulated:
            from cores import PetaliteSimCRG

            self.crg = PetaliteSimCRG(self.platform.request("sys_clk"))
        else:
            from cores import PetaliteCRG

            self.crg = PetaliteCRG(self.platform, self.sys_clk_freq)

        # 1. Make it possible that the CPU can put itself to sleep
        self.submodules.power_controller = PowerController()
        self.add_csr("power_controller")
        # Cross a pulse between clock domains
        sleep_ps = PulseSynchronizer("sys", "sys_always_on")
        self.submodules += sleep_ps
        self.comb += sleep_ps.i.eq(self.power_controller.req.re)

        # # 2. Have a signal that the host can assert to request sleep
        host_req_sleep = Signal()
        # # Temporarily disable it
        self.comb += host_req_sleep.eq(0)
        # Or alternatively, lets have a board pin that does that
        # tpm_pdn_pad = self.platform.request("tpm_pdn")
        # tpm_pdn = Signal()
        # self.specials += MultiReg(tpm_pdn_pad, tpm_pdn, "sys_always_on")
        # self.comb += host_req_sleep.eq(tpm_pdn)

        # 3. Have a small FSM that keeps track of the current state on the always-on domain
        self.submodules.power_bridge = ClockDomainsRenamer({"sys": "sys_always_on"})(
            PowerBridge()
        )
        self.comb += [
            self.power_bridge.set_sleep_pulse.eq(sleep_ps.o),
            self.power_bridge.host_req_sleep.eq(host_req_sleep),
        ]

        # 4. Gate the sys domain using the FSM
        self.comb += self.crg.power_down.eq(self.power_bridge.power_down)

    def add_id(self):
        if not self.is_simulated:
            from litex.soc.cores.dna import DNA

            self.submodules.dna = DNA()
            self.add_csr("dna")

    def add_io(self):
        if self.comm_protocol == CommProtocol.UART:
            if self.is_simulated:
                # If we are simulating, we can have a UART for interacting with the terminal
                # NOTE: this one needs to be named uart so we can use Litex stdio
                self.add_uart(
                    name="uart",
                    uart_name="sim",
                    uart_pads=self.platform.request("serial_term"),
                )

            # We also have the one uart for TPM commands
            self.add_uart(
                name="cmd_uart",
                uart_name="sim" if self.is_simulated else "serial",
                uart_pads=self.platform.request("serial"),
            )
            # Add io buffers for TPM commands
            # NOTE: considering Dilithium signatures can be ~5kB big,
            #       this IO buffer should be bigger than that.
            self.add_buffer(
                name="tpm_cmd_buffer",
                size=8 * KBYTE,
                mode="rw",
                custom=True,
            )

        else:
            raise RuntimeError()

    def add_trng(self):
        if self.is_simulated:
            from cores import SimTRNG

            trng = SimTRNG()
        else:
            from cores import RingOscillatorTRNG

            trng = RingOscillatorTRNG(platform=self.platform)

        self.submodules.trng = ClockDomainsRenamer({"sys": "sys_always_on"})(trng)
        self.add_csr("trng")

    def add_dilithium(self):
        # Add bus masters
        wb_dilithium_reader = wishbone.Interface(data_width=64)
        wb_dilithium_writer = wishbone.Interface(data_width=64)
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

        self.submodules.dilithium = Dilithium(zetas_path=self.dilithium_zetas_path)
        self.add_csr("dilithium")
        self.comb += [
            self.dilithium_reader.source.connect(self.dilithium.sink),
            self.dilithium.source.connect(self.dilithium_writer.sink),
        ]

        # Add scratch memory region for the core's input and output
        # TODO: check this IO region stuff later
        # NOTE: this puts the buffer inside of IO region
        #       I guess thats not ideal... but otherwise, the CPU wasnt
        #       able to access the given mem position, like 0x83000000.
        #       We also had to add an extra param to the add_ram method to account for that.
        # NOTE: the size of this buffer is defined by the max length of input and output data
        #       that can exist simultaneously in the buffer during an op. At the moment, that is during
        #       the sign op, in which we need to load part of the sk into the buffer to guarantee 8B alignment.
        #       If we fix the DMA engine so it doesnt need 8B alignment, we can probably make it smaller.
        self.add_buffer(
            name="dilithium_buffer",
            size=10 * KBYTE,
            mode="rw",
            custom=True,
        )
