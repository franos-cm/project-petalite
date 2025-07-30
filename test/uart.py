import socket
import time
import threading
import queue


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

    def send_byte(self, byte_val):
        """Send a single byte"""
        self.send_queue.put(byte_val)

    def send_bytes(self, data):
        """Send multiple bytes"""
        self.send_queue.put(data)

    def send_command(self, command):
        """Send a text command (for compatibility with original interface)"""
        if not command.endswith("\n"):
            command += "\n"
        self.send_queue.put(command)

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

    def wait_for_byte(self, expected_byte, timeout=5):
        """Wait for a specific byte value"""
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                item = self.received_data.get(timeout=0.1)
                msg_type, data, timestamp = item

                if msg_type == "data" and data:
                    for byte in data:
                        if byte == expected_byte:
                            return True
                elif msg_type == "error":
                    print(f"[ERROR] {data}")
                    return False

            except queue.Empty:
                continue

        return False

    def wait_for_bytes(self, num_bytes, timeout=5):
        """Wait for specific number of bytes"""
        start_time = time.time()
        buffer = b""

        while time.time() - start_time < timeout:
            try:
                item = self.received_data.get(timeout=0.1)
                msg_type, data, timestamp = item

                if msg_type == "data":
                    buffer += data

                    if self.debug:
                        print(f"[BUFFER] {buffer.hex()}")

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

    def wait_for_text(self, expected_text, timeout=30, show_debug=True):
        """Wait for specific text to appear (for text-based protocols)"""
        print(f"Waiting for '{expected_text}'...")
        buffer = ""
        start_time = time.time()

        while time.time() - start_time < timeout:
            data_items = self.get_received_data(timeout=0.5)

            for item_type, data, timestamp in data_items:
                if item_type == "data":
                    # Decode bytes to string for text matching
                    try:
                        text = data.decode("utf-8", errors="ignore")
                        buffer += text
                        if show_debug:
                            print(f"[TEXT] {repr(text)}")

                        if expected_text in buffer:
                            return True
                    except:
                        pass
                elif item_type == "error":
                    return False

        return False

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
