#!/usr/bin/env python3
"""Incident Replay & Scoring Harness — shared "repro" for MANDATE #7b/#15/#22.

This is the "cua replay nhan kich ban tu ngoai" (replay entry accepting external
scenarios) both MANDATE-15 and MANDATE-22 require as a submitted artifact, and the
repro script both #7b and #15 require. One scenario JSON file = one labeled case
(see aiops/incident_scenarios/*.json for the 3 committed cases: real / masking /
healthy_load). Scoring logic is plain, readable Python on purpose — MANDATE-15
explicitly requires the scoring logic to be open for a mentor to read.

Two independent steps, usually run together via `run`:
  inject  — toggle a flagd flag (file-based, same technique as
            docs/ai/evals/measure_detection_pipeline.py) or run an arbitrary
            shell command to create/clear the fault, and record the REAL
            wall-clock start/end of each event (not the planned ones).
  score   — read aiops/detector/alerter_history.jsonl (detection) and/or
            aiops/remediation/audit_log.jsonl (remediation) for the scored
            window and compute precision/recall/lead-time (MANDATE-07 formula)
            or a masking/healthy-load pass-fail verdict (MANDATE-15 formula).

Usage:
  # Self-validation before grading day: inject + score in one go.
  python incident_replay.py run aiops/incident_scenarios/case_real_incident.json

  # Grading day: BTC injects the hidden scenario themselves: skip injection,
  # score only, supplying the window you observed them trigger it in.
  python incident_replay.py score aiops/incident_scenarios/case_real_incident.json \\
      --start 1721800000 --end 1721800120

  # MANDATE-22: also check the remediation audit log for verify/rollback outcome
  # inside the same window.
  python incident_replay.py run aiops/incident_scenarios/case_oom_remediation.json \\
      --check-remediation
"""
import argparse
import json
import os
import subprocess
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_HERE, ".."))

DEFAULT_ALERTER_HISTORY = os.path.join(_HERE, "detector", "alerter_history.jsonl")
DEFAULT_AUDIT_LOG = os.path.join(_HERE, "remediation", "audit_log.jsonl")
DEFAULT_FLAGD_FILE = os.path.join(_REPO_ROOT, "techx-corp-platform", "src", "flagd", "demo.flagd.json")


# ---------------------------------------------------------------------------
# Injection
# ---------------------------------------------------------------------------
def _set_flag(flagd_file, flag, variant):
    with open(flagd_file, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    cfg["flags"][flag]["defaultVariant"] = variant
    with open(flagd_file, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
    print(f"  [inject] flagd {flag} -> {variant}", flush=True)


def _run_command(cmd):
    if not cmd:
        return
    print(f"  [inject] running: {cmd}", flush=True)
    subprocess.run(cmd, shell=True, check=False)


def _inject_on(inject_cfg):
    itype = inject_cfg.get("type")
    if itype == "flagd":
        _set_flag(
            inject_cfg.get("file", DEFAULT_FLAGD_FILE),
            inject_cfg["flag"],
            inject_cfg.get("on_variant", "on"),
        )
    elif itype == "command":
        _run_command(inject_cfg.get("on"))
    elif itype == "manual":
        print(f"  [inject] MANUAL step required: {inject_cfg.get('instructions')}", flush=True)
        input("  press Enter once triggered... ")
    else:
        raise ValueError(f"unknown inject type: {itype}")


def _inject_off(inject_cfg):
    itype = inject_cfg.get("type")
    if itype == "flagd":
        _set_flag(
            inject_cfg.get("file", DEFAULT_FLAGD_FILE),
            inject_cfg["flag"],
            inject_cfg.get("off_variant", "off"),
        )
    elif itype == "command":
        _run_command(inject_cfg.get("off"))
    # "manual": nothing to auto-clear; BTC/mentor controls the hidden scenario.


def _normalize_events(scenario):
    """A scenario is either one flat event (top-level fields) or a list under
    "events" (masking case: noise-spike + a separate, smaller incident).

    For expect_fire=False cases (healthy_load), "expected_rule_ids" is usually
    empty (nothing SHOULD fire) — "monitored_rule_ids" names the rule set we
    watch FOR false positives instead, and doubles as the match set here.
    """
    if "events" in scenario:
        return scenario["events"]
    watch_ids = scenario.get("expected_rule_ids") or scenario.get("monitored_rule_ids", [])
    return [{
        "label": scenario.get("id", "event"),
        "service": scenario.get("service"),
        "expected_rule_ids": watch_ids,
        "expect_fire": scenario.get("expect_fire", True),
        "inject": scenario.get("inject"),
        "offset_seconds": 0,
        "duration_seconds": scenario.get("duration_seconds", 60),
    }]


def do_inject(scenario):
    """Run every event's inject on/off on its own timeline, return the REAL
    (start_ts, end_ts) observed for each event."""
    events = _normalize_events(scenario)
    run_start = time.monotonic()
    results = []
    for ev in events:
        offset = ev.get("offset_seconds", 0)
        wait = offset - (time.monotonic() - run_start)
        if wait > 0:
            time.sleep(wait)
        t_start = time.time()
        if ev.get("inject"):
            _inject_on(ev["inject"])
        duration = ev.get("duration_seconds", 60)
        time.sleep(duration)
        if ev.get("inject"):
            _inject_off(ev["inject"])
        t_end = time.time()
        results.append({**ev, "t_start": t_start, "t_end": t_end})
    settle = scenario.get("settle_seconds", 30)
    if settle:
        print(f"  [inject] settling {settle}s before scoring...", flush=True)
        time.sleep(settle)
    return results


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------
def _load_jsonl(path):
    if not os.path.exists(path):
        return []
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def _alerts_in_window(alerter_history_path, start_ts, end_ts):
    return [r for r in _load_jsonl(alerter_history_path) if start_ts <= r.get("ts", -1) <= end_ts]


def score_events(events, alerter_history_path, settle_seconds=30):
    """MANDATE-07 formula: recall = caught/K; precision = correct fires/total
    fires; lead_time = fire_ts - incident_start_ts. Also flags MANDATE-15's
    masking (all expect_fire=True events must be caught, even the smaller one)
    and healthy-load (no fire) verdicts — the scenario's own "type" decides
    which verdict applies.
    """
    window_start = min(ev["t_start"] for ev in events)
    window_end = max(ev["t_end"] for ev in events) + settle_seconds
    observed = _alerts_in_window(alerter_history_path, window_start, window_end)

    per_event = []
    matched_alert_indices = set()
    for ev in events:
        candidates = [
            (i, a) for i, a in enumerate(observed)
            if a.get("rule_id") in ev.get("expected_rule_ids", [])
            and (ev.get("service") is None or a.get("service") == ev.get("service"))
            and a.get("ts", -1) >= ev["t_start"]
        ]
        candidates.sort(key=lambda ia: ia[1]["ts"])
        fired = bool(candidates)
        first = candidates[0][1] if candidates else None
        if candidates:
            matched_alert_indices.add(candidates[0][0])
        per_event.append({
            "label": ev.get("label"),
            "service": ev.get("service"),
            "expected_rule_ids": ev.get("expected_rule_ids", []),
            "expect_fire": ev.get("expect_fire", True),
            "fired": fired,
            "correct": fired == ev.get("expect_fire", True),
            "lead_time_seconds": (first["ts"] - ev["t_start"]) if first else None,
            "matched_alert": first,
        })

    K = sum(1 for ev in events if ev.get("expect_fire", True))
    caught = sum(1 for pe in per_event if pe["expect_fire"] and pe["fired"])
    recall = (caught / K) if K else None
    total_fires = len(observed)
    correct_fires = len(matched_alert_indices)
    precision = (correct_fires / total_fires) if total_fires else None

    return {
        "window": {"start": window_start, "end": window_end},
        "per_event": per_event,
        "metrics": {
            "K_incidents": K,
            "recall": recall,
            "precision": precision,
            "total_fires_observed": total_fires,
            "correct_fires": correct_fires,
        },
        "raw_alerts_in_window": observed,
    }


def verdict_for_type(scenario_type, per_event):
    """Pass/fail against MANDATE-15's exact "Dat khi" wording."""
    if scenario_type == "real":
        ok = all(pe["fired"] for pe in per_event if pe["expect_fire"])
        return ok, "real incident fired within window" if ok else "real incident NOT caught"
    if scenario_type == "masking":
        missed = [pe["label"] for pe in per_event if pe["expect_fire"] and not pe["fired"]]
        ok = not missed
        return ok, "both events caught, not masked" if ok else f"masked/missed: {missed}"
    if scenario_type == "healthy_load":
        false_positives = [pe["label"] for pe in per_event if not pe["expect_fire"] and pe["fired"]]
        ok = not false_positives
        return ok, "no false alarm under load" if ok else f"false alarm(s): {false_positives}"
    return None, "unknown scenario type, no verdict rule"


def check_remediation(audit_log_path, window_start, window_end):
    """MANDATE-22: pull the remediation audit trail for the same window —
    used to show detect->safety->act->verify(->rollback/escalate)."""
    records = [r for r in _load_jsonl(audit_log_path) if window_start <= r.get("ts", -1) <= window_end]
    return records


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _print_report(scenario, score, remediation_records=None):
    print("\n" + "=" * 70)
    print(f"SCENARIO: {scenario.get('id')} [{scenario.get('type')}]")
    print(scenario.get("description", ""))
    print("-" * 70)
    for pe in score["per_event"]:
        status = "FIRED" if pe["fired"] else "silent"
        lead = f"{pe['lead_time_seconds']:.1f}s" if pe["lead_time_seconds"] is not None else "n/a"
        print(f"  [{pe['label']}] expect_fire={pe['expect_fire']} -> {status} "
              f"(lead_time={lead}) {'OK' if pe['correct'] else 'MISMATCH'}")
    m = score["metrics"]
    print("-" * 70)
    print(f"  K incidents = {m['K_incidents']} | recall = {m['recall']} | "
          f"precision = {m['precision']} (correct={m['correct_fires']}/total={m['total_fires_observed']})")
    ok, reason = verdict_for_type(scenario.get("type"), score["per_event"])
    print(f"  VERDICT ({scenario.get('type')}): {'PASS' if ok else 'FAIL'} — {reason}")
    if remediation_records is not None:
        print("-" * 70)
        print(f"  remediation audit records in window: {len(remediation_records)}")
        for r in remediation_records:
            print(f"    outcome={r.get('outcome')} verify={r.get('verify')} "
                  f"rollback_or_escalate={r.get('rollback_or_escalate')}")
    print("=" * 70 + "\n")


def _write_result(scenario_path, scenario, events, score, remediation_records):
    ok, reason = verdict_for_type(scenario.get("type"), score["per_event"])
    result = {
        "scenario_id": scenario.get("id"),
        "type": scenario.get("type"),
        "events": events,
        "score": score,
        "verdict": {"pass": ok, "reason": reason},
        "remediation_records": remediation_records,
    }
    out_path = os.path.splitext(scenario_path)[0] + ".result.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, default=str)
    print(f"  result written to {out_path}")
    return out_path


def cmd_run(args):
    with open(args.scenario, "r", encoding="utf-8") as f:
        scenario = json.load(f)
    events = do_inject(scenario)
    score = score_events(events, args.alerter_history, scenario.get("settle_seconds", 30))
    remediation_records = None
    if args.check_remediation:
        remediation_records = check_remediation(args.audit_log, score["window"]["start"], score["window"]["end"])
    _print_report(scenario, score, remediation_records)
    _write_result(args.scenario, scenario, events, score, remediation_records)


def cmd_score(args):
    with open(args.scenario, "r", encoding="utf-8") as f:
        scenario = json.load(f)
    events = _normalize_events(scenario)
    if args.start is None or args.end is None:
        print("score-only mode requires --start/--end (the window you observed "
              "the hidden scenario run in)", file=sys.stderr)
        sys.exit(2)
    # Grading-day mode: BTC injected it, not us — assign every event the same
    # externally-observed window instead of per-event t_start/t_end.
    for ev in events:
        ev["t_start"] = args.start
        ev["t_end"] = args.end
    score = score_events(events, args.alerter_history, scenario.get("settle_seconds", 0))
    remediation_records = None
    if args.check_remediation:
        remediation_records = check_remediation(args.audit_log, score["window"]["start"], score["window"]["end"])
    _print_report(scenario, score, remediation_records)
    _write_result(args.scenario, scenario, events, score, remediation_records)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("scenario", help="path to a scenario JSON file (aiops/incident_scenarios/*.json)")
    common.add_argument("--alerter-history", default=DEFAULT_ALERTER_HISTORY)
    common.add_argument("--audit-log", default=DEFAULT_AUDIT_LOG)
    common.add_argument("--check-remediation", action="store_true",
                        help="also pull aiops/remediation/audit_log.jsonl for this window (MANDATE-22)")

    p_run = sub.add_parser("run", parents=[common], help="inject the scenario live, then score it")
    p_run.set_defaults(func=cmd_run)

    p_score = sub.add_parser("score", parents=[common],
                             help="score only, against an externally-observed window (grading day / BTC-injected)")
    p_score.add_argument("--start", type=float, default=None, help="unix ts the injected scenario started")
    p_score.add_argument("--end", type=float, default=None, help="unix ts the injected scenario ended")
    p_score.set_defaults(func=cmd_score)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
