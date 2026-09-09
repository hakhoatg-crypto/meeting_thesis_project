"""
Chương trình chạy AI Studio Trực Tiếp Offline trên Máy Tính
(KHÔNG CẦN BẬT SERVER / KHÔNG CẦN BẬT WEB / KHÔNG CẦN NGROK)
"""

import os
import sys
import wave
import datetime
import sounddevice as sd

# Thêm đường dẫn gốc
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import config
from src.transcriber import Transcriber
from src.summarizer import Summarizer

def record_audio(output_filename, sample_rate=16000):
    print("========================================================")
    print("   AI MEETING STUDIO - CHAY TRUC TIEP OFFLINE (KHONG SERVER)")
    print("========================================================\n")
    print("-> Nhan phi [ENTER] de BAT DAU GHI AM...")
    input()

    print("🔴 DANG GHI AM GIONG NOI... (Nhan [ENTER] de DUNG GHI AM)")

    audio_data = []

    def callback(indata, frames, time_info, status):
        audio_data.append(indata.copy())

    stream = sd.InputStream(
        samplerate=sample_rate,
        channels=1,
        dtype="int16",
        callback=callback
    )
    with stream:
        input()  # Chờ người dùng nhấn Enter để dừng

    print("⏹️ Da dung ghi am! Dang luu file am thanh...")

    os.makedirs(config.AUDIO_DIR, exist_ok=True)
    with wave.open(output_filename, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        for chunk in audio_data:
            wf.writeframes(chunk.tobytes())

    print(f"[+] Da luu file ghi am tại: {output_filename}\n")


def main():
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    wav_filename = os.path.join(config.AUDIO_DIR, f"offline_{timestamp}.wav")

    # 1. Ghi âm trực tiếp từ mic
    record_audio(wav_filename)

    # 2. Chạy nhận dạng giọng nói bằng VinAI PhoWhisper
    print("⏳ Dang phan tich giong noi bang mo hinh AI VinAI PhoWhisper...")
    transcriber = Transcriber()
    result = transcriber.transcribe(wav_filename)
    transcript = result.get("text", "").strip()

    print("\n========================================================")
    print("📝 NOI DUNG VAN BAN (TRANSCRIPT):")
    print("========================================================")
    print(transcript if transcript else "(Khong nghe thay giong noi)")

    # 3. Tóm tắt AI
    print("\n========================================================")
    print("🤖 BAN TOM TAT AI (SUMMARY):")
    print("========================================================")
    summarizer = Summarizer()
    summary = summarizer.summarize(transcript) if transcript else "Chua co noi dung."
    print(summary)

    # 4. Xuất file TXT tự động
    txt_dir = os.path.join(config.DATA_DIR, "text_reports")
    os.makedirs(txt_dir, exist_ok=True)
    txt_filename = os.path.join(txt_dir, f"CuocHop_Offline_{timestamp}.txt")
    with open(txt_filename, "w", encoding="utf-8") as f:
        f.write(f"BÁO CÁO CUỘC HỌP OFFLINE - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"File ghi am: {wav_filename}\n")
        f.write("========================================================\n\n")
        f.write("📝 NỘI DUNG VĂN BẢN CHÍNH XÁC (PHOWHISPER):\n")
        f.write(f"{transcript}\n\n")
        f.write("🤖 BẢN TÓM TẮT AI:\n")
        f.write(f"{summary}\n")

    print("\n========================================================")
    print(f"[+] DA XUAT THÀNH CONG FILE TXT BAO CAO:")
    print(f"👉 File: {txt_filename}")
    print("========================================================\n")


if __name__ == "__main__":
    main()
