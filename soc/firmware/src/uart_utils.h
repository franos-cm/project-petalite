#ifndef UART_UTILS_H
#define UART_UTILS_H

#include <stdint.h>
#include <stdio.h>
#include <libbase/uart.h>
#include <libbase/console.h>
#include "dilithium_utils.h"

dilithium_header_t uart_parse_request_header(void);
void uart_send_ready(void);
void uart_send_ack(void);
void uart_readn(volatile uint8_t *dst, uint32_t total_len, uint32_t ack_group_length);
void uart_send_response(const dilithium_response_t *rsp);

#endif // UART_UTILS_H