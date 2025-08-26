#ifndef SHARED_H
#define SHARED_H

#include <stdint.h>

typedef struct
{
    uint16_t tag;  // be16
    uint32_t size; // be32
    uint32_t cc;   // be32
} tpm_cmd_header_t;

uint16_t be16(const uint8_t *p);
uint32_t be32(const uint8_t *p);

#endif // SHARED_H