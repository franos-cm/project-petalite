#include "dilithium.h"
#include "log.h"

extern uint8_t _dilithium_buffer_start[]; // NOTE: should be 64 bit aligned

static inline size_t align8(size_t x) { return (x + 7) & ~(size_t)7; }

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

static void dilithium_setup(uint8_t op, uint8_t sec_level)
{
    dilithium_mode_write((uint32_t)op);
    dilithium_security_level_write((uint32_t)sec_level);
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
static void dilithium_read_setup(const void *base_ptr, uint32_t length)
{
    uint64_t base = (uint64_t)(uintptr_t)base_ptr;
    dilithium_reader_base_write((uint64_t)align8((size_t)base));
    dilithium_reader_length_write((uint32_t)align8((size_t)length));
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
static void dilithium_write_setup(void *base_ptr, uint32_t length)
{
    uint64_t base = (uint64_t)(uintptr_t)base_ptr;
    dilithium_writer_base_write((uint64_t)align8((size_t)base));
    dilithium_writer_length_write((uint32_t)align8((size_t)length));
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

// keypair points to the DMA scratch laid out (64b aligned) as:
//   Rho | K | S1 | S2 | T1 | T0 | TR
// We repack into (not 64b aligned):
//   pk = (Rho | T1), sk = (Rho | K | TR | S1 | S2 | T0)
static uint32_t pack_keypair(uint8_t sec_level,
                             uint8_t *keypair_addr,
                             uint8_t *pk, uint16_t *pk_size,
                             uint8_t *sk, uint16_t *sk_size)
{
    // Args checks
    if (!keypair_addr || !pk_size || !pk || !sk_size || !sk)
        return -1;

    // Useful lengths
    const uint32_t s1_len = get_s1_len(sec_level);
    const uint32_t s2_len = get_s2_len(sec_level);
    const uint32_t t0_len = get_t0_len(sec_level);
    const uint32_t t1_len = get_t1_len(sec_level);
    const uint32_t pk_len = get_pk_len(sec_level);
    const uint32_t sk_len = get_sk_len(sec_level);
    // Length checks
    if (s1_len <= 0 || s2_len <= 0 || t0_len <= 0 || t1_len <= 0)
        return -1;
    // Capacity checks (*size is capacity on input). TODO: check if thats actually the case
    if ((uint16_t)pk_len > *pk_size)
        return -2;
    if ((uint16_t)sk_len > *sk_size)
        return -3;

    // Producer (DMA scratch) layout — 64-bit aligned segments
    uint8_t *rho = keypair_addr;
    uint8_t *k = rho + align8(DILITHIUM_RHO_SIZE);
    uint8_t *s1 = k + align8(DILITHIUM_K_SIZE);
    uint8_t *s2 = s1 + align8((size_t)s1_len);
    uint8_t *t1 = s2 + align8((size_t)s2_len);
    uint8_t *t0 = t1 + align8((size_t)t1_len);
    uint8_t *tr = t0 + align8((size_t)t0_len);

    // Offsets within packed outputs
    const size_t rho_off = 0;
    const size_t k_off = rho_off + DILITHIUM_RHO_SIZE;
    const size_t tr_off = k_off + DILITHIUM_K_SIZE;
    const size_t s1_off = tr_off + DILITHIUM_TR_SIZE;
    const size_t s2_off = s1_off + (size_t)s1_len;
    const size_t t0_off = s2_off + (size_t)s2_len;
    const size_t t1_off = rho_off + DILITHIUM_RHO_SIZE;

    // sk = (rho, K, TR, S1, S2, T0)
    memcpy(sk + rho_off, rho, DILITHIUM_RHO_SIZE);
    memcpy(sk + k_off, k, DILITHIUM_K_SIZE);
    memcpy(sk + tr_off, tr, DILITHIUM_TR_SIZE);
    memcpy(sk + s1_off, s1, (size_t)s1_len);
    memcpy(sk + s2_off, s2, (size_t)s2_len);
    memcpy(sk + t0_off, t0, (size_t)t0_len);
    *sk_size = (uint16_t)sk_len;

    // pk = (rho, T1)
    memcpy(pk + rho_off, rho, DILITHIUM_RHO_SIZE);
    memcpy(pk + t1_off, t1, (size_t)t1_len);
    *pk_size = (uint16_t)pk_len;

    return 0;
}

// sig_addr points to the DMA scratch laid out (64b aligned) as:
//   z | h | c
// We repack into (not 64b aligned):
//   sig = (c | z | h)
static uint32_t pack_sig(uint8_t sec_level, uint8_t *sig_addr,
                         uint8_t *packed_sig, uint16_t *packed_sig_size)
{
    // Useful lengths
    const uint32_t z_len = get_z_len(sec_level);
    const uint32_t h_len = get_h_len(sec_level);
    const uint32_t sig_len = DILITHIUM_C_SIZE + z_len + h_len;
    // Length checks
    if (z_len <= 0 || h_len <= 0)
        return -1;

    // Producer (DMA scratch) layout — 64-bit aligned segments
    uint8_t *z = sig_addr;
    uint8_t *h = z + align8(z_len);
    uint8_t *c = h + align8(h_len);

    // Offsets within packed outputs
    const size_t c_off = 0;
    const size_t z_off = c_off + DILITHIUM_C_SIZE;
    const size_t h_off = z_off + (size_t)z_len;

    // sk = (rho, K, TR, S1, S2, T0)
    memcpy(packed_sig + c_off, c, DILITHIUM_C_SIZE);
    memcpy(packed_sig + z_off, z, (size_t)z_len);
    memcpy(packed_sig + h_off, h, (size_t)h_len);
    *packed_sig_size = (uint16_t)sig_len;

    return 0;
}

inline uint32_t get_h_len(uint8_t lvl)
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

inline uint32_t get_z_len(uint8_t lvl)
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

void dilithium_init(void)
{
    dilithium_reset();
}

// NOTE: msg_chunk should be 64 bit aligned
uint32_t dilithium_update(const uint8_t *msg_chunk, uint16_t msg_chunk_size)
{
    LOGD("Starting Update op...");
    // Wait for previous dilithium op to end, assuming it hasnt
    LOGD("Waiting for previous msg ingestion to finish...");
    dilithium_read_wait();
    // Feed message chunk into Dilithium core
    dilithium_read_setup(msg_chunk, msg_chunk_size);
    dilithium_read_start();

    LOGD("Update done!");
    return 0;
}

// NOTE: seed should be 64 bit aligned
uint32_t dilithium_keygen(uint8_t sec_level, const uint8_t *seed,
                          uint8_t *pk, uint16_t *pk_size,
                          uint8_t *sk, uint16_t *sk_size)
{
    LOGD("Starting Keygen op...");
    // NOTE: both pk and sk have Rho, but it is only output once by the module, so we subtract it
    uint8_t *keypair_addr = _dilithium_buffer_start;
    uint32_t keypair_size = get_pk_len(sec_level) + get_sk_len(sec_level) - DILITHIUM_RHO_SIZE;

    // Set Dilithium
    dilithium_setup(DILITHIUM_CMD_KEYGEN, sec_level);
    dilithium_reset();

    // Setup Dilithium DMA
    dilithium_write_setup(keypair_addr, (uint32_t)keypair_size);
    dilithium_write_start();
    dilithium_read_setup(seed, (uint32_t)DILITHIUM_SEED_SIZE);
    dilithium_read_start();

    // Start dilithium core and wait for it to finish responding
    dilithium_start();
    dilithium_read_wait();
    dilithium_write_wait();

    LOGD("Keygen done!");
    return pack_keypair(sec_level, keypair_addr, pk, pk_size, sk, sk_size);
}

uint32_t dilithium_sign_start(uint8_t sec_level, uint32_t message_size,
                              const uint8_t *sk, uint16_t sk_size)
{
    LOGD("Starting Sign Start op...");
    (void)sk_size; // Unecessary arg
    // For the first part of the sign operation, we just feed the core part of the sk
    // This is due to the specific order in which the core ingests the data.
    // Our sk is packaged as (rho | K | TR | S1 | S2 | T0), and we first need (rho | TR)
    const uint8_t *rho = sk;
    const uint8_t *tr = rho + DILITHIUM_RHO_SIZE + DILITHIUM_K_SIZE;
    // mlen is required by the core to be a 64-bit big-endian
    uint64_t mlen = __builtin_bswap64((uint64_t)message_size);

    // Write 64-bit aligned values to scratchpad
    uint8_t *input_payload_addr = _dilithium_buffer_start;
    const size_t rho_off = 0;
    const size_t mlen_off = rho_off + align8(DILITHIUM_RHO_SIZE);
    const size_t tr_off = mlen_off + align8(DILITHIUM_CORE_MLEN_SIZE);
    memcpy(input_payload_addr + rho_off, rho, DILITHIUM_RHO_SIZE);
    memcpy(input_payload_addr + mlen_off, &mlen, DILITHIUM_CORE_MLEN_SIZE);
    memcpy(input_payload_addr + tr_off, tr, DILITHIUM_TR_SIZE);

    // Ready Dilithium
    dilithium_setup(DILITHIUM_CMD_SIGN, sec_level);
    dilithium_reset();

    // DMA setup: we dont need to have Dilithium write to memory yet
    // since in the specific case of our core, the result is stored in a private buffer.
    // But we could already start it, depending on the latency.
    const size_t payload_size = tr_off + align8(DILITHIUM_TR_SIZE);
    dilithium_read_setup(input_payload_addr, payload_size);
    dilithium_read_start();

    // Start dilithium core, and we dont need to wait for it to finish reading (for now)
    // TODO: maybe we should wait for the read to finish, and then erase the sk from the buffer.
    //       I think this would be mostly done as a precaution, but in practice, sk already exists elsewhere...
    dilithium_start();

    LOGD("Sign Start done!");
    return 0;
}

uint32_t dilithium_sign_finish(uint8_t sec_level,
                               const uint8_t *sk, uint16_t sk_size,
                               uint8_t *sig, uint16_t *sig_size)
{
    LOGD("Starting Sign Finish op...");
    (void)sk_size; // Unecessary arg
    // For the last part of the sign operation, we just feed the core the rest of the sk
    // Again, our sk is packaged as (rho | K | TR | S1 | S2 | T0), and we now need (K | S1 | S2 | T0)
    const uint32_t s1_len = get_s1_len(sec_level);
    const uint32_t s2_len = get_s2_len(sec_level);
    const uint32_t t0_len = get_t0_len(sec_level);
    const uint32_t sig_len = get_sig_len(sec_level);
    // Capacity checks (*size is capacity on input).
    if ((uint16_t)sig_len > *sig_size)
        return -2;

    const uint8_t *k = sk + DILITHIUM_RHO_SIZE;
    const uint8_t *s1 = k + DILITHIUM_K_SIZE + DILITHIUM_TR_SIZE;
    const uint8_t *s2 = s1 + s1_len;
    const uint8_t *t0 = s2 + s2_len;

    // Write 64-bit aligned values to scratchpad
    uint8_t *input_payload_addr = _dilithium_buffer_start;
    const size_t k_off = 0;
    const size_t s1_off = k_off + align8(DILITHIUM_K_SIZE);
    const size_t s2_off = s1_off + align8(s1_len);
    const size_t t0_off = s2_off + align8(s2_len);
    const size_t input_payload_size = t0_off + align8(t0_len);

    // Prepare sig to be also written onto scratchpad
    uint8_t *output_payload_addr = _dilithium_buffer_start + input_payload_size;
    dilithium_write_setup(output_payload_addr, sig_len);
    dilithium_write_start();

    // Copy input payload onto positions
    memcpy(input_payload_addr + k_off, k, DILITHIUM_K_SIZE);
    memcpy(input_payload_addr + s1_off, s1, s1_len);
    memcpy(input_payload_addr + s2_off, s2, s2_len);
    memcpy(input_payload_addr + t0_off, t0, t0_len);

    // Wait for previous dilithium op to end, assuming it hasnt
    LOGD("Waiting for last message ingestion to finish...");
    dilithium_read_wait();
    // Read the rest of the sk into the dilithium core
    dilithium_read_setup(input_payload_addr, input_payload_size);
    dilithium_read_start();

    // Wait for both reading to end
    dilithium_read_wait();
    // Once reading is finished, we can start wiping the sk off the scratch buffer
    for (size_t i = 0; i < input_payload_size; i++)
        ((volatile uint8_t *)input_payload_addr)[i] = 0;
    // Then wait for writing to end, if it hasnt
    dilithium_write_wait();

    LOGD("Sign Finish done!");
    return pack_sig(sec_level, output_payload_addr, sig, sig_size);
}

uint32_t dilithium_verify_start(uint8_t sec_level, uint32_t message_size,
                                const uint8_t *pk, uint16_t pk_size,
                                const uint8_t *sig, uint16_t sig_size)
{
    LOGD("Starting Verify Start op...");
    // Unecessary args
    (void)pk_size;
    (void)sig_size;
    // For the first part of the sign operation, we just feed the core the pk,
    // and part of the sig. Specifically we send in (rho | c | z | t1 | mlen)
    const uint32_t z_len = get_z_len(sec_level);
    const uint32_t t1_len = get_t1_len(sec_level);
    const uint8_t *rho = pk;
    const uint8_t *t1 = rho + DILITHIUM_RHO_SIZE;
    const uint8_t *c = sig;
    const uint8_t *z = c + DILITHIUM_C_SIZE;
    // mlen is required by the core to be a 64-bit big-endian
    uint64_t mlen = __builtin_bswap64((uint64_t)message_size);

    // Write 64-bit aligned values to scratchpad
    uint8_t *input_payload_addr = _dilithium_buffer_start;
    const size_t rho_off = 0;
    const size_t c_off = rho_off + align8(DILITHIUM_RHO_SIZE);
    const size_t z_off = c_off + align8(DILITHIUM_C_SIZE);
    const size_t t1_off = z_off + align8(z_len);
    const size_t mlen_off = t1_off + align8(t1_len);
    memcpy(input_payload_addr + rho_off, rho, DILITHIUM_RHO_SIZE);
    memcpy(input_payload_addr + c_off, c, DILITHIUM_C_SIZE);
    memcpy(input_payload_addr + z_off, z, z_len);
    memcpy(input_payload_addr + t1_off, t1, t1_len);
    memcpy(input_payload_addr + mlen_off, &mlen, DILITHIUM_CORE_MLEN_SIZE);

    // Ready Dilithium
    dilithium_setup(DILITHIUM_CMD_VERIFY, sec_level);
    dilithium_reset();

    // DMA setup: we dont need to have Dilithium write to memory yet
    const size_t payload_size = mlen_off + align8(DILITHIUM_CORE_MLEN_SIZE);
    dilithium_read_setup(input_payload_addr, payload_size);
    dilithium_read_start();

    // Start dilithium core, and we dont need to wait for it to finish reading (for now)
    dilithium_start();

    LOGD("Verify Start done!");
    return 0;
}

uint32_t dilithium_verify_finish(uint8_t sec_level, const uint8_t *h, uint16_t h_size, bool *accepted)
{
    LOGD("Starting Verify Finish op...");
    // Unecessary args
    (void)h_size;
    // For the last part of the verify operation, we just feed the core the h part of the sig
    const uint32_t h_len = get_h_len(sec_level);
    if (!h_len)
        return -1;

    // Prepare result to be also written onto scratchpad
    uint8_t *output_payload_addr = _dilithium_buffer_start;
    dilithium_write_setup(output_payload_addr, sizeof(uint64_t));
    dilithium_write_start();

    // Wait for previous dilithium op to end, assuming it hasnt
    LOGD("Waiting for last message ingestion to finish...");
    dilithium_read_wait();
    // Read the rest of the sk into the dilithium core
    dilithium_read_setup(h, h_len);
    dilithium_read_start();

    // Wait for both reading and writing to end
    LOGD("Waiting for h read to finish...");
    dilithium_read_wait();
    LOGD("Waiting for verify write to finish...");
    dilithium_write_wait();

    // In this core, 1 encodes failure, 0 encodes acceptance
    uint64_t verify_result = *((volatile uint64_t *)output_payload_addr);
    LOGD("Verify Finish done, result was: %" PRIu64, verify_result);
    *accepted = !((bool)verify_result);
    return 0;
}