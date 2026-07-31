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

  # MANDATE-26: RCA on the same window — names ONE suspected root service with the
  # evidence behind it, not just a list of whatever is red. Works standalone (the
  # mentor supplies a window, no scenario file needed) or attached to run/score.
  python incident_replay.py rca --start 1721800000 --end 1721800120 \\
      --prom-url http://localhost:9090
  python incident_replay.py score /path/to/btc-hidden-scenario.json \\
      --start .. --end .. --rca
  # MANDATE-28: dong canh bao theo thoi gian + danh sach incident, de doi chieu xem mot
  # su co keo dai co bi "khoang cam" giua chung khong. Khong can scenario file.
  python incident_replay.py timeline --start 1721800000 --end 1721803600
"""
import argparse
import json
import os
import subprocess
import sys
import time

import diagnose
import timeline

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


def build_schedule(events):
    """(thoi diem tuong doi, "on"/"off", chi so su kien) da sap theo thoi gian.

    Tach rieng khoi do_inject de test duoc lich bom ma khong phai cho that.
    """
    schedule = []
    for i, ev in enumerate(events):
        on_at = ev.get("offset_seconds", 0)
        schedule.append((on_at, "on", i))
        schedule.append((on_at + ev.get("duration_seconds", 60), "off", i))
    # Sap theo thoi gian; cung thoi diem thi TAT truoc BAT, de hai su kien noi duoi nhau
    # tren cung mot diem bom khong bi bat roi tat ngay.
    return sorted(schedule, key=lambda s: (s[0], 0 if s[1] == "off" else 1))


def do_inject(scenario):
    """Bom moi su kien theo lich CHUNG, tra ve (t_start, t_end) THAT quan sat duoc.

    Truoc day ham nay chay TUAN TU: bat su kien 1, sleep het duration, tat, roi moi den su
    kien 2. Nghia la hai su co KHONG BAO GIO chong nhau duoc, du scenario khai offset the nao.
    MANDATE-28 lai doi dung dieu do — "mot su co thu hai xuat hien o service khac GIUA LUC su
    co dau chua dut". Nen doi sang chay theo mot lich gom tat ca moc bat/tat roi sap theo
    thoi gian: van mot luong, van khong co dong bo hoa gi, nhung chong lan thi lam duoc.

    Voi kich ban khong chong lan (moi ca hien co) hanh vi khong doi mot chut nao.

    RANG BUOC: hai su kien chong nhau KHONG duoc dung chung mot diem bom — tat su kien 1 se
    xoa luon loi cua su kien 2. Kich ban phai bom o hai service khac nhau.
    """
    events = _normalize_events(scenario)
    results = [dict(ev) for ev in events]
    run_start = time.monotonic()

    for at, action, idx in build_schedule(events):
        wait = at - (time.monotonic() - run_start)
        if wait > 0:
            time.sleep(wait)
        ev = events[idx]
        if ev.get("inject"):
            (_inject_on if action == "on" else _inject_off)(ev["inject"])
        results[idx]["t_start" if action == "on" else "t_end"] = time.time()

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
            # MANDATE-28: mot su co keo dai phai duoc bao XUYEN SUOT. `fired` chi noi "co keu
            # it nhat mot lan" nen no khong tra loi duoc cau do. Tinh o day (chu khong trong
            # verdict_for_type) vi day la cho duy nhat con giu duong dan alerter_history.
            # Rẻ, va tinh cho MOI loai kich ban de bao cao nao cung doc duoc nhip bao.
            "silent_gaps": timeline.silent_gaps(
                observed, ev.get("expected_rule_ids", []), ev.get("service"),
                ev["t_start"], ev_end,
            ) if ev.get("expect_fire", True) else [],
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
    if scenario_type == "sustained":
        # MANDATE-28 "Kiem duoc": bao LIEN TUC suot su co dai (khong khoang cam) · su co thu 2
        # no chong -> phat hien + TACH RIENG · khong bao gia vi tai hop le doi.
        #
        # Ba dieu kien deu kiem tren per_event chu khong tren tong so alert: mot su co bi bo
        # lo hoan toan va mot su co duoc bao lien tuc cho ra cung mot "tong so alert" neu chi
        # dem, nen dem la cach cham sai cho bai nay.
        want = [pe for pe in per_event if pe["expect_fire"]]
        missed = [pe["label"] for pe in want if not pe["fired"]]
        gapped = [f"{pe['label']}({max(g['seconds'] for g in pe['silent_gaps']):.0f}s)"
                  for pe in want if pe.get("silent_gaps")]
        # "Tach rieng" = moi su co co nhan phai co alert cua RIENG no, khong duoc dung chung
        # mot alert. `score_events` da kep cua so theo tung su kien nen alert khong the bi
        # dem hai lan; con lai chi can moi su kien co alert khop cua chinh no.
        stacked = [pe for pe in want if pe["service"]]
        services = {pe["service"] for pe in stacked}
        not_separated = len(services) > 1 and any(not pe["fired"] for pe in stacked)

        if missed:
            return False, f"bo lo su co: {missed}"
        if gapped:
            return False, f"co KHOANG CAM giua su co: {gapped}"
        if not_separated:
            return False, "su co chong khong duoc tach rieng"
        return True, ("bao lien tuc suot su co, khong khoang cam"
                      + (f", {len(services)} service duoc tach rieng" if len(services) > 1 else ""))
    return None, "unknown scenario type, no verdict rule"


def check_remediation(audit_log_path, window_start, window_end):
    """MANDATE-22: pull the remediation audit trail for the same window —
    used to show detect->safety->act->verify(->rollback/escalate)."""
    records = [r for r in _load_jsonl(audit_log_path) if window_start <= r.get("ts", -1) <= window_end]
    return records


def run_rca(args, window_start, window_end):
    """MANDATE-26: name ONE suspected root service for this window, with the evidence.

    Deliberately a thin wrapper: all the reasoning lives in diagnose.py so it can be read
    and unit-tested on its own. Topology comes from spanmetrics when a Prometheus URL is
    given and falls back to aiops/topology.json otherwise — never silently, the source is
    always reported alongside the verdict.
    """
    alerts = _load_jsonl(args.alerter_history)
    graph, source, note = diagnose.resolve_topology(
        prom_url=getattr(args, "prom_url", None),
        static_path=getattr(args, "topology", diagnose.DEFAULT_TOPOLOGY),
    )
    ratios = {}
    if getattr(args, "prom_url", None):
        # Sample at the end of the window: rate(...[5m]) there still covers the incident.
        ratios = diagnose.error_ratios_at(args.prom_url, window_end)
    return diagnose.diagnose(
        alerts, window_start, window_end,
        graph=graph, topology_source=source, topology_note=note, error_ratios=ratios,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _print_report(scenario, score, remediation_records=None, rca=None):
    print("\n" + "=" * 70)
    print(f"SCENARIO: {scenario.get('id')} [{scenario.get('type')}]")
    print(scenario.get("description", ""))
    print("-" * 70)
    for pe in score["per_event"]:
        status = "FIRED" if pe["fired"] else "silent"
        lead = f"{pe['lead_time_seconds']:.1f}s" if pe["lead_time_seconds"] is not None else "n/a"
        print(f"  [{pe['label']}] expect_fire={pe['expect_fire']} -> {status} "
              f"(lead_time={lead}) {'OK' if pe['correct'] else 'MISMATCH'}")
        for g in pe.get("silent_gaps", []):
            print(f"      KHOANG CAM {g['seconds']:.0f}s ({g['where']})")
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
            line = (
                f"    remediation_id={r.get('remediation_id', 'legacy')} "
                f"stage={r.get('stage')} decision={r.get('decision')} "
                f"service={r.get('service')} pod={r.get('pod')}"
            )
            if r.get("stage") == "rollback":
                line += f" rollback_performed={r.get('rollback_performed')}"
            print(line)
    print("=" * 70 + "\n")
    if rca is not None:
        print(diagnose.format_report(rca))


def _write_result(scenario_path, scenario, events, score, remediation_records, rca=None):
    ok, reason = verdict_for_type(scenario.get("type"), score["per_event"])
    result = {
        "scenario_id": scenario.get("id"),
        "type": scenario.get("type"),
        "events": events,
        "score": score,
        "verdict": {"pass": ok, "reason": reason},
        "remediation_records": remediation_records,
        "rca": rca,
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
    rca = run_rca(args, score["window"]["start"], score["window"]["end"]) if args.rca else None
    _print_report(scenario, score, remediation_records, rca)
    _write_result(args.scenario, scenario, events, score, remediation_records, rca)


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
    rca = run_rca(args, score["window"]["start"], score["window"]["end"]) if args.rca else None
    _print_report(scenario, score, remediation_records, rca)
    _write_result(args.scenario, scenario, events, score, remediation_records, rca)


def cmd_rca(args):
    """Standalone RCA — no scenario file needed.

    MANDATE-26 is graded by the mentor feeding a case and verifying on the spot, and the
    case may be one they injected themselves without ever writing a scenario JSON. So RCA
    has to answer from a bare window: "these services went red, which one is the root".
    """
    if args.start is None or args.end is None:
        print("rca requires --start/--end (the window the incident was observed in)",
              file=sys.stderr)
        sys.exit(2)
    result = run_rca(args, args.start, args.end)
    print(diagnose.format_report(result))
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, default=str)
        print(f"  rca written to {args.out}")


def cmd_timeline(args):
    """MANDATE-28: in dong canh bao theo thoi gian + danh sach incident cho mot cua so.

    Khong can scenario file — mentor bom kich ban cua ho roi dua cua so vao la doc duoc,
    dung nhu cau "xuat duoc ... de doi chieu" cua mandate.
    """
    if args.start is None or args.end is None:
        print("timeline requires --start/--end (the window you want to inspect)",
              file=sys.stderr)
        sys.exit(2)
    alerts = _load_jsonl(args.alerter_history)
    print(timeline.format_timeline(
        alerts, args.start, args.end,
        split_gap_seconds=args.max_gap, max_gap_seconds=args.max_gap,
    ))
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump({
                "window": {"start": args.start, "end": args.end},
                "max_gap_seconds": args.max_gap,
                "incidents": timeline.build_incidents(alerts, args.max_gap, args.start, args.end),
            }, f, indent=2, default=str)
        print(f"  timeline written to {args.out}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    # Shared by every subcommand, including the scenario-less `rca`.
    rca_opts = argparse.ArgumentParser(add_help=False)
    rca_opts.add_argument("--alerter-history", default=DEFAULT_ALERTER_HISTORY)
    rca_opts.add_argument("--prom-url", default=os.environ.get("PROM_URL"),
                          help="Prometheus base URL; without it RCA falls back to aiops/topology.json")
    rca_opts.add_argument("--topology", default=diagnose.DEFAULT_TOPOLOGY,
                          help="static dependency graph used when spanmetrics yields no edges")

    common = argparse.ArgumentParser(add_help=False, parents=[rca_opts])
    common.add_argument("scenario", help="path to a scenario JSON file (aiops/incident_scenarios/*.json)")
    common.add_argument("--audit-log", default=DEFAULT_AUDIT_LOG)
    common.add_argument("--check-remediation", action="store_true",
                        help="also pull aiops/remediation/audit_log.jsonl for this window (MANDATE-22)")
    common.add_argument("--rca", action="store_true",
                        help="also run root-cause analysis on the scored window (MANDATE-26)")

    p_run = sub.add_parser("run", parents=[common], help="inject the scenario live, then score it")
    p_run.set_defaults(func=cmd_run)

    p_score = sub.add_parser("score", parents=[common],
                             help="score only, against an externally-observed window (grading day / BTC-injected)")
    p_score.add_argument("--start", type=float, default=None, help="unix ts the injected scenario started")
    p_score.add_argument("--end", type=float, default=None, help="unix ts the injected scenario ended")
    p_score.set_defaults(func=cmd_score)

    p_rca = sub.add_parser("rca", parents=[rca_opts],
                           help="root-cause analysis on a window — names ONE suspected root (MANDATE-26)")
    p_rca.add_argument("--start", type=float, default=None, help="unix ts the incident window starts")
    p_rca.add_argument("--end", type=float, default=None, help="unix ts the incident window ends")
    p_rca.add_argument("--out", default=None, help="also write the RCA verdict to this JSON path")
    p_rca.set_defaults(func=cmd_rca)
    p_tl = sub.add_parser("timeline",
                          help="alert stream over time + incident list for a window (MANDATE-28)")
    p_tl.add_argument("--alerter-history", default=DEFAULT_ALERTER_HISTORY)
    p_tl.add_argument("--start", type=float, default=None, help="unix ts the window starts")
    p_tl.add_argument("--end", type=float, default=None, help="unix ts the window ends")
    p_tl.add_argument("--max-gap", type=float, default=timeline.DEFAULT_MAX_GAP_SECONDS,
                      help="gap above which alerting counts as SILENT "
                           "(default 630s = alerter cooldown 600s + one 30s poll)")
    p_tl.add_argument("--out", default=None, help="also write the incident list to this JSON path")
    p_tl.set_defaults(func=cmd_timeline)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
