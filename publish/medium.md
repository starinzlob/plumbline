# I tried to settle "did they nerf the model" without repeating the 2023 mistakes

*Draft for Medium. Long-form. Written to be read by someone who has had this argument
and is tired of it.*

---

Every few months, the same fight breaks out. Someone says the model feels dumber than it
did last week. Someone else says it's confirmation bias. Nobody has data, so it becomes a
contest of vibes, and the vibes lose to whoever is loudest.

In July 2023 this went mainstream. A paper titled "How Is ChatGPT's Behavior Changing
over Time?" got read as *GPT-4 is getting worse*, and the Hacker News thread hit 309
points. The rebuttal from Arvind Narayanan and Sayash Kapoor — *GPT-4 is not getting
worse* — hit 149. The rebuttal was correct. And it was correct for reasons that were
completely avoidable.

I wanted to build the thing that should have existed then: an instrument that measures
this properly, keeps a permanent record, and can't repeat those mistakes. It's called
driftline: drift stays invisible until you have a fixed line to measure it against.

This is a writeup of what it is, what it found on day one, and — because this is the
whole point — everything it still gets wrong.

## The two mistakes, and the rules they force

**Mistake one: the prime trap.** The 2023 paper asked "Is X prime?" 500 times. Every one
of the 500 numbers was actually prime. So a model whose behavior merely drifted toward
answering "no" more often looked like it had catastrophically collapsed — its accuracy
cratered — when all that may have changed was its answer bias. There was no negative
class, so there was no way to tell a shifted prior from a lost capability.

The rule this forces: always test the negative class. Report *balanced accuracy*, never
raw accuracy. And treat the model's answer bias — how often it says "yes" regardless of
truth — as a first-class metric. A prior shift is a real, interesting finding. It is just
a completely different finding from "the model got dumber," and conflating them is how
you get a viral wrong headline.

**Mistake two: the markdown trap.** The same paper scored generated code by whether the
raw response was directly executable. Newer GPT-4 had started wrapping its code in
markdown fences to be more helpful. The fences made the string non-executable, and it was
recorded as a collapse in coding ability. The paper measured formatting politeness and
reported it as capability.

The rule: extract the answer, then grade the *meaning* of the extracted answer. Pull code
out of fences, run it against unit tests, judge whether it's correct — never whether the
raw string happened to run. Track formatting changes as their own separate metric.

## The rule that exists because this measures drift specifically

**No LLM judges. Ever.** If you grade a drift benchmark with a model, that judge drifts
too, and you can no longer attribute a moving number to the thing you're measuring. Every
grader in driftline is deterministic code with unit tests — two of which are regressions
against the exact 2023 bugs, so the instrument has to prove it doesn't repeat them before
it measures anyone. The cost is a narrower benchmark: anything that can't be graded by
deterministic code (essay quality, "helpfulness," style) doesn't go in. I'll take a
narrow benchmark that's attributable over a broad one that isn't.

And the load-bearing rule: **every raw response is committed to git.** Scores are just my
opinion over that data. Clone the repo, delete my graders, write your own, re-score
three years of history. That's the point. The 2023 argument degenerated into people
shouting priors because nobody could re-run anyone else's scoring. The dataset has to
outlive my opinions about it.

## Behavior is not capability

The deepest of the three ideas: fine-tuning changes how a model responds to a specific
prompt, which is not the same as the model losing an ability. A capability that hides
behind one phrasing and reappears behind another has drifted in behavior, not degraded.

So driftline reports two numbers, always together:

- **behavior** — accuracy on the single terse prompt you actually type every day.
- **capability** — best-of-N across several frozen paraphrases.

Behavior falling while capability holds is *behavior drift*, and it must be reported with
those words. Only both falling together earns the word "degradation."

## What day one showed

First baseline: 10 models, 30 balanced primality tasks, 2026-07-16, served through a
proxy (more on that limitation below).

The 2023 confound reproduced live. gpt-5.4 and deepseek-v4-flash score around 60–65% on
the terse prompt — and far worse if you look only at primes, exactly the 2023 setup — but
they're near 100% capable the moment they're allowed to reason. Score them the 2023 way
and they look broken. They are not. The gap between the terse behavior and the reasoned
capability *is* the artifact that made the original paper wrong, sitting right there in
fresh data.

Vendor answer-priors split sharply. On the identical balanced set, some models lean
toward calling a number prime and others lean the other way. deepseek-v4-flash — the
small, fast model — leans hard toward "prime" (it says yes ~85% of the time when the
truth is 50%), which tanks its accuracy on composites; the larger deepseek models in the
same family don't have the skew. That's a prior, not a capability gap, and a prime-only
test set is blind to it.

## Everything this can't tell you

An honest instrument leads with its spec sheet.

- **It's a baseline, not a drift measurement.** One time point cannot show drift; that
  needs the run to repeat over months. I am not claiming any model got worse. I'm
  claiming here is an instrument that could tell, and here is what it reads on day one.
- **The capability metric saturates.** Best-of-N pins to 100% for any competent model, so
  right now it's trustworthy as evidence a capability is *intact* and nearly worthless as
  evidence one is *lost*. This is a real defect, documented in the repo, not an issue I'm
  hiding until someone finds it.
- **It's proxy-served.** All the models are reached through one OpenAI-compatible proxy,
  so any routing or caching the proxy introduces is invisible and gets attributed to
  nothing. I measure the model as served, and say so on every result.
- **It can't see inside the API.** Quantization, A/B tests, silent routing — invisible. I
  measure output, and output only. A drop is a drop; "they nerfed it to save money" is a
  motive, and I have no access to motives.
- **Grader bugs look exactly like model drift.** Which is precisely why the raw responses
  are in git. (In the course of building this I shipped, and my own tests caught, a
  grader that mistook a refusal for a wrong answer — the exact 2023 error in a new hat.)

## The conflict of interest

This project was largely written by Claude — Anthropic's model — at my direction.
Anthropic is one of the vendors driftline measures. That is a real conflict, and no
promise from me fixes it.

The mitigations are structural, not verbal. The method is pre-registered before any data
is collected. The graders are deterministic and unit-tested. And every raw response is in
git, so anyone who distrusts the authorship can re-score the entire history without my
cooperation.

If Anthropic's models are drifting, this repo's own data will say so, at the same volume
as anything else. If they're fine, it'll say that too. The instrument doesn't care who
built it. Please go check.

---

*Repo and full pre-registered methodology: [link]*
