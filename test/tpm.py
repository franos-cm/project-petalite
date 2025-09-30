import time
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

    def startup_cmd(self):
        startup_string = "80010000000C000001440000"
        startup_bytestream = bytes.fromhex(startup_string)
        print("Sending startup command...")
        self.uart.send_bytes(startup_bytestream)
        time.sleep(1)

        print("Waiting for startup answer...")
        self.wait_for_ready_signal()
        result = self.uart.wait_for_bytes(num_bytes=10, timeout=40 * 60)

        if not result:
            raise RuntimeError("Failed to get startup answer, aborting")
        print("Startup cmd response:\n", " ".join(f"{b:02X}" for b in result))
        return result

    def get_random_cmd(self):
        getrandom_string = "80010000000C0000017B0020"  # 32 bytes
        getrandom_bytestream = bytes.fromhex(getrandom_string)
        print("Sending get_random_bytes() command...")
        self.uart.send_bytes(getrandom_bytestream)
        time.sleep(1)

        print("Waiting for get_random answer...")
        self.wait_for_ready_signal()
        result = self.uart.wait_for_bytes(num_bytes=32 + 12, timeout=40 * 60)

        if not result:
            raise RuntimeError("Failed to get get_random_bytes() answer, aborting")
        print("get_random_bytes() response:\n", " ".join(f"{b:02X}" for b in result))
        return result

    def create_primary_cmd(self):
        create_primary_cmd = (
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

        create_primary_bytestream = bytes.fromhex(create_primary_cmd.replace(" ", ""))
        print("Sending create_primary() command...")
        self.uart.send_bytes(create_primary_bytestream)
        time.sleep(1)

        print("Waiting for create_primary() answer...")
        self.wait_for_ready_signal()
        result = self.read_tpm_response(timeout=45 * 60)

        if not result:
            raise RuntimeError("Failed to get create_primary() answer, aborting")
        print("create_primary() response:\n", " ".join(f"{b:02X}" for b in result))
        return result

    def compare(self, name, expected, received, res_list):
        if expected != received:
            print(f"Mismatch between expected and received [{name}]")
            res_list.append((name, expected, received))

    def test_random(self):
        self.wait_for_ready_signal()
        self.startup_cmd()
        time.sleep(1)
        self.get_random_cmd()
        return True

    def test_create_primary(self):
        self.wait_for_ready_signal()
        self.startup_cmd()
        time.sleep(1)
        self.create_primary_cmd()
        return True

    def test(self, uart_conn: UARTConnection):
        self.uart = uart_conn
        result = self.test_create_primary()
        return result


def main():
    print(f"\n=== Testing TPM ===")
    # Choose connection mode here:
    use_serial = True  # set True to talk to real hardware over UART
    tcp_port = 4327
    serial_dev = "/dev/ttyUSB0"  # adjust to your board (/dev/ttyUSB*, /dev/ttyACM*)
    baud = 115200

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
            )
        else:
            uart = UARTConnection(
                mode="tcp",
                tcp_host="localhost",
                tcp_port=tcp_port,
                tcp_connect_timeout=600,
                debug=True,
            )

        success = tester.test(uart_conn=uart)
        print(f"\n{'✅ Test passed!' if success else '❌ Test failed!'}")

    except Exception as e:
        print(f"Test failed: {e}")
    finally:
        if "uart" in locals():
            uart.close()

    return


if __name__ == "__main__":
    main()
