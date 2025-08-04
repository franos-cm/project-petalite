import os
import time
import struct

from kat_loader import TestVectorReader
from uart import UARTConnection
from utils import (
    DilithiumOp,
    ResponseHeader,
    DILITHIUM_CMD_KEYGEN,
    DILITHIUM_CMD_VERIFY,
    DILITHIUM_CMD_SIGN,
)


class DilithiumTester:
    """Dilithium test suite - uses UART connection for testing"""

    def __init__(self):
        pass

    def pre_op_handshake(self):
        while not self.uart.wait_for_ready(timeout=1):
            self.uart.send_sync()
        self.uart.send_start()
        if not self.uart.wait_for_ack():
            raise RuntimeError("Did not get START ACK")

    def send_request_header(self, cmd, msg_len: int, sec_level: int):
        # Step 2: Send header (cmd + sec_lvl + msg_len)
        print("Sending header...")
        msg_len = int(msg_len.hex(), 16)
        header = struct.pack("<BBI", cmd, sec_level, msg_len)
        self.uart.send_bytes(header)

        # Step 3: Wait for header ACK
        print("Waiting for header ACK...")
        if not self.uart.wait_for_ack():
            raise RuntimeError("Failed to get header ACK, aborting")

    def test_verify_operation(self, test_vector: dict):
        """Test the complete Dilithium verify operation"""
        try:
            # Step 1: Send signature components in order
            print("1. Sending signature components...")

            # Send Rho
            self.uart.send_in_chunks(test_vector["rho"], data_name="RHO")

            # Send C
            self.uart.send_in_chunks(test_vector["c"], data_name="C")

            # Send Z
            self.uart.send_in_chunks(test_vector["z"], data_name="Z")

            # Send T1
            self.uart.send_in_chunks(test_vector["t1"], data_name="T1")

            # Send H
            self.uart.send_in_chunks(test_vector["h"], data_name="H")

            # Send msg
            msg_len = int(test_vector["msg_len"].hex(), 16)
            self.uart.send_in_chunks(test_vector["msg"][:msg_len], data_name="MSG")
            print("✓ All data sent successfully!")

            # Give some time to see any firmware responses
            print("Waiting for response...")
            rsp = ResponseHeader(self.uart.get_response_header())
            print("Verify operation completed. Check firmware output for results.")

            self.uart.flush_received_data()
            return (rsp.verify_res == 1) and (rsp.rsp_code == 0)

        except Exception as e:
            print(f"❌ Error during verify operation: {e}")
            return False

    def test_keygen_operation(self, test_vector: dict):
        """Test the complete Dilithium verify operation"""
        try:
            rho_size = len(test_vector["rho"])
            t1_size = len(test_vector["t1"])
            k_size = len(test_vector["k"])
            tr_size = len(test_vector["tr"])
            s1_size = len(test_vector["s1"])
            s2_size = len(test_vector["s2"])
            t0_size = len(test_vector["t0"])
            payload_size = (
                rho_size + t1_size + k_size + tr_size + s1_size + s2_size + t0_size
            )

            # Send seed
            self.uart.send_in_chunks(test_vector["seed"], data_name="SEED")
            print("✓ All data sent successfully!")

            # Give some time to see any firmware responses
            print("Waiting for response...")
            rsp = ResponseHeader(self.uart.get_response_header())
            print("Keygen operation completed. Check firmware output for results.")

            # Give some time to see any firmware responses
            rsp_data = self.uart.receive_in_chunks(
                total_bytes=payload_size, timeout_per_chunk=120
            )
            self.uart.flush_received_data()

            # TODO: change this, too ugly
            rho_received = rsp_data[:rho_size]
            k_received = rsp_data[rho_size : rho_size + k_size]
            s1_received = rsp_data[rho_size + k_size : rho_size + k_size + s1_size]
            s2_received = rsp_data[
                rho_size + k_size + s1_size : rho_size + k_size + s1_size + s2_size
            ]
            t1_received = rsp_data[
                rho_size
                + k_size
                + s1_size
                + s2_size : rho_size
                + k_size
                + s1_size
                + s2_size
                + t1_size
            ]
            t0_received = rsp_data[
                rho_size
                + k_size
                + s1_size
                + s2_size
                + t1_size : rho_size
                + k_size
                + s1_size
                + s2_size
                + t1_size
                + t0_size
            ]
            tr_received = rsp_data[
                rho_size
                + k_size
                + s1_size
                + s2_size
                + t1_size
                + t0_size : rho_size
                + k_size
                + s1_size
                + s2_size
                + t1_size
                + t0_size
                + tr_size
            ]

            # Check vals and write mismatches to file
            mismatches = []
            self.compare("rho", test_vector["rho"], rho_received, mismatches)
            self.compare("k", test_vector["k"], k_received, mismatches)
            self.compare("s1", test_vector["s1"], s1_received, mismatches)
            self.compare("s2", test_vector["s2"], s2_received, mismatches)
            self.compare("t1", test_vector["t1"], t1_received, mismatches)
            self.compare("t0", test_vector["t0"], t0_received, mismatches)
            self.compare("tr", test_vector["tr"], tr_received, mismatches)

            if mismatches:
                with open("keygen_mismatches.txt", "w") as f:
                    for name, expected, received in mismatches:
                        f.write(f"[{name.upper()}] Expected:\n{expected.hex()}\n")
                        f.write(f"[{name.upper()}] Received:\n{received.hex()}\n\n")
                print(f"❌ Mismatches detected! Written to keygen_mismatches.txt")
                success = False
            else:
                success = True
                return success

        except Exception as e:
            print(f"❌ Error during verify operation: {e}")
            return False

    def compare(self, name, expected, received, res_list):
        if expected != received:
            print(f"Mismatch between expected and received [{name}]")
            res_list.append((name, expected, received))

    def test(
        self,
        uart_conn: UARTConnection,
        operation: DilithiumOp,
        test_vectors: dict,
        sec_level: int,
    ):
        """Test multiple test vectors"""
        print(
            f"\n=== Testing {len(test_vectors)} Test Vectors (Security Level {sec_level}) ==="
        )

        self.uart = uart_conn
        success_count = 0
        for i in sorted(test_vectors.keys()):
            print(f"\n--- Test Vector {i} ---")
            test_vector = test_vectors[i]

            self.pre_op_handshake()
            if operation == DilithiumOp.KEYGEN:
                self.send_request_header(
                    DILITHIUM_CMD_KEYGEN,
                    msg_len=test_vector["msg_len"],
                    sec_level=sec_level,
                )
                result = self.test_keygen_operation(test_vector=test_vector)
            elif operation == DilithiumOp.SIGN:
                self.send_request_header(
                    DILITHIUM_CMD_SIGN,
                    msg_len=test_vector["msg_len"],
                    sec_level=sec_level,
                )
                result = self.test_verify_operation(test_vector=test_vector)
            elif operation == DilithiumOp.VERIFY:
                self.send_request_header(
                    DILITHIUM_CMD_VERIFY,
                    msg_len=test_vector["msg_len"],
                    sec_level=sec_level,
                )
                result = self.test_verify_operation(test_vector=test_vector)
            else:
                raise RuntimeError()

            if result:
                success_count += 1
                print(f"✅ Vector {i} passed")
            else:
                print(f"❌ Vector {i} failed")

            time.sleep(1)  # Brief pause between vectors

        print(f"\n=== Results: {success_count}/{len(test_vectors)} vectors passed ===")
        return success_count == len(test_vectors)


def main():
    print(f"\n=== Testing Dilithium ===")
    port = 4327
    dilithium_op = DilithiumOp.KEYGEN
    sec_level = 2
    initial_vec_index = 0
    vec_num = 1

    try:
        # Create test suite
        tester = DilithiumTester()

        print(f"Loading test vectors from files...")
        test_vectors = TestVectorReader.load_dilithium_vectors(
            base_path=os.path.join(os.getcwd(), "test", "KAT"),
            sec_level=sec_level,
            initial_vec_index=initial_vec_index,
            vec_num=vec_num,
        )

        # Create UART connection
        uart = UARTConnection(port=port, max_wait=600)

        success = tester.test(
            uart_conn=uart,
            operation=dilithium_op,
            sec_level=sec_level,
            test_vectors=test_vectors,
        )
        print(f"\n{'✅ Test passed!' if success else '❌ Test failed!'}")

    except Exception as e:
        print(f"Test failed: {e}")
    finally:
        if "uart" in locals():
            uart.close()

    return


if __name__ == "__main__":
    main()
