from migen import Module, Signal, Instance, ClockSignal, ResetSignal
from litex.soc.interconnect import stream


class Dilithium(Module):
    def __init__(self):
        self.sink = stream.Endpoint([("data", 64)])
        self.source = stream.Endpoint([("data", 64)])

        self.start = Signal()
        self.mode = Signal(2)
        self.sec_lvl = Signal(3)

        self.specials += Instance(
            "combined_top",
            # Params
            p_BUS_W=4,
            p_SAMPLE_W=23,
            p_W=64,
            # Control
            i_clk=ClockSignal(),
            i_rst=ResetSignal(),
            i_start=self.start,
            i_mode=self.mode,
            i_sec_lvl=self.sec_lvl,
            # Stream input
            i_valid_i=self.sink.valid,
            o_ready_i=self.sink.ready,
            i_data_i=self.sink.data,
            # Stream output
            o_valid_o=self.source.valid,
            i_ready_o=self.source.ready,
            o_data_o=self.source.data,
        )
