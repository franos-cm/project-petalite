module keccak_tb();
    logic clk = 0;
    logic rst = 0;
    logic ready_i;
    logic valid_i;
    logic [63:0] data_in; // Adjust width as needed
    logic ready_o;
    logic valid_o;
    logic [63:0] data_out; // Adjust width as needed

    // ...existing code (clock and reset generation)...
    always #5 clk = ~clk;

    initial begin
        rst = 1;
        #20;
        rst = 0;
        ready_i = 1;
        valid_i = 1;
        data_in  = 64'hDEADBEEF;
        #40;
        // ...existing code (additional stimulus)...
        $finish;
    end

    keccak dut (
        .clk(clk),
        .rst(rst),
        .ready_i(ready_i),
        .valid_i(valid_i),
        .ready_o(ready_o),
        .valid_o(valid_o),
        .data_in(data_in),
        .data_out(data_out)
        // ...existing code (connect other signals as needed)...
    );
endmodule
