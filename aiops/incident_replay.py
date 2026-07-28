#!/usr/bin/env python3
"""Incident Replay & Scoring Harness — repro for MANDATE-07 #7b, designed to also
serve as the "replay entry accepting external scenarios" MANDATE-15 and MANDATE-22
will require (built generically on purpose; those mandates' own labeled scenario
files land in their own PRs — see aiops/incident_scenarios/README.md for the
current set). One scenario JSON file = one labeled case. Scoring logic is plain,
readable Python on purpose — reviewable end to end by a mentor, no framework.

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
  # score only, supplying the window you observed them trigger it in. The scenario
  # file may live ANYWHERE — it does not have to be inside this repo.
  python incident_replay.py score /path/to/btc-hidden-scenario.json \\
      --start 1721800000 --end 1721800120

  # Multi-event hidden scenarios (masking) are supported: the observed window is
  # split per event using the scenario own offset_seconds/duration_seconds, so a
  # single alert can never satisfy two events. Scenario rule ids are checked against
  # rules.yaml and a loud warning is printed if one does not exist.

  # --check-remediation also pulls aiops/remediation/audit_log.jsonl for the same
  # window (used once MANDATE-22's remediation scenario lands on top of this).
  python incident_replay.py run aiops/incident_scenarios/case_real_incident.json \\
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
        # ensure_ascii=False / trailing newline: this rewrites a tracked file, and
        # without them every injection escapes the non-ASCII already in the flag
        # descriptions and drops the final newline, so `git diff` shows unrelated
        # churn after each run. Found while capturing the #7b evidence.
        json.dump(cfg, f, indent=2, ensure_ascii=False)
        f.write("\n")
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


# Alert do detector tu bao cao ve CHINH NO, khong phai quan sat ve he thong duoc do.
# `detector-silent-rule` keu khi mot rule tra ve 0 series suot N chu ky (tuc rule do dang
# mu). No khong phai mot phat hien dung hay sai ve su co dang replay, nhung
# `total_fires = len(observed)` dem MOI alert trong cua so, nen de nguyen thi mot bao cao
# rule-mu roi trung cua so se KEO TUT precision do duoc, trong khi no khong noi len dieu gi
# ve viec detector bat su co chinh xac den dau.
_SELF_REPORT_RULE_IDS = {"detector-silent-rule"}


def _alerts_in_window(alerter_history_path, start_ts, end_ts):
    return [
        r for r in _load_jsonl(alerter_history_path)
        if start_ts <= r.get("ts", -1) <= end_ts
        and r.get("rule_id") not in _SELF_REPORT_RULE_IDS
    ]


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
        # An alert belongs to this event only if it lands inside THIS event's own
        # window (+settle), not merely after it started. Without the upper bound a
        # multi-event scenario lets the earlier event swallow an alert that belongs
        # to a much later one: measuring the EKS set, the payment case (detector was
        # silent for it) was scored as caught with lead_time=1166s by stealing the
        # cart case's alert 19 minutes later. Single-event scenarios never showed it
        # because `observed` is already clipped to the global window.
        ev_end = ev["t_end"] + settle_seconds
        candidates = [
            (i, a) for i, a in enumerate(observed)
            if a.get("rule_id") in ev.get("expected_rule_ids", [])
            and (ev.get("service") is None or a.get("service") == ev.get("service"))
            and ev["t_start"] <= a.get("ts", -1) <= ev_end
        ]
        candidates.sort(key=lambda ia: ia[1]["ts"])
        fired = bool(candidates)
        first = candidates[0][1] if candidates else None
        # Only an event that SHOULD fire can contribute a correct fire. On a
        # no-fire window (healthy_load) the watch set is what we look for false
        # positives with, so a match there is precisely a wrong alert — counting
        # it as correct inflated precision on exactly the case built to catch
        # over-alerting.
        if candidates and ev.get("expect_fire", True):
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
    warn_unknown_rule_ids(_normalize_events(scenario))
    events = do_inject(scenario)
    score = score_events(events, args.alerter_history, scenario.get("settle_seconds", 30))
    remediation_records = None
    if args.check_remediation:
        remediation_records = check_remediation(args.audit_log, score["window"]["start"], score["window"]["end"])
    _print_report(scenario, score, remediation_records)
    _write_result(args.scenario, scenario, events, score, remediation_records)


DEFAULT_RULES_YAML = os.path.join(_HERE, "detector", "rules.yaml")


def known_rule_ids(path=DEFAULT_RULES_YAML):
    """Doc id cua moi rule trong rules.yaml. Tra ve None neu khong doc duoc.

    Co y KHONG dung PyYAML: incident_replay.py chi phu thuoc stdlib, va harness phai
    chay duoc tren may cua giam khao ma khong can cai them gi. Chi can bat dong
    `  - id: <ten>` o dau muc rule nen mot bo doc dong don gian la du.
    """
    if not os.path.exists(path):
        return None
    ids = set()
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                s = line.strip()
                if s.startswith("- id:"):
                    ids.add(s.split(":", 1)[1].strip().strip('"\''))
    except OSError:
        return None
    return ids or None


def warn_unknown_rule_ids(events, path=DEFAULT_RULES_YAML):
    """Keu to neu scenario dan mot rule id KHONG CO trong rules.yaml.

    Vi sao can: mot rule id sai khong gay loi gi ca — `candidates` chi rong, su kien
    bi cham la "silent", va ca kich ban FAIL ma khong mot dau hieu nao noi rang nguyen
    nhan la go sai ten chu khong phai detector mu. Dung lop loi da tra gia hai lan:
    rule kafka sai ten metric nam cam hang tuan, va lan doi ten grpc-error-rate-high ->
    service-error-rate-high o #452 lam 5 file scenario cham sai.

    Nguy hiem nhat vao NGAY CHAM: kich ban do BTC dua toi co the dan ten rule khong
    khop voi rules.yaml hien tai, va ta se bao FAIL ma tuong la minh do.

    Chi CANH BAO chu khong chan: rule id la cua BTC, ho co quyen dat ten khac.
    """
    valid = known_rule_ids(path)
    if not valid:
        return []
    unknown = set()
    for ev in events:
        for rid in ev.get("expected_rule_ids", []) or []:
            if rid not in valid:
                unknown.add(rid)
    if unknown:
        print("", file=sys.stderr)
        print("!" * 70, file=sys.stderr)
        print("CANH BAO: scenario dan rule id KHONG CO trong rules.yaml:", file=sys.stderr)
        for rid in sorted(unknown):
            print(f"    - {rid}", file=sys.stderr)
        print("Nhung su kien cho rule nay se KHONG BAO GIO khop, va se bi cham la", file=sys.stderr)
        print("'silent' -> FAIL. Do la loi CAU HINH, khong phai detector mu.", file=sys.stderr)
        print(f"Rule dang co: {', '.join(sorted(valid))}", file=sys.stderr)
        print("!" * 70, file=sys.stderr)
        print("", file=sys.stderr)
    return sorted(unknown)


def _assign_observed_window(events, start, end):
    """Trai cua so quan sat duoc len tung su kien theo dung moc thoi gian cua scenario.

    Ban truoc gan CUNG MOT cua so cho MOI su kien:
        for ev in events: ev["t_start"] = start; ev["t_end"] = end
    Voi kich ban mot su kien thi dung. Voi kich ban NHIEU su kien thi sai nghiem trong:
    moi su kien deu nhan ca cua so, nen MOT alert duy nhat khop cho TAT CA — ca masking
    se bao PASS ke ca khi su co thu hai bi che hoan toan. Da xac nhan bang thuc nghiem:
    hai su kien cung tra ve lead_time=200.9s tu cung mot alert, va verdict PASS trong
    khi correct=1/total=2.

    Dieu do dac biet nguy hiem vi bo kich ban an cua MANDATE-15 CO ca masking, tuc dung
    loai nhieu su kien.

    Cach lam: scenario tu khai timeline tuong doi bang offset_seconds/duration_seconds.
    Anh xa TUYEN TINH timeline do vao cua so quan sat duoc. Neu do dai hai ben bang nhau
    thi phep anh xa la dong nhat; neu BTC chay nhanh/cham hon thi ti le duoc giu nguyen.
    """
    if not events:
        return
    if len(events) == 1:
        events[0]["t_start"], events[0]["t_end"] = start, end
        return

    spans = [(ev.get("offset_seconds", 0),
              ev.get("offset_seconds", 0) + ev.get("duration_seconds", 60))
             for ev in events]
    scenario_len = max(hi for _, hi in spans)
    observed_len = end - start

    if scenario_len <= 0 or observed_len <= 0:
        for ev in events:
            ev["t_start"], ev["t_end"] = start, end
        return

    # Moi su kien cung offset -> khong the tach duoc bang timeline. Noi ra thay vi
    # am tham cham sai.
    if len({lo for lo, _ in spans}) == 1:
        print("CANH BAO: moi su kien co cung offset_seconds nen khong tach duoc theo "
              "thoi gian; dung chung ca cua so quan sat. Diem tung su kien se khong "
              "dang tin.", file=sys.stderr)
        for ev in events:
            ev["t_start"], ev["t_end"] = start, end
        return

    scale = observed_len / scenario_len
    for ev, (lo, hi) in zip(events, spans):
        ev["t_start"] = start + lo * scale
        ev["t_end"] = start + hi * scale


def cmd_score(args):
    with open(args.scenario, "r", encoding="utf-8") as f:
        scenario = json.load(f)
    events = _normalize_events(scenario)
    if args.start is None or args.end is None:
        print("score-only mode requires --start/--end (the window you observed "
              "the hidden scenario run in)", file=sys.stderr)
        sys.exit(2)
    warn_unknown_rule_ids(events)
    _assign_observed_window(events, args.start, args.end)
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
