#include <sys/time.h>
#include <stdint.h>
#include <stddef.h>
#include <platform_interface/tpm_to_platform_interface.h>

// Fill exactly sz bytes or fail. Return 0 on success, non-zero on error.
int wolf_platform_rng_block(unsigned char *out, unsigned int sz)
{
    if (!out || sz == 0)
        return -1;

    uint32_t off = 0;
    while (off < sz)
    {
        int32_t got = _plat__GetEntropy(out + off, (uint32_t)(sz - off));
        if (got < 0)
            return -1; // propagate health/conditioning failure
        if (got == 0)
            return -1; // no progress => fail
        off += (uint32_t)got;
    }
    return 0;
}

/* Minimal stub. TODO: Improve later to read a real hardware timer. */
int gettimeofday(struct timeval *tv, void *tz)
{
    (void)tz;
    if (tv)
    {
        tv->tv_sec = 0;
        tv->tv_usec = 0;
    }
    return 0;
}
