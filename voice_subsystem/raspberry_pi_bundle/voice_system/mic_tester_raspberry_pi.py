import audioop
import re
import subprocess
import queue
import tempfile
import threading
import time
import wave
from pathlib import Path
import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

import speech_recognition as sr
from faster_whisper import WhisperModel


BASE_DIR = Path(__file__).resolve().parent
TARGET_SAMPLE_RATE = 16000
CAPTURE_SAMPLE_RATE = 44100
CHANNELS = 1
SAMPLE_WIDTH = 2
RECORD_SECONDS = 4
PRE_ROLL_SECONDS = 0.5
WAKE_WORD_PATTERNS = ["hey medidroid", "medidroid", "medi droid", "midi droid"]
SILENCE_TRANSCRIPT = "(skipped transcription: mostly silence)"


def compute_audio_levels(frames, sample_width=SAMPLE_WIDTH):
    if not frames:
        return 0.0, 0.0

    rms = audioop.rms(frames, sample_width)
    peak_min, peak_max = audioop.minmax(frames, sample_width)
    peak = max(abs(peak_min), abs(peak_max))
    max_pcm = float((2 ** (8 * sample_width - 1)) - 1)

    rms_pct = (rms / max_pcm) * 100.0
    peak_pct = (peak / max_pcm) * 100.0
    return round(rms_pct, 2), round(peak_pct, 2)


def classify_signal(rms_pct, peak_pct):
    if rms_pct < 1.0 and peak_pct < 3.0:
        return "Mostly silence"
    if rms_pct < 5.0 and peak_pct < 12.0:
        return "Weak signal detected"
    return "Clear signal detected"


def normalize_text(text):
    return re.sub(r"[^a-z0-9 ]+", "", text.lower()).strip()


def looks_like_wake_word(text):
    normalized = normalize_text(text)
    if not normalized:
        return False

    compact = normalized.replace(" ", "")
    if any(pattern.replace(" ", "") in compact for pattern in WAKE_WORD_PATTERNS):
        return True

    fuzzy_candidates = [
        "medidroid",
        "medidroyd",
        "medidyroid",
        "mididroid",
        "medidrawit",
        "imgonnadrawit",
    ]
    return any(candidate in compact for candidate in fuzzy_candidates)


def resolve_capture_device(mic_index):
    names = sr.Microphone.list_microphone_names()
    if mic_index is None or mic_index < 0 or mic_index >= len(names):
        return "default"

    name = names[mic_index]
    if "(hw:" in name:
        hw = name.split("(hw:", 1)[1].split(")", 1)[0]
        return f"plughw:{hw}"

    return "default"


class MicTesterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("MediDroid Pi Mic Tester")
        self.root.geometry("820x620")

        self.log_queue = queue.Queue()
        self.recording = False
        self.whisper_model = None

        self.selected_mic = tk.StringVar()
        self.status_text = tk.StringVar(value="Idle")
        self.level_text = tk.StringVar(value="RMS: 0.00% | Peak: 0.00%")
        self.signal_text = tk.StringVar(value="Not tested yet")
        self.transcript_text = tk.StringVar(value="")

        self.build_ui()
        self.refresh_microphones()
        self.root.after(100, self.flush_log_queue)

    def build_ui(self):
        outer = ttk.Frame(self.root, padding=12)
        outer.pack(fill="both", expand=True)

        controls = ttk.LabelFrame(outer, text="Microphone Test", padding=12)
        controls.pack(fill="x")

        ttk.Label(controls, text="Microphone").grid(row=0, column=0, sticky="w")
        self.mic_combo = ttk.Combobox(controls, textvariable=self.selected_mic, state="readonly", width=55)
        self.mic_combo.grid(row=0, column=1, padx=10, sticky="ew")

        ttk.Button(controls, text="Refresh Mics", command=self.refresh_microphones).grid(row=0, column=2, padx=(0, 8))
        self.test_btn = ttk.Button(controls, text=f"Record {RECORD_SECONDS}s Test", command=self.start_test)
        self.test_btn.grid(row=0, column=3)

        controls.columnconfigure(1, weight=1)

        summary = ttk.LabelFrame(outer, text="Results", padding=12)
        summary.pack(fill="x", pady=(10, 10))

        ttk.Label(summary, text="Status:").grid(row=0, column=0, sticky="w")
        ttk.Label(summary, textvariable=self.status_text).grid(row=0, column=1, sticky="w")

        ttk.Label(summary, text="Levels:").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Label(summary, textvariable=self.level_text).grid(row=1, column=1, sticky="w", pady=(8, 0))

        ttk.Label(summary, text="Signal:").grid(row=2, column=0, sticky="w", pady=(8, 0))
        ttk.Label(summary, textvariable=self.signal_text).grid(row=2, column=1, sticky="w", pady=(8, 0))

        ttk.Label(summary, text="Transcript:").grid(row=3, column=0, sticky="nw", pady=(8, 0))
        ttk.Label(summary, textvariable=self.transcript_text, wraplength=560, justify="left").grid(
            row=3, column=1, sticky="w", pady=(8, 0)
        )

        log_frame = ttk.LabelFrame(outer, text="Log", padding=8)
        log_frame.pack(fill="both", expand=True)

        self.log_view = ScrolledText(log_frame, wrap="word", font=("DejaVu Sans Mono", 10))
        self.log_view.pack(fill="both", expand=True)
        self.log_view.configure(state="disabled")

    def append_log(self, text):
        self.log_view.configure(state="normal")
        self.log_view.insert("end", text)
        self.log_view.see("end")
        self.log_view.configure(state="disabled")

    def flush_log_queue(self):
        try:
            while True:
                self.append_log(self.log_queue.get_nowait())
        except queue.Empty:
            pass
        self.root.after(100, self.flush_log_queue)

    def refresh_microphones(self):
        labels = []
        for idx, name in enumerate(sr.Microphone.list_microphone_names()):
            labels.append(f"{idx}: {name}")
        self.mic_combo["values"] = labels

        if labels:
            preferred = next((label for label in labels if "fifine" in label.lower()), labels[0])
            self.selected_mic.set(preferred)
            self.status_text.set("Ready")
        else:
            self.selected_mic.set("")
            self.status_text.set("No microphones detected")

    def selected_mic_index(self):
        value = self.selected_mic.get().strip()
        if not value:
            return None
        return int(value.split(":", 1)[0])

    def ensure_model(self):
        if self.whisper_model is None:
            self.log_queue.put("[SYSTEM] Loading Whisper model 'tiny.en' for transcription...\n")
            self.whisper_model = WhisperModel("tiny.en", device="cpu", compute_type="int8")

    def start_test(self):
        if self.recording:
            return

        mic_index = self.selected_mic_index()
        if mic_index is None:
            self.status_text.set("Choose a microphone first")
            return

        self.recording = True
        self.test_btn.configure(state="disabled")
        self.status_text.set("Get ready...")
        self.level_text.set("RMS: 0.00% | Peak: 0.00%")
        self.signal_text.set("Testing...")
        self.transcript_text.set("")

        worker = threading.Thread(target=self.run_test, args=(mic_index,), daemon=True)
        worker.start()

    def run_test(self, mic_index):
        temp_path = None
        converted_temp_path = None
        try:
            capture_device = resolve_capture_device(mic_index)
            self.log_queue.put(f"\n=== Testing mic index {mic_index} ===\n")
            self.log_queue.put(f"[MIC] Using ALSA device: {capture_device}\n")
            self.log_queue.put(f"[MIC] Get ready... recording starts in {PRE_ROLL_SECONDS:.1f} seconds.\n")
            self.root.after(0, lambda: self.status_text.set("Get ready..."))
            time.sleep(PRE_ROLL_SECONDS)
            self.log_queue.put(f"[MIC] Recording for {RECORD_SECONDS} seconds. Speak now.\n")
            self.root.after(0, lambda: self.status_text.set("Recording..."))

            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_file:
                temp_path = temp_file.name

            capture_started = time.perf_counter()
            subprocess.run(
                [
                    "arecord",
                    "-D",
                    capture_device,
                    "-f",
                    "S16_LE",
                    "-r",
                    str(CAPTURE_SAMPLE_RATE),
                    "-c",
                    str(CHANNELS),
                    "-d",
                    str(RECORD_SECONDS),
                    temp_path,
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            capture_elapsed = time.perf_counter() - capture_started

            with wave.open(temp_path, "rb") as wav_file:
                raw_frames = wav_file.readframes(wav_file.getnframes())

            converted_frames = audioop.ratecv(
                raw_frames,
                SAMPLE_WIDTH,
                CHANNELS,
                CAPTURE_SAMPLE_RATE,
                TARGET_SAMPLE_RATE,
                None,
            )[0]

            rms_pct, peak_pct = compute_audio_levels(converted_frames, SAMPLE_WIDTH)
            signal_state = classify_signal(rms_pct, peak_pct)

            self.root.after(0, lambda: self.level_text.set(f"RMS: {rms_pct:.2f}% | Peak: {peak_pct:.2f}%"))
            self.root.after(0, lambda: self.signal_text.set(signal_state))
            self.log_queue.put(f"[MIC] Levels => RMS {rms_pct:.2f}% | Peak {peak_pct:.2f}%\n")
            self.log_queue.put(f"[MIC] Signal state => {signal_state}\n")

            processing_started = time.perf_counter()

            if signal_state == "Mostly silence":
                transcript = SILENCE_TRANSCRIPT
                wake_match = False
                processing_elapsed = time.perf_counter() - processing_started
                total_elapsed = capture_elapsed + processing_elapsed
                self.log_queue.put("[WHISPER] Silence detected, skipping transcription.\n")
            else:
                self.ensure_model()
                self.root.after(0, lambda: self.status_text.set("Transcribing..."))

                with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as converted_file:
                    converted_temp_path = converted_file.name

                with wave.open(converted_temp_path, "wb") as wav_file:
                    wav_file.setnchannels(CHANNELS)
                    wav_file.setsampwidth(SAMPLE_WIDTH)
                    wav_file.setframerate(TARGET_SAMPLE_RATE)
                    wav_file.writeframes(converted_frames)

                trimmed_temp_path = f"{converted_temp_path}.trimmed.wav"
                subprocess.run(
                    [
                        "ffmpeg",
                        "-y",
                        "-i",
                        converted_temp_path,
                        "-af",
                        "silenceremove=start_periods=1:start_silence=0.1:start_threshold=-35dB:stop_periods=-1:stop_silence=0.2:stop_threshold=-35dB",
                        trimmed_temp_path,
                    ],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )

                transcribe_path = trimmed_temp_path if Path(trimmed_temp_path).exists() and Path(trimmed_temp_path).stat().st_size > 1024 else converted_temp_path

                segments, _ = self.whisper_model.transcribe(
                    transcribe_path,
                    beam_size=1,
                    best_of=1,
                    temperature=0.0,
                    language="en",
                    vad_filter=True,
                    condition_on_previous_text=False,
                )
                transcript = "".join(segment.text for segment in segments).strip()
                processing_elapsed = time.perf_counter() - processing_started
                total_elapsed = capture_elapsed + processing_elapsed
                wake_match = looks_like_wake_word(transcript)

                if not transcript:
                    transcript = "(no speech recognized)"

            self.root.after(0, lambda: self.transcript_text.set(transcript))
            self.log_queue.put(f"[WHISPER] Transcript => {transcript}\n")
            self.log_queue.put(f"[WHISPER] Wake-word match => {'yes' if wake_match else 'no'}\n")
            self.log_queue.put(f"[TIMING] Capture time => {capture_elapsed:.2f} seconds\n")
            self.log_queue.put(f"[TIMING] Processing time => {processing_elapsed:.2f} seconds\n")
            self.log_queue.put(f"[TIMING] Total time => {total_elapsed:.2f} seconds\n")
            self.root.after(0, lambda: self.status_text.set("Test complete"))
        except Exception as exc:
            self.root.after(0, lambda: self.status_text.set("Test failed"))
            self.root.after(0, lambda: self.signal_text.set("Error"))
            self.log_queue.put(f"[ERROR] {exc}\n")
        finally:
            if temp_path:
                try:
                    Path(temp_path).unlink()
                except OSError:
                    pass
            if converted_temp_path:
                try:
                    Path(converted_temp_path).unlink()
                except OSError:
                    pass
                trimmed_candidate = Path(f"{converted_temp_path}.trimmed.wav")
                try:
                    if trimmed_candidate.exists():
                        trimmed_candidate.unlink()
                except OSError:
                    pass

            self.recording = False
            self.root.after(0, lambda: self.test_btn.configure(state="normal"))


def main():
    root = tk.Tk()
    style = ttk.Style()
    for preferred in ("clam", "default"):
        if preferred in style.theme_names():
            style.theme_use(preferred)
            break
    MicTesterApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
