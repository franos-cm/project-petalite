`include "keccak_pkg.sv"
import <keccak_pkg>::*;


module keccak (
    // Master signals
    input  logic clk,
    input  logic rst,

    // Control input signals
    input  logic ready,

    // Data input signals
    input logic[w-1:0] data_in,
    input logic[15:0] size_in,

    // Data output signals
    output logic[w-1:0] data_out,

);

    logic[w-1:0]   round_constant;

    round_const_gen round_constant_generator (
        .round_num  (top_in), // TODO: change this
        .round_constant (round_constant)
    );

    sipo_buffer #(
        .WIDTH(w),
        .DEPTH((rate/w)) // TODO: check if this is an int
    ) const_gen (
        .clk        (clk),
        .rst        (rst),
        
        .round_num  (top_in), // TODO: change this
        .round_constant (round_constant)
    );

endmodule