"""Render a run's behavior-vs-capability chart to a standalone SVG.

Reads runs/<date>/report.json, writes assets/baseline_<date>.svg. No dependencies.
White background and dark text so it drops straight into a post; open it in any
browser and export/screenshot to PNG if a raster is needed.

    python3 scripts/make_chart.py --date 2026-07-16
"""

import argparse
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

W = 920
LEFT = 250          # label gutter
PX0 = LEFT + 15     # plot left edge
PW = W - PX0 - 40   # plot width = 100%
ROW = 46
TOP = 78
GRAY = "#8a8a82"
BLUE = "#2a78d6"
INK = "#1a1a1a"
MUTE = "#6b6b64"
GRID = "#e4e3dc"


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def x(v: float) -> float:
    return PX0 + v / 100.0 * PW


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True)
    args = ap.parse_args()

    rep = json.loads((REPO / "runs" / args.date / "report.json").read_text())
    rows = []
    for alias, d in rep["models"].items():
        s = d["scores"]
        rows.append((alias, s["behavior"]["value"] * 100, s["capability"]["value"] * 100))
    rows.sort(key=lambda r: -r[1])

    H = TOP + len(rows) * ROW + 64
    p: list[str] = []
    p.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
        f'font-family="-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif">'
    )
    p.append(f'<rect width="{W}" height="{H}" fill="#ffffff"/>')
    # title + subtitle
    p.append(f'<text x="40" y="34" font-size="21" font-weight="600" fill="{INK}">'
             f'driftline — behavior vs capability</text>')
    p.append(f'<text x="40" y="56" font-size="13" fill="{MUTE}">baseline {esc(args.date)} · '
             f'30 balanced primality tasks · served via Unify/FluxA proxy</text>')
    # legend
    lx = W - 360
    p.append(f'<rect x="{lx}" y="24" width="11" height="11" rx="2" fill="{GRAY}"/>')
    p.append(f'<text x="{lx+17}" y="34" font-size="12" fill="{MUTE}">behavior (terse prompt)</text>')
    p.append(f'<rect x="{lx+185}" y="24" width="11" height="11" rx="2" fill="{BLUE}"/>')
    p.append(f'<text x="{lx+202}" y="34" font-size="12" fill="{MUTE}">capability (best phrasing)</text>')

    # gridlines + axis labels at 0/25/50/75/100
    for g in (0, 25, 50, 75, 100):
        gx = x(g)
        p.append(f'<line x1="{gx:.1f}" y1="{TOP-12}" x2="{gx:.1f}" y2="{TOP+len(rows)*ROW-8}" '
                 f'stroke="{GRID}" stroke-width="1"/>')
        p.append(f'<text x="{gx:.1f}" y="{TOP+len(rows)*ROW+14}" font-size="11" fill="{MUTE}" '
                 f'text-anchor="middle">{g}%</text>')

    for i, (alias, beh, cap) in enumerate(rows):
        cy = TOP + i * ROW + ROW / 2
        p.append(f'<text x="{LEFT}" y="{cy+4:.1f}" font-size="13" fill="{INK}" '
                 f'text-anchor="end">{esc(alias)}</text>')
        # capability bar (drawn first, behind) then behavior on top row-split
        p.append(f'<rect x="{PX0}" y="{cy-16:.1f}" width="{x(beh)-PX0:.1f}" height="14" '
                 f'rx="3" fill="{GRAY}"/>')
        p.append(f'<rect x="{PX0}" y="{cy+2:.1f}" width="{x(cap)-PX0:.1f}" height="14" '
                 f'rx="3" fill="{BLUE}"/>')
        p.append(f'<text x="{x(beh)+6:.1f}" y="{cy-5:.1f}" font-size="11" fill="{MUTE}">{beh:.0f}%</text>')
        p.append(f'<text x="{x(cap)+6:.1f}" y="{cy+13:.1f}" font-size="11" fill="{MUTE}">{cap:.0f}%</text>')

    p.append(f'<text x="40" y="{H-16}" font-size="11" fill="{MUTE}">'
             f'k=1 for the frontier tier (no CIs); k=3–5 for the deepseek tier. '
             f'A baseline — not a drift claim.</text>')
    p.append("</svg>")

    out = REPO / "assets" / f"baseline_{args.date}.svg"
    out.parent.mkdir(exist_ok=True)
    out.write_text("\n".join(p))
    print(f"wrote {out}  ({len(rows)} models)")


if __name__ == "__main__":
    main()
