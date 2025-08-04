#ifndef UART_UTILS_H
#define UART_UTILS_H

#include <stdint.h>
#include <libbase/uart.h>
#include "dilithium_utils.h"

#define BASE_ACK_GROUP_LENGTH 64
#define UART_OK 0
#define UART_ERR_INVALID_ARGS -1

dilithium_request_t uart_parse_request_header(void);
void uart_send_ready(void);
void uart_send_ack(void);
void uart_send_start(void);
int uart_readn(volatile uint8_t *dst, uint32_t total_len, uint32_t ack_group_length);
int uart_sendn(volatile uint8_t *src, uint32_t total_len, uint32_t ack_group_length);
void uart_wait_for_ack(void);
void uart_transmission_handshake(void);
void uart_send_response(const dilithium_response_t *rsp);

#endif // UART_UTILS_H