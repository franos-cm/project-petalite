from litex.build.generic_platform import IOStandard, Pins, Subsignal
from litex.build.sim import SimPlatform
import json
import os


def load_io_from_json(json_path):
    def int_or_str(s):
        try:
            return int(s)
        except ValueError:
            return s

    with open(json_path, "r") as f:
        raw_io_data = json.load(f)

    parsed_io_array = []
    for raw_entry in raw_io_data:
        parsed_entry = [raw_entry["name"], raw_entry["index"]]

        if "subsignals" in raw_entry:
            subsignals = [
                Subsignal(name, Pins(int_or_str(signal["pins"])))
                for name, signal in raw_entry["subsignals"].items()
            ]
            parsed_entry.extend(subsignals)

        else:
            parsed_entry.append(Pins(int_or_str(raw_entry["pins"])))

        if raw_entry.get("iostandard"):
            parsed_entry.append(IOStandard(raw_entry["iostandard"]))

        parsed_io_array.append(tuple(parsed_entry))

    return parsed_io_array


class PetaliteSimPlatform(SimPlatform):
    def __init__(self, io_path):
        io = load_io_from_json(json_path=io_path)
        SimPlatform.__init__(self, "SIM", io)

    def add_dilithium_src(self, top_level_dir_path):
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

        dilithium_components_path = os.path.join(top_level_dir_path, "rtl_src/")
        keccak_components_path = os.path.join(dilithium_components_path, "shake-sv/")

        self.add_sources(keccak_components_path, *keccak_files)
        self.add_source_dir(dilithium_components_path, recursive=False)
        self.add_source_dir(top_level_dir_path, recursive=False)
