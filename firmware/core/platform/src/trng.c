#include "trng.h"
#include <generated/csr.h>

// NOTE: larger dwell → lower throughput, potentially better entropy.
#ifndef TRNG_DEFAULT_DWELL
#define TRNG_DEFAULT_DWELL 100u
#endif
#ifndef TRNG_DEFAULT_DELAY
#define TRNG_DEFAULT_DELAY 8u
#endif

void trng_init(const trng_cfg_t *cfg)
{
    // Parameters first (safe even if disabled)
    uint32_t dwell = cfg ? cfg->dwell : TRNG_DEFAULT_DWELL;
    uint16_t delay = cfg ? cfg->delay : TRNG_DEFAULT_DELAY;
    uint8_t gang = cfg ? cfg->gang : 1;
    uint8_t auto_en = cfg ? cfg->auto_enable : 1;

    trng_ctl_dwell_write(dwell);
    trng_ctl_delay_write(delay);
    trng_ctl_gang_write(gang);

    if (auto_en)
        trng_ctl_ena_write(1);
}

bool trng_try_read_u32(uint32_t *out)
{
    if (!trng_status_fresh_read())
        return false;

    // Read the word
    uint32_t w = trng_rand_rand_read();

    // ACK/clear “fresh” by writing to rand
    trng_rand_rand_write(0);

    if (out)
        *out = w;
    return true;
}

static inline uint64_t rdcycle(void)
{
    uint64_t c;
    asm volatile("rdcycle %0" : "=r"(c));
    return c;
}

int trng_read_u32_timeout(uint32_t *out, uint64_t timeout_cycles)
{
    if (timeout_cycles == 0)
    {
        // Block forever
        for (;;)
        {
            if (trng_try_read_u32(out))
                return 0;
        }
    }
    else
    {
        uint64_t start = rdcycle();
        for (;;)
        {
            if (trng_try_read_u32(out))
                return 0;
            if ((rdcycle() - start) > timeout_cycles)
                return -1;
        }
    }
}

int trng_read_bytes(uint8_t *out, size_t len)
{
    size_t off = 0;
    while (off < len)
    {
        uint32_t w;
        if (trng_read_u32_timeout(&w, 0) != 0)
            return -1;
        size_t n = (len - off >= 4) ? 4 : (len - off);
        for (size_t i = 0; i < n; ++i)
            out[off + i] = (uint8_t)(w >> (8 * i));
        off += n;
    }
    return 0;
}
