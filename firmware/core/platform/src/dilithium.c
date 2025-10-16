#include "dilithium.h"
#include "log.h"

extern uint8_t _dilithium_buffer_start[]; // NOTE: should be 64 bit aligned

static inline size_t align8(size_t x) { return (x + 7) & ~(size_t)7; }

static inline uint32_t get_h_len(uint8_t lvl)
{
    switch (lvl)
    {
    case 2:
        return DILITHIUM_H_LVL2_SIZE;
    case 3:
        return DILITHIUM_H_LVL3_SIZE;
    case 5:
        return DILITHIUM_H_LVL5_SIZE;
    default:
        return -1;
    }
}

static inline uint32_t get_s1_len(uint8_t lvl)
{
    switch (lvl)
    {
    case 2:
        return DILITHIUM_S1_LVL2_SIZE;
    case 3:
        return DILITHIUM_S1_LVL3_SIZE;
    case 5:
        return DILITHIUM_S1_LVL5_SIZE;
    default:
        return -1;
    }
}

static inline uint32_t get_s2_len(uint8_t lvl)
{
    switch (lvl)
    {
    case 2:
        return DILITHIUM_S2_LVL2_SIZE;
    case 3:
        return DILITHIUM_S2_LVL3_SIZE;
    case 5:
        return DILITHIUM_S2_LVL5_SIZE;
    default:
        return -1;
    }
}

static inline uint32_t get_t0_len(uint8_t lvl)
{
    switch (lvl)
    {
    case 2:
        return DILITHIUM_T0_LVL2_SIZE;
    case 3:
        return DILITHIUM_T0_LVL3_SIZE;
    case 5:
        return DILITHIUM_T0_LVL5_SIZE;
    default:
        return -1;
    }
}

static inline uint32_t get_t1_len(uint8_t lvl)
{
    switch (lvl)
    {
    case 2:
        return DILITHIUM_T1_LVL2_SIZE;
    case 3:
        return DILITHIUM_T1_LVL3_SIZE;
    case 5:
        return DILITHIUM_T1_LVL5_SIZE;
    default:
        return -1;
    }
}

static inline uint32_t get_z_len(uint8_t lvl)
{
    switch (lvl)
    {
    case 2:
        return DILITHIUM_Z_LVL2_SIZE;
    case 3:
        return DILITHIUM_Z_LVL3_SIZE;
    case 5:
        return DILITHIUM_Z_LVL5_SIZE;
    default:
        return -1;
    }
}

static inline uint32_t get_sig_len(uint8_t lvl)
{
    return DILITHIUM_C_SIZE + get_z_len(lvl) + get_h_len(lvl);
}

static inline uint32_t get_pk_len(uint8_t lvl)
{
    return (DILITHIUM_RHO_SIZE + get_t1_len(lvl));
}

static inline uint32_t get_sk_len(uint8_t lvl)
{
    return (
        DILITHIUM_RHO_SIZE + DILITHIUM_K_SIZE + DILITHIUM_TR_SIZE + get_s1_len(lvl) + get_s2_len(lvl) + get_t0_len(lvl));
}

static void dilithium_setup(uint8_t op, uint16_t sec_level)
{
    dilithium_mode_write(op);
    dilithium_security_level_write(sec_level);
}

static void dilithium_start(void)
{
    dilithium_start_write(1);
    dilithium_start_write(0);
}

static void dilithium_reset(void)
{
    dilithium_reset_write(1);
    dilithium_start_write(0);
    dilithium_reader_enable_write(0);
    dilithium_writer_enable_write(0);
    dilithium_reset_write(0);
}

// NOTE: since Litex DMA truncates last non-integer transfer, we need to align()
static void dilithium_read_setup(const void *base_ptr, uint32_t length) {
    uint64_t base = (uint64_t)(uintptr_t)base_ptr;
    dilithium_reader_base_write((uint64_t) align8((size_t)base));
    dilithium_reader_length_write((uint32_t) align8((size_t)length));
}

static void dilithium_read_start(void)
{
    dilithium_reader_enable_write(1);
}

static bool dilithium_read_in_progress(void)
{
    if (dilithium_reader_enable_read() && !dilithium_reader_done_read())
    {
        return true;
    }
    else
    {
        dilithium_reader_enable_write(0);
        return false;
    }
}

static void dilithium_read_wait(void)
{
    while (dilithium_read_in_progress())
        ;
}

// NOTE: since Litex DMA truncates last non-integer transfer, we need to align()
static void dilithium_write_setup(void *base_ptr, uint32_t length) {
    uint64_t base = (uint64_t)(uintptr_t)base_ptr;
    dilithium_writer_base_write((uint64_t) align8((size_t)base));
    dilithium_writer_length_write((uint32_t) align8((size_t)length));
}

static void dilithium_write_start(void)
{
    dilithium_writer_enable_write(1);
}

static bool dilithium_write_in_progress(void)
{
    if (dilithium_writer_enable_read() && !dilithium_writer_done_read())
    {
        return true;
    }
    else
    {
        dilithium_writer_enable_write(0);
        return false;
    }
}

static void dilithium_write_wait(void)
{
    while (dilithium_write_in_progress())
        ;
}

// keypair_ptr points to the DMA scratch laid out (64b aligned) as:
//   Rho | K | S1 | S2 | T1 | T0 | TR
// We repack into:
//   pk = (Rho, T1)
//   sk = (Rho, K, TR, S1, S2, T0)
static uint32_t package_keypair(uint8_t  sec_level,
                           uint8_t *keypair_ptr,
                           uint16_t *pk_size, uint8_t *pk_ptr,
                           uint16_t *sk_size, uint8_t *sk_ptr)
{
    // Args checks
    if (!keypair_ptr || !pk_size || !pk_ptr || !sk_size || !sk_ptr) return -1;

    // Useful lengths
    const uint32_t s1_len = get_s1_len(sec_level);
    const uint32_t s2_len = get_s2_len(sec_level);
    const uint32_t t0_len = get_t0_len(sec_level);
    const uint32_t t1_len = get_t1_len(sec_level);
    const uint32_t pk_len = get_pk_len(sec_level);
    const uint32_t sk_len = get_sk_len(sec_level);
    // Length checks
    if (s1_len <= 0 || s2_len <= 0 || t0_len <= 0 || t1_len <= 0) return -1;
    // Capacity checks (*size is capacity on input). TODO: check if thats actually the case
    if ((uint16_t)pk_len > *pk_size) return -2;
    if ((uint16_t)sk_len > *sk_size) return -3;

    // Producer (DMA scratch) layout — 64-bit aligned segments
    uint8_t *rho = keypair_ptr;
    uint8_t *k   = rho + align8(DILITHIUM_RHO_SIZE);
    uint8_t *s1  = k   + align8(DILITHIUM_K_SIZE);
    uint8_t *s2  = s1  + align8((size_t)s1_len);
    uint8_t *t1  = s2  + align8((size_t)s2_len);
    uint8_t *t0  = t1  + align8((size_t)t1_len);
    uint8_t *tr  = t0  + align8((size_t)t0_len);

    // Offsets within packed outputs
    const size_t rho_off = 0;
    const size_t k_off   = rho_off + DILITHIUM_RHO_SIZE;
    const size_t tr_off  = k_off   + DILITHIUM_K_SIZE;
    const size_t s1_off  = tr_off  + DILITHIUM_TR_SIZE;
    const size_t s2_off  = s1_off  + (size_t)s1_len;
    const size_t t0_off  = s2_off  + (size_t)s2_len;
    const size_t t1_off  = rho_off + DILITHIUM_RHO_SIZE;

    // sk = (rho, K, TR, S1, S2, T0)
    memcpy(sk_ptr + rho_off, rho, DILITHIUM_RHO_SIZE);
    memcpy(sk_ptr + k_off,   k,   DILITHIUM_K_SIZE);
    memcpy(sk_ptr + tr_off,  tr,  DILITHIUM_TR_SIZE);
    memcpy(sk_ptr + s1_off,  s1,  (size_t)s1_len);
    memcpy(sk_ptr + s2_off,  s2,  (size_t)s2_len);
    memcpy(sk_ptr + t0_off,  t0,  (size_t)t0_len);
    *sk_size = (uint16_t)sk_len;

    // pk = (rho, T1)
    memcpy(pk_ptr + rho_off, rho, DILITHIUM_RHO_SIZE);
    memcpy(pk_ptr + t1_off,  t1,  (size_t)t1_len);
    *pk_size = (uint16_t)pk_len;

    return 0;
}


void dilithium_init(void)
{
    dilithium_reset();
}

// NOTE: both seed_ptr and keypair_ptr should be 64 bit aligned
uint32_t dilithium_keygen(uint8_t  sec_level, const uint8_t *seed_ptr,
                          uint16_t *pk_size, uint8_t *pk_ptr,      // capacity in, size out
                          uint16_t *sk_size, uint8_t *sk_ptr)      // capacity in, size out
{
    LOGD("Starting keygen...");
    // NOTE: both pk and sk have Rho, but it is only output once by the module, so we subtract it
    uint8_t *keypair_ptr = _dilithium_buffer_start;
    uint32_t keypair_size = get_pk_len(sec_level) + get_sk_len(sec_level) - DILITHIUM_RHO_SIZE;

    // Set Dilithium
    dilithium_reset();
	dilithium_setup(DILITHIUM_CMD_KEYGEN, sec_level);

    // Setup Dilithium DMA
    dilithium_write_setup(keypair_ptr, (uint32_t)keypair_size);
    dilithium_write_start();
    dilithium_read_setup(seed_ptr, (uint32_t)DILITHIUM_SEED_SIZE);
    dilithium_read_start();

    // Start dilithium core and wait for it to finish responding
    LOGD("Starting dilithium core...");
    dilithium_start();
    // Wait for Dilithium to finish
    LOGD("Waiting for dilithium core...");
    dilithium_read_wait();
    dilithium_write_wait();

    LOGD("Keygen done!");
    return package_keypair(sec_level, keypair_ptr, pk_size, pk_ptr, sk_size, sk_ptr);
}