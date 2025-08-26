#include "parser.h"

int inline parse_and_dispatch(uint8_t *buf)
{
    tpm_cmd_header_t header = {be16(buf), be32(buf + 2), be32(buf + 6)};
    switch (header.cc)
    {
    case TPM_CC_Startup:
        return do_startup(header);
    case TPM_CC_GetRandom:
        return do_getrandom(header);
    case TPM_CC_CreatePrimary:
        return do_createprimary(header);
    case TPM_CC_LoadExternal:
        return do_loadexternal(header);
    case TPM_CC_Sign:
        return do_sign(header);
    case TPM_CC_VerifySignature:
        return do_verifysign(header);
    case TPM_CC_ReadPublic:
        return do_readpublic(header);
    case TPM_CC_FlushContext:
        return do_flush(header);
    default:
        return 0;
        // return TPM_RC_COMMAND_CODE;
    }
}