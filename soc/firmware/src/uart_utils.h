#include <stdint.h>

static void uart_send_ack(void);
static void uart_read(volatile uint8_t *dst, uint32_t len);
static void uart_read_chunks(uint8_t *dest, uint16_t total_len);