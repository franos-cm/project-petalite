#ifndef RECEIVER_H
#define RECEIVER_H

#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <generated/csr.h>
#include <libbase/irq.h>
#include <libbase/uart.h>
#include "shared.h"

// ---- TPM-specific sizes ----
#define TPM_HEADER_LEN 10u    // 2(tag) + 4(size) + 4(code)
#define TPM_MAX_CMD_LEN 4096u // tune to your worst-case; spec allows large buffers

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

void uart_irq_init(void);
uint32_t inline get_cmd_len(void);
bool receiver_ingestion_done(void);
uint32_t read_command();

#endif // RECEIVER_H