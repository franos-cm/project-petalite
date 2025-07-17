#include "uart_utils.h"
#include "dilithium_utils.h"

static void uart_send_ack(void)
{
    putchar(DILITHIUM_ACK_BYTE);
}

static void uart_read(volatile uint8_t *dst, uint32_t len)
{
    for (uint32_t i = 0; i < len; ++i)
    {
        while (!readchar_nonblock())
        {
            // wait for input byte
        }
        dst[i] = getchar();
    }
}

static void uart_read_chunks(uint8_t *dest, uint16_t total_len)
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
            while (!readchar_nonblock())
            {
                // wait
            }
            dest[received + i] = getchar();
        }

        received += chunk_len;
    }
}