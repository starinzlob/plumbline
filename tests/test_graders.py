"""Grader tests.

The first two classes are regression tests against the *actual* 2023 GPT-4 paper
mistakes. If they ever fail, this benchmark has become the thing it was built to
correct, and it must not publish until they pass again.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from driftline.graders import (  # noqa: E402
    Verdict,
    extract_boolean,
    extract_code,
    grade_codegen,
    grade_primality,
)

FIB_TESTS = """
assert fib(0) == 0
assert fib(1) == 1
assert fib(10) == 55
"""

GOOD_FIB = """def fib(n):
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a"""


class TestRule2_MarkdownFencesAreNotAFailure:
    """The 2023 paper checked whether the raw response was *directly executable*.
    GPT-4 started wrapping code in fences to be helpful; the fences broke
    execution and were scored as a coding-ability collapse. It measured
    politeness. These must all be CORRECT."""

    def test_bare_code_no_fences(self):
        assert grade_codegen(GOOD_FIB, FIB_TESTS).verdict == Verdict.CORRECT

    def test_fenced_python(self):
        r = grade_codegen(f"```python\n{GOOD_FIB}\n```", FIB_TESTS)
        assert r.verdict == Verdict.CORRECT
        assert r.format_flags["fenced"] is True

    def test_fenced_untagged(self):
        assert grade_codegen(f"```\n{GOOD_FIB}\n```", FIB_TESTS).verdict == Verdict.CORRECT

    def test_prose_wrapped_and_fenced(self):
        resp = (
            "Sure! Here's an iterative implementation, which avoids the "
            "exponential blowup of naive recursion:\n\n"
            f"```python\n{GOOD_FIB}\n```\n\n"
            "This runs in O(n) time and O(1) space. Let me know if you'd like "
            "the memoised recursive version instead!"
        )
        r = grade_codegen(resp, FIB_TESTS)
        assert r.verdict == Verdict.CORRECT, "chattiness must never score as incorrect"

    def test_prose_prefix_without_fences(self):
        resp = f"Here's the function:\n\n{GOOD_FIB}"
        assert grade_codegen(resp, FIB_TESTS).verdict == Verdict.CORRECT

    def test_multiple_blocks_picks_the_real_one(self):
        resp = (
            f"```python\n{GOOD_FIB}\n```\n\n"
            "Example usage:\n\n```python\nprint(fib(10))\n```"
        )
        assert grade_codegen(resp, FIB_TESTS).verdict == Verdict.CORRECT

    def test_wrong_code_still_fails(self):
        """The flip side: we must not become so forgiving that we can't detect
        a real regression."""
        bad = "def fib(n):\n    return n"
        assert grade_codegen(bad, FIB_TESTS).verdict == Verdict.INCORRECT

    def test_syntax_error_is_incorrect_not_unparseable(self):
        r = grade_codegen("```python\ndef fib(n)\n    return 1\n```", FIB_TESTS)
        assert r.verdict == Verdict.INCORRECT

    def test_no_code_at_all_is_unparseable(self):
        r = grade_codegen("I'd rather talk about something else.", FIB_TESTS)
        assert r.verdict == Verdict.UNPARSEABLE, (
            "a non-answer is not a wrong answer; folding it in would let a "
            "refusal-rate change masquerade as capability loss"
        )


class TestRule1_NegativeClassIsGradedSymmetrically:
    """The 2023 paper asked 'Is X prime?' 500 times with 500 primes and zero
    composites, so an answer-bias shift read as a capability collapse. The task
    generator fixes the sampling; the grader must handle both classes with
    equal fluency."""

    def test_composite_phrasings(self):
        for resp in [
            "No, 9 is not prime.",
            "9 isn't prime — it's 3 x 3.",
            "9 is a composite number.",
            "No.",
            "**No** — 9 = 3².",
        ]:
            assert grade_primality(False, resp).verdict == Verdict.CORRECT, resp

    def test_prime_phrasings(self):
        for resp in [
            "Yes, 7919 is prime.",
            "7919 is a prime number.",
            "Yes.",
            "**Yes** — it has no divisors other than 1 and itself.",
        ]:
            assert grade_primality(True, resp).verdict == Verdict.CORRECT, resp

    def test_wrong_answers_are_caught_in_both_directions(self):
        assert grade_primality(True, "No, it is not prime.").verdict == Verdict.INCORRECT
        assert grade_primality(False, "Yes, it is prime.").verdict == Verdict.INCORRECT


class TestRule3_ReasoningAloudIsGradedOnItsConclusion:
    def test_conclusion_wins_over_exploration(self):
        resp = (
            "Let me check. 91 looks prime at first glance — it's odd and not "
            "divisible by 3 or 5. But 7 x 13 = 91. So 91 is not prime."
        )
        assert grade_primality(False, resp).verdict == Verdict.CORRECT

    def test_self_correction_is_respected(self):
        resp = "91 is prime. Wait — 7 times 13 is 91. So 91 is composite."
        assert grade_primality(False, resp).verdict == Verdict.CORRECT


class TestUnparseableIsItsOwnCategory:
    def test_refusal(self):
        r = grade_primality(True, "I can't help with that.")
        assert r.verdict == Verdict.UNPARSEABLE
        assert r.format_flags["refusal_marker"] is True

    def test_empty(self):
        assert grade_primality(True, "").verdict == Verdict.UNPARSEABLE
        assert grade_primality(True, "   \n ").verdict == Verdict.UNPARSEABLE

    def test_waffle(self):
        r = grade_primality(True, "That depends on how you define things!")
        assert r.verdict == Verdict.UNPARSEABLE


class TestFormatFlagsAreObservedButNeverScored:
    def test_verbosity_recorded(self):
        chatty = "Yes, it is prime. " + "Here is some more context. " * 40
        r = grade_primality(True, chatty)
        assert r.verdict == Verdict.CORRECT, "verbosity is not an error"
        assert r.format_flags["verbose"] is True

    def test_markdown_recorded(self):
        r = grade_primality(True, "**Yes**, `7919` is prime.")
        assert r.verdict == Verdict.CORRECT
        assert r.format_flags["has_markdown"] is True


class TestExtractorsDirectly:
    def test_extract_boolean_none(self):
        val, _ = extract_boolean("hello there")
        assert val is None

    def test_extract_code_none(self):
        code, _ = extract_code("")
        assert code is None
