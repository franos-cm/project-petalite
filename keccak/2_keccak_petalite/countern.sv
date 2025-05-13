module countern #(
    parameter int N = 32,
    parameter int counter_width = (N > 1) ? $clog2(N) : 1
) (
    input  logic  clk,
    input  logic  rst,
    input  logic  en,
    input  logic  count_up,

    output logic[counter_width-1:0]   counter,
    output logic count_end
);
    logic [counter_width-1:0] _counter;

    always_ff @(posedge clk or posedge rst) begin
        if (rst)
            _counter <= '0;
    
        else if (en) begin
            if (count_up) begin
                if (_counter == N - 1)
                    _counter <= '0;
                else
                    _counter <= _counter + 1;
            end
            else begin
                if (_counter == '0)
                    _counter <= N - 1;
                else
                    _counter <= _counter - 1;
            end
        end
    end

    assign counter = _counter;
    // Generate count_end: HIGH when counter is about to wrap
    assign count_end = (count_up && (_counter == N - 1)) ||
                       (!count_up && (_counter == 0));
endmodule