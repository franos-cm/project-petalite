#ifndef WOLF_USER_SETTINGS_H
#define WOLF_USER_SETTINGS_H

/* Bare-metal, no OS */
#define SINGLE_THREADED
#define NO_FILESYSTEM
#define WOLFSSL_NO_STDIO
#define WOLFSSL_NO_SOCK
#define NO_WRITEV
#define NO_ASN_TIME

/* Make sure timeval is available to callbacks.h */
#include <time.h>
#include <sys/time.h>

/* OpenSSL compat (EVP etc.) but no TLS */
#define OPENSSL_EXTRA
#define OPENSSL_NO_SSL
#define WOLFSSL_CRYPT_ONLY

/* Trim unneeded features that showed up in your build log */
#define NO_DH             /* you don't need DH */
#define WOLFSSL_NO_LIBOQS /* stop pulling port/liboqs */
#define WOLFSSL_NO_ARIA   /* stop port/aria files */

/* Algos you actually want */
#define WOLFSSL_SHA
#define HAVE_AES
#define HAVE_ECC

/* Leave nonblocking off until SP is deliberately configured */
// #define WC_ECC_NONBLOCK

#endif
