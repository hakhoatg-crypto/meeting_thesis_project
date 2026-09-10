"""
Module: database.py
Chuc nang: Luu tru va truy van thong tin cac cuoc hop va nguoi dung bang SQLite.
"""

import os
import sys
import sqlite3
import datetime
import threading

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


def sync_to_cloud():
    """Đồng bộ dữ liệu users và meetings lên Cloudinary làm bản sao lưu vĩnh viễn."""
    try:
        from src import cloudinary_storage
        conn = get_connection()
        user_rows = conn.execute("SELECT id, email, password_hash, full_name, role, created_at FROM users").fetchall()
        meeting_rows = conn.execute("""
            SELECT id, user_id, room_name, audio_path, transcript, summary,
                   summary_time_seconds, llm_summary, llm_summary_time_seconds,
                   duration_seconds, language_confidence, created_at
            FROM meetings
        """).fetchall()
        conn.close()

        users_list = [dict(r) for r in user_rows]
        meetings_list = [dict(r) for r in meeting_rows]

        cloudinary_storage.upload_db_backup({"users": users_list, "meetings": meetings_list})
    except Exception as e:
        print(f"[database] Lỗi sync_to_cloud: {e}")


def trigger_cloud_sync():
    threading.Thread(target=sync_to_cloud, daemon=True).start()


def get_connection():
    conn = sqlite3.connect(config.DATABASE_PATH, timeout=60.0)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=60000;")
    except Exception:
        pass
    return conn


def init_db():
    """Tao bang users va meetings neu chua ton tai."""
    conn = get_connection()
    
    # Bang users
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT,
            role TEXT DEFAULT 'user',
            created_at TEXT NOT NULL
        )
    """)
    
    # Bang meetings
    conn.execute("""
        CREATE TABLE IF NOT EXISTS meetings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER DEFAULT 1,
            room_name TEXT DEFAULT 'Phiên ghi âm chính',
            audio_path TEXT NOT NULL,
            transcript TEXT,
            summary TEXT,
            summary_time_seconds REAL,
            llm_summary TEXT,
            llm_summary_time_seconds REAL,
            duration_seconds REAL,
            language_confidence REAL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)
    
    # Ho tro nang cap database cu
    existing_cols = [row[1] for row in conn.execute("PRAGMA table_info(meetings)").fetchall()]
    for col, col_type in [
        ("user_id", "INTEGER DEFAULT 1"),
        ("summary_time_seconds", "REAL"),
        ("llm_summary", "TEXT"),
        ("llm_summary_time_seconds", "REAL"),
    ]:
        if col not in existing_cols:
            conn.execute(f"ALTER TABLE meetings ADD COLUMN {col} {col_type}")

    existing_user_cols = [row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()]
    if "role" not in existing_user_cols:
        conn.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'user'")
    
    # Dam bao luon luon co tai khoan admin hakhoatg@gmail.com (mat khau: 123456)
    DEFAULT_ADMIN_HASH = "e2c3b63eb9c9ea53f45c1865b9c98ffb5588c1a7c9f47affb7b89e1078817d4c"
    admin_exists = conn.execute("SELECT COUNT(*) FROM users WHERE email = 'hakhoatg@gmail.com'").fetchone()[0]
    if admin_exists == 0:
        conn.execute("""
            INSERT INTO users (email, password_hash, full_name, role, created_at)
            VALUES ('hakhoatg@gmail.com', ?, 'Hà Khoa (Admin)', 'admin', ?)
        """, (DEFAULT_ADMIN_HASH, datetime.datetime.now().isoformat()))
    else:
        conn.execute("UPDATE users SET password_hash = ?, role = 'admin' WHERE email = 'hakhoatg@gmail.com'", (DEFAULT_ADMIN_HASH,))
            
    conn.commit()
    conn.close()

    # Restore from cloud after closing initial connection
    restore_db_from_cloud()

# ================= USER MANAGEMENT =================

def create_user(email, password_hash, full_name=None):
    try:
        conn = get_connection()
        user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        role = "admin" if (user_count == 0 or email.strip().lower() == "hakhoatg@gmail.com") else "user"
        
        cursor = conn.execute("""
            INSERT INTO users (email, password_hash, full_name, role, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (email.strip().lower(), password_hash, full_name or email.split('@')[0], role, datetime.datetime.now().isoformat()))
        conn.commit()
        user_id = cursor.lastrowid
        conn.close()
        trigger_cloud_sync()
        return True, user_id, "Đăng ký tài khoản thành công"
    except sqlite3.IntegrityError:
        return False, None, "Email này đã được sử dụng."
    except Exception as e:
        return False, None, str(e)


def restore_db_from_cloud():
    """Tải và khôi phục cơ sở dữ liệu từ Cloudinary nếu chưa có."""
    try:
        from src import cloudinary_storage
        backup_data = cloudinary_storage.download_db_backup()
        if backup_data and "users" in backup_data and len(backup_data["users"]) > 0:
            conn = get_connection()
            for u in backup_data.get("users", []):
                conn.execute("""
                    INSERT OR REPLACE INTO users (id, email, password_hash, full_name, role, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (u.get("id"), u.get("email"), u.get("password_hash"), u.get("full_name"), u.get("role", "user"), u.get("created_at")))
            
            for m in backup_data.get("meetings", []):
                conn.execute("""
                    INSERT OR REPLACE INTO meetings (id, user_id, room_name, audio_path, transcript, summary, summary_time_seconds, llm_summary, llm_summary_time_seconds, duration_seconds, language_confidence, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (m.get("id"), m.get("user_id", 1), m.get("room_name"), m.get("audio_path"), m.get("transcript"), m.get("summary"), m.get("summary_time_seconds"), m.get("llm_summary"), m.get("llm_summary_time_seconds"), m.get("duration_seconds"), m.get("language_confidence"), m.get("created_at")))
            conn.execute("UPDATE users SET password_hash = ?, role = 'admin' WHERE email = 'hakhoatg@gmail.com'", ("e2c3b63eb9c9ea53f45c1865b9c98ffb5588c1a7c9f47affb7b89e1078817d4c",))
            conn.commit()
            conn.close()
            print(f"[database] restore_db_from_cloud: Restored {len(backup_data.get('users', []))} users from Cloudinary.")
    except Exception as e:
        print(f"[database] restore_db_from_cloud error: {e}")


def get_user_by_email(email):
    email_clean = email.strip().lower()
    conn = get_connection()
    row = conn.execute("SELECT * FROM users WHERE email = ?", (email_clean,)).fetchone()
    conn.close()
    if not row:
        restore_db_from_cloud()
        conn = get_connection()
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email_clean,)).fetchone()
        conn.close()
    
    if row:
        user_dict = dict(row)
        if email_clean == "hakhoatg@gmail.com":
            DEFAULT_ADMIN_HASH = "e2c3b63eb9c9ea53f45c1865b9c98ffb5588c1a7c9f47affb7b89e1078817d4c"
            if user_dict.get("password_hash") != DEFAULT_ADMIN_HASH:
                try:
                    conn = get_connection()
                    conn.execute("UPDATE users SET password_hash = ?, role = 'admin' WHERE email = 'hakhoatg@gmail.com'", (DEFAULT_ADMIN_HASH,))
                    conn.commit()
                    conn.close()
                    user_dict["password_hash"] = DEFAULT_ADMIN_HASH
                    trigger_cloud_sync()
                except Exception as e:
                    print(f"[get_user_by_email fix admin error] {e}")
        return user_dict
    return None


def get_user_by_id(user_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_users():
    conn = get_connection()
    rows = conn.execute("""
        SELECT u.id, u.email, u.full_name, COALESCE(u.role, 'user') as role, u.created_at,
               COUNT(m.id) as meeting_count
        FROM users u
        LEFT JOIN meetings m ON u.id = m.user_id
        GROUP BY u.id
        ORDER BY u.id ASC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_user_role(target_user_id, new_role):
    try:
        conn = get_connection()
        conn.execute("UPDATE users SET role = ? WHERE id = ?", (new_role, target_user_id))
        conn.commit()
        conn.close()
        trigger_cloud_sync()
        return True, "Cập nhật quyền thành công"
    except Exception as e:
        return False, str(e)


def admin_delete_user(target_user_id):
    try:
        conn = get_connection()
        conn.execute("DELETE FROM meetings WHERE user_id = ?", (target_user_id,))
        conn.execute("DELETE FROM users WHERE id = ?", (target_user_id,))
        conn.commit()
        conn.close()
        trigger_cloud_sync()
        return True, "Đã xóa tài khoản thành công"
    except Exception as e:
        return False, str(e)


def update_user_password(user_id, password_hash):
    try:
        conn = get_connection()
        conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (password_hash, user_id))
        conn.commit()
        conn.close()
        trigger_cloud_sync()
        return True
    except Exception as e:
        print(f"[database update_user_password error] {e}")
        return False

# ================= MEETING MANAGEMENT =================

def insert_meeting(audio_path, transcript, summary, duration_seconds,
                    language_confidence, room_name="Phiên ghi âm chính",
                    summary_time_seconds=None, llm_summary=None,
                    llm_summary_time_seconds=None, user_id=1):
    conn = get_connection()
    cursor = conn.execute("""
        INSERT INTO meetings
            (user_id, room_name, audio_path, transcript, summary, summary_time_seconds,
             llm_summary, llm_summary_time_seconds, duration_seconds,
             language_confidence, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        user_id, room_name, audio_path, transcript, summary, summary_time_seconds,
        llm_summary, llm_summary_time_seconds, duration_seconds,
        language_confidence, datetime.datetime.now().isoformat()
    ))
    conn.commit()
    meeting_id = cursor.lastrowid
    conn.close()
    trigger_cloud_sync()

    try:
        reports_dir = os.path.join(config.DATA_DIR, "text_reports")
        os.makedirs(reports_dir, exist_ok=True)
        single_txt_path = os.path.join(reports_dir, f"CuocHop_{meeting_id}.txt")
        with open(single_txt_path, "w", encoding="utf-8") as f:
            f.write(f"CUỘC HỌP #{meeting_id}: {room_name}\n")
            f.write(f"Thời gian: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Thời lượng: {duration_seconds} giây\n")
            f.write(f"File ghi âm: {audio_path}\n")
            f.write("========================================================\n\n")
            f.write("📝 BIÊN BẢN HỘI THOẠI CHITIẾT:\n")
            f.write(f"{transcript or 'Chưa có nội dung.'}\n\n")
            f.write("🤖 BẢN TÓM TẮT AI:\n")
            f.write(f"{summary or 'Chưa có tóm tắt.'}\n")
    except Exception as e:
        print(f"Lỗi khi lưu file TXT tự động: {e}")

    return meeting_id


def get_all_meetings(user_id=None):
    conn = get_connection()
    if user_id is not None:
        rows = conn.execute("SELECT * FROM meetings WHERE user_id = ? ORDER BY created_at DESC", (user_id,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM meetings ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_meeting_by_id(meeting_id, user_id=None):
    conn = get_connection()
    if user_id is not None:
        row = conn.execute("SELECT * FROM meetings WHERE id = ? AND user_id = ?", (meeting_id, user_id)).fetchone()
    else:
        row = conn.execute("SELECT * FROM meetings WHERE id = ?", (meeting_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def search_meetings(keyword, user_id=None):
    conn = get_connection()
    like_pattern = f"%{keyword}%"
    if user_id is not None:
        rows = conn.execute("""
            SELECT * FROM meetings
            WHERE (user_id = ? OR user_id IS NULL) AND (transcript LIKE ? OR summary LIKE ? OR room_name LIKE ?)
            ORDER BY created_at DESC
        """, (user_id, like_pattern, like_pattern, like_pattern)).fetchall()
    else:
        rows = conn.execute("""
            SELECT * FROM meetings
            WHERE transcript LIKE ? OR summary LIKE ? OR room_name LIKE ?
            ORDER BY created_at DESC
        """, (like_pattern, like_pattern, like_pattern)).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def rename_meeting(meeting_id, new_name, user_id=None):
    try:
        meeting_id = int(meeting_id)
        conn = get_connection()
        if user_id is not None:
            row = conn.execute(
                "SELECT * FROM meetings WHERE id = ? AND (user_id = ? OR user_id IS NULL)",
                (meeting_id, user_id)
            ).fetchone()
        else:
            row = conn.execute("SELECT * FROM meetings WHERE id = ?", (meeting_id,)).fetchone()
            
        if not row:
            conn.close()
            return False, "Không tìm thấy phiên ghi âm hoặc bạn không có quyền đổi tên."
            
        conn.execute("UPDATE meetings SET room_name = ?, user_id = COALESCE(user_id, ?) WHERE id = ?", (new_name.strip(), user_id, meeting_id))
        conn.commit()
        conn.close()
        trigger_cloud_sync()
        return True, "Đổi tên thành công"
    except Exception as e:
        return False, str(e)


def delete_meeting(meeting_id, user_id=None):
    try:
        meeting_id = int(meeting_id)
        conn = get_connection()
        if user_id is not None:
            row = conn.execute(
                "SELECT * FROM meetings WHERE id = ? AND (user_id = ? OR user_id IS NULL)",
                (meeting_id, user_id)
            ).fetchone()
        else:
            row = conn.execute("SELECT * FROM meetings WHERE id = ?", (meeting_id,)).fetchone()
            
        if not row:
            conn.close()
            return False, "Không tìm thấy phiên ghi âm hoặc bạn không có quyền xóa."
        
        m_dict = dict(row)
        audio_path = m_dict.get("audio_path")

        if audio_path and audio_path.startswith("cloudinary:"):
            try:
                from src import cloudinary_storage
                cloudinary_storage.delete_audio(audio_path[len("cloudinary:"):])
            except Exception as e:
                print(f"[database] Cảnh báo xóa file trên Cloudinary: {e}")
        elif audio_path and os.path.exists(audio_path):
            try:
                os.remove(audio_path)
            except Exception as e:
                print(f"[database] Cảnh báo xóa file âm thanh: {e}")
                
        reports_dir = os.path.join(config.DATA_DIR, "text_reports")
        txt_path = os.path.join(reports_dir, f"CuocHop_{meeting_id}.txt")
        if os.path.exists(txt_path):
            try:
                os.remove(txt_path)
            except Exception as e:
                print(f"[database] Cảnh báo xóa file TXT: {e}")

        conn.execute("DELETE FROM meetings WHERE id = ?", (meeting_id,))
        conn.commit()
        conn.close()
        trigger_cloud_sync()
        return True, "Xóa thành công"
    except Exception as err:
        return False, str(err)

