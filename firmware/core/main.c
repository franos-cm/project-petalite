#include "transport.h"
#include "platform.h"
#include "run_command.h"

// These includes pull in the data structures. They contain data definitions for the
// various tests.
#include "Tpm.h"
#include "SelfTest.h"
#include "HashTestData.h"

/*
static TPM_RC TestHash(TPM_ALG_ID hashAlg)
{
    debug_breakpoint(0xC0);
    static TPM2B_DIGEST computed; // value computed
    static HMAC_STATE state;
    UINT16 digestSize;
    const TPM2B *testDigest = NULL;
    //    TPM2B_TYPE(HMAC_BLOCK, DEFAULT_TEST_HASH_BLOCK_SIZE);

    pAssert(hashAlg != TPM_ALG_NULL);
#define HASH_CASE_FOR_TEST(HASH, hash)     \
    case ALG_##HASH##_VALUE:               \
        testDigest = &c_##HASH##_digest.b; \
        break;
    switch (hashAlg)
    {
        FOR_EACH_HASH(HASH_CASE_FOR_TEST)

    default:
        FAIL(FATAL_ERROR_INTERNAL);
    }

    // If there is an algorithm without test vectors, then assume that things are OK.
    if (testDigest == NULL || testDigest->size == 0)
        return TPM_RC_SUCCESS;

    // Set the HMAC key to twice the digest size
    digestSize = CryptHashGetDigestSize(hashAlg);
    UINT16 blk = CryptHashGetBlockSize(hashAlg);

    debug_breakpoint(0xC7);                   // marker
    debug_breakpoint((BYTE)(hashAlg & 0xFF)); // low byte
    debug_breakpoint((BYTE)(hashAlg >> 8));   // high byte
    debug_breakpoint(0xC8);
    debug_breakpoint((BYTE)(blk & 0xFF)); // low
    debug_breakpoint((BYTE)(blk >> 8));   // high
    debug_breakpoint(0xC9);
    debug_breakpoint((BYTE)(digestSize & 0xFF)); // low
    debug_breakpoint((BYTE)(digestSize >> 8));   // high

    CryptHmacStart(&state, hashAlg, digestSize * 2, (BYTE *)c_hashTestKey.t.buffer);
    CryptDigestUpdate(&state.hashState,
                      2 * CryptHashGetBlockSize(hashAlg),
                      (BYTE *)c_hashTestData.t.buffer);
    computed.t.size = digestSize;

    debug_breakpoint(0xC1);
    CryptHmacEnd(&state, digestSize, computed.t.buffer);

    debug_breakpoint(0xC2);
    debug_breakpoint((BYTE)(testDigest->size & 0xFF));        // low byte
    debug_breakpoint((BYTE)((testDigest->size >> 8) & 0xFF)); // high byte

    debug_breakpoint(0xC3);
    debug_breakpoint((BYTE)(computed.t.size & 0xFF));        // low byte
    debug_breakpoint((BYTE)((computed.t.size >> 8) & 0xFF)); // high byte

    debug_breakpoint(0xC4);
    int res = memcmp(testDigest->buffer, computed.t.buffer, computed.b.size);
    debug_breakpoint((BYTE)(res & 0xFF));        // low byte
    debug_breakpoint((BYTE)((res >> 8) & 0xFF)); // high byte

    if ((testDigest->size != computed.t.size) || (res != 0))
    {
        // TODO: problem is here
        debug_breakpoint(0xC5);
        SELF_TEST_FAILURE;
    }
    debug_breakpoint(0xC6);
    return TPM_RC_SUCCESS;
}
*/

int main(void)
{
    transport_irq_init();
    // debug_breakpoint(0x00);
    // (void)TestHash(TPM_ALG_SHA256); // Debug
    // debug_breakpoint(0xFD);
    // debug_breakpoint(0xFE);
    platform_cold_boot();

    _debug_transport_write_ready();

    for (;;)
    {
        if (transport_ingestion_done())
        {
            uint32_t cmd_len = transport_get_cmd_len();
            uint32_t cmd_read_error = transport_read_command();

            if (!cmd_read_error)
            {
                uint32_t resp_len = (uint32_t)sizeof(tpm_cmd_buf);
                uint8_t *resp_ptr = tpm_cmd_buf;

                // Optionally pause RX/IRQs so the ingress path can't stomp the buffer
                // receiver_pause();
                debug_breakpoint(0xFF);
                _plat__RunCommand(cmd_len, tpm_cmd_buf, &resp_len, &resp_ptr);
                debug_breakpoint(0xFD);
                debug_breakpoint(0xFE);

                _debug_transport_write_ready();
                transport_write_rsp(resp_ptr, resp_len);

                // Now send exactly resp_len bytes
                // receiver_resume();
            }
            else
            {
                ;
            }
        }
        // Optional: low-power wait
        // asm volatile("wfi");
    }
}