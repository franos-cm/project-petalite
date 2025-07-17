#include <stdint.h>

#define DILITHIUM_CMD_KEYGEN 0x00
#define DILITHIUM_CMD_VERIFY 0x01
#define DILITHIUM_CMD_SIGN 0x02

#define DILITHIUM_CHUNK_SIZE 256
#define DILITHIUM_MAX_MSG_LEN 8192

#define DILITHIUM_START_BYTE 0xA0
#define DILITHIUM_END_BYTE 0xA1
#define DILITHIUM_ACK_BYTE 0xCC

typedef struct
{
    uint8_t start;    // should be 0xA0
    uint8_t cmd;      // e.g., 0x02 = SIGN
    uint8_t sec_lvl;  // 2, 3, or 5
    uint16_t msg_len; // total payload length in bytes
} __attribute__((packed)) dilithium_header_t;

static int invalid_header(dilithium_header_t *dh);