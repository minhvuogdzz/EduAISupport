"""Talk with the teaching loop in the terminal: `make teach` (M1-6).

Offline and with templates only; nothing is stored. Type the answer as a student would. "gợi ý" asks
for a hint while a question is open, "điểm" shows the node map, "thoát" quits.
"""

from __future__ import annotations

from datetime import UTC, datetime

from cavat.config import REPO_ROOT
from cavat.modules.content.chapter_package import load_chapter
from cavat.modules.teaching.loop import Awaiting, TeachingLoop, TeachTurn

CHAPTER = REPO_ROOT / "docs/pedagogy/math-g5/chuong-so-thap-phan/chapter.yaml"
QUIT, HINT, MAP = {"thoát", "thoat", "exit", "quit"}, {"gợi ý", "goi y"}, {"điểm", "diem"}


def show(turn: TeachTurn) -> None:
    for m in turn.messages:
        print(f"\nCô [{m.kind.value.lower()}]: {m.text}")
    if turn.choice_open:
        print("   (gõ 'gợi ý' để cô gợi ý thêm, hoặc trả lời lại)")


def node_map(loop: TeachingLoop) -> None:
    for node_id, state in loop.projection().nodes.items():
        mark = "đã qua" if state.passed_at is not None else "đang học" if state.mastery is not None else "chưa học"
        score = "--" if state.mastery is None else f"{state.mastery:.1f}"
        missing = ", ".join(state.missing) if state.passed_at is None and state.mastery is not None else ""
        print(f"  {loop.chapter.node(node_id).name:<40} {mark:<9} M={score:>5}  {missing}")


def main() -> None:
    loop = TeachingLoop(load_chapter(CHAPTER), "cli")
    print(f"Chương: {loop.chapter.package.title}. Gõ 'gợi ý', 'điểm' hoặc 'thoát' bất cứ lúc nào.")
    turn = loop.start(datetime.now(UTC))
    show(turn)
    while turn.awaiting != Awaiting.NOTHING:
        try:
            text = input("\nCon: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if text.lower() in QUIT:
            break
        if text.lower() in MAP:
            node_map(loop)
            continue
        if text.lower() in HINT and turn.awaiting == Awaiting.ANSWER:
            turn = loop.on_hint_request(datetime.now(UTC))
        else:
            turn = loop.on_student(text, datetime.now(UTC))
        show(turn)
    print()
    node_map(loop)


if __name__ == "__main__":
    main()
