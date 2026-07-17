# X / Twitter thread draft

Tone: honest, technical, no "they nerfed it" clickbait. The restraint IS the credibility.
Post as a thread. ~280 chars each.

---

**1/**
"Did they nerf the model?" gets argued every few months with zero data on either side.

So I built an instrument to measure it properly — and made it repeat the 2023 "GPT-4 is
getting worse" study without the two bugs that made that study wrong.

Here's what day one reads. 🧵

**2/**
The 2023 paper asked "is X prime?" 500 times. All 500 were prime.

A model that just drifts toward answering "no" looks like it collapsed — but you can't
tell a bias shift from a capability loss if you never test the other class.

Fix: balanced set, report answer bias separately.

**3/**
That paper also scored code by whether the raw output ran. When GPT-4 started wrapping
code in ```markdown fences``` to be helpful, the fences broke execution → scored as a
coding collapse.

It measured politeness. Fix: extract the answer, grade its meaning, not its format.

**4/**
So the tool reports two numbers, never one:

• behavior = accuracy on the terse prompt you actually type
• capability = best-of-N once the model is allowed to reason

Only both falling together is degradation. Behavior alone falling is a different story.

**5/**
Day one, 10 models. The 2023 confound is alive:

gpt-5.4 and deepseek-v4-flash read ~60% on the terse prompt — and ~100% capable once
they reason.

Score them the 2023 way (terse, primes only) and they look broken. They aren't.
[chart]

**6/**
Also visible: vendor answer-priors split hard. Some models lean toward calling a number
prime, others lean the other way — on the exact same balanced set. That's a prior, not a
skill gap, and a prime-only test set can't see it.

**7/**
Rules that make it a drift benchmark and not a hot take:
• no LLM judges (a judge drifts too) — deterministic graders w/ unit tests
• every raw response committed to git — throw out my scoring, redo it
• null results ship as loudly as findings

**8/**
Important: this is a BASELINE, not a drift claim. One time point can't show drift — that
needs months of repeats. I am NOT saying any model got worse. I'm saying here's a tool
that could tell, honestly.

**9/**
Disclosure: this was largely written by Claude (Anthropic) — one of the vendors it
measures. Real conflict. Mitigation is structural: pre-registered method, deterministic
graders, all raw responses in git so you can re-score without me.

Repo + full method: [link]
