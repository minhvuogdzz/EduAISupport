"""BANDIT-1 (ADR-058): offline evaluation of the contextual bandit on a simulated tutoring environment.

What it measures, and what it does not. A simulator draws the child's state on an item (the same nine numbers
the bandit reads), a menu of allowed moves (the policy's own move and up to two others, none giving more help
than the policy's own) and, for the move played, whether the child's next answer is right. The chance of a
right answer depends on the state and on the move, so the best move changes with the child (a question for a
child who is thinking, a hint for one who is stuck). The simulator is declared, not measured on children: it
shows that the algorithm learns a context-dependent choice under the project's reward (DI-103) and how fast,
and that logged picks with their probabilities give an unbiased value for another policy (IPS). It says
nothing about the effect of any move on real children (the thesis limits say so).

Policies compared: ``policy`` (the policy's own move, the deployed default of AUTO-1 without a model),
``random`` (uniform on the menu), ``least-help`` (the move that gives the least help), ``bandit`` (LinUCB with
epsilon-greedy, the setting of ``TUTOR_CHOOSER=bandit``) and ``oracle`` (the best expected move, an upper
bound). Writes a JSON report; ``--out`` sets the path. Deterministic for a given ``--seed``.

Run: ``make eval-bandit``.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import statistics
from pathlib import Path

import numpy as np
from cavat.core.pedagogy import HintLevel, Move
from cavat.modules.tutor.bandit import (
    BANDIT_VERSION,
    DEFAULT_ALPHA,
    DEFAULT_EPSILON,
    HELP_COST,
    MAX_HELP,
    BanditChooser,
    LinUCB,
    arm_of,
    context_vector,
)
from cavat.modules.tutor.chooser import help_of
from cavat.modules.tutor.contracts import PolicyDecision
from cavat.modules.tutor.policy import MoveOption

REPO = Path(__file__).resolve().parents[3]
DEFAULT_OUT = REPO / "docs" / "thesis" / "data" / "bandit-eval.json"
LAST_QUARTER = ("regret_last_quarter", "reward_last_quarter", "best_move_rate_last_quarter")

PROBE = PolicyDecision(move=Move.PROBE)
H1 = PolicyDecision(move=Move.HINT, level=HintLevel.H1)
H2 = PolicyDecision(move=Move.HINT, level=HintLevel.H2)
H3 = PolicyDecision(move=Move.HINT, level=HintLevel.H3)

# The menus the policy offers on a turn (AUTO-1): its own move first, then moves giving no more help.
MENUS = (
    (PROBE, H1),  # after a first wrong answer: ask how, or the first hint
    (H2, PROBE, H1),  # a second wrong answer, the policy's rung is H2
    (H3, H2, H1),  # stuck: the next rung or a smaller step
)

# Hidden truth: the log-odds of a right next answer by arm, over the context
# (bias, attempts, hints, top_rung, unproductive, help_requests, discouraged, asked_how, repeated_mistake).
TRUTH = {
    "PROBE": np.array([2.2, -1.0, -0.3, -0.3, -4.5, -1.2, -2.0, 0.4, -1.5]),
    "HINT:1": np.array([0.2, 0.4, 0.2, -0.5, 1.5, 0.8, -0.4, 0.3, 0.4]),
    "HINT:2": np.array([-0.9, 0.8, 0.6, 0.2, 3.5, 1.5, 1.2, 0.2, 1.5]),
    "HINT:3": np.array([-1.8, 1.0, 0.8, 0.8, 5.0, 2.0, 2.0, 0.2, 2.0]),
}


def draw_situation(rng: random.Random) -> dict[str, int | bool]:
    attempts = min(1 + int(rng.expovariate(0.8)), 5)
    hints = rng.randint(0, min(attempts - 1, 3))
    unproductive = min(rng.randint(0, attempts), 3) if attempts > 1 else 0
    return {
        "so_lan_tra_loi": attempts,
        "so_goi_y_da_nhan": hints,
        "bac_goi_y_cao_nhat": rng.randint(0, 2 * hints) if hints else 0,
        "luot_chua_tien_bo": unproductive,
        "so_lan_xin_goi_y": rng.randint(0, 2) if unproductive else 0,
        "dau_hieu_nan": 1 if rng.random() < 0.08 + 0.1 * unproductive else 0,
        "co_da_hoi_cach_lam": rng.random() < 0.5,
        "loi_lap_lai_nhieu_nhat": rng.randint(0, 2) if attempts > 1 else 0,
    }


def p_right(arm: str, x: tuple[float, ...]) -> float:
    return 1.0 / (1.0 + math.exp(-float(TRUTH[arm] @ np.asarray(x))))


def value(arm: str, x: tuple[float, ...], help_: int) -> float:
    """Expected reward of a move: the chance of a right answer less the help (DI-103, no partial credit)."""
    return p_right(arm, x) - HELP_COST * help_ / MAX_HELP


def menu_of(decisions: tuple[PolicyDecision, ...]) -> tuple[MoveOption, ...]:
    return tuple(MoveOption("ABC"[i], d) for i, d in enumerate(decisions))


def best_index(menu: tuple[MoveOption, ...], x: tuple[float, ...]) -> int:
    scores = [value(str(arm_of(o.decision)), x, help_of(o.decision)) for o in menu]
    return scores.index(max(scores))


def run(policy: str, rounds: int, seed: int, *, alpha: float, epsilon: float) -> dict[str, list[float]]:
    rng = random.Random(seed)
    outcomes = random.Random(seed + 1)
    model = LinUCB(alpha=alpha)
    regret: list[float] = []
    reward: list[float] = []
    log: list[dict[str, float | str | int]] = []
    for t in range(rounds):
        sit = draw_situation(rng)
        x = context_vector(sit)
        menu = menu_of(MENUS[rng.randrange(len(MENUS))])
        best = best_index(menu, x)
        propensity = 1.0
        if policy == "policy":
            index = 0
        elif policy == "random":
            index = rng.randrange(len(menu))
            propensity = 1 / len(menu)
        elif policy == "least-help":
            index = min(range(len(menu)), key=lambda i: (help_of(menu[i].decision), i))
        elif policy == "oracle":
            index = best
        elif policy == "bandit":
            pick = BanditChooser(model, seed_key=f"{seed}", epsilon=epsilon).choose(
                menu=menu, stem=str(t), last_tutor="", said="", turn=t, situation=sit
            )
            assert pick is not None and pick.propensity is not None
            index = next(i for i, o in enumerate(menu) if o.id == pick.option_id)
            propensity = pick.propensity
        else:
            raise ValueError(policy)
        decision = menu[index].decision
        arm, help_ = str(arm_of(decision)), help_of(decision)
        right = outcomes.random() < p_right(arm, x)
        r = (1.0 if right else 0.0) - HELP_COST * help_ / MAX_HELP
        model.update(arm, x, r)
        reward.append(r)
        regret.append(
            value(str(arm_of(menu[best].decision)), x, help_of(menu[best].decision)) - value(arm, x, help_)
        )
        log.append({"t": t, "arm": arm, "reward": r, "propensity": propensity, "best": best, "index": index})
    return {"regret": regret, "reward": reward, "log": log}  # type: ignore[dict-item]


def ci95(values: list[float]) -> tuple[float, float]:
    mean = statistics.fmean(values)
    half = 1.96 * statistics.stdev(values) / math.sqrt(len(values)) if len(values) > 1 else 0.0
    return mean, half


def curve(per_seed: list[list[float]], step: int) -> list[float]:
    """Mean regret per round, in blocks of ``step`` rounds, averaged over seeds."""
    rounds = len(per_seed[0])
    return [
        statistics.fmean(statistics.fmean(s[i : i + step]) for s in per_seed) for i in range(0, rounds, step)
    ]


def ips_check(seed: int, rounds: int, epsilon: float) -> dict[str, float]:
    """Value of two target policies from the log of an epsilon-greedy bandit, by inverse propensity scoring.

    The target "always take the move that gives the least help" and the target "the oracle" are both deter-
    ministic, so a logged pick counts when it is the move the target would take, weighted by 1 / probability
    of the pick. The truth is the expected reward of the target on the same contexts."""
    rng = random.Random(seed)
    outcomes = random.Random(seed + 7)
    model = LinUCB(alpha=DEFAULT_ALPHA)
    ips = {"least-help": 0.0, "oracle": 0.0}
    truth = {"least-help": 0.0, "oracle": 0.0}
    for t in range(rounds):
        sit = draw_situation(rng)
        x = context_vector(sit)
        menu = menu_of(MENUS[rng.randrange(len(MENUS))])
        pick = BanditChooser(model, seed_key=f"ips{seed}", epsilon=epsilon).choose(
            menu=menu, stem=str(t), last_tutor="", said="", turn=t, situation=sit
        )
        assert pick is not None and pick.propensity is not None
        index = next(i for i, o in enumerate(menu) if o.id == pick.option_id)
        decision = menu[index].decision
        arm, help_ = str(arm_of(decision)), help_of(decision)
        r = (1.0 if outcomes.random() < p_right(arm, x) else 0.0) - HELP_COST * help_ / MAX_HELP
        model.update(arm, x, r)
        targets = {
            "least-help": min(range(len(menu)), key=lambda i: (help_of(menu[i].decision), i)),
            "oracle": best_index(menu, x),
        }
        for name, target in targets.items():
            truth[name] += value(str(arm_of(menu[target].decision)), x, help_of(menu[target].decision))
            if index == target:
                ips[name] += r / pick.propensity
    return {
        **{f"ips_{k}": v / rounds for k, v in ips.items()},
        **{f"truth_{k}": v / rounds for k, v in truth.items()},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--rounds", type=int, default=3000)
    parser.add_argument("--seeds", type=int, default=30)
    parser.add_argument("--seed", type=int, default=20261104)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    # how often each arm is the best one: a bandit has something to learn only if it varies
    rng = random.Random(args.seed)
    best_arm: dict[str, int] = {}
    for _ in range(5000):
        x = context_vector(draw_situation(rng))
        menu = menu_of(MENUS[rng.randrange(len(MENUS))])
        arm = str(arm_of(menu[best_index(menu, x)].decision))
        best_arm[arm] = best_arm.get(arm, 0) + 1

    settings = {
        "policy": dict(alpha=0.0, epsilon=0.0),
        "random": dict(alpha=0.0, epsilon=0.0),
        "least-help": dict(alpha=0.0, epsilon=0.0),
        "bandit": dict(alpha=DEFAULT_ALPHA, epsilon=DEFAULT_EPSILON),
        "bandit-greedy": dict(alpha=DEFAULT_ALPHA, epsilon=0.0),
        "oracle": dict(alpha=0.0, epsilon=0.0),
    }
    rows: dict[str, dict[str, object]] = {}
    for name, cfg in settings.items():
        label = "bandit" if name.startswith("bandit") else name
        runs = [run(label, args.rounds, args.seed + s, **cfg) for s in range(args.seeds)]
        last = args.rounds // 4
        regret_total = [sum(r["regret"]) for r in runs]
        regret_last = [statistics.fmean(r["regret"][-last:]) for r in runs]
        reward_last = [statistics.fmean(r["reward"][-last:]) for r in runs]
        hits = [
            statistics.fmean(1.0 if e["index"] == e["best"] else 0.0 for e in r["log"][-last:])  # type: ignore[index]
            for r in runs
        ]
        rows[name] = {
            "regret_total": ci95(regret_total),
            "regret_last_quarter": ci95(regret_last),
            "reward_last_quarter": ci95(reward_last),
            "best_move_rate_last_quarter": ci95(hits),
            "regret_curve": curve([r["regret"] for r in runs], 100),
        }
    ips = [ips_check(args.seed + 100 + s, args.rounds, 0.3) for s in range(args.seeds)]
    ips_summary = {k: ci95([row[k] for row in ips]) for k in ips[0]}
    report = {
        "version": BANDIT_VERSION,
        "rounds": args.rounds,
        "seeds": args.seeds,
        "alpha": DEFAULT_ALPHA,
        "epsilon": DEFAULT_EPSILON,
        "help_cost": HELP_COST,
        "best_arm_share": {k: v / 5000 for k, v in sorted(best_arm.items())},
        "policies": rows,
        "ips_check": ips_summary,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"{BANDIT_VERSION}: {args.rounds} rounds, {args.seeds} seeds (mean ± 95% CI)")
    print("best arm share:", {k: round(v / 5000, 2) for k, v in sorted(best_arm.items())})
    print(
        f"{'policy':<14}{'regret total':>20}{'regret last 1/4':>20}{'reward last 1/4':>20}{'best move':>14}"
    )
    for name, row in rows.items():
        total = "{:.1f} ± {:.1f}".format(*row["regret_total"])  # type: ignore[misc]
        cells = ["{:.3f} ± {:.3f}".format(*row[k]) for k in LAST_QUARTER]  # type: ignore[misc]
        print(f"{name:<14}{total:>20}{cells[0]:>20}{cells[1]:>20}{cells[2]:>14}")
    print("IPS from the log of the bandit (epsilon 0.3):")
    for name in ("least-help", "oracle"):
        est, truth = ips_summary[f"ips_{name}"], ips_summary[f"truth_{name}"]
        print(f"  {name:<11} IPS {est[0]:.3f} ± {est[1]:.3f}   truth {truth[0]:.3f}")
    print(f"report: {args.out}")


if __name__ == "__main__":
    main()
