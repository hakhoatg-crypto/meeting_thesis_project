"""
Module: streaming_transcriber.py
Chuc nang: Nhan dien giong noi THOI GIAN THUC (streaming) - tra ket qua ngay
lap tuc trong khi nguoi dung dang noi, khac voi transcriber.py (Whisper) can
doi ca doan am thanh xong moi xu ly.

Ky thuat su dung: Vosk - bo cong cu ASR (Automatic Speech Recognition) mo nguon,
nho gon, thiet ke rieng cho ung dung streaming/real-time. Vosk dua tren kien truc
Kaldi (mo hinh HMM-DNN lai), khac voi kien truc Transformer end-to-end cua Whisper.

Vosk ho tro tra ve 2 loai ket qua:
    - Partial result: ket qua "tam thoi", co the thay doi khi nghe them am thanh
      (vi du dang noi "toi muon" co the hien "partial: toi muon lam")
    - Final result: ket qua "chot", khi phat hien khoang lang du de xac dinh
      1 cau da ket thuc

Yeu cau: phai tai model Vosk tieng Viet ve truoc, xem huong dan trong README.md
phan "Cai dat model Vosk cho Live Caption".
"""

import os
import sys
import json

try:
    import vosk
    vosk.SetLogLevel(-1)
except ImportError:
    vosk = None

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

class StreamingTranscriber:
    """
    Moi ket noi WebSocket (moi nguoi dung dang xem trang Live Caption) nen tao
    rieng 1 instance cua class nay, vi KaldiRecognizer luu trang thai (state)
    rieng cho tung phien nhan dien.
    """

    def __init__(self):
        if vosk is None:
            raise RuntimeError("Thu vien vosk chua duoc cai dat.")
        if not os.path.isdir(config.VOSK_MODEL_PATH):
            raise FileNotFoundError(
                f"Khong tim thay model Vosk tai: {config.VOSK_MODEL_PATH}\n"
                f"Xem huong dan tai model trong README.md, phan 'Live Caption'."
            )
        self.model = vosk.Model(config.VOSK_MODEL_PATH)
        self.recognizer = vosk.KaldiRecognizer(self.model, config.SAMPLE_RATE)
        self.recognizer.SetWords(True)

    def accept_audio_chunk(self, audio_bytes: bytes) -> dict:
        """
        Nhan 1 doan am thanh nho (PCM 16-bit, mono, 16000Hz), tra ve:
            {"type": "final", "text": "..."}   khi 1 cau da hoan chinh
            {"type": "partial", "text": "..."} khi van dang noi giua chung
        """
        if self.recognizer.AcceptWaveform(audio_bytes):
            result = json.loads(self.recognizer.Result())
            return {"type": "final", "text": result.get("text", "")}
        else:
            result = json.loads(self.recognizer.PartialResult())
            return {"type": "partial", "text": result.get("partial", "")}

    def final_flush(self) -> str:
        """Goi khi ket thuc phien, lay not phan con lai chua duoc chot."""
        result = json.loads(self.recognizer.FinalResult())
        return result.get("text", "")
