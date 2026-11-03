# Concurrency Checker - server launcher (simple UI)
# Rakhar jayga: C:\dev\concurrency-checker\launcher.pyw   ("backend" folder-er pashe)
# Chalate: double-click "Start Server.bat" (ba ei file-ta).
import os
import queue
import socket
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path

# ---- Ekhane bodlano jay -------------------------------------------------
HOST = "127.0.0.1"
PORT = 8000
MODE = "hybrid"          # llm | model | hybrid | mock
# -------------------------------------------------------------------------

BASE = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
BACKEND = BASE / "backend"
PY = BACKEND / ".venv" / "Scripts" / "python.exe"
ARGS = [str(PY), "-u", "-m", "uvicorn", "app.main:app", "--host", HOST, "--port", str(PORT)]

COMMAND_TEXT = (
    f'cd "{BACKEND}"\n'
    f'$env:DETECTOR_MODE="{MODE}"\n'
    f'& "{PY}" -m uvicorn app.main:app --host {HOST} --port {PORT}'
)

CREATE_NO_WINDOW = 0x08000000


def port_in_use() -> bool:
    try:
        with socket.create_connection((HOST, PORT), timeout=0.5):
            return True
    except OSError:
        return False


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.proc = None
        self.q = queue.Queue()
        root.title("Concurrency Checker Server")
        root.geometry("760x470")
        root.minsize(620, 380)

        tk.Label(root, text="Command", font=("Segoe UI", 10, "bold"), anchor="w").pack(fill="x", padx=12, pady=(10, 2))
        self.cmd = tk.Text(root, height=4, wrap="none", font=("Consolas", 10), bg="#f3f3f3", relief="solid", bd=1)
        self.cmd.insert("1.0", COMMAND_TEXT)
        self.cmd.config(state="disabled")
        self.cmd.pack(fill="x", padx=12)

        bar = tk.Frame(root)
        bar.pack(fill="x", padx=12, pady=10)
        self.run_btn = tk.Button(bar, text="Run", width=12, bg="#2e7d32", fg="white",
                                 font=("Segoe UI", 10, "bold"), command=self.run)
        self.run_btn.pack(side="left")
        self.stop_btn = tk.Button(bar, text="Stop", width=12, bg="#c62828", fg="white",
                                  font=("Segoe UI", 10, "bold"), command=self.stop, state="disabled")
        self.stop_btn.pack(side="left", padx=(8, 0))
        self.status = tk.Label(bar, text="Stopped", font=("Segoe UI", 10), fg="#555555")
        self.status.pack(side="left", padx=14)

        tk.Label(root, text="Log", font=("Segoe UI", 10, "bold"), anchor="w").pack(fill="x", padx=12)
        frame = tk.Frame(root)
        frame.pack(fill="both", expand=True, padx=12, pady=(2, 12))
        sb = tk.Scrollbar(frame)
        sb.pack(side="right", fill="y")
        self.log_box = tk.Text(frame, wrap="word", font=("Consolas", 9), bg="#111111", fg="#dddddd",
                               yscrollcommand=sb.set, state="disabled")
        self.log_box.pack(side="left", fill="both", expand=True)
        sb.config(command=self.log_box.yview)

        root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.poll()

    # ---------------------------------------------------------------- helpers
    def log(self, text: str):
        self.log_box.config(state="normal")
        self.log_box.insert("end", text)
        self.log_box.see("end")
        self.log_box.config(state="disabled")

    def set_status(self, text: str, color: str):
        self.status.config(text=text, fg=color)

    def alive(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    # ---------------------------------------------------------------- actions
    def run(self):
        if self.alive():
            return
        if not PY.exists():
            self.log(f"[launcher] Python pawa jayni: {PY}\n"
                     f"[launcher] launcher.pyw 'backend' folder-er pashe ache kina dekhun.\n")
            return
        if port_in_use():
            self.log(f"[launcher] Port {PORT} already use hocche (purano server cholte pare). "
                     f"Age oita bondho korun.\n")
            return
        env = os.environ.copy()
        env["DETECTOR_MODE"] = MODE
        env["PYTHONUNBUFFERED"] = "1"
        try:
            self.proc = subprocess.Popen(
                ARGS, cwd=str(BACKEND), env=env,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace",
                creationflags=CREATE_NO_WINDOW,
            )
        except Exception as e:  # noqa: BLE001
            self.log(f"[launcher] Start korte parlam na: {e}\n")
            return
        threading.Thread(target=self.reader, args=(self.proc,), daemon=True).start()
        self.log(f"[launcher] Starting (mode={MODE}) ...\n")
        self.run_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.set_status("Starting...", "#b26a00")

    def stop(self):
        p = self.proc
        if p is not None and p.poll() is None:
            # process + tar child-gulo shob bondho (Ctrl+C-er moto kaj)
            subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"],
                           capture_output=True, creationflags=CREATE_NO_WINDOW)
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass

    def reader(self, proc):
        for line in proc.stdout:
            self.q.put(line)

    def poll(self):
        try:
            while True:
                line = self.q.get_nowait()
                self.log(line)
                if "Uvicorn running on" in line:
                    self.set_status(f"Running  -  http://{HOST}:{PORT}", "#2e7d32")
        except queue.Empty:
            pass
        if self.proc is not None and self.proc.poll() is not None:
            code = self.proc.returncode
            self.log(f"[launcher] Server stopped (exit code {code}).\n")
            self.proc = None
            self.run_btn.config(state="normal")
            self.stop_btn.config(state="disabled")
            self.set_status("Stopped", "#555555")
        self.root.after(150, self.poll)

    def on_close(self):
        self.stop()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
