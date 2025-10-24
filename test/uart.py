import time
import socket
import threading
import queue

try:
    import serial  # (optional when using TCP only)
except Exception:
    serial = None


DILITHIUM_READY_BYTE = 0xA0
BASE_ACK_GROUP_LENGTH = 64


class _SocketTransport:
    def __init__(self, sock: socket.socket):
        self.sock = sock

    def settimeout(self, t: float):
        self.sock.settimeout(t)

    def recv(self, size: int) -> bytes:
        return self.sock.recv(size)

    def sendall(self, data: bytes):
        self.sock.sendall(data)

    def close(self):
        self.sock.close()


class _SerialTransport:
    def __init__(self, ser):
        self.ser = ser

    def settimeout(self, t: float):
        self.ser.timeout = t
        self.ser.write_timeout = t

    def recv(self, size: int) -> bytes:
        # pyserial returns b'' on timeout
        return self.ser.read(size)

    def sendall(self, data: bytes):
        # Ensure full write by looping until all bytes sent
        total = 0
        while total < len(data):
            n = self.ser.write(data[total:])
            if n is None:
                n = 0
            total += n

    def close(self):
        self.ser.close()


class UARTConnection:
    """Clean UART communication class - handles only communication"""

    def __init__(
        self,
        mode: str = "tcp",
        tcp_host: str = "localhost",
        tcp_port: int = 4327,
        tcp_connect_timeout: int = 600,
        # Serial parameters
        serial_port: str | None = "/dev/ttyUSB1",
        baudrate: int = 115200,
        serial_timeout: float = 0.1,
        name: str = None,
        debug: bool = True,
        # File logging options
        log_path: str | None = None,
        log_writes: bool = True,
    ):
        self.name = name
        # Keep original debug flag semantics
        self.debug = bool(debug)
        self.running = False
        self.mode = mode

        self.log_read_each_byte = mode == "serial"

        # Transport open
        self.transport = None
        if mode == "serial":
            if serial is None:
                raise RuntimeError(
                    "pyserial is required for serial mode. Install with: pip install pyserial"
                )
            if not serial_port:
                raise RuntimeError("serial_port must be provided in serial mode.")
            self._open_serial(
                serial_port=serial_port, baudrate=baudrate, timeout=serial_timeout
            )
        elif mode == "tcp":
            self._open_tcp(host=tcp_host, port=tcp_port, max_wait=tcp_connect_timeout)
        else:
            raise ValueError("mode must be 'tcp' or 'serial'")

        # Queues
        self.received_data = queue.Queue()
        self.send_queue = queue.Queue()

        # Start threads
        self.running = True
        self.read_thread = threading.Thread(target=self._read_worker, daemon=True)
        self.write_thread = threading.Thread(target=self._write_worker, daemon=True)
        self.read_thread.start()
        self.write_thread.start()
        if self.debug:
            print(f"{self._id()} Read/Write threads started")

        # Rolling pushback buffer
        self._pushback = bytearray()

        # File logging
        self.log_path = log_path
        self.log_writes = log_writes
        self._log_fp = None
        if self.log_path:
            try:
                self._log_fp = open(self.log_path, "a", buffering=1, encoding="utf-8")
                # Timestamped header
                ts = time.strftime("%Y-%m-%d %H:%M:%S")
                self._log_fp.write(f"[{ts}] === UART log started ===\n")
            except Exception as e:
                print(f"{self._id()}[LOG] Failed to open log file: {e}")
                self._log_fp = None

    def _id(self):
        return f"[{self.name}]" if self.name else ""

    def _open_tcp(self, host, port, max_wait):
        """Retry TCP connection to simulation until timeout (original style)"""
        self._console(f"Connecting to {host}:{port}... (will wait up to {max_wait}s)")
        try_count = 0
        start_time = time.time()
        while time.time() - start_time < max_wait:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.connect((host, port))
                elapsed = time.time() - start_time
                self._console(f"✅ Connected after {elapsed:.2f} seconds!")
                self.sock = sock
                self.transport = _SocketTransport(sock)
                return
            except (ConnectionRefusedError, socket.timeout):
                try:
                    sock.close()
                except Exception:
                    pass
                elapsed = time.time() - start_time
                self._console(
                    f"[{elapsed:.2f}s] Not ready yet (attempt {try_count}). Retrying..."
                )
                try_count += 1
                time.sleep(0.1)
        raise TimeoutError(
            f"❌ Could not connect to {host}:{port} after {max_wait} seconds"
        )

    def _open_serial(self, serial_port: str, baudrate: int, timeout: float):
        self._console(
            f"Opening serial {serial_port} @ {baudrate} (timeout={timeout}s)..."
        )
        ser = serial.Serial(
            port=serial_port, baudrate=baudrate, timeout=timeout, write_timeout=timeout
        )
        try:
            ser.reset_input_buffer()
            ser.reset_output_buffer()
        except Exception:
            pass
        time.sleep(0.1)
        self.transport = _SerialTransport(ser)
        self._console("✅ Serial port opened")

    # Unified console/file helpers
    def _console(self, msg: str):
        if self.debug:
            print(f"{self._id()} {msg}")

    def _emit_log_line(self, line: str):
        if self._log_fp:
            try:
                self._log_fp.write(line + "\n")
            except Exception:
                pass
        else:
            print(line)

    # NEW: simple HH:MM:SS timestamp for log lines
    def _ts(self) -> str:
        return time.strftime("%H:%M:%S")

    def _read_worker(self):
        """Background thread that continuously reads from transport"""
        while self.running:
            try:
                self.transport.settimeout(0.1)
                data = self.transport.recv(64)
                if data:
                    self.received_data.put(("data", data, time.time()))
                    # Keep original behavior and format; just route to file if set
                    if self.debug:
                        if self.log_read_each_byte:
                            for b in data:
                                self._emit_log_line(
                                    f"[{self._ts()}] {self._id()}[READ] {b:02x}"
                                )
                        else:
                            self._emit_log_line(
                                f"[{self._ts()}] {self._id()}[READ] {data.hex()}"
                            )
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    self._console(f"[READ ERROR] {e}")
                    self.received_data.put(("error", str(e), time.time()))
                break

    def _write_worker(self):
        """Background thread that handles sending data"""
        while self.running:
            try:
                command = self.send_queue.get(timeout=0.1)
                if command:
                    # Keep original formatting for writes
                    if self.debug:
                        if isinstance(command, bytes):
                            self._emit_log_line(
                                f"[{self._ts()}] {self._id()}[WRITE] 0x{command.hex().upper()}"
                            )
                        elif isinstance(command, int):
                            self._emit_log_line(
                                f"[{self._ts()}] {self._id()}[WRITE] 0x{command:X}"
                            )
                        else:
                            self._emit_log_line(
                                f"[{self._ts()}] {self._id()}[WRITE] {repr(command)}"
                            )

                    if isinstance(command, str):
                        command = command.encode()
                    elif isinstance(command, int):
                        command = bytes([command])

                    self.transport.sendall(command)
                    self.send_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                if self.running:
                    self._console(f"[WRITE ERROR] {e}")

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

    def _take_from_pushback(self, n: int) -> bytes:
        """Remove and return up to n bytes from the pushback buffer."""
        if not self._pushback:
            return b""
        take = min(n, len(self._pushback))
        chunk = bytes(self._pushback[:take])
        del self._pushback[:take]
        return chunk

    def _next_data_chunk(self, timeout=0.1):
        """Yield next data/error item, preferring pushback first.

        Returns a tuple (msg_type, data, timestamp) consistent with queue items.
        If pushback has data, returns it as a single 'data' chunk.
        """
        if self._pushback:
            data = bytes(self._pushback)
            self._pushback.clear()
            return ("data", data, time.time())
        return self.received_data.get(timeout=timeout)

    def _wait_for_byte(self, expected_byte, signal_name: str = "", timeout=5):
        """Wait for a specific byte value"""
        start_time = time.perf_counter()

        while time.perf_counter() - start_time < timeout:
            try:
                msg_type, data, timestamp = self._next_data_chunk(timeout=0.1)

                if msg_type == "data" and data:
                    for idx, byte in enumerate(data):
                        if byte == expected_byte:
                            if idx + 1 < len(data):
                                remaining = data[idx + 1 :]
                                self._pushback.extend(remaining)
                            if signal_name:
                                elapsed = time.perf_counter() - start_time
                                self._console(
                                    f"[{signal_name.upper()}] Received in {elapsed:.3f} seconds"
                                )
                            return True
                elif msg_type == "error":
                    self._console(f"[ERROR] {data}")
                    return False

            except queue.Empty:
                continue

        self._console(
            f"[TIMEOUT] No {signal_name.upper()} received in {timeout:.3f} seconds"
        )
        return False

    def wait_for_bytes(self, num_bytes, timeout=5) -> bytes:
        """Wait for specific number of bytes"""
        if not num_bytes:
            return bytes()

        start_time = time.perf_counter()
        buffer = bytearray()

        while time.perf_counter() - start_time < timeout:
            try:
                # First, consume from pushback if any
                if self._pushback and len(buffer) < num_bytes:
                    need = num_bytes - len(buffer)
                    buffer.extend(self._take_from_pushback(need))
                    if len(buffer) >= num_bytes:
                        return bytes(buffer[:num_bytes])

                msg_type, data, timestamp = self._next_data_chunk(timeout=0.1)

                if msg_type == "data":
                    need = num_bytes - len(buffer)
                    if need > 0:
                        take = data[:need]
                        buffer.extend(take)
                        # Anything beyond what we needed goes into pushback
                        if len(data) > len(take):
                            self._pushback.extend(data[len(take) :])
                    else:
                        # Already have enough, stash all data to pushback
                        self._pushback.extend(data)

                    if len(buffer) >= num_bytes:
                        return bytes(buffer[:num_bytes])

            except queue.Empty:
                continue

        return bytes(buffer) if buffer else None

    def wait_for_ready(self, timeout=120):
        return self._wait_for_byte(
            expected_byte=DILITHIUM_READY_BYTE, signal_name="READY", timeout=timeout
        )

    def send_in_chunks(
        self,
        data: bytes | bytearray,
        chunk_size: int = BASE_ACK_GROUP_LENGTH,
        data_name: str = "",
    ):
        total_chunks = (len(data) + chunk_size - 1) // chunk_size
        for chunk_num in range(total_chunks):
            start = chunk_num * chunk_size
            end = start + chunk_size
            data_chunk = data[start:end]

            self._console(
                f"Sending {data_name}({chunk_num+1}/{total_chunks}),"
                f"({len(data_chunk)} bytes): {data_chunk[:8].hex()}..."
            )
            self.send_bytes(data_chunk)
            if not self.wait_for_ack():
                self._console(f"Failed to get {data_name} ({chunk_num+1}) ACK")
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
            self._console(
                f"Receiving {data_name} ({total_bytes} bytes) in {total_chunks} chunks..."
            )

        for chunk_num in range(total_chunks):
            bytes_to_receive = min(chunk_size, total_bytes - len(full_data))

            if self.debug:
                self._console(
                    f"Receiving {data_name} chunk ({chunk_num + 1}/{total_chunks}), "
                    f"waiting for {bytes_to_receive} bytes..."
                )

            data_chunk = self.wait_for_bytes(
                num_bytes=bytes_to_receive, timeout=timeout_per_chunk
            )

            if not data_chunk or len(data_chunk) < bytes_to_receive:
                self._console(
                    f"❌ Failed to receive {data_name} chunk ({chunk_num + 1}). Timed out."
                )
                return None

            full_data += data_chunk

            self.send_ack()
            if self.debug:
                self._console(f"✅ ACK'd chunk {chunk_num + 1}/{total_chunks}")

        if len(full_data) == total_bytes:
            if data_name:
                self._console(
                    f"✅ Successfully received all {total_bytes} bytes of {data_name}."
                )
            return full_data
        else:
            self._console(
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
                    print(f"{self._id()} Received: {data.hex()}")
        except queue.Empty:
            print(f"{self._id()} No more data")

    def close(self):
        """Clean shutdown"""
        self._console("Shutting down UART connection...")
        self.running = False
        self.read_thread.join(timeout=1)
        self.write_thread.join(timeout=1)
        try:
            self.transport.close()
        except Exception:
            pass
        if self._log_fp:
            try:
                ts = time.strftime("%Y-%m-%d %H:%M:%S")
                self._log_fp.write(f"[{ts}] === UART log closed ===\n")
                self._log_fp.close()
            except Exception:
                pass
        self._console("UART connection closed")
