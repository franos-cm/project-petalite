#ifndef DILITHIUM_UTILS_H
#define DILITHIUM_UTILS_H

#include <stdint.h>
#include <stdbool.h>
#include <generated/csr.h>
#include "uart_utils.h"
#include "shared.h"

int invalid_header(dilithium_request_t *dh);
void dilithium_init(void);
void dilithium_setup(uint8_t op, uint16_t sec_level);
void dilithium_start(void);
void dilithium_reset(void);
void dilithium_read_setup(uint64_t base_addr, uint32_t length);
void dilithium_read_start(void);
void dilithium_read_wait(void);
bool dilithium_read_in_progress(void);
void dilithium_write_setup(uint64_t base_addr, uint32_t length);
void dilithium_write_start(void);
void dilithium_write_wait(void);
bool dilithium_write_in_progress(void);
void dilithium_read_msg_in_chunks(uint32_t msg_len, uintptr_t msg_chunk_addr);
uint32_t align8(uint32_t x);

#endif // DILITHIUM_UTILS_H