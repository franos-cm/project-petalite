import threading
import queue
import time
import tkinter as tk
from tkinter import ttk, messagebox
from tkinter.scrolledtext import ScrolledText
from tkinter import font as tkfont
from typing import Optional

# Requires: pip install ttkbootstrap (optional but recommended)
try:
    import ttkbootstrap as ttkb  # Beautiful themes for Tkinter
except Exception:
    ttkb = None

# Local modules
from uart import UARTConnection
from tpm_client import TPMClient
from tpm_utils import (
    sessions_param_offset as _sessions_param_offset,
    parse_createprimary_outpublic as _parse_createprimary_outpublic,
)


class ThreadSafeLog:
    def __init__(self):
        self.q = queue.Queue()

    def put(self, line: str):
        if line and not line.endswith("\n"):
            line = line + "\n"
        self.q.put(line)

    def drain_to_text(self, text_widget: ScrolledText, max_lines: int = 2000):
        updated = False
        # Temporarily enable widget if read-only
        prev_state = None
        try:
            prev_state = text_widget.cget("state")
            if prev_state == tk.DISABLED:
                text_widget.configure(state=tk.NORMAL)
        except Exception:
            prev_state = None
        while True:
            try:
                line = self.q.get_nowait()
                if line is None:
                    break
                text_widget.insert(tk.END, line)
                updated = True
            except queue.Empty:
                break
        if updated:
            lines = float(text_widget.index('end-1c').split('.')[0])
            if lines > max_lines:
                to_remove = int(lines - max_lines)
                text_widget.delete('1.0', f"{to_remove + 1}.0")
            text_widget.see(tk.END)
        # Restore state
        if prev_state == tk.DISABLED:
            try:
                text_widget.configure(state=tk.DISABLED)
            except Exception:
                pass


BaseWindow = ttkb.Window if ttkb is not None else tk.Tk


class TPMDashboard(BaseWindow):
    def __init__(self, themename: str | None = None, latency_metrics: bool = False):
        if ttkb is not None:
            super().__init__(themename=themename or "darkly")  # try: flatly, cyborg, solar
        else:
            super().__init__()
        self.title("TPM Dilithium Dashboard • Modern")
        self.geometry("1280x840")

        # store latency flag for later use in connect()
        self.latency_metrics = bool(latency_metrics)

        # Avoid clashing with ttkbootstrap Window's `style` property
        self._style = (ttkb.Style() if ttkb is not None else ttk.Style())
        self._setup_styles()

        # State
        self.uart: Optional[UARTConnection] = None
        self.client: Optional[TPMClient] = None
        self.busy = False
        self.key_handle: Optional[int] = None
        self.pubkey: Optional[bytes] = None
        self.signature: Optional[bytes] = None
        self.ticket: Optional[tuple] = None

        self.op_log = ThreadSafeLog()
        self._tooltip_win = None
        # TX/RX timing helpers
        self._last_cmd_name = None
        self._last_cmd_t0 = 0.0
        # Connection stage timers
        self._connect_t0 = None
        self._conn_t1 = None
        self._conn_t2 = None
        # Action timers
        self._running_action = None
        self._running_t0 = 0.0

        self._build_layout()
        self.after(100, self._poll_logs)

    def _setup_styles(self):
        if ttkb is not None:
            self.colors = {
                "pane_bg": "#0F141A",
                "text_fg": "#E6EDF3",
                "accent": "#4EA1FF",
                "blue": "#61AFEF",
                "purple": "#C678DD",
                "orange": "#D19A66",
                "green": "#98C379",
                "red": "#E06C75",
                "muted": "#7F848E",
            }
        else:
            try:
                self._style.theme_use("clam")
            except Exception:
                pass
            self.colors = {
                "pane_bg": "#FFFFFF",
                "text_fg": "#111111",
                "accent": "#0066CC",
                "blue": "#1F4B99",
                "purple": "#6B2D84",
                "orange": "#B36B00",
                "green": "#1E7F3F",
                "red": "#B00020",
                "muted": "#6E6E6E",
            }
        # Common styles
        self._style.configure("Heading.TLabel", font=("TkDefaultFont", 10, "bold"))
        self._style.configure("Status.TLabel", font=("TkDefaultFont", 9))
        self._style.configure("Pane.TFrame", padding=(8, 6))
        self._style.configure("Accent.TButton", padding=(8, 6))
        # Green-on-check style for connection checkboxes
        try:
            self._style.configure("Conn.TCheckbutton", foreground=self.colors["muted"])
            self._style.map(
                "Conn.TCheckbutton",
                foreground=[("selected", self.colors["green"])],
            )
        except Exception:
            pass

    def _build_layout(self):
        root = self
        root.columnconfigure(0, weight=0)
        root.columnconfigure(1, weight=1)
        # Ensure the single top row (row=0) expands to fill vertical space
        root.rowconfigure(0, weight=1)

        # Left sidebar (fixed/narrow width)
        left = ttk.Frame(root, padding=12, style="TFrame")
        left.grid(row=0, column=0, sticky="ns")
        # Constrain left bar width so it doesn't eat half the screen
        try:
            left.configure(width=360)
            left.grid_propagate(False)  # keep the set width even if children want more
        except Exception:
            pass

        # Right main
        right = ttk.Frame(root, padding=12, style="TFrame")
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        # Row 1 (bottom) should not expand vertically
        right.rowconfigure(1, weight=0)

        # Right: terminals (top) + bottom area (session info)
        right.rowconfigure(0, weight=1)
        right.rowconfigure(1, weight=0)
        logs = ttk.Frame(right, padding=12, style="TFrame")
        logs.grid(row=0, column=0, sticky="nsew")
        logs.columnconfigure(0, weight=1)
        logs.columnconfigure(1, weight=1)

        # Connection
        ttk.Label(left, text="Connection", style="Heading.TLabel").grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 6))
        self.mode_var = tk.StringVar(value="tcp")
        self.tcp_radio = ttk.Radiobutton(left, text="TCP", variable=self.mode_var, value="tcp")
        self.serial_radio = ttk.Radiobutton(left, text="Serial", variable=self.mode_var, value="serial")
        self.tcp_radio.grid(row=1, column=0, sticky="w", pady=(0, 4))
        self.serial_radio.grid(row=1, column=1, sticky="w", pady=(0, 4))

        # TCP fields
        self.tcp_host_label = ttk.Label(left, text="Host")
        self.host_entry = ttk.Entry(left)
        self.host_entry.insert(0, "localhost")
        self.tcp_port_label = ttk.Label(left, text="TCP Port")
        self.port_entry = ttk.Entry(left)
        self.port_entry.insert(0, "4327")

        # Serial fields
        self.serial_dev_label = ttk.Label(left, text="Serial Dev")
        self.ser_entry = ttk.Entry(left)
        self.ser_entry.insert(0, "/dev/ttyUSB1")
        self.baud_label = ttk.Label(left, text="Baud")
        self.baud_entry = ttk.Entry(left)
        self.baud_entry.insert(0, "115200")

        # Place fields; we'll toggle visibility based on mode
        self.tcp_host_label.grid(row=2, column=0, sticky="w")
        self.host_entry.grid(row=2, column=1, columnspan=2, sticky="ew")
        self.tcp_port_label.grid(row=3, column=0, sticky="w")
        self.port_entry.grid(row=3, column=1, columnspan=2, sticky="ew")
        self.serial_dev_label.grid(row=4, column=0, sticky="w")
        self.ser_entry.grid(row=4, column=1, columnspan=2, sticky="ew")
        self.baud_label.grid(row=5, column=0, sticky="w")
        self.baud_entry.grid(row=5, column=1, columnspan=2, sticky="ew")

        # Place fields; we'll toggle visibility based on mode
        self.tcp_host_label.grid(row=2, column=0, sticky="w")
        self.host_entry.grid(row=2, column=1, columnspan=2, sticky="ew")
        self.tcp_port_label.grid(row=3, column=0, sticky="w")
        self.port_entry.grid(row=3, column=1, columnspan=2, sticky="ew")
        self.serial_dev_label.grid(row=4, column=0, sticky="w")
        self.ser_entry.grid(row=4, column=1, columnspan=2, sticky="ew")
        self.baud_label.grid(row=5, column=0, sticky="w")
        self.baud_entry.grid(row=5, column=1, columnspan=2, sticky="ew")

        def _on_mode_change(*_):
            self._update_conn_fields()
        self.mode_var.trace_add('write', _on_mode_change)
        self._update_conn_fields()

        self.connect_btn = ttk.Button(left, text="Connect", command=self.connect, style="Accent.TButton")
        self.connect_btn.grid(row=6, column=0, sticky="ew", pady=(6, 0))
        self.disconnect_btn = ttk.Button(left, text="Disconnect", command=self.disconnect, state=tk.DISABLED)
        # Give Disconnect more room by spanning two columns
        self.disconnect_btn.grid(row=6, column=1, columnspan=2, sticky="ew", pady=(6, 0))

        self.status_var = tk.StringVar(value="Disconnected")
        self.status_label = ttk.Label(left, textvariable=self.status_var, style="Status.TLabel")
        self.status_label.grid(row=7, column=0, columnspan=3, sticky="w")

        # Connection progress indicators
        self.conn_stage1_var = tk.BooleanVar(value=False)  # Transport connected
        self.conn_stage2_var = tk.BooleanVar(value=False)  # READY received
        self.conn_stage3_var = tk.BooleanVar(value=False)  # Startup response
        self.stage1_cb = ttk.Checkbutton(left, text="Connecting to transport", variable=self.conn_stage1_var, state=tk.DISABLED, style="Conn.TCheckbutton")
        self.stage2_cb = ttk.Checkbutton(left, text="Waiting for platform READY", variable=self.conn_stage2_var, state=tk.DISABLED, style="Conn.TCheckbutton")
        self.stage3_cb = ttk.Checkbutton(left, text="Waiting for Startup(CLEAR) answer", variable=self.conn_stage3_var, state=tk.DISABLED, style="Conn.TCheckbutton")
        self.stage1_cb.grid(row=8, column=0, columnspan=3, sticky="w")
        self.stage2_cb.grid(row=9, column=0, columnspan=3, sticky="w")
        self.stage3_cb.grid(row=10, column=0, columnspan=3, sticky="w")
        # Big ready indicator (hidden until fully ready)
        self.ready_label = ttk.Label(left, text="✔ Ready for commands", foreground=self.colors["green"], font=("TkDefaultFont", 12, "bold"))
        self.ready_label.grid(row=11, column=0, columnspan=3, sticky="w", pady=(4, 0))
        try:
            self.ready_label.grid_remove()
        except Exception:
            pass

        # Message input first (not a command)
        ttk.Separator(left, orient=tk.HORIZONTAL).grid(row=12, column=0, columnspan=3, sticky="ew", pady=6)
        msg_group = ttk.LabelFrame(left, text="Message input")
        msg_group.grid(row=13, column=0, columnspan=3, sticky="ew", pady=(0, 0))
        msg_group.columnconfigure(1, weight=1)
        ttk.Label(msg_group, text="Message (hex)").grid(row=0, column=0, sticky="w", pady=(2, 2))
        self.msg_entry = ttk.Entry(msg_group)
        self.msg_entry.grid(row=0, column=1, columnspan=2, sticky="ew", pady=(2, 2))
        ttk.Label(msg_group, text="Random size").grid(row=1, column=0, sticky="w", pady=(2, 2))
        self.rand_size_entry = ttk.Entry(msg_group)
        self.rand_size_entry.insert(0, "640")
        self.rand_size_entry.grid(row=1, column=1, sticky="ew", pady=(2, 2))
        ttk.Button(msg_group, text="Fill Random", command=self.fill_random_message).grid(row=1, column=2, sticky="ew", padx=(6,0), pady=(2, 2))

        # Dilithium operations after message
        ttk.Separator(left, orient=tk.HORIZONTAL).grid(row=14, column=0, columnspan=3, sticky="ew", pady=6)
        ttk.Label(left, text="Dilithium operations", style="Heading.TLabel").grid(row=15, column=0, columnspan=3, sticky="w")
        # Create/Sign/Verify buttons with status labels next to them
        self.create_key_btn = ttk.Button(left, text="Create Dilithium Key", command=self.create_key, state=tk.DISABLED, style="Accent.TButton")
        self.create_key_btn.grid(row=16, column=0, columnspan=2, sticky="ew", pady=(2, 0))
        self.create_status_var = tk.StringVar(value="")
        self.create_status_lbl = ttk.Label(left, textvariable=self.create_status_var, style="Status.TLabel")
        self.create_status_lbl.grid(row=16, column=2, sticky="w")

        self.sign_btn = ttk.Button(left, text="Sign Message", command=self.sign_message, state=tk.DISABLED, style="Accent.TButton")
        self.sign_btn.grid(row=17, column=0, columnspan=2, sticky="ew", pady=(2, 0))
        self.sign_status_var = tk.StringVar(value="")
        self.sign_status_lbl = ttk.Label(left, textvariable=self.sign_status_var, style="Status.TLabel")
        self.sign_status_lbl.grid(row=17, column=2, sticky="w")

        self.verify_btn = ttk.Button(left, text="Verify Signature", command=self.verify_signature, state=tk.DISABLED, style="Accent.TButton")
        self.verify_btn.grid(row=18, column=0, columnspan=2, sticky="ew", pady=(2, 0))
        self.verify_status_text_var = tk.StringVar(value="")
        self.verify_status_lbl2 = ttk.Label(left, textvariable=self.verify_status_text_var, style="Status.TLabel")
        self.verify_status_lbl2.grid(row=18, column=2, sticky="w")

        # Utility
        ttk.Separator(left, orient=tk.HORIZONTAL).grid(row=19, column=0, columnspan=3, sticky="ew", pady=6)
        ttk.Label(left, text="Utility", style="Heading.TLabel").grid(row=20, column=0, columnspan=3, sticky="w")
        ttk.Label(left, text="Get random").grid(row=21, column=0, sticky="w")
        self.gr_size_entry = ttk.Entry(left, width=5)
        self.gr_size_entry.insert(0, "32")
        self.gr_size_entry.grid(row=21, column=1, sticky="w", padx=(0, 6))
        self.get_random_btn = ttk.Button(left, text="Get Random", command=self.get_random, state=tk.DISABLED, style="Accent.TButton")
        self.get_random_btn.grid(row=21, column=2, sticky="ew")

        # Operations Log (moved to left sidebar)
        ttk.Separator(left, orient=tk.HORIZONTAL).grid(row=24, column=0, columnspan=3, sticky="ew", pady=6)
        ttk.Label(left, text="Operations Log", style="Heading.TLabel").grid(row=25, column=0, columnspan=3, sticky="w")
        self.op_text = tk.Text(left, height=8, wrap=tk.WORD)
        self.op_text.grid(row=26, column=0, columnspan=3, sticky="nsew")

        for r in range(0, 27):
            left.rowconfigure(r, pad=2)
        # Make all three columns participate in horizontal growth
        left.columnconfigure(0, weight=1)
        left.columnconfigure(1, weight=1)
        left.columnconfigure(2, weight=1)
        # Let the ops log take any extra vertical space in the left sidebar
        left.rowconfigure(26, weight=1)

        # Bottom area (Session Info)
        bottom = ttk.Frame(right, padding=12, style="TFrame")
        # Keep session info anchored at the bottom without vertical expansion
        bottom.grid(row=1, column=0, sticky="ew")
        bottom.columnconfigure(0, weight=1)
        ttk.Label(bottom, text="Session Info", style="Heading.TLabel").grid(row=0, column=0, sticky="w")
        info = ttk.Frame(bottom, padding=(8, 6), style="Pane.TFrame")
        info.grid(row=1, column=0, sticky="ew")
        info.columnconfigure(1, weight=1)

        ttk.Label(info, text="Key Handle (hex):").grid(row=0, column=0, sticky="w")
        self.handle_var = tk.StringVar(value="-")
        ttk.Label(info, textvariable=self.handle_var).grid(row=0, column=1, sticky="w")

        ttk.Label(info, text="Public Key (hex, truncated):").grid(row=1, column=0, sticky="w")
        self.pk_preview_var = tk.StringVar(value="-")
        ttk.Label(info, textvariable=self.pk_preview_var, wraplength=900, justify=tk.LEFT).grid(row=1, column=1, sticky="ew")

        ttk.Label(info, text="Signature (hex, truncated):").grid(row=2, column=0, sticky="w")
        self.sig_preview_var = tk.StringVar(value="-")
        ttk.Label(info, textvariable=self.sig_preview_var, wraplength=900, justify=tk.LEFT).grid(row=2, column=1, sticky="ew")

        ttk.Label(info, text="Verify Status:").grid(row=3, column=0, sticky="w")
        self.verify_status_var = tk.StringVar(value="-")
        ttk.Label(info, textvariable=self.verify_status_var).grid(row=3, column=1, sticky="w")

        # Logs (right/top)
        ttk.Label(logs, text="TX (commands sent)", style="Heading.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(logs, text="RX (responses received)", style="Heading.TLabel").grid(row=0, column=1, sticky="w")
        # Use plain Text widgets (no visible scrollbars)
        self.tx_text = tk.Text(logs, height=18)
        self.rx_text = tk.Text(logs, height=18)
        self.tx_text.grid(row=1, column=0, sticky="nsew", padx=(0, 8))
        self.rx_text.grid(row=1, column=1, sticky="nsew")

        mono = tkfont.nametofont("TkFixedFont")
        mono.configure(size=10)
        for w in (self.tx_text, self.rx_text):
            w.configure(font=mono, background=self.colors["pane_bg"], foreground=self.colors["text_fg"],
                        insertbackground=self.colors["text_fg"], borderwidth=1, relief="solid", highlightthickness=0)
            w.tag_configure("title", foreground=self.colors["accent"], font=("TkDefaultFont", 9, "bold"))
            w.tag_configure("hdr", foreground=self.colors["blue"])      # header
            w.tag_configure("hdl", foreground=self.colors["purple"])    # handles
            w.tag_configure("auth", foreground=self.colors["orange"])   # auth area
            w.tag_configure("prm", foreground=self.colors["green"])     # parameters
            w.tag_configure("sig", foreground=self.colors["red"])       # signature
            w.tag_configure("sz", foreground=self.colors["muted"])      # sizes
            # Enable mouse wheel scrolling even without a visible scrollbar
            try:
                self._bind_text_scroll(w)
            except Exception:
                pass

        # Style the Operations Log (now in left sidebar, no scrollbar)
        self.op_text.configure(font=mono, background=self.colors["pane_bg"], foreground=self.colors["text_fg"],
                               insertbackground=self.colors["text_fg"], borderwidth=1, relief="solid", highlightthickness=0)
        try:
            self._bind_text_scroll(self.op_text)
        except Exception:
            pass

        # Adjust rows to stretch properly
        logs.rowconfigure(1, weight=1)  # TX/RX area grows

        # Make panes read-only for user input
        for w in (self.tx_text, self.rx_text, self.op_text):
            try:
                w.configure(state=tk.DISABLED)
            except Exception:
                pass

        # Theme toggle: only Dark (darkly) and Light (lumen). Compact UI.
        if ttkb is not None:
            style_obj = self._style
            toolbar = ttk.Frame(root, padding=(4, 2))
            toolbar.grid(row=0, column=1, sticky="ne", padx=(0, 8), pady=(4, 0))
            self.theme_mode = tk.StringVar(value="dark")

            def _apply_theme(mode: str):
                try:
                    style_obj.theme_use("darkly" if mode == "dark" else "lumen")
                except Exception:
                    pass
                # Update our color palette and refresh dependent widgets/styles
                if mode == "dark":
                    self.colors = {
                        "pane_bg": "#0F141A",
                        "text_fg": "#E6EDF3",
                        "accent": "#4EA1FF",
                        "blue": "#61AFEF",
                        "purple": "#C678DD",
                        "orange": "#D19A66",
                        "green": "#98C379",
                        "red": "#E06C75",
                        "muted": "#7F848E",
                    }
                    accent_active = "#6EB3FF"
                else:
                    self.colors = {
                        "pane_bg": "#FFFFFF",
                        "text_fg": "#111111",
                        "accent": "#0066CC",
                        "blue": "#1F4B99",
                        "purple": "#6B2D84",
                        "orange": "#B36B00",
                        "green": "#1E7F3F",
                        "red": "#B00020",
                        "muted": "#6E6E6E",
                    }
                # Do not override Accent.TButton colors; let the theme handle it for consistency.
                try:
                    self._refresh_color_deps()
                except Exception:
                    pass

            def _on_toggle(*_):
                _apply_theme(self.theme_mode.get())

            dark_btn = ttk.Radiobutton(toolbar, text="Dark", variable=self.theme_mode, value="dark")
            light_btn = ttk.Radiobutton(toolbar, text="Light", variable=self.theme_mode, value="light")
            dark_btn.grid(row=0, column=0, padx=(0, 4))
            light_btn.grid(row=0, column=1)
            self.theme_mode.trace_add('write', _on_toggle)
            # Ensure default dark theme applied
            _apply_theme("dark")

    def _refresh_color_deps(self):
        """Refresh colors on widgets/tags that don't auto-update with theme."""
        # Text widgets backgrounds and foregrounds
        for w in getattr(self, "tx_text", None), getattr(self, "rx_text", None), getattr(self, "op_text", None):
            if not w:
                continue
            try:
                w.configure(background=self.colors["pane_bg"], foreground=self.colors["text_fg"], insertbackground=self.colors["text_fg"])
            except Exception:
                pass
        # Retag TX/RX color tags
        for w in getattr(self, "tx_text", None), getattr(self, "rx_text", None):
            if not w:
                continue
            try:
                w.tag_configure("title", foreground=self.colors["accent"], font=("TkDefaultFont", 9, "bold"))
                w.tag_configure("hdr", foreground=self.colors["blue"])      # header
                w.tag_configure("hdl", foreground=self.colors["purple"])    # handles
                w.tag_configure("auth", foreground=self.colors["orange"])   # auth area
                w.tag_configure("prm", foreground=self.colors["green"])     # parameters
                w.tag_configure("sig", foreground=self.colors["red"])       # signature
                w.tag_configure("sz", foreground=self.colors["muted"])      # sizes
            except Exception:
                pass

    # connection
    def connect(self):
        if self.uart is not None:
            return
        # Reset connection progress
        self.conn_stage1_var.set(False)
        self.conn_stage2_var.set(False)
        self.conn_stage3_var.set(False)
        # Reset stage labels and start timer baseline
        self._stage1_base = "Connecting to transport"
        self._stage2_base = "Waiting for platform READY"
        self._stage3_base = "Waiting for Startup(CLEAR) answer"
        try:
            self.stage1_cb.configure(text=self._stage1_base)
            self.stage2_cb.configure(text=self._stage2_base)
            self.stage3_cb.configure(text=self._stage3_base)
        except Exception:
            pass
        self._connect_t0 = time.perf_counter()
        self._conn_t1 = None
        self._conn_t2 = None
        try:
            self.ready_label.grid_remove()
        except Exception:
            pass

        # Lock controls and show connecting status
        self.connect_btn.config(state=tk.DISABLED)
        self.disconnect_btn.config(state=tk.DISABLED)
        self.tcp_radio.config(state=tk.DISABLED)
        self.serial_radio.config(state=tk.DISABLED)
        self._disable_conn_fields()
        self._set_status("Connecting...", "warning")
        self._op("Connecting...")

        mode = self.mode_var.get()
        host = self.host_entry.get().strip() or "localhost"
        port = int(self.port_entry.get().strip() or 4327)
        ser_dev = self.ser_entry.get().strip()
        baud = int(self.baud_entry.get().strip() or 115200)

        def do_connect():
            try:
                if mode == "serial":
                    uart = UARTConnection(
                        mode="serial",
                        serial_port=ser_dev,
                        baudrate=baud,
                        serial_timeout=0.1,
                        debug=True,
                        name="Dashboard",
                    )
                else:
                    uart = UARTConnection(
                        mode="tcp",
                        tcp_host=host,
                        tcp_port=port,
                        tcp_connect_timeout=600,
                        debug=True,
                        name="Dashboard",
                    )
                self.uart = uart
                # Pass latency flag directly into TPMClient
                latency = bool(self.latency_metrics)
                self.client = TPMClient(
                    self.uart,
                    on_command=self._on_command,
                    on_response=self._on_response,
                    latency_metrics=latency,
                )

                # Stage 1 complete: transport connected
                t1 = time.perf_counter()
                self._conn_t1 = t1
                dur1 = t1 - (self._connect_t0 or t1)
                self.after(0, self.conn_stage1_var.set, True)
                try:
                    self.after(0, self.stage1_cb.configure, {"text": f"{self._stage1_base} — {dur1:.2f}s"})
                except Exception:
                    pass
                self.after(0, self.disconnect_btn.config, {"state": tk.NORMAL})
                self.after(0, self._set_status, f"Connected via {mode.upper()} — waiting for READY...", "warning")
                self._op(f"Connected via {mode.upper()} — waiting for platform READY...")

                # Continue with stages 2 and 3 in a separate worker
                def ready_and_startup():
                    try:
                        if not self.uart.wait_for_ready(timeout=180):
                            raise RuntimeError("Timed out waiting for READY")
                        t2 = time.perf_counter()
                        self._conn_t2 = t2
                        dur2 = t2 - (self._conn_t1 or t2)
                        self.after(0, self.conn_stage2_var.set, True)
                        try:
                            self.after(0, self.stage2_cb.configure, {"text": f"{self._stage2_base} — {dur2:.2f}s"})
                        except Exception:
                            pass
                        self._op("READY received; sending Startup(CLEAR)...")
                        self.after(0, self._set_status, "Sending Startup(CLEAR)...", "warning")
                        self.client.startup_cmd("CLEAR")
                        t3 = time.perf_counter()
                        dur3 = t3 - (self._conn_t2 or t3)
                        self.after(0, self.conn_stage3_var.set, True)
                        try:
                            self.after(0, self.stage3_cb.configure, {"text": f"{self._stage3_base} — {dur3:.2f}s"})
                        except Exception:
                            pass
                        self._op("Startup(CLEAR) completed")
                        self.after(0, self._set_status, "Connected (ready)", "ok")
                        # Show big ready label
                        try:
                            self.ready_label.grid()
                        except Exception:
                            pass
                        self.after(0, self._set_actions_enabled, True)
                    except Exception as e:
                        self._op(f"Initialization failed: {e}")
                        self.after(0, lambda: messagebox.showerror("Initialization failed", str(e)))

                threading.Thread(target=ready_and_startup, daemon=True).start()
            except Exception as e:
                self._op(f"Connection failed: {e}")
                self.after(0, lambda: messagebox.showerror("Connection failed", str(e)))
                # Re-enable controls to try again
                self.after(0, self.connect_btn.config, {"state": tk.NORMAL})
                self.after(0, self.tcp_radio.config, {"state": tk.NORMAL})
                self.after(0, self.serial_radio.config, {"state": tk.NORMAL})
                self.after(0, self._enable_conn_fields)

        threading.Thread(target=do_connect, daemon=True).start()

    def disconnect(self):
        if self.uart:
            try:
                self.uart.close()
            except Exception:
                pass
        self.uart = None
        self.client = None
        self.key_handle = None
        self.pubkey = None
        self.signature = None
        self.ticket = None
        self.handle_var.set("-")
        self.pk_preview_var.set("-")
        self.sig_preview_var.set("-")
        self.verify_status_var.set("-")
        self.status_var.set("Disconnected")
        # Reset connection indicators
        self.conn_stage1_var.set(False)
        self.conn_stage2_var.set(False)
        self.conn_stage3_var.set(False)
        try:
            # Restore base texts
            self.stage1_cb.configure(text=self._stage1_base)
            self.stage2_cb.configure(text=self._stage2_base)
            self.stage3_cb.configure(text=self._stage3_base)
        except Exception:
            pass
        try:
            self.ready_label.grid_remove()
        except Exception:
            pass
        self.connect_btn.config(state=tk.NORMAL)
        self.disconnect_btn.config(state=tk.DISABLED)
        self._set_actions_enabled(False)
        self._op("Disconnected")

    # structured TX/RX
    def _on_command(self, name: str, data: bytes, meta: dict):
        meta = dict(meta or {})
        meta.setdefault("name", name)
        # Mark last command for timing
        self._last_cmd_name = name
        self._last_cmd_t0 = time.perf_counter()
        ts = time.strftime("%H:%M:%S")
        self.after(0, self._append_packet, self.tx_text, f"[{ts}] [TX] {name} (len={len(data)})\n", data, True, meta)

    def _on_response(self, name: str, data: bytes, meta: dict):
        meta = dict(meta or {})
        meta.setdefault("name", name)
        ts = time.strftime("%H:%M:%S")
        if self._last_cmd_name == name and self._last_cmd_t0:
            elapsed = time.perf_counter() - self._last_cmd_t0
            title = f"[{ts}] [RX] {name} (len={len(data)}) — {elapsed:.2f}s\n"
        else:
            title = f"[{ts}] [RX] {name} (len={len(data)})\n"
        self.after(0, self._append_packet, self.rx_text, title, data, False, meta)

    def _append_packet(self, widget: ScrolledText, title: str, data: bytes, is_cmd: bool, meta: dict):
        # Safe insert into read-only text widget
        prev = widget.cget("state")
        widget.configure(state=tk.NORMAL)
        # Add a blank line between packets for readability
        try:
            if widget.index("end-1c") != "1.0":
                widget.insert(tk.END, "\n")
        except Exception:
            pass
        widget.insert(tk.END, title, ("title",))
        for label, start, end, tag in self._segment_packet(data, is_cmd, meta):
            chunk = data[start:end]
            if not chunk:
                continue
            hexs = chunk.hex().upper()
            spaced = " ".join(hexs[i:i+2] for i in range(0, len(hexs), 2))
            seg_tag = f"seg_{id(widget)}_{start}_{end}_{tag}"
            widget.insert(tk.END, spaced + " ", (tag, seg_tag))
            # Bind tooltip for this segment
            desc = self._seg_label_desc(label, end - start)
            try:
                widget.tag_bind(seg_tag, "<Enter>", lambda e, t=desc: self._show_tooltip(e.x_root, e.y_root, t))
                widget.tag_bind(seg_tag, "<Leave>", lambda e: self._hide_tooltip())
            except Exception:
                pass
        widget.insert(tk.END, "\n")
        widget.configure(state=prev)
        widget.see(tk.END)

    def _segment_packet(self, data: bytes, is_cmd: bool, meta: dict):
        segs = []
        n = len(data)
        if n == 0:
            return segs
        hdr_end = min(10, n)
        segs.append(("hdr", 0, hdr_end, "hdr"))
        if n <= 10:
            return segs
        tag = int.from_bytes(data[0:2], "big")

        def add(label, s, e, t):
            if s < e:
                segs.append((label, s, e, t))

        if is_cmd:
            nm = str(meta.get("name") or "")
            if tag == 0x8001:
                if nm.startswith("Startup") or nm.startswith("GetRandom"):
                    add("params", 10, min(12, n), "prm")
                elif nm.startswith("HashVerifyStart"):
                    pos = 10
                    add("handle", pos, min(pos+4, n), "hdl"); pos += 4
                    add("params", pos, min(pos+4, n), "prm"); pos += 4
                    if pos + 6 <= n:
                        add("sigHdr", pos, pos+6, "sig")
                        sig_len = int.from_bytes(data[pos+4:pos+6], "big")
                        pos += 6
                        add("sig", pos, min(pos+sig_len, n), "sig")
                    else:
                        add("params", pos, n, "prm")
                else:
                    add("params", 10, n, "prm")
            else:
                pos = 10
                if nm in ("HashSignStart", "SequenceUpdate", "HashSignFinish", "HashVerifyFinish", "CreatePrimary(Dilithium)", "CreatePrimary(ECC)"):
                    add("handle", pos, min(pos+4, n), "hdl"); pos += 4
                if pos + 4 <= n:
                    auth_size = int.from_bytes(data[pos:pos+4], "big")
                    add("authSize", pos, pos+4, "sz"); pos += 4
                    add("auth", pos, min(pos+auth_size, n), "auth"); pos += auth_size
                add("params", pos, n, "prm")
        else:
            pos = 10
            handles_out = int(meta.get("handles_out", 0) or 0)
            add("handles", pos, min(pos + 4*handles_out, n), "hdl"); pos += 4*handles_out
            if tag == 0x8002 and pos + 4 <= n:
                add("paramSize", pos, pos+4, "sz"); pos += 4
            add("params", pos, n, "prm")
        return segs

    def _seg_label_desc(self, label: str, length: int) -> str:
        name_map = {
            "hdr": "Header",
            "handle": "Handle",
            "handles": "Handles",
            "auth": "Auth area",
            "authSize": "Auth size",
            "params": "Parameters",
            "sig": "Signature",
            "sigHdr": "Signature header",
            "sz": "Size field",
        }
        pretty = name_map.get(label, label)
        return f"{pretty} — {length} bytes"

    def _show_tooltip(self, x: int, y: int, text: str):
        try:
            self._hide_tooltip()
            tw = tk.Toplevel(self)
            tw.wm_overrideredirect(True)
            tw.wm_geometry(f"+{x+12}+{y+12}")
            frm = ttk.Frame(tw, padding=(6, 4), style="Pane.TFrame")
            frm.pack(fill=tk.BOTH, expand=True)
            lbl = ttk.Label(frm, text=text)
            lbl.pack()
            self._tooltip_win = tw
        except Exception:
            self._tooltip_win = None

    def _hide_tooltip(self):
        try:
            if self._tooltip_win is not None:
                self._tooltip_win.destroy()
        except Exception:
            pass
        self._tooltip_win = None

    def _bind_text_scroll(self, widget: tk.Text):
        # Cross-platform mouse wheel support (Linux uses Button-4/5)
        def _on_mousewheel(event):
            try:
                if getattr(event, 'num', None) == 4 or getattr(event, 'delta', 0) > 0:
                    widget.yview_scroll(-3, "units")
                else:
                    widget.yview_scroll(3, "units")
                return "break"
            except Exception:
                return None
        widget.bind("<MouseWheel>", _on_mousewheel)
        widget.bind("<Button-4>", _on_mousewheel)
        widget.bind("<Button-5>", _on_mousewheel)

    # logs
    def _poll_logs(self):
        self.op_log.drain_to_text(self.op_text)
        self.after(100, self._poll_logs)

    def _op(self, line: str):
        ts = time.strftime("%H:%M:%S")
        print(f"[{ts}] {line}")
        self.op_log.put(f"[{ts}] {line}")

    # helpers
    def _disable_all_ops(self):
        self.busy = True
        for btn in (self.create_key_btn, self.get_random_btn, self.sign_btn, self.verify_btn):
            btn.config(state=tk.DISABLED)

    def _enable_all_ops(self):
        self.busy = False
        self._update_action_buttons()

    def _update_action_buttons(self):
        connected = self.uart is not None and not self.busy
        self.create_key_btn.config(state=(tk.NORMAL if connected else tk.DISABLED))
        self.get_random_btn.config(state=(tk.NORMAL if connected else tk.DISABLED))
        can_sign = connected and (self.key_handle is not None)
        self.sign_btn.config(state=(tk.NORMAL if can_sign and not self.busy else tk.DISABLED))
        can_verify = connected and (self.key_handle is not None) and (self.signature is not None)
        self.verify_btn.config(state=(tk.NORMAL if can_verify and not self.busy else tk.DISABLED))

    def _set_actions_enabled(self, enabled: bool):
        state = tk.NORMAL if enabled else tk.DISABLED
        self.create_key_btn.config(state=state)
        self.get_random_btn.config(state=state)
        self._update_action_buttons()

    def _set_status(self, text: str, level: str = "info"):
        self.status_var.set(text)
        if level == "ok":
            self.status_label.configure(foreground=self.colors["green"])
        elif level == "warning":
            self.status_label.configure(foreground=self.colors["orange"])
        elif level == "error":
            self.status_label.configure(foreground=self.colors["red"])
        else:
            self.status_label.configure(foreground=self.colors["muted"])

    # Toggle connection field visibility and state
    def _update_conn_fields(self):
        mode = self.mode_var.get()
        if mode == "tcp":
            self._grid_show(self.tcp_host_label, self.host_entry, self.tcp_port_label, self.port_entry)
            self._grid_hide(self.serial_dev_label, self.ser_entry, self.baud_label, self.baud_entry)
        else:
            self._grid_show(self.serial_dev_label, self.ser_entry, self.baud_label, self.baud_entry)
            self._grid_hide(self.tcp_host_label, self.host_entry, self.tcp_port_label, self.port_entry)

    def _grid_hide(self, *widgets):
        for w in widgets:
            try:
                w.grid_remove()
            except Exception:
                pass

    def _grid_show(self, *widgets):
        for w in widgets:
            try:
                w.grid()
            except Exception:
                pass

    def _disable_conn_fields(self):
        for w in (self.host_entry, self.port_entry, self.ser_entry, self.baud_entry):
            try:
                w.config(state=tk.DISABLED)
            except Exception:
                pass

    def _enable_conn_fields(self):
        mode = self.mode_var.get()
        try:
            self.host_entry.config(state=(tk.NORMAL if mode == "tcp" else tk.DISABLED))
            self.port_entry.config(state=(tk.NORMAL if mode == "tcp" else tk.DISABLED))
            self.ser_entry.config(state=(tk.NORMAL if mode == "serial" else tk.DISABLED))
            self.baud_entry.config(state=(tk.NORMAL if mode == "serial" else tk.DISABLED))
        except Exception:
            pass

    def _parse_hex_entry(self, entry: ttk.Entry) -> Optional[bytes]:
        s = entry.get().strip().replace(" ", "")
        if not s:
            return b""
        try:
            return bytes.fromhex(s)
        except ValueError:
            messagebox.showerror("Invalid hex", "Please enter a valid hex string (even number of characters).")
            return None

    # actions
    def create_key(self):
        if not self.client:
            return
        if self.busy:
            return

        def worker():
            try:
                self._op("CreatePrimary (Dilithium) starting…")
                resp = self.client.create_primary_dilithium_cmd()
                handle = self.client.extract_first_handle_from_response(resp)
                pub = _parse_createprimary_outpublic(resp)
                pk = pub.get("pub") if pub.get("type") == "dilithium" else None
                if pk is None:
                    raise RuntimeError("CreatePrimary did not return a Dilithium public key")
                self.after(0, self._on_key_created, handle, pk)
                self._op("CreatePrimary (Dilithium) done")
                self.after(0, self._action_end, "create", self.create_status_var, True)
            except Exception as e:
                self._op(f"CreatePrimary failed: {e}")
                self.after(0, lambda: messagebox.showerror("CreatePrimary failed", str(e)))
                self.after(0, self._action_end, "create", self.create_status_var, False)
            finally:
                self.after(0, self._enable_all_ops)

        self._disable_all_ops()
        self._action_begin("create", self.create_status_var)
        threading.Thread(target=worker, daemon=True).start()

    def _on_key_created(self, handle: int, pk: bytes):
        self.key_handle = handle
        self.pubkey = pk
        self.handle_var.set(f"0x{handle:08X}")
        preview = pk.hex().upper()
        if len(preview) > 120:
            preview = preview[:120] + "…"
        self.pk_preview_var.set(f"{preview}  (len={len(pk)})")
        self._update_action_buttons()

    def fill_random_message(self):
        try:
            n = int(self.rand_size_entry.get().strip() or "0")
            n = max(0, min(65535, n))
        except Exception:
            n = 0
        import os
        msg = os.urandom(n)
        self.msg_entry.delete(0, tk.END)
        self.msg_entry.insert(0, msg.hex().upper())
        self._op(f"Message field filled with {n} random bytes (hex)")

    def sign_message(self):
        if not self.client or self.key_handle is None:
            messagebox.showwarning("No key", "Create a Dilithium key first.")
            return
        if self.busy:
            return
        msg_bytes = self._parse_hex_entry(self.msg_entry)
        if msg_bytes is None:
            return

        def worker():
            try:
                self._op(f"HashSignStart (len={len(msg_bytes)})…")
                seq = self.client.hashsign_start_cmd(self.key_handle, len(msg_bytes), key_pw=b"abcd")
                chunk_size = 256
                sent = 0
                while sent < len(msg_bytes):
                    chunk = msg_bytes[sent: sent + chunk_size]
                    self.client.sequence_update_cmd(seq, chunk)
                    sent += len(chunk)
                sig = self.client.hashsign_finish_cmd(seq)
                self.after(0, self._on_signature_ready, msg_bytes, sig)
                self._op("HashSign finished")
                self.after(0, self._action_end, "sign", self.sign_status_var, True)
            except Exception as e:
                self._op(f"Sign failed: {e}")
                self.after(0, lambda: messagebox.showerror("Sign failed", str(e)))
                self.after(0, self._action_end, "sign", self.sign_status_var, False)
            finally:
                self.after(0, self._enable_all_ops)

        self._disable_all_ops()
        self._action_begin("sign", self.sign_status_var)
        threading.Thread(target=worker, daemon=True).start()

    def _on_signature_ready(self, msg: bytes, sig: bytes):
        self.signature = sig
        prev = sig.hex().upper()
        if len(prev) > 120:
            prev = prev[:120] + "…"
        self.sig_preview_var.set(f"{prev}  (len={len(sig)})")
        self.verify_status_var.set("-")
        self._update_action_buttons()

    def verify_signature(self):
        if not self.client or self.key_handle is None or self.signature is None:
            messagebox.showwarning("Missing data", "Need key and signature.")
            return
        if self.busy:
            return
        msg_bytes = self._parse_hex_entry(self.msg_entry)
        if msg_bytes is None:
            return

        def worker():
            try:
                self._op(f"HashVerifyStart (len={len(msg_bytes)})…")
                seq = self.client.hashverify_start_cmd(self.key_handle, len(msg_bytes), self.signature)
                chunk_size = 256
                sent = 0
                while sent < len(msg_bytes):
                    chunk = msg_bytes[sent: sent + chunk_size]
                    self.client.sequence_update_cmd(seq, chunk)
                    sent += len(chunk)
                ticket = self.client.hashverify_finish_cmd(seq)
                self.after(0, self._on_verified, ticket)
                self._op("HashVerify finished (OK)")
                self.after(0, self._action_end, "verify", self.verify_status_var, True)
            except Exception as e:
                self._op(f"Verify failed: {e}")
                self.after(0, lambda: messagebox.showerror("Verify failed", str(e)))
                self.after(0, self._action_end, "verify", self.verify_status_var, False)
            finally:
                self.after(0, self._enable_all_ops)

        self._disable_all_ops()
        self._action_begin("verify", self.verify_status_var)
        threading.Thread(target=worker, daemon=True).start()

    def _on_verified(self, ticket: tuple):
        self.ticket = ticket
        self.verify_status_var.set("OK (ticket received)")

    def get_random(self):
        if not self.client:
            return
        if self.busy:
            return
        try:
            n = int(self.gr_size_entry.get().strip() or "32")
            n = max(1, min(65535, n))
        except Exception:
            n = 32

        def worker():
            try:
                self._op(f"GetRandom({n})…")
                rsp = self.client.get_random_cmd(num_bytes=n)
                off = _sessions_param_offset(rsp, response_handle_count=0)
                if off + 2 <= len(rsp):
                    size = int.from_bytes(rsp[off:off+2], 'big')
                    rnd = rsp[off+2:off+2+size]
                else:
                    rnd = b""
                preview = rnd.hex().upper()
                if len(preview) > 120:
                    preview = preview[:120] + "…"
                self._op(f"GetRandom returned {len(rnd)} bytes: {preview}")
            except Exception as e:
                self._op(f"GetRandom failed: {e}")
                messagebox.showerror("GetRandom failed", str(e))
            finally:
                self.after(0, self._enable_all_ops)

        self._disable_all_ops()
        threading.Thread(target=worker, daemon=True).start()

    # --- action status helpers ---
    def _action_begin(self, name: str, var: tk.StringVar):
        self._running_action = name
        self._running_t0 = time.perf_counter()
        var.set("Executing… 0.0s")
        self._tick_action_timer(name, var)

    def _tick_action_timer(self, name: str, var: tk.StringVar):
        if self._running_action == name:
            elapsed = time.perf_counter() - self._running_t0
            try:
                var.set(f"Executing… {elapsed:.1f}s")
            except Exception:
                pass
            # continue updating
            self.after(200, self._tick_action_timer, name, var)

    def _action_end(self, name: str, var: tk.StringVar, success: bool = True):
        if self._running_action == name:
            elapsed = time.perf_counter() - self._running_t0
            mark = "✓" if success else "✗"
            text = (
                f"Done {mark} in {elapsed:.2f}s"
                if success
                else f"Error {mark} after {elapsed:.2f}s"
            )
            try:
                var.set(text)
            except Exception:
                pass
            self._running_action = None


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="TPM Dilithium Dashboard")
    parser.add_argument(
        "--latency-metrics",
        action="store_true",
        help=(
            "Expect two READYs per TPM command (latency record + response) "
            "and log per-command latency."
        ),
    )
    args = parser.parse_args()

    # Pass flag directly into the dashboard; no post-hoc mutation
    app = TPMDashboard(latency_metrics=bool(args.latency_metrics))
    app.mainloop()
