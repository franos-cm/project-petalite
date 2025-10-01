#ifndef WOLFSSL_COMPAT_H
#define WOLFSSL_COMPAT_H

/* Provide aliases for token-pasting in TPM macros that expect
 * <HASH>_DIGEST_SIZE after OpenSSL-style remapping (e.g. SHA384 -> wolfSSL_SHA384).
 * Map to the existing wolfCrypt WC_* values.
 */
#ifndef wolfSSL_SHA384_DIGEST_SIZE
#define wolfSSL_SHA384_DIGEST_SIZE WC_SHA384_DIGEST_SIZE
#endif

#ifndef wolfSSL_SHA512_DIGEST_SIZE
#define wolfSSL_SHA512_DIGEST_SIZE WC_SHA512_DIGEST_SIZE
#endif

#ifndef TPM_ALG_wolfSSL_SHA384
#define TPM_ALG_wolfSSL_SHA384 TPM_ALG_SHA384
#endif

#ifndef TPM_ALG_wolfSSL_SHA512
#define TPM_ALG_wolfSSL_SHA512 TPM_ALG_SHA512
#endif

#ifndef OID_PKCS1_wolfSSL_SHA1
#define OID_PKCS1_wolfSSL_SHA1 OID_PKCS1_SHA1
#endif
#ifndef OID_ECDSA_wolfSSL_SHA1
#define OID_ECDSA_wolfSSL_SHA1 OID_ECDSA_SHA1
#endif

#ifndef OID_PKCS1_wolfSSL_SHA256
#define OID_PKCS1_wolfSSL_SHA256 OID_PKCS1_SHA256
#endif
#ifndef OID_ECDSA_wolfSSL_SHA256
#define OID_ECDSA_wolfSSL_SHA256 OID_ECDSA_SHA256
#endif

#ifndef OID_PKCS1_wolfSSL_SHA384
#define OID_PKCS1_wolfSSL_SHA384 OID_PKCS1_SHA384
#endif
#ifndef OID_ECDSA_wolfSSL_SHA384
#define OID_ECDSA_wolfSSL_SHA384 OID_ECDSA_SHA384
#endif

#ifndef OID_PKCS1_wolfSSL_SHA512
#define OID_PKCS1_wolfSSL_SHA512 OID_PKCS1_SHA512
#endif
#ifndef OID_ECDSA_wolfSSL_SHA512
#define OID_ECDSA_wolfSSL_SHA512 OID_ECDSA_SHA512
#endif

#ifndef TPM_WOLFSSL_AES_WRAPPERS
#define TPM_WOLFSSL_AES_WRAPPERS

#include <wolfssl/wolfcrypt/aes.h>
#include <public/BaseTypes.h>

// TODO: revise teh functions below

/* TPM core expects:
 *   void TpmCryptEncryptAES(void*, BYTE*, const BYTE*);
 *   void TpmCryptDecryptAES(void*, BYTE*, const BYTE*);
 * wolfSSL provides int wc_AesEncrypt/Decrypt(Aes*, byte*, const byte*).
 * Wrap them to avoid incompatible function pointer casts (and UB).
 */
static inline void
TpmCryptEncryptAES(void *keySchedule, BYTE *out, const BYTE *in)
{
    (void)wc_AesEncryptDirect((Aes *)keySchedule, out, in); /* discard status */
}

static inline void TpmCryptDecryptAES(void *keySchedule, BYTE *out, const BYTE *in)
{
    (void)wc_AesDecryptDirect((Aes *)keySchedule, out, in); /* discard status */
}
#endif /* TPM_WOLFSSL_AES_WRAPPERS */

#endif /* WOLFSSL_COMPAT_H */