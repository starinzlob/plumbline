"""Collect one run. Resumable, saves every raw response to disk as it goes.

Every call writes a JSON file under runs/<date>/<model>/ BEFORE the next call is
made, so an interruption (or an exhausted balance) never loses data already paid
for. Re-running skips files that already exist.

Usage:
  python3 scripts/run.py --date 2026-07-16 --models gpt-5.4,gemini-3.5-flash
  python3 scripts/run.py --date 2026-07-16            # all models in config
Options:
  --paraphrases 0,1   which paraphrase indices to send (default 0,1)
  --k 1               samples per (task,paraphrase)
"""

import argparse
import json
import sys
import time
from datetime import date as _date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import yaml  # noqa: E402

from plumbline.client import call, load_key  # noqa: E402
from plumbline.graders import grade_primality  # noqa: E402

REPO = Path(__file__).resolve().parents[1]


def load_tasks() -> list[dict]:
    tasks = []
    for line in (REPO / "tasks" / "primality.jsonl").read_text().splitlines():
        if line.strip():
            tasks.append(json.loads(line))
    return tasks


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=_date.today().isoformat())
    ap.add_argument("--models", default="", help="comma-separated aliases; default = all in config")
    ap.add_argument("--paraphrases", default="0,1")
    ap.add_argument("--k", type=int, default=1)
    ap.add_argument("--balance-floor", type=int, default=300,
                    help="stop cleanly once x-llm-balance drops below this")
    args = ap.parse_args()

    cfg = yaml.safe_load((REPO / "config.yaml").read_text())
    key = load_key()
    endpoint = cfg["endpoint"]
    samp = cfg["sampling"]
    para_idx = [int(x) for x in args.paraphrases.split(",")]

    wanted = [x.strip() for x in args.models.split(",") if x.strip()]
    by_alias = {m["alias"]: m for m in cfg["models"]}
    if wanted:
        # Honour the caller's order (lets us run cheapest-first to secure the
        # affordable data before spending on the expensive tier).
        models = [by_alias[a] for a in wanted if a in by_alias]
    else:
        models = list(cfg["models"])
    tasks = load_tasks()

    run_dir = REPO / "runs" / args.date
    run_dir.mkdir(parents=True, exist_ok=True)
    # Manifest pins the exact config this run was collected under (Rule 7).
    (run_dir / "manifest.json").write_text(json.dumps({
        "date": args.date,
        "endpoint": endpoint,
        "served_via": cfg.get("served_via"),
        "sampling": {**samp, "k_samples": args.k},
        "paraphrases": para_idx,
        "models": [m["alias"] for m in models],
        "n_tasks": len(tasks),
    }, indent=2))

    spent_estimate = 0
    n_calls = 0
    for m in models:
        alias = m["alias"]
        mdir = run_dir / alias.replace("/", "__")
        mdir.mkdir(parents=True, exist_ok=True)
        print(f"\n=== {alias} ===")
        n_ok = n_wrong = n_unparse = n_err = 0
        for t in tasks:
            expected = t["answer"]["value"]
            for pi in para_idx:
                prompt = t["prompts"][pi]
                for k in range(args.k):
                    fname = mdir / f"{t['id'].split('/')[-1]}_p{pi}_s{k}.json"
                    if fname.exists():
                        continue
                    r = call(endpoint, alias, prompt,
                             temperature=samp["temperature"], top_p=samp["top_p"],
                             max_tokens=samp["max_tokens"], seed=samp.get("request_seed"),
                             timeout_s=samp["timeout_s"], key=key)
                    n_calls += 1
                    if not r.ok:
                        n_err += 1
                        rec = {"ok": False, "error": r.error, "task": t["id"],
                               "paraphrase": pi, "sample": k, "alias": alias}
                        fname.write_text(json.dumps(rec))
                        # A 402/insufficient-balance or repeated error: stop this
                        # model rather than hammering a dead endpoint.
                        if "402" in r.error or "insufficient" in r.error.lower():
                            print(f"  balance exhausted or payment error — stopping: {r.error[:80]}")
                            _summarise(run_dir); return
                        continue
                    g = grade_primality(expected, r.text)
                    ch = r.raw_meta.get("cost_headers", {})
                    cost = ch.get("x-llm-cost-credits")
                    if cost:
                        spent_estimate += int(cost)
                    bal = ch.get("x-llm-balance")
                    rec = {
                        "ok": True,
                        "task": t["id"],
                        "paraphrase": pi,
                        "sample": k,
                        "alias": alias,
                        "model_returned": r.model_returned,
                        "expected": expected,
                        "task_class": t["meta"]["class"],
                        "response": r.text,
                        "reasoning_content": r.reasoning,
                        "content_starved": r.content_starved,
                        "finish_reason": r.raw_meta.get("finish_reason"),
                        "verdict": g.verdict.value,
                        "extracted": g.extracted,
                        "format_flags": g.format_flags,
                        "usage": r.usage,
                        "cost_credits": cost,
                        "latency_ms": r.latency_ms,
                    }
                    fname.write_text(json.dumps(rec, ensure_ascii=False))
                    if g.verdict.value == "correct":
                        n_ok += 1
                    elif g.verdict.value == "incorrect":
                        n_wrong += 1
                    else:
                        n_unparse += 1
                    # Balance-floor stop: safer than waiting for a 402, and keeps
                    # a small residual so we never leave the wallet at exactly 0
                    # mid-call. All data collected so far is already on disk.
                    if bal is not None and int(bal) < args.balance_floor:
                        print(f"  balance {bal} < floor {args.balance_floor} — stopping cleanly")
                        _summarise(run_dir); return
                    time.sleep(1.0)
        graded = n_ok + n_wrong
        acc = f"{n_ok/graded:.1%}" if graded else "n/a"
        print(f"  correct={n_ok} wrong={n_wrong} unparseable={n_unparse} errors={n_err}  acc(graded)={acc}")
        print(f"  running spend estimate: {spent_estimate} credits over {n_calls} new calls")

    _summarise(run_dir)


def _summarise(run_dir: Path) -> None:
    print(f"\nraw responses saved under {run_dir}")
    print("next: python3 scripts/report.py --date", run_dir.name)


if __name__ == "__main__":
    main()
