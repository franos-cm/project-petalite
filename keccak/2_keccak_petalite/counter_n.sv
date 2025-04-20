module counter_n #(
    parameter int n,
    parameter int counter_width = (n > 1) ? $clog2(n) : 1
) (
    input  logic  clk,
    input  logic  rst,
    input  logic  en,
    input  logic  count_up,

    output logic[counter_width-1:0]   counter,
);
    logic [counter_width-1:0] _counter;

    always_ff @(posedge clk or posedge rst) begin
        if (rst)
            _counter <= '0;
    
        else if (en) begin
            if (count_up) begin
                if (_counter == n - 1)
                    _counter <= '0;
                else
                    _counter <= _counter + 1;
            end
            else begin
                if (_counter == '0)
                    _counter <= n - 1;
                else
                    _counter <= _counter - 1;
            end
        end
    end

    assign counter = _counter;
endmodule