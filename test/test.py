import os
import sys
import time
import struct

from utils import *
from kat_loader import TestVectorReader
from uart import UARTConnection


class DilithiumTester:
    """Dilithium test suite - uses UART connection for testing"""

    def __init__(self):
        pass

    def wait_for_ack(self, timeout=1500):
        """Wait for ACK byte from firmware and log time to receive"""
        start_time = time.perf_counter()
        if self.uart.wait_for_byte(DILITHIUM_ACK_BYTE, timeout):
            elapsed = time.perf_counter() - start_time
            print(f"[ACK] Received ACK in {elapsed:.3f} seconds")
            return True
        else:
            elapsed = time.perf_counter() - start_time
            print(
                f"[TIMEOUT] No ACK received in {elapsed:.3f} seconds (timeout={timeout}s)"
            )
            return False

    def test_verify_operation(
        self, sec_level: int, test_vectors: list, uart_conn: UARTConnection
    ):
        """Test the complete Dilithium verify operation"""

        self.uart = uart_conn
        try:
            print(f"\n=== Test start ===")
            base_ack_group_length = 64

            # Step 0: wait for READY
            print("0. Waiting for READY byte...")
            if not self.uart.wait_for_byte(DILITHIUM_READY_BYTE, timeout=300):
                print("Failed to get READY, aborting")
                return

            # Step 1: Send START byte
            print("1. Sending START byte...")
            self.uart.send_byte(DILITHIUM_START_BYTE)
            if not self.wait_for_ack():
                print("Failed to get START ACK, aborting")
                return False

            # Step 2: Send header (cmd + sec_lvl + msg_len)
            print("2. Sending header...")
            msg_len = int(test_vectors["msg_len"].hex(), 16)
            header = struct.pack("<BBI", DILITHIUM_CMD_VERIFY, sec_level, msg_len)
            self.uart.send_bytes(header)

            # Step 3: Wait for header ACK
            print("3. Waiting for header ACK...")
            if not self.wait_for_ack():
                print("Failed to get header ACK, aborting")
                return False

            # Step 4: Send signature components in order
            print("4. Sending signature components...")

            # Send Rho
            rho_data = test_vectors["rho"]
            print(f"\tSending Rho ({len(rho_data)} bytes): {rho_data[:8].hex()}...")
            self.uart.send_bytes(rho_data)
            if not self.wait_for_ack():
                print("Failed to get Rho ACK")
                return False

            # Send C
            c_data = test_vectors["c"]
            print(f"\tSending C ({len(c_data)} bytes): {c_data[:8].hex()}...")
            self.uart.send_bytes(c_data)
            if not self.wait_for_ack():
                print("Failed to get C ACK")
                return False

            # Send Z
            z_data = test_vectors["z"]
            total_chunks = (
                len(z_data) + base_ack_group_length - 1
            ) // base_ack_group_length
            for chunk_num in range(total_chunks):
                start = chunk_num * base_ack_group_length
                end = start + base_ack_group_length
                part_z_data = z_data[start:end]

                print(
                    f"\tSending Z({chunk_num+1}/{total_chunks}), ({len(part_z_data)} bytes): {part_z_data[:8].hex()}..."
                )
                self.uart.send_bytes(part_z_data)
                if not self.wait_for_ack():
                    print("Failed to get Z ACK")
                    return False

            # Send T1
            t1_data = test_vectors["t1"]
            total_chunks = (
                len(t1_data) + base_ack_group_length - 1
            ) // base_ack_group_length
            for chunk_num in range(total_chunks):
                start = chunk_num * base_ack_group_length
                end = start + base_ack_group_length
                part_t1_data = t1_data[start:end]
                print(
                    f"\tSending T1({chunk_num+1}/{total_chunks}), ({len(part_t1_data)} bytes): {part_t1_data[:8].hex()}..."
                )
                self.uart.send_bytes(part_t1_data)
                if not self.wait_for_ack():
                    print("Failed to get T1 ACK")
                    return False

            # Send H
            h_data = test_vectors["h"]
            total_chunks = (
                len(h_data) + base_ack_group_length - 1
            ) // base_ack_group_length
            for chunk_num in range(total_chunks):
                start = chunk_num * base_ack_group_length
                end = start + base_ack_group_length
                part_h_data = h_data[start:end]
                print(
                    f"\tSending H({chunk_num+1}/{total_chunks}), ({len(part_h_data)} bytes): {part_h_data[:8].hex()}..."
                )
                self.uart.send_bytes(part_h_data)
                if not self.wait_for_ack():
                    print("Failed to get H ACK")
                    return False

            # Step 5: Send message in chunks
            message_data = test_vectors["msg"]
            print(f"5. Sending message data ({msg_len} bytes) in chunks...")
            print(f"Message preview: {message_data[:20].hex()}...")
            bytes_sent = 0
            chunk_num = 1

            while bytes_sent < msg_len:
                chunk_size = min(DILITHIUM_CHUNK_SIZE, msg_len - bytes_sent)
                chunk = message_data[bytes_sent : bytes_sent + chunk_size]

                print(f"Sending message chunk {chunk_num}: {chunk_size} bytes")
                self.uart.send_bytes(chunk)

                # For chunks after the first one, wait for ACK first
                print(f"Waiting for chunk {chunk_num} ACK...")
                if not self.wait_for_ack():
                    print(f"Failed to get chunk {chunk_num} ACK")
                    return False

                bytes_sent += chunk_size
                chunk_num += 1

            print("✓ All data sent successfully!")

            # Give some time to see any firmware responses
            self.uart.wait_for_bytes(num_bytes=1000, timeout=1200)
            print("TIMEOUT")

            self.uart.flush_received_data()
            print("Verify operation completed. Check firmware output for results.")
            return True

        except Exception as e:
            print(f"❌ Error during verify operation: {e}")
            return False

    def test_multiple_vectors(self, sec_level=2, num_vectors=3):
        """Test multiple test vectors"""
        print(
            f"\n=== Testing {num_vectors} Test Vectors (Security Level {sec_level}) ==="
        )

        success_count = 0
        for i in range(num_vectors):
            print(f"\n--- Test Vector {i} ---")
            if self.test_verify_operation(sec_level=sec_level, vector_index=i):
                success_count += 1
                print(f"✅ Vector {i} passed")
            else:
                print(f"❌ Vector {i} failed")

            time.sleep(1)  # Brief pause between vectors

        print(f"\n=== Results: {success_count}/{num_vectors} vectors passed ===")
        return success_count == num_vectors


def main():

    port = 4327
    sec_level = 2
    vector_index = 0

    print(f"\n=== Testing Dilithium Verify (Security Level {sec_level} ===")
    # Create test suite
    tester = DilithiumTester()

    print(f"Loading test vectors {vector_index} from files...")
    test_vectors = TestVectorReader.load_dilithium_vectors(
        base_path=os.path.join(os.getcwd(), "test", "KAT"),
        sec_level=sec_level,
        vector_index=vector_index,
    )

    # Create UART connection
    uart = UARTConnection(port=port, max_wait=600)

    success = tester.test_verify_operation(
        sec_level=sec_level, test_vectors=test_vectors, uart_conn=uart
    )
    print(f"\n{'✅ Test passed!' if success else '❌ Test failed!'}")

    return

    if len(sys.argv) > 1:
        port = int(sys.argv[1])

    try:
        # Create UART connection
        uart = UARTConnection(port=port)

        # Create test suite
        tester = DilithiumTester(uart)

        print("\nChoose test mode:")
        print("1 - Single test with files (specify security level)")
        print("2 - Multiple test vectors from files")
        print("4 - Load and inspect test vector file")

        choice = input("Enter choice (1-3): ").strip()

        if choice == "0":
            # Single test with real test vectors
            sec_level = int(input("Security level (2/3/5): ") or "2")
            vector_index = int(input("Vector index (default 0): ") or "0")

            success = tester.test_verify_operation2(
                base_kat_path=os.path.join(os.getcwd(), "test", "KAT"),
                sec_level=sec_level,
                vector_index=vector_index,
            )
            print(f"\n{'✅ Test passed!' if success else '❌ Test failed!'}")

        if choice == "1":
            # Single test with real test vectors
            sec_level = int(input("Security level (2/3/5): ") or "2")
            vector_index = int(input("Vector index (default 0): ") or "0")

            success = tester.test_verify_operation(
                base_kat_path=os.path.join(os.getcwd(), "test", "KAT"),
                sec_level=sec_level,
                vector_index=vector_index,
            )
            print(f"\n{'✅ Test passed!' if success else '❌ Test failed!'}")

        elif choice == "2":
            # Multiple test vectors
            sec_level = int(input("Security level (2/3/5): ") or "2")
            num_vectors = int(input("Number of vectors to test (default 3): ") or "3")

            success = tester.test_multiple_vectors(
                sec_level=sec_level, num_vectors=num_vectors
            )
            print(f"\n{'✅ All tests passed!' if success else '❌ Some tests failed!'}")

        elif choice == "3":
            # Just load and inspect files
            print("\nFile inspection mode:")
            sec_level = int(input("Security level (2/3/5): ") or "2")

            # Load test vectors
            vectors = TestVectorReader.load_dilithium_vectors(
                base_path=kat_path, sec_level=sec_level, vector_index=0
            )

            print(f"\nLoaded test vectors for security level {sec_level}:")
            for component, data in vectors.items():
                print(f"  {component}: {len(data)} bytes - {data[:16].hex()}...")

            # Option to test with loaded vectors
            if input("\nTest with these vectors? (y/n): ").lower() == "y":
                success = tester.test_verify_operation(
                    sec_level=sec_level, test_vectors=vectors
                )
                print(f"\n{'✅ Test passed!' if success else '❌ Test failed!'}")

        else:
            print("Invalid choice")

    except ConnectionRefusedError:
        print("Connection refused! Make sure your simulation is running.")
    except Exception as e:
        print(f"Test failed: {e}")
    finally:
        if "uart" in locals():
            uart.close()


if __name__ == "__main__":
    main()
