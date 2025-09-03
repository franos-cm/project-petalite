#include "transport.h"

// Global vars for the interrupt service
static rx_state_t rx_state = RX_WAITING_FOR_HEADER;
static rx_return_code_t rx_code = SUCCESSFUL;
static uint32_t bytes_collected = 0;
uint32_t expected_cmd_len = 0;

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

// ---- Interrupt Service Routine ----
static void rx_isr(void)
{
    // Drain all available bytes quickly
    while (!uart_rxempty_read())
    {
        uint8_t b = uart_rxtx_read();

        // If a previous error or ready state hasn't been consumed, drop bytes (or mask RX)
        if (rx_state == RX_COMMAND_READY || rx_state == RX_ERROR)
        {
            // Optional: you could mask RX to apply backpressure:
            // uint32_t en = uart_ev_enable_read();
            // uart_ev_enable_write(en & ~UART_EV_RX);
            continue;
            // We should send an error message back or something like that
        }

        ((volatile uint8_t *)tpm_cmd_buf)[bytes_collected++] = b;

        if (rx_state == RX_WAITING_FOR_HEADER && bytes_collected == TPM_HEADER_LEN)
        {
            // We just completed the header; parse total command size
            expected_cmd_len = header_extract_command_size((const uint8_t *)tpm_cmd_buf);

            rx_state = (expected_cmd_len == TPM_HEADER_LEN) ? RX_COMMAND_READY : RX_WAITING_FOR_BODY;
        }

        if (rx_state == RX_WAITING_FOR_BODY && bytes_collected == expected_cmd_len)
            rx_state = RX_COMMAND_READY;
    }
}

static void transport_isr(void)
{
    uint32_t pending = uart_ev_pending_read();

    if (pending & UART_EV_RX)
    {
        rx_isr();
        uart_ev_pending_write(UART_EV_RX);
    }

    if (pending & UART_EV_TX)
    {
        uart_ev_pending_write(UART_EV_TX);
    }
}

// ---- Public API for main loop ----
// Call once at startup
void transport_irq_init(void)
{
    receiver_reset();

    // Clear stale events and enable RX interrupts
    uart_ev_pending_write(uart_ev_pending_read());
    uart_ev_enable_write(UART_EV_RX); // enable RX only, for now

    // Hook ISR and unmask at CPU/PLIC level
    irq_attach(UART_INTERRUPT, transport_isr);
    irq_setmask(irq_getmask() | (1u << UART_INTERRUPT));
    irq_setie(1);
}

inline uint32_t transport_get_cmd_len(void)
{
    return expected_cmd_len;
}

inline bool transport_ingestion_done(void)
{
    return (rx_state == RX_COMMAND_READY) || (rx_state == RX_ERROR);
}

uint32_t transport_read_command(void)
{
    if (rx_state == RX_COMMAND_READY)
        receiver_reset();

    // Optional: re-enable RX if you masked it in ISR
    // uint32_t en = uart_ev_enable_read();
    // uart_ev_enable_write(en | UART_EV_RX);

    return rx_code;
}