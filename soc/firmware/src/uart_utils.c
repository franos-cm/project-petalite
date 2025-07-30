#include "uart_utils.h"

void uart_send_ack(void)
{
    putchar(DILITHIUM_ACK_BYTE);
}

void uart_send_ready(void)
{
    putchar(DILITHIUM_READY_BYTE);
}

dilithium_header_t uart_parse_request_header(void)
{
    dilithium_header_t header;

    header.cmd = getchar();
    header.sec_lvl = getchar();

    header.msg_len = ((uint32_t)getchar()) << 0;
    header.msg_len |= ((uint32_t)getchar()) << 8;
    header.msg_len |= ((uint32_t)getchar()) << 16;
    header.msg_len |= ((uint32_t)getchar()) << 24;

    return header;
}

void uart_readn(volatile uint8_t *dst, uint32_t total_len, uint32_t ack_group_length)
{
    if (ack_group_length > total_len)
    {
        // Throw error instead
        ack_group_length = total_len;
    }

    for (uint32_t i = 0; i < total_len; i++)
    {
        dst[i] = getchar();

        // Send an ACK every ack_group_length bytes, except for last one, which must be done manually
        if (ack_group_length && (((i + 1) % ack_group_length == 0) && (i != total_len - 1)))
        {
            uart_send_ack();
        }
    }
}

void uart_send_response(const dilithium_response_t *rsp)
{
    putchar(rsp->cmd);
    putchar(rsp->sec_lvl);
    putchar(rsp->rsp_code);
    putchar(rsp->verify_res);
}
