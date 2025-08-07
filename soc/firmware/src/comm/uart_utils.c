#include "uart_utils.h"

inline void uart_send_ack(void)
{
    uart_write(DILITHIUM_ACK_BYTE);
}

inline void uart_send_ready(void)
{
    uart_write(DILITHIUM_READY_BYTE);
}

inline void uart_send_start(void)
{
    uart_write(DILITHIUM_START_BYTE);
}

inline dilithium_request_t uart_parse_request_header(void)
{
    dilithium_request_t header;

    header.cmd = uart_read();
    header.sec_lvl = uart_read();

    header.msg_len = ((uint32_t)uart_read()) << 0;
    header.msg_len |= ((uint32_t)uart_read()) << 8;
    header.msg_len |= ((uint32_t)uart_read()) << 16;
    header.msg_len |= ((uint32_t)uart_read()) << 24;

    return header;
}

int uart_readn(volatile uint8_t *dst, uint32_t total_len, uint32_t ack_group_length)
{
    // TODO: could probably include this in the if block further down
    if (ack_group_length > total_len)
        ack_group_length = total_len;

    uint32_t ack_counter = 0;
    for (uint32_t i = 0; i < total_len; i++)
    {
        dst[i] = uart_read();

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
        ack_group_length = total_len;

    uint32_t ack_counter = 0;
    for (uint32_t i = 0; i < total_len; i++)
    {
        uart_write(src[i]);

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
    while (uart_read() != DILITHIUM_ACK_BYTE)
        ;
}

void uart_transmission_handshake(void)
{
    uart_send_start();
    uart_wait_for_ack();
}

void uart_send_response(const dilithium_response_t *rsp)
{
    uart_write(rsp->cmd);
    uart_write(rsp->sec_lvl);
    uart_write(rsp->rsp_code);
    uart_write(rsp->verify_res);
}
