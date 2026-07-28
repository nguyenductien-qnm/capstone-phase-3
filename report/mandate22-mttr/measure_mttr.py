#!/usr/bin/env python3
"""Do MTTR cua vong tu dap tren pod moi mttr-canary (TF1-106).

MTTR = tu luc container bi OOMKill den luc pod Ready tro lai.

Vi sao phai do theo goc nay: Kubernetes DA tu restart pod OOMKilled roi, nen "before"
khong phai "nam chet". Gia tri that cua vong tu dap la o CrashLoopBackOff — kubelet lui
theo cap so nhan (10s, 20s, 40s, 80s, 160s, toi da 300s) khi pod OOM lien tuc, con
remediation XOA pod nen lich lai moi va backoff ve 0.

Ghi lai moi chu ky: thoi diem OOM, thoi diem Ready tro lai, so restart, va pod name
(doi ten = pod bi xoa va tao lai, tuc remediation da hanh dong).
"""
import json
import subprocess
import sys
import time
from datetime import datetime, timezone

NS = "techx-tf1"
SEL = "opentelemetry.io/name=mttr-canary"


def kubectl_json(*args):
    try:
        out = subprocess.run(["kubectl", "-n", NS, *args, "-o", "json"],
                             capture_output=True, text=True, timeout=30)
        return json.loads(out.stdout) if out.stdout.strip() else None
    except Exception:
        return None


def parse_ts(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


def snapshot():
    d = kubectl_json("get", "pods", "-l", SEL)
    if not d or not d.get("items"):
        return None
    p = d["items"][0]
    cs = (p.get("status", {}).get("containerStatuses") or [{}])[0]
    term = (cs.get("lastState", {}) or {}).get("terminated", {}) or {}
    running = (cs.get("state", {}) or {}).get("running", {}) or {}
    return {
        "pod": p["metadata"]["name"],
        "ready": cs.get("ready", False),
        "restarts": cs.get("restartCount", 0),
        "last_oom_at": parse_ts(term.get("finishedAt")) if term.get("reason") == "OOMKilled" else None,
        "last_reason": term.get("reason"),
        "started_at": parse_ts(running.get("startedAt")),
    }


def main():
    label = sys.argv[1] if len(sys.argv) > 1 else "before"
    minutes = float(sys.argv[2]) if len(sys.argv) > 2 else 12
    deadline = time.time() + minutes * 60

    print(f"### Do MTTR [{label}] trong {minutes:.0f} phut")
    print(f"### {'gio':>8s} {'pod':>30s} {'ready':>6s} {'restart':>8s} {'su kien':<28s}")
    print("### " + "-" * 88)

    cycles = []           # {oom_at, ready_at, restarts, pod}
    pending_oom = None
    prev = None

    while time.time() < deadline:
        s = snapshot()
        if s is None:
            time.sleep(5)
            continue

        ev = ""
        if prev is None:
            ev = "bat dau theo doi"
        else:
            if s["pod"] != prev["pod"]:
                ev = f"POD MOI (cu: {prev['pod'][-12:]}) <- da bi xoa"
            elif s["restarts"] > prev["restarts"]:
                ev = f"OOM lan {s['restarts']}"
                pending_oom = s["last_oom_at"] or time.time()
            elif s["ready"] and not prev["ready"] and pending_oom:
                ready_at = time.time()
                mttr = ready_at - pending_oom
                cycles.append({"oom_at": pending_oom, "ready_at": ready_at,
                               "mttr": mttr, "restarts": s["restarts"], "pod": s["pod"]})
                ev = f"READY tro lai — MTTR = {mttr:.1f}s"
                pending_oom = None
            elif not s["ready"] and prev["ready"]:
                ev = "mat READY"

        if ev:
            print(f"### {datetime.now().strftime('%H:%M:%S'):>8s} {s['pod'][-30:]:>30s} "
                  f"{str(s['ready']):>6s} {s['restarts']:>8d} {ev:<28s}", flush=True)
        prev = s
        time.sleep(5)

    print("### " + "-" * 88)
    if not cycles:
        print("### Khong ghi duoc chu ky nao — chay lai lau hon, hoac pod khong OOM.")
        return
    vals = [c["mttr"] for c in cycles]
    print(f"### [{label}] {len(vals)} chu ky do duoc")
    for i, c in enumerate(cycles, 1):
        print(f"###   chu ky {i}: MTTR = {c['mttr']:7.1f}s  (sau restart thu {c['restarts']})")
    print(f"### [{label}] MTTR trung binh = {sum(vals)/len(vals):.1f}s  "
          f"min = {min(vals):.1f}s  max = {max(vals):.1f}s")

    out = f"report/mandate15/mttr-{label}.json"
    try:
        with open(out, "w", encoding="utf-8") as f:
            json.dump({"label": label, "cycles": cycles,
                       "mean": sum(vals)/len(vals), "min": min(vals), "max": max(vals)},
                      f, indent=2)
        print(f"### ghi: {out}")
    except OSError as exc:
        print(f"### khong ghi duoc {out}: {exc}")


if __name__ == "__main__":
    main()
