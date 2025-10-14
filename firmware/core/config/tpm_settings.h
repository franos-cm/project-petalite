#pragma once

// Flag for non-debug build
#define NDEBUG

// Flags related to entropy.
/* Enable SHA-256 conditioner (2:1). Default OFF.
 * 0 = disabled -> raw TRNG bytes with continuous test
 * 1 = enabled  -> 64 bytes TRNG in, 32 bytes SHA-256 out
 */
#ifndef PLAT_ENTROPY_CONDITION_SHA256
#define PLAT_ENTROPY_CONDITION_SHA256 1
#endif

/* Bytes of TRNG per 32 bytes of conditioned output. */
#ifndef PLAT_ENTROPY_CONDITION_IN_PER_OUT32
#define PLAT_ENTROPY_CONDITION_IN_PER_OUT32 64
#endif
