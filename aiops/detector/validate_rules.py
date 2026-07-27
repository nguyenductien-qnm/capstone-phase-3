#!/usr/bin/env python3
"""
validate_rules.py  :  Kiem tra rules.yaml TRUOC khi no ra cum.

Vi sao co file nay
------------------
Truoc do rules.yaml KHONG duoc kiem tra o bat cu dau: khong schema, khong parse
PromQL, va khong mot test nao load no (`load_config` trong detector.py chua tung
duoc test cham toi). Hau qua do duoc tren EKS ngay 26/07:

  rule `kafka-consumer-lag-high` query `kafka_consumer_group_lag` — mot ten metric
  KHONG ton tai. PromQL sai ten TRA VE CHUOI RONG chu khong nem loi, va
  `eval_metric_rule` nuot im lang chuoi rong. Rule nam do CAM HANG TUAN trong khi
  ai cung tuong no dang canh queue lag.

  Xem: report/mandate15-eks/report.md §4.4

Script nay chan duoc phan chan duoc, va noi thang phan no KHONG chan duoc.

Bat duoc gi
-----------
  - Cu phap PromQL sai (qua `promtool check rules`).
  - Truong bat buoc thieu, sai kieu, hoac `id` trung nhau.
  - `op` khong phai gt/lt. Quan trong hon ve nhin: `eval_metric_rule` so sanh bang
    `value > threshold if op == "gt" else value < threshold`, nghia la MOI gia tri
    go sai ("GT", ">", "greater") deu am tham chay thanh `lt` — rule bi DAO CHIEU
    ma khong co mot dau hieu nao.
  - TRUONG LA (khong nam trong schema). Day la lop loi nguy hiem nhat ma script
    bat duoc: go `dynamic_min_fration` thieu chu 'c' thi `rule.get(...)` tra None,
    cong SLO im lang khong bao gio ap, rule chay tiep nhu chua he co ai cau hinh gi.

Loi va canh bao
---------------
Phan biet hai truong hop rat khac nhau, dung gop lam mot:

  LOI     — ten khong thuoc tu vung cua BAT KY type nao. Gan nhu chac chan go sai,
            va hau qua la im lang. CI do.
  CANH BAO — ten hop le o type KHAC (vd `match_phrases` tren rule k8s_status). Co the
            la co y: `oom-detected` giu lai match_phrases lam tai lieu sau khi doi tu
            log-based sang k8s_status, va da ghi ro ly do trong comment. Cung co the la
            dat nham type. In ra de nguoi doc tu quyet; --strict thi coi la loi.

KHONG bat duoc gi
-----------------
  Ten metric/label sai. `kafka_consumer_group_lag` la PromQL HOP LE HOAN TOAN —
  no chi tinh co khong khop chuoi nao tren cum nay. Muon bat phai hoi Prometheus
  that, ma CI thi khong co cum. Hai lop con lai lo viec do:

    1. `python detector.py --once --dry-run` tren Prometheus port-forward — cong
       thu cong bat buoc truoc khi merge (checklist PR).
    2. Co che detector tu to cao rule cam khi chay lien tuc.

  Dung tuong script nay xanh la rule song. No chi bao dam rule DUNG CU PHAP.

Dung
----
  python validate_rules.py                     # kiem rules.yaml canh file nay
  python validate_rules.py --file khac.yaml
  python validate_rules.py --allow-missing-promtool   # bo qua check PromQL

Ma thoat: 0 = sach, 1 = co loi, 2 = khong chay duoc (thieu file/promtool).
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile

import yaml

_HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_RULES = os.path.join(_HERE, "rules.yaml")

VALID_TYPES = ("metric", "log", "k8s_status")
VALID_OPS = ("gt", "lt")
VALID_SEVERITIES = ("critical", "warning", "info")

NUMBER = (int, float)

# Truong dung chung cho moi rule, bat ke type.
COMMON_REQUIRED = {
    "id": str,
    "type": str,
    "severity": str,
    "summary": str,
}

# Truong theo tung type. Nguon su that la chinh detector.py — moi khoa o day phai
# ung voi mot `rule.get(...)` / `rule[...]` co that trong code:
#   metric     -> eval_metric_rule       (detector.py:53)
#   log        -> eval_log_rule          (detector.py:161)
#   k8s_status -> eval_k8s_status_rule   (detector.py:180)
#
# THEM TRUONG SCHEMA MOI VAO DETECTOR THI PHAI THEM VAO DAY CUNG COMMIT. Do la co y:
# truong la bi bao loi, nen quen khai bao se lam CI do ngay chu khong am tham bo qua.
TYPE_FIELDS = {
    "metric": {
        "required": {"query": str, "threshold": NUMBER},
        "optional": {
            "op": str,
            "summary_dynamic": str,
            "dynamic_min_fraction": NUMBER,
        },
    },
    "log": {
        # match_phrases HOAC match_phrase — xu ly rieng ben duoi vi la quan he "hoac".
        "required": {},
        "optional": {
            "match_phrases": (list, str),
            "match_phrase": (list, str),
            "window_minutes": NUMBER,
            "min_count": NUMBER,
        },
    },
    "k8s_status": {
        "required": {},
        "optional": {
            "k8s_namespace": str,
            "service_label_key": str,
            "lookback_seconds": NUMBER,
        },
    },
}


def _type_name(expected):
    if isinstance(expected, tuple):
        return " hoac ".join(t.__name__ for t in expected)
    return expected.__name__


def _check_field_types(rule, spec, where, errors):
    for key, expected in spec.items():
        if key not in rule:
            continue
        if not isinstance(rule[key], expected):
            errors.append(
                f"{where}: truong '{key}' phai la {_type_name(expected)}, "
                f"dang la {type(rule[key]).__name__}"
            )


def validate_rule(rule, index, seen_ids, errors, warnings):
    """Kiem mot rule. Ghi vao `errors`/`warnings`. Tra ve query PromQL neu co."""
    where = f"rules[{index}]"

    if not isinstance(rule, dict):
        errors.append(f"{where}: phai la mot mapping, dang la {type(rule).__name__}")
        return None

    rule_id = rule.get("id")
    if isinstance(rule_id, str) and rule_id:
        where = f"rule '{rule_id}'"
        if rule_id in seen_ids:
            # id trung khong chi la chuyen thu tu: `history_key` va `dedup_key` deu la
            # f"{rule['id']}:{svc}", nen hai rule trung id se DUNG CHUNG baseline 3-sigma
            # va dung chung cooldown 600s — cai sau nuot bao dong cua cai truoc.
            errors.append(f"{where}: id bi trung (da xuat hien o rule truoc do)")
        seen_ids.add(rule_id)

    for key, expected in COMMON_REQUIRED.items():
        if key not in rule:
            errors.append(f"{where}: thieu truong bat buoc '{key}'")
    _check_field_types(rule, COMMON_REQUIRED, where, errors)

    rule_type = rule.get("type")
    if rule_type is not None and rule_type not in VALID_TYPES:
        # run_cycle chi log warning roi `continue` — rule bi bo qua HOAN TOAN va im lang.
        errors.append(
            f"{where}: type '{rule_type}' khong hop le "
            f"(chi nhan {', '.join(VALID_TYPES)}) — run_cycle se bo qua rule nay"
        )
        return None

    severity = rule.get("severity")
    if severity is not None and severity not in VALID_SEVERITIES:
        errors.append(
            f"{where}: severity '{severity}' khong hop le "
            f"(chi nhan {', '.join(VALID_SEVERITIES)})"
        )

    summary = rule.get("summary")
    if isinstance(summary, str) and not summary.strip():
        errors.append(f"{where}: summary rong — alert se khong noi len duoc chuyen gi")

    if rule_type is None:
        return None

    spec = TYPE_FIELDS[rule_type]
    for key in spec["required"]:
        if key not in rule:
            errors.append(f"{where}: type={rule_type} nhung thieu truong bat buoc '{key}'")
    _check_field_types(rule, spec["required"], where, errors)
    _check_field_types(rule, spec["optional"], where, errors)

    known = set(COMMON_REQUIRED) | set(spec["required"]) | set(spec["optional"])
    # Tu vung cua MOI type gop lai — dung de phan biet "go sai" voi "dat nham type".
    all_known = set(COMMON_REQUIRED)
    for other in TYPE_FIELDS.values():
        all_known |= set(other["required"]) | set(other["optional"])

    for key in rule:
        if key in known:
            continue
        if key in all_known:
            # Ten co that, chi la khong thuoc type nay. Co the co y (xem `oom-detected`:
            # giu match_phrases lam tai lieu sau khi doi sang k8s_status, co ghi ly do),
            # cung co the la dat nham type. Khong tu quyet ho — bao de nguoi doc quyet.
            owners = sorted(
                t for t, s in TYPE_FIELDS.items()
                if key in s["required"] or key in s["optional"]
            )
            warnings.append(
                f"{where}: truong '{key}' hop le voi type={'/'.join(owners)} nhung "
                f"rule nay type={rule_type} — detector KHONG doc no. Co y thi bo qua, "
                f"nham type thi sua"
            )
        else:
            errors.append(
                f"{where}: truong la '{key}' — khong thuoc tu vung cua bat ky type nao, "
                f"detector KHONG doc truong nay. Go sai ten thi cau hinh im lang khong co "
                f"tac dung. Truong hop le cho type={rule_type}: {', '.join(sorted(known))}"
            )

    if rule_type == "metric":
        op = rule.get("op", "gt")
        if op not in VALID_OPS:
            errors.append(
                f"{where}: op '{op}' khong hop le (chi nhan gt/lt). "
                f"detector so sanh bang `value > threshold if op == 'gt' else value < threshold` "
                f"— moi gia tri khac 'gt' deu chay thanh 'lt', tuc DAO CHIEU rule"
            )
        frac = rule.get("dynamic_min_fraction")
        if isinstance(frac, NUMBER) and not isinstance(frac, bool):
            if frac <= 0:
                errors.append(
                    f"{where}: dynamic_min_fraction={frac} phai > 0 "
                    f"(no la ti le cua threshold; <= 0 thi cong luon mo, vo nghia)"
                )
            elif frac > 1:
                errors.append(
                    f"{where}: dynamic_min_fraction={frac} > 1 nghia la tang dong chi keu "
                    f"KHI DA VUOT nguong tinh — luc do tang tinh da keu roi, tang dong thanh thua"
                )
        if op == "lt" and rule.get("dynamic_min_fraction") is not None:
            # Khong phai loi cu phap, nhung la cau hinh khong co tac dung — dung lop loi
            # ma script nay sinh ra de chan.
            errors.append(
                f"{where}: op=lt kem dynamic_min_fraction — cong SLO CHI ap cho nhanh gt "
                f"(detector.py:109-115), dat o day khong co tac dung nao"
            )

    if rule_type == "log":
        if not (rule.get("match_phrases") or rule.get("match_phrase")):
            errors.append(
                f"{where}: type=log phai co 'match_phrases' hoac 'match_phrase'"
            )

    for key in ("window_minutes", "min_count", "lookback_seconds", "threshold"):
        val = rule.get(key)
        if isinstance(val, NUMBER) and not isinstance(val, bool) and val < 0:
            errors.append(f"{where}: '{key}'={val} am — gan nhu chac chan la nham")

    if rule_type == "metric":
        query = rule.get("query")
        if isinstance(query, str) and query.strip():
            return query
    return None


def validate_config(cfg, errors, warnings):
    """Kiem cau truc top-level. Tra ve list (rule_id, query) de check PromQL."""
    if not isinstance(cfg, dict):
        errors.append(f"file phai parse ra mot mapping, dang la {type(cfg).__name__}")
        return []

    poll = cfg.get("poll_interval_seconds")
    if poll is None:
        errors.append("thieu 'poll_interval_seconds' o top-level")
    elif not isinstance(poll, NUMBER) or isinstance(poll, bool) or poll <= 0:
        errors.append(f"'poll_interval_seconds'={poll!r} phai la so duong")

    for key in ("sources", "alert"):
        if key not in cfg:
            errors.append(f"thieu khoi '{key}' o top-level")
        elif not isinstance(cfg[key], dict):
            errors.append(f"'{key}' phai la mapping, dang la {type(cfg[key]).__name__}")

    rules = cfg.get("rules")
    if rules is None:
        errors.append("thieu 'rules' o top-level")
        return []
    if not isinstance(rules, list):
        errors.append(f"'rules' phai la list, dang la {type(rules).__name__}")
        return []
    if not rules:
        errors.append("'rules' rong — detector se chay ma khong canh gi ca")
        return []

    seen_ids = set()
    queries = []
    for i, rule in enumerate(rules):
        query = validate_rule(rule, i, seen_ids, errors, warnings)
        if query is not None:
            queries.append((rule.get("id", f"rules[{i}]"), query))
    return queries


def check_promql(queries, errors):
    """Parse cu phap tung query bang `promtool check rules`.

    Goi promtool MOT LAN CHO MOI QUERY chu khong gop het vao mot file: gop lai thi
    promtool bao loi kem so dong cua file tam, khong lan ra duoc rule nao sai.
    Voi ~11 metric rule thi chi phi khong dang ke.
    """
    promtool = shutil.which("promtool")
    if not promtool:
        return False

    for rule_id, query in queries:
        # Ten recording rule phai khop [a-zA-Z_:][a-zA-Z0-9_:]* — dau hai cham hop le.
        doc = {
            "groups": [
                {
                    "name": "aiops-syntax-check",
                    "rules": [{"record": "aiops:syntax:check", "expr": query}],
                }
            ]
        }
        with tempfile.NamedTemporaryFile(
            "w", suffix=".yaml", delete=False, encoding="utf-8"
        ) as fh:
            yaml.safe_dump(doc, fh, allow_unicode=True)
            path = fh.name
        try:
            proc = subprocess.run(
                [promtool, "check", "rules", path],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if proc.returncode != 0:
                detail = (proc.stdout + proc.stderr).strip()
                errors.append(f"rule '{rule_id}': PromQL sai cu phap\n    {detail}")
        finally:
            os.unlink(path)
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1].strip())
    ap.add_argument("--file", default=DEFAULT_RULES, help="duong dan rules.yaml")
    ap.add_argument(
        "--allow-missing-promtool",
        action="store_true",
        help=(
            "khong co promtool thi bo qua check PromQL thay vi bao loi. "
            "CI KHONG duoc dung co nay — CI bo qua im lang dung la lop loi dang di sua"
        ),
    )
    ap.add_argument(
        "--strict",
        action="store_true",
        help="coi canh bao la loi (truong hop le o type khac cung lam CI do)",
    )
    args = ap.parse_args()

    if not os.path.exists(args.file):
        print(f"KHONG THAY FILE: {args.file}", file=sys.stderr)
        return 2

    try:
        with open(args.file, encoding="utf-8") as fh:
            cfg = yaml.safe_load(fh)
    except yaml.YAMLError as exc:
        print(f"YAML khong parse duoc: {exc}", file=sys.stderr)
        return 1

    errors = []
    warnings = []
    queries = validate_config(cfg, errors, warnings)
    if args.strict:
        errors.extend(warnings)
        warnings = []

    promql_checked = check_promql(queries, errors)
    if not promql_checked:
        msg = (
            "khong tim thay `promtool` tren PATH — KHONG kiem duoc cu phap PromQL. "
            "Cai qua goi prometheus, hoac chay lai voi --allow-missing-promtool."
        )
        if args.allow_missing_promtool:
            print(f"CANH BAO: {msg}", file=sys.stderr)
        else:
            print(f"LOI: {msg}", file=sys.stderr)
            return 2

    n_rules = len(cfg.get("rules") or []) if isinstance(cfg, dict) else 0
    name = os.path.basename(args.file)

    if warnings:
        print(f"{name}: {len(warnings)} canh bao\n", file=sys.stderr)
        for warn in warnings:
            print(f"  ! {warn}", file=sys.stderr)
        print(file=sys.stderr)

    if errors:
        print(f"{name}: {len(errors)} loi\n", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        print(file=sys.stderr)
        return 1

    checked = f", {len(queries)} query PromQL" if promql_checked else ""
    warned = f", {len(warnings)} canh bao" if warnings else ""
    print(f"{name}: OK — {n_rules} rule{checked}{warned}")
    if not promql_checked:
        print("  (bo qua check PromQL: khong co promtool)")
    print(
        "  Luu y: script nay KHONG kiem duoc ten metric co ton tai tren cum hay khong.\n"
        "  Chay `python detector.py --once --dry-run` tren Prometheus that de biet."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
