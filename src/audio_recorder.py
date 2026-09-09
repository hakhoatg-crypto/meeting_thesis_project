"""
Module: audio_recorder.py
Chuc nang: Lang nghe lien tuc qua microphone, tu dong phat hien tieng noi (VAD)
de bat dau ghi am, va tu dong dung khi im lang qua lau.

Ky thuat su dung: WebRTC VAD (Voice Activity Detection) - thuat toan nhe,
chay thoi gian thuc, ban dau duoc Google phat trien cho WebRTC.
"""

import time
import wave
import queue
import datetime
import os

import sounddevice as sd
import webrtcvad

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


class AudioRecorder:
    def __init__(self):
        self.vad = webrtcvad.Vad(config.VAD_AGGRESSIVENESS)
        self.frame_size = int(config.SAMPLE_RATE * config.FRAME_DURATION_MS / 1000)

    def _is_speech(self, frame_bytes: bytes) -> bool:
        """Kiem tra 1 frame am thanh co chua tieng noi hay khong."""
        try:
            return self.vad.is_speech(frame_bytes, config.SAMPLE_RATE)
        except Exception:
            return False

    def record_until_silence(self) -> str:
        """
        Lang nghe lien tuc tu microphone. Khi phat hien tieng noi se bat dau ghi.
        Ghi lien tuc cho den khi im lang qua config.SILENCE_TIMEOUT_SECONDS.
        Ham nay se "block" (dung lai doi) cho den khi co nguoi noi neu chua co ai noi.

        Tra ve: duong dan tuyet doi cua file .wav vua ghi duoc.
        """
        print("[AudioRecorder] Dang lang nghe... cho phat hien tieng noi.")

        audio_q = queue.Queue()

        def callback(indata, frames, time_info, status):
            audio_q.put(bytes(indata))

        stream = sd.RawInputStream(
            samplerate=config.SAMPLE_RATE,
            blocksize=self.frame_size,
            device=config.MIC_DEVICE_INDEX,
            dtype="int16",
            channels=1,
            callback=callback,
        )

        recorded_frames = []
        is_recording = False
        silence_start = None
        start_time = None

        with stream:
            while True:
                frame = audio_q.get()
                speech = self._is_speech(frame)

                if not is_recording:
                    if speech:
                        print("[AudioRecorder] Phat hien tieng noi. Bat dau ghi am.")
                        is_recording = True
                        start_time = datetime.datetime.now()
                        recorded_frames = [frame]
                        silence_start = None
                else:
                    recorded_frames.append(frame)
                    if speech:
                        silence_start = None
                    else:
                        if silence_start is None:
                            silence_start = time.time()
                        elif time.time() - silence_start >= config.SILENCE_TIMEOUT_SECONDS:
                            print(f"[AudioRecorder] Im lang {config.SILENCE_TIMEOUT_SECONDS}s. "
                                  f"Dung ghi am.")
                            break

        filename = start_time.strftime("meeting_%Y%m%d_%H%M%S.wav")
        filepath = os.path.join(config.AUDIO_DIR, filename)

        with wave.open(filepath, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # int16 = 2 bytes
            wf.setframerate(config.SAMPLE_RATE)
            wf.writeframes(b"".join(recorded_frames))

        duration_sec = len(recorded_frames) * config.FRAME_DURATION_MS / 1000
        print(f"[AudioRecorder] Da luu: {filepath} ({duration_sec:.0f} giay)")
        return filepath
