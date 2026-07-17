"""Deterministic graders. No LLM judge appears anywhere in this file, by design
(METHODOLOGY.md Rule 4): a judge that drifts cannot measure drift.

Every grader returns a Result whose `verdict` is one of:

  CORRECT     — extracted answer is semantically right
  INCORRECT   — extracted answer is semantically wrong
  UNPARSEABLE — no answer could be extracted (refusal, waffle, empty)

UNPARSEABLE is deliberately NOT folded into INCORRECT. A model that becomes
chattier and stops emitting a clean yes/no has changed its *format*, and
collapsing that into "wrong" is exactly the mistake that made the 2023 GPT-4
paper measure markdown fences and report it as coding ability (Rule 2).
Callers decide how to treat it; the scorer reports it as its own series.
"""

from __future__ import annotations

import ast
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class Verdict(str, Enum):
    CORRECT = "correct"
    INCORRECT = "incorrect"
    UNPARSEABLE = "unparseable"


@dataclass
class Result:
    verdict: Verdict
    extracted: object = None
    # Free-form, never used in scoring — for humans re-auditing a run by hand.
    note: str = ""
    # Format observations, tracked as their own metric and never mixed into
    # capability (Rule 2).
    format_flags: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Boolean extraction
# ---------------------------------------------------------------------------

# Ordered most-specific-first. Each pattern maps to the boolean it asserts.
# These run against the *last* matching position in the text, because models
# routinely reason aloud ("6 could be prime... no, 6 = 2x3, so it is composite")
# and the conclusion is what we are grading, not the exploration.
_BOOL_PATTERNS: list[tuple[re.Pattern, bool]] = [
    # Negative forms must precede positive ones: "is not prime" contains "is prime".
    (re.compile(r"\bis\s+not\s+(?:a\s+)?prime\b", re.I), False),
    (re.compile(r"\bisn'?t\s+(?:a\s+)?prime\b", re.I), False),
    (re.compile(r"\bnot\s+(?:a\s+)?prime\s+number\b", re.I), False),
    (re.compile(r"\bis\s+(?:a\s+)?composite\b", re.I), False),
    (re.compile(r"\bcomposite\s+number\b", re.I), False),
    (re.compile(r"\bis\s+(?:a\s+)?prime\b", re.I), True),
    (re.compile(r"\bprime\s+number\b", re.I), True),
    # Bare yes/no, typically the whole response under a "answer only" prompt.
    (re.compile(r"^\s*\**\s*no\b", re.I | re.M), False),
    (re.compile(r"^\s*\**\s*yes\b", re.I | re.M), True),
    (re.compile(r"\bno\b[.!]?\s*$", re.I), False),
    (re.compile(r"\byes\b[.!]?\s*$", re.I), True),
]

_REFUSAL = re.compile(
    r"\b(i can'?t|i cannot|i'?m not able|i won'?t|as an ai|i'?m unable)\b", re.I
)


def extract_boolean(text: str) -> tuple[bool | None, dict]:
    """Pull a yes/no conclusion out of arbitrary prose.

    Returns (value, format_flags). value is None when nothing could be found.

    The extractor takes the *last* assertion in the text. A model that thinks
    out loud and then concludes is answering correctly; grading its first guess
    would penalise reasoning, which is a behaviour change we must not launder
    into a capability number.
    """
    flags = {
        "chars": len(text),
        "refusal_marker": bool(_REFUSAL.search(text)),
        "has_markdown": bool(re.search(r"[*_`#]", text)),
    }
    if not text or not text.strip():
        return None, flags

    best_pos = -1
    best_val: bool | None = None
    for pat, val in _BOOL_PATTERNS:
        for m in pat.finditer(text):
            # >= so that later patterns at the same position lose to earlier
            # (more specific) ones only when strictly earlier in the list.
            if m.start() > best_pos:
                best_pos = m.start()
                best_val = val
    flags["verbose"] = len(text) > 400
    return best_val, flags


def grade_primality(expected: bool, response: str) -> Result:
    """Grade 'is N prime?'. expected is the ground truth from sympy-free
    deterministic trial division at task-generation time."""
    val, flags = extract_boolean(response)
    if val is None:
        return Result(Verdict.UNPARSEABLE, None, "no yes/no conclusion found", flags)
    ok = val == expected
    return Result(
        Verdict.CORRECT if ok else Verdict.INCORRECT,
        val,
        "",
        flags,
    )


# ---------------------------------------------------------------------------
# Code extraction
# ---------------------------------------------------------------------------

_FENCE = re.compile(
    r"```[ \t]*([A-Za-z0-9_+-]*)[ \t]*\r?\n(.*?)(?:```|\Z)", re.S
)

# Does this text show any syntactic sign of being a code attempt at all? Used
# only to separate "not code" (UNPARSEABLE) from "broken code" (INCORRECT).
# Deliberately generous: a false positive here costs us a mis-bucketed refusal,
# while a false negative would hide a genuine syntax-error regression.
_CODE_SIGNAL = re.compile(
    r"(\bdef\b|\bclass\b|\bimport\b|\breturn\b|\blambda\b|\bfor\b\s|\bwhile\b\s"
    r"|\bif\b\s|[(){}\[\]]|=|:)",
)


def extract_code(text: str) -> tuple[str | None, dict]:
    """Pull Python source out of a response.

    THIS FUNCTION IS RULE 2. The 2023 paper scored code by asking whether the
    raw response string was directly executable; when GPT-4 started wrapping
    code in markdown fences to be helpful, the fences made it non-executable
    and it was recorded as a capability collapse. It was a formatting change.

    So: fences are stripped, not punished. Their presence is recorded in
    format_flags, where it is reported as its own series and never mixed into
    the correctness number.
    """
    flags = {"chars": len(text), "fenced": False, "n_blocks": 0, "prose_only": False}
    if not text or not text.strip():
        return None, flags

    blocks = [(lang, body) for lang, body in _FENCE.findall(text)]
    flags["n_blocks"] = len(blocks)

    if blocks:
        flags["fenced"] = True
        # Prefer python-tagged blocks; else the longest block. Models sometimes
        # emit a usage example or a shell command alongside the real answer.
        py = [b for lang, b in blocks if lang.lower() in ("python", "py", "python3")]
        candidates = py or [b for _, b in blocks]
        code = max(candidates, key=lambda b: len(b))
    else:
        # No fences at all: the whole response may be bare code — or it may be
        # a refusal, which is a different thing entirely.
        #
        # Without this check, "I'd rather talk about something else." fails to
        # parse as Python and scores INCORRECT, which would let a rise in
        # refusal rate masquerade as a fall in coding ability. That is the 2023
        # mistake wearing a different hat, and our own test suite caught us
        # committing it. A response with no syntactic sign of code was never a
        # code attempt, and is UNPARSEABLE.
        if not _CODE_SIGNAL.search(text):
            flags["no_code_signal"] = True
            return None, flags
        code = text
        flags["prose_only"] = True

    code = code.strip("\n")
    if not code.strip():
        return None, flags

    # Only accept it if it actually parses as Python. This is the line between
    # "extraction failed" and "the model wrote broken code" — a distinction the
    # scorer needs, and one that a naive .replace('```','') would erase.
    try:
        ast.parse(code)
    except SyntaxError:
        # Salvage attempt: drop leading prose lines until it parses. Handles
        # "Here's the function:\n\ndef f(): ..." with no fences.
        lines = code.split("\n")
        for i in range(1, len(lines)):
            tail = "\n".join(lines[i:])
            if not tail.strip():
                break
            try:
                ast.parse(tail)
                flags["salvaged_prose_prefix"] = i
                return tail, flags
            except SyntaxError:
                continue
        flags["syntax_error"] = True
        return code, flags  # hand it back; the runner will score it INCORRECT

    return code, flags


def grade_codegen(
    code_response: str, tests: str, timeout: int = 10
) -> Result:
    """Extract code, execute it against frozen unit tests in a subprocess.

    Judged on whether the code is *correct*, never on whether the raw string
    happened to run (Rule 2).
    """
    code, flags = extract_code(code_response)
    if code is None:
        return Result(Verdict.UNPARSEABLE, None, "no code found in response", flags)
    if flags.get("syntax_error"):
        return Result(Verdict.INCORRECT, code, "extracted code has a syntax error", flags)

    program = code + "\n\n" + tests
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "candidate.py"
        p.write_text(program)
        try:
            proc = subprocess.run(
                [sys.executable, str(p)],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=td,
            )
        except subprocess.TimeoutExpired:
            return Result(Verdict.INCORRECT, code, f"timed out after {timeout}s", flags)

    if proc.returncode == 0:
        return Result(Verdict.CORRECT, code, "", flags)
    err = (proc.stderr or "").strip().split("\n")[-1][:200]
    return Result(Verdict.INCORRECT, code, f"tests failed: {err}", flags)
