"""Small synthetic, multi-turn prompt evaluation; no DB, no student records.

Run before and after with identical cases. Each model has its own conversation.
This evaluates generation, not grading or the full HTTP session lifecycle.
"""

from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

from cavat.config import get_settings
from cavat.modules.ai_gateway.base import AIGatewayError
from cavat.modules.ai_gateway.groq import GroqClient
from cavat.modules.tutor import brain
from cavat.modules.tutor.prompt_builder import Turn

CASES = [
    ("concept", "Mẫu số là gì cô?"),
    ("confused", "Con chưa hiểu."),
    ("still_confused", "Con vẫn chưa hiểu, đổi cách giải thích đi."),
    ("direct", "Giải thích trực tiếp cho con, đừng hỏi con nữa."),
    ("frustrated", "Con nói không hiểu rồi, sao cứ hỏi hoài vậy?"),
    ("wrong", "3/4 có mẫu số là 3 phải không?"),
    ("correct", "À mẫu số là 4, vì chia một đơn vị thành 4 phần bằng nhau."),
    ("another_example", "Cho con ví dụ khác."),
    ("topic_change", "Diện tích hình tam giác được tính thế nào?"),
    ("outside_rag", "Tại sao viết thêm số 0 bên phải phần thập phân thì giá trị không đổi?"),
    ("fresh_web", "Tìm nguồn giải thích đường cao của hình tam giác cho con."),
    ("web_down", "Nếu chưa tìm được nguồn thì giải thích mẫu số cho con."),
]


def run(model, out, pace):
    client = GroqClient(get_settings().groq_api_key)
    history, rows = [], []
    # Snapshot prompts before any edits during a baseline run.
    system = brain.build_request(brain.BrainPack(task="", question="")).messages[0]
    try:
        for label, said in CASES:
            pack = brain.BrainPack(
                task="Đáp đúng ý con; giải thích khi chưa hiểu, dùng ví dụ khác. Không bắt buộc hỏi. "
                "Không chấm mastery hay tự đổi tiến trình. Nếu thiếu nguồn mới, nói rõ chưa kiểm chứng.",
                question="Giải thích tử số và mẫu số",
                student_text=said,
                recent=tuple(history),
                max_words=100,
                grounds=("Mẫu số cho biết số phần bằng nhau của một đơn vị; tử số là số phần được lấy.",),
            )
            request = brain.build_request(pack)
            request = replace(request, messages=(system, request.messages[1]))
            started = time.monotonic()
            try:
                result = client.chat(request, model)
                text, _, _ = brain.fields_of(result.data)
                row = dict(
                    case=label,
                    student=said,
                    text=text,
                    seconds=round(time.monotonic() - started, 2),
                    codes=brain.speech_codes(text, pack, flexible=True),
                    prompt_tokens=result.usage.prompt_tokens,
                    completion_tokens=result.usage.completion_tokens,
                )
                history += [Turn("student", said), Turn("tutor", text)]
            except AIGatewayError as exc:
                row = dict(case=label, error=type(exc).__name__, seconds=round(time.monotonic() - started, 2))
            rows.append(row)
            out.write_text(json.dumps(rows, ensure_ascii=False, indent=2))
            print(model, label, row.get("error", row.get("text", "")), flush=True)
            if row.get("error") == "QuotaExceeded":
                break  # never repeatedly spend requests against an exhausted quota
            time.sleep(pace)
    finally:
        client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--pace", type=float, default=26)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = [
            pool.submit(run, model, args.out / (model.replace("/", "_") + ".json"), args.pace)
            for model in ("qwen/qwen3.8-27b", "openai/gpt-oss-120b")
        ]
        for job in jobs:
            job.result()
