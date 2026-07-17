"""Size a full run before spending on one.

Two calls per model — a terse prompt (~1 completion token) and a step-by-step
prompt (the expensive case, hundreds of tokens on a reasoning model) — bracket
the real per-call cost. Also records the exact model string each vendor returns,
so we know which vendors expose a dated snapshot (silent-swap detectable) and
which just echo the alias (we're blind).

~14 calls, a fraction of a percent of balance. The full run is gated separately.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import yaml  # noqa: E402

from driftline.client import call, load_key  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
TERSE = "Is 22493 a prime number? Answer yes or no."
STEPWISE = "Determine whether 22493 is prime. Work through it step by step, then state your conclusion."


def credits(r) -> int | None:
    v = r.raw_meta.get("cost_headers", {}).get("x-llm-cost-credits")
    return int(v) if v is not None else None


def main() -> None:
    cfg = yaml.safe_load((REPO / "config.yaml").read_text())
    key = load_key()
    endpoint = cfg["endpoint"]
    print(f"{'model alias':<34} {'terse':>6} {'stepwise':>9} {'snapshot returned':<40}")
    print("-" * 92)

    rows = []
    first_balance = last_balance = None
    for m in cfg["models"]:
        alias = m["alias"]
        c_terse = c_step = None
        snap = ""
        for prompt, slot in ((TERSE, "terse"), (STEPWISE, "step")):
            r = call(endpoint, alias, prompt, temperature=0, max_tokens=1024, key=key)
            time.sleep(1.5)
            if not r.ok:
                snap = f"ERROR: {r.error[:30]}"
                continue
            bal = r.raw_meta.get("cost_headers", {}).get("x-llm-balance")
            if bal is not None:
                if first_balance is None:
                    first_balance = int(bal)
                last_balance = int(bal)
            if slot == "terse":
                c_terse = credits(r)
            else:
                c_step = credits(r)
                snap = r.model_returned or "(echoed alias)"
        rows.append((alias, c_terse, c_step, m.get("role", "")))
        print(f"{alias:<34} {str(c_terse):>6} {str(c_step):>9} {snap:<40}")

    print("-" * 92)
    # Per full run: 30 tasks x 5 samples x [2 terse-ish paraphrases + 1 stepwise]
    #   = 300 terse-ish calls + 150 stepwise calls, per model.
    total = 0
    print("\nprojected cost per FULL WEEKLY RUN (per model, then summed):")
    for alias, ct, cs, role in rows:
        if ct is None or cs is None:
            print(f"  {alias:<34} (incomplete probe, skipped)")
            continue
        per_model = 300 * ct + 150 * cs
        total += per_model
        tag = "  [reference]" if role == "reference" else ""
        print(f"  {alias:<34} {per_model:>8} credits{tag}")
    print(f"\n  TOTAL PER WEEKLY RUN: ~{total} credits")
    if first_balance:
        print(f"  balance observed:     {first_balance} -> {last_balance} credits")
        if total:
            print(f"  runway:               ~{last_balance // total} weekly runs "
                  f"(~{last_balance // total // 4} months) on current balance")


if __name__ == "__main__":
    main()
