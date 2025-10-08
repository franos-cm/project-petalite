#!/usr/bin/env python3
from litex.soc.integration.builder import Builder
from litex_boards.platforms import digilent_netfpga_sume

from platforms import PetaliteSimPlatform, add_rtl_sources
from utils import CommProtocol, arg_parser, generate_gtkw_savefile
from petalite import PetaliteCore


def main():
    args = arg_parser()

    # Platform definition
    platform = (
        PetaliteSimPlatform(io_path=args.io_json)
        if args.sim
        else digilent_netfpga_sume.Platform()
    )
    add_rtl_sources(platform=platform, top_level_dir_path=args.rtl_dir_path)

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
        from litex.build.sim.config import SimConfig

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
            trace_start=args.trace_start if args.trace else -1,
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
