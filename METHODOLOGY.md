# Methodology (pre-registered)

This document is the contract. It is written **before** any data is collected, and
the scoring rules here are frozen. If we change a rule later, the change lands in
git with a dated entry in `CHANGELOG-METHOD.md`, and every affected historical run
is **re-scored from raw responses** and republished. We never silently re-cut a
metric to make a chart look better.

## The question

Do commercial LLM APIs get worse over time behind a stable model name?

That question has been asked loudly and answered badly. In 2023, ["GPT-4 is getting
worse over time, not better"](https://news.ycombinator.com/item?id=36815594) hit 309
points on Hacker News; the rebuttal, ["GPT-4 is not getting
worse"](https://www.aisnakeoil.com/p/is-gpt-4-getting-worse-over-time), hit 149. The
rebuttal was right, and it was right for reasons that are entirely avoidable.

We are trying to answer the same question without repeating those mistakes.

## What went wrong last time, and the rule it produces

### 1. The prime number trap → always test the negative class

The 2023 paper asked "Is X prime?" 500 times. **All 500 numbers were prime.** A model
whose behavior drifted toward answering "no" more often looked like it had
catastrophically collapsed. Not one composite was tested, so there was no way to tell
capability loss from a shifted answer bias.

> **Rule 1.** Every task family ships a balanced positive and negative class. We report
> **balanced accuracy**, never raw accuracy. We additionally publish the confusion
> matrix and the model's **answer bias** (its overall yes-rate) as a first-class metric,
> because a pure bias shift is a real finding — just a completely different one from
> "the model got dumber."

### 2. The markdown backtick trap → grade meaning, never format

The 2023 paper checked whether generated code was **directly executable**. Newer GPT-4
had started wrapping code in markdown fences to be more helpful. The fences made the
output non-executable, and it was scored as failure. The paper measured formatting
politeness and reported it as coding ability.

> **Rule 2.** Graders extract the answer, then judge the extracted answer's semantics.
> Code is pulled out of fences, executed against unit tests, and judged on whether it
> is **correct** — never on whether the raw string happened to run. Formatting changes
> are tracked as a *separate* metric (`format_drift`), never mixed into capability.

### 3. Behavior ≠ capability → ask more than once, more than one way

Fine-tuning changes how a model responds to a specific prompt. That is not the same as
the model losing the ability. A capability that hides behind one phrasing and appears
behind another has drifted in behavior, not degraded.

> **Rule 3.** Every task ships **N paraphrases** (default 3), written in advance and
> frozen. We report two separate headline numbers:
>
> - **`behavior`** — accuracy on the single canonical prompt. Answers "did the thing I
>   type every day get worse?"
> - **`capability`** — best-of-N across paraphrases. Answers "can the model still do it
>   at all?"
>
> `behavior` falling while `capability` holds is **behavior drift** and must be reported
> with those words. Only both falling together may be called degradation.

## Rules that exist because this is a drift benchmark specifically

### 4. No LLM judges. Ever.

An LLM judge drifts too. Grading a drift benchmark with a model whose own behavior is
un-pinned means you cannot attribute a moving number to the thing being measured. Every
grader in this repo is deterministic code with unit tests. If a task cannot be graded by
deterministic code, **it does not go in the benchmark.** This rules out essay quality,
"helpfulness," and style. We accept a narrower benchmark in exchange for an attributable
one.

### 5. Raw responses are the artifact; scores are a derived opinion

Every raw response is committed to git, keyed by date, model, task, paraphrase, and
sample index. Anyone can clone the repo, throw out our graders, write their own, and
re-score three years of history. **That is the point.** The 2023 argument turned into
people shouting priors at each other because nobody could re-run anyone else's scoring.
The dataset outlives our opinions about it.

### 6. Null results are published just as loudly

"No drift detected" ships with the same prominence, the same chart, and the same
announcement as any finding of drift. The pre-registered analysis in this file is what
runs, whatever it returns. A benchmark that is only newsworthy when it finds a villain
is not a measurement instrument, it's advocacy with a chart on it — and it deserves to
be dismissed as such.

### 7. Sampling noise is not drift

LLM APIs are nondeterministic even at temperature 0. A benchmark that reports a single
number per day will manufacture drift out of noise, and be wrong.

> We run **k samples** (default 5) per prompt, report the mean with **bootstrapped 95%
> confidence intervals**, and call nothing a change unless the intervals separate.
> Every published claim of drift must survive `scripts/significance.py`. All sampling
> params (temperature, top_p, seed, max_tokens) are pinned in `config.yaml` and logged
> into every run.

### 8. Vendor-neutral, symmetric, and hostile to our own conclusions

Every vendor gets the identical task set, identical graders, identical treatment. We do
not add a task because it makes a vendor look bad. Task sets change only by the
amendment process in Rule 0, never in response to a result.

**Disclosure:** this repo was largely written by Claude (Anthropic) at the direction of
the repo owner. That is a real conflict of interest, since Anthropic is one of the
vendors under measurement. The mitigations are structural, not promises: the method is
pre-registered here, the graders are deterministic and unit-tested, and every raw
response is in git so that anyone who distrusts the authorship can re-score the whole
history themselves without our cooperation. Please do.

## The proxy caveat

The models are reached through a single OpenAI-compatible proxy (Unify, via the
FluxA `proxy-monetize` endpoint), not through each vendor's own API. This is a
deliberate, disclosed trade-off.

**Why it's acceptable:** one key reaches all vendors under identical transport, and
routing through a proxy is how a large and growing share of people actually consume
these models (OpenRouter and friends). Measuring the proxy-served model measures
something real.

**What it costs us:** any routing, caching, quantization, or A/B split the proxy
introduces is invisible and gets attributed to nothing. A drop we observe could be
the vendor's or the proxy's, and this benchmark cannot separate them — consistent
with the existing limit that we cannot see inside any API.

**Mitigations, in order of what's built:**

1. Every result is stamped **"as served through Unify on `<date>`"**. We never claim
   to measure a vendor's direct API.
2. We request floating aliases and **record the exact snapshot string returned**
   (e.g. request `anthropic/claude-sonnet-4.6`, log
   `anthropic/claude-4.6-sonnet-20260217`). An alias→snapshot change is published as
   its own finding: *the name you type started pointing at different weights.* This
   is one of the most concrete forms of the "they swapped my model" complaint, and
   almost nobody is recording it.
3. **Planned, not yet built:** periodically cross-check one model direct-vs-proxy to
   bound the proxy's own contribution. Until that exists, the caveat stands at full
   strength and every chart carries it.

## Rule 0 — amendments

Task sets and graders may be **added to**, but a frozen task is never edited or deleted;
it is superseded, with the old one retained and still scored. Any methodology change:

1. lands as a dated entry in `CHANGELOG-METHOD.md` explaining the reasoning,
2. triggers a full re-score of all history from raw responses,
3. and republishes both the old and new series side by side.

## What this benchmark cannot tell you

Stating this up front, because every honest instrument has a spec sheet:

- It **cannot** see inside the API. Quantization, routing, distillation, caching, and
  A/B tests are invisible to us. We measure output, and output only.
- It **cannot** prove intent. A drop is a drop. "They nerfed it to save money" is a
  motive, and we have no access to motives. We will not speculate about them in
  findings.
- It **cannot** speak to your workload. This is a narrow set of deterministically
  gradable tasks. Your agent loop is not in it.
- It **cannot** rule out that we are the ones who broke something. Grader bugs look
  exactly like model drift. That is precisely why the raw responses are in git.

## Known defects in this instrument

Found by running `scripts/demo_2023_replay.py` against a synthetic model whose true
competence we fixed by construction. Listed here rather than in an issue tracker,
because a measurement instrument's spec sheet should lead with what it gets wrong.

- **`capability` saturates.** Best-of-N over 3 paraphrases × k samples is
  `1 - (1-p)^(3k)`, which pins to 1.0 for any competent model: at p=0.95 and k=3, it
  is 99.99%. A saturated metric cannot detect the very degradation it exists to
  detect — it will read 100% right up until the model falls off a cliff. Until this
  is fixed, `capability` is only trustworthy as evidence **against** degradation (a
  held capability is real), and is close to worthless as evidence **for** it.
  Candidate fixes under consideration: report per-paraphrase accuracy curves
  instead of a max; use harder tasks so p sits nearer 0.5 where the metric has
  resolution; report capability at fixed k with its own CI. Not yet chosen, so
  not yet claimed.
- **Three paraphrases is not "any phrasing."** Rule 3's `capability` says only that
  the ability survives *the three phrasings we froze in advance*. A capability that
  needs a fourth is invisible to us and will be misreported as lost. The paraphrase
  set is a floor on prompt sensitivity, never a ceiling.
- **The task set is small and narrow.** 30 primality tasks is enough to catch a
  large bias shift and nowhere near enough to catch a subtle one. Confidence
  intervals will be wide and should be believed when they are.
