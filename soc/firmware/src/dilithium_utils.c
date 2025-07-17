#include "dilithium_utils.h"

static int invalid_header(dilithium_header_t *dh)
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

static void dilithium_setup(uint8_t op, uint16_t sec_level)
{
    main_mode_write(op);
    main_sec_lvl_write(sec_level);
}

static void dilithium_start()
{
    main_start_write(1);
    main_start_write(0);
}

static void dilithium_reset()
{
    main_start_write(1);
    main_start_write(0);
}

static void dilithium_init()
{
    main_reset_write(1);
    main_reset_write(0);
}