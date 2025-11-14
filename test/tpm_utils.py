import time

# Shared TPM constants
TPM_ALG_ECC = 0x0023
TPM_ALG_DILITHIUM = 0x0072
TPM_CC_HashSignStart = 0x200001A0
TPM_CC_HashSignFinish = 0x200001A1
TPM_CC_SequenceUpdate = 0x0000015C
TPM_CC_HashVerifyStart = 0x200001A2
TPM_CC_HashVerifyFinish = 0x200001A3


def u32_be_hex(v: int) -> str:
    return f"{v & 0xFFFFFFFF:08X}"


def u16_be_hex(v: int) -> str:
    return f"{v & 0xFFFF:04X}"


def bytes_hex(b: bytes) -> str:
    return b.hex().upper()


def sessions_param_offset(rsp: bytes, response_handle_count: int = 0) -> int:
    """Return offset where response parameters start (after rc, handles, and parameterSize if ST_SESSIONS)."""
    if len(rsp) < 10:
        raise RuntimeError("TPM response too short")
    tag = int.from_bytes(rsp[0:2], "big")
    off = 10 + (4 * response_handle_count)
    if tag == 0x8002:
        off += 4  # parameterSize
    return off


def parse_createprimary_outpublic(rsp: bytes):
    """Parse CreatePrimary outPublic and return a dict with type and key fields.
    Supports ECC and Dilithium; returns raw bytes for unknown types.
    """
    off = sessions_param_offset(rsp, response_handle_count=1)
    if off + 2 > len(rsp):
        raise RuntimeError("Bad CreatePrimary response (no outPublic)")
    out_pub_size = int.from_bytes(rsp[off : off + 2], "big")
    off += 2
    end = off + out_pub_size
    if end > len(rsp):
        raise RuntimeError("Bad CreatePrimary response (truncated outPublic)")

    p = off
    type_alg = int.from_bytes(rsp[p : p + 2], "big"); p += 2
    name_alg = int.from_bytes(rsp[p : p + 2], "big"); p += 2
    object_attrs = int.from_bytes(rsp[p : p + 4], "big"); p += 4
    ap_size = int.from_bytes(rsp[p : p + 2], "big"); p += 2
    p += ap_size

    if type_alg == TPM_ALG_DILITHIUM:
        p += 2 + 2 + 1 + 2  # symmetric + scheme + securityLevel + nameHashAlg
        u_size = int.from_bytes(rsp[p : p + 2], "big"); p += 2
        pub = rsp[p : p + u_size]
        return {"type": "dilithium", "nameAlg": name_alg, "objectAttributes": object_attrs, "pub": pub}

    if type_alg == TPM_ALG_ECC:
        p += 2 + 2 + 2 + 2 + 2  # ECC parameters
        x_size = int.from_bytes(rsp[p : p + 2], "big"); p += 2
        x = rsp[p : p + x_size]; p += x_size
        y_size = int.from_bytes(rsp[p : p + 2], "big"); p += 2
        y = rsp[p : p + y_size]; p += y_size
        return {"type": "ecc", "nameAlg": name_alg, "objectAttributes": object_attrs, "x": x, "y": y}

    return {"type": f"0x{type_alg:04X}", "nameAlg": name_alg, "objectAttributes": object_attrs, "raw": rsp[off:end]}


def build_dilithium_signature_param(sig: bytes) -> str:
    """Return TPMT_SIGNATURE for Dilithium: sigAlg|hashAlg(NULL)|TPM2B sig."""
    sigAlg = u16_be_hex(TPM_ALG_DILITHIUM)
    hashAlg = u16_be_hex(0x0010)  # TPM_ALG_NULL
    tpmb = u16_be_hex(len(sig)) + bytes_hex(sig)
    return f"{sigAlg}{hashAlg}{tpmb}"
