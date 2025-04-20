`include "keccak_pkg.sv"
import <keccak_pkg>::*;


module keccak_f (
    input  k_state            data_in,
    input  logic[WIDTH-1:0]   round_constant,
    input  k_state            data_out,
);

endmodule

