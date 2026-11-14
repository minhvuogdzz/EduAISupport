"""Mathematics projection golden (ENG-4, english-module-rules M3 and E3): byte for byte as before ENG-4.

``golden/math-projection-before-eng4.json`` was written by ``golden/make_math_projection_golden.py`` on
the commit before ENG-4 (6ac53b9): the event logs of seven scripted learners taught the decimals chapter by
the teaching loop, offline, and five synthetic logs that touch every branch of the projector (every error
class, misconceptions, guesses, LLM labels, voice answers with a low ASR confidence). Each log is projected
again with the code of today and the canonical JSON of the projection must hash to the stored value.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pytest
from cavat.modules.assessment.projector import MASTERY_POLICY_VERSION, project_chapter
from cavat.modules.content.chapter_package import load_chapter

ROOT = Path(__file__).resolve().parents[3]
GOLDEN = json.loads((Path(__file__).parent / "golden/math-projection-before-eng4.json").read_text("utf-8"))
CHAPTER = load_chapter(ROOT / GOLDEN["chapter"])


@dataclass(frozen=True)
class Ev:
    event_type: str
    payload: dict
    session_id: str
    occurred_at: datetime


def events(log: dict) -> list[Ev]:
    return [
        Ev(e["event_type"], e["payload"], e["session_id"], datetime.fromisoformat(e["occurred_at"]))
        for e in log["events"]
    ]


def digest(projection) -> str:
    canonical = json.dumps(projection.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def test_the_mathematics_policy_keeps_its_version():
    assert GOLDEN["policy_version"] == MASTERY_POLICY_VERSION == "node-mastery/0.3.0"
    assert CHAPTER.package.subject == "math"


@pytest.mark.parametrize("log", GOLDEN["logs"], ids=lambda log: f"{log['kind']}-{log['seed']}")
def test_a_stored_mathematics_log_projects_byte_for_byte_as_before(log):
    projection = project_chapter(events(log), CHAPTER)
    summary = {
        n.node_id: [n.mastery, n.level, n.passed_at, sum(e.node_id == n.node_id for e in projection.evidence)]
        for n in projection.nodes.values()
    }
    assert summary == log["summary"]
    assert projection.policy_version == "node-mastery/0.3.0"
    assert digest(projection) == log["sha256"]


def _generator():
    """The script that wrote the golden, imported to replay its scripted learners (it writes nothing here)."""
    spec = importlib.util.spec_from_file_location(
        "golden_maker", Path(__file__).parent / "golden/make_math_projection_golden.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("golden_maker", module)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "log",
    [log for log in GOLDEN["logs"] if log["kind"] == "teaching-loop"],
    ids=lambda log: f"seed-{log['seed']}",
)
def test_the_mathematics_teaching_loop_writes_the_same_events_as_before(log):
    """The scripted learners of the golden study the chapter again with the code of today (the checker
    dispatch of ENG-4 included): every event, in order, is the one written before ENG-4."""
    maker = _generator()
    loop = maker.converse(maker.Learner(log["seed"], log["skill"]), f"golden-{log['seed']}")
    assert [maker.event_json(e) for e in loop.events] == log["events"]
