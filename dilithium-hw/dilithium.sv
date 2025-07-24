`timescale 1ns / 1ps

module dilithium (
    input  logic           clk,
    input  logic           rst,
    input  logic           start,
    input  logic[1:0]      mode,
    input  logic[2:0]      sec_lvl,
    input  logic           valid_i,
    output logic           ready_i,
    input  logic[63:0]     data_i,
    output logic           valid_o,
    input  logic           ready_o,
    output logic[63:0]     data_o,
    output logic           last,
    output logic [4:0] cstate0_out,
    output logic [4:0] cstate1_out,
    output logic [4:0] cstate2_out,
    output logic [9:0] ctr_out
);
    logic start_strobe;
    logic dilithium_valid_o, dilithium_ready_o;
    logic [63:0] dilithium_data_o;

    edge_detector start_detector (
        .clk  (clk),
        .signal_in(start),
        .rising_edge(start_strobe)
    );

    dilithium_adapter adapter (
        .clk     (clk),
        .rst     (rst),
        .start   (start_strobe),
        .mode    (mode),
        .sec_lvl (sec_lvl),
        .dilithium_valid_o (dilithium_valid_o),
        .dilithium_ready_o (dilithium_ready_o),
        .dilithium_data_o (dilithium_data_o),
        .valid_o (valid_o),
        .ready_o (ready_o),
        .data_o (data_o),
        .last (last)
    );

    combined_top top (
        .clk     (clk),
        .rst     (rst),
        .start   (start_strobe),
        .mode    (mode),
        .sec_lvl (sec_lvl),
        .valid_i (valid_i),
        .ready_i (ready_i),
        .data_i (data_i),
        .valid_o (dilithium_valid_o),
        .ready_o (dilithium_ready_o),
        .data_o (dilithium_data_o),
        .cstate0_out (cstate0_out),
        .cstate1_out (cstate1_out),
        .cstate2_out (cstate2_out),
        .ctr_out (ctr_out)
    );

endmodule