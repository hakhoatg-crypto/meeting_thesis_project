"""
Module: summarizer.py
Chuc nang: Tom tat noi dung van ban cuoc hop.

Ky thuat su dung: TextRank - thuat toan tom tat trich xuat (extractive summarization)
dua tren ly thuyet do thi (graph-based ranking), cung ho hang voi thuat toan PageRank
cua Google. Thuat toan xay dung do thi trong do moi cau la 1 dinh, canh noi giua 2 cau
duoc tinh trong so theo do tuong dong ngu nghia, roi chon ra cac cau "trung tam" nhat
(duoc nhieu cau khac "tro toi") de dua vao ban tom tat.

Uu diem so voi goi API AI (GPT...):
    - Hoan toan mien phi, chay offline, khong can Internet
    - Khong phu thuoc ben thu 3, phu hop yeu cau bao mat du lieu cuoc hop
Nhuoc diem:
    - La tom tat "trich xuat" (chon nguyen cau co san), khong "sinh ra" cau moi
      nhu tom tat "abstractive" cua cac mo hinh LLM lon.
"""

import os
import sys

from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.text_rank import TextRankSummarizer

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


class Summarizer:
    def __init__(self):
        self.summarizer = TextRankSummarizer()

    def summarize(self, text: str, sentence_count: int = None) -> str:
        """
        Tom tat van ban dau vao, tra ve chuoi van ban da rut gon.
        """
        if sentence_count is None:
            sentence_count = getattr(config, "SUMMARY_SENTENCE_COUNT", 3)

        if not text or len(text.strip()) == 0:
            return ""

        parser = PlaintextParser.from_string(text, Tokenizer("english"))
        summary_sentences = self.summarizer(parser.document, sentence_count)

        summary_text = " ".join(str(sentence) for sentence in summary_sentences)
        return summary_text

    def extract_action_items(self, text: str) -> list:
        """Trích xuất danh sách việc cần làm (Action Items) từ văn bản."""
        if not text:
            return []
        import re
        action_keywords = ["cần", "phải", "hoàn thành", "gửi", "báo cáo", "kiểm tra", "chuẩn bị", "xem", "làm", "nghiên cứu", "nộp"]
        sentences = [s.strip() for s in re.split(r'[.!?\n]', text) if len(s.strip()) > 5]
        actions = []
        for idx, s in enumerate(sentences):
            s_lower = s.lower()
            if any(kw in s_lower for kw in action_keywords):
                assignee = "Chung"
                if "anh" in s_lower or "chị" in s_lower or "ông" in s_lower or "bà" in s_lower or "bạn" in s_lower:
                    words = s.split()
                    for w in words:
                        if w.lower() in ["anh", "chị", "ông", "bà", "bạn"] and words.index(w) < len(words) - 1:
                            assignee = f"{w} {words[words.index(w)+1]}"
                            break
                actions.append({
                    "id": idx + 1,
                    "task": s,
                    "assignee": assignee,
                    "is_completed": False
                })
        return actions[:6]

    def extract_keywords(self, text: str) -> list:
        """Trích xuất từ khóa nổi bật (Keywords)."""
        if not text:
            return []
        import re
        words = re.findall(r'\b\w{3,}\b', text.lower())
        stopwords = {"này", "được", "trong", "người", "khi", "như", "theo", "cho", "của", "với", "ngày", "năm", "bấm", "chạy"}
        freq = {}
        for w in words:
            if w not in stopwords and not w.isdigit():
                freq[w] = freq.get(w, 0) + 1
        sorted_words = sorted(freq.items(), key=lambda x: x[1], reverse=True)
        return [{"word": w.capitalize(), "count": c} for w, c in sorted_words[:5]]

    def extract_sentiment(self, text: str) -> dict:
        """Phân tích cảm xúc cuộc họp (Sentiment Analysis)."""
        if not text:
            return {"label": "Neutral", "text": "Trung tính 😐", "score": 0.5}
        text_lower = text.lower()
        pos_words = ["tốt", "hay", "tuyệt", "thành công", "ok", "đạt", "nhất", "xuất sắc", "hoàn thành"]
        neg_words = ["lỗi", "chậm", "hỏng", "thất bại", "kém", "muộn", "căng thẳng", "khó", "sự cố"]
        pos_score = sum(1 for w in pos_words if w in text_lower)
        neg_score = sum(1 for w in neg_words if w in text_lower)
        if pos_score > neg_score:
            return {"label": "Positive", "text": "Tích cực 😄", "score": 0.85}
        elif neg_score > pos_score:
            return {"label": "Negative", "text": "Căng thẳng 😬", "score": 0.35}
        return {"label": "Neutral", "text": "Trung tính 😐", "score": 0.60}

    def segment_timestamps(self, text: str, duration_sec: float) -> list:
        """Chia văn bản thành các mẩu thời gian để bấm vào câu nhảy tới đúng giây âm thanh."""
        import re
        sentences = [s.strip() for s in re.split(r'[.!?\n]', text) if s.strip()]
        if not sentences:
            return []
        total_len = sum(len(s) for s in sentences) or 1
        curr_time = 0.0
        segments = []
        for idx, s in enumerate(sentences):
            ratio = len(s) / total_len
            seg_duration = max(1.5, ratio * duration_sec)
            start_t = curr_time
            end_t = min(duration_sec, start_t + seg_duration)
            curr_time = end_t
            segments.append({
                "id": idx + 1,
                "start": round(start_t, 1),
                "end": round(end_t, 1),
                "text": s,
            })
        return segments

