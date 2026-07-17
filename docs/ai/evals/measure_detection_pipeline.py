#!/usr/bin/env python3
"""Do that (real measurement) cho cau hoi CDO: poll interval detector.

Phase 1  ingest-lag : T(request gay log) -> T(log query duoc tren OpenSearch).
Phase 2  MTTD       : T(bat llmRateLimitError qua flagd file) -> T(phrase rule
                      llm-rate-limit-429 xuat hien tren OpenSearch).
Suy ra   MTTD(P)    = do_tre_do_duoc + U(0, P) cho P in {10,30,60,120}s
                      (poll offset la co che deterministic, khong phai gia dinh).

Chay tren docker-compose stack local. Khong ghi file output — stdout only.
"""
import json
import sys
import time
import urllib.request

OS_URL = "http://localhost:32804"
FRONT = "http://localhost:8080"
FLAGD_FILE = "techx-corp-platform/src/flagd/demo.flagd.json"
PRODUCT = "L9ECAV7KIM"
PHRASE_INGEST = "Receive AskProductAIAssistant"
PHRASES_429 = ["Rate limit reached", "rate_limit_exceeded", "429"]


def http_json(url, body=None, timeout=5):
    req = urllib.request.Request(url, method="POST" if body else "GET")
    req.add_header("Content-Type", "application/json")
    data = json.dumps(body).encode() if body else None
    with urllib.request.urlopen(req, data=data, timeout=timeout) as r:
        return json.loads(r.read())


def os_count(phrases, window_minutes=5):
    should = [{"match_phrase": {"body": p}} for p in phrases]
    q = {"query": {"bool": {
        "filter": [{"range": {"observedTimestamp": {"gte": f"now-{window_minutes}m"}}}],
        "should": should, "minimum_should_match": 1}}}
    return http_json(f"{OS_URL}/otel-logs-*/_count", q)["count"]


def ask_ai():
    try:
        http_json(f"{FRONT}/api/product-ask-ai-assistant/{PRODUCT}",
                  {"question": "Can you summarize the product reviews?"}, timeout=30)
    except Exception as e:
        print(f"    (ask-ai response err: {type(e).__name__})", flush=True)


def wait_count_increase(phrases, baseline, timeout_s=180, step=0.5):
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout_s:
        if os_count(phrases) > baseline:
            return time.monotonic() - t0
        time.sleep(step)
    return None


def set_flag(name, variant):
    with open(FLAGD_FILE) as f:
        cfg = json.load(f)
    cfg["flags"][name]["defaultVariant"] = variant
    with open(FLAGD_FILE, "w") as f:
        json.dump(cfg, f, indent=2)


def phase_ingest(n=8):
    print("== Phase 1: ingest lag (request -> queryable on OpenSearch) ==")
    lags = []
    for i in range(n):
        base = os_count([PHRASE_INGEST])
        ask_ai()
        lag = wait_count_increase([PHRASE_INGEST], base)
        lags.append(lag)
        print(f"  sample {i+1}: {'TIMEOUT' if lag is None else f'{lag:.1f}s'}", flush=True)
        time.sleep(3)
    ok = sorted(x for x in lags if x is not None)
    if ok:
        print(f"  ingest lag: n={len(ok)} P50={ok[len(ok)//2]:.1f}s max={ok[-1]:.1f}s")
    return ok


def phase_mttd(rounds=5):
    print("== Phase 2: MTTD (flag ON -> phrase 429 tren OpenSearch) ==")
    seen = []
    for r in range(rounds):
        base = os_count(PHRASES_429)
        set_flag("llmRateLimitError", "on")
        t0 = time.monotonic()
        # mock tra 429 ~50%/request -> ban 10 request de gan nhu chac chan dinh
        for _ in range(10):
            ask_ai()
        lag = wait_count_increase(PHRASES_429, base)
        elapsed = None if lag is None else time.monotonic() - t0
        set_flag("llmRateLimitError", "off")
        seen.append(elapsed)
        print(f"  round {r+1}: T_seen-T0 = {'TIMEOUT' if elapsed is None else f'{elapsed:.1f}s'}", flush=True)
        time.sleep(20)
    ok = sorted(x for x in seen if x is not None)
    if ok:
        print(f"  detectable-on-OS delay: n={len(ok)} P50={ok[len(ok)//2]:.1f}s max={ok[-1]:.1f}s")
        print("\n== Suy MTTD theo poll interval (offset poll = U(0,P), deterministic) ==")
        print(f"  {'poll':>6} | {'MTTD trung binh':>16} | {'MTTD max':>9}")
        for p in (10, 30, 60, 120):
            mean = sum(ok) / len(ok) + p / 2
            worst = ok[-1] + p
            print(f"  {p:>5}s | {mean:>15.1f}s | {worst:>8.1f}s")
    return ok


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    if mode in ("all", "ingest"):
        phase_ingest()
    if mode in ("all", "mttd"):
        phase_mttd()
