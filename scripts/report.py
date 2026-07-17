"""Score a collected run from its raw responses and write a report.

Reads only the JSON files under runs/<date>/. Scores are a derived opinion over
the raw artifact (Rule 5): anyone can delete this file, write their own, and
re-score the same responses.
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from driftline.graders import Verdict  # noqa: E402
from driftline.score import Sample, score_run  # noqa: E402

REPO = Path(__file__).resolve().parents[1]


def load_samples(model_dir: Path) -> list[Sample]:
    samples = []
    for f in sorted(model_dir.glob("*.json")):
        rec = json.loads(f.read_text())
        if not rec.get("ok"):
            continue
        samples.append(Sample(
            task_id=rec["task"],
            family="primality",
            paraphrase=rec["paraphrase"],
            sample=rec["sample"],
            verdict=Verdict(rec["verdict"]),
            expected=rec["expected"],
            extracted=rec["extracted"],
            task_class=rec["task_class"],
            format_flags=rec.get("format_flags", {}),
        ))
    return samples


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True)
    args = ap.parse_args()
    run_dir = REPO / "runs" / args.date
    manifest = json.loads((run_dir / "manifest.json").read_text())
    k = manifest["sampling"]["k_samples"]

    report = {"date": args.date, "served_via": manifest.get("served_via"),
              "k_samples": k, "models": {}}

    print(f"\n{'='*76}\ndriftline run {args.date}  —  served via {manifest.get('served_via')}")
    print(f"k_samples={k}  paraphrases={manifest['paraphrases']}  "
          f"tasks={manifest['n_tasks']}")
    if k < 2:
        print("NOTE: k=1 — this is a BASELINE snapshot. No confidence intervals are\n"
              "possible from a single sample, so nothing here may be called 'drift'.\n"
              "Drift detection begins when a second run exists to compare against.")
    print("=" * 76)

    snapshots = {}
    for mdir in sorted(run_dir.iterdir()):
        if not mdir.is_dir():
            continue
        alias = mdir.name.replace("__", "/")
        samples = load_samples(mdir)
        if not samples:
            continue
        # record the snapshot string the proxy returned (silent-swap anchor)
        anysample = next(iter(mdir.glob("*.json")))
        rec = json.loads(anysample.read_text())
        snapshots[alias] = rec.get("model_returned", "")

        s = score_run(samples)
        report["models"][alias] = {"scores": s, "snapshot_returned": snapshots[alias]}

        beh = s["behavior"]["value"]
        cap = s["capability"]["value"]
        ba = s.get("balanced_accuracy", {}).get("value")
        bias = s.get("answer_bias_yes_rate", {}).get("value")
        rp = s.get("recall_positive", {}).get("value")
        rn = s.get("recall_negative", {}).get("value")
        unp = s["unparseable_rate"]["value"]
        print(f"\n{alias}")
        print(f"  snapshot returned : {snapshots[alias] or '(echoed alias — no snapshot exposed)'}")
        print(f"  behavior (terse)  : {beh:.1%}")
        print(f"  capability (best phr): {cap:.1%}")
        if ba is not None:
            print(f"  balanced accuracy : {ba:.1%}   (recall+ {rp:.1%} / recall- {rn:.1%})")
            print(f"  answer bias (yes) : {bias:.1%}   (ground truth 50.0%)")
        print(f"  unparseable rate  : {unp:.1%}")
        print(f"  mean resp chars   : {s['format_drift']['mean_response_chars']:.0f}")

    out = run_dir / "report.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"\nwrote {out}")

    # Snapshot anchor table — the baseline future runs check silent swaps against.
    print(f"\n{'-'*76}\nSNAPSHOT ANCHORS (what each alias resolved to on {args.date}):")
    for alias, snap in snapshots.items():
        print(f"  {alias:<34} -> {snap or '(alias echoed; swaps undetectable here)'}")


if __name__ == "__main__":
    main()
