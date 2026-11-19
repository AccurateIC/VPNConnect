"""Tkinter front end, built so any employee can connect without reading docs.

One screen per state (FR-GUI-01): Setup (no profile) -> Sign in -> Connected,
each with one primary button. Plain-language errors (FR-GUI-06), with the raw
text kept in a collapsible Details panel for IT.

Threading (BR-GUI-02): every NetworkManager call runs in a worker thread.
Widgets are touched only on the Tk main loop; workers report back through
`App.events`. Screen and error logic lives in the Tk-free `ui_model`.
"""

from __future__ import annotations

import queue
import signal
import threading
import time
import tkinter as tk
import webbrowser
from tkinter import filedialog, font as tkfont, messagebox, ttk

from . import __version__, nm, settings, ui_model

POLL_MS = 100
TICK_MS = 1000
STATUS_REFRESH_MS = 5000
CLOSE_CAP_MS = 15000  # FR-GUI-09: close anyway after this long

# Colour tokens (text on white / white on colour, all >= 4.5:1 contrast).
BG = "#ffffff"
SURFACE = "#f6f8fa"
TEXT = "#1f2328"
MUTED = "#59636e"
BORDER = "#d1d9e0"
PRIMARY = "#0969da"
PRIMARY_ACTIVE = "#0550ae"
STATUS_COLOURS = {  # FR-GUI-05
    "idle": "#59636e",
    "busy": "#9a6700",
    "ok": "#1a7f37",
    "problem": "#cf222e",
}
ERROR_BG = "#ffebe9"
NOTICE_BG = "#ddf4ff"
LOCK_MASK = 0x2  # X11 Caps Lock modifier bit


def _setup_style(root: tk.Tk) -> dict:
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    base = tkfont.nametofont("TkDefaultFont")
    size = abs(base.cget("size")) or 10
    family = base.cget("family")
    fonts = {
        "body": (family, size),
        "small": (family, max(size - 1, 8)),
        "title": (family, size + 6, "bold"),
        "heading": (family, size + 3, "bold"),
        "big": (family, size + 2, "bold"),
    }
    root.configure(background=BG)
    style.configure(".", background=BG, foreground=TEXT, font=fonts["body"])
    style.configure("TFrame", background=BG)
    style.configure("TLabel", background=BG, foreground=TEXT)
    style.configure("Muted.TLabel", foreground=MUTED)
    style.configure("Heading.TLabel", font=fonts["heading"])
    style.configure("Footer.TFrame", background=SURFACE)
    style.configure("TCheckbutton", background=BG)
    style.map("TCheckbutton", background=[("active", BG)])
    style.configure("TEntry", padding=6, fieldbackground=BG, bordercolor=BORDER)
    style.configure("TButton", padding=(12, 6))
    style.configure("Link.TButton", padding=(6, 4), relief="flat", background=SURFACE,
                    foreground=PRIMARY, borderwidth=0)
    style.map("Link.TButton", background=[("active", BORDER)])
    style.configure("Primary.TButton", padding=(16, 9), font=fonts["big"],
                    background=PRIMARY, foreground="#ffffff", bordercolor=PRIMARY)
    style.map(
        "Primary.TButton",
        background=[("disabled", "#8c959f"), ("pressed", PRIMARY_ACTIVE), ("active", PRIMARY_ACTIVE)],
        foreground=[("disabled", "#ffffff")],
    )
    style.configure("TMenubutton", padding=(8, 4), background=SURFACE)
    return fonts


class App:
    def __init__(self, root: tk.Tk, cfg: settings.Settings, from_tray: bool = False):
        self.root, self.cfg = root, cfg
        # FR-TRAY-05: opened from the top-bar icon, the icon owns the connection,
        # so closing the window never disconnects.
        self.from_tray = from_tray
        self.raise_requested = False
        self.events: queue.Queue = queue.Queue()
        self.status = nm.Status(exists=False, state="missing")
        self.loaded = False  # first status not known yet
        self.load_failed = False  # status could not be read at all
        self.limit_retry_at = 0.0
        self.offered = None  # .ovpn currently offered on the Setup screen
        self.busy = False
        self.connecting = False
        self.closing = False
        self.connected_at: float | None = None
        self.error: ui_model.Friendly | None = None
        self.notice = ""
        self.screen = ""
        self.details_open = False

        self.fonts = _setup_style(root)
        root.title("VPNConnect")
        root.geometry("460x620")
        root.minsize(420, 580)
        root.protocol("WM_DELETE_WINDOW", self.on_close)
        root.bind("<Escape>", lambda _e: self._close_details())
        root.bind("<FocusIn>", self._on_focus, add="+")

        # Status banner (FR-GUI-05): colour + one line saying what is going on.
        self.banner = tk.Frame(root, background=STATUS_COLOURS["idle"], padx=18, pady=14)
        self.banner.pack(fill="x")
        self.banner_title = tk.Label(self.banner, font=self.fonts["title"], fg="#ffffff",
                                     background=STATUS_COLOURS["idle"], anchor="w")
        self.banner_title.pack(fill="x")
        self.banner_sub = tk.Label(self.banner, font=self.fonts["body"], fg="#ffffff",
                                   background=STATUS_COLOURS["idle"], anchor="w")
        self.banner_sub.pack(fill="x")

        # Footer: More menu (FR-GUI-07) and Details toggle (FR-GUI-06).
        footer = ttk.Frame(root, style="Footer.TFrame", padding=(10, 6))
        footer.pack(side="bottom", fill="x")
        self.more_btn = ttk.Menubutton(footer, text="More")
        self.more_menu = tk.Menu(self.more_btn, tearoff=False)
        self.more_btn["menu"] = self.more_menu
        self.more_btn.pack(side="left")
        self.details_btn = ttk.Button(footer, text="Show details", style="Link.TButton",
                                      command=self._toggle_details)
        self.details_btn.pack(side="right")

        # Details panel, collapsed by default.
        self.details = ttk.Frame(root, padding=(18, 0, 18, 8))
        self.log_box = tk.Text(self.details, height=7, wrap="word", state="disabled",
                               font=self.fonts["small"], background=SURFACE, foreground=TEXT,
                               relief="flat", highlightthickness=1, highlightbackground=BORDER)
        self.log_box.pack(fill="both", expand=True)
        ttk.Button(self.details, text="Copy for IT", style="Link.TButton",
                   command=self._copy_details).pack(anchor="e", pady=(4, 0))

        self.body = ttk.Frame(root, padding=(24, 18, 24, 12))
        self.body.pack(fill="both", expand=True)

        self._render()
        self.root.after(POLL_MS, self._poll)
        self.root.after(TICK_MS, self._tick)
        self.root.after(STATUS_REFRESH_MS, self._refresh_loop)
        self._background(self._first_run)

    # ---- threading helpers ----------------------------------------------------
    def _background(self, fn, *args):
        self.busy = True
        self._sync()

        def worker():
            try:
                fn(*args)
            except nm.VPNError as exc:
                self.events.put(("error", str(exc)))
            except Exception as exc:  # never let a worker die silently
                self.events.put(("error", f"Unexpected error: {exc}"))
            finally:
                try:
                    self._put_status()
                finally:  # always unlock the UI, whatever nm.status did
                    self.events.put(("idle", None))

        threading.Thread(target=worker, daemon=True).start()

    def _put_status(self):
        """Worker side: report the current status, or that it could not be read."""
        try:
            self.events.put(("refresh", nm.status(self.cfg.connection_name)))
        except Exception as exc:  # VPNError, PermissionError, ... never leave the UI hanging
            self.events.put(("status_failed", str(exc)))

    def log(self, msg: str):
        """Thread-safe. Never pass the password here (BR-GUI-01)."""
        self.events.put(("log", msg))

    def _poll(self):
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "log":
                    self._append(payload)
                elif kind == "error":
                    self._append("Error: " + payload)
                    self._show_error(payload)
                elif kind == "refresh":
                    self._apply_status(payload)
                elif kind == "status_failed":
                    self._append("Error: " + payload)
                    if not self.loaded:  # never stay on "Checking..." forever
                        self.load_failed = True
                        self.error = ui_model.friendly_error(payload)
                        self._sync()
                elif kind == "notice":
                    self.notice = payload
                    self._render(force=True)
                elif kind == "idle":
                    self.busy = False
                    self.connecting = False
                    self._sync()
                elif kind == "raise":
                    self.bring_to_front()
                elif kind == "closed":
                    self._destroy()
                    return
        except queue.Empty:
            pass
        self.root.after(POLL_MS, self._poll)

    def _refresh_loop(self):
        if not self.busy and not self.closing:
            threading.Thread(target=self._put_status, daemon=True).start()
        self.root.after(STATUS_REFRESH_MS, self._refresh_loop)

    # ---- state ------------------------------------------------------------------
    def _apply_status(self, st: nm.Status):
        was_connected = self.status.connected
        if self.load_failed:
            self.error = None
        self.status, self.loaded, self.load_failed = st, True, False
        if st.connected and not was_connected:
            self.connected_at = time.monotonic()
            self.error = None
        elif not st.connected:
            if was_connected and not self.busy and not self.closing and not self.notice:
                self.notice = "The VPN connection dropped. Sign in again to reconnect."
            self.connected_at = None
        self._sync()

    def _show_error(self, raw: str):
        kind = ui_model.classify_error(raw)
        self.error = ui_model.friendly_error(raw, otp=self.cfg.otp)
        self.notice = ""
        on_sign_in = self.screen == ui_model.SIGN_IN and hasattr(self, "password")
        if on_sign_in:
            self.password.delete(0, "end")
        self._render(force=True)
        if on_sign_in and self.screen == ui_model.SIGN_IN:
            # Only a wrong password sends you back to the password field.
            (self.password if kind == "auth" else self.connect_btn).focus_set()

    def _tick(self):
        """Once a second: connected timer, session countdown, session limit."""
        if self.screen == ui_model.CONNECTED and self.connected_at is not None:
            elapsed = time.monotonic() - self.connected_at
            limit = self.cfg.session_limit_minutes
            left = ui_model.minutes_left(limit, elapsed)
            text = f"Connected for {ui_model.format_duration(elapsed)}"
            if left is not None:
                text += f"  -  disconnects in {ui_model.format_minutes(left)}"
            self.timer_var.set(text)
            now = time.monotonic()
            # FR-GUI-10. connected_at stays set, so a failed disconnect is retried (every 30 s).
            if left == 0 and not self.busy and not self.closing and now >= self.limit_retry_at:
                self.limit_retry_at = now + 30
                self.notice = (f"You were signed out after {ui_model.format_minutes(limit)}, "
                               "as set by IT. Sign in again to reconnect.")
                self.log(f"Session limit of {limit} min reached - disconnecting.")
                self._background(nm.disconnect, self.cfg.connection_name)
        self.root.after(TICK_MS, self._tick)

    # ---- rendering ----------------------------------------------------------------
    def _current_screen(self) -> str:
        if self.load_failed:
            return "problem"
        if not self.loaded:
            return "loading"
        if self.connecting:
            return ui_model.SIGN_IN
        return ui_model.screen_for(self.status)

    def _sync(self):
        """Bring banner, screen and enabled-state in line with the current state."""
        self._render()
        self._update_banner()
        self._update_menu()
        self.more_btn.state(["disabled"] if self.closing else ["!disabled"])
        if self.screen == ui_model.SIGN_IN:
            locked = self.busy or self.closing
            for w in self.sign_in_inputs:
                w.state(["disabled"] if locked else ["!disabled"])
            self.connect_btn.configure(text="Connecting..." if self.connecting else "Connect")
            self.connect_btn.state(["disabled"] if locked else ["!disabled"])
        elif self.screen == ui_model.SETUP:
            for w in self.setup_buttons:
                w.state(["disabled"] if self.busy or self.closing else ["!disabled"])
        elif self.screen == ui_model.CONNECTED:
            self.disconnect_btn.state(["disabled"] if self.busy or self.closing else ["!disabled"])
        elif self.screen == "problem":
            self.retry_btn.state(["disabled"] if self.busy or self.closing else ["!disabled"])

    def _update_banner(self):
        name = self.cfg.connection_name
        if self.closing:
            kind, title, sub = "busy", "Disconnecting...", "The window will close in a moment."
        elif self.load_failed:
            kind, title, sub = "problem", "Can't check the VPN", "See the message below."
        elif not self.loaded:
            kind, title, sub = "idle", "Checking...", name
        elif self.connecting or self.status.state == "connecting":
            kind, title, sub = "busy", "Connecting...", "This can take up to a minute."
        elif self.status.connected:
            kind, title, sub = "ok", "Connected", f"You are on {name}."
        elif self.error is not None:
            kind, title, sub = "problem", "Not connected", "See the message below."
        elif not self.status.exists:
            kind, title, sub = "idle", "Not set up yet", "Add your VPN file to get started."
        else:
            kind, title, sub = "idle", "Not connected", name
        colour = STATUS_COLOURS[kind]
        for w in (self.banner, self.banner_title, self.banner_sub):
            w.configure(background=colour)
        self.banner_title.configure(text=title)
        self.banner_sub.configure(text=sub)

    def _render(self, force: bool = False):
        screen = self._current_screen()
        if screen == self.screen and not force:
            return
        typed_user = self.username.get() if self.screen == ui_model.SIGN_IN else ""
        self.screen = screen
        for child in self.body.winfo_children():
            child.destroy()
        if screen == ui_model.SETUP:
            self._build_setup()
        elif screen == ui_model.SIGN_IN:
            self._build_sign_in(typed_user)
        elif screen == ui_model.CONNECTED:
            self._build_connected()
        elif screen == "problem":
            self._build_problem()
        else:
            ttk.Label(self.body, text="One moment...", style="Muted.TLabel").pack(anchor="w")

    def _message_box(self, parent):
        """Error (red) or notice (blue) box shown above the form, if any."""
        if self.error is not None:
            bg, head, text = ERROR_BG, self.error.headline, self.error.next_step
        elif self.notice:
            bg, head, text = NOTICE_BG, "", self.notice
        else:
            return
        box = tk.Frame(parent, background=bg, padx=12, pady=10)
        box.pack(fill="x", pady=(0, 14))
        if head:
            tk.Label(box, text=head, background=bg, fg=TEXT, font=self.fonts["big"],
                     anchor="w", justify="left", wraplength=360).pack(fill="x")
        tk.Label(box, text=text, background=bg, fg=TEXT, font=self.fonts["body"],
                 anchor="w", justify="left", wraplength=360).pack(fill="x")

    def _build_setup(self):
        """FR-GUI-02."""
        b = self.body
        ttk.Label(b, text="Set up the VPN", style="Heading.TLabel").pack(anchor="w")
        ttk.Label(b, text="You only do this once. You need your personal VPN file\n"
                          "(it ends in .ovpn).", style="Muted.TLabel",
                  justify="left").pack(anchor="w", pady=(4, 16))
        self._message_box(b)
        self.setup_buttons = []

        found = self.offered = ui_model.newest_profile()
        if found is not None:
            btn = ttk.Button(b, text=f"Use {found.name}", style="Primary.TButton",
                             command=lambda: self._import(str(found)))
            btn.pack(fill="x")
            ttk.Label(b, text="Found in your Downloads folder.", style="Muted.TLabel").pack(
                anchor="w", pady=(4, 12))
            other = ttk.Button(b, text="Choose a different file...", command=self.on_choose_file)
            other.pack(fill="x")
            self.setup_buttons += [btn, other]
            btn.focus_set()
        else:
            btn = ttk.Button(b, text="Choose VPN file...", style="Primary.TButton",
                             command=self.on_choose_file)
            btn.pack(fill="x")
            self.setup_buttons.append(btn)
            btn.focus_set()

        if self.cfg.portal_url:
            ttk.Label(b, text="Don't have the file yet?", style="Muted.TLabel").pack(
                anchor="w", pady=(18, 4))
            portal = ttk.Button(b, text="Download it from the VPN portal", command=self.open_portal)
            portal.pack(fill="x")
            self.setup_buttons.append(portal)
        else:
            ttk.Label(b, text="Don't have the file yet? Ask IT for it.", style="Muted.TLabel").pack(
                anchor="w", pady=(18, 0))

    def _on_focus(self, event):
        """Rescan Downloads when the window comes back (the user just downloaded the file)."""
        if event.widget is self.root and self.screen == ui_model.SETUP and not self.busy:
            if ui_model.newest_profile() != self.offered:
                self._render(force=True)
                self._sync()

    def _build_problem(self):
        """Status could not be read at all: say so, offer Try again."""
        b = self.body
        self._message_box(b)
        self.retry_btn = ttk.Button(b, text="Try again", style="Primary.TButton", command=self.on_retry)
        self.retry_btn.pack(fill="x")
        self.retry_btn.focus_set()

    def on_retry(self):
        self._append("Trying again...")
        self._background(self._first_run)

    def _build_sign_in(self, typed_user: str):
        """FR-GUI-03."""
        b = self.body
        b.columnconfigure(0, weight=1)
        ttk.Label(b, text="Sign in to connect", style="Heading.TLabel").pack(anchor="w", pady=(0, 12))
        self._message_box(b)

        ttk.Label(b, text="Username").pack(anchor="w")
        self.username = ttk.Entry(b)
        self.username.pack(fill="x", pady=(2, 10))
        self.username.insert(0, typed_user or self.status.username)

        ttk.Label(b, text="Password").pack(anchor="w")
        row = ttk.Frame(b)
        row.pack(fill="x", pady=(2, 0))
        # exportselection=False: a selected (shown) password never reaches the X clipboard.
        self.password = ttk.Entry(row, show="•", exportselection=False)
        self.password.pack(side="left", fill="x", expand=True)
        self.show_pw = tk.BooleanVar(value=False)
        show = ttk.Checkbutton(row, text="Show", variable=self.show_pw,
                               command=lambda: self.password.configure(show="" if self.show_pw.get() else "•"))
        show.pack(side="left", padx=(8, 0))
        self.caps_var = tk.StringVar(value="")
        tk.Label(b, textvariable=self.caps_var, fg=STATUS_COLOURS["busy"], background=BG,
                 font=self.fonts["small"], anchor="w").pack(fill="x")
        self.sign_in_inputs = [self.username, self.password, show]

        self.otp = None
        if self.cfg.otp:
            ttk.Label(b, text="Code from your authenticator app").pack(anchor="w", pady=(6, 0))
            self.otp = ttk.Entry(b, width=12, exportselection=False)
            self.otp.pack(anchor="w", pady=(2, 0))
            self.sign_in_inputs.append(self.otp)

        self.connect_btn = ttk.Button(b, text="Connect", style="Primary.TButton", command=self.on_connect)
        self.connect_btn.pack(fill="x", pady=(16, 0))

        for w in self.sign_in_inputs[:2] + ([self.otp] if self.otp else []):
            w.bind("<Return>", lambda _e: self.on_connect())
            w.bind("<KeyPress>", self._caps_check, add="+")
            w.bind("<KeyRelease>", self._caps_check, add="+")
        (self.password if self.username.get() else self.username).focus_set()

    def _build_connected(self):
        """FR-GUI-04."""
        b = self.body
        user = self.status.username
        ttk.Label(b, text="You're connected", style="Heading.TLabel").pack(anchor="w")
        if self.error is not None:
            self._message_box(b)
        ttk.Label(b, text=f"Signed in as {user}." if user else "Company sites and shares now work.",
                  style="Muted.TLabel").pack(anchor="w", pady=(4, 0))
        self.timer_var = tk.StringVar(value="")
        ttk.Label(b, textvariable=self.timer_var).pack(anchor="w", pady=(14, 0))
        self.disconnect_btn = ttk.Button(b, text="Disconnect", style="Primary.TButton",
                                         command=self.on_disconnect)
        self.disconnect_btn.pack(fill="x", pady=(20, 0))
        self.disconnect_btn.focus_set()
        if self.from_tray:
            ttk.Label(b, text="You can close this window. The VPN stays on until you disconnect\n"
                              "from the VPN icon in the top bar.", style="Muted.TLabel",
                      justify="left").pack(anchor="w", pady=(10, 0))
        elif self.cfg.disconnect_on_exit:  # OQ-GUI-01 assumption: closing still disconnects
            ttk.Label(b, text="Closing this window disconnects the VPN.", style="Muted.TLabel").pack(
                anchor="w", pady=(10, 0))
        self.notice = ""

    def _update_menu(self):
        """FR-GUI-07."""
        m = self.more_menu
        m.delete(0, "end")
        idle = "normal" if not self.busy else "disabled"
        if self.status.exists:
            m.add_command(label="Change VPN file...", command=self.on_choose_file, state=idle)
            m.add_command(label="Remove VPN file from this computer...", command=self.on_remove, state=idle)
        if self.cfg.portal_url:
            m.add_command(label="Open VPN portal", command=self.open_portal)
        if m.index("end") is not None:
            m.add_separator()
        m.add_command(label="About VPNConnect", command=self.on_about)

    # ---- details panel --------------------------------------------------------------
    def _append(self, msg: str):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", time.strftime("%H:%M:%S  ") + msg + "\n")
        lines = int(self.log_box.index("end-1c").split(".")[0])
        if lines > 200:
            self.log_box.delete("1.0", f"{lines - 200}.0")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _toggle_details(self):
        self.details_open = not self.details_open
        if self.details_open:
            self.details.pack(side="bottom", fill="both", before=self.body)
            self.details_btn.configure(text="Hide details")
        else:
            self.details.pack_forget()
            self.details_btn.configure(text="Show details")

    def _close_details(self):
        if self.details_open:
            self._toggle_details()

    def _copy_details(self):
        header = (f"VPNConnect {__version__} | {self.cfg.connection_name} | "
                  f"state: {self.status.state}\n")
        self.root.clipboard_clear()
        self.root.clipboard_append(header + self.log_box.get("1.0", "end"))
        self._append("Details copied. Paste them into your message to IT.")

    def _caps_check(self, event):
        self.caps_var.set("Caps Lock is on." if event.state & LOCK_MASK else "")

    # ---- actions --------------------------------------------------------------------
    def _first_run(self):
        st = nm.status(self.cfg.connection_name)
        if not st.exists and settings.SYSTEM_PROFILE.is_file():
            self.log("Adding the company VPN file...")
            nm.import_profile(settings.SYSTEM_PROFILE, self.cfg.connection_name)

    def on_choose_file(self):
        path = filedialog.askopenfilename(
            parent=self.root, title="Choose your VPN file",
            initialdir=str(ui_model.downloads_dir()),
            filetypes=[("VPN file (.ovpn)", "*.ovpn"), ("All files", "*")],
        )
        if path:
            self._import(path)

    def _import(self, path: str):
        self.error = None
        username = self.status.username

        def job():
            if self.status.connected:
                nm.disconnect(self.cfg.connection_name)
            nm.import_profile(path, self.cfg.connection_name, username)
            self.log(f"Added VPN file {path}.")
            self.events.put(("notice", "VPN file added. Enter your username and password to connect."))

        self._background(job)

    def on_connect(self):
        if self.busy or self.closing or not self.status.exists or self.status.connected:
            return
        username = self.username.get().strip()
        password = self.password.get()
        code = self.otp.get().strip() if self.otp is not None else ""
        if self.otp is not None:
            self.otp.delete(0, "end")
        self.password.delete(0, "end")  # BR-GUI-01: never kept after an attempt
        missing = [name for name, ok in (("username", username), ("password", password),
                                         ("otp", code or self.otp is None)) if not ok]
        if missing:
            self.error = ui_model.Friendly(
                "Fill in your username, password" + (" and code." if self.otp is not None else "."),
                "Then press Connect.")
            self._render(force=True)  # rebuilds the form, so look the field up afterwards
            getattr(self, missing[0]).focus_set()
            return
        password += code
        self.error, self.notice = None, ""
        self.connecting = True
        previous_user = self.status.username

        def job():
            self.log(f"Connecting as {username}...")
            nm.connect(self.cfg.connection_name, password,
                       username if username != previous_user else "")
            self.log("Connected.")

        self._background(job)
        self._render(force=True)
        self._sync()

    def on_disconnect(self):
        def job():
            nm.disconnect(self.cfg.connection_name)
            self.log("Disconnected.")

        self._background(job)

    def on_remove(self):
        if not messagebox.askyesno(
            "Remove VPN file",
            "Remove your VPN file from this computer?\n\n"
            "You will need your .ovpn file again to reconnect.",
            parent=self.root,
        ):
            return

        def job():
            if self.status.connected:
                nm.disconnect(self.cfg.connection_name)
            nm.delete(self.cfg.connection_name)
            self.log("VPN file removed.")

        self.error, self.notice = None, ""
        self._background(job)

    def open_portal(self):
        webbrowser.open(self.cfg.portal_url)

    def on_about(self):
        messagebox.showinfo(
            "About VPNConnect",
            f"VPNConnect {__version__}\n\nConnects you to {self.cfg.connection_name}.\n"
            "Your password is never saved.\n\nNeed help? Contact IT and use\n"
            "'Show details' > 'Copy for IT'.",
            parent=self.root,
        )

    def on_close(self):
        """FR-GUI-09: disconnect off the main thread, then close (15 s cap)."""
        if self.closing:
            return
        # Also disconnect a connection that is still coming up, or it would be
        # left running after the app is gone.
        active = self.status.connected or self.connecting or self.status.state == "connecting"
        if self.from_tray or not (active and self.cfg.disconnect_on_exit):
            self._destroy()
            return
        self.closing = True
        self.busy = True
        self._sync()

        def job():
            try:
                nm.disconnect(self.cfg.connection_name)
            except nm.VPNError:
                pass
            self.events.put(("closed", None))

        threading.Thread(target=job, daemon=True).start()
        self.root.after(CLOSE_CAP_MS, self._destroy)

    def _destroy(self):
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def bring_to_front(self):
        """The top-bar icon asked for the window again (FR-TRAY-04)."""
        self.root.deiconify()
        self.root.lift()
        self.root.attributes("-topmost", True)
        self.root.after(300, lambda: self.root.attributes("-topmost", False))
        self.root.focus_force()


def show_problems(problems: list[str]) -> None:
    """FR-GUI-08: the app was opened from the menu but this computer is missing pieces."""
    root = tk.Tk()
    fonts = _setup_style(root)
    root.title("VPNConnect")
    root.minsize(420, 0)
    banner = tk.Frame(root, background=STATUS_COLOURS["problem"], padx=18, pady=14)
    banner.pack(fill="x")
    tk.Label(banner, text="VPNConnect can't start", font=fonts["title"], fg="#ffffff",
             background=STATUS_COLOURS["problem"], anchor="w").pack(fill="x")
    body = ttk.Frame(root, padding=(24, 18))
    body.pack(fill="both", expand=True)
    ttk.Label(body, text="This computer is missing something the VPN needs:",
              wraplength=380, justify="left").pack(anchor="w")
    for p in problems:
        ttk.Label(body, text="- " + p, style="Muted.TLabel", wraplength=380,
                  justify="left").pack(anchor="w", pady=(6, 0))
    ttk.Label(body, text="Ask IT to run install.sh on this computer.", style="Heading.TLabel",
              wraplength=380, justify="left").pack(anchor="w", pady=(16, 0))
    btn = ttk.Button(body, text="Close", style="Primary.TButton", command=root.destroy)
    btn.pack(anchor="e", pady=(18, 0))
    btn.focus_set()
    root.bind("<Return>", lambda _e: root.destroy())
    root.bind("<Escape>", lambda _e: root.destroy())
    root.mainloop()


def run(cfg: settings.Settings, from_tray: bool = False) -> int:
    root = tk.Tk(className="vpnconnect")
    app = App(root, cfg, from_tray=from_tray)
    # SIGUSR1 from the tray = "show yourself". The handler only queues; _poll acts on it.
    signal.signal(signal.SIGUSR1, lambda *_a: app.events.put(("raise", None)))
    root.mainloop()
    return 0
