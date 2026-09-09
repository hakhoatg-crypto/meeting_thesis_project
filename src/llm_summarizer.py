"""
Module: llm_summarizer.py
Chuc nang: Tom tat noi dung cuoc hop bang LLM (Large Language Model).

Ky thuat su dung: Goi API cua OpenAI GPT - mo hinh ngon ngu lon (LLM), khac voi
TextRank o cho: LLM hieu ngu canh toan bo van ban va "sinh ra" (generate) cau
tom tat MOI bang chinh kha nang ngon ngu cua no, thay vi chi trich xuat (chon loc)
nguyen van cac cau co san nhu TextRank.

Day la ky thuat "abstractive summarization" (tom tat sinh) doi lap voi
"extractive summarization" (tom tat trich xuat) cua module summarizer.py.

Yeu cau: can OPENAI_API_KEY hop le trong config.py va ket noi Internet.
"""

import os
import sys
import time

from openai import OpenAI

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

PROMPT_TEMPLATE = """Ban la tro ly ghi bien ban cuoc hop chuyen nghiep. Duoi day la noi dung
day du (transcript) cua mot cuoc hop bang tieng Viet. Hay tom tat lai NGAN GON,
mach lac, tu nhien nhu mot thu ky thuc su viet, theo cau truc:

1. Tom tat noi dung chinh (3-5 cau)
2. Cac quyet dinh da chot (neu co)
3. Danh sach dau viec can lam (Action Items)

Noi dung transcript:
---
{transcript}
---
"""


class LLMSummarizer:
    def __init__(self):
        if not config.OPENAI_API_KEY or config.OPENAI_API_KEY == "dan_api_key_cua_ban_vao_day":
            raise ValueError(
                "Chua cau hinh OPENAI_API_KEY trong config.py. "
                "Module nay can API key hop le de hoat dong."
            )
        self.client = OpenAI(api_key=config.OPENAI_API_KEY)

    def summarize(self, text: str) -> dict:
        """
        Tom tat van ban bang LLM.
        Tra ve dict gom: summary (van ban tom tat), elapsed_seconds (thoi gian xu ly).
        """
        if not text or len(text.strip()) == 0:
            return {"summary": "", "elapsed_seconds": 0}

        t0 = time.time()
        response = self.client.chat.completions.create(
            model=config.LLM_SUMMARY_MODEL,
            messages=[{"role": "user", "content": PROMPT_TEMPLATE.format(transcript=text)}],
            temperature=0.3,
        )
        elapsed = time.time() - t0

        summary = response.choices[0].message.content.strip()
        return {"summary": summary, "elapsed_seconds": elapsed}
