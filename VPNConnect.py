import os
import shutil
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import threading
import time
import subprocess
import signal

BASE_DIR = os.path.dirname(__file__)
VPN_DIR = os.path.join(BASE_DIR, "vpn")
CONFIG_FILE = os.path.join(VPN_DIR, "sophos.ovpn")
CRED_FILE = os.path.join(VPN_DIR, "credentials.txt")

# Global variable to track VPN process
vpn_process = None
timer_thread = None
timeout_flag = False

def ensure_vpn_dir():
    os.makedirs(VPN_DIR, exist_ok=True)

def select_ovpn():
    filepath = filedialog.askopenfilename(filetypes=[("OpenVPN config", "*.ovpn")])
    if filepath:
        ensure_vpn_dir()
        shutil.copy(filepath, CONFIG_FILE)
        inject_auth_line(CONFIG_FILE)
        log(f"✅ Config file copied to: {CONFIG_FILE}")

def inject_auth_line(path):
    with open(path, "r") as f:
        lines = f.readlines()

    # Remove any existing auth-user-pass lines
    lines = [line for line in lines if not line.strip().startswith("auth-user-pass")]
    lines.append("auth-user-pass credentials.txt\n")

    with open(path, "w") as f:
        f.writelines(lines)

def save_credentials(username, password):
    with open(CRED_FILE, "w") as f:
        f.write(f"{username}\n{password}\n")
    os.chmod(CRED_FILE, 0o600)  # Secure permissions

def run_openvpn():
    global vpn_process, timer_thread, timeout_flag
    
    if not os.path.exists(CONFIG_FILE):
        messagebox.showerror("Missing Config", "Please select a .ovpn file first.")
        return

    username = username_entry.get().strip()
    password = password_entry.get().strip()

    if not username or not password:
        messagebox.showerror("Missing Credentials", "Please enter username and password.")
        return

    save_credentials(username, password)
    inject_auth_line(CONFIG_FILE)

    cmd = f"pkexec openvpn --cd {VPN_DIR} --config {CONFIG_FILE}"
    log("🔐 Starting VPN...")
    
    # Start the VPN in a separate thread
    vpn_thread = threading.Thread(target=start_vpn, args=(cmd,), daemon=True)
    vpn_thread.start()
    
    # Start the 30-minute timer
    timeout_flag = False
    timer_thread = threading.Thread(target=timeout_handler, daemon=True)
    timer_thread.start()

def start_vpn(cmd):
    """Run the VPN process in a background thread"""
    global vpn_process
    try:
        # Start OpenVPN process
        vpn_process = subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            preexec_fn=os.setsid  # Create new process group
        )
        log(f"🔄 VPN running with PID: {vpn_process.pid}")
        
        # Stream output to log
        for line in iter(vpn_process.stdout.readline, ''):
            log(line.strip())
            
        vpn_process.stdout.close()
        return_code = vpn_process.wait()
        log(f"ℹ️ VPN process exited with code: {return_code}")
        
    except Exception as e:
        log(f"❌ Failed to start VPN: {str(e)}")
    finally:
        vpn_process = None

def timeout_handler():
    """Terminate everything after 30 minutes"""
    global timeout_flag
    log("⏳ 30-minute timer started. Application will auto-close after 30 minutes.")
    
    # Wait for 30 minutes (1800 seconds)
    time.sleep(3600)
    
    if not timeout_flag:
        timeout_flag = True
        log("⏰ 30 minutes have passed. Terminating VPN and closing application...")
        kill_openvpn_process()
        root.after(100, root.destroy)  # Schedule GUI destruction on main thread

def kill_openvpn_process():
    global vpn_process
    if vpn_process:
        try:
            # Terminate the process group including any child processes
            os.killpg(os.getpgid(vpn_process.pid), signal.SIGTERM)
            log(f"⛔ Terminated VPN process (PID: {vpn_process.pid})")
        except ProcessLookupError:
            log("ℹ️ VPN process already terminated")
        except Exception as e:
            log(f"⚠️ Error terminating VPN: {str(e)}")
        finally:
            vpn_process = None
    else:
        log("ℹ️ No active VPN process to terminate")

def on_close():
    global timeout_flag
    timeout_flag = True  # Prevent timeout from triggering after manual close
    log("Closing application...")
    kill_openvpn_process()
    root.destroy()

def log(message):
    log_box.insert(tk.END, message + "\n")
    log_box.yview(tk.END)
    log_box.update()  # Force GUI update

# GUI Setup
root = tk.Tk()
root.title("Sophos VPN Client")
root.geometry("600x500")

# Handle window close button
root.protocol("WM_DELETE_WINDOW", on_close)

frame = tk.Frame(root)
frame.pack(pady=10)

tk.Button(frame, text="📁 Select .ovpn File", command=select_ovpn).grid(row=0, column=0, columnspan=2, pady=10)

tk.Label(frame, text="Username:").grid(row=1, column=0, sticky="e")
username_entry = tk.Entry(frame, width=35)
username_entry.grid(row=1, column=1)

tk.Label(frame, text="Password:").grid(row=2, column=0, sticky="e")
password_entry = tk.Entry(frame, width=35, show="*")
password_entry.grid(row=2, column=1)

tk.Button(frame, text="▶️ Start VPN", bg="green", fg="white", command=run_openvpn).grid(row=3, column=0, columnspan=2, pady=15)

log_box = scrolledtext.ScrolledText(root, width=70, height=18)
log_box.pack(pady=5)

# Add some initial instructions
log("Instructions:")
log("1. Click 'Select .ovpn File' to choose your VPN configuration")
log("2. Enter your username and password")
log("3. Click 'Start VPN' to connect")
log("4. Application will automatically close after 30 minutes")

root.mainloop()