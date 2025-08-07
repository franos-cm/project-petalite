#ifndef SHARED_H
#define SHARED_H

#include <stdint.h>

#define DILITHIUM_CMD_KEYGEN 0x00
#define DILITHIUM_CMD_VERIFY 0x01
#define DILITHIUM_CMD_SIGN 0x02

#define DILITHIUM_CHUNK_SIZE 256
#define DILITHIUM_MAX_MSG_LEN 8192

// TODO: maybe change byte values here
#define DILITHIUM_SYNC_BYTE 0xB0
#define DILITHIUM_READY_BYTE 0xA0
#define DILITHIUM_START_BYTE 0xAC
#define DILITHIUM_ACK_BYTE 0xCC

typedef struct
{
    uint8_t cmd;      // e.g., 0x02 = SIGN
    uint8_t sec_lvl;  // 2, 3, or 5
    uint32_t msg_len; // total payload length in bytes. TODO: change to 64
} __attribute__((packed)) dilithium_request_t;

typedef struct
{
    uint8_t cmd;        // e.g., 0x02 = SIGN
    uint8_t sec_lvl;    // 2, 3, or 5
    uint8_t rsp_code;   // e.g., 0x0 okay
    uint8_t verify_res; // 1 is okay, 0 is bad, -1 is not applicable
} __attribute__((packed)) dilithium_response_t;

#endif // SHARED_H