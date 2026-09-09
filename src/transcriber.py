"""
Module: transcriber.py
Chức năng: Chuyển đổi file âm thanh (.wav) thành văn bản tiếng Việt chính xác cao.
Hỗ trợ cả VinAI PhoWhisper (mô hình ASR tiếng Việt hàng đầu của VinAI)
và OpenAI Whisper (Faster-Whisper).
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


class Transcriber:
    def __init__(self):
        self.model_name = config.WHISPER_MODEL_SIZE
        print(f"[Transcriber] Dang khoi tao mo hinh ASR '{self.model_name}'...")

        if "phowhisper" in self.model_name.lower():
            from transformers import pipeline
            device_id = 0 if config.WHISPER_DEVICE.lower() == "cuda" else -1
            self.pipe = pipeline(
                "automatic-speech-recognition",
                model=self.model_name,
                device=device_id,
            )
            self.use_phowhisper = True
            print(f"[Transcriber] [+] Da tai mo hinh VinAI PhoWhisper thanh cong!")
        else:
            from faster_whisper import WhisperModel
            self.model = WhisperModel(
                self.model_name,
                device=config.WHISPER_DEVICE,
                compute_type=config.WHISPER_COMPUTE_TYPE,
            )
            self.use_phowhisper = False
            print(f"[Transcriber] [+] Da tai mo hinh Faster-Whisper thanh cong!")

    def transcribe(self, audio_filepath: str) -> dict:
        """
        Chuyển file âm thanh thành văn bản tiếng Việt.

        Trả về dict gồm:
            - text: toàn bộ văn bản
            - segments: danh sách các đoạn nhỏ kèm thời gian
            - language_probability: độ tin cậy phát hiện ngôn ngữ
        """
        if self.use_phowhisper:
            result = self.pipe(audio_filepath)
            text = result.get("text", "").strip()
            return {
                "text": text,
                "segments": [{"start": 0.0, "end": 0.0, "text": text}],
                "language_probability": 1.0,
            }
        else:
            segments_gen, info = self.model.transcribe(
                audio_filepath,
                language=config.WHISPER_LANGUAGE,
                beam_size=5,
            )

            segments = []
            text_parts = []
            for seg in segments_gen:
                segments.append({
                    "start": seg.start,
                    "end": seg.end,
                    "text": seg.text.strip(),
                })
                text_parts.append(seg.text.strip())

            return {
                "text": " ".join(text_parts),
                "segments": segments,
                "language_probability": info.language_probability,
            }
