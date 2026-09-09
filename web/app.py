#!/usr/bin/env python3
"""
web/app.py - Dashboard web AI Voice Studio với Đăng nhập & Quản lý Phân quyền Dữ liệu Cá nhân
"""

import os
import sys
import asyncio
import time
import uuid
import hashlib
import queue as pyqueue

if not hasattr(asyncio, "to_thread"):
    async def _to_thread(func, *args, **kwargs):
        import functools
        loop = asyncio.get_event_loop()
        pfunc = functools.partial(func, *args, **kwargs)
        return await loop.run_in_executor(None, pfunc)
    asyncio.to_thread = _to_thread

if not hasattr(asyncio, "create_task"):
    def _create_task(coro):
        return asyncio.ensure_future(coro)
    asyncio.create_task = _create_task

try:
    import websockets
    if not hasattr(websockets, "legacy"):
        import types
        _legacy = types.ModuleType("legacy")
        if hasattr(websockets, "handshake"):
            _legacy.handshake = websockets.handshake
        if hasattr(websockets, "http"):
            _legacy.http = websockets.http
        if hasattr(websockets, "server"):
            _legacy.server = websockets.server
        if hasattr(websockets, "framing"):
            _legacy.framing = websockets.framing
        websockets.legacy = _legacy
except Exception:
    pass


sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, Request, Query, WebSocket, WebSocketDisconnect, Header, HTTPException, Depends, UploadFile, File, Form
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

import config
from src import database

app = FastAPI(title="Hệ thống AI Voice Studio - Quản lý Phân quyền & Phiên ghi âm")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://meeting-studio-khoa.web.app", "http://localhost:8000", "http://127.0.0.1:8000"],
    allow_origin_regex=r"https?://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(CURRENT_DIR, "templates"))
app.mount("/static", StaticFiles(directory=os.path.join(CURRENT_DIR, "static")), name="static")

# ================= AUTHENTICATION & SESSION MANAGEMENT =================
# Bộ nhớ Session tạm thời (Ephemeral Session Storage) -> Xóa khi tắt app/browser
ACTIVE_SESSIONS: dict[str, dict] = {}
SESSION_TTL_SECONDS = 24 * 60 * 60  # session hết hạn sau 24h kể từ lúc đăng nhập

def hash_password(password: str) -> str:
    """Mã hóa mật khẩu bằng PBKDF2-HMAC-SHA256 chuẩn bảo mật."""
    salt = b"ai_voice_studio_salt_2026"
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000).hex()

def get_current_user_from_request(request: Request) -> dict | None:
    """Lấy thông tin User hiện tại từ Header Authorization, Cookie hoặc Query Parameter."""
    token = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
    
    if not token:
        token = request.headers.get("X-Session-Token")
    if not token:
        token = request.query_params.get("token")
    if not token:
        token = request.cookies.get("session_token")
        
    if token and token in ACTIVE_SESSIONS:
        session = ACTIVE_SESSIONS[token]
        created_at = session.get("_created_at", 0)
        if time.time() - created_at > SESSION_TTL_SECONDS:
            del ACTIVE_SESSIONS[token]
            return None
        return session
    return None


def require_authenticated_user(request: Request) -> dict:
    user = get_current_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="Phiên làm việc đã hết hạn. Vui lòng đăng nhập lại.")
    return user


def require_admin_user(request: Request) -> dict:
    user = require_authenticated_user(request)
    db_user = database.get_user_by_id(user["id"])
    if not db_user or db_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Bạn không có quyền Admin để thực hiện thao tác này.")
    return db_user

# ================= AUTH API ENDPOINTS =================

@app.post("/api/auth/register")
async def register(request: Request):
    try:
        data = await request.json()
        email = data.get("email", "").strip()
        password = data.get("password", "")
        full_name = data.get("full_name", "").strip()

        if not email or not password:
            return JSONResponse({"ok": False, "error": "Vui lòng nhập đầy đủ Email và Mật khẩu."}, status_code=400)
            
        pass_hash = hash_password(password)
        ok, user_id, msg = database.create_user(email, pass_hash, full_name)
        if not ok:
            return JSONResponse({"ok": False, "error": msg}, status_code=400)
            
        created_user = database.get_user_by_id(user_id)
        role = created_user.get("role", "user") if created_user else "user"
        
        # Tạo Session Token mới
        token = uuid.uuid4().hex
        user_data = {"id": user_id, "email": email, "full_name": full_name or email.split('@')[0], "role": role}
        ACTIVE_SESSIONS[token] = {**user_data, "_created_at": time.time()}
        
        return {"ok": True, "message": "Đăng ký tài khoản thành công!", "token": token, "user": user_data}
    except Exception as e:
        print(f"[app register error] {e}")
        return JSONResponse({"ok": False, "error": f"Lỗi đăng ký: {e}"}, status_code=500)


@app.post("/api/auth/login")
async def login(request: Request):
    try:
        data = await request.json()
        email = data.get("email", "").strip()
        password = data.get("password", "")

        if not email or not password:
            return JSONResponse({"ok": False, "error": "Vui lòng nhập Email và Mật khẩu."}, status_code=400)

        user = database.get_user_by_email(email)
        if not user:
            return JSONResponse({"ok": False, "error": "Email hoặc mật khẩu không chính xác."}, status_code=401)

        stored_hash = user["password_hash"]
        current_hash = hash_password(password)

        valid = (stored_hash == current_hash)

        if not valid:
            return JSONResponse({"ok": False, "error": "Email hoặc mật khẩu không chính xác."}, status_code=401)

        # Tạo Session Token mới
        token = uuid.uuid4().hex
        role = user.get("role", "user") or "user"
        user_data = {"id": user["id"], "email": user["email"], "full_name": user.get("full_name") or email.split('@')[0], "role": role}
        ACTIVE_SESSIONS[token] = {**user_data, "_created_at": time.time()}

        return {"ok": True, "message": "Đăng nhập thành công!", "token": token, "user": user_data}
    except Exception as e:
        print(f"[app login error] {e}")
        return JSONResponse({"ok": False, "error": f"Lỗi đăng nhập: {e}"}, status_code=500)


@app.post("/api/auth/logout")
async def logout(request: Request):
    token = request.headers.get("X-Session-Token") or request.cookies.get("session_token")
    if token and token in ACTIVE_SESSIONS:
        del ACTIVE_SESSIONS[token]
    return {"ok": True, "message": "Đã đăng xuất thành công!"}


@app.get("/api/auth/me")
async def get_me(request: Request):
    user = get_current_user_from_request(request)
    if user:
        db_user = database.get_user_by_id(user["id"])
        if db_user:
            user["role"] = db_user.get("role", "user")
        return {"authenticated": True, "user": user}
    return {"authenticated": False}


# ================= ADMIN MANAGEMENT ENDPOINTS =================

@app.get("/api/admin/users")
async def admin_get_users(request: Request):
    require_admin_user(request)
    users = database.get_all_users()
    return {"ok": True, "users": users}


@app.post("/api/admin/users/role")
async def admin_change_user_role(request: Request):
    require_admin_user(request)
    data = await request.json()
    target_id = data.get("user_id")
    new_role = data.get("role", "user")
    if not target_id or new_role not in ["admin", "user"]:
        return JSONResponse({"ok": False, "error": "Dữ liệu không hợp lệ."}, status_code=400)
    ok, msg = database.update_user_role(target_id, new_role)
    if ok:
        return {"ok": True, "message": msg}
    return JSONResponse({"ok": False, "error": msg}, status_code=400)


@app.post("/api/admin/users/reset-password")
async def admin_reset_user_password(request: Request):
    require_admin_user(request)
    data = await request.json()
    target_id = data.get("user_id")
    new_password = data.get("password", "").strip()
    if not target_id or len(new_password) < 4:
        return JSONResponse({"ok": False, "error": "Mật khẩu phải có ít nhất 4 ký tự."}, status_code=400)
    pass_hash = hash_password(new_password)
    ok = database.update_user_password(target_id, pass_hash)
    if ok:
        return {"ok": True, "message": "Đặt lại mật khẩu thành công!"}
    return JSONResponse({"ok": False, "error": "Lỗi khi đổi mật khẩu."}, status_code=400)


@app.post("/api/admin/users/delete")
async def admin_delete_user_endpoint(request: Request):
    current_admin = require_admin_user(request)
    data = await request.json()
    target_id = data.get("user_id")
    if target_id == current_admin["id"]:
        return JSONResponse({"ok": False, "error": "Không thể xóa chính tài khoản Admin đang đăng nhập."}, status_code=400)
    ok, msg = database.admin_delete_user(target_id)
    if ok:
        return {"ok": True, "message": msg}
    return JSONResponse({"ok": False, "error": msg}, status_code=400)

# ================= BACKGROUND REALTIME PIPELINE =================
pipeline = None
pipeline_event_queue: "pyqueue.Queue" = pyqueue.Queue()
screen_connections: list = []


async def _broadcast_loop():
    while True:
        event = await asyncio.to_thread(pipeline_event_queue.get)
        for ws in list(screen_connections):
            try:
                await ws.send_json(event)
            except Exception:
                if ws in screen_connections:
                    screen_connections.remove(ws)


@app.on_event("startup")
async def startup():
    database.init_db()

    global pipeline
    try:
        from src.live_meeting_pipeline import MeetingPipeline
        pipeline = MeetingPipeline(pipeline_event_queue)
        print("[web/app] MeetingPipeline san sang.")
    except Exception as e:
        print(f"[web/app] Bo qua MeetingPipeline: {e}")
        pipeline = None

    asyncio.create_task(_broadcast_loop())


@app.websocket("/ws/meeting-screen")
@app.websocket("/ws/live-transcribe")
async def websocket_meeting_screen(websocket: WebSocket, token: str = Query(default="")):
    await websocket.accept()
    screen_connections.append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in screen_connections:
            screen_connections.remove(websocket)
    except Exception:
        if websocket in screen_connections:
            screen_connections.remove(websocket)


@app.post("/api/meeting/start")
@app.post("/api/meetings/start")
async def start_meeting_endpoint(request: Request):
    user = get_current_user_from_request(request)
    if pipeline:
        try:
            pipeline.start(user_id=(user["id"] if user else None))
            return {"ok": True, "message": "Bắt đầu cuộc họp mới thành công!"}
        except Exception as e:
            return JSONResponse({"ok": False, "error": f"Lỗi khởi chạy cuộc họp: {e}"}, status_code=500)
    return {"ok": True, "message": "Đã bắt đầu cuộc họp!"}


@app.post("/api/meeting/stop")
@app.post("/api/meetings/stop")
async def stop_meeting_endpoint(request: Request):
    user = get_current_user_from_request(request)
    if pipeline:
        try:
            pipeline.stop()
            return {"ok": True, "message": "Đã dừng cuộc họp!"}
        except Exception as e:
            return JSONResponse({"ok": False, "error": f"Lỗi dừng cuộc họp: {e}"}, status_code=500)
    return {"ok": True, "message": "Đã dừng cuộc họp!"}

# ================= WEB PAGES & RECORDING APIS =================

@app.get("/", response_class=HTMLResponse)
def index(request: Request, q: str = Query(default="")):
    user = get_current_user_from_request(request)
    user_id = user["id"] if user else None
    
    if user_id:
        meetings = database.search_meetings(q, user_id=user_id) if q else database.get_all_meetings(user_id=user_id)
    else:
        meetings = []

    return templates.TemplateResponse("index.html", {
        "request": request,
        "meetings": meetings,
        "query": q,
        "user": user,
    })


@app.get("/api/meetings")
def get_meetings_json(request: Request, q: str = Query(default="")):
    user = require_authenticated_user(request)
    user_id = user["id"]
    if q:
        return database.search_meetings(q, user_id=user_id)
    return database.get_all_meetings(user_id=user_id)


@app.get("/meeting/{meeting_id}", response_class=HTMLResponse)
def meeting_detail(request: Request, meeting_id: int):
    user = get_current_user_from_request(request)
    user_id = user["id"] if user else None
    meeting = database.get_meeting_by_id(meeting_id, user_id=user_id)
    return templates.TemplateResponse("detail.html", {
        "request": request,
        "meeting": meeting,
        "user": user,
    })


@app.get("/audio/{meeting_id}")
def get_audio(request: Request, meeting_id: int):
    user = get_current_user_from_request(request)
    user_id = user["id"] if user else None
    meeting = database.get_meeting_by_id(meeting_id, user_id=user_id)
    if not meeting:
        return JSONResponse({"error": "Không tìm thấy file âm thanh hoặc không có quyền truy cập."}, status_code=404)

    audio_ref = meeting["audio_path"]
    if isinstance(audio_ref, str) and audio_ref.startswith("cloudinary:"):
        from src import cloudinary_storage
        public_id = audio_ref[len("cloudinary:"):]
        signed_url = cloudinary_storage.get_signed_playback_url(public_id, expires_in_seconds=300)
        if signed_url:
            return RedirectResponse(signed_url)
        return JSONResponse({"error": "Không tạo được URL phát lại."}, status_code=500)

    if os.path.exists(audio_ref):
        return FileResponse(audio_ref, media_type="audio/wav")
    return JSONResponse({"error": "Không tìm thấy file âm thanh hoặc không có quyền truy cập."}, status_code=404)


@app.post("/api/meeting/rename/{meeting_id}")
async def rename_meeting_endpoint(request: Request, meeting_id: int):
    user = require_authenticated_user(request)
    data = await request.json()
    new_name = data.get("room_name", "").strip()
    if not new_name:
        return JSONResponse({"ok": False, "error": "Tên phiên ghi âm không được để trống."}, status_code=400)
        
    ok, msg = database.rename_meeting(meeting_id, new_name, user_id=user["id"])
    if ok:
        return {"ok": True, "message": "Đã đổi tên phiên ghi âm thành công!"}
    return JSONResponse({"ok": False, "error": msg}, status_code=400)


@app.post("/api/meeting/delete/{meeting_id}")
@app.delete("/api/meeting/delete/{meeting_id}")
def delete_meeting_endpoint(request: Request, meeting_id: int):
    user = require_authenticated_user(request)
    ok, msg = database.delete_meeting(meeting_id, user_id=user["id"])
    if ok:
        return {"ok": True, "message": f"Đã xóa phiên ghi âm #{meeting_id} thành công!"}
    return JSONResponse({"ok": False, "error": msg}, status_code=400)


@app.get("/screen", response_class=HTMLResponse)
def screen_page(request: Request):
    user = get_current_user_from_request(request)
    return templates.TemplateResponse("screen.html", {
        "request": request,
        "pipeline_ready": pipeline is not None,
        "user": user,
    })


@app.post("/api/meeting/save_browser_recording")
async def save_browser_recording(request: Request, file: UploadFile = File(...), room_name: str = Form("Phiên ghi âm mới")):
    import time
    import datetime
    
    user = get_current_user_from_request(request)
    if not user:
        return JSONResponse({"ok": False, "error": "Phiên làm việc đã hết hạn. Vui lòng đăng nhập lại."}, status_code=401)
    user_id = user["id"]

    if not file:
        return JSONResponse({"ok": False, "error": "Khong nhan duoc file audio."}, status_code=400)

    user_audio_dir = os.path.join(config.AUDIO_DIR, f"user_{user_id}")
    os.makedirs(user_audio_dir, exist_ok=True)

    start_time = datetime.datetime.now()
    filename = start_time.strftime("recording_%Y%m%d_%H%M%S.wav")
    filepath = os.path.join(user_audio_dir, filename)

    contents = await file.read()
    with open(filepath, "wb") as f:
        f.write(contents)

    duration_sec = 0.0
    try:
        import wave
        with wave.open(filepath, "rb") as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            duration_sec = frames / float(rate)
    except Exception:
        duration_sec = len(contents) / (16000 * 2)

    transcript = ""
    confidence = 1.0
    summary = ""
    summary_time = 0.0
    llm_summary_text = None
    llm_summary_time = None

    if getattr(config, "USE_ASSEMBLYAI", False):
        try:
            from src.assemblyai_transcriber import AssemblyAIBatchTranscriber
            aai_trans = AssemblyAIBatchTranscriber()
            trans_res = aai_trans.transcribe(filepath)
            transcript = trans_res.get("text", "")
            confidence = trans_res.get("language_probability", 1.0)
        except Exception as e:
            print(f"[app] Loi AssemblyAI Transcribe: {e}")

    # Đẩy file lên Cloudinary (workspace riêng theo user_id), nếu đã cấu hình.
    # Nếu chưa cấu hình (thiếu biến .env) thì giữ nguyên hành vi cũ: lưu local.
    from src import cloudinary_storage
    stored_audio_ref = filepath
    if cloudinary_storage.is_enabled():
        try:
            public_id = cloudinary_storage.upload_audio(user_id, filepath, filename)
            if public_id:
                stored_audio_ref = f"cloudinary:{public_id}"
                os.remove(filepath)  # không giữ bản sao trên ổ đĩa nữa
        except Exception as e:
            print(f"[app] Loi upload Cloudinary, giu file local: {e}")

    meeting_id = database.insert_meeting(
        audio_path=stored_audio_ref,
        transcript=transcript,
        summary=summary or transcript[:250],
        summary_time_seconds=summary_time,
        llm_summary=llm_summary_text,
        llm_summary_time_seconds=llm_summary_time,
        duration_seconds=duration_sec,
        language_confidence=confidence,
        room_name=room_name,
        user_id=user_id,
    )

    return {
        "ok": True,
        "meeting_id": meeting_id,
        "room_name": room_name,
        "duration_seconds": duration_sec,
        "transcript": transcript,
        "summary": summary or transcript[:250],
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", getattr(config, "WEB_PORT", 8000)))
    uvicorn.run("web.app:app", host="0.0.0.0", port=port, reload=False)
