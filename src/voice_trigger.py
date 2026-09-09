"""
Module: voice_trigger.py
Chức năng: Lắng nghe mic ngầm ở chế độ chờ (Standby), tự động bật cuộc họp
khi nghe thấy câu lệnh "Bắt đầu cuộc họp" hoặc "Mở cuộc họp".
"""

import os
import sys
import json
import time
import queue
try:
    import vosk
    vosk.SetLogLevel(-1)
except ImportError:
    vosk = None

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

class VoiceCommandListener:
    def __init__(self, pipeline):
        self.pipeline = pipeline
        self._running = False
        self._model = None

    def start(self):
        if self._running:
            return
        if vosk is None:
            print("[VoiceCommandListener] Thu vien vosk chua duoc cai dat. Bo qua tinh nang Voice Trigger.")
            return
        if not os.path.isdir(config.VOSK_MODEL_PATH):
            print("[VoiceCommandListener] Khong tim thay model Vosk.")
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def _run(self):
        try:
            self._model = vosk.Model(config.VOSK_MODEL_PATH)
        except Exception as e:
            print(f"[VoiceCommandListener] Loi khoi tao Vosk model: {e}")
            return

        recognizer = vosk.KaldiRecognizer(self._model, config.SAMPLE_RATE)
        recognizer.SetWords(True)

        audio_q = queue.Queue()

        def callback(indata, frames, time_info, status):
            if self._running:
                audio_q.put(bytes(indata))

        frame_size = int(config.SAMPLE_RATE * config.FRAME_DURATION_MS / 1000)

        start_keywords = [
            "bắt đầu cuộc họp", "bắt đầu họp", "mở cuộc họp",
            "bắt đầu cuộc họp mới", "bat dau cuoc hop", "bat dau hop", "mo cuoc hop"
        ]

        print("[VoiceCommandListener] Đã bật chế độ chờ nhận diện giọng nói lệnh 'Bắt đầu cuộc họp'...")

        try:
            stream = sd.RawInputStream(
                samplerate=config.SAMPLE_RATE,
                blocksize=frame_size,
                device=config.MIC_DEVICE_INDEX,
                dtype="int16",
                channels=1,
                callback=callback,
            )
        except Exception as e:
            print(f"[VoiceCommandListener] Khong mo duoc mic cho standby trigger: {e}")
            return

        with stream:
            while self._running:
                try:
                    frame = audio_q.get(timeout=0.5)
                except queue.Empty:
                    continue

                # Nếu cuộc họp chính đang chạy thì tạm ngưng check trigger bật
                if self.pipeline.is_running:
                    time.sleep(0.5)
                    continue

                if recognizer.AcceptWaveform(frame):
                    text = json.loads(recognizer.Result()).get("text", "").lower()
                    if text and any(kw in text for kw in start_keywords):
                        print(f"[VoiceCommandListener] 🟢 Phát hiện câu lệnh BẮT ĐẦU: '{text}'!")
                        self.pipeline.start(room_name="Phòng họp Voice Command")
                else:
                    partial = json.loads(recognizer.PartialResult()).get("partial", "").lower()
                    if partial and any(kw in partial for kw in start_keywords):
                        print(f"[VoiceCommandListener] 🟢 Phát hiện câu lệnh BẮT ĐẦU từ partial: '{partial}'!")
                        self.pipeline.start(room_name="Phòng họp Voice Command")
