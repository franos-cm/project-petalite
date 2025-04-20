from migen import *
from migen.fhdl.verilog import convert
import os

class SimpleCounter(Module):
    def __init__(self):
        self.input = Signal(8)
        self.output = Signal(8)
        
        # Example logic: output = input + 1
        self.sync += self.output.eq(self.input + 1)

def testbench(dut):
    print("Running testbench")

    yield dut.input.eq(5)
    assert (yield dut.input) == 0, f"1: Expected 0 in input, got {(yield dut.input)}" # initial input is 0, clock has not advances yet
    yield  # yield advances 1 clock and commits 5
    assert (yield dut.input) == 5, f"2: Expected 5, got {(yield dut.input)}" # now 5 is supposed to be committed to input
    yield  # yield advances 1 clock and sync logic is executed
    assert (yield dut.output) == 6, f"3: Expected 6, got {(yield dut.output)}" # 6 is supposed to be committed to output

    print("All tests passed!")

# Run testbench
dut = SimpleCounter()
vcd_name = os.path.join(os.getcwd(), "simplecounter.vcd")
run_simulation(dut, testbench(dut), vcd_name=vcd_name)
print("Waveforms written to simplecounter.vcd")

# Get Verilog code
dut_for_verilog = SimpleCounter()
verilog_text = convert(dut_for_verilog, name="simple_counter", ios={dut_for_verilog.input, dut_for_verilog.output})
verilog_text.write("simplecounter.v")
print("Verilog code written to simplecounter.v")