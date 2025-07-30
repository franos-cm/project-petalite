# Size constants (converted from hex to decimal for readability)
DILITHIUM_SIZES_DICT = {
    # H component sizes
    "h": {2: 84, 3: 61, 5: 83},  # 84  # 61  # 83
    # S1 component sizes
    "s1": {2: 384, 3: 640, 5: 672},  # 384  # 640  # 672
    # S2 component sizes
    "s2": {2: 384, 3: 768, 5: 768},  # 384  # 768  # 768
    # T0 component sizes
    "t0": {2: 1664, 3: 2496, 5: 3328},  # 1664  # 2496  # 3328
    # T1 component sizes
    "t1": {2: 1280, 3: 1920, 5: 2560},  # 1280  # 1920  # 2560
    # Z component sizes
    "z": {2: 2304, 3: 3200, 5: 4480},  # 2304  # 3200  # 4480
    "rho": 32,
    "k": 32,
    "tr": 32,
    "c": 32,
}


DILITHIUM_CMD_KEYGEN = 0x00
DILITHIUM_CMD_VERIFY = 0x01
DILITHIUM_CMD_SIGN = 0x02

DILITHIUM_CHUNK_SIZE = 256
DILITHIUM_MAX_MSG_LEN = 8192

DILITHIUM_READY_BYTE = 0xA0
DILITHIUM_ACK_BYTE = 0xCC
DILITHIUM_START_BYTE = 0xAC
DILITHIUM_END_BYTE = 0xA1
