from migen import Signal, ClockDomain, If
from migen.genlib.resetsync import AsyncResetSynchronizer
from litex.gen import LiteXModule
from litex.soc.cores.clock import S7PLL
from litex.soc.interconnect.csr import CSRStorage, AutoCSR
from litex.soc.cores.clock import S7IDELAYCTRL


class PetaliteCRG(LiteXModule):
    def __init__(self, platform, sys_clk_freq):
        self.rst = Signal()
        self.power_down = Signal()
        self.cd_sys = ClockDomain()
        self.cd_sys_always_on = ClockDomain()
        # Unsure why we need these ClockDomains, but synthesis fails otherwise
        self.cd_sys4x = ClockDomain()  # TODO: check why these are needed
        self.cd_idelay = ClockDomain()
        self.cd_sfp = ClockDomain()

        # Clock configs
        self.pll = pll = S7PLL(speedgrade=-2)
        pll.register_clkin(platform.request("clk200"), 200e6)
        # TODO: shouldnt cpu_reset_n be active low? although this does work
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
        # This is also needed for some reason
        pll.create_clkout(self.cd_sys4x, 4 * sys_clk_freq)
        pll.create_clkout(self.cd_idelay, 200e6)
        pll.create_clkout(self.cd_sfp, 200e6)

        # Resets: both AO and SYS reset on rst or PLL unlock
        reset_combo = self.rst | (~pll.locked)
        self.specials += [
            AsyncResetSynchronizer(self.cd_sys, reset_combo),
            AsyncResetSynchronizer(self.cd_sys_always_on, reset_combo),
        ]

        # Also required for synthesis for some reason
        self.idelayctrl = S7IDELAYCTRL(self.cd_idelay)

        # Add false path constraints for all generated clocks
        platform.add_false_path_constraints(self.cd_sys.clk, pll.clkin)
        platform.add_false_path_constraints(self.cd_sys_always_on.clk, pll.clkin)
        platform.add_false_path_constraints(self.cd_sys4x.clk, pll.clkin)
        platform.add_false_path_constraints(self.cd_idelay.clk, pll.clkin)
        platform.add_false_path_constraints(self.cd_sfp.clk, pll.clkin)
        # Affirm these two clocks are asynchronous (since sys can pause via BUFGCE)
        platform.add_platform_command(
            "set_clock_groups -asynchronous -group {{ {sys} }} -group {{ {ao} }}",
            sys=self.cd_sys.clk,
            ao=self.cd_sys_always_on.clk,
        )


class PetaliteSimCRG(LiteXModule):
    """
    Simulation CRG identical to hardware behavior but without PLL:
      - cd_por          : reset-less POR generator
      - cd_sys_always_on: driven by simulator clock, reset by POR
      - cd_sys          : same clock, reset by POR OR power_down
    """

    def __init__(self, clk_in):
        self.cd_sys_always_on = ClockDomain()
        self.cd_sys = ClockDomain()
        self.cd_por = ClockDomain(reset_less=True)
        self.power_down = Signal(reset=0)

        # Clocks
        self.comb += [
            self.cd_sys_always_on.clk.eq(clk_in),
            self.cd_sys.clk.eq(clk_in),
            self.cd_por.clk.eq(clk_in),
        ]

        # POR (matches original migen CRG behavior)
        int_rst = Signal(reset=1)
        self.sync.por += int_rst.eq(0)

        # Asynchronous reset like on hardware CRG
        self.specials += [
            AsyncResetSynchronizer(self.cd_sys_always_on, int_rst),
            AsyncResetSynchronizer(self.cd_sys, int_rst | self.power_down),
        ]


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
                ~self.power_down,  # awake
                If(self.host_req_sleep | self.set_sleep_pulse, self.power_down.eq(1)),
            ).Else(  # sleeping
                If(~self.host_req_sleep, self.power_down.eq(0))  # host releases -> wake
            )
        ]


class PowerController(LiteXModule, AutoCSR):
    """
    For now this is a verbose way of getting a single CSR,
    but it could be useful in the future, if we add more signals.
    Moreover, just declaring this signal and CSR in the SoC
    initializer did not seem to work, so this is probably good practice.
    """

    def __init__(self):
        self.req = CSRStorage(size=1)
