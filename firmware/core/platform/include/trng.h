#pragma once
#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C"
{
#endif

    typedef struct
    {
        uint32_t dwell;      // sysclk cycles to dwell (entropy accumulation)
        uint16_t delay;      // sysclk cycles between merge and sample
        uint8_t gang;        // 1 = enabled, 0 = disabled
        uint8_t auto_enable; // 1 = set ena=1 in init
    } trng_cfg_t;

    // Initialize parameters and (optionally) enable
    void trng_init(const trng_cfg_t *cfg);

    // Turn on/off
    static inline void trng_enable(void) { trng_ctl_ena_write(1); }
    static inline void trng_disable(void) { trng_ctl_ena_write(0); }

    // Non-blocking: returns true if a new word is ready and stores it in *out
    bool trng_try_read_u32(uint32_t *out);

    // Blocking with optional timeout (cycles); timeout=0 => wait forever
    // Returns 0 on success, -1 on timeout
    int trng_read_u32_timeout(uint32_t *out, uint64_t timeout_cycles);

    // Convenience: blocking forever
    static inline uint32_t trng_read_u32(void)
    {
        uint32_t w;
        (void)trng_read_u32_timeout(&w, 0);
        return w;
    }

    // Fill a buffer (blocking). Returns 0 on success.
    int trng_read_bytes(uint8_t *out, size_t len);

#ifdef __cplusplus
}
#endif
