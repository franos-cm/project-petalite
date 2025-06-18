from migen import Module, Signal, Instance, ClockSignal, ResetSignal
from litex.soc.interconnect import stream


class Dilithium(Module):
    def __init__(self):
        # AXI-Stream endpoints -------------------------------------------------
        layout = [("data", 64)]
        self.sink = stream.Endpoint(layout)  # input to RTL
        self.source = stream.Endpoint(layout)  # output from RTL

        # Control/CSR wires ----------------------------------------------------
        self.start = Signal()
        self.mode = Signal(2)
        self.sec_lvl = Signal(3)

        # RTL instance ---------------------------------------------------------
        self.specials += Instance(
            "dilithium",
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
