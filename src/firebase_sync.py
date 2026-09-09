"""
Module: firebase_sync.py
Chức năng: Tự động đồng bộ dữ liệu cuộc họp (bản tóm tắt, transcript, metadata, file âm thanh)
từ Jetson Nano lên Firebase Cloud (Firestore Database & Storage).

Nếu chưa cài firebase-admin hoặc chưa có file serviceAccountKey.json, mô-đun sẽ
báo log cảnh báo và bỏ qua an toàn - KHÔNG HỂ LÀM SẬP hệ thống local.
"""

import os
import sys
import time
import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

_firebase_initialized = False
_db = None
_bucket = None

def init_firebase():
    global _firebase_initialized, _db, _bucket
    if _firebase_initialized:
        return True

    cred_path = os.environ.get("FIREBASE_CREDENTIALS_PATH", os.path.join(config.BASE_DIR, "serviceAccountKey.json"))
    storage_bucket = os.environ.get("FIREBASE_STORAGE_BUCKET", "")

    if not os.path.exists(cred_path):
        return False

    try:
        import firebase_admin
        from firebase_admin import credentials, firestore, storage

        if not firebase_admin._apps:
            cred = credentials.Certificate(cred_path)
            opts = {}
            if storage_bucket:
                opts['storageBucket'] = storage_bucket
            firebase_admin.initialize_app(cred, opts if opts else None)

        _db = firestore.client()
        if storage_bucket:
            _bucket = storage.bucket()
        _firebase_initialized = True
        print("[FirebaseSync] [+] Đã kết nối Firebase Cloud Firestore thành công!")
        return True
    except Exception as e:
        print(f"[FirebaseSync] Lỗi khởi tạo Firebase: {e}")
        return False


def sync_meeting(meeting_data: dict) -> bool:
    """
    Đồng bộ 1 cuộc họp lên Firebase.
    meeting_data dict gồm:
        - meeting_id
        - room_name
        - duration_seconds
        - transcript
        - summary
        - llm_summary
        - audio_path
        - created_at
    """
    if not init_firebase():
        return False

    try:
        meeting_id = meeting_data.get("meeting_id")
        audio_path = meeting_data.get("audio_path", "")
        audio_url = ""

        # Khong upload audio len Firebase Storage de tiet kiem chi phi 100%
        # File audio WAV duoc luu cu cuc bo tren o cung (data/audio/)
        audio_url = f"/audio/{meeting_id}"

        from src.summarizer import Summarizer
        sum_engine = Summarizer()

        transcript = meeting_data.get("transcript", "")
        duration = meeting_data.get("duration_seconds", 0)

        action_items = meeting_data.get("action_items") or sum_engine.extract_action_items(transcript)
        keywords = meeting_data.get("keywords") or sum_engine.extract_keywords(transcript)
        sentiment = meeting_data.get("sentiment") or sum_engine.extract_sentiment(transcript)
        segments = meeting_data.get("segments") or sum_engine.segment_timestamps(transcript, duration)

        from firebase_admin import firestore
        doc_ref = _db.collection("meetings").document(str(meeting_id))
        doc_data = {
            "id": meeting_id,
            "room_name": meeting_data.get("room_name", "Phòng họp"),
            "duration_seconds": duration,
            "transcript": transcript,
            "summary": meeting_data.get("summary", ""),
            "llm_summary": meeting_data.get("llm_summary", ""),
            "action_items": action_items,
            "keywords": keywords,
            "sentiment": sentiment,
            "segments": segments,
            "audio_url": audio_url,
            "created_at": meeting_data.get("created_at") or datetime.datetime.now().isoformat(),
            "updated_at": firestore.SERVER_TIMESTAMP if _db else datetime.datetime.now().isoformat(),
            "source_device": "Jetson Nano Server",
        }
        doc_ref.set(doc_data, merge=True)
        print(f"[FirebaseSync] [+] Đã đồng bộ Cuộc họp #{meeting_id} (kèm Action Items, Keywords, Sentiment) lên Firebase!")
        return True
    except Exception as e:
        print(f"[FirebaseSync] Lỗi đồng bộ cuộc họp #{meeting_data.get('meeting_id')}: {e}")
        return False
