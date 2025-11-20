from migen import Module, Instance, ClockSignal, ResetSignal
from litex.soc.interconnect import stream
from litex.soc.interconnect.csr import CSRStorage, AutoCSR


class Dilithium(Module, AutoCSR):
    def __init__(self, zetas_path: str):
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
            # Parametrs
            p_ZETAS_PATH=zetas_path,
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
