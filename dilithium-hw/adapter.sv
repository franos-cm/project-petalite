`timescale 1ns / 1ps

module fifo_buffer #(
    parameter int WIDTH,
    parameter int DEPTH
) (
    input  logic              clk,
    input  logic              rst,
    input  logic              read_en,
    input  logic              write_en,
    input  logic[WIDTH-1:0]   data_in,
    output logic[WIDTH-1:0]   data_out,
    output logic              full,
    output logic              last_word_in_buffer,
    output logic              empty
);
    localparam ADDR_WIDTH = $clog2(DEPTH);

    (* ram_style = "block" *) logic [WIDTH-1:0] buffer_data [DEPTH-1:0];
    logic [ADDR_WIDTH-1:0] read_address, write_address;
    // NOTE: we could avoid having counter by having one extra bit in the adresses, but the
    // update logic for the adresses gets more complex... this solution is more intuitive.
    logic [ADDR_WIDTH:0] counter, updated_counter;

    always_ff @(posedge clk) begin
        
    
        if (rst) begin
            read_address <= 0;
            write_address <= 0;
            updated_counter = 0;
        end
        else begin
            updated_counter = counter;
            if (write_en && !full) begin
                buffer_data[write_address] <= data_in;
                write_address <= (write_address == DEPTH-1) ? 0 : write_address + 1;
                updated_counter = updated_counter + 1;
            end
            if (read_en && !empty) begin
                read_address <= (read_address == DEPTH-1) ? 0 : read_address + 1;
                updated_counter = updated_counter - 1;
            end
        end

        // Note non blocking statements for updated_counter
        counter <= updated_counter;
    end

    assign data_out = buffer_data[read_address];
    assign empty = (counter == 0);
    assign last_word_in_buffer = (counter == 'd1);
    assign full  = (counter == DEPTH);
endmodule


module edge_detector (
    input  logic clk,
    input  logic signal_in,
    output logic rising_edge,
    output logic falling_edge
);
    logic prev_signal;

    always_ff @(posedge clk) begin
        prev_signal <= signal_in;
    end

    assign rising_edge = signal_in & ~prev_signal;
    assign falling_edge = (~signal_in) & prev_signal;

endmodule


module dilithium_adapter #(
    parameter w = 64
) (
    input  logic              clk,
    input  logic              rst,
    input  logic              start,
    input logic[1:0]          mode,
    input logic[2:0]          sec_lvl,

    // Coming from Dilithium
    input  logic           dilithium_valid_o,
    output logic           dilithium_ready_o,
    input  logic[w-1:0]    dilithium_data_o,

    // External IOs
    output logic           valid_o,
    input  logic           ready_o,
    output logic [w-1:0]   data_o,
    output logic           last


);
    // Measured in words
    localparam int max_output_size = 932;
    localparam int max_output_width = $clog2(max_output_size);

    logic buffer_empty, output_last, output_done;
    logic last_word_in_buffer;
    logic [max_output_width - 1 : 0] output_size;


    // Buffer
    fifo_buffer #(
        .WIDTH(64),
        .DEPTH(max_output_size)
    ) buffer (
        .clk  (clk),
        .rst  (rst || start),
        .read_en (ready_o),
        .write_en (dilithium_valid_o),
        .data_in (dilithium_data_o),
        .data_out (data_o),
        .empty (buffer_empty),
        .last_word_in_buffer (last_word_in_buffer)
    );

    // Output size counter
    countern #(
        .WIDTH(max_output_width) 
    ) output_counter (
        .clk (clk),
        .rst (rst || start),
        .en (dilithium_valid_o),
        .load_max (start),
        .max_count(output_size),
        .count_last(output_last),
        .count_end(output_done)
    );

    // Latch to know if the first pad has already been used
    latch dilithium_ready_in_latch (
        .clk (clk),
        .set (start),
        .rst (rst || (output_last && dilithium_valid_o)),
        .q   (dilithium_ready_o)
    );


    always_comb begin
        if (mode == 0)
            if (sec_lvl == 3'd2)
                output_size = 'd480;
            else if (sec_lvl == 3'd3)
                output_size = 'd744;
            else
                output_size = 'd932;
        else if (mode == 2'd1)
            output_size = 'd1;
        else
            if (sec_lvl == 3'd2)
                output_size = 'd303;
            else if (sec_lvl == 3'd3)
                output_size = 'd412;
            else
                output_size = 'd575;
    end;

    assign valid_o = !buffer_empty;
    assign last = output_done && last_word_in_buffer;

endmodule