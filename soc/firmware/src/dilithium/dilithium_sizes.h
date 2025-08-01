#ifndef DILITHIUM_SIZES_H
#define DILITHIUM_SIZES_H

#include <stdint.h>

// TODO: change these if used
#define DILITHIUM_SIG_LVL2_SIZE 0x5000
#define DILITHIUM_SIG_LVL3_SIZE 0x5000
#define DILITHIUM_SIG_LVL5_SIZE 0x5000

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

int get_sig_len(uint8_t lvl);
int get_pk_len(uint8_t lvl);
int get_sk_len(uint8_t lvl);
int get_z_len(uint8_t lvl);
int get_t1_len(uint8_t lvl);
int get_t0_len(uint8_t lvl);
int get_h_len(uint8_t lvl);
int get_s1_len(uint8_t lvl);
int get_s2_len(uint8_t lvl);

#endif // DILITHIUM_SIZES_H