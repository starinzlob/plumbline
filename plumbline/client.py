"""OpenAI-compatible client for the Unify/FluxA proxy endpoint.

Two responsibilities beyond "make the call":

  1. Never leak the key. It is read from the environment or a gitignored .env,
     used, and never printed, logged, or committed. The whole repo's credibility
     rests on transparency; a key in the git history would be a fatal irony.

  2. Record the EXACT model string the proxy returns. We request a floating alias
     ("anthropic/claude-sonnet-4.6") and the proxy answers with a dated snapshot
     ("anthropic/claude-4.6-sonnet-20260217"). When that mapping changes, the name
     you type started pointing at different weights — a first-class finding, not a
     footnote.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]


def load_key() -> str:
    """Resolve the FluxA key without ever returning it to a log path.

    Order: env FLUXA_API_KEY, then <repo>/.env. Nothing else is probed — we do
    not enumerate other vendors' credentials.
    """
    k = os.environ.get("FLUXA_API_KEY")
    if k:
        return k.strip()
    envf = _REPO / ".env"
    if envf.exists():
        for line in envf.read_text().splitlines():
            line = line.strip()
            if line.startswith("FLUXA_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError(
        "No FLUXA_API_KEY. Put it in the environment or in ~/plumbline/.env "
        "(which is gitignored). The key is never printed or committed."
    )


@dataclass
class Response:
    ok: bool
    text: str
    model_returned: str  # the exact snapshot string the proxy answered with
    latency_ms: int
    usage: dict
    raw_meta: dict       # status, any cost headers, error detail — for auditing
    error: str = ""


def call(
    endpoint: str,
    model_alias: str,
    prompt: str,
    *,
    temperature: float = 0,
    top_p: float = 1,
    max_tokens: int = 1024,
    seed: int | None = None,
    timeout_s: int = 60,
    key: str | None = None,
    retries: int = 2,
) -> Response:
    key = key or load_key()
    body = {
        "model": model_alias,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "top_p": top_p,
        "max_tokens": max_tokens,
    }
    if seed is not None:
        body["seed"] = seed
    data = json.dumps(body).encode()

    last_err = ""
    for attempt in range(retries + 1):
        req = urllib.request.Request(
            endpoint,
            data=data,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=timeout_s) as r:
                latency = int((time.time() - t0) * 1000)
                payload = json.loads(r.read().decode())
                # Cost/metering often rides in headers on x402-style proxies.
                cost_headers = {
                    h: r.headers.get(h)
                    for h in r.headers.keys()
                    if any(t in h.lower() for t in ("cost", "unit", "credit", "price", "balance", "usage"))
                }
                choice = (payload.get("choices") or [{}])[0]
                text = (choice.get("message") or {}).get("content") or ""
                return Response(
                    ok=True,
                    text=text,
                    model_returned=payload.get("model", ""),
                    latency_ms=latency,
                    usage=payload.get("usage", {}) or {},
                    raw_meta={
                        "status": 200,
                        "cost_headers": cost_headers,
                        "finish_reason": choice.get("finish_reason"),
                        "id": payload.get("id"),
                    },
                )
        except urllib.error.HTTPError as e:
            detail = e.read().decode()[:500] if e.fp else ""
            last_err = f"HTTP {e.code}: {detail}"
            # 429 backoff per project rule; other 4xx won't fix on retry.
            if e.code == 429:
                time.sleep(25)
                continue
            if 400 <= e.code < 500:
                break
        except Exception as e:  # noqa: BLE001
            last_err = f"{type(e).__name__}: {e}"
        time.sleep(2 * (attempt + 1))

    return Response(False, "", "", 0, {}, {"status": "error"}, error=last_err)
