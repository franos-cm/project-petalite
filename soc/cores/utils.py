import os
from litex.build.generic_platform import GenericPlatform


def add_rtl_sources(platform: GenericPlatform, top_level_dir_path: str):
    # Force correct compilation order for Keccak
    keccak_files = [
        "keccak_pkg.sv",
        "components/latch.sv",
        "components/regn.sv",
        "components/countern.sv",
        "components/piso_buffer.sv",
        "components/sipo_buffer.sv",
        "components/sipo_buffer.sv",
        "components/size_counter.sv",
        "components/round_constant_gen.sv",
        "components/round.sv",
        "components/padding_gen.sv",
        "stages/load_fsm.sv",
        "stages/load_datapath.sv",
        "stages/load_stage.sv",
        "stages/permute_fsm.sv",
        "stages/permute_datapath.sv",
        "stages/permute_stage.sv",
        "stages/dump_fsm.sv",
        "stages/dump_datapath.sv",
        "stages/dump_stage.sv",
        "keccak.sv",
    ]

    dilithium_components_path = os.path.join(top_level_dir_path, "components/")
    keccak_components_path = os.path.join(dilithium_components_path, "shake-sv/")

    platform.add_sources(keccak_components_path, *keccak_files)
    platform.add_source_dir(dilithium_components_path, recursive=False)
    platform.add_source_dir(top_level_dir_path, recursive=False)
