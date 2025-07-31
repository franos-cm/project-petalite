#ifndef DILITHIUM_H
#define DILITHIUM_H

#include <stdint.h>
#include <stdio.h>
#include <libbase/uart.h>
#include <libbase/console.h>
#include "dilithium_sizes.h"
#include "dilithium_utils.h"
#include "uart_utils.h"

int handle_verify(uint8_t sec_level, uint32_t msg_len);
int handle_keygen(uint8_t sec_level);
void get_seed(volatile uint8_t *seed_buffer);
uint32_t align8(uint32_t x);

#endif // DILITHIUM_H