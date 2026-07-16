"""One real call, to verify wiring before spending on a full run.

Uses the cheapest model. Prints everything EXCEPT the key: the returned snapshot
string, latency, token usage, and any cost/metering headers the proxy exposes, so
we can size a full run's cost before committing to it.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from plumbline.client import call, load_key  # noqa: E402

ENDPOINT = "https://proxy-monetize.fluxapay.xyz/llm/unify-llm/v1/chat/completions"


def main() -> None:
    try:
        load_key()  # verify presence; return value deliberately discarded
    except RuntimeError as e:
        print("KEY NOT FOUND:", e)
        sys.exit(1)
    print("key: loaded (not printed)\n")

    alias = sys.argv[1] if len(sys.argv) > 1 else "google/gemini-3.5-flash"
    prompt = "Is 22493 a prime number? Answer yes or no."  # ground truth: composite (83*271)
    print(f"requesting alias : {alias}")
    print(f"prompt           : {prompt}\n")

    r = call(ENDPOINT, alias, prompt, temperature=0, max_tokens=256)
    if not r.ok:
        print("CALL FAILED:", r.error)
        sys.exit(2)

    print(f"model returned   : {r.model_returned!r}")
    print(f"  ^ alias -> snapshot. This is what we track for silent-swap detection.")
    print(f"latency          : {r.latency_ms} ms")
    print(f"usage            : {r.usage}")
    print(f"cost headers     : {r.raw_meta.get('cost_headers')}")
    print(f"finish_reason    : {r.raw_meta.get('finish_reason')}")
    print(f"\nresponse text    : {r.text[:300]!r}")
    print("\n(ground truth: 22493 = 83 x 271, so the correct answer is NO / not prime)")


if __name__ == "__main__":
    main()
