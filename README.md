# He thong Ghi am va Tom tat Bien ban Cuoc hop Tu dong

Do an tot nghiep - Ung dung cong nghe AI nhan dien giong noi (Speech Recognition)
tren thiet bi nhung Jetson Nano, ket hop xu ly ngon ngu tu nhien (NLP) de tu dong
tao bien ban cuoc hop tieng Viet.

## Kien truc he thong

```
Microphone → [1] AudioRecorder (VAD tu dong phat hien noi/im lang)
                    ↓ file .wav
             [2] Transcriber (Whisper offline - am thanh → van ban)
                    ↓ text
             [3] Summarizer (TextRank - tom tat van ban)
                    ↓ summary
             [4] Database (SQLite - luu tru)
                    ↓
             [5] Web Dashboard (FastAPI - xem lai lich su)
```

## Cong nghe su dung

| Thanh phan | Cong nghe | Ly do chon |
|---|---|---|
| Phat hien tieng noi | WebRTC VAD | Nhe, real-time, khong can GPU |
| Nhan dien giong noi | faster-whisper (Whisper) | Do chinh xac cao cho tieng Viet, chay offline mien phi |
| Tom tat van ban | TextRank (sumy) | Thuat toan kinh dien, khong can API tra phi, de giai thich khoa hoc |
| Luu tru | SQLite | Nhe, khong can cai server database rieng |
| Giao dien web | FastAPI + Jinja2 | Nhanh, don gian, du de lam demo |
| Danh gia | WER (jiwer) | Thuoc do chuan trong nghien cuu ASR |

## Cai dat

```bash
pip install -r requirements.txt
```

**QUAN TRONG:** cai dung version ghim trong `requirements.txt` (khong dung `pip install -U`
de tu y nang cap fastapi/jinja2/starlette len ban moi nhat), vi cac ban moi hon co the
doi API `TemplateResponse` va lam sap trang `/`, `/live`, `/screen` (loi
`TypeError: unhashable type: 'dict'`).

Neu gap loi OpenMP tren Windows, chay them lenh sau truoc khi chay chuong trinh:
```bash
set KMP_DUPLICATE_LIB_OK=TRUE          (Command Prompt)
$env:KMP_DUPLICATE_LIB_OK="TRUE"       (PowerShell)
```
(Cac file main.py va evaluate.py da tu dong xu ly loi nay san, khong bat buoc phai
chay lenh tren tay.)

### Cau hinh bao mat (bat buoc truoc khi dung du lieu cuoc hop that)

1. Copy `.env.example` thanh `.env` (cung thu muc voi `config.py`):
   ```bash
   cp .env.example .env
   ```
2. Dien vao `.env`:
   - `API_AUTH_TOKEN`: mot chuoi bi mat dai, ngau nhien (vi du chay
     `python -c "import secrets; print(secrets.token_hex(32))"` de tao). App Flutter
     phai duoc build voi cung gia tri nay (`--dart-define=API_KEY=...`).
   - `ALLOWED_ORIGINS`: domain that cua app/web client duoc phep goi API, cach nhau
     boi dau phay. KHONG de trong hoac dung domain ngrok mien phi cho moi truong that.
   - `OPENAI_API_KEY` (tuy chon): chi dien neu muon bat tinh nang so sanh tom tat LLM.
3. File `.env` da nam trong `.gitignore` - se khong bao gio bi day len Git.

Neu bo qua buoc nay, he thong van chay duoc (de tien test noi bo) nhung se in
canh bao ra console va KHONG bao ve cac endpoint dieu khien/doc du lieu cuoc hop.

### Ghi chu ve NLTK (tach cau cho module tom tat)

Du lieu tach cau (`punkt_tab`) da duoc dong goi san trong thu muc `nltk_data/` cua
chinh du an nay - **khong can Internet** de chay `summarizer.py`, dam bao dung
tinh than "offline" cho thiet bi nhu Jetson Nano khong co mang.

## Cach chay

### 1. Chay he thong ghi am + xu ly chinh
```bash
python main.py
```
He thong se tu dong lang nghe microphone, ghi am khi co nguoi noi, tu dung khi
im lang, roi tu dong chuyen thanh van ban va tom tat.

### 2. Chay Dashboard xem lai lich su
Mo mot cua so terminal khac (de main.py van chay ngam):
```bash
python web/app.py
```
Sau do mo trinh duyet, truy cap: http://localhost:8000

### 3. Danh gia do chinh xac (WER)
```bash
python evaluate.py
```
Xem huong dan chuan bi du lieu kiem thu trong phan "Danh gia" ben duoi.

## Cau truc thu muc

```
meeting_thesis_project/
├── config.py                  # Cau hinh trung tam
├── main.py                    # Diem khoi dau - chay pipeline chinh
├── evaluate.py                 # Danh gia do chinh xac (WER)
├── requirements.txt
├── src/
│   ├── audio_recorder.py      # Module 1: Ghi am tu dong (VAD)
│   ├── transcriber.py         # Module 2: Speech-to-Text (Whisper)
│   ├── summarizer.py          # Module 3: Tom tat (TextRank)
│   └── database.py            # Module 4: Luu tru (SQLite)
├── web/
│   ├── app.py                 # Module 5: Web Dashboard (FastAPI)
│   ├── templates/              # Giao dien HTML
│   └── static/                 # CSS
├── data/                        # Du lieu sinh ra khi chay (audio, database)
└── test_data/                   # Du lieu mau de danh gia WER (tu chuan bi)
```

## Speech-to-Text: AssemblyAI (cloud) vs Vosk+Whisper (local) - 2 CHE DO chon 1

Ban dau do an dung kien truc hybrid local (Vosk cho live caption + Whisper cho
bien ban chinh xac). He thong hien ho tro THEM 1 lua chon: **AssemblyAI**
(dich vu cloud) - 1 luong duy nhat vua tra chu ngay lap tuc vua la ban ghi
chinh xac cuoi cung, khong can 2 mo hinh song song nua.

Chon che do bang co dien `ASSEMBLYAI_API_KEY` trong file `.env` hay khong:

| | AssemblyAI (co dien API key) | Vosk + Whisper (de trong) |
|---|---|---|
| Do chinh xac | Cao hon dang ke | Trung binh (tuy chat luong mic) |
| Can Internet? | **Bat buoc, lien tuc** trong luc hop | Khong - chay offline hoan toan |
| Chi phi | Tinh phi theo thoi gian ket noi | Mien phi |
| Kien truc | 1 luong streaming duy nhat | 2 luong song song (Vosk + Whisper) |
| Phu hop khi | Uu tien do chinh xac, co Internet on dinh | Thiet bi edge khong co mang (vd Jetson Nano o vung khong co Internet) |

**Luu y:** module `voice_trigger.py` (nghe lenh "Bat dau cuoc hop" luc CHUA hop)
luon dung Vosk du o che do nao, vi no phai lang nghe LIEN TUC 24/7 - dung dich
vu tra phi cho viec nay se rat ton kem. AssemblyAI (neu bat) chi duoc dung SAU
KHI cuoc hop da bat dau.

### Cai dat AssemblyAI (khuyen dung neu co Internet on dinh)

1. Dang ky tai https://www.assemblyai.com/ (co goi mien phi de test)
2. Lay API key trong trang Dashboard cua AssemblyAI
3. Dien vao file `.env`: `ASSEMBLYAI_API_KEY=key-cua-ban`
4. Chay lai `python web/app.py` - se thay log
   `[MeetingPipeline] Che do: AssemblyAI (cloud) - can Internet on dinh.`

### Cai dat Vosk cho che do local/offline (khong dien ASSEMBLYAI_API_KEY)

1. Tai model tieng Viet tai: https://alphacephei.com/vosk/models
   (tim dong "vn" - Vietnamese, khuyen nghi ban "vosk-model-vn-0.4" ~1.4GB cho
   do chinh xac tot, hoac ban nho hon neu can toc do)
2. Giai nen, doi ten thu muc thanh `vosk-model-vn`, dat vao: `models/vosk-model-vn/`
   (tao thu muc `models/` trong thu muc goc du an neu chua co)
3. Cau truc dung phai la: `meeting_thesis_project/models/vosk-model-vn/am/final.mdl`
   (co file .mdl ben trong, khong phai giai nen thua 1 lop thu muc)

### Chay Live Caption (trang /live, dung mic trinh duyet)

```bash
python web/app.py
```
Mo trinh duyet, vao: http://localhost:8000/live
Bam nut "Bat dau noi", trinh duyet se xin quyen dung microphone - bam Allow/Cho phep.
Noi vao mic, chu se tu dong hien ra ngay ben duoi. Endpoint `/ws/live-transcribe`
tu dong chon AssemblyAI hoac Vosk theo cau hinh `.env` da neu tren.

### Kien truc ky thuat (che do AssemblyAI)

```
Trinh duyet (JS bat mic qua Web Audio API)
        ↓ gui tung khoi am thanh nho qua WebSocket
FastAPI WebSocket endpoint (/ws/live-transcribe)
        ↓
AssemblyAILiveSession (src/assemblyai_transcriber.py)
        ↓ gui am thanh qua Internet len AssemblyAI Streaming API
        ↓ nhan ve ket qua "Turn" (partial khi dang noi, final khi het cau)
Trinh duyet hien chu ngay len man hinh
```

## Danh gia do chinh xac (Chuong "Thuc nghiem" trong bao cao)

De co so lieu dinh luong dua vao bao cao do an:

1. Ghi am 3-5 doan noi mau (moi doan 30 giay - 2 phut), luu vao `test_data/sample1.wav`,
   `test_data/sample2.wav`, v.v.
2. Voi moi file, tu nghe lai va go tay CHINH XAC 100% nhung gi da noi, luu vao file
   cung ten voi hau to `_ground_truth.txt` (vi du: `test_data/sample1_ground_truth.txt`)
3. Chay `python evaluate.py` - he thong se tinh WER (Ty le loi tu) cho tung mau va
   WER trung binh, co the trich dan truc tiep vao bao cao.

Cong thuc: `WER = (Substitutions + Deletions + Insertions) / So tu trong ban goc`

## Tinh nang So sanh 2 phuong phap tom tat (Diem nhan khoa hoc cua do an)

He thong ho tro dong thoi 2 phuong phap tom tat de so sanh:

| Tieu chi | TextRank (Trich xuat) | LLM/GPT (Sinh) |
|---|---|---|
| Chi phi | Mien phi | Tra phi theo luong dung (rat re) |
| Toc do | Nhanh (< 1 giay) | Cham hon (vai giay, phu thuoc mang) |
| Can Internet | Khong | Co |
| Chat luong doc | Ghep cau co san, doi khi cut lun | Tu nhien, mach lac nhu nguoi that viet |
| Bao mat du lieu | Cao (khong gui du lieu ra ngoai) | Thap hon (gui qua API ben thu 3) |

De bat tinh nang so sanh nay:
1. Lay OpenAI API Key tai https://platform.openai.com/api-keys
2. Dien vao `config.py`: `OPENAI_API_KEY = "sk-..."`
3. Doi `ENABLE_LLM_SUMMARY = True` trong `config.py`
4. Chay lai `python main.py` - moi cuoc hop se tu dong duoc tom tat bang CA 2 phuong phap,
   luu ca thoi gian xu ly cua tung phuong phap vao database
5. Vao Dashboard (`/meeting/<id>`) de xem 2 ket qua hien thi song song, tien so sanh truc quan

Day chinh la phan **thuc nghiem so sanh** co the dua vao chuong "Danh gia va Ket qua"
cua bao cao do an - the hien duoc kha nang phan tich, khong chi dung lai o muc
"su dung cong nghe co san".

## Huong phat trien them (co the neu trong bao cao)

- Thay TextRank bang mo hinh tom tat "abstractive" (vi du fine-tune mBART/PhoBERT)
  de tom tat tu nhien hon
- Ho tro nhieu Jetson Nano dong thoi (nhieu phong hop), backend tap trung
- Xac thuc nguoi dung (dang nhap) cho Dashboard
- Nhan dien nguoi noi (Speaker Diarization) de biet ai noi cau nao trong bien ban
