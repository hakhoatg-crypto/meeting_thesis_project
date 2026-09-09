import sqlite3
import os
from datetime import datetime

# Thư mục gốc dự án
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'data', 'meetings.db')
OUTPUT_DIR = os.path.join(BASE_DIR, 'data', 'text_reports')

os.makedirs(OUTPUT_DIR, exist_ok=True)

print("========================================================")
print("      CHUYEN DOI DATABASE MEETINGS.DB SANG FILE TXT")
print("========================================================\n")

if not os.path.exists(DB_PATH):
    print(f"X Khong tim thay file database tai: {DB_PATH}")
    exit(1)

try:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT id, room_name, audio_path, transcript, summary, duration_seconds, created_at FROM meetings ORDER BY id DESC")
    rows = cursor.fetchall()

    if not rows:
        print("[!] Chua co cuoc hop nao trong Database!")
    else:
        # 1. Xuất file TXT tổng hợp tất cả cuộc họp
        master_txt_path = os.path.join(OUTPUT_DIR, "Danh_Sach_Tat_Ca_Cuoc_Hop.txt")
        with open(master_txt_path, "w", encoding="utf-8") as f:
            f.write("========================================================\n")
            f.write("      BÁO CÁO NHẬT KÝ TẤT CẢ CUỘC HỌP AI STUDIO\n")
            f.write(f"      Thời gian xuất file: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("========================================================\n\n")

            for row in rows:
                m_id, room_name, audio_path, transcript, summary, duration, created_at = row
                dur_str = f"{int(duration)} giây" if duration else "Chưa ghi nhận"
                f.write(f"=== CUỘC HỌP #{m_id}: {room_name} ===\n")
                f.write(f"⏱️ Ngày khởi tạo: {created_at}\n")
                f.write(f"⏳ Thời lượng: {dur_str}\n")
                f.write(f"🎙️ File ghi âm: {audio_path or 'Không có'}\n\n")
                f.write("📝 BIÊN BẢN HỘI THOẠI (TRANSCRIPT):\n")
                f.write(f"{transcript or 'Chưa có nội dung hội thoại.'}\n\n")
                f.write("🤖 BẢN TÓM TẮT AI (SUMMARY):\n")
                f.write(f"{summary or 'Chưa tạo bản tóm tắt.'}\n")
                f.write("--------------------------------------------------------\n\n")

        print(f"[+] DA XUAT THANH CONG FILE TXT TONG HOP:")
        print(f"    File: {master_txt_path}\n")

        # 2. Xuất từng file TXT riêng cho từng cuộc họp
        for row in rows:
            m_id, room_name, audio_path, transcript, summary, duration, created_at = row
            clean_date = (created_at or "").replace(":", "-").replace(" ", "_")
            single_txt_path = os.path.join(OUTPUT_DIR, f"CuocHop_{m_id}.txt")
            with open(single_txt_path, "w", encoding="utf-8") as f:
                f.write(f"CUỘC HỌP #{m_id}: {room_name}\n")
                f.write(f"Thời gian: {created_at}\n")
                f.write(f"Thời lượng: {duration} giây\n")
                f.write("========================================================\n\n")
                f.write("📝 BIÊN BẢN HỘI THOẠI CHITIẾT:\n")
                f.write(f"{transcript or 'Chưa có nội dung.'}\n\n")
                f.write("🤖 BẢN TÓM TẮT AI:\n")
                f.write(f"{summary or 'Chưa có tóm tắt.'}\n")

        print(f"[+] Da luu danh sach cac file TXT chi tiet trong thu muc:\n    {OUTPUT_DIR}")

    conn.close()

except Exception as e:
    print(f"[X] Loi khi xuat file: {e}")
