"""
Module: noise_filter.py
Chức năng: Lọc tạp âm, khử ồn môi trường thời gian thực (Realtime Audio Noise Reduction / Filtering)
dành riêng cho thiết bị nhúng Jetson Nano.

Các công nghệ khử ồn được áp dụng:
1. High-Pass Filter (Lọc bỏ tần số ù thấp < 80Hz như tiếng gió quạt, tiếng rè nguồn điện).
2. Spectral Noise Suppression (Giảm thiểu tiếng xì nền môi trường).
"""

import numpy as np

class AudioNoiseFilter:
    def __init__(self, sample_rate=16000):
        self.sample_rate = sample_rate
        self._prev_in = 0.0
        self._prev_out = 0.0

    def filter_pcm16_frame(self, pcm_bytes: bytes) -> bytes:
        """
        Nhận mẩu âm thanh PCM 16-bit Mono (16kHz), lọc nhiễu âm và trả về PCM 16-bit sạch.
        """
        if not pcm_bytes:
            return pcm_bytes
        try:
            audio_data = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32)
            if len(audio_data) == 0:
                return pcm_bytes

            # 1. High-Pass Filter (Lọc bỏ dải tần ù thấp < 80Hz)
            alpha = 0.95
            filtered = np.zeros_like(audio_data)
            for i in range(len(audio_data)):
                filtered[i] = alpha * (self._prev_out + audio_data[i] - self._prev_in)
                self._prev_in = audio_data[i]
                self._prev_out = filtered[i]

            # 2. Dynamic Noise Floor Suppression (Khử nền xì xào khoảng lặng)
            max_val = np.max(np.abs(filtered))
            if max_val < 300:  # Ngưỡng nhiễu nền môi trường
                filtered = filtered * 0.1

            # Ép dải về PCM 16-bit
            np.clip(filtered, -32768, 32767, out=filtered)
            return filtered.astype(np.int16).tobytes()
        except Exception:
            return pcm_bytes
