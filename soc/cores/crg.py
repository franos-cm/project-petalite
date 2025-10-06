from migen import Signal, ClockDomain, If
from litex.gen import LiteXModule
from litex.soc.cores.clock import S7PLL
from migen.genlib.resetsync import AsyncResetSynchronizer


class PetaliteCRG(LiteXModule):
    def __init__(self, platform, sys_clk_freq):
        self.rst = Signal()
        self.power_down = Signal()
        self.cd_sys = ClockDomain()
        self.cd_sys_always_on = ClockDomain()

        # Clock configs
        self.pll = pll = S7PLL(speedgrade=-2)
        pll.register_clkin(platform.request("clk200"), 200e6)
        self.comb += pll.reset.eq(platform.request("cpu_reset_n") | self.rst)
        # System clock domain is gated by power_down, which allows
        # for "powering down" the TPM in some cases
        pll.create_clkout(
            self.cd_sys,
            sys_clk_freq,
            with_reset=False,
            buf="bufgce",
            ce=(pll.locked & (~self.power_down)),
        )
        # Secondary always-on clock domain which is not gated
        # by power_down, so we can keep essential systems running
        pll.create_clkout(
            self.cd_sys_always_on,
            sys_clk_freq,
            with_reset=False,
            buf="bufgce",
            ce=pll.locked,
        )

        # Resets: both AO and SYS reset on rst or PLL unlock
        reset_combo = self.rst | (~pll.locked)
        self.specials += [
            AsyncResetSynchronizer(self.cd_sys, reset_combo),
            AsyncResetSynchronizer(self.cd_sys_always_on, reset_combo),
        ]

        # Vivado configs
        platform.add_false_path_constraints(self.cd_sys.clk, pll.clkin)


class PowerBridge(LiteXModule):
    """
    Policy B latch in AO:
      - set_sleep_pulse : AO pulse (CPU request, sys->AO via PulseSynchronizer)
      - host_req_sleep  : AO level (host requests/maintains sleep; any AO source)
      - power_down      : AO level to CRG (1 = gate cd_sys)
    """

    def __init__(self):
        self.set_sleep_pulse = Signal()
        self.host_req_sleep = Signal()
        self.power_down = Signal(reset=0)

        self.sync += [
            If(
                self.power_down == 0,  # awake
                If(self.host_req_sleep | self.set_sleep_pulse, self.power_down.eq(1)),
            ).Else(  # sleeping
                If(~self.host_req_sleep, self.power_down.eq(0))  # host releases -> wake
            )
        ]
