#include "dilithium_sizes.h"

static int get_sig_len(uint8_t lvl)
{
    switch (lvl)
    {
    case 2:
        return DILITHIUM_SIG_LVL2_SIZE;
    case 3:
        return DILITHIUM_SIG_LVL3_SIZE;
    case 5:
        return DILITHIUM_SIG_LVL5_SIZE;
    default:
        return -1;
    }
}

static int get_pk_len(uint8_t lvl)
{
    switch (lvl)
    {
    case 2:
        return DILITHIUM_PK_LVL2_SIZE;
    case 3:
        return DILITHIUM_PK_LVL3_SIZE;
    case 5:
        return DILITHIUM_PK_LVL5_SIZE;
    default:
        return -1;
    }
}

static int get_sk_len(uint8_t lvl)
{
    switch (lvl)
    {
    case 2:
        return DILITHIUM_SK_LVL2_SIZE;
    case 3:
        return DILITHIUM_SK_LVL3_SIZE;
    case 5:
        return DILITHIUM_SK_LVL5_SIZE;
    default:
        return -1;
    }
}

static int get_c_len(uint8_t lvl)
{
    switch (lvl)
    {
    case 2:
        return DILITHIUM_C_LVL2_SIZE;
    case 3:
        return DILITHIUM_C_LVL3_SIZE;
    case 5:
        return DILITHIUM_C_LVL5_SIZE;
    default:
        return -1;
    }
}

static int get_h_len(uint8_t lvl)
{
    switch (lvl)
    {
    case 2:
        return DILITHIUM_H_LVL2_SIZE;
    case 3:
        return DILITHIUM_H_LVL3_SIZE;
    case 5:
        return DILITHIUM_H_LVL5_SIZE;
    default:
        return -1;
    }
}

static int get_s1_len(uint8_t lvl)
{
    switch (lvl)
    {
    case 2:
        return DILITHIUM_S1_LVL2_SIZE;
    case 3:
        return DILITHIUM_S1_LVL3_SIZE;
    case 5:
        return DILITHIUM_S1_LVL5_SIZE;
    default:
        return -1;
    }
}

static int get_s2_len(uint8_t lvl)
{
    switch (lvl)
    {
    case 2:
        return DILITHIUM_S2_LVL2_SIZE;
    case 3:
        return DILITHIUM_S2_LVL3_SIZE;
    case 5:
        return DILITHIUM_S2_LVL5_SIZE;
    default:
        return -1;
    }
}

static int get_t0_len(uint8_t lvl)
{
    switch (lvl)
    {
    case 2:
        return DILITHIUM_T0_LVL2_SIZE;
    case 3:
        return DILITHIUM_T0_LVL3_SIZE;
    case 5:
        return DILITHIUM_T0_LVL5_SIZE;
    default:
        return -1;
    }
}

static int get_t1_len(uint8_t lvl)
{
    switch (lvl)
    {
    case 2:
        return DILITHIUM_T1_LVL2_SIZE;
    case 3:
        return DILITHIUM_T1_LVL3_SIZE;
    case 5:
        return DILITHIUM_T1_LVL5_SIZE;
    default:
        return -1;
    }
}

static int get_tr_len(uint8_t lvl)
{
    switch (lvl)
    {
    case 2:
        return DILITHIUM_TR_LVL2_SIZE;
    case 3:
        return DILITHIUM_TR_LVL3_SIZE;
    case 5:
        return DILITHIUM_TR_LVL5_SIZE;
    default:
        return -1;
    }
}

static int get_z_len(uint8_t lvl)
{
    switch (lvl)
    {
    case 2:
        return DILITHIUM_Z_LVL2_SIZE;
    case 3:
        return DILITHIUM_Z_LVL3_SIZE;
    case 5:
        return DILITHIUM_Z_LVL5_SIZE;
    default:
        return -1;
    }
}