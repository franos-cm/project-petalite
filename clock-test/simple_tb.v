`timescale 1ns / 1ps
`define P 10

module tb_keygen_top;
    reg toggle = 1;
    reg clk_reg = 1;

    wire clk_wire;
    assign clk_wire = clk_reg;
    combined_top DUT (
        .clk_reg(clk_reg),
        .clk_wire(clk_wire)
    );
  

    always @(posedge clk_reg) begin
        toggle <= !toggle;
    end
      
  
    always #(`P/2) clk_reg = ~clk_reg;
  

endmodule
`undef P