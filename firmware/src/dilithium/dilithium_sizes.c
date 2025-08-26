#include "dilithium_sizes.h"

int get_sig_len(uint8_t lvl)
{
    return DILITHIUM_C_SIZE + get_z_len(lvl) + get_h_len(lvl);
}

int get_pk_len(uint8_t lvl)
{
    return (DILITHIUM_RHO_SIZE + get_t1_len(lvl));
}

int get_sk_len(uint8_t lvl)
{
    return (
        DILITHIUM_RHO_SIZE + DILITHIUM_K_SIZE + DILITHIUM_TR_SIZE + get_s1_len(lvl) + get_s2_len(lvl) + get_t0_len(lvl));
}

int get_h_len(uint8_t lvl)
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

int get_s1_len(uint8_t lvl)
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

int get_s2_len(uint8_t lvl)
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

int get_t0_len(uint8_t lvl)
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

int get_t1_len(uint8_t lvl)
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

int get_z_len(uint8_t lvl)
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