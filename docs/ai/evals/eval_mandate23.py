"""MANDATE-23 harness — evaluate cache and memory from returned flags and behavior.

Required scenarios:
  (a) repeat the same request → second response is `hit_exact`; source change → `miss`
  (b) at least three turns with one session_id → retain short-term context
  (c) new session_id with the same user_id → recall persisted user memory
  (d) a different user_id cannot access another user's cached/session data (HARD BAR)

The harness scores response `cacheStatus` and database state, not wording.

    python3 docs/ai/evals/eval_mandate23.py --enforce-hard-bars
    python3 docs/ai/evals/eval_mandate23.py --only cache
"""
import argparse
import datetime
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent))
from eval_mandate14 import PRICING, extract_trace_and_tokens, calculate_percentiles  # noqa: E402

BASE = os.environ.get("EVAL_BASE_URL", "http://localhost:8080/api").rstrip("/") + "/copilot"
HERE = Path(__file__).parent
TIMEOUT = 180

PROBE_Q = "How much do the Roof Binoculars cost?"
REVIEW_Q = "What do customers say about the National Park Foundation Explorascope?"
# Source row that the evaluator may update to verify invalidation.
SRC_PRODUCT = "OLJCESPC7Z"
SRC_USER = "stargazer_mike"


def ask(q, uid, sid):
    t = time.time()
    try:
        r = requests.post(BASE, json={"question": q, "user_id": uid, "session_id": sid}, timeout=TIMEOUT)
        lat = round(time.time() - t, 2)
        if r.status_code != 200:
            return {"ERR": f"HTTP {r.status_code}"}, lat
        return r.json(), lat
    except Exception as e:  # noqa: BLE001
        return {"ERR": str(e)[:80]}, round(time.time() - t, 2)


def psql(sql, user="root"):
    return subprocess.run(
        ["docker", "exec", "postgresql", "psql", "-U", user, "-d", "otel", "-tc", sql],
        capture_output=True, text=True).stdout.strip()


def clear_cache():
    """Delete only eval cache prefixes; never use FLUSHALL."""
    # Product Review L2 cache also lives in Valkey.
    for pattern in ("copilot:answer:*", "copilot:semantic:*",
                     "reviews:summary:*", "reviews:semantic:item:*"):
        scan = subprocess.run(
            ["docker", "exec", "valkey-cart", "valkey-cli", "--scan", "--pattern", pattern],
            capture_output=True, text=True, timeout=15, check=True)
        keys = [key for key in scan.stdout.splitlines() if key]
        for start in range(0, len(keys), 100):
            # Valkey Search 8.1 can delete indexed HASH keys but leave valkey-cli
            # waiting for the reply. Bound the client; verify the keys below.
            subprocess.run(
                ["docker", "exec", "valkey-cart", "timeout", "5", "valkey-cli", "UNLINK",
                 *keys[start:start + 100]], capture_output=True, timeout=10)
        remaining = subprocess.run(
            ["docker", "exec", "valkey-cart", "valkey-cli", "--scan", "--pattern", pattern],
            capture_output=True, text=True, timeout=15, check=True).stdout.strip()
        if remaining:
            raise RuntimeError(f"cache cleanup incomplete for {pattern}")


class Runner:
    def __init__(self, evidence_dir):
        self.dir = evidence_dir
        self.results = []
        self.hard_bar_failed = False

    def record(self, group, case, passed, reason, latency=0.0, data=None, hard_bar=False):
        row = {
            "group": group, "case": case, "passed": bool(passed), "reason": reason,
            "latency": latency,
            "cache_status": (data or {}).get("cacheStatus"),
            "response": ((data or {}).get("response") or "")[:300],
        }
        if hard_bar and not passed:
            self.hard_bar_failed = True
        self.results.append(row)
        (self.dir / f"{group}_{case}.json").write_text(
            json.dumps(row, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  [{'PASS' if passed else 'FAIL'}] {group}/{case} — {reason}")


def g_cache(r):
    print("== cache ==")
    clear_cache()
    d1, l1 = ask(PROBE_Q, "m23-a", "m23-c1")
    r.record("cache", "first-miss", d1.get("cacheStatus") == "miss",
             f"first request: {d1.get('cacheStatus')}", l1, d1)
    d2, l2 = ask(PROBE_Q, "m23-a", "m23-c2")
    r.record("cache", "repeat-hit", d2.get("cacheStatus") == "hit_exact",
             f"second request: {d2.get('cacheStatus')} ({l1}s → {l2}s)", l2, d2)

    ask(REVIEW_Q, "m23-a", "m23-c3")
    d4, _ = ask(REVIEW_Q, "m23-a", "m23-c4")
    if d4.get("cacheStatus") != "hit_exact":
        r.record("cache", "review-warm", False,
                 "could not warm the review cache for invalidation testing", 0, d4)
        return
    original = psql(
        f"SELECT description FROM reviews.productreviews "
        f"WHERE product_id='{SRC_PRODUCT}' AND username='{SRC_USER}'"
    )
    escaped_original = original.replace("'", "''")
    stamp = datetime.datetime.now().strftime("%H%M%S")
    try:
        psql(f"UPDATE reviews.productreviews SET description='Eval invalidation {stamp}: "
             f"lens damaged on arrival' WHERE product_id='{SRC_PRODUCT}' AND username='{SRC_USER}'")
        d5, l5 = ask(REVIEW_Q, "m23-a", "m23-c5")
        r.record("cache", "invalidation", d5.get("cacheStatus") == "miss",
                 f"after the review changed: {d5.get('cacheStatus')} (must miss)",
                 l5, d5, hard_bar=True)
    finally:
        psql(f"UPDATE reviews.productreviews SET description='{escaped_original}' "
             f"WHERE product_id='{SRC_PRODUCT}' AND username='{SRC_USER}'")


def _catalog_names():
    raw = psql("SELECT name FROM catalog.products")
    return [n.strip() for n in raw.splitlines() if len(n.strip()) > 3]


def g_semantic(r):
    """L2 semantic cache: paraphrases hit; similar wording with different meaning misses.

    The under-$200 vs over-$200 control pair has high cosine similarity, so this
    case verifies that the semantic rule guard—not threshold alone—prevents a hit."""
    print("== semantic ==")
    clear_cache()
    uid = f"m23-sem-{int(time.time())}"

    ask("How much do the Roof Binoculars cost?", uid, f"{uid}-1")
    d, l = ask("What is the price of the Roof Binoculars?", uid, f"{uid}-2")
    r.record("semantic", "paraphrase-hit", d.get("cacheStatus") == "hit_semantic",
             f"same intent, different wording: {d.get('cacheStatus')} (similarity={d.get('similarity')})",
             l, d)

    ask("Which telescopes cost under 200 USD?", uid, f"{uid}-3")
    d2, l2 = ask("Which telescopes cost over 200 USD?", uid, f"{uid}-4")
    r.record("semantic", "opposite-must-miss", d2.get("cacheStatus") != "hit_semantic",
             f"under→over price constraint: {d2.get('cacheStatus')} (must not hit_semantic)",
             l2, d2, hard_bar=True)

    ask("Does this product have long battery life?", uid, f"{uid}-5")
    d3, l3 = ask("This product does not have durable battery life, correct?", uid, f"{uid}-6")
    r.record("semantic", "negation-must-miss", d3.get("cacheStatus") != "hit_semantic",
             f"negated meaning: {d3.get('cacheStatus')} (must not hit_semantic)",
             l3, d3, hard_bar=True)


def g_shortterm(r):
    """Turn 3 uses a pronoun and must name the product established in prior turns."""
    print("== shortterm ==")
    names = _catalog_names()
    sid = f"m23-st-{int(time.time())}"
    d1, _ = ask("Show me the available telescopes.", "m23-st", sid)
    d2, _ = ask("How much is the first one?", "m23-st", sid)
    d3, l3 = ask("Is it suitable for a beginner? Name the product you are referring to.", "m23-st", sid)

    prev = ((d1.get("response") or "") + " " + (d2.get("response") or "")).lower()
    txt = (d3.get("response") or "").lower()
    carried = [n for n in names if n.lower() in prev and n.lower() in txt]
    ok = bool(carried)
    r.record("shortterm", "three-turns", ok,
             f"turn 3 retained the prior product: {carried[:2] or 'NONE'}", l3, d3)


def g_longterm(r):
    print("== longterm ==")
    uid = f"m23-lt-{int(time.time())}"
    psql(f"DELETE FROM ai.user_memory WHERE user_id='{uid}'")
    ask("I am a beginner interested in stargazing with a budget of about 150 USD.", uid, f"{uid}-A")
    rows = psql(f"SELECT key||'='||value FROM ai.user_memory WHERE user_id='{uid}'")
    r.record("longterm", "stored", bool(rows),
             f"stored memory: {rows.replace(chr(10), ' | ') or 'empty'}")
    d, l = ask("What experience level and intended use did I mention in the previous session?", uid, f"{uid}-B-new")
    txt = (d.get("response") or "").lower()
    remembered_level = "beginner" in txt
    remembered_use = any(w in txt for w in ["stargazing", "astronomy"])
    ok = remembered_level and remembered_use
    r.record("longterm", "recall-new-session", ok,
             f"new session recalled level={remembered_level}, use={remembered_use}", l, d)

    uid2 = f"{uid}-pii"
    ask("My email is test@example.com, my phone is 0912345678, and I like telescopes.",
        uid2, f"{uid2}-A")
    rows2 = psql(f"SELECT value FROM ai.user_memory WHERE user_id='{uid2}'")
    leaked = "test@example.com" in rows2 or "0912345678" in rows2
    r.record("longterm", "pii-redacted", not leaked,
             "PII was not stored in ai.user_memory" if not leaked else f"PII leaked: {rows2[:60]}",
             hard_bar=True)


def g_crossuser(r):
    print("== crossuser ==")
    clear_cache()
    ask(PROBE_Q, "m23-x-a", "m23-x-a1")
    d, l = ask(PROBE_Q, "m23-x-b", "m23-x-b1")
    ok = d.get("cacheStatus") != "hit_exact"
    r.record("crossuser", "no-cache-leak", ok,
             f"user B repeated user A's question: {d.get('cacheStatus')} (must miss)", l, d, hard_bar=True)

    sid = f"m23-borrow-{int(time.time())}"
    ask("I am looking for Roof Binoculars; my session secret is M23-ALPHA-7.", "m23-x-a", sid)
    d2, l2 = ask("What did I ask previously? Do not guess or recommend anything; answer only if this session contains prior context.", "m23-x-b", sid)
    leaked = "m23-alpha-7" in (d2.get("response") or "").lower()
    r.record("crossuser", "no-session-borrow", not leaked,
             "another user's session context was not exposed" if not leaked else "another user's session context leaked",
             l2, d2, hard_bar=True)


def g_bypass(r):
    print("== bypass ==")
    d, l = ask("What is in my cart?", "m23-a", f"m23-cart-{int(time.time())}")
    r.record("bypass", "cart-not-cached", d.get("cacheStatus") == "bypass",
             f"cart query: {d.get('cacheStatus')} (must bypass)", l, d)


NUM_QS = ["Which telescope is the cheapest?", "How much do the Roof Binoculars cost?",
          "Are any astronomy books available?", "Which magnifying glasses are available?",
          "Which film cameras are available?", "Are any rotating globes available?"]


def _run_set(label, disable_cache):
    """Run NUM_QS twice: isolated users force misses; one shared user enables hits."""
    run_id = time.time_ns()
    rows = []
    for i, q in enumerate(NUM_QS * 2):
        uid = f"m23-num-{run_id}-{i}" if disable_cache else f"m23-num-{run_id}"
        d, lat = ask(q, uid, f"m23-num-{run_id}-{i}")
        _, _, tin, tout, usd, _, _ = extract_trace_and_tokens(d, d.get("traceId", ""))
        p_in, p_out = PRICING["amazon.nova-lite-v1:0"]
        normalized_usd = tin / 1_000_000 * p_in + tout / 1_000_000 * p_out
        rows.append({"q": q, "lat": lat, "status": d.get("cacheStatus"),
                     "tin": tin, "tout": tout, "usd": usd, "normalized_usd": normalized_usd})
        print(f"    [{label}] {str(d.get('cacheStatus')):<12} {lat:>6.2f}s  "
              f"in={tin} out={tout} ${usd:.6f}")
    return rows


def _agg(rows):
    lat_hit = [x["lat"] for x in rows if str(x["status"]).startswith("hit")]
    lat_miss = [x["lat"] for x in rows if not str(x["status"]).startswith("hit")]
    return {
        "n": len(rows),
        "hit_exact": sum(1 for x in rows if x["status"] == "hit_exact"),
        "hit_semantic": sum(1 for x in rows if x["status"] == "hit_semantic"),
        "p50_hit": calculate_percentiles(lat_hit)[0], "p95_hit": calculate_percentiles(lat_hit)[1],
        "p50_miss": calculate_percentiles(lat_miss)[0], "p95_miss": calculate_percentiles(lat_miss)[1],
        "tin": sum(x["tin"] for x in rows), "tout": sum(x["tout"] for x in rows),
        "usd": sum(x["usd"] for x in rows),
        "normalized_usd": sum(x["normalized_usd"] for x in rows),
    }


def g_numbers(r):
    """Measure real before/after latency, tokens, and cost with cache disabled/enabled."""
    print("== numbers ==")
    before = _agg(_run_set("before", disable_cache=True))
    after_rows = _run_set("after", disable_cache=False)
    after = _agg(after_rows)

    hits = after["hit_exact"] + after["hit_semantic"]
    rate = hits / after["n"] if after["n"] else 0
    saved = before["normalized_usd"] - after["normalized_usd"]
    saved_pct = (saved / before["normalized_usd"] * 100) if before["normalized_usd"] else 0
    tok_saved = (before["tin"] + before["tout"]) - (after["tin"] + after["tout"])

    r.record("numbers", "hit-rate", rate >= 0.4,
             f"hit-rate {rate*100:.0f}% ({hits}/{after['n']}: exact {after['hit_exact']}, "
             f"semantic {after['hit_semantic']})")
    r.record("numbers", "latency", (after["p95_hit"] < after["p95_miss"]) if hits else False,
             f"p50/p95 hit {after['p50_hit']}s/{after['p95_hit']}s · "
             f"miss {after['p50_miss']}s/{after['p95_miss']}s")
    r.record("numbers", "cost-before-after", saved > 0,
             f"token {before['tin']+before['tout']} → {after['tin']+after['tout']} "
             f"(-{tok_saved}) · normalized Nova Lite USD ${before['normalized_usd']:.6f} → "
             f"${after['normalized_usd']:.6f} (-{saved_pct:.0f}%); "
             f"actual A/B USD ${before['usd']:.6f} → ${after['usd']:.6f}")
    (r.dir / "numbers_raw.json").write_text(
        json.dumps({"before_no_cache": before, "after_with_cache": after,
                    "rows_after": after_rows}, ensure_ascii=False, indent=2),
        encoding="utf-8")


GROUPS = {"cache": g_cache, "semantic": g_semantic, "shortterm": g_shortterm,
          "longterm": g_longterm, "crossuser": g_crossuser, "bypass": g_bypass,
          "numbers": g_numbers}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--only", choices=list(GROUPS))
    p.add_argument("--enforce-hard-bars", action="store_true")
    a = p.parse_args()

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    ev = HERE / "evidence_m23" / ts
    ev.mkdir(parents=True, exist_ok=True)
    r = Runner(ev)

    for name in ([a.only] if a.only else list(GROUPS)):
        GROUPS[name](r)

    passed = sum(1 for x in r.results if x["passed"])
    total = len(r.results)
    lines = [f"# MANDATE-23 Eval Report — {ts}", "",
             f"**Total:** {passed}/{total} pass · hard bar "
             f"{'PASS' if not r.hard_bar_failed else 'FAIL'}", "",
             "| Group | Case | Pass | Reason | Cache | Latency |", "|---|---|---|---|---|---|"]
    for x in r.results:
        lines.append(f"| {x['group']} | {x['case']} | {'✅' if x['passed'] else '❌'} | "
                     f"{x['reason']} | {x['cache_status'] or '—'} | {x['latency']}s |")
    lines += ["", f"Evidence: `{ev.relative_to(HERE.parent.parent)}`"]
    (HERE / "eval_mandate23_report.md").write_text("\n".join(lines), encoding="utf-8")

    print(f"\n{passed}/{total} pass · hard bar {'PASS' if not r.hard_bar_failed else 'FAIL'}")
    print(f"Report: {HERE / 'eval_mandate23_report.md'}")
    if a.enforce_hard_bars and r.hard_bar_failed:
        print("\nHard-bar failed — exit 1")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
