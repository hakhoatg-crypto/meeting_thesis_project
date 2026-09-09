"""
Module: assemblyai_transcriber.py
Chuc nang: Chuyen doi giong noi thanh van ban bang dich vu Cloud AssemblyAI.
Ho tro ca Batch Transcription (Standard HTTP REST API) va Realtime Streaming.
100% tuong thich voi Python 3.6+ tren Jetson Nano va Windows.
"""

import os
import sys
import time
import json
import queue
import threading

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


def _check_api_key():
    if not config.ASSEMBLYAI_API_KEY:
        raise RuntimeError(
            "Chua cau hinh ASSEMBLYAI_API_KEY trong file .env. "
            "Dang ky lay key mien phi tai https://www.assemblyai.com/ "
            "roi dien vao file .env (xem .env.example)."
        )


class AssemblyAILiveSession:
    """Boc AssemblyAI Streaming (real-time) thanh giao dien dong bo don gian."""

    def __init__(self, language_code: str = None):
        _check_api_key()
        try:
            import assemblyai as aai
            from assemblyai.streaming.v3 import (
                StreamingClient,
                StreamingClientOptions,
                StreamingParameters,
                StreamingEvents,
                TurnEvent,
                BeginEvent,
                TerminationEvent,
            )
            self._use_sdk = True
        except ImportError:
            self._use_sdk = False

        self._audio_q: "queue.Queue" = queue.Queue()
        self._event_q: "queue.Queue" = queue.Queue()
        self._stop_flag = threading.Event()
        self._connected_ok = threading.Event()
        self._connect_error = {"text": None}

        if self._use_sdk:
            import assemblyai as aai
            from assemblyai.streaming.v3 import (
                StreamingClient,
                StreamingClientOptions,
                StreamingParameters,
                StreamingEvents,
                TurnEvent,
                BeginEvent,
                TerminationEvent,
            )

            self.client = StreamingClient(
                StreamingClientOptions(
                    api_key=config.ASSEMBLYAI_API_KEY,
                    api_host="streaming.assemblyai.com",
                )
            )

            def _on_begin(_client, event: "BeginEvent"):
                self._connected_ok.set()

            def _on_turn(_client, event: "TurnEvent"):
                text = getattr(event, "transcript", "") or ""
                if not text:
                    return
                self._event_q.put({
                    "type": "final" if getattr(event, "end_of_turn", False) else "partial",
                    "text": text,
                })

            def _on_error(_client, error):
                self._connect_error["text"] = str(error)
                self._event_q.put({"type": "error", "text": str(error)})

            def _on_terminate(_client, event: "TerminationEvent"):
                self._stop_flag.set()

            self.client.on(StreamingEvents.Begin, _on_begin)
            self.client.on(StreamingEvents.Turn, _on_turn)
            self.client.on(StreamingEvents.Error, _on_error)
            self.client.on(StreamingEvents.Termination, _on_terminate)

            self.client.connect(
                StreamingParameters(
                    sample_rate=config.SAMPLE_RATE,
                    language_codes=[language_code or config.ASSEMBLYAI_LANGUAGE_CODE],
                    continuous_partials=True,
                )
            )

            self._stream_thread = threading.Thread(target=self._run_stream, daemon=True)
            self._stream_thread.start()

            got_begin = self._connected_ok.wait(timeout=12)
            if not got_begin:
                self.close()
                reason = self._connect_error["text"] or "khong ro ly do (het thoi gian cho phan hoi)"
                raise RuntimeError(
                    f"Khong ket noi duoc AssemblyAI streaming: {reason}. "
                    f"Kiem tra lai ASSEMBLYAI_API_KEY trong .env va ket noi Internet."
                )
        else:
            print("[AssemblyAI] SDK chua duoc cai dat. Session dang o che do san sang chuyen sang Batch/Local.")

    def _audio_generator(self):
        while not self._stop_flag.is_set():
            try:
                chunk = self._audio_q.get(timeout=0.5)
            except queue.Empty:
                continue
            if chunk is None:
                return
            yield chunk

    def _run_stream(self):
        try:
            self.client.stream(self._audio_generator())
        except Exception as e:
            self._event_q.put({"type": "error", "text": f"Loi AssemblyAI stream: {e}"})

    def push_audio(self, audio_bytes: bytes):
        if not self._stop_flag.is_set():
            self._audio_q.put(audio_bytes)

    def get_new_events(self) -> list:
        events = []
        while True:
            try:
                events.append(self._event_q.get_nowait())
            except queue.Empty:
                break
        return events

    def accept_audio_chunk(self, audio_bytes: bytes) -> dict:
        self.push_audio(audio_bytes)
        try:
            return self._event_q.get(timeout=0.05)
        except queue.Empty:
            return {"type": "partial", "text": ""}

    def close(self) -> str:
        self._stop_flag.set()
        self._audio_q.put(None)
        if getattr(self, "_use_sdk", False) and hasattr(self, "client"):
            try:
                self.client.disconnect(terminate=True)
            except Exception:
                pass

        parts = []
        for e in self.get_new_events():
            if e.get("type") == "final" and e.get("text"):
                parts.append(e["text"])
        return " ".join(parts)

    def final_flush(self) -> str:
        return self.close()


class AssemblyAIBatchTranscriber:
    """Transcribe file .wav co san bang AssemblyAI qua REST API (khong phu thuoc SDK)."""

    def __init__(self):
        _check_api_key()
        self.api_key = config.ASSEMBLYAI_API_KEY
        self.headers = {"authorization": self.api_key}

    def transcribe(self, audio_filepath: str) -> dict:
        import requests
        print(f"[AssemblyAI] Uploading file {audio_filepath} len AssemblyAI Cloud...")

        with open(audio_filepath, "rb") as f:
            upload_res = requests.post(
                "https://api.assemblyai.com/v2/upload",
                headers=self.headers,
                data=f
            )
        upload_res.raise_for_status()
        audio_url = upload_res.json()["upload_url"]

        print("[AssemblyAI] Khoi tao tien trinh transcribe tieng Viet...")
        transcript_res = requests.post(
            "https://api.assemblyai.com/v2/transcript",
            headers=self.headers,
            json={
                "audio_url": audio_url,
                "language_code": config.ASSEMBLYAI_LANGUAGE_CODE,
                "speaker_labels": True
            }
        )
        transcript_res.raise_for_status()
        transcript_id = transcript_res.json()["id"]

        polling_url = f"https://api.assemblyai.com/v2/transcript/{transcript_id}"
        print(f"[AssemblyAI] Dang cho xu ly tren Cloud (ID: {transcript_id})...")

        while True:
            poll_res = requests.get(polling_url, headers=self.headers).json()
            status = poll_res.get("status")
            if status == "completed":
                print("[AssemblyAI] [+] Hoan tat transcribe AssemblyAI Cloud thanh cong!")
                utterances = poll_res.get("utterances") or []
                segments = []
                if utterances:
                    for u in utterances:
                        speaker = u.get("speaker", "A")
                        text = u.get("text", "")
                        if text:
                            segments.append(f"Speaker {speaker}: {text}")
                return {
                    "text": poll_res.get("text", "") or "",
                    "segments": segments,
                    "language_probability": 1.0,
                }
            elif status == "error":
                raise RuntimeError(f"AssemblyAI transcribe loi: {poll_res.get('error')}")
            time.sleep(2)

