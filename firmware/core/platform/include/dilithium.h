#pragma once
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <generated/csr.h>

// NOTE: start of any read or write from dilithium must be 64 bit aligned.
// TODO: check that that is the case

#define DILITHIUM_H_LVL2_SIZE 84
#define DILITHIUM_H_LVL3_SIZE 61
#define DILITHIUM_H_LVL5_SIZE 83

#define DILITHIUM_S1_LVL2_SIZE 384
#define DILITHIUM_S1_LVL3_SIZE 640
#define DILITHIUM_S1_LVL5_SIZE 672

#define DILITHIUM_S2_LVL2_SIZE 384
#define DILITHIUM_S2_LVL3_SIZE 768
#define DILITHIUM_S2_LVL5_SIZE 768

#define DILITHIUM_T0_LVL2_SIZE 1664
#define DILITHIUM_T0_LVL3_SIZE 2496
#define DILITHIUM_T0_LVL5_SIZE 3328

#define DILITHIUM_T1_LVL2_SIZE 1280
#define DILITHIUM_T1_LVL3_SIZE 1920
#define DILITHIUM_T1_LVL5_SIZE 2560

#define DILITHIUM_Z_LVL2_SIZE 2304
#define DILITHIUM_Z_LVL3_SIZE 3200
#define DILITHIUM_Z_LVL5_SIZE 4480

#define DILITHIUM_SEED_SIZE 32
#define DILITHIUM_K_SIZE 32
#define DILITHIUM_RHO_SIZE 32
#define DILITHIUM_TR_SIZE 32
#define DILITHIUM_C_SIZE 32

#define DILITHIUM_CMD_KEYGEN 0
#define DILITHIUM_CMD_VERIFY 1
#define DILITHIUM_CMD_SIGN 2

void dilithium_init(void);
uint32_t dilithium_keygen(uint8_t sec_level, const uint8_t *seed_ptr,
                          uint16_t *pk_size, uint8_t *pk_ptr,
                          uint16_t *sk_size, uint8_t *sk_ptr);
