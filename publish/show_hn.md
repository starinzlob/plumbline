# Show HN draft

**Title options (pick one — HN rewards precise over spicy):**

1. `Show HN: Driftline – a reproducible test for whether LLMs silently drift`
2. `Show HN: Driftline – I tried to settle "did they nerf the model" without the 2023 mistakes`
3. `Show HN: A drift benchmark that commits every raw model response to git`

Recommended: #1. It says what it is and makes no claim it can't back.

---

**Body:**

Every few months the same argument runs here: the model got worse, they nerfed it,
they're burning my tokens. In 2023 "GPT-4 is getting worse over time" hit 309 points;
the rebuttal ("GPT-4 is not getting worse") hit 149. The rebuttal was right, and it was
right for avoidable reasons. Three years later people still argue this with nothing but
vibes, because nobody kept a record.

Driftline keeps the record. Same tasks, same graders, same prompts, on a schedule, with
every raw response committed to git so you can throw out my scoring and redo it.

It's built to not repeat the two mistakes that sank the 2023 paper:

- That paper asked "Is X prime?" 500 times — all 500 were prime. A model drifting toward
  "no" looked like collapse. Driftline uses a balanced positive/negative set and reports
  balanced accuracy plus the model's answer bias as a first-class metric, because a prior
  shift is a real finding — just a completely different one from "it got dumber."
- That paper scored code by whether the raw string was directly executable; when GPT-4
  started wrapping code in markdown fences to be helpful, the fences broke execution and
  scored as a coding collapse. Driftline extracts the answer, then grades its semantics.
  Formatting is tracked separately, never mixed into capability.

There are no LLM judges anywhere — a judge that drifts can't measure drift, so every
grader is deterministic code with unit tests. Two of those tests are regressions against
the exact 2023 bugs. It also reports two separate numbers: `behavior` (accuracy on the
terse prompt you actually type) and `capability` (best-of-N across frozen paraphrases).
Only both falling together may be called degradation.

First baseline, 10 models, 2026-07-16 — and the 2023 confound shows up live: gpt-5.4 and
deepseek-v4-flash read ~60–65% on the terse prompt (and much worse on primes alone) but
are ~100% capable once allowed to reason. Score them the 2023 way and they look broken.
They aren't.

**This is a baseline, not a drift finding.** One time point can't show drift — that
needs the run to repeat over months. I'm not claiming any model got worse. I'm claiming
here's an instrument that could tell, honestly, and here's what it reads on day one.

**Disclosure:** this was largely written by Claude (Anthropic), which is one of the
vendors it measures. That's a real conflict. The mitigations are structural: the method
is pre-registered before data collection, the graders are deterministic and unit-tested,
and every raw response is in git so anyone who distrusts the authorship can re-score the
whole history without my cooperation. Please do.

Known limits are in the repo, including one I already know is broken (the capability
metric saturates and can't yet detect the degradation it exists to detect).

Repo: https://github.com/starinzlob/driftline
