module keccak_fsm (
    input  logic clk,
    input  logic rst,
    input  logic valid_i,
    input  logic ready_i,
    input  logic input_buffer_full,
    input  logic last_input_data,
    input  logic last_output_data,
    input  logic round_done,

    output logic valid_o,
    output logic ready_o,
    output logic control_regs_enable,
    output logic input_buffer_we,
    output logic output_buffer_w,
    output logic absorb_enable,
    output logic round_count_en,
    output logic state_enable
);

    // Define states using enum
    typedef enum logic [5:0] {
        RESTART,
        START,
        INITIAL_ABSORB,
        ABSORB,
        FINAL_ABSORB,
        SQUEEZE
    } state_t;

    state_t current_state, next_state;

    // State register
    always_ff @(posedge clk or posedge rst) begin
        if (rst)
            current_state <= RESTART;
        else
            current_state <= next_state;
    end

    // Next state logic
    always_comb begin
    absorb_enable        = 0;
    round_count_en       = 0;
    state_enable         = 0;
    control_regs_enable  = 0;
    input_buffer_we      = 0;
    output_buffer_w      = 0;
    ready_o              = 0;
    valid_o              = 0;

        unique case (current_state)
            RESTART:  begin
                next_state = START;
            end

            START:  begin
                if (valid_i) begin
                    next_state = INITIAL_ABSORB;
                    control_regs_enable = 1;
                end else begin
                    next_state = START;
                end
            end

            // Taking in first r bits
            INITIAL_ABSORB:  begin
                if (input_buffer_full) begin
                    next_state = ABSORB;
                    absorb_enable = 1;
                    round_count_en = 0;
                    ready_o = 0;
                
                end else begin 
                    next_state = INITIAL_ABSORB;
                    input_buffer_we = valid_i ? 1 : 0;
                    ready_o = 1;
                end
            end

            // Absorbs other input bits
            ABSORB:  begin
                if (round_done && last_input_data) begin
                    next_state = FINAL_ABSORB;
                end else begin
                    next_state = ABSORB;
                end
                // Input buffer is ready, and round is done
                if (input_buffer_full && round_done) begin
                    absorb_enable = 1;
                    round_count_en = 0;
                    state_enable = 0;
                    input_buffer_we = 0;
                    ready_o = 0;
                end
                else if (input_buffer_full && !round_done) begin
                    absorb_enable = 0;
                    round_count_en = 1;
                    state_enable = 1;
                    input_buffer_we = 0;
                    ready_o = 0;
                end
                else if (!input_buffer_full && !round_done) begin
                    absorb_enable = 0;
                    round_count_en = 1;
                    state_enable = 1;
                    input_buffer_we = valid_i ? 1 : 0;
                    ready_o = 1;
                end
                else if (!input_buffer_full && round_done) begin
                    absorb_enable = 0;
                    round_count_en = 1;
                    state_enable = 0;
                    input_buffer_we = valid_i ? 1 : 0;
                    ready_o = 1;
                end
            end

            FINAL_ABSORB:  begin
                if (round_done) begin
                    next_state = SQUEEZE;
                    // output_buffer_we = 1;
                end else begin
                    next_state = FINAL_ABSORB;
                end
            end

            SQUEEZE:  begin
                next_state = SQUEEZE;
//                if (round_done && last_output_data) begin
//                    next_state = FINAL_SQUEEZE;
//                end else begin
//                    next_state = SQUEEZE;
//                end

//                if (output_buffer_empty && round_done) begin
//                    output_buffer_we = 1;
//                end

            end


            default: next_state = RESTART;
        endcase
    end

endmodule
