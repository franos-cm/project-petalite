#include <stdio.h>
#include <libbase/uart.h>
#include <libbase/console.h>
#include "uart_utils.h"
#include "dilithium_utils.h"

void uart_send_ack(void)
{
    putchar(DILITHIUM_ACK_BYTE);
}

void uart_readn(volatile uint8_t *dst, uint32_t total_len, uint32_t ack_group_length)
{
    if (ack_group_length > total_len)
    {
        ack_group_length = total_len;
    }

    for (uint32_t i = 0; i < total_len; i++)
    {
        dst[i] = getchar();

        // Send an ACK every ack_group_length bytes
        if (ack_group_length && ((i + 1) % ack_group_length == 0 || i == total_len - 1))
        {
            uart_send_ack();
        }
    }
}

void uart_read_chunks(uint8_t *dest, uint16_t total_len)
{
    uint16_t received = 0;

    while (received < total_len)
    {
        uint16_t chunk_len = (total_len - received > DILITHIUM_CHUNK_SIZE)
                                 ? DILITHIUM_CHUNK_SIZE
                                 : (total_len - received);

        // Wait for full chunk
        for (int i = 0; i < chunk_len; ++i)
        {
            // while (!readchar_nonblock())
            // {
            //     // wait
            // }
            dest[received + i] = getchar();
        }

        received += chunk_len;
    }
}