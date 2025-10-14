#include "trng.h"
#include "log.h"

static inline uint32_t clamp_bits(uint32_t v, uint8_t sz)
{
    return v & _BF_MASK(sz);
}

static inline void trng_set_ena(bool en)
{
    uint32_t ctl = trng_ctl_read();
    ctl = TRNG_CTL_SET_ENA(ctl, en ? 1u : 0u);
    trng_ctl_write(ctl);
}

void trng_init(const trng_cfg_t *cfg)
{
    const uint32_t dwell = clamp_bits(cfg ? cfg->dwell : TRNG_DEFAULT_DWELL,
                                      CSR_TRNG_CTL_DWELL_SIZE);
    const uint32_t delay = clamp_bits(cfg ? cfg->delay : TRNG_DEFAULT_DELAY,
                                      CSR_TRNG_CTL_DELAY_SIZE);
    const bool gang = cfg ? cfg->gang : true;
    const bool en = cfg ? cfg->auto_enable : true;

    uint32_t ctl = trng_ctl_read();
    ctl = TRNG_CTL_SET_DWELL(ctl, dwell);
    ctl = TRNG_CTL_SET_DELAY(ctl, delay);
    ctl = TRNG_CTL_SET_GANG(ctl, gang ? 1u : 0u);
    ctl = TRNG_CTL_SET_ENA(ctl, en ? 1u : 0u);
    trng_ctl_write(ctl);
}

void trng_enable(void)
{
    trng_set_ena(1);
}

void trng_disable(void)
{
    trng_set_ena(0);
};

void trng_get_cfg(trng_cfg_t *out)
{
    if (!out)
        return;
    const uint32_t ctl = trng_ctl_read();
    out->dwell = TRNG_CTL_GET_DWELL(ctl);
    out->delay = (uint16_t)TRNG_CTL_GET_DELAY(ctl);
    out->gang = TRNG_CTL_GET_GANG(ctl) ? true : false;
    out->auto_enable = TRNG_CTL_GET_ENA(ctl) ? true : false;
}

bool trng_try_read_u32(uint32_t *out)
{
    if (!TRNG_STATUS_FRESH(trng_status_read()))
        return false;

    uint32_t w = trng_rand_read();
    if (out)
        *out = w;
    return true;
}

int trng_read_u32_timeout(uint32_t *out, uint64_t timeout_cycles)
{
    uint64_t start = 0, now;
    if (timeout_cycles)
        asm volatile("rdcycle %0" : "=r"(start));
    for (;;)
    {
        if (trng_try_read_u32(out))
            return 0;
        if (timeout_cycles)
        {
            asm volatile("rdcycle %0" : "=r"(now));
            if ((now - start) > timeout_cycles)
                return -1;
        }
    }
}

uint32_t trng_read_u32(void)
{
    uint32_t w;
    (void)trng_read_u32_timeout(&w, 0);
    return w;
}

int trng_read_bytes(uint8_t *out, size_t len)
{
    size_t off = 0;
    while (off < len)
    {
        const uint32_t w = trng_read_u32();
        const size_t n = (len - off >= 4) ? 4 : (len - off);
        for (size_t i = 0; i < n; ++i)
            out[off + i] = (uint8_t)(w >> (8 * i));
        off += n;
    }
    return 0;
}

void trng_warmup(uint32_t max_count)
{
    uint32_t a = trng_read_u32();
    for (uint32_t i = 0; i < max_count; i++)
    {
        uint32_t b = trng_read_u32();
        while (b == a)
            b = trng_read_u32();
        a = b;
    }
}

// NOTE: these last functions are for debugging and mostly unnecessary
//       also time measurements seem io bound when using logs, so not very trustworthy
//       maybe we should delete these, if we dont use them in the near future
static inline uint32_t popcnt32(uint32_t x)
{
    return __builtin_popcount(x);
}

// Throughput and 1s/0s ratio
void trng_test(uint64_t words_samples)
{
    const uint64_t t0 = log_now_cycles();
    uint64_t ones = 0, words = 0;

    LOGD("TRNG bench start");
    while (words < words_samples)
    {
        uint32_t w = trng_read_u32(); // blocks; read-to-clear
        ones += popcnt32(w);
        words += 1;
    }
    const uint64_t elapsed = log_now_cycles() - t0;
    const uint64_t bits = words * 32ULL;

    // integer throughput (words/s), rounded
    uint64_t wps = elapsed ? (words * (uint64_t)CONFIG_CLOCK_FREQUENCY + elapsed / 2) / elapsed : 0;

    // ratios in basis points (0.01%)
    uint32_t ones_bp = bits ? (uint32_t)((ones * 10000ULL + bits / 2) / bits) : 0;
    uint32_t zeros_bp = 10000u - ones_bp;

    LOGD("words=%llu, bits=%llu, ones=%llu",
         (unsigned long long)words, (unsigned long long)bits, (unsigned long long)ones);
    LOGD("throughput=%llu words/s, ones_ratio=%u.%02u%% (zeros_ratio=%u.%02u%%)",
         (unsigned long long)wps,
         ones_bp / 100, ones_bp % 100,
         zeros_bp / 100, zeros_bp % 100);
    LOGD("TRNG bench end");
}

/* Per-sample timing: prints word + Δcycles + Δµs (integers only) */
void trng_measure_cycles_per_sample(unsigned samples)
{
    LOGD("TRNG: measuring %u samples...", samples);

    while (!TRNG_STATUS_FRESH(trng_status_read()))
        ;
    (void)trng_rand_read(); // clear

    uint64_t t_prev = log_now_cycles();

    for (unsigned i = 0; i < samples; ++i)
    {
        while (!TRNG_STATUS_FRESH(trng_status_read()))
            ;
        uint64_t t_now = log_now_cycles();
        uint32_t w = trng_rand_read();

        uint64_t dt_cyc = t_now - t_prev;
        uint64_t dt_us = (dt_cyc * 1000000ULL + (CONFIG_CLOCK_FREQUENCY / 2)) / CONFIG_CLOCK_FREQUENCY;

        LOGD("sample %03u: 0x%08x  dcyc=%llu  dus=%llu",
             i, w,
             (unsigned long long)dt_cyc,
             (unsigned long long)dt_us);

        t_prev = t_now;
    }
    LOGD("TRNG: measurement done.");
}