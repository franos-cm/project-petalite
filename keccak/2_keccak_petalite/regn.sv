module regn #(
    parameter int N = 32,
    parameter logic [N-1:0] INIT = '0  // default initialization
) (
    input  logic clk,
    input  logic rst,
    input  logic en,
    input  logic [N-1:0] data_in,
    output logic [N-1:0] data_out
);

    always_ff @(posedge clk) begin
        if (rst)
            data_out <= INIT;
        else if (en)
            data_out <= data_in;
    end

endmodule
