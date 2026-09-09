#!/usr/bin/env python3
"""
main.py - Diem khoi dau chinh cua he thong.

Chay file nay de bat dau qua trinh:
    1. Lang nghe lien tuc qua microphone
    2. Tu dong ghi am khi phat hien tieng noi, tu dong dung khi im lang
    3. Chuyen am thanh thanh van ban (Whisper offline)
    4. Tom tat noi dung (TextRank)
    5. Luu vao co so du lieu de xem lai qua Dashboard web

CACH DUNG:
    python main.py
"""

import os

os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"  # tranh loi xung dot OpenMP tren Windows

import time
import wave
import contextlib

import config
from src.audio_recorder import AudioRecorder
from src.transcriber import Transcriber
from src.summarizer import Summarizer
from src import database

llm_summarizer = None
if config.ENABLE_LLM_SUMMARY:
    try:
        from src.llm_summarizer import LLMSummarizer
        llm_summarizer = LLMSummarizer()
        print("[main] Da bat tinh nang tom tat bang LLM (che do so sanh).")
    except Exception as e:
        print(f"[main] Khong the khoi tao LLM Summarizer ({e}). "
              f"Se chi dung TextRank.")


def get_audio_duration(filepath):
    with contextlib.closing(wave.open(filepath, 'r')) as f:
        frames = f.getnframes()
        rate = f.getframerate()
        return frames / float(rate)


def main():
    print("=" * 70)
    print("HE THONG GHI AM & TOM TAT CUOC HOP TU DONG")
    print("Do an tot nghiep - Ung dung AI nhan dien giong noi tren Jetson Nano")
    print("=" * 70)

    database.init_db()
    recorder = AudioRecorder()
    transcriber = Transcriber()
    summarizer = Summarizer()

    print("\n[main] He thong san sang. Nhan Ctrl+C de dung.\n")

    while True:
        try:
            # Buoc 1+2: Ghi am tu dong
            audio_path = recorder.record_until_silence()
            duration = get_audio_duration(audio_path)

            # Buoc 3: Chuyen giong noi thanh van ban
            result = transcriber.transcribe(audio_path)
            transcript = result["text"]
            confidence = result["language_probability"]

            if not transcript.strip():
                print("[main] Khong nhan dien duoc noi dung nao, bo qua.\n")
                continue

            # Buoc 4: Tom tat bang TextRank (luon chay, mien phi, offline)
            t0 = time.time()
            summary = summarizer.summarize(transcript)
            summary_time = time.time() - t0

            # Buoc 4b: Tom tat bang LLM (tuy chon, de so sanh)
            llm_summary_text = None
            llm_summary_time = None
            if llm_summarizer is not None:
                try:
                    llm_result = llm_summarizer.summarize(transcript)
                    llm_summary_text = llm_result["summary"]
                    llm_summary_time = llm_result["elapsed_seconds"]
                except Exception as e:
                    print(f"[main] Loi khi goi LLM Summarizer: {e}")

            # Buoc 5: Luu vao database
            meeting_id = database.insert_meeting(
                audio_path=audio_path,
                transcript=transcript,
                summary=summary,
                summary_time_seconds=summary_time,
                llm_summary=llm_summary_text,
                llm_summary_time_seconds=llm_summary_time,
                duration_seconds=duration,
                language_confidence=confidence,
            )

            print("\n" + "=" * 70)
            print(f"HOAN TAT CUOC HOP #{meeting_id}")
            print("=" * 70)
            print(f"Thoi luong: {duration:.0f} giay")
            print(f"Do tin cay ngon ngu: {confidence:.0%}")
            print("-" * 70)
            print(f"TOM TAT (TextRank, {summary_time:.2f}s):")
            print(summary)
            if llm_summary_text:
                print("-" * 70)
                print(f"TOM TAT (LLM, {llm_summary_time:.2f}s):")
                print(llm_summary_text)
            print("=" * 70)
            print(f"\n>>> Xem chi tiet tai Dashboard web (chay app.py trong thu muc web/)\n")

        except KeyboardInterrupt:
            print("\n[main] Da dung he thong.")
            break
        except Exception as e:
            print(f"[main] Loi: {e}")
            import time
            time.sleep(3)


if __name__ == "__main__":
    main()
