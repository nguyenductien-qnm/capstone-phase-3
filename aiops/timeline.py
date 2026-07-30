#!/usr/bin/env python3
"""
timeline.py  :  dong canh bao theo thoi gian + danh sach incident (MANDATE-28).

MANDATE-28 doi tuong minh mot artifact de mentor doi chieu:
    "Xuat duoc dong canh bao theo thoi gian + danh sach incident de doi chieu."

File nay lam dung hai thu do, va dung chung cho ca lenh `timeline` lan verdict cua kich ban
`sustained` trong incident_replay.py — MOT cach tinh, khong hai. Neu bao cao cho mentor va
verdict tu cham dung hai cong thuc khac nhau thi ca hai deu khong dang tin.

CHI STDLIB, cung ly do voi incident_replay.py: mentor tu chay tren may ho, khong cai gi them.
"""

# `alerter.py` gom alert theo cooldown 600s cho tung `rule x service`. Nghia la ngay ca mot
# rule keu MOI chu ky (poll 30s) thi trong `alerter_history.jsonl` van chi thay mot ban ghi
# moi 10 phut. Do la chong spam CO CHU DICH (ADR-012), khong phai detector bi mu.
#
# Nen nguong "khoang cam" phai la cooldown + mot chu ky poll = 630s. Duoi nguong do la nhip
# binh thuong; VUOT nguong do moi la im lang that. Dat 600 tron se bao dong gia moi lan
# scrape lech vai giay; dat qua cao se nuot mat dung cai mandate di tim.
DEFAULT_MAX_GAP_SECONDS = 630

# Nguong tach hai incident. Dung chung con so voi tren CO Y: neu mot khoang trong du lon de
# bi goi la "khoang cam" thi no cung du lon de doc nhu hai lan bung phat rieng. Mot nguong,
# hai cach doc — va bao cao noi ro ca hai (xem format_timeline).
DEFAULT_SPLIT_GAP_SECONDS = DEFAULT_MAX_GAP_SECONDS

# Alert detector tu bao ve chinh no, khong phai quan sat ve he thong duoc do.
# Giu dong bo voi incident_replay._SELF_REPORT_RULE_IDS.
_SELF_REPORT_RULE_IDS = {"detector-silent-rule", "baseline-rebaselined"}


def _clean(alerts, window_start=None, window_end=None, include_self_report=False):
    out = []
    for a in alerts:
        ts = a.get("ts")
        if ts is None:
            continue
        if window_start is not None and ts < window_start:
            continue
        if window_end is not None and ts > window_end:
            continue
        if not include_self_report and a.get("rule_id") in _SELF_REPORT_RULE_IDS:
            continue
        out.append(a)
    return sorted(out, key=lambda a: a["ts"])


def build_incidents(alerts, split_gap_seconds=DEFAULT_SPLIT_GAP_SECONDS,
                    window_start=None, window_end=None):
    """Gom alert lien tiep cung (rule_id, service) thanh incident.

    Mot incident dut khi khoang cach giua hai alert lien tiep vuot `split_gap_seconds`.

    Tra ve list dict da sap theo thoi gian bat dau:
      {rule_id, service, start, end, duration_seconds, n_alerts, max_gap_seconds, gaps}
    `gaps` la moi khoang cach giua cac alert trong incident — de nguoi doc tu thay nhip.
    """
    by_key = {}
    for a in _clean(alerts, window_start, window_end):
        by_key.setdefault((a.get("rule_id"), a.get("service")), []).append(a["ts"])

    incidents = []
    for (rule_id, service), stamps in by_key.items():
        run = [stamps[0]]
        for ts in stamps[1:]:
            if ts - run[-1] > split_gap_seconds:
                incidents.append(_incident(rule_id, service, run))
                run = [ts]
            else:
                run.append(ts)
        incidents.append(_incident(rule_id, service, run))
    return sorted(incidents, key=lambda i: (i["start"], i["service"] or "", i["rule_id"] or ""))


def _incident(rule_id, service, stamps):
    gaps = [round(b - a, 1) for a, b in zip(stamps, stamps[1:])]
    return {
        "rule_id": rule_id,
        "service": service,
        "start": stamps[0],
        "end": stamps[-1],
        "duration_seconds": round(stamps[-1] - stamps[0], 1),
        "n_alerts": len(stamps),
        "max_gap_seconds": max(gaps) if gaps else 0.0,
        "gaps": gaps,
    }


def silent_gaps(alerts, rule_ids, service, t_start, t_end,
                max_gap_seconds=DEFAULT_MAX_GAP_SECONDS):
    """Khoang cam cua mot su co trong CUA SO DA BIET [t_start, t_end].

    `rule_ids`: tap rule duoc coi la "phu" su co nay. Alert tu BAT KY rule nao trong tap
    deu tinh la con dang bao — vi voi nguoi truc, duoc bao la duoc bao, khong quan trong
    rule nao noi.

    Khac `build_incidents`: ham nay dung cho cham diem, nen no lay cua so tu NHAN cua kich
    ban chu khong tu suy ra tu chinh cac alert. Suy tu alert thi mot su co bi bo lo hoan
    toan se cho ra "0 khoang cam" — dung ky thuat ma vo nghia.

    Tinh ca hai dau: tu t_start toi alert dau tien, va tu alert cuoi toi t_end.
    """
    wanted = {rule_ids} if isinstance(rule_ids, str) else set(rule_ids or ())
    stamps = [a["ts"] for a in _clean(alerts, t_start, t_end)
              if a.get("rule_id") in wanted and (service is None or a.get("service") == service)]
    if not stamps:
        return [{"from": t_start, "to": t_end, "seconds": round(t_end - t_start, 1),
                 "where": "toan bo cua so — KHONG co alert nao"}]

    gaps = []
    edges = [t_start] + stamps + [t_end]
    for a, b in zip(edges, edges[1:]):
        if b - a > max_gap_seconds:
            if a == t_start:
                where = "dau cua so toi alert dau tien"
            elif b == t_end:
                where = "alert cuoi toi cuoi cua so"
            else:
                where = "giua hai alert"
            gaps.append({"from": a, "to": b, "seconds": round(b - a, 1), "where": where})
    return gaps


def services_alerting(alerts, t_start, t_end):
    """Tap service co alert trong cua so. Dung de bat bao gia ngoai kich ban."""
    return sorted({a.get("service") for a in _clean(alerts, t_start, t_end) if a.get("service")})


def format_timeline(alerts, window_start=None, window_end=None,
                    split_gap_seconds=DEFAULT_SPLIT_GAP_SECONDS,
                    max_gap_seconds=DEFAULT_MAX_GAP_SECONDS):
    """Ban in cho nguoi doc: dong canh bao theo thoi gian + danh sach incident."""
    import datetime

    def hhmmss(ts):
        return datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime("%H:%M:%S")

    rows = _clean(alerts, window_start, window_end, include_self_report=True)
    incidents = build_incidents(alerts, split_gap_seconds, window_start, window_end)

    out = ["", "=" * 74, "DONG CANH BAO THEO THOI GIAN (MANDATE-28)", "-" * 74]
    if not rows:
        out += ["  (khong co alert nao trong cua so)", "=" * 74, ""]
        return "\n".join(out)

    t0 = rows[0]["ts"]
    # Khoang cach phai tinh THEO TUNG `rule x service`, khong phai so voi dong ngay truoc.
    # So voi dong truoc thi mot alert cua service KHAC se che mat khoang cam cua service dang
    # xet — dung cai bug MANDATE-28 di tim, chi la o ban in thay vi o detector.
    prev_by_key = {}
    for a in rows:
        key = (a.get("rule_id"), a.get("service"))
        prev = prev_by_key.get(key)
        gap = "" if prev is None else f"  (+{a['ts'] - prev:.0f}s)"
        flag = "  <== KHOANG CAM" if prev is not None and a["ts"] - prev > max_gap_seconds else ""
        out.append(f"  {hhmmss(a['ts'])}  T+{a['ts'] - t0:6.0f}s  "
                   f"{(a.get('severity') or '?'):8s} {(a.get('rule_id') or '?'):28s} "
                   f"{(a.get('service') or '?')}{gap}{flag}")
        prev_by_key[key] = a["ts"]

    out += ["-" * 74, f"DANH SACH INCIDENT ({len(incidents)}) — tach khi cach nhau > {split_gap_seconds:.0f}s", "-" * 74]
    dem = {}
    for i in incidents:
        dem[(i["rule_id"], i["service"])] = dem.get((i["rule_id"], i["service"]), 0) + 1
    for i in incidents:
        key = (i["rule_id"], i["service"])
        if i["max_gap_seconds"] > max_gap_seconds:
            cam = f"  <== co khoang cam {i['max_gap_seconds']:.0f}s BEN TRONG"
        elif dem[key] > 1:
            cam = f"  <== {dem[key]} lan bung phat roi rac — co khoang cam GIUA chung"
        else:
            cam = ""
        out.append(f"  {hhmmss(i['start'])} -> {hhmmss(i['end'])}  "
                   f"({i['duration_seconds']:6.0f}s, {i['n_alerts']:3d} alert)  "
                   f"{(i['rule_id'] or '?'):28s} {i['service'] or '?'}{cam}")
    out += ["", f"  nguong khoang cam: {max_gap_seconds:.0f}s "
                f"(= cooldown 600s cua alerter + 1 chu ky poll 30s)", "=" * 74, ""]
    return "\n".join(out)
