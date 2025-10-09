#pragma once
#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>
#include <generated/csr.h>

/* Bitfield helpers (use generated OFFSETS/SIZES) */
#define _BF_MASK(sz) ((uint32_t)((sz) == 32 ? 0xFFFFFFFFu : ((1u << (sz)) - 1u)))
#define _BF_GET(v, off, sz) (((uint32_t)(v) >> (off)) & _BF_MASK(sz))
#define _BF_SET(v, off, sz, x) ((((uint32_t)(v)) & ~(_BF_MASK(sz) << (off))) | \
                                (((uint32_t)(x) & _BF_MASK(sz)) << (off)))

/* TRNG field helpers */
#define TRNG_CTL_GET_ENA(v) _BF_GET((v), CSR_TRNG_CTL_ENA_OFFSET, CSR_TRNG_CTL_ENA_SIZE)
#define TRNG_CTL_SET_ENA(v, x) _BF_SET((v), CSR_TRNG_CTL_ENA_OFFSET, CSR_TRNG_CTL_ENA_SIZE, (x))
#define TRNG_CTL_GET_GANG(v) _BF_GET((v), CSR_TRNG_CTL_GANG_OFFSET, CSR_TRNG_CTL_GANG_SIZE)
#define TRNG_CTL_SET_GANG(v, x) _BF_SET((v), CSR_TRNG_CTL_GANG_OFFSET, CSR_TRNG_CTL_GANG_SIZE, (x))
#define TRNG_CTL_GET_DWELL(v) _BF_GET((v), CSR_TRNG_CTL_DWELL_OFFSET, CSR_TRNG_CTL_DWELL_SIZE)
#define TRNG_CTL_SET_DWELL(v, x) _BF_SET((v), CSR_TRNG_CTL_DWELL_OFFSET, CSR_TRNG_CTL_DWELL_SIZE, (x))
#define TRNG_CTL_GET_DELAY(v) _BF_GET((v), CSR_TRNG_CTL_DELAY_OFFSET, CSR_TRNG_CTL_DELAY_SIZE)
#define TRNG_CTL_SET_DELAY(v, x) _BF_SET((v), CSR_TRNG_CTL_DELAY_OFFSET, CSR_TRNG_CTL_DELAY_SIZE, (x))
#define TRNG_STATUS_FRESH(v) _BF_GET((v), CSR_TRNG_STATUS_FRESH_OFFSET, CSR_TRNG_STATUS_FRESH_SIZE)

// NOTE: larger dwell → lower throughput, potentially better entropy.
#ifndef TRNG_DEFAULT_DWELL
#define TRNG_DEFAULT_DWELL 100u
#endif
#ifndef TRNG_DEFAULT_DELAY
#define TRNG_DEFAULT_DELAY 8u
#endif

/* Config struct */
typedef struct
{
    uint32_t dwell;   /* 20-bit */
    uint16_t delay;   /* 10-bit */
    bool gang;        /* true/false */
    bool auto_enable; /* true = set ENA=1 */
} trng_cfg_t;

/* API (single init that accepts NULL for defaults) */
void trng_init(const trng_cfg_t *cfg);
void trng_get_cfg(trng_cfg_t *out);
void trng_enable(void);
void trng_disable(void);

bool trng_try_read_u32(uint32_t *out);
int trng_read_u32_timeout(uint32_t *out, uint64_t timeout_cycles);
uint32_t trng_read_u32(void);
int trng_read_bytes(uint8_t *out, size_t len);
void trng_warmup(uint32_t max_count);
// NOTE: these last two are for debugging and mostly unnecessary.
//       also time measurements seem io bound when using logs.
//       Maybe we should just delete these already.
void trng_test(uint64_t words_samples);
void trng_measure_cycles_per_sample(unsigned samples);