#!/usr/bin/env python3
"""Render the MANDATE-07 #7b evidence chart from real Prometheus data.

Committed instead of a screenshot on purpose: a screenshot cannot be checked,
while this pulls the same series the detector rule evaluates, writes the raw
response next to the image, and can be re-run by a reviewer against their own
Prometheus. The shaded fault windows and the alert markers are read from the
harness output (`*.result.json`, `alerter_history.jsonl`), not typed in by hand.

    python report/mandate07b/plot_evidence.py                 # live Prometheus
    python report/mandate07b/plot_evidence.py --from-cache    # committed JSON

Needs matplotlib; everything else is stdlib.
"""
import argparse
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
SCENARIOS = os.path.join(REPO, "aiops", "incident_scenarios")
RAW_JSON = os.path.join(HERE, "image", "error_ratio_raw.json")
OUT_PNG = os.path.join(HERE, "image", "error-ratio-timeline.png")

# The exact expression `grpc-error-rate-high` evaluates (aiops/detector/rules.yaml).
QUERY = (
    'sum by (service_name) (rate(rpc_server_duration_milliseconds_count'
    '{rpc_grpc_status_code=~"2|4|13|14"}[5m]))'
    ' / clamp_min(sum by (service_name) '
    '(rate(rpc_server_duration_milliseconds_count[5m])), 0.001)'
)
THRESHOLD = 0.05

# dataviz palette, categorical slots 1-2 + status/critical. Validated with
# scripts/validate_palette.js --mode light: all six checks PASS.
SERIES_COLORS = {"checkout": "#2a78d6", "product-catalog": "#eb6834"}
CRITICAL = "#d03b3b"
INK, INK_MUTED, GRID = "#1a1a19", "#5c5c58", "#e0e0dc"
SURFACE = "#fcfcfb"


def fetch(prom_url, start, end, step=30):
    params = urllib.parse.urlencode(
        {"query": QUERY, "start": int(start), "end": int(end), "step": step})
    with urllib.request.urlopen(f"{prom_url}/api/v1/query_range?{params}", timeout=30) as r:
        return json.load(r)


def load_windows():
    """Fault windows the harness actually injected, from its own output."""
    windows = []
    for name in sorted(os.listdir(SCENARIOS)):
        if not name.endswith(".result.json"):
            continue
        with open(os.path.join(SCENARIOS, name), encoding="utf-8") as f:
            res = json.load(f)
        for ev in res.get("events", []):
            if ev.get("inject") and ev.get("t_start") and ev.get("t_end"):
                windows.append((ev["t_start"], ev["t_end"],
                                res.get("scenario_id", ""), res["verdict"]["pass"]))
    return windows


def load_alerts(rule_id="grpc-error-rate-high"):
    path = os.path.join(HERE, "alerter_history.jsonl")
    out = []
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if rec.get("rule_id") == rule_id:
                out.append((rec["ts"], rec.get("service")))
    return out


def plot(payload, windows, alerts, out_png, uninjected_from=None):
    series = payload["data"]["result"]
    fig, ax = plt.subplots(figsize=(12, 5.5), dpi=160)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)

    # Stagger the window captions: adjacent runs are minutes apart and their
    # labels collided into unreadable mush on the first render.
    for i, (lo, hi, label, passed) in enumerate(sorted(windows)):
        ax.axvspan(datetime.fromtimestamp(lo), datetime.fromtimestamp(hi),
                   color=INK, alpha=0.055, lw=0, zorder=0)
        short = label.replace("case-", "").replace("-001", "")
        ax.annotate(f"{short}  {'PASS' if passed else 'FAIL'}",
                    xy=(datetime.fromtimestamp(lo), 1.10 if i % 2 == 0 else 1.03),
                    fontsize=7.5, color=INK_MUTED,
                    ha="left", va="bottom", annotation_clip=False)

    ax.axhline(THRESHOLD, color=CRITICAL, lw=1.6, ls=(0, (5, 3)), zorder=2)
    ax.annotate(f"rule threshold  {THRESHOLD}", xy=(0.995, THRESHOLD), xycoords=("axes fraction", "data"),
                xytext=(0, 6), textcoords="offset points",
                fontsize=8.5, color=CRITICAL, ha="right", va="bottom", weight="bold")

    peak = None
    for s in series:
        name = s["metric"].get("service_name", "?")
        color = SERIES_COLORS.get(name)
        if color is None:
            continue
        xs = [datetime.fromtimestamp(float(t)) for t, _ in s["values"]]
        ys = [float(v) for _, v in s["values"]]
        ax.plot(xs, ys, color=color, lw=2, label=name, zorder=3,
                solid_capstyle="round")
        hi = max(range(len(ys)), key=lambda i: ys[i])
        if name == "checkout":
            peak = (xs[hi], ys[hi])

    for ts, svc in alerts:
        color = SERIES_COLORS.get(svc, INK_MUTED)
        ax.plot(datetime.fromtimestamp(ts), THRESHOLD, marker="v", markersize=8,
                color=color, markeredgecolor=SURFACE, markeredgewidth=1.6, zorder=5)

    if peak:
        ax.annotate(f"{peak[1]:.3f}", xy=peak, xytext=(6, 4), textcoords="offset points",
                    fontsize=9.5, color=INK, weight="bold")

    # The sustained rise after the last injection is NOT injected — it is the
    # email restart-loop the quiet window uncovered (report §4.6). Labelling it
    # keeps the chart honest; unlabelled it reads as a fourth injection.
    if uninjected_from is not None:
        ax.annotate("no fault injected from here on —\ncheckout failing because the email\n"
                    "service was restart-looping (report §4.6)",
                    xy=(datetime.fromtimestamp(uninjected_from + 600), 0.55),
                    xytext=(150, -40), textcoords="offset points",
                    fontsize=8, color=INK_MUTED, ha="left", va="top",
                    arrowprops=dict(arrowstyle="-", color=GRID, lw=1.2,
                                    shrinkA=2, shrinkB=6))

    ax.set_ylim(-0.04, 1.06)
    ax.set_ylabel("gRPC error ratio", fontsize=9.5, color=INK_MUTED)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    ax.grid(axis="y", color=GRID, lw=0.8, zorder=0)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=INK_MUTED, labelsize=8.5, length=0)

    fig.suptitle("MANDATE-07 #7b — detector fires on a real injected fault",
                 fontsize=13, color=INK, weight="bold", x=0.012, ha="left", y=1.06)
    ax.annotate("Series = the exact expression rule `grpc-error-rate-high` evaluates.  "
                "▼ = alert actually dispatched (alerter_history.jsonl).  "
                "Shaded = fault window injected by incident_replay.py.",
                xy=(0, 1.0), xycoords="axes fraction", xytext=(0, 44),
                textcoords="offset points", fontsize=8.5, color=INK_MUTED)

    leg = ax.legend(frameon=False, fontsize=9, loc="center right", ncol=1)
    for t in leg.get_texts():
        t.set_color(INK)

    fig.tight_layout()
    fig.savefig(out_png, facecolor=SURFACE, bbox_inches="tight")
    print(f"wrote {out_png}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--prom-url", default="http://localhost:9090")
    p.add_argument("--from-cache", action="store_true",
                   help="plot the committed raw JSON instead of querying Prometheus")
    p.add_argument("--pad-seconds", type=int, default=600)
    args = p.parse_args()

    os.makedirs(os.path.join(HERE, "image"), exist_ok=True)
    windows = load_windows()
    if not windows:
        raise SystemExit("no injected windows found in *.result.json — run the harness first")

    if args.from_cache:
        with open(RAW_JSON, encoding="utf-8") as f:
            payload = json.load(f)
    else:
        start = min(w[0] for w in windows) - args.pad_seconds
        end = max(w[1] for w in windows) + args.pad_seconds
        payload = fetch(args.prom_url, start, end)
        with open(RAW_JSON, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=1)
        print(f"wrote {RAW_JSON}")

    # Everything after the last injected window is background, not scenario.
    plot(payload, windows, load_alerts(), OUT_PNG,
         uninjected_from=max(w[1] for w in windows))


if __name__ == "__main__":
    main()
