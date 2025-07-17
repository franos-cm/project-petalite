from migen import Module, Signal
from litex.soc.interconnect.csr import CSRStorage, CSRStatus, AutoCSR


class PetaliteMailbox(Module, AutoCSR):
    """Petalite's side of the mailbox - only CSRs petalite should see"""

    def __init__(self):
        # CSRs that will be added to petalite's CSR space
        self.to_host = CSRStorage(32)
        self.to_host_valid = CSRStorage(1)
        self.from_host = CSRStatus(32)
        self.from_host_valid = CSRStatus(1)

        # Signals for connecting to host side
        self.tx_data = Signal(32)
        self.tx_valid = Signal()
        self.rx_data = Signal(32)
        self.rx_valid = Signal()

        # Connect CSRs to signals
        self.comb += [
            self.tx_data.eq(self.to_host.storage),
            self.tx_valid.eq(self.to_host_valid.storage),
            self.from_host.status.eq(self.rx_data),
            self.from_host_valid.status.eq(self.rx_valid),
        ]


class HostMailbox(Module, AutoCSR):
    """Host's side of the mailbox - only CSRs host should see"""

    def __init__(self):
        # CSRs that will be added to host's CSR space
        self.to_petalite = CSRStorage(32)
        self.to_petalite_valid = CSRStorage(1)
        self.from_petalite = CSRStatus(32)
        self.from_petalite_valid = CSRStatus(1)

        # Signals for connecting to petalite side
        self.tx_data = Signal(32)
        self.tx_valid = Signal()
        self.rx_data = Signal(32)
        self.rx_valid = Signal()

        # Connect CSRs to signals
        self.comb += [
            self.tx_data.eq(self.to_petalite.storage),
            self.tx_valid.eq(self.to_petalite_valid.storage),
            self.from_petalite.status.eq(self.rx_data),
            self.from_petalite_valid.status.eq(self.rx_valid),
        ]
