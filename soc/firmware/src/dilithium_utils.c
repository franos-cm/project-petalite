#include "dilithium_utils.h"
#include <generated/csr.h>

int invalid_header(dilithium_header_t *dh)
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

void dilithium_init(void)
{
    dilithium_reset_write(1);
    dilithium_start_write(0);
    dilithium_reset_write(0);
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
    dilithium_reset_write(0);
}

void dilithium_dma_read_setup(uint64_t base_addr, uint32_t length)
{
    dilithium_reader_base_write(base_addr);
    dilithium_reader_length_write(length);
}

void dilithium_dma_read_start(void)
{
    dilithium_reader_enable_write(1);
}

void dilithium_dma_read_wait(void)
{
    while (!dilithium_reader_done_read())
        ;
    dilithium_reader_enable_write(0);
}
