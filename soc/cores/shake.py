from migen import Module, Instance, ClockSignal, ResetSignal
from litex.soc.interconnect import stream
from litex.soc.interconnect.csr import CSRStorage, AutoCSR


class Shake(Module, AutoCSR):
    def __init__(self):
        # AXI-Stream endpoints -------------------------------------------------
        layout = [("data", 64)]
        self.sink = stream.Endpoint(layout)  # input to RTL
        self.source = stream.Endpoint(layout)  # output from RTL

        # Control signals ------------------------------------------------------
        self.reset = CSRStorage(1)

        # RTL instance ---------------------------------------------------------
        self.specials += Instance(
            "shake",
            # Control
            i_clk=ClockSignal(),
            i_rst=(ResetSignal() | self.reset.storage),
            # Stream input
            i_valid_in=self.sink.valid,
            o_ready_in=self.sink.ready,
            i_data_in=self.sink.data,
            # Stream output
            o_valid_out=self.source.valid,
            i_ready_out=self.source.ready,
            o_data_out=self.source.data,
        )
