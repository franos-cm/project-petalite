import time
import argparse
from uart import UARTConnection


class TpmTester:
    """Dilithium test suite - uses UART connection for testing"""

    def __init__(self):
        pass

    def wait_for_ready_signal(self):
        while not self.uart.wait_for_ready(timeout=180):
            pass

    def read_tpm_response(self, timeout):
        header = self.uart.wait_for_bytes(num_bytes=10, timeout=timeout)
        response_size = int.from_bytes(header[2:6], byteorder="big")
        body = self.uart.wait_for_bytes(num_bytes=(response_size - 10), timeout=timeout)
        return header + body

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
        return result

    def create_primary_dilithium_cmd(self):
        # TPM2_CreatePrimary with Dilithium L2
        bytestring = (
            # ===== Header =====
            "80 02"              # TPM_ST_SESSIONS
            "00 00 00 41"        # command size = 63 bytes
            "00 00 01 31"        # TPM_CC_CreatePrimary
            # ===== Handle =====
            "40 00 00 01"        # TPM_RH_OWNER
            # ===== AuthArea =====
            "00 00 00 09"        # authArea size = 9
            "40 00 00 09"        # TPM_RS_PW
            "00 00"              # nonce size = 0
            "00"                 # session attributes
            "00 00"              # hmac size = 0 (empty owner auth)
            # ===== inSensitive (TPM2B_SENSITIVE_CREATE) =====
            "00 08"              # total size = 8
            "00 04"              # userAuth size = 4
            "61 62 63 64"        # "abcd"
            "00 00"              # sensitive.data size = 0
            # ===== inPublic (TPM2B_PUBLIC) =====
            "00 14"              # TPMT_PUBLIC size = 20
            "00 72"              # type = TPM_ALG_DILITHIUM (0x0072)
            "00 0B"              # nameAlg = TPM_ALG_SHA256 (0x000B)
            "00 04 04 72"        # objectAttributes = 0x00040472
            "00 00"              # authPolicy size = 0
            # ----- TPMS_DILITHIUM_PARMS -----
            "00 10"              # parameters.symmetric.algorithm = TPM_ALG_NULL
            "00 10"              # parameters.scheme.scheme = TPM_ALG_NULL
            "00 02"              # securityLevel = 2
            "00 0B"              # nameHashAlg = TPM_ALG_SHA256
            # ----- unique -----
            "00 00"              # unique (TPM2B) size = 0
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
            raise RuntimeError("Failed to get create_primary_dilithium() answer, aborting")
        print("create_primary_dilithium() response:\n", " ".join(f"{b:02X}" for b in result))
        return result

    def compare(self, name, expected, received, res_list):
        if expected != received:
            print(f"Mismatch between expected and received [{name}]")
            res_list.append((name, expected, received))

    def test(self):
        self.wait_for_ready_signal()
        self.startup_cmd()
        self.create_primary_cmd()
        return True

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
                    input("\nCommand [startup|get_random|create_primary|help|quit]: ")
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
                print("  startup        - send TPM2_Startup (choose CLEAR or STATE)")
                print("  get_random     - request N random bytes")
                print("  create_primary - send CreatePrimary sample command")
                print("  quit           - exit")
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
        tester = TpmTester()

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

        # Ensure REPL has a bound UART
        tester.uart = uart

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
