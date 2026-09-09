#!/usr/bin/env python3
"""
evaluate.py - Danh gia do chinh xac cua he thong nhan dien giong noi.

Su dung chi so WER (Word Error Rate - Ty le loi tu), la thuoc do chuan trong
linh vuc nghien cuu ASR (Automatic Speech Recognition), duoc dinh nghia:

    WER = (S + D + I) / N

Trong do:
    S = so tu bi thay the sai (Substitutions)
    D = so tu bi thieu / xoa mat (Deletions)
    I = so tu bi them thua (Insertions)
    N = tong so tu trong van ban goc (Ground Truth)

WER cang THAP thi he thong cang CHINH XAC (0% la hoan hao tuyet doi).

CACH DUNG:
    1. Ghi am 1 doan noi ngan, luu vao test_data/sample.wav
    2. Tu go tay chinh xac 100% noi dung ban da noi vao test_data/ground_truth.txt
    3. Chay: python evaluate.py
    4. Ket qua WER se duoc in ra, dung so nay de dua vao bao cao do an
       (chuong "Danh gia va Ket qua thuc nghiem")

Co the chay nhieu lan voi nhieu file mau khac nhau (sample1.wav, sample2.wav...)
de tinh WER trung binh, tang do tin cay khoa hoc cho bao cao.
"""

import os
import sys
import glob

os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

import jiwer

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import config
from src.transcriber import Transcriber

TEST_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_data")


def evaluate_single(transcriber, audio_path, ground_truth_path):
    with open(ground_truth_path, "r", encoding="utf-8") as f:
        ground_truth = f.read().strip()

    result = transcriber.transcribe(audio_path)
    hypothesis = result["text"].strip()

    # Chuan hoa van ban truoc khi so sanh: chuyen chu thuong, bo dau cau thua
    transform = jiwer.Compose([
        jiwer.ToLowerCase(),
        jiwer.RemoveMultipleSpaces(),
        jiwer.Strip(),
        jiwer.RemovePunctuation(),
        jiwer.ReduceToListOfListOfWords(),
    ])

    wer = jiwer.wer(
        ground_truth, hypothesis,
        truth_transform=transform, hypothesis_transform=transform,
    )

    return {
        "audio": os.path.basename(audio_path),
        "ground_truth": ground_truth,
        "hypothesis": hypothesis,
        "wer": wer,
    }


def main():
    print("=" * 70)
    print("DANH GIA DO CHINH XAC HE THONG - WORD ERROR RATE (WER)")
    print("=" * 70)

    os.makedirs(TEST_DATA_DIR, exist_ok=True)

    wav_files = sorted(glob.glob(os.path.join(TEST_DATA_DIR, "*.wav")))

    if not wav_files:
        print(f"\n[!] Khong tim thay file .wav nao trong thu muc: {TEST_DATA_DIR}")
        print("Huong dan chuan bi du lieu kiem thu:")
        print(f"  1. Ghi am 1 doan noi, luu vao: {TEST_DATA_DIR}/sample1.wav")
        print(f"  2. Go tay chinh xac noi dung da noi vao: {TEST_DATA_DIR}/sample1_ground_truth.txt")
        print("  3. Co the lap lai voi sample2.wav, sample3.wav... de co nhieu mau kiem thu")
        print("  4. Chay lai: python evaluate.py")
        return

    transcriber = Transcriber()
    results = []

    for wav_path in wav_files:
        base_name = os.path.splitext(wav_path)[0]
        gt_path = base_name + "_ground_truth.txt"

        if not os.path.exists(gt_path):
            print(f"[!] Bo qua {wav_path}: khong tim thay file ground truth tuong ung ({gt_path})")
            continue

        print(f"\n[*] Dang danh gia: {os.path.basename(wav_path)}")
        result = evaluate_single(transcriber, wav_path, gt_path)
        results.append(result)

        print(f"    Van ban goc (Ground Truth) : {result['ground_truth']}")
        print(f"    Van ban AI nhan dien       : {result['hypothesis']}")
        print(f"    WER                        : {result['wer']:.2%}")

    if results:
        avg_wer = sum(r["wer"] for r in results) / len(results)
        print("\n" + "=" * 70)
        print(f"KET QUA TONG HOP ({len(results)} mau kiem thu)")
        print("=" * 70)
        print(f"WER trung binh: {avg_wer:.2%}")
        print(f"(Co the trich so nay vao bao cao do an, chuong Danh gia thuc nghiem)")
    else:
        print("\n[!] Khong co mau kiem thu hop le nao duoc danh gia.")


if __name__ == "__main__":
    main()
