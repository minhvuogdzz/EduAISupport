"""Talk with the English tutor in the terminal: `make teach-en` (ENG-5b).

Unit 11 "Family time", offline and with templates only; nothing is stored. The loop is built exactly as an
English session builds it (``english_session.loop_options``: the English validator and the rule that keeps a
question of another subject out of the lesson). "gợi ý" asks for a hint while a question is open, "điểm"
shows the node map, "thoát" quits.
"""

from __future__ import annotations

from datetime import UTC, datetime

from cavat.modules.session.chapter_service import chapters
from cavat.modules.teaching.loop import Awaiting, TeachingLoop
from cavat.modules.tutor.english_session import loop_options
from teach_cli import HINT, MAP, QUIT, node_map, show

UNIT = "eng-g5-u11-family-time"


def main() -> None:
    unit = chapters("english")[UNIT]
    loop = TeachingLoop(unit, "cli-en", **loop_options(unit))
    print(f"Unit: {unit.package.title}. Gõ 'gợi ý', 'điểm' hoặc 'thoát' bất cứ lúc nào.")
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
