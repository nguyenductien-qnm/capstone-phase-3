#!/usr/bin/env python3
"""So 2 cach dinh nghia "sut thong luong" tren cung 12h chuoi that.

A) TU THAN : rate5m(svc) / rate1h(svc)
   Cai gi lam ca he tut (load-gen doi tai, dem vang khach) deu keu — va keu DONG LOAT
   ca chuc service, do loi cho tat ca trong khi nguyen nhan la mot thu o thuong nguon.

B) SO BAN : [rate5m(svc)/rate1h(svc)] / [rate5m(tong)/rate1h(tong)]
   Ca he cung tut thi tu va mau cung tut -> ~1.0, khong keu. Chi MOT service chet thi
   ti le cua no -> 0 con cua he ~1 -> keu. Do dung "service nay chet", khong phai
   "hom nay it khach".
"""
import json
import sys
import time
import urllib.parse
import urllib.request

PROM = "http://localhost:9090"
KINDS = 'span_kind=~"SPAN_KIND_SERVER|SPAN_KIND_CONSUMER"'
STEP, HOURS, COOLDOWN = 30, 12, 600
END = int(time.time())
START = END - HOURS * 3600


def qr(expr):
    u = f"{PROM}/api/v1/query_range?" + urllib.parse.urlencode(
        {"query": expr, "start": START, "end": END, "step": STEP})
    d = json.load(urllib.request.urlopen(u, timeout=180))
    if d.get("status") != "success":
        raise SystemExit(json.dumps(d)[:300])
    return d["data"]["result"]


def by_svc(res):
    return {s["metric"].get("service_name", "?"):
            {int(float(t)): float(v) for t, v in s["values"]} for s in res}


def flat(res):
    return {int(float(t)): float(v) for t, v in res[0]["values"]} if res else {}


def count_fires(ratios, threshold):
    fires, last = 0, -1e9
    for ts in sorted(ratios):
        if ratios[ts] < threshold and ts - last >= COOLDOWN:
            fires += 1
            last = ts
    return fires


def main():
    threshold = float(sys.argv[1]) if len(sys.argv) > 1 else 0.2
    gate = float(sys.argv[2]) if len(sys.argv) > 2 else 0.02

    m = f"traces_span_metrics_calls_total{{{KINDS}}}"
    s5 = by_svc(qr(f"sum by (service_name) (rate({m}[5m]))"))
    s1h = by_svc(qr(f"sum by (service_name) (rate({m}[1h]))"))
    t5 = flat(qr(f"sum(rate({m}[5m]))"))
    t1h = flat(qr(f"sum(rate({m}[1h]))"))

    print(f"threshold={threshold}  cong={gate} req/s  {HOURS}h  step={STEP}s  "
          f"cooldown={COOLDOWN}s\n")
    print(f"{'service':20s} {'A tu than':>10s} {'B so ban':>9s} "
          f"{'A min':>8s} {'B min':>8s}")
    print("-" * 60)

    tot_a = tot_b = 0
    for svc in sorted(s1h):
        ra, rb = {}, {}
        for ts, lv in s1h[svc].items():
            sv = s5.get(svc, {}).get(ts)
            if sv is None or lv <= gate:
                continue
            self_ratio = sv / max(lv, 0.001)
            ra[ts] = self_ratio
            T5, T1 = t5.get(ts), t1h.get(ts)
            if T5 is None or T1 is None or T1 <= 0:
                continue
            sys_ratio = T5 / max(T1, 0.001)
            if sys_ratio <= 0.001:
                continue
            rb[ts] = self_ratio / sys_ratio
        fa, fb = count_fires(ra, threshold), count_fires(rb, threshold)
        tot_a += fa
        tot_b += fb
        mna = f"{min(ra.values()):.3f}" if ra else "-"
        mnb = f"{min(rb.values()):.3f}" if rb else "-"
        print(f"{svc:20s} {fa:10d} {fb:9d} {mna:>8s} {mnb:>8s}")

    print("-" * 60)
    print(f"{'TONG':20s} {tot_a:10d} {tot_b:9d}   bao dong / {HOURS}h")


if __name__ == "__main__":
    main()
