#ifndef DILITHIUM_H
#define DILITHIUM_H

#include <stdint.h>
#include "dilithium_sizes.h"
#include "dilithium_utils.h"
#include "uart_utils.h"
#include "shared.h"

void get_seed(volatile uint8_t *seed_buffer);
uintptr_t get_sk_addr(int sk_id, uint8_t sec_level);
int handle_verify(uint8_t sec_level, uint32_t msg_len);
int handle_keygen(uint8_t sec_level);
int handle_sign(uint8_t sec_level, uint32_t msg_len);

#endif // DILITHIUM_H