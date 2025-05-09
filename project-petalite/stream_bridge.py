import os
from migen import *
from migen.sim import run_simulation
from litex.soc.interconnect import stream
from litex.soc.interconnect.csr import *


class CSRToStreamBridge(Module, AutoCSR):
    def __init__(self, data_width=64):
        ### --- INPUT STREAM (CPU → stream) ---
        self.stream = stream.Endpoint([("data", data_width)])
        self.data_csr_in = CSRStorage(data_width)
        self.ready_csr_out = CSRStatus()
        self.valid_csr_in = CSRStorage()

        # Aditional signals to account for CPU timing
        self.completed_status = CSRStatus()
        self.completed_ack = CSRStorage()
        self.completed_internal = Signal(reset=0)
        self.comb += self.completed_status.status.eq(self.completed_internal)
        self.sync += If(self.completed_ack.re == 1, self.completed_internal.eq(0))

        # FSM for managing communication, in accordance with AXI-Stream
        self.submodules.fsm = FSM(reset_state="IDLE")
        self.fsm.act(
            "IDLE",
            self.stream.valid.eq(0),
            self.ready_csr_out.status.eq(0),
            If(
                (self.completed_internal == 0)
                & (self.valid_csr_in.storage == 1)
                & (self.stream.ready == 1),
                NextState("HANDSHAKE_DONE"),
            )
            .Elif(
                (self.completed_internal == 0)
                & ((self.valid_csr_in.storage == 1) & (self.stream.ready == 0)),
                NextState("HANDSHAKE_VALID_INITIATED"),
            )
            .Elif(
                (self.completed_internal == 0)
                & ((self.valid_csr_in.storage == 0) & (self.stream.ready == 1)),
                NextState("HANDSHAKE_READY_INITIATED"),
            ),
        )
        self.fsm.act(
            "HANDSHAKE_VALID_INITIATED",
            self.stream.valid.eq(1),
            self.ready_csr_out.status.eq(0),
            self.stream.data.eq(self.data_csr_in.storage),
            If(
                self.valid_csr_in.storage == 0,
                NextState("IDLE"),
            ).Elif(
                self.stream.ready == 1,
                NextState("HANDSHAKE_DONE"),
            ),
        )
        self.fsm.act(
            "HANDSHAKE_READY_INITIATED",
            self.stream.valid.eq(0),
            self.ready_csr_out.status.eq(1),
            If(
                self.stream.ready == 0,
                NextState("IDLE"),
            ).Elif(
                self.ready_csr_out.status == 1,
                NextState("HANDSHAKE_DONE"),
            ),
        )
        self.fsm.act(
            "HANDSHAKE_DONE",
            NextValue(self.completed_internal, 1),
            self.stream.valid.eq(1),
            self.ready_csr_out.status.eq(1),
            self.stream.data.eq(self.data_csr_in.storage),
            NextState("IDLE"),
        )


class StreamToCSRBridge(Module, AutoCSR):
    def __init__(self, data_width=64):
        ### --- OUTPUT STREAM (stream → CPU) ---
        self.stream = stream.Endpoint([("data", data_width)])
        self.data_csr_out = CSRStatus(data_width)
        self.valid_csr_out = CSRStatus()
        self.ready_csr_in = CSRStorage()

        # Aditional signals to account for CPU timing
        self.pending_status = CSRStatus()
        self.pending_ack = CSRStorage()
        self.pending_internal = Signal(reset=0)
        self.comb += self.pending_status.status.eq(self.pending_internal)
        self.sync += If(self.pending_ack.re == 1, self.pending_internal.eq(0))

        # FSM for managing communication, in accordance with AXI-Stream
        self.submodules.fsm = FSM(reset_state="IDLE")
        self.fsm.act(
            "IDLE",
            self.stream.ready.eq(0),
            self.valid_csr_out.status.eq(0),
            If(
                (self.pending_internal == 0)
                & (self.stream.valid == 1)
                & (self.ready_csr_in.storage == 1),
                NextState("HANDSHAKE_DONE"),
            )
            .Elif(
                (self.pending_internal == 0)
                & ((self.ready_csr_in.storage == 0) & (self.stream.valid == 1)),
                NextState("HANDSHAKE_VALID_INITIATED"),
            )
            .Elif(
                (self.pending_internal == 0)
                & ((self.ready_csr_in.storage == 1) & (self.stream.valid == 0)),
                NextState("HANDSHAKE_READY_INITIATED"),
            ),
        )
        self.fsm.act(
            "HANDSHAKE_VALID_INITIATED",
            self.stream.ready.eq(0),
            self.valid_csr_out.status.eq(1),
            self.data_csr_out.status.eq(self.stream.data),
            If(
                self.stream.valid == 0,
                NextState("IDLE"),
            ).Elif(
                self.ready_csr_in.storage == 1,
                NextState("HANDSHAKE_DONE"),
            ),
        )
        self.fsm.act(
            "HANDSHAKE_READY_INITIATED",
            self.stream.ready.eq(1),
            self.valid_csr_out.status.eq(0),
            If(
                self.ready_csr_in.storage == 0,
                NextState("IDLE"),
            ).Elif(
                self.stream.valid == 1,
                NextState("HANDSHAKE_DONE"),
            ),
        )
        self.fsm.act(
            "HANDSHAKE_DONE",
            NextValue(self.pending_internal, 1),
            self.stream.ready.eq(1),
            self.valid_csr_out.status.eq(1),
            self.data_csr_out.status.eq(self.stream.data),
            NextState("IDLE"),
        )


def handshake_scenario_1(dut):
    """
    ready and valid happen at the same time
    """
    yield dut.valid_csr_in.storage.eq(1)
    yield dut.stream.ready.eq(1)
    yield dut.data_csr_in.storage.eq(0x1122334455667788)
    yield

    yield dut.stream.ready.eq(0)
    yield dut.valid_csr_in.storage.eq(0)
    yield

    assert (yield dut.stream.valid) == 1, "Valid was not set in stream"
    assert (yield dut.ready_csr_out.status) == 1, "Ready was not set in CSR"
    yield

    assert (yield dut.completed_status.status) == 1, "completed flag is not set"
    yield

    yield dut.completed_ack.re.eq(1)
    yield
    yield dut.completed_ack.re.eq(0)
    yield
    assert (yield dut.completed_status.status) == 0, "completed flag is set"


def handshake_scenario_2(dut):
    """
    valid happens before
    """
    yield dut.valid_csr_in.storage.eq(1)
    yield dut.data_csr_in.storage.eq(0x8811223344)
    yield

    for _ in range(3):
        yield

    yield dut.stream.ready.eq(1)
    yield
    yield dut.stream.ready.eq(0)
    yield
    yield dut.valid_csr_in.storage.eq(0)

    assert (yield dut.stream.valid) == 1, "Valid was not set in stream"
    assert (yield dut.ready_csr_out.status) == 1, "Ready was not set in CSR"
    yield

    assert (yield dut.completed_status.status) == 1, "completed flag is not set"
    yield

    yield dut.completed_ack.re.eq(1)
    yield
    yield dut.completed_ack.re.eq(0)
    yield
    assert (yield dut.completed_status.status) == 0, "completed flag is set"


def handshake_scenario_3(dut):
    """
    ready happens before
    """
    yield dut.stream.ready.eq(1)
    yield

    for _ in range(3):
        yield

    yield dut.valid_csr_in.storage.eq(1)
    yield dut.data_csr_in.storage.eq(0x5548292)
    yield

    yield dut.valid_csr_in.storage.eq(0)

    yield dut.stream.ready.eq(1)
    yield
    yield dut.stream.ready.eq(0)
    yield
    yield dut.valid_csr_in.storage.eq(0)

    assert (yield dut.stream.valid) == 1, "Valid was not set in stream"
    assert (yield dut.ready_csr_out.status) == 1, "Ready was not set in CSR"
    yield

    assert (yield dut.completed_status.status) == 1, "completed flag is not set"
    yield

    yield dut.completed_ack.re.eq(1)
    yield
    yield dut.completed_ack.re.eq(0)
    yield
    assert (yield dut.completed_status.status) == 0, "completed flag is set"


# ----------------------------------------------------------------------
# Top‑level test‑bench coroutine
# ----------------------------------------------------------------------
def tb(dut):
    # reset: keep “sys” reset high for two cycles
    yield dut.cd_sys.rst.eq(1)
    yield dut.valid_csr_in.storage.eq(0)
    yield dut.stream.ready.eq(0)
    yield dut.data_csr_in.storage.eq(0x0)
    yield
    yield
    yield dut.cd_sys.rst.eq(0)
    yield

    # run the three scenarios back‑to‑back
    yield from handshake_scenario_1(dut)
    yield
    yield from handshake_scenario_2(dut)
    # yield from handshake_scenario_3(dut)

    # let the simulation idle a few extra cycles
    for _ in range(1):
        yield


# ----------------------------------------------------------------------
# Run the simulation
# ----------------------------------------------------------------------
if __name__ == "__main__":
    DW = 64  # data width used in the DUT
    CLK_PERIOD = 10  # 100 MHz default “sys” clock

    dut = CSRToStreamBridge(data_width=DW)
    dut.clock_domains.cd_sys = ClockDomain()
    vcd_name = os.path.join(os.getcwd(), "csr_stream_bridge.vcd")

    run_simulation(
        dut,
        tb(dut),
        vcd_name=vcd_name,
        clocks={"sys": CLK_PERIOD},
    )
