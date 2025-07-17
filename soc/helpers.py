import os
import argparse
from enum import StrEnum
from typing import Tuple

from litex.soc.interconnect import wishbone


class CoreType(StrEnum):
    EMBEDDED = "EMBEDDED"
    PCIE_DEVICE = "PCIE_DEVICE"
    HOST = "HOST"


HostBusInterfaces = Tuple[wishbone.Interface, wishbone.Interface]


def str_to_int(s):
    try:
        f = float(s)
    except ValueError:
        raise argparse.ArgumentTypeError(f"Value '{s}' is not a number.")

    if not f.is_integer():
        raise argparse.ArgumentTypeError(f"Value '{s}' is not an integer value.")

    return int(f)


def host_arg_parser_debug():
    parser = argparse.ArgumentParser(description="Project Petalite SoC")

    parser.add_argument(
        "--sys-clk-freq",
        type=str_to_int,
        default=1e8,
        help="System clock frequency",
    )

    parser.add_argument(
        "--load",
        action="store_true",
        default=False,
        help="Either load the bitstream or run the simulation.",
    )

    parser.add_argument(
        "--compile-gateware",
        action="store_true",
        default=False,
        help="Only build the gateware.",
    )

    parser.add_argument(
        "--sim",
        action="store_true",
        default=False,
        help="Build for simulation or real board",
    )

    parser.add_argument(
        "--io-json",
        type=str,
        help="Path to the io json config. Required for a simulated platform.",
    )

    parser.add_argument(
        "--host-firmware",
        type=str,
        help="Path to the firmware binary file. Required if --load is set.",
    )

    parser.add_argument(
        "--rtl-dir-path",
        type=str,
        default="./dilithium-hw",
        help="Directory path for custom cores",
    )
    parser.add_argument(
        "--build-dir",
        type=str,
        default="./build-soc",
        help="Path to the build dir.",
    )
    parser.add_argument(
        "--debug-bridge",
        action="store_true",
        default=False,
        help="Debug bridge.",
    )

    parser.add_argument(
        "--trace",
        action="store_true",
        default=False,
        help="Generate waveforms or not.",
    )

    args = parser.parse_args()
    if args.sim and not args.io_json:
        parser.error("Simulated platform requires a pin map json.")
    if args.load and (not (args.host_firmware)):
        parser.error("Loading requires firmware binary")

    return args


def host_arg_parser():
    parser = argparse.ArgumentParser(description="Project Petalite SoC")

    parser.add_argument(
        "--sys-clk-freq",
        type=str_to_int,
        default=1e8,
        help="System clock frequency",
    )

    parser.add_argument(
        "--load",
        action="store_true",
        default=False,
        help="Either load the bitstream or run the simulation.",
    )

    parser.add_argument(
        "--compile-petalite-software",
        action="store_true",
        default=False,
        help="Compile petalite software.",
    )

    parser.add_argument(
        "--compile-gateware",
        action="store_true",
        default=False,
        help="Only build the gateware.",
    )

    parser.add_argument(
        "--sim",
        action="store_true",
        default=False,
        help="Build for simulation or real board",
    )

    parser.add_argument(
        "--io-json",
        type=str,
        help="Path to the io json config. Required for a simulated platform.",
    )

    parser.add_argument(
        "--host-firmware",
        type=str,
        help="Path to the firmware binary file. Required if --load is set.",
    )

    parser.add_argument(
        "--petalite-firmware",
        type=str,
        help="Path to the firmware binary file. Required if --load is set.",
    )

    parser.add_argument(
        "--rtl-dir-path",
        type=str,
        default="./dilithium-hw",
        help="Directory path for custom cores",
    )
    parser.add_argument(
        "--build-dir",
        type=str,
        default="./build-soc",
        help="Path to the build dir.",
    )
    parser.add_argument(
        "--trace",
        action="store_true",
        default=False,
        help="Generate waveforms or not.",
    )
    parser.add_argument(
        "--debug-bridge",
        action="store_true",
        default=False,
        help="Debug bridge.",
    )

    args = parser.parse_args()
    if args.sim and not args.io_json:
        parser.error("Simulated platform requires a pin map json.")
    if args.compile_petalite_software and not args.io_json:
        parser.error("Simulated platform requires a pin map json.")
    if args.load and (not (args.host_firmware and args.petalite_firmware)):
        parser.error("Loading requires firmware binary")
    if args.load and args.compile_petalite_software:
        parser.error("Cannot load and compile petalite software on same step.")

    return args


def petalite_arg_parser():
    parser = argparse.ArgumentParser(description="Project Petalite SoC")

    parser.add_argument(
        "--type",
        type=CoreType,
        default=CoreType.HOST,
        help="Communication protocol",
    )
    parser.add_argument(
        "--sys-clk-freq",
        type=str_to_int,
        default=1e8,
        help="System clock frequency",
    )

    parser.add_argument(
        "--load",
        action="store_true",
        default=False,
        help="Either load the bitstream or run the simulation.",
    )
    parser.add_argument(
        "--compile-gateware",
        action="store_true",
        default=False,
        help="Only build the gateware.",
    )
    parser.add_argument(
        "--sim",
        action="store_true",
        default=False,
        help="Build for simulation or real board",
    )
    parser.add_argument(
        "--io-json",
        type=str,
        help="Path to the io json config. Required for a simulated platform.",
    )
    parser.add_argument(
        "--firmware",
        type=str,
        help="Path to the firmware binary file. Required if --load is set.",
    )

    parser.add_argument(
        "--rtl-dir-path",
        type=str,
        default="./dilithium-hw",
        help="Directory path for custom cores",
    )
    parser.add_argument(
        "--build-dir",
        type=str,
        default="./build-soc",
        help="Path to the build dir.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        default=False,
        help="Generate waveforms or not.",
    )

    args = parser.parse_args()
    print(args.sim)
    if args.sim and not args.io_json:
        parser.error("Simulated platform requires a pin map json.")
    if args.load and not args.firmware:
        parser.error("Loading requires firmware binary.")

    return args


def generate_gtkw_savefile(builder, vns, trace_fst):
    from litex.build.sim import gtkwave as gtkw

    dumpfile = os.path.join(
        builder.gateware_dir, "sim.{}".format("fst" if trace_fst else "vcd")
    )
    savefile = os.path.join(builder.gateware_dir, "sim.gtkw")
    soc = builder.soc

    with gtkw.GTKWSave(vns, savefile=savefile, dumpfile=dumpfile) as save:
        save.clocks()
        save.fsm_states(soc)
        if "main_ram" in soc.bus.slaves.keys():
            save.add(
                soc.bus.slaves["main_ram"],
                mappers=[gtkw.wishbone_sorter(), gtkw.wishbone_colorer()],
            )

        if hasattr(soc, "sdrphy"):
            # all dfi signals
            save.add(
                soc.sdrphy.dfi, mappers=[gtkw.dfi_sorter(), gtkw.dfi_in_phase_colorer()]
            )

            # each phase in separate group
            with save.gtkw.group("dfi phaseX", closed=True):
                for i, phase in enumerate(soc.sdrphy.dfi.phases):
                    save.add(
                        phase,
                        group_name="dfi p{}".format(i),
                        mappers=[
                            gtkw.dfi_sorter(phases=False),
                            gtkw.dfi_in_phase_colorer(),
                        ],
                    )

            # only dfi command/data signals
            def dfi_group(name, suffixes):
                save.add(
                    soc.sdrphy.dfi,
                    group_name=name,
                    mappers=[
                        gtkw.regex_filter(gtkw.suffixes2re(suffixes)),
                        gtkw.dfi_sorter(),
                        gtkw.dfi_per_phase_colorer(),
                    ],
                )

            dfi_group("dfi commands", ["cas_n", "ras_n", "we_n"])
            dfi_group("dfi commands", ["wrdata"])
            dfi_group("dfi commands", ["wrdata_mask"])
            dfi_group("dfi commands", ["rddata"])
