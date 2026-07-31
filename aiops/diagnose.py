#!/usr/bin/env python3
"""
diagnose.py  :  Diagnose stage — RCA chi dung goc (MANDATE-26).

Pipeline: Detect -> Correlate -> **Diagnose** -> Act.
`detector.py` la Detect, `correlate.py` la Correlate, file nay la Diagnose.

Bai toan
--------
Khi mot su co lan cheo nhieu service, nhieu service cung do mot luc. San cua MANDATE-26 la
chi ra MOT service nghi la goc KEM LY LE, chu khong phai liet ke danh sach service dang do
va cung khong duoc dung o trieu chung downstream.

Ba nguon bang chung (khop dung chu "trace / topology / tin hieu" cua mandate)
----------------------------------------------------------------------------
1. THU TU THOI GIAN  — tu `alerter_history.jsonl`: service nao keu TRUOC. Day la co che
   chinh de phan biet nhan qua voi trung hop ("cai do truoc = goc").

2. HUONG PHU THUOC   — do thi A->B ("A goi B"). Neu A va B CUNG do va A->B thi trang thai
   cua B GIAI THICH duoc trang thai cua A, nen B la goc kha di hon A. Diem cua mot ung vien
   = so service do khac phu thuoc BAC CAU vao no: goc that giai thich duoc nhieu trieu chung.

3. DO LON LOI        — ti le loi trong cua so, lam bang chung bo tro (khong phai tin hieu
   quyet dinh: mot service downstream co the do nang hon chinh cai goc).

Vi sao CHI STDLIB
-----------------
File nay duoc `incident_replay.py` goi, ma harness do co y chi phu thuoc stdlib — "phai chay
duoc tren may cua giam khao ma khong can cai them gi" (xem `known_rule_ids`). MANDATE-26 cham
bang cach mentor tu dua ca kiem vao chay tai cho, nen tinh chat do la mot phan cua yeu cau,
khong phai so thich. Goi Prometheus bang urllib, khong requests; khong numpy/scipy.

Chay
----
  python aiops/incident_replay.py rca --start <unix_ts> --end <unix_ts>
  python aiops/incident_replay.py score <scenario.json> --start .. --end .. --rca
"""

import json
import os
import urllib.parse
import urllib.request
from collections import defaultdict

_HERE = os.path.dirname(os.path.abspath(__file__))

DEFAULT_TOPOLOGY = os.path.join(_HERE, "topology.json")

# Alert do detector tu bao ve CHINH NO, khong phai quan sat ve he thong duoc do.
# Giu dong bo voi `incident_replay._SELF_REPORT_RULE_IDS` — mot bao cao rule-mu roi trung
# cua so khong noi len dieu gi ve service nao la goc.
_SELF_REPORT_RULE_IDS = {"detector-silent-rule"}

# CACH CHAM: do thi quyet dinh, thoi gian pha hoa. KHONG phai tong co trong so.
#
# Diem cua mot ung vien = ti le service do khac phu thuoc bac cau vao no. Hai ung vien bang
# diem thi CAI DO TRUOC thang. Het.
#
# Da tung viet dang `W_GRAPH*g + W_TIME*t + W_MAGNITUDE*m` va bo dan tung so hang, moi lan
# deu vi kiem CHIEU FAIL cho thay so hang do KHONG DOI DUOC KET QUA nao. Ghi lai ca ba de
# khong ai them lai:
#
#   W_MAGNITUDE (do lon loi) — bo vi hai le. Mot, dat ve 0 khong test nao doi. Hai, no keo
#     SAI HUONG: mandate cam "dung o trieu chung downstream", ma downstream lai chinh la cho
#     co volume loi lon nhat (cart chet -> checkout loi 100%, cart chi loi o phan request
#     cham toi no). Van DOC va BAO CAO ti le loi trong phan giai thich — no la boi canh co
#     ich cho nguoi truc — chi khong duoc tham gia quyet dinh.
#
#   W_TIME (thu tu thoi gian) — bo vi tiebreak `(-score, t_first)` DA lam dung viec do roi.
#     Dat W_TIME=0 van 15/15 xanh. Giu no lai chi de "trong co ve co nhieu tin hieu".
#
#   UNLINKED_PENALTY — bo vi he so phat 0.2 dat lai thanh 1.0 van xanh het; doi sang LOAI HAN
#     khoi danh sach nghi pham thi co che moi that su ganh viec.
#
# Bai hoc chung: mot tham so khong doi duoc ket qua nao la mot nut giat cho co. No lam mo
# hinh trong phuc tap hon nang luc that cua no.

# Service do nhung khong noi duoc voi phan con lai cua nhom do -> KHONG phai ung vien goc
# cua cascade nay, ma la mot su co RIENG dang chay song song.
#
# Hai lan sua o cho nay, ca hai do kiem CHIEU FAIL bat duoc, ghi lai de khong ai lam lai:
#
# 1. Ban dau cho no o lai bang xep hang voi he so phat 0.2. Dat lai thanh 1.0 (tuc bo han
#    hinh phat) van XANH HET — tang do thi da du manh nen he so do khong bao gio doi duoc
#    ket qua. Mot nut chi giat cho co. Doi sang LOAI HAN: co che moi that su ganh viec, va
#    dung nghia hon — no khong phai "nghi pham yeu", no la su co khac.
#
# 2. Sau do dat nguong `MIN_LINKED_FOR_CASCADE = 2`. Ha xuong 1 van XANH HET, vi `_linked`
#    DOI XUNG: a noi voi b thi b cung noi voi a, nen tap `linked` khong bao gio co dung
#    1 phan tu — no la 0 hoac >= 2. Mot nguong nhan gia tri nao cung nhu nhau la mot nguong
#    gia. Bo han, viet thang dieu kien that: co it nhat mot cap noi duoc voi nhau.


# ---------------------------------------------------------------------------
# Doc alert
# ---------------------------------------------------------------------------
def _load_jsonl(path):
    if not path or not os.path.exists(path):
        return []
    out = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def red_services(alerts, window_start, window_end):
    """Gom alert theo service -> {service: {t_first, n_alerts, rules}}.

    `t_first` la moc quyet dinh cho tang thu-tu-thoi-gian, nen phai la alert SOM NHAT cua
    service do trong cua so, khong phai alert dau tien doc duoc tu file (file khong bao dam
    thu tu).
    """
    by_svc = {}
    for a in alerts:
        ts = a.get("ts")
        if ts is None or not (window_start <= ts <= window_end):
            continue
        if a.get("rule_id") in _SELF_REPORT_RULE_IDS:
            continue
        svc = a.get("service")
        if not svc or svc == "unknown":
            # `oom-detected` hien bao service="unknown" (khiem khuyet da biet, TF1-116).
            # Bo qua o day thay vi tao mot nut ma "unknown" trong do thi nghi pham.
            continue
        cur = by_svc.setdefault(svc, {"t_first": ts, "n_alerts": 0, "rules": set()})
        cur["n_alerts"] += 1
        cur["rules"].add(a.get("rule_id"))
        if ts < cur["t_first"]:
            cur["t_first"] = ts
    for v in by_svc.values():
        v["rules"] = sorted(r for r in v["rules"] if r)
    return by_svc


# ---------------------------------------------------------------------------
# Do thi phu thuoc
# ---------------------------------------------------------------------------
def _prom_query(base_url, promql, timeout=10):
    url = base_url.rstrip("/") + "/api/v1/query?" + urllib.parse.urlencode({"query": promql})
    with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310
        payload = json.loads(resp.read().decode("utf-8"))
    if payload.get("status") != "success":
        raise RuntimeError(f"Prometheus tra status={payload.get('status')}")
    return payload["data"]["result"]


def _ten_span_cu_the(span_name):
    """Ten span co du dinh danh MOT endpoint khong.

    Chi nhan ten co '/' hoac '.':
        gRPC          `oteldemo.CartService/GetCart`      -> co ca hai
        HTTP co route `GET /api/cart`                     -> co '/'
        TRAN          `GET` `POST` `redis` `resolve`      -> khong co gi -> LOAI

    VI SAO CAN RIENG BO LOC NAY, du da co bo loc mo ho ben duoi. Bo loc mo ho chi bo mot
    `span_name` khi no ung voi >1 service SERVER — tuc no phu thuoc vao LUU LUONG tai thoi
    diem query. Do 31/07 tren cum: co luc `GET` chi co `frontend-proxy` lam SERVER (mot
    service -> khong mo ho -> LOT LUOI), luc khac lai co ca `frontend` (hai service -> bi
    bo). Cung mot cai ten, hai ket qua khac nhau tuy gio.

    Hau qua cua lan lot luoi do, do that: 6 service phat span CLIENT ten tran (`cart`,
    `checkout`, `shipping`, `shopping-copilot`, `product-reviews`, `load-generator` — chung
    goi ElastiCache/RDS/Bedrock, nhung dich KHONG duoc trace) deu bi noi mot canh gia ve
    `frontend-proxy`. 5 canh SAI tren tong 16, tat ca do ve MOT nut, khien `frontend-proxy`
    thanh "thu ma ai cung phu thuoc" va RCA cham no lam goc voi confidence 0.8 — trong khi
    goc that la `quote`, con `frontend-proxy` la RIA NGOAI CUNG. Dung thu mandate cam:
    "khong dung o trieu chung downstream".

    Bo loc nay khong phu thuoc luu luong nen khong co ca lot luoi theo gio.
    """
    return "/" in span_name or "." in span_name


def graph_from_spanmetrics(prom_url, timeout=10):
    """Suy canh A->B bang khop `span_name` giua span CLIENT cua A va span SERVER cua B.

    spanmetrics KHONG co nhan `peer.service` (do 27/07, verify.md V2), nen day la cach duy
    nhat suy ra huong goi ma khong phai doi cau hinh collector.

    Bo qua span_name mo ho (mot ten ung voi NHIEU service SERVER — vi du "GET" cua HTTP) va
    dem lai so bi bo. Doan mo ho ma van noi canh thi do thi se sai theo huong khong doan
    truoc duoc, va mot do thi sai con nguy hiem hon khong co do thi.

    Tra ve (graph, stats). graph = {caller: [callee, ...]}.
    """
    client_rows = _prom_query(
        prom_url,
        'count by (service_name, span_name) '
        '(traces_span_metrics_calls_total{span_kind="SPAN_KIND_CLIENT"})',
        timeout,
    )
    server_rows = _prom_query(
        prom_url,
        'count by (service_name, span_name) '
        '(traces_span_metrics_calls_total{span_kind=~"SPAN_KIND_SERVER|SPAN_KIND_CONSUMER"})',
        timeout,
    )

    generic = set()

    servers_by_span = defaultdict(set)
    for row in server_rows:
        m = row.get("metric", {})
        if not (m.get("span_name") and m.get("service_name")):
            continue
        if not _ten_span_cu_the(m["span_name"]):
            generic.add(m["span_name"])
            continue
        servers_by_span[m["span_name"]].add(m["service_name"])

    graph = defaultdict(set)
    ambiguous = set()
    for row in client_rows:
        m = row.get("metric", {})
        caller, span = m.get("service_name"), m.get("span_name")
        if not caller or not span:
            continue
        if not _ten_span_cu_the(span):
            generic.add(span)
            continue
        callees = servers_by_span.get(span)
        if not callees:
            continue
        if len(callees) > 1:
            ambiguous.add(span)
            continue
        callee = next(iter(callees))
        if callee != caller:
            graph[caller].add(callee)

    stats = {
        "client_series": len(client_rows),
        "server_series": len(server_rows),
        "generic_span_names": len(generic),
        "ambiguous_span_names": len(ambiguous),
        "edges": sum(len(v) for v in graph.values()),
    }
    return {k: sorted(v) for k, v in graph.items()}, stats


def load_static_topology(path=DEFAULT_TOPOLOGY):
    if not path or not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {k: list(v) for k, v in (data.get("edges") or {}).items()}


def _hop_nhat_do_thi(*do_thi):
    """Hop (union) cac do thi {caller: [callee]}. Khong ghi de, chi gop."""
    gop = defaultdict(set)
    for g in do_thi:
        for caller, callees in (g or {}).items():
            gop[caller].update(callees)
    return {k: sorted(v) for k, v in gop.items()}


def resolve_topology(prom_url=None, static_path=DEFAULT_TOPOLOGY, timeout=10):
    """Tra ve (graph, source, note). KHONG BAO GIO xuong cap am tham.

    HOP NHAT spanmetrics voi file tinh, KHONG phai "cai nay thay cai kia". Truoc day
    spanmetrics thay the file tinh moi khi no tra > 0 canh, nen tren cum file tinh khong
    bao gio duoc dung — va suy luan thi RECALL THAP: do 30/07 chi suy duoc 13/28 canh sync
    (46%) va 0/4 canh async.

    Vi sao thieu canh cung sai chu khong chi "kem chinh xac", do that 31/07: giet `quote`,
    canh THAT `frontend-proxy -> frontend` bi thieu (span CLIENT cua frontend-proxy ten
    `router frontend egress`, khong khop SERVER span_name nao). Chi voi do thi suy ra,
    khong service do nao phu thuoc vao `shipping` nen `shipping` duoc 0 diem. Hop nhat voi
    file tinh — noi co `frontend -> shipping`, `checkout -> shipping`, `shipping -> quote` —
    thi `shipping` giai thich duoc 4/4 va len dung vi tri goc.

    Danh doi da biet, ghi ra chu khong giau: file tinh co the LOI THOI (vi du
    `checkout -> payment` da chuyen sang Kafka 25/07, nen no nam o `async_edges` chu khong
    o `edges`). Hop nhat co the keo lai mot canh cu ma suy luan da dung khi bo qua. Doi lai
    la khong mat canh that. Voi RCA, thieu canh va thua canh deu dan toi ket luan sai, nen
    `note` phai noi ro bao nhieu canh den tu dau de nguoi doc tu kiem duoc.
    """
    suy = {}
    stats = None
    if prom_url:
        try:
            suy, stats = graph_from_spanmetrics(prom_url, timeout)
            ghi_chu_suy = (
                f"{stats['edges']} canh suy tu spanmetrics "
                f"({stats['client_series']} chuoi CLIENT, {stats['server_series']} chuoi SERVER"
            )
            if stats["generic_span_names"]:
                ghi_chu_suy += f", bo {stats['generic_span_names']} span_name tran"
            if stats["ambiguous_span_names"]:
                ghi_chu_suy += f", bo {stats['ambiguous_span_names']} span_name mo ho"
            ghi_chu_suy += ")"
            if stats["edges"] == 0:
                ghi_chu_suy = "spanmetrics tra 0 canh"
        except Exception as exc:  # noqa: BLE001
            suy, ghi_chu_suy = {}, f"khong query duoc Prometheus ({exc})"
    else:
        ghi_chu_suy = "khong dua --prom-url"

    tinh = load_static_topology(static_path)
    ten_file = os.path.basename(static_path)

    if suy and tinh:
        gop = _hop_nhat_do_thi(suy, tinh)
        n_gop = sum(len(v) for v in gop.values())
        n_suy = sum(len(v) for v in suy.values())
        n_tinh = sum(len(v) for v in tinh.values())
        return gop, "spanmetrics+static", (
            f"{n_gop} canh = hop nhat cua {n_suy} canh spanmetrics va {n_tinh} canh "
            f"{ten_file}. {ghi_chu_suy}. CANH BAO: phan tu file tinh co the da loi thoi."
        )
    if suy:
        return suy, "spanmetrics", f"{ghi_chu_suy}, khong co {ten_file} de hop nhat"
    if tinh:
        edges = sum(len(v) for v in tinh.values())
        return tinh, "static-fallback", (
            f"{ghi_chu_suy} -> dung {ten_file} ({edges} canh). "
            "CANH BAO: file tinh co the da loi thoi so voi kien truc that."
        )
    return {}, "none", (
        f"{ghi_chu_suy}, va khong co file topology -> KHONG loai duoc tuong quan. "
        "Xep hang duoi day CHI dua tren thu tu thoi gian."
    )


def _depends_on(graph, start, target, _seen=None):
    """True neu `start` phu thuoc BAC CAU vao `target` (co duong start -> ... -> target)."""
    if _seen is None:
        _seen = set()
    if start in _seen:
        return False
    _seen.add(start)
    for nxt in graph.get(start, ()):
        if nxt == target or _depends_on(graph, nxt, target, _seen):
            return True
    return False


def _linked(graph, a, b):
    """a va b co lien he phu thuoc theo huong nao do khong."""
    return _depends_on(graph, a, b) or _depends_on(graph, b, a)


# ---------------------------------------------------------------------------
# Cham diem
# ---------------------------------------------------------------------------
def diagnose(alerts, window_start, window_end, graph=None, topology_source="none",
             topology_note="", error_ratios=None):
    """Tra ve dict co `root_suspect`, `ranking` va `explanation` doc duoc."""
    graph = graph or {}
    error_ratios = error_ratios or {}
    reds = red_services(alerts, window_start, window_end)

    if not reds:
        return {
            "root_suspect": None,
            "confidence": None,
            "ranking": [],
            "concurrent_unrelated": [],
            "topology": {"source": topology_source, "note": topology_note},
            "explanation": ["Khong co alert nao trong cua so — khong co gi de chan doan."],
        }

    services = sorted(reds)
    graph_usable = any(graph.values())

    # --- Tach cascade ra khoi su co chay song song ---------------------------
    # Mot service do ma KHONG noi duoc voi bat ky service do nao khac thi no khong phai
    # ung vien goc cua cascade nay. Do la co che "khong nham tuong quan thanh nhan qua".
    linked = {
        s for s in services
        if any(_linked(graph, s, o) for o in services if o != s)
    }
    # `linked` la 0 hoac >= 2 (xem ghi chu o dau file), nen "co cascade" = tap nay khong rong.
    cascade_mode = graph_usable and bool(linked)
    candidates = sorted(linked) if cascade_mode else services
    unrelated = sorted(set(services) - set(candidates))

    def _entry(svc, score, explains_n, t_first_map):
        return {
            "service": svc,
            "score": round(score, 4),
            "explains_n": explains_n,
            "t_first": t_first_map[svc],
            "rank_by_time": sorted(t_first_map.values()).index(t_first_map[svc]) + 1,
            "error_ratio": error_ratios.get(svc),
            "n_alerts": reds[svc]["n_alerts"],
            "rules": reds[svc]["rules"],
        }

    # Thu tu thoi gian tinh tren TOAN BO service do, ke ca cai bi loai — de con noi duoc
    # "no keu truoc nhung van bi loai" trong bao cao.
    t_all = {s: reds[s]["t_first"] for s in services}

    # --- Tang 1: do thi. Bao nhieu ung vien KHAC phu thuoc vao ung vien nay. ---
    explains = {
        svc: sum(1 for o in candidates if o != svc and _depends_on(graph, o, svc))
        for svc in candidates
    }
    max_explains = max(explains.values()) if explains else 0

    ranking = [
        _entry(svc, (explains[svc] / max_explains) if max_explains else 0.0,
               explains[svc], t_all)
        for svc in candidates
    ]

    # Do thi quyet dinh; hoa diem thi keu truoc thang. Khi max_explains == 0 (do thi khong
    # tach duoc ai voi ai) thi moi diem deu 0 va thu tu thoi gian quyet dinh toan bo — luc
    # do `basis` phai noi ro la dang xep theo thoi gian, khong duoc de nguoi doc tuong ket
    # luan co do thi chong lung.
    ranking.sort(key=lambda r: (-r["score"], r["t_first"]))
    top = ranking[0]
    total = sum(r["score"] for r in ranking)
    basis = "dependency-graph" if max_explains else "temporal-only"

    concurrent = [
        {**_entry(svc, 0.0, 0, t_all),
         "reason": "khong co duong phu thuoc nao toi nhom do con lai — nhieu kha nang la "
                   "mot su co RIENG chay song song, khong phai goc cua cascade nay"}
        for svc in unrelated
    ]

    return {
        "root_suspect": top["service"],
        # Ti trong diem do thi, KHONG phai xac suat. Doc la "no noi troi bao nhieu so voi
        # phan con lai". None khi do thi khong dong gop gi — bia mot con so o do la noi doi.
        "confidence": round(top["score"] / total, 3) if total else None,
        "basis": basis,
        "ranking": ranking,
        "concurrent_unrelated": concurrent,
        "topology": {"source": topology_source, "note": topology_note},
        "explanation": _build_explanation(top, ranking, concurrent, graph, graph_usable, basis),
        "window": {"start": window_start, "end": window_end},
    }


def _build_explanation(top, ranking, concurrent, graph, graph_usable, basis="dependency-graph"):
    """Ly le doc duoc — day la SAN cua mandate, khong phai phan trang tri."""
    lines = []
    svc = top["service"]
    n_all = len(ranking) + len(concurrent)

    others = [r for r in ranking if r["service"] != svc]
    if top["rank_by_time"] == 1 and n_all > 1:
        deltas = sorted(
            (r["t_first"] - top["t_first"], r["service"])
            for r in others + concurrent
        )
        detail = ", ".join(f"{name} +{d:.0f}s" for d, name in deltas[:3])
        lines.append(f"keu DAU TIEN trong cua so — som hon {detail}")
    elif n_all > 1:
        lines.append(
            f"KHONG keu dau tien (hang {top['rank_by_time']}/{n_all} theo thoi gian) "
            "— duoc chon nho huong phu thuoc, xem dong duoi"
        )

    if top["explains_n"] > 0:
        dependents = [r["service"] for r in others if _depends_on(graph, r["service"], svc)]
        lines.append(
            f"{top['explains_n']}/{len(others)} service do con lai phu thuoc vao no "
            f"({', '.join(dependents)}) — trang thai cua no giai thich duoc chung"
        )
    elif graph_usable:
        lines.append(
            "khong service do nao phu thuoc vao no theo topology hien co — "
            "xep hang nay CHI dua tren thu tu thoi gian"
        )
    else:
        lines.append("KHONG co topology — chua loai duoc kha nang day chi la trung hop")

    if basis == "temporal-only":
        lines.append(
            "CANH BAO: do thi khong tach duoc ung vien nao (khong ai phu thuoc vao ai trong "
            "nhom do), nen ket luan nay YEU hon binh thuong — no chi noi 'cai nay do truoc'"
        )

    if top["error_ratio"] is not None:
        lines.append(f"ti le loi {top['error_ratio']:.4f}")

    if top["rules"]:
        lines.append(f"rule da keu: {', '.join(top['rules'])}")

    if concurrent:
        lines.append(
            "LOAI khoi danh sach nghi pham (do nhung khong noi duoc voi nhom do — "
            "nhieu kha nang la su co rieng chay song song): "
            + ", ".join(c["service"] for c in concurrent)
        )
    return lines


# ---------------------------------------------------------------------------
# Do lon loi (tuy chon — chi khi co Prometheus)
# ---------------------------------------------------------------------------
def error_ratios_at(prom_url, at_ts, window="5m", timeout=10):
    """Ti le loi tung service tai mot thoi diem. Tra ve {} neu khong lay duoc."""
    promql = (
        'sum by (service_name) (rate(traces_span_metrics_calls_total{'
        'status_code="STATUS_CODE_ERROR", span_name!="grpc.health.v1.Health/Check", '
        'span_kind=~"SPAN_KIND_SERVER|SPAN_KIND_CONSUMER"}[' + window + "]))"
        " / clamp_min(sum by (service_name) (rate(traces_span_metrics_calls_total{"
        'span_name!="grpc.health.v1.Health/Check", '
        'span_kind=~"SPAN_KIND_SERVER|SPAN_KIND_CONSUMER"}[' + window + "])), 0.001)"
    )
    url = prom_url.rstrip("/") + "/api/v1/query?" + urllib.parse.urlencode(
        {"query": promql, "time": at_ts}
    )
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310
            payload = json.loads(resp.read().decode("utf-8"))
        if payload.get("status") != "success":
            return {}
        out = {}
        for row in payload["data"]["result"]:
            svc = row.get("metric", {}).get("service_name")
            if svc:
                out[svc] = float(row["value"][1])
        return out
    except Exception:  # noqa: BLE001
        return {}


# ---------------------------------------------------------------------------
# In bao cao
# ---------------------------------------------------------------------------
def format_report(result):
    lines = ["", "=" * 70, "RCA — Diagnose stage (MANDATE-26)", "-" * 70]
    if not result["root_suspect"]:
        lines += ["  " + l for l in result["explanation"]]
        lines += ["=" * 70, ""]
        return "\n".join(lines)

    conf = result["confidence"]
    conf_txt = f"confidence {conf}" if conf is not None else "confidence n/a"
    lines.append(
        f"  ROOT SUSPECT: {result['root_suspect']}   "
        f"({conf_txt} · can cu: {result.get('basis', '?')})"
    )
    lines.append("  vi sao:")
    for l in result["explanation"]:
        lines.append(f"    - {l}")
    lines.append("  xep hang nghi pham:")
    for r in result["ranking"]:
        lines.append(
            f"    {r['service']:<18} {r['score']:.4f}  "
            f"(giai thich {r['explains_n']} · hang thoi gian {r['rank_by_time']})"
        )
    if result.get("concurrent_unrelated"):
        lines.append("  LOAI khoi nghi pham — su co rieng chay song song:")
        for c in result["concurrent_unrelated"]:
            lines.append(
                f"    {c['service']:<18} (hang thoi gian {c['rank_by_time']}) — {c['reason']}"
            )
    topo = result["topology"]
    lines.append(f"  nguon topology: {topo['source']} — {topo['note']}")
    lines += ["=" * 70, ""]
    return "\n".join(lines)
