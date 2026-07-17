"""Scoring. Implements the pre-registered analysis in METHODOLOGY.md.

The two headline numbers are deliberately kept apart:

  behavior    accuracy on the canonical prompt only (paraphrase 0)
              -> "did the thing I type every day get worse?"
  capability  best-of-N across all frozen paraphrases
              -> "can the model still do this at all?"

Reporting only the first is how you end up announcing that a model got dumber
when it actually just got chattier. Reporting only the second hides a change
users genuinely feel. Both ship, always, side by side.
"""

from __future__ import annotations

import random
from collections import defaultdict
from dataclasses import asdict, dataclass

from .graders import Verdict


@dataclass
class Metric:
    value: float
    lo: float
    hi: float
    n: int

    def as_dict(self) -> dict:
        return asdict(self)

    def __repr__(self) -> str:
        return f"{self.value:.3f} [{self.lo:.3f}, {self.hi:.3f}] (n={self.n})"


def bootstrap(
    values: list[float], iters: int = 10_000, seed: int = 0, alpha: float = 0.05
) -> Metric:
    """Percentile bootstrap CI.

    Rule 7: an API is nondeterministic even at temperature 0. A single number
    per day will manufacture drift out of sampling noise. Nothing in this repo
    is called a change unless intervals separate.
    """
    if not values:
        return Metric(float("nan"), float("nan"), float("nan"), 0)
    n = len(values)
    mean = sum(values) / n
    if n == 1:
        return Metric(mean, float("nan"), float("nan"), 1)
    rng = random.Random(seed)
    means = []
    for _ in range(iters):
        s = sum(values[rng.randrange(n)] for _ in range(n)) / n
        means.append(s)
    means.sort()
    lo = means[int((alpha / 2) * iters)]
    hi = means[min(iters - 1, int((1 - alpha / 2) * iters))]
    return Metric(mean, lo, hi, n)


@dataclass
class Sample:
    """One graded response."""

    task_id: str
    family: str
    paraphrase: int
    sample: int
    verdict: Verdict
    expected: object
    extracted: object
    task_class: str  # "prime" / "semiprime" / etc — the positive/negative class
    format_flags: dict


def _correct(s: Sample) -> bool:
    return s.verdict == Verdict.CORRECT


def score_run(samples: list[Sample], seed: int = 0) -> dict:
    """Compute the full pre-registered metric set for one model on one day."""
    out: dict = {}

    canonical = [s for s in samples if s.paraphrase == 0]

    # --- behavior: canonical prompt only ------------------------------------
    out["behavior"] = bootstrap([1.0 if _correct(s) else 0.0 for s in canonical], seed=seed).as_dict()

    # --- capability: best-of-N across paraphrases ---------------------------
    # A task counts as within-capability if ANY frozen paraphrase, on ANY
    # sample, produced a correct answer. Rule 3: a capability that hides behind
    # one phrasing and appears behind another has drifted, not degraded.
    by_task: dict[str, list[Sample]] = defaultdict(list)
    for s in samples:
        by_task[s.task_id].append(s)
    cap = [1.0 if any(_correct(x) for x in v) else 0.0 for v in by_task.values()]
    out["capability"] = bootstrap(cap, seed=seed).as_dict()

    # --- balanced accuracy (Rule 1) -----------------------------------------
    # THE fix for the 2023 prime trap. Raw accuracy over an unbalanced set lets
    # an answer-bias shift impersonate a capability collapse. We report per-class
    # recall and their mean, and we report raw accuracy too — but only so the
    # gap between them is visible.
    pos = [1.0 if _correct(s) else 0.0 for s in canonical if s.expected is True]
    neg = [1.0 if _correct(s) else 0.0 for s in canonical if s.expected is False]
    if pos and neg:
        tpr = bootstrap(pos, seed=seed)
        tnr = bootstrap(neg, seed=seed)
        out["recall_positive"] = tpr.as_dict()
        out["recall_negative"] = tnr.as_dict()
        out["balanced_accuracy"] = bootstrap(
            [(tpr.value + tnr.value) / 2], seed=seed
        ).as_dict()
        out["balanced_accuracy"]["value"] = (tpr.value + tnr.value) / 2

        # --- answer bias --------------------------------------------------
        # The model's overall yes-rate, regardless of correctness. If this moves
        # and balanced accuracy holds, the finding is "the model's prior
        # shifted" — a real result, and a completely different one from
        # "the model got worse". The 2023 paper could not tell these apart.
        answered = [s for s in canonical if s.extracted is not None]
        if answered:
            yes_rate = sum(1.0 for s in answered if s.extracted is True) / len(answered)
            out["answer_bias_yes_rate"] = {"value": yes_rate, "n": len(answered)}
            out["answer_bias_baseline"] = {
                "value": sum(1.0 for s in canonical if s.expected is True) / len(canonical),
                "note": "ground-truth positive rate; task set is balanced so this is 0.5 by construction",
            }

    # --- unparseable, tracked separately and never folded into wrong --------
    out["unparseable_rate"] = bootstrap(
        [1.0 if s.verdict == Verdict.UNPARSEABLE else 0.0 for s in canonical], seed=seed
    ).as_dict()
    out["refusal_rate"] = bootstrap(
        [1.0 if s.format_flags.get("refusal_marker") else 0.0 for s in canonical], seed=seed
    ).as_dict()

    # --- format drift (Rule 2), observed, never scored ----------------------
    out["format_drift"] = {
        "mean_response_chars": (
            sum(s.format_flags.get("chars", 0) for s in canonical) / len(canonical)
            if canonical else 0
        ),
        "fenced_rate": (
            sum(1.0 for s in canonical if s.format_flags.get("fenced")) / len(canonical)
            if canonical else 0
        ),
        "verbose_rate": (
            sum(1.0 for s in canonical if s.format_flags.get("verbose")) / len(canonical)
            if canonical else 0
        ),
    }

    out["n_samples"] = len(samples)
    out["n_tasks"] = len(by_task)
    return out


def compare(a: dict, b: dict, key: str) -> dict:
    """Compare one metric across two runs.

    Rule 7: nothing is a change unless the intervals separate. This function is
    the only sanctioned way to say the word "drift" in this repo.
    """
    ma, mb = a.get(key), b.get(key)
    if not ma or not mb:
        return {"verdict": "missing", "key": key}
    separated = ma["hi"] < mb["lo"] or mb["hi"] < ma["lo"]
    delta = mb["value"] - ma["value"]
    return {
        "key": key,
        "from": ma["value"],
        "to": mb["value"],
        "delta": delta,
        "intervals_separate": separated,
        "verdict": (
            "no significant change"
            if not separated
            else ("improved" if delta > 0 else "declined")
        ),
    }


def interpret(before: dict, after: dict) -> str:
    """Turn two runs into the one sentence we are allowed to publish.

    This function is where Rule 3 becomes non-negotiable: 'behavior' falling
    while 'capability' holds MUST be reported with the words 'behavior drift'.
    """
    beh = compare(before, after, "behavior")
    cap = compare(before, after, "capability")

    if not beh["intervals_separate"] and not cap["intervals_separate"]:
        return (
            "No drift detected. Neither behavior nor capability moved beyond "
            "sampling noise. (Published with the same prominence as any other "
            "result — Rule 6.)"
        )
    if beh["intervals_separate"] and not cap["intervals_separate"]:
        return (
            f"BEHAVIOR DRIFT: accuracy on the canonical prompt {beh['verdict']} "
            f"({beh['from']:.3f} -> {beh['to']:.3f}), but capability held under "
            f"rephrasing. The model can still do the task; it stopped doing it "
            f"when asked the usual way. This is NOT evidence of degradation."
        )
    if cap["intervals_separate"]:
        return (
            f"CAPABILITY CHANGE: best-of-N across all frozen paraphrases "
            f"{cap['verdict']} ({cap['from']:.3f} -> {cap['to']:.3f}). The "
            f"ability did not reappear under any phrasing we tried. This is the "
            f"only condition under which this repo uses the word 'degradation' "
            f"— and it still says nothing about why."
        )
    return "Inconclusive."
