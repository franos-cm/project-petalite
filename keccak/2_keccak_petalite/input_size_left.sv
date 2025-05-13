import keccak_pkg::*;

module size_counter #(
    parameter int WIDTH = 32,
    parameter int bits_in_block = 64
) (
    input  logic  clk,
    input  logic  rst,
    input  logic  en_write,
    input  logic  en_count,
    input  logic[WIDTH-1:0]  size,

    output logic last_block,
    output logic[$clog2(bits_in_block)-1:0] size_left
);
    logic [WIDTH-1:0] _counter;

    always_ff @(posedge clk or posedge rst) begin
        if (rst)
            _counter <= '0;
        else if (en_write)
            _counter <= size;
        else if (en_count)
            _counter <= _counter - bits_in_block;
    end

    assign size_left = _counter[($clog2(bits_in_block)-1):0];
    assign last_block = (_counter <= bits_in_block);
endmodule