# TODO: this file is undoubtedly messy at the moment, and we should make it cleaner eventually.
import os
import time
import argparse
from uart import UARTConnection

TPM_ALG_ECC = 0x0023
TPM_ALG_DILITHIUM = 0x0072
TPM_CC_HashSignStart = 0x200001A0
TPM_CC_HashSignFinish = 0x200001A1
TPM_CC_SequenceUpdate = 0x0000015C
TPM_CC_HashVerifyStart = 0x200001A2
TPM_CC_HashVerifyFinish = 0x200001A3


def _u32_be_hex(v: int) -> str:
    return f"{v & 0xFFFFFFFF:08X}"


def _u16_be_hex(v: int) -> str:
    return f"{v & 0xFFFF:04X}"


def _bytes_hex(b: bytes) -> str:
    return b.hex().upper()


def _write_hex_file(path: str, data: bytes) -> None:
    with open(path, "w") as f:
        f.write(data.hex().upper() + "\n")


def _sessions_param_offset(rsp: bytes, response_handle_count: int = 0) -> int:
    # Return offset where response parameters start (after rc, handles, and parameterSize if ST_SESSIONS)
    if len(rsp) < 10:
        raise RuntimeError("TPM response too short")
    tag = int.from_bytes(rsp[0:2], "big")
    off = 10 + (4 * response_handle_count)
    if tag == 0x8002:
        off += 4  # parameterSize
    return off


def _parse_createprimary_outpublic(rsp: bytes):
    # Returns dict with type and key fields extracted from outPublic
    # CreatePrimary has 1 response handle
    off = _sessions_param_offset(rsp, response_handle_count=1)
    if off + 2 > len(rsp):
        raise RuntimeError("Bad CreatePrimary response (no outPublic)")
    out_pub_size = int.from_bytes(rsp[off : off + 2], "big")
    off += 2
    end = off + out_pub_size
    if end > len(rsp):
        raise RuntimeError("Bad CreatePrimary response (truncated outPublic)")

    # TPMT_PUBLIC
    p = off
    type_alg = int.from_bytes(rsp[p : p + 2], "big")
    p += 2
    name_alg = int.from_bytes(rsp[p : p + 2], "big")
    p += 2
    object_attrs = int.from_bytes(rsp[p : p + 4], "big")
    p += 4
    ap_size = int.from_bytes(rsp[p : p + 2], "big")
    p += 2
    p += ap_size  # authPolicy bytes

    if type_alg == TPM_ALG_DILITHIUM:
        # parameters: symmetric(2), scheme(2), securityLevel(1), nameHashAlg(2)
        p += 2 + 2 + 1 + 2
        # unique: TPM2B (size + bytes)
        u_size = int.from_bytes(rsp[p : p + 2], "big")
        p += 2
        pub = rsp[p : p + u_size]
        return {
            "type": "dilithium",
            "nameAlg": name_alg,
            "objectAttributes": object_attrs,
            "pub": pub,
        }
    elif type_alg == TPM_ALG_ECC:
        # parameters (as built in create_primary_cmd): symmetric(2), scheme(2)+hash(2), curveID(2), kdf(2)
        p += 2 + 2 + 2 + 2 + 2
        # unique: TPMS_ECC_POINT => TPM2B x, TPM2B y
        x_size = int.from_bytes(rsp[p : p + 2], "big")
        p += 2
        x = rsp[p : p + x_size]
        p += x_size
        y_size = int.from_bytes(rsp[p : p + 2], "big")
        p += 2
        y = rsp[p : p + y_size]
        p += y_size
        return {
            "type": "ecc",
            "nameAlg": name_alg,
            "objectAttributes": object_attrs,
            "x": x,
            "y": y,
        }
    else:
        return {
            "type": f"0x{type_alg:04X}",
            "nameAlg": name_alg,
            "objectAttributes": object_attrs,
            "raw": rsp[off:end],
        }


class TpmTester:
    """Dilithium test suite - uses UART connection for testing"""

    uart: UARTConnection

    def __init__(self, uart: UARTConnection):
        self.uart = uart

    def wait_for_ready_signal(self):
        while not self.uart.wait_for_ready(timeout=180):
            pass

    def read_tpm_response(self, timeout):
        header = self.uart.wait_for_bytes(num_bytes=10, timeout=timeout)
        response_size = int.from_bytes(header[2:6], byteorder="big")
        body = self.uart.wait_for_bytes(num_bytes=(response_size - 10), timeout=timeout)
        return header + body

    def extract_first_handle_from_response(self, rsp: bytes) -> int:
        # After 10-byte header, a response-handle (if present) is 4 bytes big-endian.
        if len(rsp) < 14:
            raise RuntimeError("Response too short to contain a handle")
        return int.from_bytes(rsp[10:14], byteorder="big")
    
    def build_dilithium_signature_param(self, sig: bytes) -> str:
        # TPMT_SIGNATURE for Dilithium: sigAlg(2) | hash(2=TPM_ALG_NULL) | TPM2B sig
        sigAlg = _u16_be_hex(TPM_ALG_DILITHIUM)
        hashAlg = _u16_be_hex(0x0010)  # TPM_ALG_NULL
        tpmb = _u16_be_hex(len(sig)) + _bytes_hex(sig)
        return f"{sigAlg}{hashAlg}{tpmb}"

    def startup_cmd(self, startup_type: str = "CLEAR"):
        # Map startup type to 2-byte parameter
        st = (startup_type or "").strip().upper()
        if st in ("0", "CLEAR", ""):
            su_val = "0000"
        elif st in ("1", "STATE"):
            su_val = "0001"
        else:
            su_val = "0000"  # default CLEAR

        # Full command: TPM_ST_NO_SESSIONS (0x8001), size 0x000C, TPM_CC_Startup (0x00000144), TPM_SU (2 bytes)
        bytestring = f"80010000000C00000144{su_val}"
        bytestream = bytes.fromhex(bytestring)
        print("Sending startup command...")
        self.uart.send_bytes(bytestream)

        print("Waiting for startup answer...")
        self.wait_for_ready_signal()
        result = self.read_tpm_response(timeout=3600)

        if not result:
            raise RuntimeError("Failed to get startup answer, aborting")
        print("Startup cmd response:\n", " ".join(f"{b:02X}" for b in result))
        return result

    def get_random_cmd(self, num_bytes: int = 32):
        # Replace fixed length with user choice
        num_bytes = max(1, min(0xFFFF, int(num_bytes)))
        bytestring = f"80010000000C0000017B{num_bytes:04X}"
        bytestream = bytes.fromhex(bytestring.replace(" ", ""))
        print(f"Sending get_random_bytes({num_bytes}) command...")
        self.uart.send_bytes(bytestream)

        print("Waiting for get_random answer...")
        self.wait_for_ready_signal()
        result = self.read_tpm_response(timeout=3600)

        if not result:
            raise RuntimeError("Failed to get get_random_bytes() answer, aborting")
        print("get_random_bytes() response:\n", " ".join(f"{b:02X}" for b in result))
        return result

    def create_primary_cmd(self):
        bytestring = (
            # =========== Header ===========
            "80 02"  # ST_SESSIONS
            "00 00 00 45"  # Command size
            "00 00 01 31"  # CreatePrimary
            # =========== Handle ===========
            "40 00 00 01"  # Owner handle
            # =========== AuthArea ===========
            "00 00 00 09"  # Size of authArea
            "40 00 00 09"  # TPM_RS_PW -> use password
            "00 00 00 00 00"  # all zeroes
            # =========== inSensitive ===========
            "00 08"  # Size of sensitive area
            "00 04"  # Size of password
            "61 62 63 64"  # Password
            "00 00"  # Sensitive data
            # =========== inPublic ===========
            "00 18"  # Size of inPublic
            "00 23"  # TPM_ALG_ECC
            "00 0B"  # TPM_ALG_SHA256 for deriving name
            "00 04 04 72"  # objectAttributes TODO: revise
            "00 00"  # authPolicy TODO: revise
            "00 10  00 18 00 0B  00 03  00 10"  # TPMS_ECC_PARMS
            "00 00  00 00"  # unique TODO: revise
            # outsideInfo
            "00 00"
            # creationPCR
            "00 00 00 00"
        )

        bytestream = bytes.fromhex(bytestring.replace(" ", ""))
        print("Sending create_primary() command...")
        self.uart.send_bytes(bytestream)

        print("Waiting for create_primary() answer...")
        self.wait_for_ready_signal()
        result = self.read_tpm_response(timeout=3600)

        if not result:
            raise RuntimeError("Failed to get create_primary() answer, aborting")
        print("create_primary() response:\n", " ".join(f"{b:02X}" for b in result))

        # Extract and print public key
        pub = _parse_createprimary_outpublic(result)
        ts = time.strftime("%Y%m%d-%H%M%S")
        if pub["type"] == "ecc":
            x, y = pub["x"], pub["y"]
            print(f"ECC public key:")
            print(f"  X ({len(x)} bytes): {x.hex().upper()}")
            print(f"  Y ({len(y)} bytes): {y.hex().upper()}")
            _write_hex_file(f"ecc_pub_x_{ts}.hex", x)
            _write_hex_file(f"ecc_pub_y_{ts}.hex", y)
        elif pub["type"] == "dilithium":
            pk = pub["pub"]
            print(f"Dilithium public key ({len(pk)} bytes): {pk.hex().upper()}")
            _write_hex_file(f"dilithium_pub_{ts}.hex", pk)
        else:
            print(
                f"Unknown public type {pub['type']} (raw len={len(pub.get('raw', b''))})"
            )

        return result

    def create_primary_dilithium_cmd(self):
        # TPM2_CreatePrimary with Dilithium L2
        bytestring = (
            # ===== Header =====
            "80 02"  # TPM_ST_SESSIONS
            "00 00 00 40"  # command size = 64 bytes
            "00 00 01 31"  # TPM_CC_CreatePrimary
            # ===== Handle =====
            "40 00 00 01"  # TPM_RH_OWNER
            # ===== AuthArea =====
            "00 00 00 09"  # authArea size = 9
            "40 00 00 09"  # TPM_RS_PW
            "00 00"  # nonce size = 0
            "00"  # session attributes
            "00 00"  # hmac size = 0 (empty owner auth)
            # ===== inSensitive (TPM2B_SENSITIVE_CREATE) =====
            "00 08"  # total size = 8
            "00 04"  # userAuth size = 4
            "61 62 63 64"  # "abcd"
            "00 00"  # sensitive.data size = 0
            # ===== inPublic (TPM2B_PUBLIC) =====
            "00 13"  # TPMT_PUBLIC size = 19
            "00 72"  # type = TPM_ALG_DILITHIUM (0x0072)
            "00 0B"  # nameAlg = TPM_ALG_SHA256 (0x000B)
            "00 04 04 72"  # objectAttributes = 0x00040472
            "00 00"  # authPolicy size = 0
            # ----- TPMS_DILITHIUM_PARMS -----
            "00 10"  # parameters.symmetric.algorithm = TPM_ALG_NULL
            "00 10"  # parameters.scheme.scheme = TPM_ALG_NULL
            "02"  # securityLevel = 2
            "00 0B"  # nameHashAlg = TPM_ALG_SHA256
            # ----- unique -----
            "00 00"  # unique (TPM2B) size = 0
            # ===== outsideInfo =====
            "00 00"
            # ===== creationPCR =====
            "00 00 00 00"
        )
        bytestream = bytes.fromhex(bytestring.replace(" ", ""))
        print("Sending create_primary_dilithium() command...")
        self.uart.send_bytes(bytestream)

        print("Waiting for create_primary_dilithium() answer...")
        self.wait_for_ready_signal()
        result = self.read_tpm_response(timeout=3600)

        if not result:
            raise RuntimeError(
                "Failed to get create_primary_dilithium() answer, aborting"
            )
        print(
            "create_primary_dilithium() response:\n",
            " ".join(f"{b:02X}" for b in result),
        )

        # Extract and print Dilithium public key
        pub = _parse_createprimary_outpublic(result)
        ts = time.strftime("%Y%m%d-%H%M%S")
        if pub["type"] == "dilithium":
            pk = pub["pub"]
            print(f"Dilithium public key ({len(pk)} bytes): {pk.hex().upper()}")
            _write_hex_file(f"dilithium_pub_{ts}.hex", pk)
        else:
            print(f"Unexpected public type {pub['type']} in Dilithium CreatePrimary")

        return result

    def hashsign_start_cmd(
        self, key_handle: int, total_len: int, key_pw: bytes = b"abcd"
    ) -> int:
        # Build TPM2_HashSignStart request with one RS_PW auth for the key
        tag = "80 02"  # TPM_ST_SESSIONS
        cc = _u32_be_hex(TPM_CC_HashSignStart)
        # Handle area: key handle
        handle_hex = _u32_be_hex(key_handle)
        # Auth area: one TPMS_AUTH_COMMAND (RS_PW)
        # sessionHandle (RS_PW), nonce(0), sessionAttributes(0), hmac = key_pw
        auth_entry = "40000009"  # TPM_RS_PW
        auth_entry += "0000"  # nonce size = 0
        auth_entry += "00"  # session attributes
        auth_entry += _u16_be_hex(len(key_pw))  # hmac size
        auth_entry += _bytes_hex(key_pw)  # hmac bytes
        auth_area_size_hex = _u32_be_hex(len(bytes.fromhex(auth_entry)))
        # Parameters: totalLen (UINT32)
        params_hex = _u32_be_hex(int(total_len))
        # Compute command size
        # header(10) + handle(4) + authSize(4) + authEntry + params(4)
        size_bytes = 10 + 4 + 4 + len(bytes.fromhex(auth_entry)) + 4
        size_hex = _u32_be_hex(size_bytes)
        bytestring = (
            f"{tag}"
            f"{size_hex}"
            f"{cc}"
            f"{handle_hex}"
            f"{auth_area_size_hex}"
            f"{auth_entry}"
            f"{params_hex}"
        )
        bytestream = bytes.fromhex(bytestring)
        print(f"Sending HashSignStart(total_len={total_len})...")
        self.uart.send_bytes(bytestream)

        print(f"Waiting for HashSignStart(total_len={total_len}) answer...")
        self.wait_for_ready_signal()
        result = self.read_tpm_response(timeout=3600)

        if not result:
            raise RuntimeError("Failed to get HashSignStart() answer, aborting")
        print("HashSignStart() response:\n", " ".join(f"{b:02X}" for b in result))

        rc = int.from_bytes(result[6:10], "big")
        if rc != 0:
            raise RuntimeError(f"HashSignStart failed rc=0x{rc:08X}")

        seq_handle = self.extract_first_handle_from_response(result)
        print(f"HashSignStart OK, sequenceHandle=0x{seq_handle:08X}")
        return seq_handle

    def sequence_update_cmd(self, seq_handle: int, chunk: bytes) -> None:
        # TPM2_SequenceUpdate: ST_SESSIONS, 1 in-handle (sequence), auth for the handle, TPM2B_MAX_BUFFER
        tag = "80 02"  # TPM_ST_SESSIONS
        cc = _u32_be_hex(TPM_CC_SequenceUpdate)
        handle_hex = _u32_be_hex(seq_handle)

        # RS_PW auth for the sequence handle (empty auth value set by start)
        auth_entry = "40000009"  # TPM_RS_PW
        auth_entry += "0000"  # nonce size = 0
        auth_entry += "00"  # session attributes
        auth_entry += "0000"  # hmac size = 0
        auth_area_size_hex = _u32_be_hex(len(bytes.fromhex(auth_entry)))

        # TPM2B_MAX_BUFFER
        buf_hex = _u16_be_hex(len(chunk)) + _bytes_hex(chunk)

        # header(10) + handle(4) + authSize(4) + authEntry + buffer(2+N)
        size_bytes = 10 + 4 + 4 + len(bytes.fromhex(auth_entry)) + 2 + len(chunk)
        size_hex = _u32_be_hex(size_bytes)

        hex_cmd = (
            f"{tag}{size_hex}{cc}{handle_hex}{auth_area_size_hex}{auth_entry}{buf_hex}"
        )
        bytestream = bytes.fromhex(hex_cmd)

        print(f"Sending SequenceUpdate command...")
        self.uart.send_bytes(bytestream)
        print(f"Waiting for SequenceUpdate answer...")
        self.wait_for_ready_signal()
        result = self.read_tpm_response(timeout=3600)

        if not result:
            raise RuntimeError("Failed to get SequenceUpdate() answer, aborting")
        print("SequenceUpdate() response:\n", " ".join(f"{b:02X}" for b in result))

        rc = int.from_bytes(result[6:10], "big")
        if rc != 0:
            raise RuntimeError(f"SequenceUpdate failed rc=0x{rc:08X}")

    def hashsign_finish_cmd(self, seq_handle: int) -> bytes:
        # TPM2_HashSignFinish: ST_SESSIONS, 1 in-handle (sequence), auth for the handle, no params
        tag = "80 02"
        cc = _u32_be_hex(TPM_CC_HashSignFinish)
        handle_hex = _u32_be_hex(seq_handle)
        auth_entry = "40000009" + "0000" + "00" + "0000"
        auth_area_size_hex = _u32_be_hex(len(bytes.fromhex(auth_entry)))
        size_bytes = 10 + 4 + 4 + len(bytes.fromhex(auth_entry))
        size_hex = _u32_be_hex(size_bytes)
        bytestring = f"{tag}{size_hex}{cc}{handle_hex}{auth_area_size_hex}{auth_entry}"
        bytestream = bytes.fromhex(bytestring)

        print("Sending HashSignFinish...")
        self.uart.send_bytes(bytestream)
        print("Waiting for HashSignFinish response...")
        self.wait_for_ready_signal()
        result = self.read_tpm_response(timeout=3600)

        if not result:
            raise RuntimeError("Failed to get HashSignFinish() answer, aborting")
        print("HashSignFinish() response:\n", " ".join(f"{b:02X}" for b in result))

        rc = int.from_bytes(result[6:10], "big")
        if rc != 0:
            raise RuntimeError(f"HashSignFinish failed rc=0x{rc:08X}")

        # Skip parameterSize for ST_SESSIONS responses
        off = _sessions_param_offset(result, response_handle_count=0)

        # TPMT_SIGNATURE
        sigAlg = int.from_bytes(result[off : off + 2], "big")
        off += 2
        hashAlg = int.from_bytes(result[off : off + 2], "big")
        off += 2
        sig_len = int.from_bytes(result[off : off + 2], "big")
        off += 2
        sig_bytes = result[off : off + sig_len]

        print(
            f"HashSignFinish OK: sigAlg=0x{sigAlg:04X}, hashAlg=0x{hashAlg:04X}, sig_len={sig_len}"
        )
        return sig_bytes
    
    def hashverify_start_cmd(self, key_handle: int, total_len: int, signature: bytes) -> int:
        # No authorization required (public key); use ST_NO_SESSIONS
        tag = "80 01"  # TPM_ST_NO_SESSIONS
        cc = _u32_be_hex(TPM_CC_HashVerifyStart)

        handle_hex = _u32_be_hex(key_handle)
        total_hex = _u32_be_hex(int(total_len))
        sig_param_hex = self.build_dilithium_signature_param(signature)

        # header(10) + handle(4) + params(totalLen 4 + TPMT_SIGNATURE)
        size_bytes = 10 + 4 + 4 + len(bytes.fromhex(sig_param_hex))
        size_hex = _u32_be_hex(size_bytes)

        bytestring = f"{tag}{size_hex}{cc}{handle_hex}{total_hex}{sig_param_hex}"
        bytestream = bytes.fromhex(bytestring)

        print(f"Sending HashVerifyStart(total_len={total_len})...")
        self.uart.send_bytes(bytestream)
        print(f"Waiting for HashVerifyStart answer...")
        self.wait_for_ready_signal()
        rsp = self.read_tpm_response(timeout=3600)
        if not rsp:
            raise RuntimeError("Failed to get HashVerifyStart() answer, aborting")
        print("HashVerifyStart() response:\n", " ".join(f"{b:02X}" for b in rsp))

        rc = int.from_bytes(rsp[6:10], "big")
        if rc != 0:
            raise RuntimeError(f"HashVerifyStart failed rc=0x{rc:08X}")

        seq_handle = self.extract_first_handle_from_response(rsp)
        print(f"HashVerifyStart OK, sequenceHandle=0x{seq_handle:08X}")
        return seq_handle

    def hashverify_finish_cmd(self, seq_handle: int):
        # Mirror HashSignFinish (use ST_SESSIONS with empty RS_PW on the sequence)
        tag = "80 02"  # TPM_ST_SESSIONS
        cc = _u32_be_hex(TPM_CC_HashVerifyFinish)
        handle_hex = _u32_be_hex(seq_handle)

        # RS_PW auth with empty HMAC
        auth_entry = "40000009" + "0000" + "00" + "0000"
        auth_area_size_hex = _u32_be_hex(len(bytes.fromhex(auth_entry)))

        size_bytes = 10 + 4 + 4 + len(bytes.fromhex(auth_entry))
        size_hex = _u32_be_hex(size_bytes)

        bytestring = f"{tag}{size_hex}{cc}{handle_hex}{auth_area_size_hex}{auth_entry}"
        bytestream = bytes.fromhex(bytestring)

        print("Sending HashVerifyFinish...")
        self.uart.send_bytes(bytestream)
        print("Waiting for HashVerifyFinish response...")
        self.wait_for_ready_signal()
        rsp = self.read_tpm_response(timeout=3600)
        if not rsp:
            raise RuntimeError("Failed to get HashVerifyFinish() answer, aborting")
        print("HashVerifyFinish() response:\n", " ".join(f"{b:02X}" for b in rsp))

        rc = int.from_bytes(rsp[6:10], "big")
        if rc != 0:
            raise RuntimeError(f"HashVerifyFinish failed rc=0x{rc:08X}")

        # Parse TPMT_TK_VERIFIED from response parameters
        off = _sessions_param_offset(rsp, response_handle_count=0)
        tag_val = int.from_bytes(rsp[off : off + 2], "big"); off += 2
        hierarchy = int.from_bytes(rsp[off : off + 4], "big"); off += 4
        dsz = int.from_bytes(rsp[off : off + 2], "big"); off += 2
        digest = rsp[off : off + dsz]

        print(
            f"HashVerifyFinish OK: ticket.tag=0x{tag_val:04X}, hierarchy=0x{hierarchy:08X}, digestLen={dsz}"
        )
        return (tag_val, hierarchy, digest)

    def run_hashsign_flow(self, message: bytes, chunk_size: int = 256) -> bytes:
        print("Running HashSignFlow...")
        resp = self.create_primary_dilithium_cmd()
        key_handle = self.extract_first_handle_from_response(resp)
        print(f"Dilithium key handle = 0x{key_handle:08X}")

        seq = self.hashsign_start_cmd(
            key_handle=key_handle, total_len=len(message), key_pw=b"abcd"
        )

        # Print and save message
        ts = time.strftime("%Y%m%d-%H%M%S")
        print(f"Message ({len(message)} bytes): {message.hex().upper()}")
        _write_hex_file(f"hashsign_msg_{ts}.hex", message)

        sent = 0
        while sent < len(message):
            chunk = message[sent : sent + chunk_size]
            self.sequence_update_cmd(seq, chunk)
            sent += len(chunk)
        assert sent == len(message)

        sig = self.hashsign_finish_cmd(seq)
        print(f"Signature ({len(sig)} bytes): {sig.hex().upper()}")
        _write_hex_file(f"hashsign_sig_{ts}.hex", sig)
        return sig
    
    def run_dilithium_flow(self, message: bytes, chunk_size: int = 256) -> bool:
        print("Running HashSign + HashVerify flow...")
        resp = self.create_primary_dilithium_cmd()
        key_handle = self.extract_first_handle_from_response(resp)
        print(f"Dilithium key handle = 0x{key_handle:08X}")

        # HashSign sequence
        seq_sign = self.hashsign_start_cmd(
            key_handle=key_handle, total_len=len(message), key_pw=b"abcd"
        )
        ts = time.strftime("%Y%m%d-%H%M%S")
        print(f"Message ({len(message)} bytes): {message.hex().upper()}")
        _write_hex_file(f"hashsign_msg_{ts}.hex", message)

        sent = 0
        while sent < len(message):
            chunk = message[sent : sent + chunk_size]
            self.sequence_update_cmd(seq_sign, chunk)
            sent += len(chunk)
        sig = self.hashsign_finish_cmd(seq_sign)
        print(f"Signature ({len(sig)} bytes): {sig.hex().upper()}")
        _write_hex_file(f"hashsign_sig_{ts}.hex", sig)

        # HashVerify sequence
        seq_verify = self.hashverify_start_cmd(
            key_handle=key_handle, total_len=len(message), signature=sig
        )
        sent = 0
        while sent < len(message):
            chunk = message[sent : sent + chunk_size]
            self.sequence_update_cmd(seq_verify, chunk)
            sent += len(chunk)
        ticket = self.hashverify_finish_cmd(seq_verify)
        _write_hex_file(f"hashverify_ticket_{ts}.hex", ticket[2])
        print("Verify succeeded and ticket stored.")
        return True

    def test(self):
        print("\nWaiting for SoC to signal it is READY...")
        self.wait_for_ready_signal()
        self.startup_cmd(startup_type="CLEAR")
        msg = os.urandom(640)
        return self.run_dilithium_flow(message=msg, chunk_size=256)

    def repl(self):
        print("\nWaiting for SoC to signal it is READY...")
        self.wait_for_ready_signal()
        print("\nInteractive TPM tester. Type 'help' for options.")
        # Optional startup first
        try:
            ans = input("Send TPM2_Startup first? [Y/n] ").strip().lower()
        except EOFError:
            ans = "y"
        if ans in ("", "y", "yes"):
            try:
                su = input("Startup type? [CLEAR/state] ").strip().upper() or "CLEAR"
            except EOFError:
                su = "CLEAR"
            self.startup_cmd(startup_type="CLEAR" if su != "STATE" else "STATE")

        while True:
            try:
                cmd = (
                    input(
                        "\nCommand [startup|get_random|create_primary|complete_hashsign|complete_dilithium|help|quit]: "
                    )
                    .strip()
                    .lower()
                )
            except EOFError:
                cmd = "quit"

            if cmd in ("quit", "exit", "q"):
                print("Exiting.")
                return True
            if cmd in ("help", "?"):
                print("Available commands:")
                print("  startup            - send TPM2_Startup (choose CLEAR or STATE)")
                print("  get_random         - request N random bytes")
                print("  create_primary     - send CreatePrimary sample command")
                print("  complete_hashsign  - do complete HashSign Dilithium flow")
                print("  complete_dilithium - sign then verify the same message")
                print("  quit               - exit")
                continue

            if cmd == "startup":
                try:
                    su = (
                        input("Startup type? [CLEAR/state] ").strip().upper() or "CLEAR"
                    )
                except EOFError:
                    su = "CLEAR"
                self.startup_cmd(startup_type="CLEAR" if su != "STATE" else "STATE")
                continue

            if cmd == "get_random":
                try:
                    n = int(input("How many bytes? [32] ").strip() or "32")
                except Exception:
                    n = 32
                self.get_random_cmd(num_bytes=n)
                continue

            if cmd == "create_primary":
                try:
                    algo = int(input("ECC (1) or Dilithium (2)? [1] ").strip() or "1")
                except Exception:
                    algo = 1

                if algo == 1:
                    self.create_primary_cmd()
                elif algo == 2:
                    self.create_primary_dilithium_cmd()
                continue

            if cmd in ("complete_hashsign"):
                # Simple demo message; adjust or prompt as needed
                msg = os.urandom(640)
                self.run_hashsign_flow(message=msg, chunk_size=256)
                continue

            if cmd in ("complete_dilithium"):
                msg = os.urandom(640)
                self.run_dilithium_flow(message=msg, chunk_size=256)
                continue

            print("Unknown command. Type 'help'.")


def parse_args():
    parser = argparse.ArgumentParser(description="TPM tester over UART or TCP")
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--serial",
        dest="use_serial",
        action="store_true",
        help="Use serial connection instead of tcp",
    )
    mode_group.add_argument(
        "--tcp",
        dest="use_serial",
        action="store_false",
        help="Use TCP connection",
    )
    parser.set_defaults(use_serial=False)

    parser.add_argument(
        "--tcp-port",
        type=int,
        default=4327,
        help="TCP port for TCP mode (default: 4327)",
    )
    parser.add_argument(
        "--serial-dev",
        type=str,
        default="/dev/ttyUSB1",
        help="Serial device path for serial mode (default: /dev/ttyUSB1)",
    )
    parser.add_argument(
        "--baud",
        type=int,
        default=115200,
        help="Baud rate for serial mode (default: 115200)",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Interactive mode (menu-driven).",
    )
    parser.add_argument(
        "--log",
        action="store_true",
        help="Route UART logs to a timestamped file.",
    )
    parser.add_argument(
        "--log-name",
        type=str,
        default="uart-log",
        help="Base filename for UART logs (timestamp and .log will be appended).",
    )
    return parser.parse_args()


def main():
    print(f"\n=== Testing TPM ===")
    args = parse_args()
    use_serial = args.use_serial
    tcp_port = args.tcp_port
    serial_dev = args.serial_dev
    baud = args.baud

    # Build timestamped log path if requested
    log_path = None
    if getattr(args, "log", False):
        ts = time.strftime("%Y%m%d-%H%M%S")
        base = args.log_name
        log_path = f"{base}-{ts}.log"

    try:
        # Create UART connection
        if use_serial:
            uart = UARTConnection(
                mode="serial",
                serial_port=serial_dev,
                baudrate=baud,
                serial_timeout=0.1,
                debug=True,
                log_path=log_path,
            )
        else:
            uart = UARTConnection(
                mode="tcp",
                tcp_host="localhost",
                tcp_port=tcp_port,
                tcp_connect_timeout=600,
                debug=True,
                log_path=log_path,
            )

        tester = TpmTester(uart=uart)
        if args.interactive:
            success = tester.repl()
        else:
            success = tester.test()

        print(f"\n{'✅ Test passed!' if success else '❌ Test failed!'}")

    except Exception as e:
        print(f"Test failed: {e}")
    finally:
        if "uart" in locals():
            uart.close()

    return


if __name__ == "__main__":
    main()
