#!/usr/bin/env python3
"""Grid-search tham so Drain3 tren LOG THAT cua he (khong tin default).

Khong co ground-truth label -> tieu chi chon (do duoc, khong cam tinh):
  1. n_templates   : qua it = under-split, qua nhieu = over-split
  2. coverage_top20: % dong roi vao 20 template lon nhat (do "gom" duoc)
  3. singleton_pct : % template chi co 1 dong (nhieu/over-split)
  4. stability     : |templates(nua dau) - templates(nua sau)| / templates(full)
                     (thap = template hoi tu, moi mau moi la novelty that)
  5. error_sep     : cac phrase loi da biet co tach template rieng khong
Usage: python3 drain3_grid.py <logfile>
"""
import os
import re
import sys
from collections import Counter

from drain3 import TemplateMiner
from drain3.template_miner_config import TemplateMinerConfig
from drain3.masking import MaskingInstruction


def _mask_rules():
    pats = [
        (r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", "UUID"),
        (r"\b(?:\d{1,3}\.){3}\d{1,3}\b", "IP"),
        (r"\b\d{4}-\d{2}-\d{2}[T ][\d:.,+Zz-]+\b", "TS"),
        (r"\b\d+\.\d+\b", "FLOAT"),
        (r"\b\d+\b", "NUM"),
    ]
    return [MaskingInstruction(regex_pattern=p, mask_with=m) for p, m in pats]

KNOWN_ERRORS = ["Rate limit reached", "OOMKilled", "too many clients",
                "no such host", "Caught Exception"]
# bo tien to "container-name  | " cua docker compose logs
PREFIX = re.compile(r"^[a-z0-9._-]+\s*\|\s*", re.I)
# bo timestamp dau dong neu co
TS = re.compile(r"^\d{4}-\d{2}-\d{2}[T ][\d:.,+Zz-]+\s*")


def load(path, limit=60000):
    lines = []
    with open(path, errors="replace") as f:
        for raw in f:
            m = TS.sub("", PREFIX.sub("", raw.strip()))
            if m:
                lines.append(m[:500])
            if len(lines) >= limit:
                break
    return lines


def run(lines, sim_th, depth):
    cfg = TemplateMinerConfig()
    cfg.drain_sim_th = sim_th
    cfg.drain_depth = depth
    # Masking: id/timestamp/ip nhung trong dong day len singleton — mask truoc khi mine
    # (baseline giao trinh AIOps cung mask <NUM>/<IP>/<UUID>). Bat bang MASK=1.
    if os.getenv("MASK") == "1":
        cfg.masking_instructions = _mask_rules()
    tm = TemplateMiner(config=cfg)
    for ln in lines:
        tm.add_log_message(ln)
    sizes = Counter()
    for c in tm.drain.clusters:
        sizes[c.cluster_id] = c.size
    n = len(sizes)
    total = sum(sizes.values())
    top20 = sum(s for _, s in sizes.most_common(20)) / total if total else 0
    singles = sum(1 for s in sizes.values() if s == 1) / n if n else 0
    return tm, n, top20, singles


def stability(lines, sim_th, depth):
    half = len(lines) // 2
    _, n1, _, _ = run(lines[:half], sim_th, depth)
    _, n2, _, _ = run(lines[half:], sim_th, depth)
    _, nf, _, _ = run(lines, sim_th, depth)
    return abs(n1 - n2) / nf if nf else 1.0


def error_sep(tm):
    hit = 0
    for phrase in KNOWN_ERRORS:
        for c in tm.drain.clusters:
            if phrase.lower() in c.get_template().lower():
                hit += 1
                break
    return hit


if __name__ == "__main__":
    lines = load(sys.argv[1])
    print(f"log lines: {len(lines)}")
    print(f"{'sim_th':>6} {'depth':>5} | {'templates':>9} {'top20cov':>8} "
          f"{'single%':>7} {'stab':>5} {'err_sep':>7}")
    for sim in (0.3, 0.4, 0.5, 0.6):
        for depth in (4, 5, 6):
            tm, n, cov, sing = run(lines, sim, depth)
            stab = stability(lines, sim, depth)
            es = error_sep(tm)
            print(f"{sim:>6} {depth:>5} | {n:>9} {cov:>8.2%} "
                  f"{sing:>7.2%} {stab:>5.2f} {es:>5}/{len(KNOWN_ERRORS)}")
