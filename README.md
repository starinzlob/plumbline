# driftline

**Drift is invisible until you have a fixed line to measure it against.**

Every few months, Hacker News has the same argument: *the model got worse. They
nerfed it. They're burning my tokens on purpose.* In 2023 the argument ran to
[309 points](https://news.ycombinator.com/item?id=36815594); the
[rebuttal](https://www.aisnakeoil.com/p/is-gpt-4-getting-worse-over-time) ran to
149. Three years later people are still having it, still with nothing but vibes,
because nobody kept a record.

This repo keeps the record. Same tasks, same graders, same prompts, run on a
schedule, forever. Every raw response committed to git so you can throw out our
scoring and do your own.

It is a measuring instrument, not an accusation. If the models are fine, this
repo will say so, at exactly the same volume.

---

## The instrument checks itself first

The 2023 paper was wrong, and it was wrong in two specific, avoidable ways. Before
this benchmark measures anyone, it has to prove it doesn't repeat them.

`scripts/demo_2023_replay.py` builds a synthetic model whose true competence is
**fixed in code** — by construction it cannot get dumber — and shifts only its
answer prior on terse prompts, the most boring thing fine-tuning does. Then it
scores that model both ways:

```
THE 2023 METHOD  (prime-only task set, raw accuracy)
  before:  94.2%
  after:    9.7%
  headline it would produce: 'accuracy collapsed by 84 points'

DRIFTLINE  (balanced task set, behavior vs capability split)
  behavior            92.2%  ->   53.9%
  capability         100.0%  ->  100.0%
  recall_positive     93.3%  ->    8.9%     <- all 2023 looked at
  recall_negative     91.1%  ->   98.9%     <- what it never looked at
  answer_bias(yes)    51.1%  ->    5.0%     <- the actual cause

  VERDICT: BEHAVIOR DRIFT: accuracy on the canonical prompt declined, but
  capability held under rephrasing. The model can still do the task; it
  stopped doing it when asked the usual way. This is NOT evidence of
  degradation.
```

The model never changed. The 2023 method reports an 84-point collapse that did not
happen. Run it yourself: `python3 scripts/demo_2023_replay.py`.

## The two mistakes, and the rules they produced

**1. The prime trap.** The 2023 paper asked "Is X prime?" 500 times. All 500 numbers
were prime. A model drifting toward "no" looked like it had collapsed — you can see
it above: `recall_positive` cratered 93→9 while `recall_negative` *rose* 91→99. They
only measured the half that fell.

→ Balanced positive/negative classes, always. **Balanced accuracy**, never raw. The
model's **answer bias** is a first-class metric, because a prior shift is a real
finding — just a completely different one from "it got dumber."

**2. The markdown trap.** The 2023 paper checked whether generated code was *directly
executable*. GPT-4 had started wrapping code in fences to be helpful; the fences broke
execution and scored as a coding collapse. It measured politeness.

→ Graders extract the answer, then judge its **semantics**. Code is pulled out of
fences, executed against unit tests, judged on correctness. Formatting is tracked as
its own metric and never mixed into capability.

**3. Behavior ≠ capability.** A capability that hides behind one phrasing and appears
behind another has drifted, not degraded.

→ Two headline numbers, always shipped together. `behavior` = the canonical prompt
you actually type. `capability` = best-of-N over frozen paraphrases. Only both
falling together may be called degradation.

## Rules that exist because this measures drift specifically

- **No LLM judges. Ever.** A judge drifts too; grading drift with a drifting ruler
  makes the result unattributable. Every grader is deterministic code with unit
  tests. Tasks that can't be graded that way don't go in — no essay quality, no
  "helpfulness." A narrower benchmark that is attributable beats a broad one that
  isn't.
- **Raw responses are the artifact; scores are a derived opinion.** Clone the repo,
  delete our graders, write your own, re-score three years of history. That's the
  point. The 2023 fight became people shouting priors because nobody could re-run
  anyone's scoring.
- **Null results ship just as loudly.** A benchmark that's only newsworthy when it
  finds a villain is advocacy with a chart on it.
- **Sampling noise is not drift.** k samples per prompt, bootstrapped 95% CIs,
  nothing called a change unless the intervals separate.

Full pre-registered method, including **the defects we already know about**:
[METHODOLOGY.md](METHODOLOGY.md).

## Status

Early. The instrument and its self-check work; it has not yet been pointed at a live
API. Currently 30 primality tasks (balanced, seeded, frozen) and an executed-code
grader. See METHODOLOGY.md § "Known defects in this instrument" for what's honestly
broken — `capability` saturates and can't yet detect the degradation it exists to
detect.

## Conflict of interest

This repo was largely written by Claude (Anthropic), at the direction of the repo
owner. Anthropic is one of the vendors this benchmark measures. That is a real
conflict and no promise from us fixes it. The mitigations are structural instead:
the method is pre-registered before data collection, the graders are deterministic
and unit-tested, and every raw response lands in git so anyone who distrusts the
authorship can re-score the entire history without our cooperation.

Please do.

## Run it

```bash
python3 -m pytest tests/ -q          # 21 tests, incl. regressions against both 2023 bugs
python3 scripts/gen_primality.py     # regenerate the frozen task set (seeded, byte-identical)
python3 scripts/demo_2023_replay.py  # the self-check above
```

## License

MIT.
