/* user_settings.h – rv64 bare-metal, crypto-only, OpenSSL compat
 *
 * Flip the PROFILE_* gates to change feature sets quickly.
 */
#ifndef WOLF_USER_SETTINGS_H
#define WOLF_USER_SETTINGS_H

#ifdef __cplusplus
extern "C"
{
#endif

/* ============================================================
 * Choose a profile
 * ============================================================ */
#if 1
#define PROFILE_OPENSSL_FULL_CRYPTO /* “complete” EVP/EC/BN/SHA/AES */
#else
#define PROFILE_TINY_CRYPTO /* minimal later */
#endif

/* ============================================================
 * Platform / toolchain (safe for bare-metal rv64)
 * ============================================================ */
#define SINGLE_THREADED
#define NO_FILESYSTEM
#define WOLFSSL_NO_STDIO
#define WOLFSSL_NO_SOCK
#define NO_WRITEV
#define NO_DEV_RANDOM /* no /dev/random on bare-metal */
#define NO_MAIN_DRIVER

#define TARGET_EMBEDDED /* match wolf template style */
#define WOLFSSL_SMALL_STACK
#define SIZEOF_LONG_LONG 8
#define WOLFSSL_GENERAL_ALIGNMENT 8 /* rv64: align to 8 for safety */

/* Keep timeval available to callbacks.h */
#include <time.h>
#include <sys/time.h>

/* ============================================================
 * Common (both profiles): OpenSSL compatibility, no TLS
 * ============================================================ */
// !defined(OPENSSL_COEXIST) && (defined(OPENSSL_EXTRA)
#define OPENSSL_EXTRA
#define OPENSSL_ALL
#define OPENSSL_NO_SSL
#define WOLFSSL_CRYPT_ONLY
#define WOLFCRYPT_ONLY
#define NO_WOLFSSL_CLIENT
#define NO_WOLFSSL_SERVER

/* ============================================================
 * Math backend (good for rv64 without asm)
 * ============================================================ */
#ifndef USE_FAST_MATH
#define USE_FAST_MATH 1
#endif

/* Force TFM, disable SP math */
#undef WOLFSSL_SP
#undef WOLFSSL_SP_MATH

/* If you do very large RSA, consider setting FP_MAX_BITS, otherwise default is fine */
// Needed for some tpm features
#define WOLFSSL_KEY_GEN

/* Harden against side-channel attacks */
#define WC_RSA_BLINDING      /* Protects RSA private keys from timing attacks */
#define TFM_TIMING_RESISTANT /* For the Fast Math library */
#define ECC_TIMING_RESISTANT /* For the Elliptic Curve library */

/* ============================================================
 * Profile A: OPENSSL_FULL_CRYPTO
 * Goal: broad EVP coverage w/o TLS. Larger, but “complete” for
 * the headers you listed.
 * ============================================================ */
#ifdef PROFILE_OPENSSL_FULL_CRYPTO

/* --- Public-key --- */
#undef NO_RSA
#undef NO_DH
/* Curves: enable the common set so EC/BN are “complete” */
#define ECC_USER_CURVES
#define HAVE_ECC
/* If you need 192/224 as well, add HAVE_ECC192/HAVE_ECC224 */

/* --- Symmetric / AEAD --- */
#define HAVE_AES
#define HAVE_AES_ECB
#define HAVE_AES_CBC
#define WOLFSSL_AES_DIRECT
#define WOLFSSL_AES_COUNTER /* AES-CTR */
#define HAVE_AESGCM
#define HAVE_AESCCM
#define HAVE_CHACHA
#define HAVE_POLY1305
#define HAVE_ONE_TIME_AUTH /* required by Poly1305 */

/* --- Hash / MAC / KDF --- */
#undef NO_SHA    /* enable SHA-1 for EVP completeness */
#undef NO_SHA256 /* SHA-224/256 */
#define WOLFSSL_SHA224
#define WOLFSSL_SHA512
#define WOLFSSL_SHA384
/* Enable SHA-3 only if you really need it */
/* #define WOLFSSL_SHA3 */
#undef NO_MD5 /* MD5 is often present in EVP suites */
#define HAVE_HKDF
#define WOLFSSL_CMAC

/* --- ASN.1 / X.509 helpers (no TLS) --- */
/* Keep ASN.1 on so you can parse/load PEM/DER keys if needed. */
#undef NO_ASN_TIME /* leave time parsing on if loading certs */
    /* If you never parse certificates/keys, you may later define NO_CERTS. */

    /* --- Debug / strings (leave on while integrating) --- */
    /* #define NO_ERROR_STRINGS */

    /* --- Inline / size trade --- */
    /* #define NO_INLINE */ /* ~1 KB smaller, slightly slower */

#endif /* PROFILE_OPENSSL_FULL_CRYPTO */

/* ============================================================
 * Profile B: TINY_CRYPTO (future size-trim)
 * ============================================================ */
#ifdef PROFILE_TINY_CRYPTO

/* Disable what you don’t need */
#define NO_RSA
#define NO_DSA
#define NO_DH
#define NO_DES3
#define NO_RC4
#define NO_MD4
#define NO_MD5
#define NO_PWDBASED
#define NO_CERTS /* no X.509/ASN.1 parsing */
#define NO_ASN_TIME

/* ECC only P-256 */
#define HAVE_ECC
#define ECC_USER_CURVES
#undef NO_ECC256
#define NO_ECC384
#define NO_ECC521

/* AES minimal modes you actually call */
#define HAVE_AES
#define HAVE_AES_CBC
/* #define WOLFSSL_AES_COUNTER */ /* add if you need CTR */
/* No GCM/CCM unless used */
/* #define HAVE_AESGCM */
/* #define HAVE_AESCCM */

/* Hash only SHA-256 */
#define NO_SHA   /* disable SHA-1 */
#undef NO_SHA256 /* keep SHA-256 */
#undef WOLFSSL_SHA512
#undef WOLFSSL_SHA384
#undef WOLFSSL_SHA3

/* Chacha/Poly disabled unless required */
/* #define HAVE_CHACHA */
/* #define HAVE_POLY1305 */

/* Tighten size */
#define NO_ERROR_STRINGS
#define NO_INLINE
#define NO_WOLFSSL_MEMORY

#ifndef WOLFSSL_IGNORE_FILE_WARN
#define WOLFSSL_IGNORE_FILE_WARN
#endif

#endif /* PROFILE_TINY_CRYPTO */

    /* ============================================================
     * RNG: default HashDRBG is fine; seed it from your platform.
     * For HW RNG, plug a seed: CUSTOM_RAND_GENERATE or _BLOCK.
     * ============================================================ */
    /* #define HAVE_HASHDRBG */ /* implied by default; keep it */

/* RNG: use platform entropy directly (no HashDRBG in wolfSSL) */
#undef HAVE_HASHDRBG
#define WC_NO_HASHDRBG

    /* Declare the block generator we’ll implement */
    int wolf_platform_rng_block(unsigned char *out, unsigned int sz);

/* Point wolfSSL at it */
#define CUSTOM_RAND_GENERATE_BLOCK wolf_platform_rng_block

#ifdef __cplusplus
}
#endif
#endif /* WOLF_USER_SETTINGS_H */
