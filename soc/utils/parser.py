import argparse
from .common import CommProtocol


def str_to_int(s):
    try:
        f = float(s)
    except ValueError:
        raise argparse.ArgumentTypeError(f"Value '{s}' is not a number.")

    if not f.is_integer():
        raise argparse.ArgumentTypeError(f"Value '{s}' is not an integer value.")

    return int(f)


def arg_parser():
    parser = argparse.ArgumentParser(description="Project Petalite SoC")
    parser.add_argument(
        "--sys-clk-freq",
        type=str_to_int,
        default=200e6,
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
        default="./dilithium-rtl",
        help="Directory path for custom cores",
    )
    parser.add_argument(
        "--build-dir",
        type=str,
        help="Path to the build dir.",
    )

    parser.add_argument(
        "--comm",
        type=lambda s: CommProtocol(s.upper()),
        choices=list(CommProtocol),
        default=CommProtocol.UART,
        help="Communication protocol (UART or PCIE).",
    )

    parser.add_argument(
        "--trace",
        action="store_true",
        default=False,
        help="Generate waveforms or not.",
    )
    parser.add_argument(
        "--trace-start",
        type=str_to_int,
        default=0,
        help="Time (in ns) to begin tracing",
    )

    parser.add_argument(
        "--debug-bridge",
        action="store_true",
        default=False,
        help="Add etherbone bridge.",
    )

    args = parser.parse_args()
    if args.sim and not args.io_json:
        parser.error("Simulated platform requires a pin map json.")
    if args.load and not args.firmware:
        parser.error("Loading requires firmware binary.")

    return args
