import keccak_pkg::*;


module keccak_datapath (
    input  logic clk,
    input  logic rst,
    input logic control_regs_enable,
    input logic absorb_enable,
    input logic round_count_en,
    input logic input_buffer_we,
    input logic state_enable,
    input logic output_buffer_we,
    input logic[w-1:0] data_in,

    output logic input_buffer_full,
    output logic round_done,
    output logic last_input_data,
    output logic last_output_data,
    output logic[w-1:0] data_out
);
    logic[3:0] operation_mode;

    // Round
    logic[1599:0] state_reg_in;
    logic[1599:0] state_reg_out;
    logic [1087:0] input_buffer_out;

    // Round counter
    logic[$clog2(24)-1:0] round_num;

    // Round constant gen
    logic[w-1:0] round_constant;
    
    // Sipo and Piso
    logic[w-1:0] input_data_in;

    // Sipo and Piso counter
    logic buffer_counter_enable;
    logic buffer_counter_reset;


    regn #(
        .N(4)
    ) operation_mode_reg (
        .clk  (clk),
        .rst (rst),
        .en (control_regs_enable),
        .data_in (data_in[63:60]),
        .data_out (operation_mode)
    );

    size_counter #(
        .WIDTH(32)
    ) input_size_left (
        .clk (clk),
        .rst (rst),
        .en_write(control_regs_enable),
        .en_count(input_buffer_we),
        .size(data_in[31:0]),
        .last_block(last_input_data)
    );

    size_counter #(
        .WIDTH(28)
    ) output_size_left (
        .clk (clk),
        .rst (rst),
        .en_write(control_regs_enable),
        .en_count(output_buffer_we), // TODO: this is not right
        .size(data_in[59:32])
    );

    countern #(
        .N(24)
    ) round_counter (
        .clk  (clk),
        .rst (rst),
        .en (round_count_en),
        .count_up (1),
        .counter(round_num),
        .count_end(round_done)
    );

    assign buffer_counter_enable = input_buffer_we;
    assign buffer_counter_reset = absorb_enable || rst;
    countern #(
        .N(17)
    ) buffer_counter (
        .clk  (clk),
        .rst (buffer_counter_reset),
        .en (buffer_counter_enable),
        .count_up (1),
        .count_end (input_buffer_full)
    );


    // padding_generator #(
    //     .WIDTH(w),
    // ) padding_gen (
    //     .clk(clk),
    //     .rst(rst),
    // )

    assign input_data_in = data_in;

    sipo_buffer #(
        .WIDTH(w),
        .DEPTH(17)
    ) input_buffer(
        .clk (clk),
        .rst (rst),
        .en (input_buffer_we),
        .data_in (input_data_in),
        .data_out (input_buffer_out)
    );

    round_constant_generator round_constant_gen (
        .round_num  (round_num),
        .round_constant (round_constant)
    );

    regn #(
        .N(1600)
    ) state_reg (
        .clk  (clk),
        .rst (rst),
        .en (state_enable),
        .data_in (state_reg_in),
        .data_out (state_reg_out)
    );
    
    // Conversions to keccak_function format
    k_state round_in;
    k_state round_out;
    genvar row, col, i;
    generate
      for (row = 0; row < 5; row++) begin
        for (col = 0; col < 5; col++) begin
          for (i = 0; i < 64; i++) begin : assign_bits
            localparam int idx = row*5*64 + col*64 + i;
            if ((row < 3) || (row == 3 && col < 2)) begin
              // Rate part (first 1088 bits)
              assign round_in[row][col][i] =
                state_reg_out[idx] ^ (input_buffer_out[idx] & absorb_enable);
            end else begin
              // Capacity part (remaining 512 bits)
              assign round_in[row][col][i] = state_reg_out[idx];
            end
          end
        end
      end
    endgenerate

    keccak_f keccak_function(
        .round_in(round_in),
        .round_constant_signal(round_constant),
        .round_out(round_out)
    );

    // Conversions from keccak_function format
    genvar row2, col2, i2;
    generate
      for (row2 = 0; row2 < 5; row2++) begin
        for (col2 = 0; col2 < 5; col2++) begin
          for (i2 = 0; i2 < 64; i2++) begin
            localparam int idx = row2*5*64 + col2*64 + i2;
            assign state_reg_in[idx] = round_out[row2][col2][i2];
          end
        end
      end
    endgenerate

    piso_buffer #(
        .WIDTH(w),
        .DEPTH(17)
    ) output_buffer(
        .clk (clk),
        .rst (rst),
        .en (input_buffer_we),
        .data_in (state_reg_out[1087:0]), // state reg in or out?
        .data_out (data_out)
    );


endmodule