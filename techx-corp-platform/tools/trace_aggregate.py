"""Trace aggregate tool — query Valkey for LLM trace records, output cost/latency summary.

Usage: python tools/trace_aggregate.py [--fetch TRACE_ID] [--session SESSION_ID]
"""

from __future__ import annotations

import json
import os
import sys

import redis as _redis


def _valkey_client():
    addr = os.environ.get("VALKEY_ADDR", "localhost:6379")
    host, port = addr.rsplit(":", 1) if ":" in addr else (addr, "6379")
    return _redis.Redis(host=host, port=int(port), decode_responses=True, socket_timeout=2)


def main():
    vc = _valkey_client()
    if "--fetch" in sys.argv:
        idx = sys.argv.index("--fetch")
        tid = sys.argv[idx + 1]
        raw = vc.get(f"trace:{tid}")
        if raw:
            print(json.dumps(json.loads(raw), indent=2))
        else:
            print(f"Trace {tid} not found")
        return

    if "--session" in sys.argv:
        idx = sys.argv.index("--session")
        sid = sys.argv[idx + 1]
        ids = vc.smembers(f"trace:session:{sid}")
        print(f"Session {sid}: {len(ids)} traces")
        for tid in sorted(ids):
            tid_str = tid.decode() if isinstance(tid, bytes) else tid
            raw = vc.get(f"trace:{tid_str}")
            if raw:
                t = json.loads(raw)
                print(f"  {tid_str}: {t.get('model_id','?')} {t.get('outcome','?')} "
                      f"{t.get('latency_ms','?')}ms ${t.get('cost_usd',0):.6f}")
        return

    # Default: aggregate view
    rows: dict[tuple, dict] = {}
    try:
        for key in vc.scan_iter("trace:*", count=100):
            raw = vc.get(key)
            if not raw:
                continue
            t = json.loads(raw)
            group = (t.get("model_id", "?"), t.get("surface", "?"))
            if group not in rows:
                rows[group] = {"model_id": group[0], "surface": group[1],
                               "count": 0, "tokens_in": 0, "tokens_out": 0,
                               "cost": 0.0, "latency_ms": 0}
            r = rows[group]
            r["count"] += 1
            r["tokens_in"] += t.get("tokens_in", 0)
            r["tokens_out"] += t.get("tokens_out", 0)
            r["cost"] += t.get("cost_usd", 0)
            r["latency_ms"] += t.get("latency_ms", 0)
    except Exception as e:
        print(f"Valkey scan error: {e}")
        sys.exit(1)

    print(f"{'Model':<28} {'Surface':<10} {'Calls':>6} {'Tokens In':>10} {'Tokens Out':>10} {'Cost USD':>10} {'Avg Lat':>8}")
    print("-" * 90)
    for g in sorted(rows.values(), key=lambda r: r["cost"], reverse=True):
        avg_lat = f"{g['latency_ms'] / g['count']:.0f}ms" if g["count"] else "-"
        print(f"{g['model_id']:<28} {g['surface']:<10} {g['count']:>6} {g['tokens_in']:>10} "
              f"{g['tokens_out']:>10} ${g['cost']:>9.6f} {avg_lat:>8}")


if __name__ == "__main__":
    main()
