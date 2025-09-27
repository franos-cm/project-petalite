#!/usr/bin/env python3
import argparse
import os
import sys
import shutil
import subprocess
from pathlib import Path
from contextlib import contextmanager
from litex.build.tools import replace_in_file


# ---------- helpers ----------
def run(cmd, cwd=None, env=None):
    print("+ " + " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=cwd, env=env, check=True)


@contextmanager
def maybe_patch_linker(ld_path: Path, mem_name: str):
    """
    Temporarily rewrite 'main_ram' -> mem_name in linker.ld for the build,
    then restore the original file afterwards. NOP if mem_name == 'main_ram'.
    """
    if not ld_path.exists() or mem_name == "main_ram":
        yield
        return
    original = ld_path.read_text()
    replace_in_file(str(ld_path), "main_ram", mem_name)
    try:
        yield
    finally:
        ld_path.write_text(original)


def make_env(build_dir: Path, firmware_name: str):
    env = os.environ.copy()
    env["BUILD_DIR"] = str(build_dir)
    env["FIRMWARE_NAME"] = firmware_name
    return env


def copy_artifacts(fw_dir: Path, out_dir: Path, firmware_name: str, make_fbi: bool):
    out_dir.mkdir(parents=True, exist_ok=True)
    binf = fw_dir / f"{firmware_name}.bin"
    if not binf.exists():
        print(f"error: expected {binf} not found", file=sys.stderr)
        sys.exit(1)
    shutil.copy2(binf, out_dir / binf.name)
    if make_fbi:
        py = sys.executable or "python3"
        fbi = out_dir / f"{firmware_name}.fbi"
        run(
            [
                py,
                "-m",
                "litex.soc.software.crcfbigen",
                str(out_dir / binf.name),
                "-o",
                str(fbi),
                "--fbi",
                "--little",
            ]
        )


# ---------- CLI ----------


def add_common(sp):
    default_fwdir = Path(__file__).parent
    sp.add_argument("--fw-dir", default=default_fwdir)
    sp.add_argument("--build-path", default="builds/soc")
    sp.add_argument("--firmware-name", default="firmware")
    sp.add_argument("--output-dir", default="builds")


def main():
    p = argparse.ArgumentParser(description="Firmware helper (Makefile wrapper).")
    sub = p.add_subparsers(dest="cmd", required=True)

    # existing
    sp_build = sub.add_parser("build", help="Build firmware (.bin); copy artifacts")
    add_common(sp_build)
    sp_build.add_argument("--mem", default="rom")
    sp_build.add_argument("--fbi", action="store_true")
    sp_build.add_argument("--firmware-build-dir", default="builds/firmware")

    sp_wolf = sub.add_parser("wolfssl-build", help="Build/install wolfSSL only")
    add_common(sp_wolf)

    sp_cw = sub.add_parser("wolfssl-clean", help="Clean wolfSSL build/install")
    add_common(sp_cw)

    sp_clean = sub.add_parser("clean", help="Run 'make clean'")
    add_common(sp_clean)

    sp_show = sub.add_parser("show", help="Run 'make show'")
    add_common(sp_show)

    sp_show_inc = sub.add_parser("show-includes", help="Run 'make show-includes'")
    add_common(sp_show_inc)

    sp_cc_inc = sub.add_parser("cc-include-search", help="Run 'make cc-include-search'")
    add_common(sp_cc_inc)

    sp_tpm = sub.add_parser("tpm-build", help="Build TPM+platform+compat static lib")
    add_common(sp_tpm)

    sp_tpm_clean = sub.add_parser("tpm-clean", help="Clean TPM static lib build")
    add_common(sp_tpm_clean)

    sp_tpm_flags = sub.add_parser("show-tpm-flags", help="Clean TPM static lib build")
    add_common(sp_tpm_flags)

    sp_list = sub.add_parser("list-tpm-sources", help="List TPM/ sources")
    add_common(sp_list)

    libs_flags = sub.add_parser("show-soc-libs", help="Clean TPM static lib build")
    add_common(libs_flags)

    sp_show_cflags = sub.add_parser("show-flags", help="Run 'make show-cflags'")
    add_common(sp_show_cflags)
    sp_show_wolfssl_cflags = sub.add_parser(
        "show-wolfssl-flags", help="Run 'make show-cflags'"
    )
    add_common(sp_show_wolfssl_cflags)

    sp_bin_clean = sub.add_parser(
        "firmware-clean", help="Remove copied firmware .bin/.fbi artifacts only"
    )
    add_common(sp_bin_clean)

    args = p.parse_args()

    fw_dir = Path(args.fw_dir).resolve()
    if os.path.isabs(args.build_path):
        build_dir = Path(args.build_path).resolve()
    else:
        build_dir = (fw_dir.parent / args.build_path).resolve()

    env = make_env(build_dir, args.firmware_name)

    if args.cmd == "wolfssl-build":
        run(["make", "wolfssl-build"], cwd=fw_dir, env=env)
        return
    elif args.cmd == "wolfssl-clean":
        run(["make", "wolfssl-clean"], cwd=fw_dir, env=env)
        return
    elif args.cmd == "clean":
        run(["make", "clean"], cwd=fw_dir, env=env)
        for ext in (".bin", ".fbi"):
            art = Path(args.output_dir) / f"{args.firmware_name}{ext}"
            if art.exists():
                try:
                    art.unlink()
                    print(f"+ removed {art}")
                except OSError as e:
                    print(f"warn: could not remove {art}: {e}", file=sys.stderr)
        return
    elif args.cmd == "show":
        run(["make", "show"], cwd=fw_dir, env=env)
        return
    elif args.cmd == "show-includes":
        run(["make", "show-includes"], cwd=fw_dir, env=env)
        return
    elif args.cmd == "cc-include-search":
        run(["make", "cc-include-search"], cwd=fw_dir, env=env)
        return
    elif args.cmd == "show-flags":
        run(["make", "show-flags"], cwd=fw_dir, env=env)
        return
    elif args.cmd == "show-wolfssl-flags":
        run(["make", "show-wolfssl-flags"], cwd=fw_dir, env=env)
        return
    elif args.cmd == "tpm-build":
        run(["make", "tpm-build"], cwd=fw_dir, env=env)
        return
    elif args.cmd == "tpm-clean":
        run(["make", "tpm-clean"], cwd=fw_dir, env=env)
        return
    elif args.cmd == "show-tpm-flags":
        run(["make", "show-tpm-flags"], cwd=fw_dir, env=env)
        return
    elif args.cmd == "list-tpm-sources":
        run(["make", "list-tpm-sources"], cwd=fw_dir, env=env)
        return
    elif args.cmd == "show-soc-libs":
        run(["make", "show-soc-libs"], cwd=fw_dir, env=env)
        return
    elif args.cmd == "firmware-clean":
        run(["make", "firmware-clean"], cwd=fw_dir, env=env)

        removed_any = False
        for ext in (".bin", ".fbi"):
            art = Path(args.output_dir) / f"{args.firmware_name}{ext}"
            if art.exists():
                try:
                    art.unlink()
                    print(f"+ removed {art}")
                    removed_any = True
                except OSError as e:
                    print(f"warn: could not remove {art}: {e}", file=sys.stderr)
        if not removed_any:
            print("(no firmware artifacts to remove)")
        return

    elif args.cmd == "build":
        ld = fw_dir / "linker.ld"
        with maybe_patch_linker(ld, args.mem):
            run(["make"], cwd=fw_dir, env=env)
        copy_artifacts(
            Path(args.firmware_build_dir).resolve(),
            Path(args.output_dir).resolve(),
            args.firmware_name,
            make_fbi=args.fbi,
        )
        return


if __name__ == "__main__":
    main()
