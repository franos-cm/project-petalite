import socket
import time
import threading
import queue
from typing import List

from utils import (
    DILITHIUM_ACK_BYTE,
    DILITHIUM_READY_BYTE,
    DILITHIUM_SYNC_BYTE,
    DILITHIUM_START_BYTE,
    BASE_ACK_GROUP_LENGTH,
)


class UARTConnection:
    """Clean UART communication class - handles only communication"""

    def __init__(self, host="localhost", port=4327, debug: bool = True, max_wait=600):
        self.debug = debug
        self.running = False
        self._wait_for_sim_connection(host=host, port=port, max_wait=max_wait)

        # Thread-safe queues
        self.received_data = queue.Queue()
        self.send_queue = queue.Queue()

        # Start threads
        self.running = True
        self.read_thread = threading.Thread(target=self._read_worker, daemon=True)
        self.write_thread = threading.Thread(target=self._write_worker, daemon=True)

        self.read_thread.start()
        self.write_thread.start()

        print("Read/Write threads started")

    def _wait_for_sim_connection(self, host, port, max_wait):
        """Retry TCP connection to simulation until timeout"""
        print(f"Connecting to {host}:{port}... (will wait up to {max_wait}s)")
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        try_count = 0
        start_time = time.time()

        while time.time() - start_time < max_wait:
            try:
                self.sock.connect((host, port))
                elapsed = time.time() - start_time
                print(f"✅ Connected to simulation after {elapsed:.2f} seconds!")
                return

            except (ConnectionRefusedError, socket.timeout):
                elapsed = time.time() - start_time
                print(
                    f"[{elapsed:.2f}s] Simulation not ready yet (attempt {try_count}). Retrying..."
                )
                try_count += 1
                time.sleep(0.1)

        raise TimeoutError(
            f"❌ Could not connect to simulation at {host}:{port} after {max_wait} seconds"
        )

    def _read_worker(self):
        """Background thread that continuously reads from socket"""
        while self.running:
            try:
                self.sock.settimeout(0.1)
                data = self.sock.recv(64)
                if data:
                    self.received_data.put(("data", data, time.time()))
                    if self.debug:
                        print(f"[READ] {data.hex()}")

            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    print(f"[READ ERROR] {e}")
                    self.received_data.put(("error", str(e), time.time()))
                break

    def _write_worker(self):
        """Background thread that handles sending data"""
        while self.running:
            try:
                command = self.send_queue.get(timeout=0.1)
                if command:
                    if self.debug:
                        if isinstance(command, bytes):
                            print(f"[WRITE] 0x{command.hex().upper()}")
                        elif isinstance(command, int):
                            print(f"[WRITE] 0x{command:X}")
                        else:
                            print(f"[WRITE] {repr(command)}")

                    if isinstance(command, str):
                        command = command.encode()
                    elif isinstance(command, int):
                        command = bytes([command])

                    self.sock.sendall(command)
                    self.send_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                if self.running:
                    print(f"[WRITE ERROR] {e}")

    def send_bytes(self, data):
        """Send multiple bytes"""
        self.send_queue.put(data)

    def get_received_data(self, timeout=0.1):
        """Get any received data (non-blocking)"""
        received = []
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                item = self.received_data.get_nowait()
                received.append(item)
                self.received_data.task_done()
            except queue.Empty:
                break

        return received

    def _wait_for_byte(self, expected_byte, signal_name: str = "", timeout=5):
        """Wait for a specific byte value"""
        start_time = time.perf_counter()

        while time.perf_counter() - start_time < timeout:
            try:
                item = self.received_data.get(timeout=0.1)
                msg_type, data, timestamp = item

                if msg_type == "data" and data:
                    for byte in data:
                        if byte == expected_byte:
                            if signal_name:
                                elapsed = time.perf_counter() - start_time
                                print(
                                    f"[{signal_name.upper()}] Received in {elapsed:.3f} seconds"
                                )
                            return True

                elif msg_type == "error":
                    print(f"[ERROR] {data}")
                    return False

            except queue.Empty:
                continue

        print(f"[TIMEOUT] No {signal_name.upper()} received in {timeout:.3f} seconds")
        return False

    def wait_for_bytes(self, num_bytes, timeout=5):
        """Wait for specific number of bytes"""
        start_time = time.perf_counter()
        buffer = b""

        while time.perf_counter() - start_time < timeout:
            try:
                item = self.received_data.get(timeout=0.1)
                msg_type, data, timestamp = item

                if msg_type == "data":
                    buffer += data

                    if len(buffer) >= num_bytes:
                        result = buffer[:num_bytes]
                        # Put remaining bytes back (if any)
                        if len(buffer) > num_bytes:
                            remaining = buffer[num_bytes:]
                            self.received_data.put(("data", remaining, time.time()))
                        return result

            except queue.Empty:
                continue

        return buffer if buffer else None

    def wait_for_ack(self, timeout=120):
        return self._wait_for_byte(
            expected_byte=DILITHIUM_ACK_BYTE, signal_name="ACK", timeout=timeout
        )

    def wait_for_ready(self, timeout=120):
        return self._wait_for_byte(
            expected_byte=DILITHIUM_READY_BYTE, signal_name="READY", timeout=timeout
        )

    def wait_for_start(self, timeout=120):
        return self._wait_for_byte(
            expected_byte=DILITHIUM_START_BYTE, signal_name="START", timeout=timeout
        )

    def get_response_header(self, timeout=1200):
        self.wait_for_start()
        self.send_ack()
        response_header = self.wait_for_bytes(num_bytes=4, timeout=timeout)
        self.send_ack()
        return response_header

    def send_ack(self):
        print(f"\t[ACK] Sending ACK...")
        self.send_bytes(DILITHIUM_ACK_BYTE)

    def send_sync(self):
        print(f"\t[SYNC] Sending SYNC...")
        self.send_bytes(DILITHIUM_SYNC_BYTE)

    def send_start(self):
        print(f"\t[START] Sending START...")
        self.send_bytes(DILITHIUM_START_BYTE)

    def send_in_chunks(
        self,
        data: List[bytes],
        chunk_size: int = BASE_ACK_GROUP_LENGTH,
        data_name: str = "",
    ):
        total_chunks = (len(data) + chunk_size - 1) // chunk_size
        for chunk_num in range(total_chunks):
            start = chunk_num * chunk_size
            end = start + chunk_size
            data_chunk = data[start:end]

            print(
                f"\tSending {data_name}({chunk_num+1}/{total_chunks}), ({len(data_chunk)} bytes): {data_chunk[:8].hex()}..."
            )
            self.send_bytes(data_chunk)
            if not self.wait_for_ack():
                print(f"Failed to get {data_name} ({chunk_num+1}) ACK")
                return False

    def receive_in_chunks(
        self,
        total_bytes: int,
        chunk_size: int = BASE_ACK_GROUP_LENGTH,
        data_name: str = "",
        timeout_per_chunk: int = 15,
    ):
        """Receive a large amount of data in chunks, sending an ACK after each chunk.

        Args:
            total_bytes (int): The total number of bytes to receive.
            chunk_size (int): The size of each chunk to receive.
            data_name (str): A descriptive name for the data being received (for logging).
            timeout_per_chunk (int): The timeout in seconds for receiving each chunk.

        Returns:
            bytes: The complete data received, or None if the operation failed or timed out.
        """
        full_data = b""
        total_chunks = (total_bytes + chunk_size - 1) // chunk_size

        if data_name:
            print(
                f"\tReceiving {data_name} ({total_bytes} bytes) in {total_chunks} chunks..."
            )

        for chunk_num in range(total_chunks):
            bytes_to_receive = min(chunk_size, total_bytes - len(full_data))

            if self.debug:
                print(
                    f"\tReceiving {data_name} chunk ({chunk_num + 1}/{total_chunks}), waiting for {bytes_to_receive} bytes..."
                )

            # Wait for the next chunk of data
            data_chunk = self.wait_for_bytes(
                num_bytes=bytes_to_receive, timeout=timeout_per_chunk
            )

            if not data_chunk or len(data_chunk) < bytes_to_receive:
                print(
                    f"❌ Failed to receive {data_name} chunk ({chunk_num + 1}). Timed out."
                )
                return None

            full_data += data_chunk

            # Acknowledge receipt of the chunk
            self.send_ack()
            if self.debug:
                print(f"\t✅ ACK'd chunk {chunk_num + 1}/{total_chunks}")

        if len(full_data) == total_bytes:
            if data_name:
                print(
                    f"✅ Successfully received all {total_bytes} bytes of {data_name}."
                )
            return full_data
        else:
            print(
                f"❌ Error: Expected {total_bytes} bytes, but received {len(full_data)}."
            )
            return None

    def flush_received_data(self):
        """Show any remaining received data"""
        print("\n--- Remaining received data ---")
        try:
            while True:
                item = self.received_data.get_nowait()
                msg_type, data, timestamp = item
                if msg_type == "data":
                    print(f"Received: {data.hex()}")
        except queue.Empty:
            print("No more data")

    def close(self):
        """Clean shutdown"""
        print("Shutting down UART connection...")
        self.running = False
        self.read_thread.join(timeout=1)
        self.write_thread.join(timeout=1)
        self.sock.close()
        print("UART connection closed")
