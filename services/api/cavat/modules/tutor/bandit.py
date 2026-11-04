"""A contextual bandit picks one of the moves the policy allows (BANDIT-1, ADR-058, DI-101 to DI-104).

Where Qwen reads a menu and names a move (``chooser.ModelChooser``, AUTO-1), the bandit learns from what
the child does next. The menu is still the policy's (``policy.options``: at most three moves, none giving
more help than the policy's own, CLAUDE.md rule 1), and ``policy.accept`` still plays the pick only when it
is on that menu. Nothing about the answer reaches the bandit (rule 2): the context is the counts of
``chooser.situation``.

* **Arm**: the kind of move and its rung (``PROBE``, ``HINT:2``...), so the same arm means the same thing on
  every menu. A menu holding a move that is not learnable (``VERIFY``, ``CONFIRM_ADVANCE``) is passed to the
  fallback chooser, or to the policy's own move.
* **Context** ``x``: nine numbers in [0, 1] (``context_vector``).
* **Reward** ``r``: 1 for the child's next graded answer correct, 0.5 partly, 0 wrong, less ``HELP_COST``
  times the help of the move over 7 (``reward_of``). A hint that works is worth less than a question that
  makes the child think it through.
* **Model**: LinUCB with one ridge regression per arm (Li, Chu, Langford, Schapire, 2010). It keeps the
  sums ``S = sum x x^T``, ``s = sum r x`` and the count ``n``: additive, so the order of the rewards does not
  matter and the state is a fold over ``BANDIT_REWARD`` events, never written by a model (rule 3).
* **Pick**: the arm with the highest optimistic score, with probability ``1 - epsilon``; any menu move with
  probability ``epsilon / k``. The probability of the pick is recorded (``Choice.propensity``), which makes
  the log usable for off-policy evaluation. Ties go to the policy's own move, so a bandit that has learned
  nothing plays what the policy plays.

Every pick is recorded (``MOVE_CHOSEN``) and replayed from the record (``RecordedChooser``): a replay never
asks the bandit again.
"""

from __future__ import annotations

import hashlib
import math
import random
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

import numpy as np

from cavat.core.pedagogy import Move, Outcome
from cavat.modules.tutor.chooser import Choice, MoveChooser, Situation, help_of
from cavat.modules.tutor.contracts import PolicyDecision
from cavat.modules.tutor.policy import MoveOption

BANDIT_VERSION = "contextual-bandit/0.1.0"

# DI-103: the weight of the help in the reward. A hint that gets the child to a right answer scores 1 - 0.3
# x rung / 7, so the bandit prefers the smaller help that works.
HELP_COST = 0.3
MAX_HELP = 7
# DI-102: LinUCB's exploration width, the ridge, and the share of picks made at random on the menu.
DEFAULT_ALPHA = 0.5
DEFAULT_RIDGE = 1.0
DEFAULT_EPSILON = 0.1

FEATURES = (
    "bias",
    "attempts",
    "hints",
    "top_rung",
    "unproductive",
    "help_requests",
    "discouraged",
    "asked_how",
    "repeated_mistake",
)
DIM = len(FEATURES)

_LEARNABLE = frozenset({Move.PROBE, Move.OFFER_CHOICE, Move.HINT, Move.COGNITIVE_CONFLICT, Move.EXPLAIN})


def _unit(value: object, cap: int) -> float:
    return min(max(float(value or 0), 0.0), float(cap)) / cap


def context_vector(situation: Situation | None) -> tuple[float, ...]:
    """The child's state on the item as nine numbers in [0, 1] (DI-101): counts only, never an answer."""
    s = situation or {}
    return (
        1.0,
        _unit(s.get("so_lan_tra_loi"), 5),
        _unit(s.get("so_goi_y_da_nhan"), 4),
        _unit(s.get("bac_goi_y_cao_nhat"), 7),
        _unit(s.get("luot_chua_tien_bo"), 4),
        _unit(s.get("so_lan_xin_goi_y"), 3),
        _unit(s.get("dau_hieu_nan"), 3),
        1.0 if s.get("co_da_hoi_cach_lam") else 0.0,
        _unit(s.get("loi_lap_lai_nhieu_nhat"), 3),
    )


def arm_of(d: PolicyDecision) -> str | None:
    """The arm of a move, or None when the bandit may not choose it (a move that closes or confirms)."""
    if d.move not in _LEARNABLE:
        return None
    if d.move in (Move.HINT, Move.EXPLAIN):
        return f"{d.move.value}:{int(d.level) if d.level is not None else 1}"
    return d.move.value


def reward_of(outcome: Outcome | str, help_: int) -> float:
    """What the next graded answer was worth (DI-103): right 1, partly right 0.5, wrong 0, less the help."""
    name = str(getattr(outcome, "value", outcome))
    base = {Outcome.CORRECT.value: 1.0, Outcome.PARTIAL.value: 0.5}.get(name, 0.0)
    return round(base - HELP_COST * min(max(help_, 0), MAX_HELP) / MAX_HELP, 6)


class LinUCB:
    """One ridge regression per arm over the context (Li et al., 2010), kept as additive sums."""

    def __init__(self, *, alpha: float = DEFAULT_ALPHA, ridge: float = DEFAULT_RIDGE) -> None:
        self.alpha, self.ridge = alpha, ridge
        self._sxx: dict[str, np.ndarray] = {}
        self._sxr: dict[str, np.ndarray] = {}
        self._n: dict[str, int] = {}

    def update(self, arm: str, context: Sequence[float], reward: float) -> None:
        x = np.asarray(context, dtype=float)
        self._sxx[arm] = self._sxx.get(arm, np.zeros((DIM, DIM))) + np.outer(x, x)
        self._sxr[arm] = self._sxr.get(arm, np.zeros(DIM)) + reward * x
        self._n[arm] = self._n.get(arm, 0) + 1

    def count(self, arm: str) -> int:
        return self._n.get(arm, 0)

    def score(self, arm: str, context: Sequence[float]) -> tuple[float, float]:
        """(expected reward, exploration bonus) of an arm on a context."""
        x = np.asarray(context, dtype=float)
        a = self.ridge * np.eye(DIM) + self._sxx.get(arm, 0.0)
        b = self._sxr.get(arm, np.zeros(DIM))
        theta = np.linalg.solve(a, b)
        bonus = self.alpha * math.sqrt(max(float(x @ np.linalg.solve(a, x)), 0.0))
        return float(theta @ x), bonus

    def ucb(self, arm: str, context: Sequence[float]) -> float:
        mean, bonus = self.score(arm, context)
        return mean + bonus

    # -- the state as the additive increments a store keeps (a replayable fold, DI-104)

    def stats(self, arm: str) -> dict[str, float]:
        flat: dict[str, float] = {"n": float(self._n.get(arm, 0))}
        sxx, sxr = self._sxx.get(arm), self._sxr.get(arm)
        for i in range(DIM):
            flat[f"b_{i}"] = float(sxr[i]) if sxr is not None else 0.0
            for j in range(DIM):
                flat[f"a_{i}_{j}"] = float(sxx[i, j]) if sxx is not None else 0.0
        return flat

    @classmethod
    def from_stats(
        cls,
        per_arm: Mapping[str, Mapping[str, float]],
        *,
        alpha: float = DEFAULT_ALPHA,
        ridge: float = DEFAULT_RIDGE,
    ) -> LinUCB:
        model = cls(alpha=alpha, ridge=ridge)
        for arm, flat in per_arm.items():
            model._n[arm] = int(flat.get("n", 0))
            model._sxr[arm] = np.array([float(flat.get(f"b_{i}", 0.0)) for i in range(DIM)])
            model._sxx[arm] = np.array(
                [[float(flat.get(f"a_{i}_{j}", 0.0)) for j in range(DIM)] for i in range(DIM)]
            )
        return model


def increments(context: Sequence[float], reward: float) -> dict[str, float]:
    """The ``$inc`` of one reward: ``n``, ``b`` and the outer product of the context."""
    x = [float(v) for v in context]
    inc = {"n": 1.0}
    for i in range(DIM):
        inc[f"b_{i}"] = reward * x[i]
        for j in range(DIM):
            inc[f"a_{i}_{j}"] = x[i] * x[j]
    return inc


def fold(
    rewards: Iterable[Mapping[str, object]], *, alpha: float = DEFAULT_ALPHA, ridge: float = DEFAULT_RIDGE
) -> LinUCB:
    """The bandit as a pure function of its ``BANDIT_REWARD`` payloads (CLAUDE.md rule 3)."""
    model = LinUCB(alpha=alpha, ridge=ridge)
    for r in rewards:
        model.update(str(r["arm"]), r["context"], float(r["reward"]))  # type: ignore[arg-type]
    return model


def pick_probabilities(greedy: int, size: int, epsilon: float) -> list[float]:
    """The probability of each move of a menu: epsilon spread over all, the rest on the greedy one."""
    p = [epsilon / size] * size
    p[greedy] += 1.0 - epsilon
    return p


@dataclass
class BanditChooser:
    """Picks the move of the menu with the best optimistic score, learned from the school's past answers.

    ``seed_key`` (the session) and the turn seed the draw of the exploration, so one session, one turn, one
    menu always give the same pick. ``fallback`` reads the menus the bandit does not learn from."""

    model: LinUCB
    seed_key: str = ""
    epsilon: float = DEFAULT_EPSILON
    fallback: MoveChooser | None = None

    @property
    def calls_made(self) -> int:
        return getattr(self.fallback, "calls_made", 0)

    def choose(
        self,
        *,
        menu: Sequence[MoveOption],
        stem: str,
        last_tutor: str,
        said: str,
        turn: int,
        situation: Situation | None = None,
    ) -> Choice | None:
        if len(menu) < 2:
            return None
        arms = [arm_of(o.decision) for o in menu]
        if any(a is None for a in arms):
            if self.fallback is None:
                return None
            return self.fallback.choose(
                menu=menu, stem=stem, last_tutor=last_tutor, said=said, turn=turn, situation=situation
            )
        x = context_vector(situation)
        scores = [self.model.ucb(str(a), x) for a in arms]
        best = max(scores)
        # ties go to the earliest move of the menu: "A", the policy's own
        greedy = next(i for i, s in enumerate(scores) if s >= best - 1e-9)
        p = pick_probabilities(greedy, len(menu), self.epsilon)
        digest = hashlib.sha256(f"{self.seed_key}|{turn}|{stem}".encode()).digest()
        draw = random.Random(int.from_bytes(digest[:8], "big")).random()
        index, acc = len(menu) - 1, 0.0
        for i, pi in enumerate(p):
            acc += pi
            if draw < acc:
                index = i
                break
        explored = index != greedy
        mean, bonus = self.model.score(str(arms[index]), x)
        why = "thử một nước khác để học thêm" if explored else "nước có điểm kỳ vọng cao nhất"
        reason = (
            f"Bộ chọn học từ kết quả các lượt trước: {why}"
            f" (điểm {mean + bonus:.2f}, giúp mức {help_of(menu[index].decision)})."
        )
        return Choice(
            menu[index].id,
            reason[:160],
            source="BANDIT",
            arm=str(arms[index]),
            propensity=round(p[index], 6),
            context=x,
            scores={str(a): round(s, 6) for a, s in zip(arms, scores, strict=True)},
        )
