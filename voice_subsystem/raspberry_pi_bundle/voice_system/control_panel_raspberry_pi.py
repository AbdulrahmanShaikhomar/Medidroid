import os
import queue
import shutil
import subprocess
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from tkinter.scrolledtext import ScrolledText

import speech_recognition as sr


BASE_DIR = Path(__file__).resolve().parent
AGENT_PATH = BASE_DIR / "agent_raspberry_pi.py"


class RaspberryPiControlPanel:
    def __init__(self, root):
        self.root = root
        self.root.title("MediDroid Raspberry Pi Control Panel")
        self.root.geometry("920x650")

        self.process = None
        self.log_queue = queue.Queue()
        self.reader_thread = None
        self.mic_options = []

        self.selected_mic = tk.StringVar()
        self.selected_model = tk.StringVar(value="tiny.en")
        self.status_text = tk.StringVar(value="Idle")
        self.mute_audio = tk.BooleanVar(value=False)

        self.build_ui()
        self.refresh_microphones()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.after(100, self.flush_log_queue)

    def build_ui(self):
        outer = ttk.Frame(self.root, padding=12)
        outer.pack(fill="both", expand=True)

        controls = ttk.LabelFrame(outer, text="Voice Input", padding=12)
        controls.pack(fill="x")

        ttk.Label(controls, text="Microphone").grid(row=0, column=0, sticky="w")
        self.mic_combo = ttk.Combobox(controls, textvariable=self.selected_mic, state="readonly", width=58)
        self.mic_combo.grid(row=0, column=1, padx=10, sticky="ew")

        ttk.Label(controls, text="Whisper Model").grid(row=1, column=0, sticky="w", pady=(10, 0))
        model_combo = ttk.Combobox(
            controls,
            textvariable=self.selected_model,
            state="readonly",
            values=["tiny.en", "base.en", "small.en"],
            width=20,
        )
        model_combo.grid(row=1, column=1, padx=10, sticky="w", pady=(10, 0))

        ttk.Checkbutton(controls, text="Mute audio playback", variable=self.mute_audio).grid(
            row=1, column=2, columnspan=2, sticky="w", pady=(10, 0)
        )

        ttk.Button(controls, text="Refresh", command=self.refresh_microphones).grid(row=0, column=2, padx=(0, 8))
        self.start_btn = ttk.Button(controls, text="Start Pi Live Demo", command=self.start_agent)
        self.start_btn.grid(row=0, column=3, padx=(0, 8))
        self.stop_btn = ttk.Button(controls, text="Stop", command=self.stop_agent, state="disabled")
        self.stop_btn.grid(row=0, column=4)

        controls.columnconfigure(1, weight=1)

        info = ttk.Frame(outer, padding=(0, 10, 0, 10))
        info.pack(fill="x")
        ttk.Label(info, text="Status:").pack(side="left")
        ttk.Label(info, textvariable=self.status_text).pack(side="left", padx=(6, 0))

        help_text = (
            "Choose the Raspberry Pi microphone, select a Whisper model, then click Start. "
            "Say 'Hey MediDroid' once to arm the live interaction. The output below mirrors the terminal log."
        )
        ttk.Label(outer, text=help_text, wraplength=880, justify="left").pack(fill="x", pady=(0, 10))

        log_frame = ttk.LabelFrame(outer, text="Live Output", padding=8)
        log_frame.pack(fill="both", expand=True)

        self.log_view = ScrolledText(log_frame, wrap="word", font=("DejaVu Sans Mono", 10))
        self.log_view.pack(fill="both", expand=True)
        self.log_view.configure(state="disabled")

    def refresh_microphones(self):
        names = sr.Microphone.list_microphone_names()
        self.mic_options = [(idx, name) for idx, name in enumerate(names)]
        labels = [f"{idx}: {name}" for idx, name in self.mic_options]
        self.mic_combo["values"] = labels

        if labels:
            previous = self.selected_mic.get()
            if previous in labels:
                self.selected_mic.set(previous)
            else:
                preferred = next((label for label in labels if "microphone" in label.lower()), labels[0])
                self.selected_mic.set(preferred)
        else:
            self.selected_mic.set("")

    def append_log(self, text):
        self.log_view.configure(state="normal")
        self.log_view.insert("end", text)
        self.log_view.see("end")
        self.log_view.configure(state="disabled")

    def flush_log_queue(self):
        try:
            while True:
                item = self.log_queue.get_nowait()
                self.append_log(item)
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self.flush_log_queue)

    def selected_mic_index(self):
        value = self.selected_mic.get().strip()
        if not value:
            return None
        return int(value.split(":", 1)[0])

    def python_command(self):
        if shutil.which("python3"):
            return "python3"
        if shutil.which("python"):
            return "python"
        return None

    def start_agent(self):
        if self.process and self.process.poll() is None:
            messagebox.showinfo("MediDroid", "The Raspberry Pi live demo is already running.")
            return

        mic_index = self.selected_mic_index()
        if mic_index is None:
            messagebox.showerror("MediDroid", "Please choose a microphone first.")
            return

        python_cmd = self.python_command()
        if not python_cmd:
            messagebox.showerror("MediDroid", "Could not find python3 or python on this Raspberry Pi.")
            return

        command = [python_cmd, "-u", str(AGENT_PATH), "--mic-index", str(mic_index), "--stt-model", self.selected_model.get()]
        if self.mute_audio.get():
            command.append("--mute")

        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"

        try:
            self.process = subprocess.Popen(
                command,
                cwd=str(BASE_DIR),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                text=True,
                bufsize=1,
                env=env,
            )
        except Exception as exc:
            messagebox.showerror("MediDroid", f"Failed to start the Raspberry Pi live demo.\n\n{exc}")
            return

        self.status_text.set(f"Running on microphone index {mic_index}")
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.append_log(f"\n=== Starting Raspberry Pi live demo on microphone index {mic_index} ===\n")
        self.append_log(f"Command: {' '.join(command)}\n")

        self.reader_thread = threading.Thread(target=self.read_process_output, daemon=True)
        self.reader_thread.start()

        watcher = threading.Thread(target=self.wait_for_process_exit, daemon=True)
        watcher.start()

    def read_process_output(self):
        if not self.process or not self.process.stdout:
            return

        for line in self.process.stdout:
            self.log_queue.put(line)

    def wait_for_process_exit(self):
        if not self.process:
            return

        return_code = self.process.wait()
        self.log_queue.put(f"\n=== Raspberry Pi live demo stopped (exit code {return_code}) ===\n")
        self.root.after(0, self.on_process_stopped)

    def on_process_stopped(self):
        self.status_text.set("Idle")
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.process = None

    def stop_agent(self):
        if not self.process or self.process.poll() is not None:
            self.on_process_stopped()
            return

        self.append_log("\n=== Stopping Raspberry Pi live demo... ===\n")
        self.process.terminate()

    def on_close(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
        self.root.destroy()


def main():
    root = tk.Tk()
    style = ttk.Style()
    for preferred in ("clam", "default"):
        if preferred in style.theme_names():
            style.theme_use(preferred)
            break
    RaspberryPiControlPanel(root)
    root.mainloop()


if __name__ == "__main__":
    main()
