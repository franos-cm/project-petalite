`include "keccak_pkg.sv"
import <keccak_pkg>::*;

module input_size_left #(
    parameter int WIDTH,
    parameter int bytes_in_block =  w / 8
) (
    input  logic  clk,
    input  logic  rst,
    input  logic  en_write,
    input  logic  en_count,
    input  logic[WIDTH-1:0]  input_byte_size,

    output logic last_block,
    output logic[$clog2(bytes_in_block)-1:0] input_bytes_left,
);
    logic [WIDTH-1:0] _counter;
    localparam int byte_delta = w / 8;

    always_ff @(posedge clk or posedge rst) begin
        if (rst)
            _counter <= '0;
        else if (en_write)
            _counter <= input_byte_size;
        else if (en_count)
            _counter <= _counter - bytes_in_block;
    end

    assign input_bytes_left = _counter[($clog2(bytes_in_block)-1):0];
    assign last_block = (_counter <= byte_delta);
endmodule