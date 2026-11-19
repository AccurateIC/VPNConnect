"""Tkinter front end. All NetworkManager calls run in worker threads; widgets are
only touched from the Tk main loop (results come back through a queue)."""

from __future__ import annotations

import queue
import threading
import time
import tkinter as tk
import webbrowser
from tkinter import filedialog, messagebox, scrolledtext, ttk

from . import __version__, nm, settings

POLL_MS = 150
STATUS_REFRESH_MS = 5000


class App:
    def __init__(self, root: tk.Tk, cfg: settings.Settings):
        self.root, self.cfg = root, cfg
        self.events: queue.Queue = queue.Queue()
        self.busy = False
        self.connected_at: float | None = None
        self.status = nm.Status(exists=False, state="missing")

        root.title(f"{cfg.connection_name} - VPNConnect")
        root.minsize(480, 420)
        root.protocol("WM_DELETE_WINDOW", self.on_close)

        main = ttk.Frame(root, padding=14)
        main.pack(fill="both", expand=True)
        main.columnconfigure(1, weight=1)

        self.state_var = tk.StringVar(value="Checking ...")
        self.state_label = ttk.Label(main, textvariable=self.state_var, font=("TkDefaultFont", 13, "bold"))
        self.state_label.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))

        ttk.Label(main, text="Username").grid(row=1, column=0, sticky="e", padx=(0, 8), pady=3)
        self.username = ttk.Entry(main)
        self.username.grid(row=1, column=1, sticky="ew", pady=3)

        ttk.Label(main, text="Password").grid(row=2, column=0, sticky="e", padx=(0, 8), pady=3)
        self.password = ttk.Entry(main, show="•")
        self.password.grid(row=2, column=1, sticky="ew", pady=3)
        self.password.bind("<Return>", lambda _e: self.on_connect())

        self.otp = None
        if cfg.otp:
            ttk.Label(main, text="OTP code").grid(row=3, column=0, sticky="e", padx=(0, 8), pady=3)
            self.otp = ttk.Entry(main, width=10)
            self.otp.grid(row=3, column=1, sticky="w", pady=3)
            self.otp.bind("<Return>", lambda _e: self.on_connect())

        buttons = ttk.Frame(main)
        buttons.grid(row=4, column=0, columnspan=2, sticky="ew", pady=12)
        self.connect_btn = ttk.Button(buttons, text="Connect", command=self.on_connect)
        self.connect_btn.pack(side="left")
        self.disconnect_btn = ttk.Button(buttons, text="Disconnect", command=self.on_disconnect)
        self.disconnect_btn.pack(side="left", padx=6)
        ttk.Button(buttons, text="Import .ovpn ...", command=self.on_import).pack(side="right")
        if cfg.portal_url:
            ttk.Button(buttons, text="Get profile", command=lambda: webbrowser.open(cfg.portal_url)).pack(
                side="right", padx=6
            )

        self.log_box = scrolledtext.ScrolledText(main, height=10, state="disabled", wrap="word")
        self.log_box.grid(row=5, column=0, columnspan=2, sticky="nsew")
        main.rowconfigure(5, weight=1)
        ttk.Label(main, text=f"v{__version__}", foreground="gray").grid(row=6, column=1, sticky="e")

        self.root.after(POLL_MS, self._poll)
        self.root.after(STATUS_REFRESH_MS, self._refresh_loop)
        self._background(self._first_run)

    # ---- threading helpers -------------------------------------------------
    def _background(self, fn, *args):
        self.busy = True
        self._update_buttons()

        def worker():
            try:
                fn(*args)
            except nm.VPNError as exc:
                self.events.put(("error", str(exc)))
            except Exception as exc:  # never let a worker die silently
                self.events.put(("error", f"Unexpected error: {exc}"))
            finally:
                self.events.put(("refresh", nm.status(self.cfg.connection_name)))
                self.events.put(("idle", None))

        threading.Thread(target=worker, daemon=True).start()

    def log(self, msg: str):
        self.events.put(("log", msg))

    def _poll(self):
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "log":
                    self._append(payload)
                elif kind == "error":
                    self._append("✖ " + payload)
                    messagebox.showerror("VPNConnect", payload, parent=self.root)
                elif kind == "refresh":
                    self._apply_status(payload)
                elif kind == "idle":
                    self.busy = False
                    self._update_buttons()
        except queue.Empty:
            pass
        self._check_session_limit()
        self.root.after(POLL_MS, self._poll)

    def _append(self, msg: str):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", time.strftime("%H:%M:%S  ") + msg + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    # ---- state ---------------------------------------------------------------
    def _apply_status(self, st: nm.Status):
        was_connected = self.status.connected
        self.status = st
        if st.connected and not was_connected:
            self.connected_at = time.monotonic()
        elif not st.connected:
            self.connected_at = None
        if st.username and not self.username.get():
            self.username.insert(0, st.username)
        label = {
            "missing": "No profile - import your .ovpn file",
            "connected": "● Connected",
            "connecting": "Connecting ...",
            "disconnected": "○ Disconnected",
        }.get(st.state, st.state)
        self.state_var.set(label)
        self.state_label.configure(foreground="#1a7f37" if st.connected else "")
        self._update_buttons()

    def _update_buttons(self):
        idle = not self.busy
        self.connect_btn.state(["!disabled"] if idle and self.status.exists and not self.status.connected else ["disabled"])
        self.disconnect_btn.state(["!disabled"] if idle and self.status.connected else ["disabled"])

    def _refresh_loop(self):
        if not self.busy:
            threading.Thread(
                target=lambda: self.events.put(("refresh", nm.status(self.cfg.connection_name))), daemon=True
            ).start()
        self.root.after(STATUS_REFRESH_MS, self._refresh_loop)

    def _check_session_limit(self):
        limit = self.cfg.session_limit_minutes
        if limit and self.connected_at and not self.busy:
            if time.monotonic() - self.connected_at >= limit * 60:
                self.connected_at = None
                self.log(f"Session limit of {limit} min reached - disconnecting.")
                self._background(nm.disconnect, self.cfg.connection_name)

    # ---- actions ---------------------------------------------------------------
    def _first_run(self):
        st = nm.status(self.cfg.connection_name)
        if not st.exists and settings.SYSTEM_PROFILE.is_file():
            self.log("Importing company VPN profile ...")
            nm.import_profile(settings.SYSTEM_PROFILE, self.cfg.connection_name)
            st = nm.status(self.cfg.connection_name)
        if not st.exists:
            self.log("Step 1: click 'Import .ovpn ...' and choose your VPN profile.")
            if self.cfg.portal_url:
                self.log("No profile yet? Click 'Get profile' to download it from the VPN portal.")
        else:
            self.log("Enter your password and click Connect.")

    def on_import(self):
        path = filedialog.askopenfilename(
            parent=self.root, title="Choose your VPN profile",
            filetypes=[("OpenVPN profile", "*.ovpn"), ("All files", "*")],
        )
        if not path:
            return
        username = self.username.get().strip()

        def job():
            if self.status.connected:
                nm.disconnect(self.cfg.connection_name)
            nm.import_profile(path, self.cfg.connection_name, username)
            self.log(f"Imported profile from {path}.")

        self._background(job)

    def on_connect(self):
        if self.busy or not self.status.exists or self.status.connected:
            return
        username = self.username.get().strip()
        password = self.password.get()
        if self.otp is not None:
            password += self.otp.get().strip()
            self.otp.delete(0, "end")
        if not username or not password:
            messagebox.showwarning("VPNConnect", "Enter your username and password.", parent=self.root)
            return
        self.password.delete(0, "end")
        self.state_var.set("Connecting ...")

        def job():
            self.log("Connecting ...")
            nm.connect(
                self.cfg.connection_name, password,
                username if username != self.status.username else "",
            )
            msg = "Connected."
            if self.cfg.session_limit_minutes:
                msg += f" You will be disconnected after {self.cfg.session_limit_minutes} min."
            self.log(msg)

        self._background(job)

    def on_disconnect(self):
        def job():
            nm.disconnect(self.cfg.connection_name)
            self.log("Disconnected.")

        self._background(job)

    def on_close(self):
        if self.status.connected and self.cfg.disconnect_on_exit:
            try:
                nm.disconnect(self.cfg.connection_name)
            except nm.VPNError:
                pass
        self.root.destroy()


def run(cfg: settings.Settings) -> int:
    root = tk.Tk()
    App(root, cfg)
    root.mainloop()
    return 0
