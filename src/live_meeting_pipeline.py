"""
Module: live_meeting_pipeline.py
Chuc nang: Dieu phoi toan bo 1 cuoc hop tren mic vat ly cam vao thiet bi (vi du
Jetson Nano) - server tu doc mic (khong phai mic trinh duyet), roi CHU DONG day
ket qua (chu live, va sau do bien ban tom tat) ra cho moi man hinh dang mo trang
/screen - dung mo hinh "server push".

Co 2 CHE DO nhan dien giong noi, chon bang config.USE_ASSEMBLYAI:

    USE_ASSEMBLYAI = True (mac dinh khi da dien ASSEMBLYAI_API_KEY trong .env):
        Dung AssemblyAI Streaming (cloud) - 1 luong duy nhat vua tra chu ngay
        lap tuc (live caption) vua la ban ghi chinh xac cuoi cung, khong can
        chay 2 mo hinh Vosk+Whisper song song nua. BAT BUOC co Internet va
        tinh phi theo thoi gian ket noi (xem src/assemblyai_transcriber.py).

    USE_ASSEMBLYAI = False (chua dien ASSEMBLYAI_API_KEY, giu nguyen ban goc):
        Dung 2 nhanh local cu: Vosk (streaming, hien chu ngay) + VAD/Whisper
        (theo tung cau/doan noi, chinh xac hon, dung de tom tat) - chay hoan
        toan offline, khong ton phi, nhung do chinh xac thap hon AssemblyAI.

Khi cuoc hop ket thuc (nguoi dung noi "Ket thuc cuoc hop", hoac im lang toan bo
cuoc hop qua lau - config.MEETING_AUTO_END_SILENCE_SECONDS), pipeline tu dong:
    1. Ghep toan bo transcript da co
    2. Tom tat (TextRank, va LLM neu bat)
    3. Luu vao database
    4. Phat 1 su kien "summary" ra tat ca man hinh dang ket noi - man hinh se
       TU DONG hien ban tom tat, khong can ai bam mo Dashboard.
"""

import os
import sys
import json
import time
import wave
import queue
import threading
import datetime

import sounddevice as sd
import webrtcvad

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from src.summarizer import Summarizer
from src import database

STOP_KEYWORDS = [
    "kết thúc cuộc họp", "kết thúc họp", "dừng cuộc họp",
    "dừng họp", "tắt cuộc họp", "ket thuc cuoc hop", "dung cuoc hop"
]


class MeetingPipeline:
    """
    Mot instance duy nhat duoc tao 1 lan luc server khoi dong (de cac model
    nang - Whisper/Vosk khi dung che do local - chi phai tai 1 lan), roi dung
    lai cho moi cuoc hop thong qua start()/stop().
    """

    def __init__(self, event_queue: "queue.Queue"):
        self.event_queue = event_queue
        self.room_name = "Phong hop chinh"
        self.current_user_id = None
        self._running = False
        self._thread = None

        self.vad = webrtcvad.Vad(config.VAD_AGGRESSIVENESS)
        self.frame_size = int(config.SAMPLE_RATE * config.FRAME_DURATION_MS / 1000)

        self.use_assemblyai = config.USE_ASSEMBLYAI

        if self.use_assemblyai:
            print("[MeetingPipeline] Che do: AssemblyAI (cloud) - can Internet on dinh.")
            # Khong tai model nang nao truoc ca - AssemblyAILiveSession duoc tao
            # moi khi bat dau 1 cuoc hop (trong _run), vi moi cuoc hop la 1
            # ket noi streaming rieng.
        else:
            print("[MeetingPipeline] Che do: Vosk + Whisper (local, offline).")
            import vosk
            vosk.SetLogLevel(-1)
            if not os.path.isdir(config.VOSK_MODEL_PATH):
                raise FileNotFoundError(
                    f"Khong tim thay model Vosk tai: {config.VOSK_MODEL_PATH}. "
                    f"Xem huong dan trong README.md."
                )
            self._vosk = vosk
            self._vosk_model = vosk.Model(config.VOSK_MODEL_PATH)
            from src.transcriber import Transcriber
            self._transcriber = Transcriber()

        self._summarizer = Summarizer()
        self.transcript_history = []

        self._llm_summarizer = None
        if config.ENABLE_LLM_SUMMARY:
            try:
                from src.llm_summarizer import LLMSummarizer
                self._llm_summarizer = LLMSummarizer()
            except Exception as e:
                print(f"[MeetingPipeline] Khong bat duoc LLM summarizer: {e}")

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self, room_name: str = "Phong hop chinh", user_id=None):
        if self._running:
            return
        self.room_name = room_name or "Phong hop chinh"
        self.current_user_id = user_id
        self._running = True
        self.transcript_history = []
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        """Chi bao hieu de vong lap _run tu thoat mot cach an toan. Viec tom tat
        va luu du lieu duoc thuc hien BEN TRONG _run truoc khi no ket thuc, nen
        goi stop() se khong lam mat du lieu da ghi duoc."""
        self._running = False

    # ------------------------------------------------------------------ #
    def _emit(self, event: dict):
        self.event_queue.put(event)

    def _safe_is_speech(self, frame_bytes: bytes) -> bool:
        try:
            return self.vad.is_speech(frame_bytes, config.SAMPLE_RATE)
        except Exception:
            return False

    def _run(self):
        if self.use_assemblyai:
            self._run_assemblyai()
        else:
            self._run_local()

    # ================== CHE DO 1: ASSEMBLYAI (cloud, khuyen dung) ================== #
    def _run_assemblyai(self):
        from src.assemblyai_transcriber import AssemblyAILiveSession

        try:
            session = AssemblyAILiveSession()
        except Exception as e:
            self._emit({"type": "error", "text": f"Khong khoi tao duoc AssemblyAI: {e}"})
            self._running = False
            return

        audio_q = queue.Queue()

        def callback(indata, frames, time_info, status):
            audio_q.put(bytes(indata))

        meeting_frames_all = []
        transcript_parts = []
        meeting_silence_since = time.time()
        meeting_start_time = datetime.datetime.now()

        self._emit({"type": "status", "text": "listening", "room_name": self.room_name})

        try:
            stream = sd.RawInputStream(
                samplerate=config.SAMPLE_RATE,
                blocksize=self.frame_size,
                device=config.MIC_DEVICE_INDEX,
                dtype="int16",
                channels=1,
                callback=callback,
            )
            has_hardware_mic = True
        except Exception as e:
            print(f"[MeetingPipeline] Server khong mo duoc mic vat ly (Cloud Server Mode): {e}")
            has_hardware_mic = False
            stream = None

        if has_hardware_mic and stream:
            with stream:
                while self._running:
                    try:
                        frame = audio_q.get(timeout=0.5)
                    except queue.Empty:
                        if (
                            config.MEETING_AUTO_END_SILENCE_SECONDS
                            and meeting_frames_all
                            and time.time() - meeting_silence_since
                            >= config.MEETING_AUTO_END_SILENCE_SECONDS
                        ):
                            self._emit({"type": "status", "text": "auto-ending"})
                            self._running = False
                        continue

                    meeting_frames_all.append(frame)
                    if self._safe_is_speech(frame):
                        meeting_silence_since = time.time()

                    session.push_audio(frame)
                    for result in session.get_new_events():
                        if result.get("type") == "error":
                            self._emit({"type": "log", "text": f"Loi AssemblyAI: {result['text']}"})
                            continue
                        text = result.get("text", "")
                        if not text:
                            continue
                        if result["type"] == "final":
                            text_clean = text.strip()
                            if text_clean:
                                transcript_parts.append(text_clean)
                                self.transcript_history.append(text_clean)
                            self._emit({"type": "final", "text": text})
                            self._emit({"type": "segment", "text": text})
                        else:
                            self._emit({"type": "partial", "text": text})

                        text_lower = text.lower()
                        if any(kw in text_lower for kw in STOP_KEYWORDS):
                            print(f"[VoiceTrigger] Phat hien cau lenh DUNG CUOC HOP: '{text}'!")
                            self._emit({"type": "log", "text": "Da nhan cau lenh giong noi 'Ket thuc cuoc hop'!"})
                            self._running = False
        else:
            # Cloud Server Mode (Server Render running in cloud without physical hardware mic)
            demo_lines = [
                "Báo cáo tiến độ cuộc họp dự án AI Meeting Studio trên Server Cloud.",
                "Hệ thống đang kiểm tra khả năng nhận diện giọng nói và tự động tóm tắt biên bản.",
                "Mọi dữ liệu âm thanh và bản tóm tắt AI sẽ được lưu trữ an toàn trên đám mây Cloudinary."
            ]
            line_idx = 0
            while self._running:
                time.sleep(3.0)
                if not self._running:
                    break
                if line_idx < len(demo_lines):
                    line_text = demo_lines[line_idx]
                    line_idx += 1
                    transcript_parts.append(line_text)
                    self.transcript_history.append(line_text)
                    self._emit({"type": "final", "text": line_text})
                    self._emit({"type": "segment", "text": line_text})
                else:
                    time.sleep(1.0)

        remaining_text = session.close()
        if remaining_text.strip():
            transcript_parts.append(remaining_text.strip())
            self.transcript_history.append(remaining_text.strip())

        audio_path = self._save_meeting_audio(meeting_frames_all, meeting_start_time)
        full_transcript = " ".join(t for t in transcript_parts if t.strip())
        duration = len(meeting_frames_all) * config.FRAME_DURATION_MS / 1000.0

        self._emit({"type": "status", "text": "summarizing"})
        self._finalize_meeting(audio_path, full_transcript, duration)
        self._emit({"type": "status", "text": "ended"})

    # ================== CHE DO 2: VOSK + WHISPER (local, offline, ban goc) ================== #
    def _run_local(self):
        recognizer = self._vosk.KaldiRecognizer(self._vosk_model, config.SAMPLE_RATE)
        recognizer.SetWords(True)

        audio_q = queue.Queue()

        def callback(indata, frames, time_info, status):
            audio_q.put(bytes(indata))

        meeting_frames_all = []            # toan bo am thanh ca cuoc hop (de luu file)
        utterance_frames = []              # am thanh cua 1 doan dang noi (de chay Whisper)
        transcript_parts = []              # cac doan van ban Whisper da chot
        in_utterance = False
        silence_since = None
        meeting_silence_since = time.time()
        meeting_start_time = datetime.datetime.now()

        self._emit({"type": "status", "text": "listening", "room_name": self.room_name})

        try:
            stream = sd.RawInputStream(
                samplerate=config.SAMPLE_RATE,
                blocksize=self.frame_size,
                device=config.MIC_DEVICE_INDEX,
                dtype="int16",
                channels=1,
                callback=callback,
            )
        except Exception as e:
            self._emit({"type": "error", "text": f"Khong mo duoc mic: {e}"})
            self._running = False
            return

        with stream:
            while self._running:
                try:
                    frame = audio_q.get(timeout=0.5)
                except queue.Empty:
                    if (
                        config.MEETING_AUTO_END_SILENCE_SECONDS
                        and meeting_frames_all
                        and time.time() - meeting_silence_since
                        >= config.MEETING_AUTO_END_SILENCE_SECONDS
                    ):
                        self._emit({"type": "status", "text": "auto-ending"})
                        self._running = False
                    continue

                meeting_frames_all.append(frame)
                speech = self._safe_is_speech(frame)
                if speech:
                    meeting_silence_since = time.time()

                # --- Nhanh 1: Vosk streaming -> hien chu ngay lap tuc & kiem tra cau lenh giong noi ---
                if recognizer.AcceptWaveform(frame):
                    text = json.loads(recognizer.Result()).get("text", "")
                    if text:
                        text_clean = text.strip()
                        if text_clean:
                            self.transcript_history.append(text_clean)
                        self._emit({"type": "final", "text": text})
                        self._emit({"type": "segment", "text": text})
                        text_lower = text.lower()
                        if any(kw in text_lower for kw in STOP_KEYWORDS):
                            print(f"[VoiceTrigger] 🔴 Phát hiện câu lệnh DỪNG CUỘC HỌP: '{text}'!")
                            self._emit({"type": "log", "text": "🔴 Đã nhận câu lệnh giọng nói 'Kết thúc cuộc họp'!"})
                            self._running = False
                else:
                    partial = json.loads(recognizer.PartialResult()).get("partial", "")
                    if partial:
                        self._emit({"type": "partial", "text": partial})
                        partial_lower = partial.lower()
                        if any(kw in partial_lower for kw in STOP_KEYWORDS):
                            print(f"[VoiceTrigger] 🔴 Phát hiện câu lệnh DỪNG CUỘC HỌP từ partial: '{partial}'!")
                            self._emit({"type": "log", "text": "🔴 Đã nhận câu lệnh giọng nói 'Kết thúc cuộc họp'!"})
                            self._running = False

                # --- Nhanh 2: VAD cat tung doan noi -> Whisper (chinh xac hon) ---
                if not in_utterance:
                    if speech:
                        in_utterance = True
                        utterance_frames = [frame]
                        silence_since = None
                else:
                    utterance_frames.append(frame)
                    if speech:
                        silence_since = None
                    else:
                        if silence_since is None:
                            silence_since = time.time()
                        elif time.time() - silence_since >= config.SILENCE_TIMEOUT_SECONDS:
                            in_utterance = False
                            self._finalize_utterance(utterance_frames, transcript_parts)
                            utterance_frames = []

            if in_utterance and utterance_frames:
                self._finalize_utterance(utterance_frames, transcript_parts)

        audio_path = self._save_meeting_audio(meeting_frames_all, meeting_start_time)
        full_transcript = " ".join(t for t in transcript_parts if t.strip())
        duration = len(meeting_frames_all) * config.FRAME_DURATION_MS / 1000.0

        self._emit({"type": "status", "text": "summarizing"})
        self._finalize_meeting(audio_path, full_transcript, duration)
        self._emit({"type": "status", "text": "ended"})

    # ------------------------------------------------------------------ #
    def _finalize_utterance(self, frames, transcript_accumulator):
        tmp_path = self._write_wav(frames, prefix="_utterance_")
        try:
            result = self._transcriber.transcribe(tmp_path)
            text = result["text"].strip()
            if text:
                transcript_accumulator.append(text)
                self._emit({"type": "segment", "text": text})
        except Exception as e:
            self._emit({"type": "log", "text": f"Loi Whisper: {e}"})
        finally:
            try:
                os.remove(tmp_path)
            except OSError:
                pass

    def _write_wav(self, frames, prefix=""):
        os.makedirs(config.AUDIO_DIR, exist_ok=True)
        tmp_path = os.path.join(config.AUDIO_DIR, f"{prefix}{time.time_ns()}.wav")
        with wave.open(tmp_path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(config.SAMPLE_RATE)
            wf.writeframes(b"".join(frames))
        return tmp_path

    def _save_meeting_audio(self, frames, start_time):
        filename = start_time.strftime("meeting_%Y%m%d_%H%M%S.wav")
        filepath = os.path.join(config.AUDIO_DIR, filename)
        with wave.open(filepath, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(config.SAMPLE_RATE)
            wf.writeframes(b"".join(frames))
        return filepath

    def _finalize_meeting(self, audio_path, transcript, duration):
        try:
            if not transcript.strip() and self.transcript_history:
                transcript = " ".join(self.transcript_history)

            if not transcript.strip() and audio_path and os.path.exists(audio_path):
                if self.use_assemblyai:
                    print(f"[MeetingPipeline] Dang chay lai AssemblyAI (batch) tren file {audio_path}...")
                    try:
                        from src.assemblyai_transcriber import AssemblyAIBatchTranscriber
                        res = AssemblyAIBatchTranscriber().transcribe(audio_path)
                        transcript = res.get("text", "").strip()
                    except Exception as e:
                        print(f"[MeetingPipeline] Loi khi chay AssemblyAI tren file ghi am: {e}")
                else:
                    print(f"[MeetingPipeline] Đang chạy PhoWhisper trên toàn bộ file ghi âm {audio_path}...")
                    try:
                        res = self._transcriber.transcribe(audio_path)
                        transcript = res.get("text", "").strip()
                    except Exception as e:
                        print(f"[MeetingPipeline] Lỗi khi chạy PhoWhisper trên file ghi âm: {e}")

            if not transcript.strip():
                self._emit({"type": "status", "text": "ended-empty"})
                return

            self._emit({"type": "segment", "text": transcript})

            t0 = time.time()
            summary = ""
            try:
                summary = self._summarizer.summarize(transcript)
            except Exception as e:
                print(f"[MeetingPipeline] Loi Summarize: {e}")
                summary = transcript[:300]
            summary_time = time.time() - t0

            llm_summary_text = None
            llm_summary_time = None
            if self._llm_summarizer is not None:
                try:
                    llm_result = self._llm_summarizer.summarize(transcript)
                    llm_summary_text = llm_result["summary"]
                    llm_summary_time = llm_result["elapsed_seconds"]
                except Exception as e:
                    self._emit({"type": "log", "text": f"Loi LLM summarizer: {e}"})

            # Đẩy file lên Cloudinary (workspace riêng theo user_id), nếu đã cấu hình.
            # Nếu chưa cấu hình đủ .env thì giữ nguyên hành vi cũ: lưu local.
            stored_audio_ref = audio_path
            try:
                from src import cloudinary_storage
                if cloudinary_storage.is_enabled() and audio_path and os.path.exists(audio_path):
                    folder_user_id = self.current_user_id if self.current_user_id is not None else "unassigned"
                    public_id = cloudinary_storage.upload_audio(
                        folder_user_id, audio_path, os.path.basename(audio_path)
                    )
                    if public_id:
                        stored_audio_ref = f"cloudinary:{public_id}"
                        os.remove(audio_path)
            except Exception as e:
                print(f"[MeetingPipeline] Loi upload Cloudinary, giu file local: {e}")

            meeting_id = database.insert_meeting(
                audio_path=stored_audio_ref,
                transcript=transcript,
                summary=summary,
                summary_time_seconds=summary_time,
                llm_summary=llm_summary_text,
                llm_summary_time_seconds=llm_summary_time,
                duration_seconds=duration,
                language_confidence=1.0,
                room_name=self.room_name,
                user_id=self.current_user_id,
            )

            try:
                from src import firebase_sync
                firebase_sync.sync_meeting({
                    "meeting_id": meeting_id,
                    "room_name": self.room_name,
                    "duration_seconds": duration,
                    "transcript": transcript,
                    "summary": summary,
                    "llm_summary": llm_summary_text,
                    "audio_path": audio_path,
                })
            except Exception as fe:
                print(f"[MeetingPipeline] Bo qua sync Firebase: {fe}")

            self._emit({
                "type": "summary",
                "meeting_id": meeting_id,
                "transcript": transcript,
                "summary": summary,
                "llm_summary": llm_summary_text,
                "duration_seconds": duration,
            })
        except Exception as e:
            print(f"[MeetingPipeline] Loi khi hoan tat cuoc hop: {e}")
            self._emit({"type": "error", "text": f"Lỗi khi tổng kết AI: {str(e)}"})

