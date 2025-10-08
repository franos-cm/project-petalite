import json
from litex.build.generic_platform import IOStandard, Pins, Subsignal


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
