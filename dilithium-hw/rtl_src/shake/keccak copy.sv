// `timescale 1ns / 1ps
// import keccak_pkg_mine::*;

// // module keccak (
// //     // Master signals
// //     input wire logic clk,
// //     input var logic rst,

// //     // Control input signals
// //     input var logic ready_in,
// //     input var logic valid_in,
// //     // Control output signals
// //     output wire logic ready_out,
// //     output wire logic valid_out,

// //     // Data input signals
// //     input var logic[w-1:0] data_in,
// //     // Data output signals
// //     output wire logic[w-1:0] data_out
// // );


// module keccak (
//     // Master signals
//     input wire logic clk,
//     input wire logic rst,

//     // Control input signals
//     input wire logic ready_in,
//     input wire logic valid_in,
//     // Control output signals
//     output var logic ready_out,
//     output var logic valid_out,

//     // Data input signals
//     input wire logic[w-1:0] data_in,
//     // Data output signals
//     output var logic[w-1:0] data_out
// );

//     // Changing polarity to be coherent with reference_code
//     wire logic valid_in_internal, ready_in_internal;

//     // First to second stage data signals
//     wire logic[RATE_SHAKE128-1:0] rate_input;
//     wire logic[1:0] operation_mode_load_stage;
//     wire logic[31:0] output_size_load_stage;

//     // Second to third stage data signals
//     wire logic[RATE_SHAKE128-1:0] rate_output;
//     wire logic[1:0] operation_mode_permute_stage;
//     wire logic[31:0] output_size_permute_stage;
//     wire logic output_buffer_we;

//     // Handshaking signals
//     wire logic input_buffer_ready, input_buffer_ready_wr, input_buffer_ready_clr;
//     wire logic last_output_block, last_output_block_wr, last_output_block_clr;
//     wire logic output_buffer_available, output_buffer_available_wr, output_buffer_available_clr;
//     wire logic last_block_in_buffer, last_block_in_buffer_wr, last_block_in_buffer_clr;


//     // Polarity change
//     assign valid_in_internal = !valid_in;
//     assign ready_in_internal = !ready_in;


//     // First pipeline stage
//     load_stage load_pipeline_stage (
//         // External inputs
//         .clk                     (clk),
//         .rst                     (rst),
//         .valid_in                (valid_in_internal),
//         .data_in                 (data_in),
//         // Outputs for next stage
//         .rate_input              (rate_input),
//         .operation_mode          (operation_mode_load_stage),
//         .output_size             (output_size_load_stage),
//         // External outputs
//         .ready_out               (ready_out),
//         // Second stage pipeline handshaking
//         .input_buffer_ready      (input_buffer_ready),
//         .input_buffer_ready_wr   (input_buffer_ready_wr),
//         .last_block_in_buffer_wr (last_block_in_buffer_wr)
//     );

//     // Signaling between first and second stage
//     latch input_buffer_ready_latch (
//         .clk (clk),
//         .set (input_buffer_ready_wr),
//         .rst (input_buffer_ready_clr),
//         .q   (input_buffer_ready)
//     );
//     latch last_block_in_buffer_latch (
//         .clk (clk),
//         .set (last_block_in_buffer_wr),
//         .rst (last_block_in_buffer_clr),
//         .q   (last_block_in_buffer)
//     );

//     // Second pipeline stage
//     permute_stage permute_pipeline_stage (
//         // External inputs
//         .clk                          (clk),
//         .rst                          (rst),
//         // Inputs from previous stage
//         .rate_input                   (rate_input),
//         .operation_mode_in            (operation_mode_load_stage),
//         .output_size_in               (output_size_load_stage),
//         // Outputs for next stage
//         .rate_output                  (rate_output),
//         .operation_mode_out           (operation_mode_permute_stage),
//         .output_size_out              (output_size_permute_stage),
//         .output_buffer_we             (output_buffer_we),
//         // First stage pipeline handshaking
//         .input_buffer_ready           (input_buffer_ready),
//         .input_buffer_ready_clr       (input_buffer_ready_clr),
//         .last_block_in_buffer         (last_block_in_buffer),
//         .last_block_in_buffer_clr     (last_block_in_buffer_clr),
//         // Third stage pipeline handshaking
//         .output_buffer_available      (output_buffer_available),
//         .output_buffer_available_clr  (output_buffer_available_clr),
//         .last_output_block_wr         (last_output_block_wr)
//     );

//     // Signaling between second and third stage
//     latch output_buffer_available_latch (
//         .clk (clk),
//         .set (output_buffer_available_wr),
//         .rst (output_buffer_available_clr),
//         .q   (output_buffer_available)
//     );
//     latch last_output_block_latch (
//         .clk (clk),
//         .set (last_output_block_wr),
//         .rst (last_output_block_clr),
//         .q   (last_output_block)
//     );

//     // Third pipeline stage
//     dump_stage dump_pipeline_stage (
//         // External inputs
//         .clk                         (clk),
//         .rst                         (rst),
//         .ready_in                    (ready_in_internal),
//         // Inputs from previous stage
//         .rate_output                 (rate_output),
//         .operation_mode              (operation_mode_permute_stage),
//         .output_size                 (output_size_permute_stage),
//         .output_buffer_we            (output_buffer_we),
//         // External outputs
//         .data_out                    (data_out),
//         .valid_out                   (valid_out),
//         // Second stage pipeline handshaking
//         .last_output_block           (last_output_block),
//         .last_output_block_clr       (last_output_block_clr),
//         .output_buffer_available_wr  (output_buffer_available_wr)
//     );


// endmodule
