#include "dilithium_utils.h"

int invalid_header(dilithium_request_t *dh)
{
    // Validate security level
    if (dh->sec_lvl != 2 && dh->sec_lvl != 3 && dh->sec_lvl != 5)
    {
        return 1;
    }
    if (dh->msg_len > DILITHIUM_MAX_MSG_LEN)
    {
        return 2;
    }
    return 0;
}

inline uint32_t align8(uint32_t x)
{
    return (x + 7) & ~7;
}

void dilithium_init(void)
{
    dilithium_reset();
}

void dilithium_setup(uint8_t op, uint16_t sec_level)
{
    dilithium_mode_write(op);
    dilithium_security_level_write(sec_level);
}

void dilithium_start(void)
{
    dilithium_start_write(1);
    dilithium_start_write(0);
}

void dilithium_reset(void)
{
    dilithium_reset_write(1);
    dilithium_start_write(0);
    dilithium_reader_enable_write(0);
    dilithium_writer_enable_write(0);
    dilithium_reset_write(0);
}

// NOTE: since Litex DMA truncates last non-integer transfer, we need to ceil()
void dilithium_read_setup(uint64_t base_addr, uint32_t length)
{
    dilithium_reader_base_write(align8(base_addr));
    dilithium_reader_length_write(align8(length));
}

void dilithium_read_start(void)
{
    dilithium_reader_enable_write(1);
}

bool dilithium_read_in_progress(void)
{
    if (dilithium_reader_enable_read() && !dilithium_reader_done_read())
    {
        return true;
    }
    else
    {
        dilithium_reader_enable_write(0);
        return false;
    }
}

void dilithium_read_wait(void)
{
    while (dilithium_read_in_progress())
        ;
}

// NOTE: since Litex DMA truncates last non-integer transfer, we need to ceil()
void dilithium_write_setup(uint64_t base_addr, uint32_t length)
{
    dilithium_writer_base_write(align8(base_addr));
    dilithium_writer_length_write(align8(length));
}

void dilithium_write_start(void)
{
    dilithium_writer_enable_write(1);
}

bool dilithium_write_in_progress(void)
{
    if (dilithium_writer_enable_read() && !dilithium_writer_done_read())
    {
        return true;
    }
    else
    {
        dilithium_writer_enable_write(0);
        return false;
    }
}

void dilithium_write_wait(void)
{
    while (dilithium_write_in_progress())
        ;
}

void dilithium_read_msg_in_chunks(uint32_t msg_len, uintptr_t msg_chunk_addr)
{
    // Ingest the entire message in chunks.
    int message_bytes_read = 0;
    while (message_bytes_read < msg_len)
    {
        // Calculate the size of the next chunk to read.
        int remaining_msg_bytes = msg_len - message_bytes_read;
        int current_chunk_size = (remaining_msg_bytes > DILITHIUM_CHUNK_SIZE) ? DILITHIUM_CHUNK_SIZE : remaining_msg_bytes;

        // Before starting the next DMA, wait for the previous one to complete.
        dilithium_read_wait();

        uart_send_ack();
        uart_readn((volatile uint8_t *)msg_chunk_addr, current_chunk_size, BASE_ACK_GROUP_LENGTH);

        // Pass the newly read chunk to the DMA.
        dilithium_read_setup((uint64_t)msg_chunk_addr, align8(current_chunk_size));
        dilithium_read_start();

        message_bytes_read += current_chunk_size;
    }
}