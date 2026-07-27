#!/usr/bin/env python3
"""Hieu chinh do lon "su co 2" cua ca masking (MANDATE-15).

Muc tieu: tim thoi luong gian doan `cart` sao cho ti le loi cua `checkout` roi vao
(0.05, 0.10) — TREN cong SLO (0.50 x 0.10) nhung DUOI nguong tinh (0.10), tuc chi
tang 3-sigma bat duoc. Vuot 0.10 thi tang tinh keu va bai test masking vo nghia.

Bom NGAN va khoi phuc ve dung minReplicas cua HPA (2).
"""
import json
import subprocess
import sys
import time
import urllib.parse
import urllib.request

NS = "techx-tf1"
PROM = "http://localhost:9090"
NOHC = ('span_name!="grpc.health.v1.Health/Check",'
        'span_kind=~"SPAN_KIND_SERVER|SPAN_KIND_CONSUMER"')
M = "traces_span_metrics_calls_total"
Q = (f'sum by (service_name) (rate({M}{{status_code="STATUS_CODE_ERROR",{NOHC}}}[5m]))'
     f' / clamp_min(sum by (service_name) (rate({M}{{{NOHC}}}[5m])), 0.001)')

GATE, STATIC = 0.05, 0.10


def ratio(svc="checkout"):
    try:
        u = f"{PROM}/api/v1/query?" + urllib.parse.urlencode({"query": Q})
        d = json.load(urllib.request.urlopen(u, timeout=10))
        for s in d["data"]["result"]:
            if s["metric"].get("service_name") == svc:
                return float(s["value"][1])
    except Exception as exc:
        print(f"    (query loi: {exc})")
    return 0.0


def scale(n):
    subprocess.run(["kubectl", "-n", NS, "scale", "deploy/cart", f"--replicas={n}"],
                   capture_output=True, timeout=30)


def main():
    dur = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    watch = int(sys.argv[2]) if len(sys.argv) > 2 else 390

    print(f"### Hieu chinh: cart -> 0 replica trong {dur}s, theo doi {watch}s")
    print(f"### Dai muc tieu cho su co 2: ({GATE}, {STATIC})\n")
    print(f"{'thoi diem':>10s} {'ti-le':>9s}  ghi chu")
    print(f"{'-'*10} {'-'*9}  {'-'*30}")
    print(f"{'t=-5s':>10s} {ratio():>9.4f}  truoc khi bom")

    scale(0)
    t0 = time.time()
    print(f"{'t=0':>10s} {ratio():>9.4f}  cart -> 0 replica")
    time.sleep(dur)
    scale(2)
    print(f"{f't={dur}s':>10s} {ratio():>9.4f}  cart -> 2 (khoi phuc)")

    peak, peak_t = 0.0, 0
    while True:
        el = int(time.time() - t0)
        if el >= watch:
            break
        time.sleep(20)
        r = ratio()
        el = int(time.time() - t0)
        note = ""
        if r > peak:
            peak, peak_t, note = r, el, "<- dinh moi"
        if GATE < r < STATIC:
            note += "  [TRONG DAI MUC TIEU]"
        elif r >= STATIC:
            note += "  [VUOT nguong tinh -> tang tinh se keu]"
        print(f"{f't={el}s':>10s} {r:>9.4f}  {note}")

    print(f"\n### Dinh do duoc: {peak:.4f} tai t={peak_t}s")
    if peak <= 0.001:
        print("### Khong len duoc ti le nao. Gian doan qua ngan, hoac cart khong con")
        print("### nam tren duong di dong bo cua checkout — phai kiem lai.")
    else:
        print(f"### Suy ra tuyen tinh: {dur}s -> dinh {peak:.4f}")
        for tgt in (0.06, 0.07, 0.08):
            print(f"###   de dat ~{tgt}: can ~{dur * tgt / peak:.0f}s gian doan")
    out = subprocess.run(["kubectl", "-n", NS, "get", "deploy", "cart",
                          "-o", "jsonpath={.spec.replicas}"],
                         capture_output=True, text=True, timeout=30)
    print(f"### cart hien tai: {out.stdout} replica (HPA minReplicas = 2)")


if __name__ == "__main__":
    main()
