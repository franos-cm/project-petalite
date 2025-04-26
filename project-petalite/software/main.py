#!/usr/bin/env python3

import os
import sys
import argparse
from litex.build.tools import replace_in_file


def main():
    parser = argparse.ArgumentParser(description="LiteX Bare Metal App Builder.")
    parser.add_argument(
        "--build-path",
        required=True,
        help="Target's build path (e.g., build/board_name).",
    )
    parser.add_argument(
        "--output-dir",
        default="firmware",
        help="Output directory for build files (default: firmware/).",
    )
    parser.add_argument(
        "--firmware-name",
        default="firmware",
        help="Name of the firmware binary (without extension, e.g., petalite_firmware).",
    )
    parser.add_argument("--with-cxx", action="store_true", help="Enable CXX support.")
    parser.add_argument(
        "--mem",
        default="main_ram",
        help="Memory Region where code will be loaded/executed.",
    )
    args = parser.parse_args()

    firmware_bin = args.firmware_name + ".bin"
    firmware_fbi = args.firmware_name + ".fbi"

    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)

    # Copy contents to output directory
    os.system(f"cp {os.path.abspath(os.path.dirname(__file__))}/* {args.output_dir}")
    os.system(
        f"chmod -R u+w {args.output_dir}"
    )  # Nix specific: Allow linker script to be modified.

    # Update memory region in linker script
    replace_in_file(os.path.join(args.output_dir, "linker.ld"), "main_ram", args.mem)

    # Compile the project
    build_path = (
        args.build_path
        if os.path.isabs(args.build_path)
        else os.path.join("..", args.build_path)
    )

    os.system(
        f"export BUILD_DIR={build_path} FIRMWARE_NAME={args.firmware_name} && {'export WITH_CXX=1 &&' if args.with_cxx else ''} cd {args.output_dir} && make"
    )

    # Rename and copy the binary output
    compiled_bin = os.path.join(args.output_dir, args.firmware_name + ".bin")
    if os.path.exists(compiled_bin):
        os.rename(compiled_bin, os.path.join(args.output_dir, firmware_bin))
    else:
        print(f"Error: Expected compiled binary {compiled_bin} not found.")
        sys.exit(1)

    # Prepare flash boot image
    python3 = (
        sys.executable or "python3"
    )  # Nix specific: reuse current Python executable if available.
    os.system(
        f"{python3} -m litex.soc.software.crcfbigen {os.path.join(args.output_dir, firmware_bin)} -o {os.path.join(args.output_dir, firmware_fbi)} --fbi --little"
    )  # FIXME: Endianness.

    # Clean up unnecessary files (keep only .bin, .fbi, and linker.ld)
    for filename in os.listdir(args.output_dir):
        if not (
            filename == firmware_bin
            or filename == firmware_fbi
            or filename == "linker.ld"
        ):
            filepath = os.path.join(args.output_dir, filename)
            if os.path.isfile(filepath):
                os.remove(filepath)


if __name__ == "__main__":
    main()
