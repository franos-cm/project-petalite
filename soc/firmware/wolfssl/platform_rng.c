#include <stdint.h>
#include <stddef.h>
// #include "TpmToPlatformInterface.h"   /* header you pasted, for _plat__GetEntropy */

/* Fill exactly sz bytes or fail. Return 0 on success, non-zero on error. */
int wolf_platform_rng_block(unsigned char *out, unsigned int sz)
{
    // uint32_t off = 0;
    // while (off < sz) {
    //     /* _plat__GetEntropy returns:
    //        <0  = failure (sticky)
    //        >=0 = number of bytes provided this call (may be less than requested) */
    //     int32_t got = _plat__GetEntropy(out + off, (uint32_t)(sz - off));
    //     if (got < 0) return -1;                 /* propagate hardware failure */
    //     if (got == 0)   return -1;              /* no progress => fail */
    //     off += (uint32_t)got;
    // }
    return 0;
}

// Option A (recommended): point wolfSSL at your HW RNG
// Add this to your user_settings.h (keeps HashDRBG, but uses your seed):
// /* ---- RNG: hardware-backed seed ---- */
// #define HAVE_HASHDRBG                /* keep the default DRBG */
// #define CUSTOM_RAND_TYPE   unsigned int
// /* Provide these in your code (see stubs below) */
// extern unsigned int board_rng_seed32(void);
// #define CUSTOM_RAND_GENERATE board_rng_seed32
// /* If you can return raw bytes too, hook the block generator: */
// extern int board_rng_read_block(unsigned char* out, unsigned int sz);
// #define CUSTOM_RAND_GENERATE_BLOCK board_rng_read_block
// Short answer: Option B (disable wolfSSL’s HashDRBG and feed it straight from your platform entropy) is the better fit for Microsoft’s TPM reference stack.
// Why? The MS TPM code already expects you to provide entropy via _plat__GetEntropy() and it runs its own DRBG internally. If you also keep wolfSSL’s HashDRBG, you end up with two DRBGs to seed/verify/size—more flash, more moving parts, more audit surface. Going “direct” keeps a single source of truth for randomness across the whole device.