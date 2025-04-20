from migen import *
from migen.fhdl.verilog import convert

from litex.soc.interconnect.csr import *

# Pulse Width Modulation
# https://en.wikipedia.org/wiki/Pulse-width_modulation
#     ________              ________
# ___|        |____________|        |___________
#    <-width->
#    <--------period------->

# _PWM ---------------------------------------------------------------------------------------------

class _PWM(Module, AutoCSR):
    def __init__(self, pwm):
        self.enable = enable = Signal()
        self.width  = width  = Signal(32)
        self.period = period = Signal(32)

        # # #

        self.count = Signal(32)

        self.sync += [
            If(
                # Only count up if its enbled
                enable,

                # If count reach period, set count to 0
                If(self.count >= period,
                   self.count.eq(0)
                ).Else(
                    self.count.eq(self.count + 1)
                ),

                # If count < width, set pwm to 1; else 0
                If((self.count < width - 1) | (self.count == self.period), pwm.eq(1)).Else(pwm.eq(0)),
            ).Else(
                self.count.eq(0),
                pwm.eq(0),
            )
        ]

# PWM ----------------------------------------------------------------------------------------------

class PWM(Module, AutoCSR):
    def __init__(self, pwm):
        self.enable = CSRStorage()
        self.width  = CSRStorage(32)
        self.period = CSRStorage(32)

        _pwm = _PWM(pwm)
        self.submodules += _pwm

        self.comb += [
            _pwm.enable.eq(self.enable.storage),
            _pwm.width.eq(self.width.storage),
            _pwm.period.eq(self.period.storage)
        ]

# Main ---------------------------------------------------------------------------------------------

if __name__ == '__main__':
    pwm = Signal()
    dut = _PWM(pwm)

    def dut_tb(dut):
        yield dut.enable.eq(1)
        yield dut.period.eq(100)
    
        for width in [0, 25, 50, 75, 100]:
            yield dut.width.eq(width)

            for i in range(1000):
                if (yield dut.count) == (yield dut.period):
                    print("Period reached")
                    print((yield dut.count))
                    print((yield dut.period))
                yield
    run_simulation(dut, dut_tb(dut), vcd_name="pwm.vcd")

    dut_for_verilog = _PWM(pwm)
    verilog_text = convert(dut_for_verilog, name="pwm", ios={dut_for_verilog.enable, dut_for_verilog.width, dut_for_verilog.period, pwm})
    verilog_text.write("pwm.v")
