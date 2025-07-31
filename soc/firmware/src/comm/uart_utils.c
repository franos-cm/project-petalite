#include "uart_utils.h"

inline void uart_send_ack(void)
{
    putchar(DILITHIUM_ACK_BYTE);
}

inline void uart_send_ready(void)
{
    putchar(DILITHIUM_READY_BYTE);
}

inline void uart_send_start(void)
{
    putchar(DILITHIUM_START_BYTE);
}

inline dilithium_request_t uart_parse_request_header(void)
{
    dilithium_request_t header;

    header.cmd = getchar();
    header.sec_lvl = getchar();

    header.msg_len = ((uint32_t)getchar()) << 0;
    header.msg_len |= ((uint32_t)getchar()) << 8;
    header.msg_len |= ((uint32_t)getchar()) << 16;
    header.msg_len |= ((uint32_t)getchar()) << 24;

    return header;
}

int uart_readn(volatile uint8_t *dst, uint32_t total_len, uint32_t ack_group_length)
{
    if (ack_group_length > total_len)
        return UART_ERR_INVALID_ARGS;

    uint32_t ack_counter = 0;
    for (uint32_t i = 0; i < total_len; i++)
    {
        dst[i] = getchar();

        if (ack_group_length > 0)
        {
            ack_counter++;
            // If the group is full and it's not the final byte of the entire transfer...
            if ((ack_counter == ack_group_length) && (i < total_len - 1))
            {
                uart_send_ack();
                ack_counter = 0;
            }
        }
    }

    return UART_OK;
}

int uart_sendn(volatile uint8_t *src, uint32_t total_len, uint32_t ack_group_length)
{
    if (ack_group_length > total_len)
        return UART_ERR_INVALID_ARGS;

    uint32_t ack_counter = 0;
    for (uint32_t i = 0; i < total_len; i++)
    {
        putchar(src[i]);

        if (ack_group_length > 0)
        {
            ack_counter++;
            // If the group is full and it's not the final byte of the entire transfer...
            if ((ack_counter == ack_group_length) && (i < total_len - 1))
            {
                uart_wait_for_ack();
                ack_counter = 0;
            }
        }
    }

    return UART_OK;
}

inline void uart_wait_for_ack(void)
{
    while (getchar() == DILITHIUM_ACK_BYTE)
        ;
}

void uart_transmission_handshake(void)
{
    uart_send_start();
    uart_wait_for_ack();
}

void uart_send_response(const dilithium_response_t *rsp)
{
    putchar(rsp->cmd);
    putchar(rsp->sec_lvl);
    putchar(rsp->rsp_code);
    putchar(rsp->verify_res);
}
