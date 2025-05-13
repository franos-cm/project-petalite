import keccak_pkg::*;

module keccak (
    // Master signals
    input  logic clk,
    input  logic rst,

    // Control input signals
    input  logic ready_i,
    input  logic valid_i,
    // Control input signals
    output  logic ready_o,
    output  logic valid_o,

    // Data input signals
    input logic[w-1:0] data_in,

    // Data output signals
    output logic[w-1:0] data_out
);

    logic control_regs_enable;
    logic input_buffer_we;
    logic absorb_enable;
    logic round_count_en;
    logic state_enable;
    logic input_buffer_full;
    logic round_done;
    logic last_input_data;
    logic last_output_data;

    keccak_fsm fsm_inst (
        .clk                  (clk),
        .rst                  (rst),
        .valid_i              (valid_i),
        .ready_i              (ready_i),
        .input_buffer_full    (input_buffer_full),
        .last_input_data      (last_input_data),
        .last_output_data     (last_output_data),
        .round_done           (round_done),
        .valid_o              (valid_o),
        .ready_o              (ready_o),
        .control_regs_enable  (control_regs_enable),
        .input_buffer_we      (input_buffer_we),
        .absorb_enable        (absorb_enable),
        .round_count_en       (round_count_en),
        .state_enable         (state_enable)
    );

    keccak_datapath datapath_inst (
        .clk                  (clk),
        .rst                  (rst),
        .control_regs_enable  (control_regs_enable),
        .absorb_enable        (absorb_enable),
        .round_count_en       (round_count_en),
        .input_buffer_we      (input_buffer_we),
        .state_enable         (state_enable),
        .data_in              (data_in),
        .input_buffer_full    (input_buffer_full),
        .round_done           (round_done),
        .last_input_data      (last_input_data),
        .last_output_data     (last_output_data),
        .data_out             (data_out)
    );

endmodule