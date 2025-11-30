#pragma once
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <irq.h>
#include <generated/csr.h>
#include <generated/soc.h>
#include <libbase/uart.h>
#include "platform.h"

// ---- TPM-specific sizes ----
#define TPM_HEADER_LEN 10u    // 2(tag) + 4(size) + 4(code)
#define TPM_MAX_CMD_LEN 4096u // tune to your worst-case; spec allows large buffers

// Send a latency record: 8-byte big-endian cycle count.
#define TPM_LATENCY_RECORD_LEN 8u

// NOTE: this should be 64 bit aligned
extern uint8_t tpm_cmd_buf[TPM_MAX_CMD_LEN];

// TODO: we need some FSM info so we can deny new requests before finishing one being done atm, such as testing
// ---- Simple assembler state machine ----
typedef enum
{

    RX_WAITING_FOR_HEADER = 0,
    RX_WAITING_FOR_BODY = 1,
    RX_COMMAND_READY = 2,
    RX_ERROR = 3

} rx_state_t;

typedef enum
{

    SUCCESSFUL = 0,
    ER_CMDSIZE_TOO_LARGE = 1,
    ER_CMDSIZE_SMALLER_THAN_HEADER = 2,

} rx_return_code_t;

void transport_irq_init(void);
uint32_t transport_get_cmd_len(void);
uint32_t transport_get_bytes_read(void);
bool transport_ingestion_done(void);
uint32_t transport_read_command(void);
void transport_write_byte(uint8_t b);
void transport_write_rsp(const uint8_t *buf, uint32_t len);
void transport_write_ready(void);
void transport_write_latency_record(uint64_t cycles);
void debug_breakpoint(uint8_t b);