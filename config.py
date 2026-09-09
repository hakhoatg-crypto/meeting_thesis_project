"""
File cau hinh trung tam cho toan bo he thong.
Chinh sua cac gia tri o day de tuy chinh hanh vi he thong ma khong can sua code o cac file khac.
"""

import os

# Nap cac bien tu file .env (neu co) - KHONG commit file .env len Git.
# Xem file .env.example de biet cac bien can khai bao.
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ============ DUONG DAN THU MUC ============
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Du lieu tach cau cho NLTK/sumy (dung trong summarizer.py) da duoc dong goi SAN
# trong thu muc nltk_data/ cua chinh du an nay - KHONG can tai tu Internet, dam
# bao he thong chay dung nghia "offline" tren thiet bi khong co mang (Jetson Nano).
os.environ.setdefault("NLTK_DATA", os.path.join(BASE_DIR, "nltk_data"))
DATA_DIR = os.path.join(BASE_DIR, "data")
AUDIO_DIR = os.path.join(DATA_DIR, "audio")
DATABASE_PATH = os.path.join(DATA_DIR, "meetings.db")

os.makedirs(AUDIO_DIR, exist_ok=True)

# ============ CAU HINH GHI AM (VAD) ============
SAMPLE_RATE = 16000                # tan so lay mau am thanh (Hz)
FRAME_DURATION_MS = 30             # do dai moi frame VAD xu ly (10, 20 hoac 30 ms)
VAD_AGGRESSIVENESS = 2             # do nhay VAD: 0 (it nhay) -> 3 (rat nhay)
SILENCE_TIMEOUT_SECONDS = 5        # im lang lien tuc bao nhieu giay thi tu dong dung ghi
MIC_DEVICE_INDEX = None            # None = dung mic mac dinh; hoac dien so index cu the

# ============ CAU HINH SPEECH-TO-TEXT CHO CUOC HOP CHINH (AssemblyAI - cloud) ============
# Doi tu Whisper/Vosk local sang AssemblyAI: chinh xac hon nhieu, co streaming
# that (khong can 2 nhanh Vosk+Whisper song song nua), NHUNG bat buoc phai co
# Internet on dinh trong suot cuoc hop va tinh phi theo thoi gian ket noi.
# Dang ky lay API key tai https://www.assemblyai.com/ , dien vao file .env
# (bien ASSEMBLYAI_API_KEY) - KHONG dien truc tiep vao day.
ASSEMBLYAI_API_KEY = os.environ.get("ASSEMBLYAI_API_KEY", "")
ASSEMBLYAI_LANGUAGE_CODE = os.environ.get("ASSEMBLYAI_LANGUAGE_CODE", "vi")
# True = dung AssemblyAI cho ca cuoc hop chinh; False = quay lai Whisper local cu.
USE_ASSEMBLYAI = bool(ASSEMBLYAI_API_KEY)

# ============ CAU HINH SPEECH-TO-TEXT DU PHONG (PhoWhisper VinAI / Whisper - local) ============
# Chi con dung khi USE_ASSEMBLYAI = False (chua co ASSEMBLYAI_API_KEY), de code
# van chay duoc offline nhu ban goc neu chua muon tra phi dich vu cloud.
WHISPER_MODEL_SIZE = "vinai/phowhisper-small" # "vinai/phowhisper-small" / "vinai/phowhisper-medium" / "medium" / "large-v3"
WHISPER_DEVICE = "cpu"             # "cpu" hoac "cuda" (neu co GPU NVIDIA)
WHISPER_COMPUTE_TYPE = "int8"      # int8 (nhanh) / float32 (chinh xac hon, cham hon)
WHISPER_LANGUAGE = "vi"            # ma ngon ngu tieng Viet

# ============ CAU HINH VOSK (CHI dung cho che do CHO nghe lenh "Bat dau cuoc hop") ============
# Van giu Vosk (nho, mien phi, chay local) rieng cho voice_trigger.py vi no phai
# lang nghe LIEN TUC 24/7 khi chua co cuoc hop nao - neu dung AssemblyAI (tra phi
# theo thoi gian ket noi) cho viec nay se rat ton kem. Sau khi nghe duoc lenh
# "Bat dau cuoc hop", pipeline chinh moi chuyen sang dung AssemblyAI o tren.
VOSK_MODEL_PATH = os.path.join(BASE_DIR, "models", "vosk-model-vn")

# ============ CAU HINH PIPELINE HOP NHAT (man hinh phong hop) ============
# Neu CA cuoc hop im lang lien tuc qua bao nhieu giay thi TU DONG ket thuc va
# tom tat (backup cho truong hop quen bam nut "Ket thuc hop"). Dat None de tat
# tinh nang nay va chi ket thuc bang cach bam nut thu cong.
MEETING_AUTO_END_SILENCE_SECONDS = 60

# ============ CAU HINH TOM TAT (TextRank) ============
SUMMARY_SENTENCE_COUNT = 5         # so cau giu lai trong ban tom tat

# ============ CAU HINH TOM TAT BANG LLM (De so sanh) ============
# KHONG dien API key truc tiep vao day. Tao file ".env" (copy tu ".env.example")
# o thu muc goc du an va dien OPENAI_API_KEY vao do - file .env da duoc liet ke
# trong .gitignore nen se khong bao gio bi day nham len Git/chia se cong khai.
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
LLM_SUMMARY_MODEL = os.environ.get("LLM_SUMMARY_MODEL", "gpt-4o-mini")
# Tu dong bat neu co OPENAI_API_KEY hop le, tru khi ENABLE_LLM_SUMMARY=false trong .env
ENABLE_LLM_SUMMARY = bool(OPENAI_API_KEY) and os.environ.get("ENABLE_LLM_SUMMARY", "true").lower() != "false"

# ============ CAU HINH BAO MAT API (Dashboard/App doc du lieu cuoc hop) ============
# Khoa API don gian de bao ve cac endpoint dieu khien/doc du lieu cuoc hop.
# Dat trong file .env: API_AUTH_TOKEN=mot-chuoi-bi-mat-dai-va-kho-doan
# Neu de trong, he thong se CANH BAO ra console va chay o che do KHONG BAO VE
# (chi phu hop khi test noi bo, KHONG duoc dung khi trien khai that).
API_AUTH_TOKEN = os.environ.get("API_AUTH_TOKEN", "")

# Danh sach domain duoc phep goi API tu trinh duyet/app (CORS). Vi du:
# ALLOWED_ORIGINS=https://app-cua-cong-ty.com,https://admin.cong-ty.com
# KHONG dung "*" (cho phep tat ca) khi da co du lieu cuoc hop that.
_origins_env = os.environ.get("ALLOWED_ORIGINS", "")
ALLOWED_ORIGINS = [o.strip() for o in _origins_env.split(",") if o.strip()] or ["*"]


# ============ CAU HINH LUU TRU CLOUDINARY (moi tai khoan mot folder rieng) ============
# Lay 3 gia tri nay tai Dashboard Cloudinary sau khi dang ky - dien vao file .env,
# KHONG dien truc tiep vao day. Neu de trong, he thong tu dong quay ve luu file
# audio tren o dia local nhu truoc (xem web/app.py).
CLOUDINARY_CLOUD_NAME = os.environ.get("CLOUDINARY_CLOUD_NAME", "")
CLOUDINARY_API_KEY = os.environ.get("CLOUDINARY_API_KEY", "")
CLOUDINARY_API_SECRET = os.environ.get("CLOUDINARY_API_SECRET", "")

# ============ CAU HINH WEB DASHBOARD ============
WEB_HOST = "0.0.0.0"
WEB_PORT = 8000
