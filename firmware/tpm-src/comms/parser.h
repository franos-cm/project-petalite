#ifndef PARSER_H
#define PARSER_H

#include <stdint.h>
#include "shared.h"

enum TPM_CC
{
    TPM_CC_Startup = (uint32_t)0x00000144,
    TPM_CC_Shutdown = (uint32_t)0x00000145,
    TPM_CC_CreatePrimary = (uint32_t)0x00000131,
    TPM_CC_LoadExternal = (uint32_t)0x00000167,
    TPM_CC_ReadPublic = (uint32_t)0x00000173,
    TPM_CC_Sign = (uint32_t)0x0000015D,
    TPM_CC_VerifySignature = (uint32_t)0x00000177,
    TPM_CC_FlushContext = (uint32_t)0x00000165,
    TPM_CC_GetCapability = (uint32_t)0x0000017A,
    TPM_CC_GetRandom = (uint32_t)0x0000017B,
};

int parse_and_dispatch(uint8_t *buf);

#endif // PARSER_H