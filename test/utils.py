from enum import StrEnum

DILITHIUM_SIZES_DICT = {
    2: {
        "h": 84,
        "s1": 384,
        "s2": 384,
        "t0": 1664,
        "t1": 1280,
        "z": 2304,
        "rho": 32,
        "k": 32,
        "tr": 32,
        "c": 32,
    },
    3: {
        "h": 61,
        "s1": 640,
        "s2": 768,
        "t0": 2496,
        "t1": 1920,
        "z": 3200,
        "rho": 32,
        "k": 32,
        "tr": 32,
        "c": 32,
    },
    5: {
        "h": 83,
        "s1": 672,
        "s2": 768,
        "t0": 3328,
        "t1": 2560,
        "z": 4480,
        "rho": 32,
        "k": 32,
        "tr": 32,
        "c": 32,
    },
}


DILITHIUM_CMD_KEYGEN = 0x00
DILITHIUM_CMD_VERIFY = 0x01
DILITHIUM_CMD_SIGN = 0x02

DILITHIUM_CHUNK_SIZE = 256
DILITHIUM_MAX_MSG_LEN = 8192

DILITHIUM_SYNC_BYTE = 0xB0
DILITHIUM_READY_BYTE = 0xA0
DILITHIUM_ACK_BYTE = 0xCC
DILITHIUM_START_BYTE = 0xAC
BASE_ACK_GROUP_LENGTH = 64


class DilithiumOp(StrEnum):
    KEYGEN = "KEYGEN"
    SIGN = "SIGN"
    VERIFY = "VERIFY"


class ResponseHeader:
    def __init__(self, bytestream):
        self.cmd = bytestream[0]
        self.sec_lvl = bytestream[1]
        self.rsp_code = bytestream[2]
        self.verify_res = bytestream[3]
