`timescale 1ns / 1ps

module combined_top (
    input clk_reg,
    input clk_wire
);

    // clock_consumer_vhd vhd_clock_reg(
    //     .clk(clk_reg)
    // );

    clock_consumer_sv sv_clock_reg(
        .clk(clk_reg)
    );


    // clock_consumer_vhd vhd_clock_wire(
    //     .clk(clk_wire)
    // );

    clock_consumer_sv sv_clock_wire(
        .clk(clk_wire)
    );


    
endmodule
