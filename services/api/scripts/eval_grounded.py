"""Grounded speech, live (RAG-2): Qwen answers the child's own questions from the Hybrid RAG and bridges wrong
theory answers; every output passes the deterministic check first, then a second model judges it against
its sources.

Run by hand, with GROQ_API_KEY and GEMINI_API_KEY in services/api/.env: `make eval-grounded`. The cases are
`evals/datasets/grounded-decimals-v1.yaml`: questions on the chapter, the child asking back the tutor's own
question, questions outside the lesson or on a later lesson, and wrong theory answers. Each runs the real
speaker on the real index (Gemini vectors, cached) with the theory question it waits on.
`make eval-grounded ONLY=G02,B04` runs some cases only, to look closer without spending the whole quota.

Cost (free tier, docs/poc/free-tier-quota.md): about 20 Qwen calls (some 30 000 of its 200 000 tokens a day),
paced under its 8 000 tokens a minute; about 15 judge calls on openai/gpt-oss-120b, which has its own quota;
one Gemini embedding per new question. Not part of `make test`: the tests stay offline. The report goes to
evals/reports/<date>-grounded-live.md.
"""

from __future__ import annotations

import asyncio
import sys
import time
from dataclasses import dataclass, field
from datetime import date
from statistics import fmean

import yaml
from cavat.config import REPO_ROOT
from cavat.core.memory_db import InMemoryDatabase
from cavat.modules.ai_gateway.base import ChatMessage, ChatRequest, ModelClass
from cavat.modules.ai_gateway.router import build_router
from cavat.modules.assessment.vi_numbers import normalize_text, phrase_regex
from cavat.modules.rag.service import RagService
from cavat.modules.session import chapter_service
from cavat.modules.session.service import DEMO_SCHOOL_ID
from cavat.modules.teaching.grounded import GROUNDED_VERSION, GroundedSpeaker

DATASET = REPO_ROOT / "evals/datasets/grounded-decimals-v1.yaml"
JUDGE_MODEL = "openai/gpt-oss-120b"
PAUSE_S = 12  # about 1 500 tokens a Qwen call: stays under the 8 000 tokens a minute
LEAD = "Mình cùng xem lại nhé:"
KIND = {"ANSWERED": "answer", "PARKED": "park", "SAME_AS_CHECK": "same", "LATER": "later"}

JUDGE_SYSTEM = (
    "Bạn là giáo viên Toán tiểu học có kinh nghiệm, kiểm tra một lời nói của gia sư AI với học sinh lớp 5. "
    "Gia sư chỉ được nói điều có trong các đoạn nguồn (nội dung bài đã duyệt) hoặc trong lời học sinh. "
    "Chấm thang 1 đến 5 (5 là tốt nhất): faithful: mọi ý và mọi con số của lời gia sư đều có trong đoạn "
    "nguồn hoặc lời học sinh; relevant: trả lời đúng điều học sinh hỏi (với CÂU_NỐI: nhắc đúng điều học sinh "
    "vừa nói); correct: đúng kiến thức Toán; child_friendly: dễ hiểu, ấm áp với trẻ 10 tuổi. "
    "hallucination là true nếu có ý hoặc con số không có trong đoạn nguồn và lời học sinh. "
    "leaked_check là true nếu lời gia sư nói ra đáp án của câu gia sư đang chờ học sinh trả lời "
    "(cau_gia_su_dang_cho). "
    "Với loai CÂU_NỐI: đó là MỘT câu gia sư nói trước loi_giai_thich_noi_ngay_sau (lời giải thích đã duyệt, "
    "nói nguyên văn ngay sau câu nối, không cần chấm). Câu nối được phép, và nên, nhắc lại lời học sinh, kể "
    "cả khi lời đó sai, miễn là nói rõ đó là ý của học sinh (con nghĩ, con nói...) và không khẳng định nó "
    "đúng: nhắc lại như vậy KHÔNG phải bịa. Với câu nối, hallucination chỉ true khi gia sư tự khẳng định một "
    "ý sai hoặc thêm ý không có trong đoạn nguồn và lời học sinh; correct chấm việc câu nối (cùng lời giải "
    "thích ngay sau) có làm học sinh hiểu sai không; leaked_check luôn là false (lời giải thích sau đó vốn "
    "nêu đáp án). Trả về JSON đúng schema, nhận xét bằng tiếng Việt, ngắn."
)
JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "faithful": {"type": "integer", "minimum": 1, "maximum": 5},
        "relevant": {"type": "integer", "minimum": 1, "maximum": 5},
        "correct": {"type": "integer", "minimum": 1, "maximum": 5},
        "child_friendly": {"type": "integer", "minimum": 1, "maximum": 5},
        "hallucination": {"type": "boolean"},
        "leaked_check": {"type": "boolean"},
        "comment": {"type": "string"},
    },
    "required": [
        "faithful",
        "relevant",
        "correct",
        "child_friendly",
        "hallucination",
        "leaked_check",
        "comment",
    ],
    "additionalProperties": False,
}
SCORES = ("faithful", "relevant", "correct", "child_friendly")
SCORE_LABELS = ("Bám nguồn", "Đúng trọng tâm", "Đúng kiến thức", "Hợp với trẻ 10 tuổi")


@dataclass
class Row:
    case: dict
    got: str
    source: str
    text: str
    judged_text: str = ""  # what the judge scores: the answer, or the bridge sentence alone
    rejected: list[tuple[str, ...]] = field(default_factory=list)
    refused: list[str] = field(default_factory=list)  # the model outputs the check refused
    sources: list[str] = field(default_factory=list)
    grounding: str = ""
    judged: dict = field(default_factory=dict)


def judge(
    router, kind: str, waiting: str, said: str, evidence: list[str], text: str, after: str = ""
) -> dict:
    # Labelled lines, not JSON: an empty JSON field made the judge read "the tutor said nothing" and score
    # 1/1/1/1 although the reply was there (TQ-3; seen again on G05 of 2026-10-07).
    lines = [
        f"LOẠI LƯỢT: {kind}",
        f"CÂU GIA SƯ ĐANG CHỜ CON TRẢ LỜI: {waiting or '(không có)'}",
        f"HỌC SINH VỪA NÓI: {said}",
        "ĐOẠN NGUỒN (tài liệu đã duyệt):",
        *[f"- {e}" for e in evidence],
        f"LỜI GIA SƯ CẦN CHẤM: «{text}»",
    ]
    if after:
        lines.append(f"LỜI GIẢI THÍCH NÓI NGAY SAU (đã duyệt, không chấm): {after}")
    case = "\n".join(lines)
    request = ChatRequest(
        messages=(
            ChatMessage("system", JUDGE_SYSTEM),
            ChatMessage("user", case),
        ),
        json_schema=JUDGE_SCHEMA,
        schema_name="judgement",
        max_output_tokens=400,
        temperature=0.0,
    )
    reason = None
    for _ in range(2):  # the judge's JSON is sometimes invalid: one more try
        outcome = router.chat(ModelClass.EVAL_JUDGE, request, calls_used=0)
        if outcome.result is not None and outcome.result.data is not None:
            return outcome.result.data
        reason = outcome.fallback_reason
    return {"comment": f"không chấm được ({reason})"}


def run(only: set[str]) -> tuple[list[Row], str, int]:
    chapter = chapter_service.chapters()["math-g5-decimals"]
    order = chapter.topological_order()
    tutor_router = build_router(for_eval=True)
    judge_router = build_router(chains={ModelClass.EVAL_JUDGE: (JUDGE_MODEL,)}, for_eval=True)
    index = asyncio.run(RagService(DEMO_SCHOOL_ID, chapter_service.chapters).current(InMemoryDatabase()))
    semantic = index.embedder.name if index.embedder else "off"
    cases = yaml.safe_load(DATASET.read_text(encoding="utf-8"))["cases"]
    cases = [c for c in cases if not only or c["id"] in only]
    if index.embedder is not None:  # every question vector in one batched request (cached), not one per case
        index.embedder.embed(sorted({c["said"] for c in cases}), "RETRIEVAL_QUERY")
    rows: list[Row] = []
    calls = 0
    for case in cases:
        variant = next(t for t in chapter.node(case["node"]).theory if t.id == case["ref"])
        speaker = GroundedSpeaker(index, tutor_router, student_name="An", order=order)
        said = case["said"]
        if case["expect"] == "bridge":
            if variant.accept and phrase_regex(variant.accept).search(normalize_text(said)):
                print(
                    f"{case['id']}: the reply is right for {case['ref']}, not a bridge case", file=sys.stderr
                )
            spoken = speaker.bridge(
                said, asked=variant.ask, explanation=variant.reply, judged="chưa đúng", lead=LEAD
            )
            row = Row(case, "bridge", spoken.source, spoken.text)
            if spoken.source == "LLM":
                row.judged_text = spoken.text.removesuffix(variant.reply).strip()
            evidence, after = [variant.ask, variant.reply], variant.reply
        else:
            turn = speaker.answer(said, node_id=case["node"], pending=variant.ask, hide=[variant.reply])
            if turn.retrieval is not None and turn.retrieval.semantic != semantic:
                raise SystemExit(f"{case['id']} ran without its vector: the numbers would not be clean")
            spoken = turn.spoken
            text = spoken.text if spoken else ""
            row = Row(case, KIND[turn.kind], spoken.source if spoken else "TEMPLATE", text, judged_text=text)
            if turn.later_node:
                row.text = f"(bài sau: {chapter.node(turn.later_node).name})"
            row.grounding = turn.retrieval.grounding if turn.retrieval else ""
            evidence = (
                [s.chunk.text.replace(variant.reply, "") for s in turn.retrieval.results]
                if (turn.retrieval and spoken)
                else []
            )
            after = ""
        if spoken is not None:
            row.rejected, row.refused, row.sources = (
                list(spoken.rejected),
                list(spoken.refused),
                list(spoken.sources),
            )
        calls += speaker.calls_made
        if row.judged_text:
            kind = "CÂU_NỐI" if row.got == "bridge" else "TRẢ_LỜI"
            row.judged = judge(judge_router, kind, variant.ask, said, evidence, row.judged_text, after)
        rows.append(row)
        print(f"{case['id']} {said!r} -> {row.got} [{row.source}] {row.text}", flush=True)
        if speaker.calls_made:
            time.sleep(PAUSE_S)
    return rows, semantic, calls


def report(rows: list[Row], semantic: str, calls: int) -> str:
    def cell(text: str) -> str:
        return " ".join(str(text).split()).replace("|", "/")

    def averages(subset: list[Row]) -> list[str]:
        judged = [r for r in subset if all(k in r.judged for k in SCORES)]
        out = [f"  - Số câu được chấm: {len(judged)}/{len(subset)}"]
        for key, label in zip(SCORES, SCORE_LABELS, strict=True):
            values = [r.judged[key] for r in judged]
            out.append(f"  - {label}: {fmean(values):.2f}/5" if values else f"  - {label}: không có điểm")
        out.append(
            f"  - Bịa ngoài nguồn (giám khảo): {sum(bool(r.judged.get('hallucination')) for r in subset)}"
        )
        out.append(f"  - Lộ đáp án câu đang chờ: {sum(bool(r.judged.get('leaked_check')) for r in subset)}")
        return out

    questions = [r for r in rows if r.case["expect"] != "bridge"]
    bridges = [r for r in rows if r.case["expect"] == "bridge"]
    answers = [r for r in questions if r.got == "answer"]
    lines = [
        f"# Lời nói có căn cứ, chạy thật ({date.today().isoformat()})",
        "",
        f"`make eval-grounded` (`services/api/scripts/eval_grounded.py`), `{GROUNDED_VERSION}`, prompt "
        f"`grounded.v1.md`; bộ ca `{DATASET.relative_to(REPO_ROOT)}`. Truy xuất: `{semantic}`; gia sư: Qwen; "
        f"giám khảo: `{JUDGE_MODEL}`. Qwen được gọi {calls} lần.",
        "",
        "## Quyết định với câu con tự hỏi",
        "",
        f"- Đúng loại (trả lời, mời con tự nghĩ, bài sau, để lại cho giáo viên): "
        f"{sum(r.got == r.case['expect'] for r in questions)}/{len(questions)}.",
        f"- Trả lời bằng lời Qwen đã qua kiểm chứng: {sum(r.source == 'LLM' for r in answers)}; "
        f"trích nguyên văn đoạn nguồn (Qwen bị chặn hoặc không gọi được): "
        f"{sum(r.source == 'EXTRACT' for r in answers)}.",
        f"- Ca có câu Qwen bị bộ kiểm chứng chặn: {sum(1 for r in rows if r.rejected)}.",
        "- Giám khảo chấm các câu trả lời:",
        *averages(answers),
        "",
        "## Câu nối trước lời giải thích đã duyệt",
        "",
        f"- Câu nối do Qwen viết và qua kiểm chứng: {sum(r.source == 'LLM' for r in bridges)}/"
        f"{len(bridges)}; "
        f'còn lại dùng câu mẫu "{LEAD}".',
        "- Giám khảo chấm câu nối:",
        *averages([r for r in bridges if r.judged_text]),
        "",
        "## Từng ca",
        "",
        "| Ca | Con nói | Mong đợi | Kết quả | Nguồn | Bị chặn | Lời gia sư | Giám khảo |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        verdict = (
            " / ".join(f"{k} {r.judged[k]}" for k in SCORES if k in r.judged)
            + (" · BỊA" if r.judged.get("hallucination") else "")
            + (" · LỘ" if r.judged.get("leaked_check") else "")
            + (f" · {r.judged['comment']}" if r.judged.get("comment") else "")
        )
        rejected = "; ".join(",".join(codes) for codes in r.rejected)
        lines.append(
            f"| {r.case['id']} | {cell(r.case['said'])} | {r.case['expect']} | {r.got} | {r.source} | "
            f"{cell(rejected) or '–'} | {cell(r.text) or '–'} | {cell(verdict) or '–'} |"
        )
    refused = [
        (r.case["id"], text, ",".join(codes))
        for r in rows
        for text, codes in zip(r.refused, r.rejected, strict=False)
    ]
    if refused:
        lines += ["", "## Câu Qwen viết mà bộ kiểm chứng chặn (học sinh không nghe thấy)", ""]
        lines += [f"- {cid} ({codes}): «{cell(text)}»" for cid, text, codes in refused]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    only = set(sys.argv[1].split(",")) if len(sys.argv) > 1 and sys.argv[1] else set()
    found, model, used = run(only)
    text = report(found, model, used)
    suffix = "-partial" if only else ""
    out = REPO_ROOT / "evals/reports" / f"{date.today().isoformat()}-grounded-live{suffix}.md"
    out.write_text(text, encoding="utf-8")
    print(text)
    print(f"Report: {out.relative_to(REPO_ROOT)}")
