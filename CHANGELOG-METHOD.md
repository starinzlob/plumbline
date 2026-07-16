# Methodology changelog

Every entry here triggers a full re-score of all history from raw responses, and
republication of the old and new series side by side (METHODOLOGY.md Rule 0).

## 2026-07-15 — pre-registration

Initial method frozen before any data collection. No live API has been called.
Rules 1-8 and Rule 0 as written in METHODOLOGY.md. Task set: 30 primality tasks,
balanced 15/15, seed 20260715.

Known defects recorded at pre-registration time (not discovered later): `capability`
saturates under best-of-N; three paraphrases is a floor on prompt sensitivity, not a
ceiling; task set is small. See METHODOLOGY.md § Known defects.

## 2026-07-16b — reasoning-content handling + max_tokens

Found while smoke-testing the open-weight tier: reasoning models (deepseek-*,
glm-*, kimi-*, etc.) spend completion tokens on `reasoning_content` first. With
max_tokens=1024 some emitted only reasoning and an EMPTY `content`, which the
grader would score UNPARSEABLE — indistinguishable from a refusal, and capable of
manufacturing a fake refusal-rate spike (fake drift).

Changes:
- max_tokens 1024 -> 2048 (sampling param change; applies to runs from this date).
- Client now captures `reasoning_content` and sets `content_starved` when content
  is empty, reasoning is present, and finish_reason == "length".
- Runner persists `reasoning_content`, `content_starved`, `finish_reason`.

A true refusal (empty content, empty reasoning, finish "stop") stays UNPARSEABLE.
A starved response is flagged, not silently counted as a refusal. Per Rule 0 this
does not retro-invalidate the 2026-07-16 frontier baseline (those models were not
content-starved), but it is logged for full provenance.
