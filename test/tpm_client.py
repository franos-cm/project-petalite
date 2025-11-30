import time
from typing import Optional
from uart import UARTConnection
from tpm_utils import (
    TPM_ALG_ECC,
    TPM_ALG_DILITHIUM,
    TPM_CC_HashSignStart,
    TPM_CC_HashSignFinish,
    TPM_CC_SequenceUpdate,
    TPM_CC_HashVerifyStart,
    TPM_CC_HashVerifyFinish,
    u32_be_hex as _u32_be_hex,
    u16_be_hex as _u16_be_hex,
    bytes_hex as _bytes_hex,
    sessions_param_offset as _sessions_param_offset,
    parse_createprimary_outpublic as _parse_createprimary_outpublic,
    build_dilithium_signature_param as _build_dilithium_signature_param,
)

# Latency protocol constants (mirror firmware)
TPM_LATENCY_RECORD_LEN = 8  # 8-byte big-endian cycle count


class TPMClient:
    """Minimal TPM client for Dilithium demo; uses UARTConnection directly."""

    def __init__(
        self,
        uart: UARTConnection,
        on_command=None,
        on_response=None,
        latency_metrics: bool = False,  # default OFF, match tpm.py
    ):
        self.uart = uart
        self._on_command = on_command
        self._on_response = on_response
        # When False, fall back to legacy "no-latency" behavior
        self.latency_metrics = bool(latency_metrics)

    # ---- internal helpers ----
    def _emit_command(self, name: str, data: bytes, meta: dict | None = None):
        if self._on_command:
            try:
                self._on_command(name, data, meta or {})
            except Exception:
                pass

    def _emit_response(self, name: str, data: bytes, meta: dict | None = None):
        if self._on_response:
            try:
                self._on_response(name, data, meta or {})
            except Exception:
                pass

    def wait_for_ready_signal(self):
        while not self.uart.wait_for_ready(timeout=180):
            pass

    def _read_ready_and_bytes(self, num_bytes: int, timeout: float) -> bytes:
        """Wait for a READY marker, then read num_bytes."""
        if not self.uart.wait_for_ready(timeout=timeout):
            raise RuntimeError("Timeout waiting for READY marker from SoC")
        return self.uart.wait_for_bytes(num_bytes=num_bytes, timeout=timeout)

    def _read_latency_and_response(self, timeout: float) -> tuple[int, bytes]:
        """
        Firmware protocol:
          1) READY + latency record (8 bytes, big-endian cycles)
          2) READY + TPM response (header+body)
        Returns (latency_cycles, response_bytes).
        """
        # 1) Latency record
        lat_raw = self._read_ready_and_bytes(TPM_LATENCY_RECORD_LEN, timeout)
        if len(lat_raw) != TPM_LATENCY_RECORD_LEN:
            raise RuntimeError(
                f"Incomplete latency record ({len(lat_raw)} bytes, expected {TPM_LATENCY_RECORD_LEN})"
            )
        # Entire 8 bytes are the cycle count
        lat_cycles = int.from_bytes(lat_raw, byteorder="big", signed=False)

        # 2) TPM response: header then body
        header = self._read_ready_and_bytes(10, timeout)
        if len(header) != 10:
            raise RuntimeError("Short TPM response header")
        response_size = int.from_bytes(header[2:6], byteorder="big")
        if response_size < 10:
            raise RuntimeError(f"Invalid TPM response size {response_size}")
        body = self.uart.wait_for_bytes(num_bytes=(response_size - 10), timeout=timeout)
        if len(body) != (response_size - 10):
            raise RuntimeError("Short TPM response body")
        return lat_cycles, header + body

    def read_tpm_response(self, timeout):
        """
        Read TPM response.
        If latency_metrics is True:
          READY + latency record, READY + response.
        Else:
          just header+body (legacy behavior).
        """
        if self.latency_metrics:
            lat_cycles, rsp = self._read_latency_and_response(timeout)
            print(f"TPM command latency: {lat_cycles} cycles")
            return rsp

        # Legacy: no READY / latency parsing here.
        # NOTE: with current firmware (which always sends READY+latency+READY+response),
        # using this path will desync the stream.
        header = self.uart.wait_for_bytes(num_bytes=10, timeout=timeout)
        if not header or len(header) < 10:
            raise RuntimeError("Short TPM response header")
        response_size = int.from_bytes(header[2:6], "big")
        body = self.uart.wait_for_bytes(num_bytes=(response_size - 10), timeout=timeout)
        if not body or len(body) < (response_size - 10):
            raise RuntimeError("Short TPM response body")
        return header + body

    def extract_first_handle_from_response(self, rsp: bytes) -> int:
        if len(rsp) < 14:
            raise RuntimeError("Response too short to contain a handle")
        return int.from_bytes(rsp[10:14], byteorder="big")

    def build_dilithium_signature_param(self, sig: bytes) -> str:
        return _build_dilithium_signature_param(sig)

    # ---- commands ----
    def startup_cmd(self, startup_type: str = "CLEAR"):
        st = (startup_type or "").strip().upper()
        if st in ("0", "CLEAR", ""):
            su_val = "0000"
        elif st in ("1", "STATE"):
            su_val = "0001"
        else:
            su_val = "0000"
        bytestring = f"80010000000C00000144{su_val}"
        bytestream = bytes.fromhex(bytestring)
        print("Sending Startup command...")
        self._emit_command("Startup", bytestream, {"handles_out": 0})
        self.uart.send_bytes(bytestream)
        print("Waiting for Startup answer...")
        # NOTE: if latency_metrics=False and you are on new firmware, this will desync.
        result = self.read_tpm_response(timeout=3600)
        if not result:
            raise RuntimeError("Failed to get startup answer, aborting")
        print("Startup cmd response received")
        self._emit_response("Startup", result, {"handles_out": 0})
        return result

    def get_random_cmd(self, num_bytes: int = 32):
        num_bytes = max(1, min(0xFFFF, int(num_bytes)))
        bytestring = f"80010000000C0000017B{num_bytes:04X}"
        bytestream = bytes.fromhex(bytestring)
        print(f"Sending get_random_bytes({num_bytes}) command...")
        self._emit_command("GetRandom", bytestream, {"handles_out": 0})
        self.uart.send_bytes(bytestream)
        print("Waiting for get_random answer...")
        result = self.read_tpm_response(timeout=3600)
        if not result:
            raise RuntimeError("Failed to get get_random_bytes() answer, aborting")
        print("get_random_bytes() response received")
        self._emit_response("GetRandom", result, {"handles_out": 0})
        return result

    def create_primary_dilithium_cmd(self):
        # Exact command aligned with working tpm.py tester (avoid extra trailing zeros)
        hex_cmd = (
            "80020000003E0000013140000001000000094000000900000000000008000461626364"
            "000000110072000B00040472000000100010020000000000000000"
        )
        bytestream = bytes.fromhex(hex_cmd)
        print("Sending create_primary_dilithium() command...")
        self._emit_command("CreatePrimary(Dilithium)", bytestream, {"handles_out": 1})
        self.uart.send_bytes(bytestream)
        print("Waiting for create_primary_dilithium() answer...")
        result = self.read_tpm_response(timeout=3600)
        if not result:
            raise RuntimeError("Failed to get create_primary_dilithium() answer, aborting")
        print("create_primary_dilithium() response received")
        self._emit_response("CreatePrimary(Dilithium)", result, {"handles_out": 1})
        return result

    def hashsign_start_cmd(self, key_handle: int, total_len: int, key_pw: bytes = b"abcd") -> int:
        tag = "80 02"
        cc = _u32_be_hex(TPM_CC_HashSignStart)
        handle_hex = _u32_be_hex(key_handle)
        auth_entry = "40000009" + "0000" + "00" + _u16_be_hex(len(key_pw)) + _bytes_hex(key_pw)
        auth_area_size_hex = _u32_be_hex(len(bytes.fromhex(auth_entry)))
        params_hex = _u32_be_hex(int(total_len))
        size_bytes = 10 + 4 + 4 + len(bytes.fromhex(auth_entry)) + 4
        size_hex = _u32_be_hex(size_bytes)
        bytestring = f"{tag}{size_hex}{cc}{handle_hex}{auth_area_size_hex}{auth_entry}{params_hex}"
        bytestream = bytes.fromhex(bytestring)
        print(f"Sending HashSignStart(total_len={total_len})...")
        self._emit_command("HashSignStart", bytestream, {"handles_out": 1})
        self.uart.send_bytes(bytestream)
        print("Waiting for HashSignStart answer...")
        result = self.read_tpm_response(timeout=3600)
        if not result:
            raise RuntimeError("Failed to get HashSignStart() answer, aborting")
        print("HashSignStart() response received")
        self._emit_response("HashSignStart", result, {"handles_out": 1})
        rc = int.from_bytes(result[6:10], "big")
        if rc != 0:
            raise RuntimeError(f"HashSignStart failed rc=0x{rc:08X}")
        seq_handle = self.extract_first_handle_from_response(result)
        return seq_handle

    def sequence_update_cmd(self, seq_handle: int, chunk: bytes) -> None:
        tag = "80 02"
        cc = _u32_be_hex(TPM_CC_SequenceUpdate)
        handle_hex = _u32_be_hex(seq_handle)
        auth_entry = "40000009" + "0000" + "00" + "0000"
        auth_area_size_hex = _u32_be_hex(len(bytes.fromhex(auth_entry)))
        buf_hex = _u16_be_hex(len(chunk)) + _bytes_hex(chunk)
        size_bytes = 10 + 4 + 4 + len(bytes.fromhex(auth_entry)) + 2 + len(chunk)
        size_hex = _u32_be_hex(size_bytes)
        hex_cmd = f"{tag}{size_hex}{cc}{handle_hex}{auth_area_size_hex}{auth_entry}{buf_hex}"
        bytestream = bytes.fromhex(hex_cmd)
        print("Sending SequenceUpdate command...")
        self._emit_command("SequenceUpdate", bytestream, {"handles_out": 0})
        self.uart.send_bytes(bytestream)
        print("Waiting for SequenceUpdate answer...")
        result = self.read_tpm_response(timeout=3600)
        if not result:
            raise RuntimeError("Failed to get SequenceUpdate() answer, aborting")
        print("SequenceUpdate() response received")
        self._emit_response("SequenceUpdate", result, {"handles_out": 0})
        rc = int.from_bytes(result[6:10], "big")
        if rc != 0:
            raise RuntimeError(f"SequenceUpdate failed rc=0x{rc:08X}")

    def hashsign_finish_cmd(self, seq_handle: int) -> bytes:
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
        self._emit_command("HashSignFinish", bytestream, {"handles_out": 0})
        self.uart.send_bytes(bytestream)
        print("Waiting for HashSignFinish response...")
        result = self.read_tpm_response(timeout=3600)
        if not result:
            raise RuntimeError("Failed to get HashSignFinish() answer, aborting")
        print("HashSignFinish() response received")
        self._emit_response("HashSignFinish", result, {"handles_out": 0})
        rc = int.from_bytes(result[6:10], "big")
        if rc != 0:
            raise RuntimeError(f"HashSignFinish failed rc=0x{rc:08X}")
        off = _sessions_param_offset(result, response_handle_count=0)
        sigAlg = int.from_bytes(result[off : off + 2], "big"); off += 2
        hashAlg = int.from_bytes(result[off : off + 2], "big"); off += 2
        sig_len = int.from_bytes(result[off : off + 2], "big"); off += 2
        sig_bytes = result[off : off + sig_len]
        return sig_bytes

    def hashverify_start_cmd(self, key_handle: int, total_len: int, signature: bytes) -> int:
        tag = "80 01"
        cc = _u32_be_hex(TPM_CC_HashVerifyStart)
        handle_hex = _u32_be_hex(key_handle)
        total_hex = _u32_be_hex(int(total_len))
        sig_param_hex = self.build_dilithium_signature_param(signature)
        size_bytes = 10 + 4 + 4 + len(bytes.fromhex(sig_param_hex))
        size_hex = _u32_be_hex(size_bytes)
        bytestring = f"{tag}{size_hex}{cc}{handle_hex}{total_hex}{sig_param_hex}"
        bytestream = bytes.fromhex(bytestring)
        print(f"Sending HashVerifyStart(total_len={total_len})...")
        self._emit_command("HashVerifyStart", bytestream, {"handles_out": 1})
        self.uart.send_bytes(bytestream)
        print("Waiting for HashVerifyStart answer...")
        rsp = self.read_tpm_response(timeout=3600)
        if not rsp:
            raise RuntimeError("Failed to get HashVerifyStart() answer, aborting")
        print("HashVerifyStart() response received")
        self._emit_response("HashVerifyStart", rsp, {"handles_out": 1})
        rc = int.from_bytes(rsp[6:10], "big")
        if rc != 0:
            raise RuntimeError(f"HashVerifyStart failed rc=0x{rc:08X}")
        seq_handle = self.extract_first_handle_from_response(rsp)
        return seq_handle

    def hashverify_finish_cmd(self, seq_handle: int):
        tag = "80 02"
        cc = _u32_be_hex(TPM_CC_HashVerifyFinish)
        handle_hex = _u32_be_hex(seq_handle)
        auth_entry = "40000009" + "0000" + "00" + "0000"
        auth_area_size_hex = _u32_be_hex(len(bytes.fromhex(auth_entry)))
        size_bytes = 10 + 4 + 4 + len(bytes.fromhex(auth_entry))
        size_hex = _u32_be_hex(size_bytes)
        bytestring = f"{tag}{size_hex}{cc}{handle_hex}{auth_area_size_hex}{auth_entry}"
        bytestream = bytes.fromhex(bytestring)
        print("Sending HashVerifyFinish...")
        self._emit_command("HashVerifyFinish", bytestream, {"handles_out": 0})
        self.uart.send_bytes(bytestream)
        print("Waiting for HashVerifyFinish response...")
        rsp = self.read_tpm_response(timeout=3600)
        if not rsp:
            raise RuntimeError("Failed to get HashVerifyFinish() answer, aborting")
        print("HashVerifyFinish() response received")
        self._emit_response("HashVerifyFinish", rsp, {"handles_out": 0})
        rc = int.from_bytes(rsp[6:10], "big")
        if rc != 0:
            raise RuntimeError(f"HashVerifyFinish failed rc=0x{rc:08X}")
        off = _sessions_param_offset(rsp, response_handle_count=0)
        tag_val = int.from_bytes(rsp[off : off + 2], "big"); off += 2
        hierarchy = int.from_bytes(rsp[off : off + 4], "big"); off += 4
        dsz = int.from_bytes(rsp[off : off + 2], "big"); off += 2
        digest = rsp[off : off + dsz]
        return (tag_val, hierarchy, digest)
