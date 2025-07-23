#include <stdint.h>

void uart_send_ack(void);
void uart_readn(volatile uint8_t *dst, uint32_t total_len, uint32_t ack_group_length);
void uart_read_chunks(uint8_t *dest, uint16_t total_len);