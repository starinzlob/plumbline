"""Replay the 2023 GPT-4 controversy against a model we fully control.

We simulate a model that did NOT lose any ability, and whose answer prior merely
shifted toward "no" on terse prompts — the single most boring, most likely thing
that fine-tuning does. Then we score it two ways:

  1. The 2023 method: ask only about primes, count raw accuracy.
  2. This repo's pre-registered method.

If driftline cannot tell these apart, it has no reason to exist, and the honest
move is to delete it rather than ship another chart.

Nothing here touches an API. It is a test of the *instrument*, using a synthetic
model whose ground truth we know by construction, which is the only setting in
which an instrument's correctness can actually be checked.
"""

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from driftline.graders import Verdict  # noqa: E402
from driftline.score import Sample, interpret, score_run  # noqa: E402


def simulate(n_tasks, rng, no_bias_terse, competence=0.95, only_primes=False):
    """A synthetic model.

    `competence` is its TRUE ability and is held FIXED across both runs — by
    construction, this model never gets dumber.

    `no_bias_terse` is the probability it blurts "no" on the canonical terse
    prompt without engaging. This is the behaviour change. Under the
    step-by-step paraphrase it always engages, so its capability is intact and
    recoverable — exactly the case Rule 3 exists to catch.
    """
    samples = []
    for i in range(n_tasks):
        expected = True if only_primes else (i % 2 == 0)
        task_class = "prime" if expected else "semiprime"
        for para in range(3):
            for k in range(3):
                if para == 0 and rng.random() < no_bias_terse:
                    said = False  # blurted "no" without engaging
                else:
                    said = expected if rng.random() < competence else (not expected)
                samples.append(
                    Sample(
                        task_id=f"t{i}",
                        family="primality",
                        paraphrase=para,
                        sample=k,
                        verdict=Verdict.CORRECT if said == expected else Verdict.INCORRECT,
                        expected=expected,
                        extracted=said,
                        task_class=task_class,
                        format_flags={"chars": 20},
                    )
                )
    return samples


def method_2023(samples):
    """Raw accuracy on the canonical prompt, over a prime-only task set.
    This is, as faithfully as we can restate it, what the 2023 paper did."""
    c = [s for s in samples if s.paraphrase == 0]
    return sum(1 for s in c if s.verdict == Verdict.CORRECT) / len(c)


def main():
    rng = random.Random(7)
    N = 120

    # ---- The 2023 method's view ------------------------------------------
    before_primes = simulate(N, rng, no_bias_terse=0.02, only_primes=True)
    after_primes = simulate(N, rng, no_bias_terse=0.90, only_primes=True)
    a23, b23 = method_2023(before_primes), method_2023(after_primes)

    print("=" * 72)
    print("THE 2023 METHOD  (prime-only task set, raw accuracy)")
    print("=" * 72)
    print(f"  before: {a23:6.1%}")
    print(f"  after:  {b23:6.1%}")
    print(f"  headline it would produce: 'accuracy collapsed by "
          f"{(a23 - b23) * 100:.0f} points'")
    print()

    # ---- driftline's view -------------------------------------------------
    before = simulate(N, rng, no_bias_terse=0.02, only_primes=False)
    after = simulate(N, rng, no_bias_terse=0.90, only_primes=False)
    sb, sa = score_run(before), score_run(after)

    print("=" * 72)
    print("DRIFTLINE  (balanced task set, behavior vs capability split)")
    print("=" * 72)
    for k in ("behavior", "capability", "recall_positive", "recall_negative"):
        f, t = sb[k], sa[k]
        print(f"  {k:<18} {f['value']:6.1%}  ->  {t['value']:6.1%}"
              f"   [after CI {t['lo']:.2f}, {t['hi']:.2f}]")
    print(f"  {'balanced_accuracy':<18} {sb['balanced_accuracy']['value']:6.1%}"
          f"  ->  {sa['balanced_accuracy']['value']:6.1%}")
    print(f"  {'answer_bias(yes)':<18} {sb['answer_bias_yes_rate']['value']:6.1%}"
          f"  ->  {sa['answer_bias_yes_rate']['value']:6.1%}"
          f"   (ground truth is 50.0% by construction)")
    print()
    print("  VERDICT:")
    for line in _wrap(interpret(sb, sa), 68):
        print(f"    {line}")
    print()

    print("=" * 72)
    print("GROUND TRUTH (known by construction — the model was never changed)")
    print("=" * 72)
    print("  competence parameter: 0.95 before, 0.95 after — IDENTICAL.")
    print("  The only thing that moved was the terse-prompt answer prior.")
    print()
    print(f"  The 2023 method reports a {(a23 - b23) * 100:.0f}-point capability")
    print("  collapse that did not happen.")
    print(f"  Driftline reports capability {sb['capability']['value']:.1%} ->"
          f" {sa['capability']['value']:.1%}, and names the real cause.")

    # This is the assertion the whole repo stands on.
    assert not _sep(sb["capability"], sa["capability"]), \
        "capability must NOT move — the synthetic model's competence was fixed"
    assert _sep(sb["behavior"], sa["behavior"]), \
        "behavior MUST move — we injected a prior shift"
    print()
    print("  [self-check passed: capability held, behavior moved]")


def _sep(a, b):
    return a["hi"] < b["lo"] or b["hi"] < a["lo"]


def _wrap(s, w):
    words, line, out = s.split(), "", []
    for x in words:
        if len(line) + len(x) + 1 > w:
            out.append(line)
            line = x
        else:
            line = (line + " " + x).strip()
    if line:
        out.append(line)
    return out


if __name__ == "__main__":
    main()
