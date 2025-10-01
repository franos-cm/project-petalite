import os
from migen import Module, Instance, ClockSignal, ResetSignal
from litex.soc.interconnect import stream
from litex.soc.interconnect.csr import CSRStorage, AutoCSR
from litex.build.generic_platform import GenericPlatform


class Dilithium(Module, AutoCSR):
    def __init__(self):
        # AXI-Stream endpoints -------------------------------------------------
        layout = [("data", 64)]
        self.sink = stream.Endpoint(layout)  # input to RTL
        self.source = stream.Endpoint(layout)  # output from RTL

        # Control/CSR wires ----------------------------------------------------
        self.start = CSRStorage(1)
        self.mode = CSRStorage(2)
        self.security_level = CSRStorage(3)
        self.reset = CSRStorage(1)

        # RTL instance ---------------------------------------------------------
        self.specials += Instance(
            "dilithium",
            # Control
            i_clk=ClockSignal(),
            i_rst=(ResetSignal() | self.reset.storage),
            i_start=self.start.storage,
            i_mode=self.mode.storage,
            i_sec_lvl=self.security_level.storage,
            # Stream input
            i_valid_i=self.sink.valid,
            o_ready_i=self.sink.ready,
            i_data_i=self.sink.data,
            # Stream output
            o_valid_o=self.source.valid,
            i_ready_o=self.source.ready,
            o_data_o=self.source.data,
        )


def add_dilithium_src(platform: GenericPlatform, top_level_dir_path: str):
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
