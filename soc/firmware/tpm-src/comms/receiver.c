#include "receiver.h"

// Global vars for the interrupt service
static volatile rx_state_t rx_state = RX_WAITING_FOR_HEADER;
static volatile rx_return_code_t rx_code = SUCCESSFUL;
static volatile uint32_t bytes_collected = 0;
static volatile uint32_t expected_cmd_len = 0;

// ---- Helpers ----
static inline uint32_t be32_read(const uint8_t *p)
{
    // TPM marshaling is big-endian ("MSB first")
    return ((uint32_t)p[0] << 24) |
           ((uint32_t)p[1] << 16) |
           ((uint32_t)p[2] << 8) |
           ((uint32_t)p[3] << 0);
}

// Where commandSize lives inside the header (offset 2, length 4)
static inline uint32_t header_extract_command_size(const uint8_t *hdr)
{
    return be32_read(&hdr[2]);
}

static void receiver_reset(void)
{
    // Reset assembler state
    rx_state = RX_WAITING_FOR_HEADER;
    rx_code = SUCCESSFUL;
    bytes_collected = 0;
    expected_cmd_len = 0;
}

static rx_return_code_t command_length_is_valid()
{
    if (expected_cmd_len < TPM_HEADER_LEN)
        return ER_CMDSIZE_SMALLER_THAN_HEADER;
    if (expected_cmd_len > TPM_MAX_CMD_LEN)
        return ER_CMDSIZE_TOO_LARGE;
    return SUCCESSFUL;
}

// ---- Interrupt Service Routine ----
static void uart_rx_isr(void)
{
    // Drain all available bytes quickly
    while (uart_read_nonblock())
    {
        uint8_t b = uart_read();

        // If a previous error or ready state hasn't been consumed, drop bytes (or mask RX)
        if (rx_state == RX_COMMAND_READY || rx_state == RX_ERROR)
        {
            // Optional: you could mask RX to apply backpressure:
            // uint32_t en = uart_ev_enable_read();
            // uart_ev_enable_write(en & ~UART_EV_RX);
            continue;
            // We should send an error message back or something like that
        }

        ((volatile uint8_t *)tpm_cmd_shared_buf)[bytes_collected++] = b;

        if (rx_state == RX_WAITING_FOR_HEADER && bytes_collected == TPM_HEADER_LEN)
        {
            // We just completed the header; parse total command size
            expected_cmd_len = header_extract_command_size((const uint8_t *)tpm_cmd_shared_buf);
            rx_code = command_length_is_valid(expected_cmd_len);

            if (rx_code)
            {
                rx_state = RX_ERROR;
                continue;
            }

            rx_state = (expected_cmd_len == TPM_HEADER_LEN) ? RX_COMMAND_READY
                                                            : RX_WAITING_FOR_BODY;
        }

        if (rx_state == RX_WAITING_FOR_BODY && bytes_collected == expected_cmd_len)
        {
            rx_state = RX_COMMAND_READY;
        }
    }
}

static void uart_isr(void)
{
    uint32_t pending = uart_ev_pending_read();

    if (pending & UART_EV_RX)
    {
        uart_rx_isr();
        uart_ev_pending_write(UART_EV_RX);
    }

    if (pending & UART_EV_TX)
    {
        uart_ev_pending_write(UART_EV_TX);
    }
}

// ---- Public API for main loop ----
// Call once at startup
void uart_irq_init(void)
{
    receiver_reset();

    // Clear stale events and enable RX interrupts
    uart_ev_pending_write(UART_EV_RX | UART_EV_TX);
    uart_ev_enable_write(UART_EV_RX); // enable RX only

    // Hook ISR and unmask at CPU/PLIC level
    irq_set_handler(UART_INTERRUPT, uart_isr);
    irq_setmask(irq_getmask() | (1u << UART_INTERRUPT));
    irq_enable();
}

bool inline receiver_ingestion_done(void)
{
    return (rx_state == RX_COMMAND_READY) || (rx_state == RX_ERROR);
}

uint32_t read_command()
{
    if (rx_state != RX_COMMAND_READY)
        return rx_code;

    memcpy(tpm_cmd_private_buf, tpm_cmd_shared_buf, bytes_collected);

    // Optional: re-enable RX if you masked it in ISR
    // uint32_t en = uart_ev_enable_read();
    // uart_ev_enable_write(en | UART_EV_RX);

    receiver_reset();
    return rx_code;
}
