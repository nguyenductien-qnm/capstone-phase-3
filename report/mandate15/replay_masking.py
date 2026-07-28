#!/usr/bin/env python3
"""Replay offline ca masking qua CA HAI phien ban code — co va khong winsorize.

Vi sao phai lam offline: winsorize da merge va deploy len cum (#455), nen khong con do
duoc ve "truoc winsorize" bang cach chay that nua. Cua so do do da dong.

Replay offline lai CHAT HON mot lan chay that: ca hai nhanh code chay tren DUNG MOT bo
du lieu dau vao (chuoi Prometheus cua chinh cua so da bom), nen khong bi nhieu do luu
luong khac nhau giua hai lan chay. Dung ky thuat da dung de chot cong SLO o ADR-012.

Mo phong lai chinh xac eval_metric_rule cua develop hien tai: cong SLO, cua so truot 30
mau, arm tu mau thu 5, cooldown 600s theo (rule, service).
"""
import json
import sys
import time
import urllib.parse
import urllib.request

PROM = "http://localhost:9090"
STEP, COOLDOWN = 30, 600
NOHC = ('span_name!="grpc.health.v1.Health/Check",'
        'span_kind=~"SPAN_KIND_SERVER|SPAN_KIND_CONSUMER"')
M = "traces_span_metrics_calls_total"
# service-error-rate-high: nguong tinh 0.10, cong SLO 0.50 -> san dong 0.05
THRESHOLD, GATE = 0.10, 0.50


def qr(expr, start, end):
    u = f"{PROM}/api/v1/query_range?" + urllib.parse.urlencode(
        {"query": expr, "start": int(start), "end": int(end), "step": STEP})
    d = json.load(urllib.request.urlopen(u, timeout=180))
    assert d.get("status") == "success", str(d)[:300]
    return d["data"]["result"]


def simulate(values, winsorize):
    """Tra ve list (ts, method) cho moi lan rule KEU.

    method = 'static' | 'dynamic' — phan biet quan trong: neu su co 2 duoc bat boi tang
    TINH thi bai test masking vo nghia, PASS vi ly do sai.
    """
    history, fires, last = [], [], -1e9
    for ts, v in values:
        static_fired = v > THRESHOLD
        dyn_fired = False
        dynamic_threshold = 0.0
        if len(history) >= 5:
            mean = sum(history) / len(history)
            var = sum((x - mean) ** 2 for x in history) / len(history)
            std = var ** 0.5
            dynamic_threshold = mean + 3 * std
            gate_ok = v >= GATE * THRESHOLD
            if v > dynamic_threshold and (v - mean) > 0.001 and gate_ok:
                dyn_fired = True

        hv = v
        if winsorize and len(history) >= 5:
            hv = min(v, dynamic_threshold)
        history.append(hv)
        if len(history) > 30:
            history.pop(0)

        if (static_fired or dyn_fired) and ts - last >= COOLDOWN:
            fires.append((ts, "static" if static_fired else "dynamic"))
            last = ts
    return fires


def main():
    result_path = sys.argv[1]
    svc = sys.argv[2] if len(sys.argv) > 2 else "frontend"
    d = json.load(open(result_path, encoding="utf-8"))
    evs = d["events"]
    start = min(e["t_start"] for e in evs) - 300
    end = max(e["t_end"] for e in evs) + d.get("settle_seconds", 300) + 120

    expr = (f'sum by (service_name) (rate({M}{{status_code="STATUS_CODE_ERROR",{NOHC}}}[5m]))'
            f' / clamp_min(sum by (service_name) (rate({M}{{{NOHC}}}[5m])), 0.001)')
    series = None
    for s in qr(expr, start, end):
        if s["metric"].get("service_name") == svc:
            series = [(int(float(t)), float(v)) for t, v in s["values"]
                      if v not in ("NaN", "+Inf", "-Inf")]
    if not series:
        print(f"khong co chuoi cho service={svc}")
        return

    print(f"### Replay offline ca masking tren service={svc}")
    print(f"### {len(series)} diem, step {STEP}s, nguong tinh {THRESHOLD}, "
          f"cong SLO {GATE} (san {GATE*THRESHOLD})\n")

    for label, wins in (("KHONG winsorize (truoc #455)", False),
                        ("CO winsorize (sau #455)", True)):
        fires = simulate(series, wins)
        print(f"### {label}: {len(fires)} lan keu")
        caught = []
        for ev in evs:
            lo, hi = ev["t_start"], ev["t_end"] + d.get("settle_seconds", 300)
            hit = [(ts, m) for ts, m in fires if lo <= ts <= hi]
            mark = "BAT DUOC" if hit else "BI CHE"
            extra = f" ({hit[0][1]}, lead {hit[0][0]-lo:.0f}s)" if hit else ""
            print(f"###   {ev['label']:18s} {mark}{extra}")
            caught.append(bool(hit))
        verdict = "PASS" if all(caught) else "FAIL"
        print(f"###   -> VERDICT (masking): {verdict}\n")


if __name__ == "__main__":
    main()
