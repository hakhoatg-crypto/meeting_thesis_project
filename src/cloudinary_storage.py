"""
Module: cloudinary_storage.py
Chức năng: Upload file âm thanh lên Cloudinary theo từng tài khoản (mỗi user một
"thư mục" riêng: users/{user_id}/audio/...), lưu ở chế độ PRIVATE (không public),
và tạo signed URL có thời hạn khi cần phát lại hoặc gửi cho AssemblyAI.

QUAN TRỌNG VỀ BẢO MẬT:
- API_SECRET chỉ được dùng ở backend (file này), KHÔNG BAO GIỜ gửi xuống Flutter
  app hay trình duyệt.
- Vì để type="private", ai có link secure_url mặc định KHÔNG xem/tải được nếu
  không có chữ ký hợp lệ - phải đi qua get_signed_playback_url() bên dưới.
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

_configured = False


def _ensure_configured():
    global _configured
    if _configured:
        return True
    if not (config.CLOUDINARY_CLOUD_NAME and config.CLOUDINARY_API_KEY and config.CLOUDINARY_API_SECRET):
        return False
    import cloudinary
    cloudinary.config(
        cloud_name=config.CLOUDINARY_CLOUD_NAME,
        api_key=config.CLOUDINARY_API_KEY,
        api_secret=config.CLOUDINARY_API_SECRET,
        secure=True,
    )
    _configured = True
    return True


def is_enabled() -> bool:
    """True nếu đã cấu hình đủ 3 biến Cloudinary trong .env."""
    return _ensure_configured()


def upload_audio(user_id, local_filepath: str, meeting_filename: str) -> str | None:
    """
    Upload 1 file âm thanh lên Cloudinary vào folder riêng của user_id.
    Trả về public_id (để lưu vào DB) hoặc None nếu Cloudinary chưa được cấu hình.
    File được để type="private" - không truy cập công khai được qua secure_url.
    """
    if not _ensure_configured():
        return None

    import cloudinary.uploader

    public_id = f"users/{user_id}/audio/{os.path.splitext(meeting_filename)[0]}"
    result = cloudinary.uploader.upload(
        local_filepath,
        resource_type="video",  # Cloudinary xếp audio vào nhóm "video"
        type="private",
        public_id=public_id,
        overwrite=True,
    )
    return result.get("public_id", public_id)


def get_signed_playback_url(public_id: str, expires_in_seconds: int = 300) -> str | None:
    """
    Sinh URL có chữ ký + thời hạn (mặc định 5 phút) để phát lại hoặc tải file
    private về xử lý (vd. gửi cho AssemblyAI). Hết hạn thì URL không dùng được nữa.
    """
    if not _ensure_configured():
        return None

    import time
    import cloudinary.utils

    url, _ = cloudinary.utils.cloudinary_url(
        public_id,
        resource_type="video",
        type="private",
        sign_url=True,
        secure=True,
        expires_at=int(time.time()) + expires_in_seconds,
    )
    return url


def delete_audio(public_id: str) -> bool:
    """Xóa file khỏi Cloudinary (dùng khi người dùng xóa phiên ghi âm)."""
    if not _ensure_configured():
        return False
    import cloudinary.uploader
    res = cloudinary.uploader.destroy(public_id, resource_type="video", type="private")
    return res.get("result") == "ok"


def upload_db_backup(data_dict: dict) -> bool:
    """Upload database backup JSON (users + meetings metadata) to Cloudinary."""
    if not _ensure_configured():
        return False
    try:
        import json
        import cloudinary.uploader
        payload = json.dumps(data_dict, ensure_ascii=False).encode('utf-8')
        cloudinary.uploader.upload(
            payload,
            resource_type="raw",
            public_id="backup/db_backup.json",
            overwrite=True,
        )
        return True
    except Exception as e:
        print(f"[cloudinary] DB backup error: {e}")
        return False


def download_db_backup() -> dict | None:
    """Download database backup JSON from Cloudinary."""
    if not _ensure_configured():
        return None
    try:
        import requests
        import cloudinary.utils
        url, _ = cloudinary.utils.cloudinary_url(
            "backup/db_backup.json",
            resource_type="raw",
            secure=True,
        )
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            data = res.json()
            print(f"[cloudinary] Successfully downloaded backup from Cloudinary: {len(data.get('users', []))} users")
            return data
        else:
            print(f"[cloudinary] Download backup returned status {res.status_code}")
    except Exception as e:
        print(f"[cloudinary] DB restore download error: {e}")
    return None


