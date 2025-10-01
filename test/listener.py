"""Simple SoC UART listener

Purpose:
  Lightweight alternative to the DilithiumTester that just:
    * connects to the existing LiteX UART TCP bridge
    * prints anything the SoC sends (hex + ASCII preview)
    * optionally performs a basic handshake (SYNC -> wait READY -> START -> wait START echo -> ACK)
    * sends predefined responses when trigger patterns are observed
    * optionally allows interactive manual sending (hex bytes typed by user)

Trigger configuration:
  Triggers can be passed as a JSON file (via --triggers path.json) with format:

  {
    "triggers": [
      {"match": "READY", "send": ["START"]},
      {"match": "START", "send": ["ACK"]},
      {"match_hex": "a1b2c3", "send_hex": ["cc"], "once": true}
    ]
  }

  Fields:
    match:     Keyword corresponding to a single control byte (SYNC, READY, START, ACK)
    match_hex: Raw hex pattern to search for in the rolling receive buffer
    send:      List of keyword control bytes to transmit
    send_hex:  List of raw hex blobs to transmit
    once:      If true, trigger is removed after first activation

  If no trigger file is provided, you can use built-in simple presets via --preset:
    * handshake_ack : Automatically respond START after READY and ACK after START

Interactive mode:
  Run with --interactive and type hex strings (e.g. "b0" or "accc00") then ENTER to send.

Example usage:
  python -m test.simple_listener --port 4327 --preset handshake_ack --handshake
  python -m test.simple_listener --triggers my_triggers.json --interactive

Note:
  This does NOT remove or modify the existing dilithium testing infrastructure.
"""

from __future__ import annotations

import argparse
import json
import os
import select
import sys
import time
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

from uart import UARTConnection
from utils import (
    DILITHIUM_SYNC_BYTE,
    DILITHIUM_READY_BYTE,
    DILITHIUM_START_BYTE,
    DILITHIUM_ACK_BYTE,
)


# Mapping from keyword to actual control byte value
CONTROL_BYTES = {
    "SYNC": DILITHIUM_SYNC_BYTE,
    "READY": DILITHIUM_READY_BYTE,
    "START": DILITHIUM_START_BYTE,
    "ACK": DILITHIUM_ACK_BYTE,
}

# Default trigger file (relative to this script directory) that we try to load
SCRIPT_DIR = os.path.dirname(__file__)
DEFAULT_TRIGGER_REL = os.path.join("triggers", "get_random.json")


def _resolve_trigger_path(path: str) -> Optional[str]:
    """Attempt to resolve a trigger file path.

    Order tried:
      1. As-is (cwd relative or absolute)
      2. Relative to this script directory
    Returns the first existing path or None.
    """
    candidates = []
    if path:
        candidates.append(path)
        candidates.append(os.path.join(SCRIPT_DIR, path))
    for cand in candidates:
        if os.path.isfile(cand):
            return cand
    return None


@dataclass
class Trigger:
    match: Optional[str] = None  # keyword match (single control byte)
    match_hex: Optional[str] = None  # hex pattern
    send: List[str] = field(default_factory=list)  # list of keyword sends
    send_hex: List[str] = field(default_factory=list)  # list of raw hex payloads
    once: bool = False  # remove after firing
    _fired: bool = False  # internal state

    def matches(self, buffer: bytes) -> bool:
        if self._fired and self.once:
            return False
        if self.match:
            bval = CONTROL_BYTES.get(self.match.upper())
            if bval is None:
                return False
            # Trigger if last received byte equals this control byte (search end of buffer)
            if buffer and buffer[-1] == bval:
                return True
        if self.match_hex:
            pattern = bytes.fromhex(self.match_hex)
            if pattern in buffer:
                return True
        return False

    def build_send_payloads(self) -> List[bytes]:
        payloads: List[bytes] = []
        for kw in self.send:
            bval = CONTROL_BYTES.get(kw.upper())
            if bval is not None:
                payloads.append(bytes([bval]))
        for hx in self.send_hex:
            try:
                payloads.append(bytes.fromhex(hx))
            except ValueError:
                pass
        return payloads


class SimpleSoCListener:
    def __init__(
        self,
        port: int = 4327,
        host: str = "localhost",
        triggers: Optional[List[Trigger]] = None,
        max_wait: int = 600,
        debug: bool = True,
        buffer_limit: int = 8192,
    ):
        self.uart = UARTConnection(
            mode="tcp",
            tcp_port=port,
            tcp_host=host,
            tcp_connect_timeout=max_wait,
            debug=debug,
        )
        self.triggers: List[Trigger] = triggers or []
        self.buffer = bytearray()
        self.buffer_limit = buffer_limit
        self.running = False

    def perform_basic_handshake(self, timeout: int = 10):
        """Optional basic handshake: send SYNC until READY, then send START."""
        start = time.time()
        print("[HANDSHAKE] Starting basic handshake...")
        while time.time() - start < timeout:
            # Send SYNC periodically
            self.uart.send_sync()
            # Check any newly received data for READY
            items = self.uart.get_received_data(timeout=0.2)
            for _, data, _ in items:
                self.buffer.extend(data)
                if self.buffer[-1] == DILITHIUM_READY_BYTE:
                    print("[HANDSHAKE] READY received -> sending START")
                    self.uart.send_start()
                    return True
            time.sleep(0.2)
        print("[HANDSHAKE] Timed out waiting for READY")
        return False

    def _process_triggers(self):
        # Evaluate triggers in order; allow multiple per loop
        for trig in list(self.triggers):
            if trig.matches(self.buffer):
                print(
                    f"[TRIGGER] Matched {'match=' + trig.match if trig.match else 'hex=' + trig.match_hex} -> sending responses"
                )
                for payload in trig.build_send_payloads():
                    print(f"[TRIGGER] Sending: {payload.hex()}")
                    self.uart.send_bytes(payload)
                trig._fired = True
                if trig.once:
                    self.triggers.remove(trig)

    def _print_new_data(self, items):
        for msg_type, data, ts in items:
            if msg_type != "data":
                continue
            self.buffer.extend(data)
            # Bound buffer size
            if len(self.buffer) > self.buffer_limit:
                del self.buffer[: len(self.buffer) - self.buffer_limit]

    def _maybe_handle_stdin(self):
        if not sys.stdin.isatty():
            return
        rlist, _, _ = select.select([sys.stdin], [], [], 0)
        if rlist:
            line = sys.stdin.readline().strip()
            if not line:
                return
            if line.lower() in {"quit", "exit"}:
                print("[INTERACTIVE] Exit requested")
                self.running = False
                return
            try:
                payload = bytes.fromhex(line)
            except ValueError:
                print("[INTERACTIVE] Invalid hex; enter e.g. 'ac' or 'b0cc'")
                return
            print(f"[INTERACTIVE] Sending {payload.hex()}")
            self.uart.send_bytes(payload)

    def run(self, duration: Optional[float] = None, interactive: bool = False):
        self.running = True
        start = time.time()
        print("[LISTENER] Running... Ctrl-C to stop")
        try:
            while self.running:
                items = self.uart.get_received_data(timeout=0.25)
                if items:
                    self._print_new_data(items)
                    self._process_triggers()

                if interactive:
                    self._maybe_handle_stdin()

                if duration and (time.time() - start) > duration:
                    print("[LISTENER] Duration reached; stopping")
                    break
        except KeyboardInterrupt:
            print("\n[LISTENER] Interrupted by user")
        finally:
            self.running = False
            print("[LISTENER] Stopped")

    def close(self):
        self.uart.close()


def load_triggers(path: str) -> List[Trigger]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    triggers_cfg = data.get("triggers", [])
    triggers: List[Trigger] = []
    for entry in triggers_cfg:
        triggers.append(
            Trigger(
                match=entry.get("match"),
                match_hex=entry.get("match_hex"),
                send=entry.get("send", []),
                send_hex=entry.get("send_hex", []),
                once=entry.get("once", False),
            )
        )
    return triggers


def preset_triggers(name: str) -> List[Trigger]:
    name = name.lower()
    if name == "handshake_ack":
        return [
            Trigger(match="READY", send=["START"], once=True),
            Trigger(match="START", send=["ACK"], once=False),
        ]
    raise ValueError(f"Unknown preset '{name}'")


def parse_args(argv: List[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Simple SoC UART listener")
    p.add_argument(
        "--port", type=int, default=4327, help="TCP port of LiteX UART bridge"
    )
    p.add_argument(
        "--host", type=str, default="localhost", help="Host (default localhost)"
    )
    p.add_argument("--triggers", type=str, help="Path to JSON trigger config")
    p.add_argument(
        "--preset", type=str, help="Use built-in trigger preset (e.g. handshake_ack)"
    )
    p.add_argument(
        "--duration",
        type=float,
        default=6000,
        help="Stop after N seconds (default: run until Ctrl-C)",
    )
    p.add_argument(
        "--interactive", action="store_true", help="Enable interactive hex input"
    )
    p.add_argument(
        "--handshake",
        action="store_true",
        help="Perform basic SYNC->READY->START handshake before listening",
    )
    p.add_argument(
        "--no-default-triggers",
        default=False,
        help="Do not auto-load the built-in default trigger file even if present",
    )
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None):
    args = parse_args(argv or sys.argv[1:])

    triggers: List[Trigger] = []
    if args.triggers:
        resolved = _resolve_trigger_path(args.triggers)
        if not resolved:
            print(
                f"Trigger file '{args.triggers}' not found (tried: '{args.triggers}', '{os.path.join(SCRIPT_DIR, args.triggers)}')"
            )
            return 1
        try:
            triggers = load_triggers(resolved)
            print(f"Loaded {len(triggers)} triggers from {resolved}")
        except Exception as e:
            print(f"Failed to load triggers '{resolved}': {e}")
            return 1
    elif args.preset:
        try:
            triggers = preset_triggers(args.preset)
            print(f"Loaded preset '{args.preset}' with {len(triggers)} triggers")
        except Exception as e:
            print(f"Preset error: {e}")
            return 1
    else:
        # Attempt to load default trigger file silently if present unless suppressed
        if not args.no_default_triggers:
            default_path = os.path.join(SCRIPT_DIR, DEFAULT_TRIGGER_REL)
            if os.path.isfile(default_path):
                try:
                    triggers = load_triggers(default_path)
                    print(
                        f"Loaded default trigger file '{DEFAULT_TRIGGER_REL}' with {len(triggers)} triggers"
                    )
                except Exception as e:
                    print(f"Default trigger load error ({default_path}): {e}")
            else:
                print("No triggers: default trigger file not found")
        else:
            print(
                "No triggers: default trigger loading suppressed (--no-default-triggers)"
            )

    listener = SimpleSoCListener(
        port=args.port,
        host=args.host,
        triggers=triggers,
    )

    if args.handshake:
        listener.perform_basic_handshake()

    listener.run(duration=args.duration, interactive=args.interactive)
    listener.close()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
