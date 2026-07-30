"""MANDATE-28 — dong canh bao theo thoi gian, danh sach incident, va verdict `sustained`.

Mandate doi mot artifact tuong minh: "Xuat duoc dong canh bao theo thoi gian + danh sach
incident de doi chieu". File nay kiem ca artifact do lan logic cham diem dung chung no.

Run:
    pytest aiops/test_timeline.py -v
"""
import incident_replay as ir
import timeline

T0 = 1_785_000_000.0
POLL = 30.0
COOLDOWN = 600.0


def _a(ts_offset, service="checkout", rule="service-error-rate-high", sev="critical"):
    return {"ts": T0 + ts_offset, "rule_id": rule, "service": service, "severity": sev}


def _nhip(start, stop, step=COOLDOWN, **kw):
    """Alert theo dung nhip cooldown 600s — nhip that cua mot rule keu moi chu ky."""
    out, t = [], start
    while t <= stop:
        out.append(_a(t, **kw))
        t += step
    return out


# ---------------------------------------------------------------------------
# silent_gaps — dung cua so tu NHAN, khong suy tu chinh alert
# ---------------------------------------------------------------------------
def test_nhip_cooldown_binh_thuong_khong_phai_khoang_cam():
    """Rule keu moi chu ky van chi GUI alert 10 phut/lan. Do la chong spam, khong phai mu."""
    alerts = _nhip(0, 3600)
    gaps = timeline.silent_gaps(alerts, ["service-error-rate-high"], "checkout",
                                T0, T0 + 3600)
    assert gaps == [], f"600s la nhip cooldown, khong duoc coi la cam: {gaps}"


def test_khoang_cam_that_bi_bat():
    """Bo het alert tu phut 10 den phut 40 — dung cai bug MANDATE-28 nham toi."""
    alerts = _nhip(0, 600) + _nhip(2400, 3600)
    gaps = timeline.silent_gaps(alerts, ["service-error-rate-high"], "checkout",
                                T0, T0 + 3600)
    assert len(gaps) == 1
    assert gaps[0]["seconds"] == 1800.0
    assert gaps[0]["where"] == "giua hai alert"


def test_khong_co_alert_nao_thi_ca_cua_so_la_khoang_cam():
    """Suy cua so tu chinh alert se cho ra '0 khoang cam' — dung ky thuat ma vo nghia."""
    gaps = timeline.silent_gaps([], ["service-error-rate-high"], "checkout", T0, T0 + 3600)
    assert len(gaps) == 1 and gaps[0]["seconds"] == 3600.0
    assert "KHONG co alert nao" in gaps[0]["where"]


def test_bat_ca_hai_dau_cua_so():
    """Bao muon 20 phut roi tat som 20 phut cung la cam, du o giua lien tuc."""
    alerts = _nhip(1200, 2400)
    gaps = timeline.silent_gaps(alerts, ["service-error-rate-high"], "checkout",
                                T0, T0 + 3600)
    assert {g["where"] for g in gaps} == {"dau cua so toi alert dau tien",
                                          "alert cuoi toi cuoi cua so"}


def test_alert_cua_rule_khac_khong_lap_duoc_khoang_cam_cua_rule_nay():
    alerts = _nhip(0, 600) + _nhip(1200, 2400, rule="latency-p95-high") + _nhip(3000, 3600)
    gaps = timeline.silent_gaps(alerts, ["service-error-rate-high"], "checkout",
                                T0, T0 + 3600)
    assert gaps and gaps[0]["seconds"] == 2400.0


def test_bat_ky_rule_nao_trong_tap_deu_tinh_la_dang_bao():
    """Voi nguoi truc, duoc bao la duoc bao — khong quan trong rule nao noi."""
    alerts = _nhip(0, 600) + _nhip(1200, 2400, rule="latency-p95-high") + _nhip(3000, 3600)
    gaps = timeline.silent_gaps(alerts, ["service-error-rate-high", "latency-p95-high"],
                                "checkout", T0, T0 + 3600)
    assert gaps == []


def test_bo_qua_alert_detector_tu_bao_ve_chinh_no():
    alerts = _nhip(0, 600) + [_a(1800, rule="detector-silent-rule", sev="info")] + _nhip(3000, 3600)
    gaps = timeline.silent_gaps(alerts, ["service-error-rate-high"], "checkout", T0, T0 + 3600)
    assert gaps, "alert tu-to-cao khong duoc lap khoang cam cua he thong duoc do"


# ---------------------------------------------------------------------------
# build_incidents
# ---------------------------------------------------------------------------
def test_gom_thanh_incident_va_tach_khi_cach_xa():
    alerts = _nhip(0, 1200) + _nhip(3600, 4200)
    inc = timeline.build_incidents(alerts)
    assert len(inc) == 2
    assert inc[0]["n_alerts"] == 3 and inc[0]["duration_seconds"] == 1200.0
    assert inc[1]["start"] == T0 + 3600


def test_hai_service_thanh_hai_incident_rieng():
    alerts = _nhip(0, 1200) + _nhip(600, 1800, service="payment")
    inc = timeline.build_incidents(alerts)
    assert {i["service"] for i in inc} == {"checkout", "payment"}
    assert len(inc) == 2


def test_bao_cao_doc_duoc_va_chi_ro_khoang_cam():
    alerts = _nhip(0, 600) + _nhip(2400, 3600)
    txt = timeline.format_timeline(alerts, T0, T0 + 3600)
    assert "DONG CANH BAO THEO THOI GIAN" in txt
    assert "DANH SACH INCIDENT" in txt
    assert "KHOANG CAM" in txt, "bao cao phai chi thang ra cho cam, khong bat nguoi doc tu tinh"


def test_alert_service_khac_khong_che_duoc_khoang_cam_TREN_BAN_IN():
    """Cot khoang cach phai tinh theo tung `rule x service`, khong so voi dong ngay truoc.

    So voi dong truoc thi mot alert cua frontend chen vao giua se lam khoang cam 1800s cua
    checkout hien ra thanh "+600s" — dung cai bug MANDATE-28 di tim, chi la o ban in.
    Bug that, phat hien khi chay thu CLI.
    """
    alerts = (_nhip(0, 1200, service="checkout")
              + _nhip(1800, 3000, service="frontend")
              + [_a(3000, service="checkout")])
    txt = timeline.format_timeline(alerts, T0, T0 + 3600)
    dong_cam = [l for l in txt.splitlines() if "KHOANG CAM" in l and "checkout" in l]
    assert dong_cam, "khoang cam 1800s cua checkout phai hien ra du frontend keu xen vao"
    assert "+1800s" in dong_cam[0], dong_cam[0]


def test_nhieu_lan_bung_phat_cung_service_duoc_danh_dau():
    alerts = _nhip(0, 1200) + _nhip(3000, 3600)
    txt = timeline.format_timeline(alerts, T0, T0 + 3600)
    assert "lan bung phat roi rac" in txt, \
        "hai incident cung mot rule x service nghia la co khoang cam giua chung — phai noi ra"


# ---------------------------------------------------------------------------
# verdict `sustained`
# ---------------------------------------------------------------------------
def _ev(label, service, t0, t1, rules=("service-error-rate-high",)):
    return {"label": label, "service": service, "expected_rule_ids": list(rules),
            "expect_fire": True, "t_start": T0 + t0, "t_end": T0 + t1}


def _cham(events, alerts, tmp_path, settle=0):
    p = tmp_path / "h.jsonl"
    import json
    p.write_text("\n".join(json.dumps(a) for a in alerts) + "\n", encoding="utf-8")
    return ir.score_events(events, str(p), settle)


def test_sustained_PASS_khi_bao_lien_tuc(tmp_path):
    score = _cham([_ev("su-co-dai", "checkout", 0, 3600)], _nhip(0, 3600), tmp_path)
    ok, ly_do = ir.verdict_for_type("sustained", score["per_event"])
    assert ok is True, ly_do


def test_sustained_FAIL_khi_co_khoang_cam(tmp_path):
    alerts = _nhip(0, 600) + _nhip(2400, 3600)
    score = _cham([_ev("su-co-dai", "checkout", 0, 3600)], alerts, tmp_path)
    ok, ly_do = ir.verdict_for_type("sustained", score["per_event"])
    assert ok is False and "KHOANG CAM" in ly_do, ly_do


def test_sustained_FAIL_khi_bo_lo_su_co_chong(tmp_path):
    """Su co 1 duoc bao suot, su co 2 tren service khac hoan toan im — phai FAIL."""
    events = [_ev("su-co-1", "checkout", 0, 3600), _ev("su-co-2", "payment", 1800, 3600)]
    score = _cham(events, _nhip(0, 3600), tmp_path)
    ok, ly_do = ir.verdict_for_type("sustained", score["per_event"])
    assert ok is False and "bo lo" in ly_do, ly_do


def test_sustained_PASS_khi_su_co_chong_duoc_tach_rieng(tmp_path):
    events = [_ev("su-co-1", "checkout", 0, 3600), _ev("su-co-2", "payment", 1800, 3600)]
    alerts = _nhip(0, 3600) + _nhip(1800, 3600, service="payment")
    score = _cham(events, alerts, tmp_path)
    ok, ly_do = ir.verdict_for_type("sustained", score["per_event"])
    assert ok is True and "tach rieng" in ly_do, ly_do


def test_alert_cua_service_khac_khong_lap_duoc_khoang_cam(tmp_path):
    """payment keu am i khong the che cho viec checkout dang im."""
    events = [_ev("su-co-dai", "checkout", 0, 3600)]
    alerts = _nhip(0, 600) + _nhip(600, 3600, service="payment")
    score = _cham(events, alerts, tmp_path)
    ok, ly_do = ir.verdict_for_type("sustained", score["per_event"])
    assert ok is False and "KHOANG CAM" in ly_do, ly_do


# ---------------------------------------------------------------------------
# Lich bom — su co 2 phai no CHONG len su co 1
# ---------------------------------------------------------------------------
def test_lich_bom_cho_phep_chong_lan():
    """Truoc day do_inject chay tuan tu nen hai su co KHONG BAO GIO chong nhau duoc."""
    events = [
        {"label": "dai", "offset_seconds": 0, "duration_seconds": 2100},
        {"label": "chong", "offset_seconds": 1200, "duration_seconds": 600},
    ]
    sched = ir.build_schedule(events)
    assert [(at, act, i) for at, act, i in sched] == [
        (0, "on", 0), (1200, "on", 1), (1800, "off", 1), (2100, "off", 0),
    ], "su kien 2 phai bat VA tat khi su kien 1 van dang chay"


def test_lich_bom_tuan_tu_khong_doi_hanh_vi():
    """Kich ban khong chong lan (moi ca hien co) phai chay y het nhu truoc."""
    events = [
        {"label": "spike", "offset_seconds": 0, "duration_seconds": 360},
        {"label": "nho", "offset_seconds": 900, "duration_seconds": 60},
    ]
    assert ir.build_schedule(events) == [
        (0, "on", 0), (360, "off", 0), (900, "on", 1), (960, "off", 1),
    ]


def _kich_ban(ten):
    import json
    import os
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "incident_scenarios", ten)
    return json.load(open(p, encoding="utf-8"))


def _diem_bom(ev):
    """Ten deployment bi giet, doc tu lenh `inject.on`."""
    import re
    m = re.search(r"deploy/([a-z0-9-]+)", ev["inject"]["on"])
    assert m, f"khong doc duoc diem bom tu: {ev['inject']['on']}"
    return m.group(1)


def _phu_thuoc_vao(topo, tu, den):
    """`tu` co phu thuoc DONG BO (truc tiep hay bac cau) vao `den` khong?

    Chi di theo `edges`. `async_edges` co y KHONG tinh: da do 26/07 rang giet payment
    KHONG lam ti le loi cua checkout nhuc nhich (0.0000 suot 13/13 mau), nen canh qua
    Kafka khong truyen loi sang nguoi goi.
    """
    edges = {k: v for k, v in topo.get("edges", {}).items() if not k.startswith("_")}
    da_tham, hang_doi = set(), [tu]
    while hang_doi:
        node = hang_doi.pop()
        if node in da_tham:
            continue
        da_tham.add(node)
        for ke in edges.get(node, []):
            if ke == den:
                return True
            hang_doi.append(ke)
    return False


def test_kich_ban_sustained_trong_repo_hop_le():
    """File kich ban commit trong repo phai thuc su chong lan, khong chi noi la chong."""
    sc = _kich_ban("case_sustained_stacked.json")
    assert sc["type"] == "sustained"
    dai, chong = sc["events"]
    assert dai["duration_seconds"] >= 1800, "su co 'dai' phai dai hon cua so baseline 15 phut"
    assert chong["offset_seconds"] > dai["offset_seconds"]
    assert (chong["offset_seconds"] + chong["duration_seconds"]
            < dai["offset_seconds"] + dai["duration_seconds"]), \
        "su co 2 phai nam TRON trong su co 1, khong thi khong goi la no chong"
    assert dai["service"] != chong["service"], "hai su co phai o hai service khac nhau"


def test_nan_nhan_su_kien_2_khong_duoc_do_san_vi_su_kien_1():
    """Bay da SAP DAM PHAI mot lan — ban 001 cua kich ban nay.

    Ban do giet `cart` (su kien 1) roi cham diem su kien 2 tren `frontend`. Nhung
    `frontend -> cart` la canh dong bo, nen frontend DA do truoc khi su kien 2 bat dau.
    Phep kiem "su co 2 duoc bat va tach rieng" khi do PASS du freeze co hoat dong hay
    khong — mot ca kiem luon xanh, dung thu ma ca dot MANDATE-15/26 di tim.

    Rang buoc: nan nhan cua su kien 2 KHONG duoc phu thuoc dong bo vao diem bom cua
    su kien 1. Kiem tren chinh `topology.json` de con so khong troi khoi do thi.
    """
    import json
    import os
    topo = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                       "topology.json"), encoding="utf-8"))
    sc = _kich_ban("case_sustained_stacked.json")
    dai, chong = sc["events"]
    bom_1 = _diem_bom(dai)

    assert not _phu_thuoc_vao(topo, chong["service"], bom_1), (
        f"nan nhan su kien 2 (`{chong['service']}`) phu thuoc vao `{bom_1}` — thu ma su kien 1 "
        f"giet. No se do san truoc khi su kien 2 bat dau, nen phep kiem 'tach rieng' thanh vo nghia."
    )
    assert chong["service"] != bom_1, "nan nhan su kien 2 khong duoc chinh la thu su kien 1 giet"


def test_hai_su_kien_khong_dung_chung_diem_bom():
    """Lenh `off` cua su kien 1 se xoa luon loi cua su kien 2 neu chung cung mot deployment."""
    dai, chong = _kich_ban("case_sustained_stacked.json")["events"]
    assert _diem_bom(dai) != _diem_bom(chong)


def test_co_kich_ban_tham_do_va_no_kiem_dung_cap_service():
    """Kich ban dai bat buoc phai co ban tham do di truoc, va tham do phai do DUNG cap do.

    Khong co rang buoc nay thi de xay ra canh: doi cap service o kich ban dai ma quen doi
    ban tham do, roi chay 40 phut de phat hien ra minh tham do nham thu.
    """
    probe = _kich_ban("case_preflight_probe.json")
    dai, chong = _kich_ban("case_sustained_stacked.json")["events"]

    assert len(probe["events"]) == 1, "tham do chi nen hoi MOT cau"
    ev = probe["events"][0]
    assert ev["service"] == chong["service"], (
        f"tham do dang do `{ev['service']}` nhung kich ban dai cham diem su kien 2 tren "
        f"`{chong['service']}` — do nham thu"
    )
    assert _diem_bom(ev) == _diem_bom(chong), "tham do phai bom dung diem ma su kien 2 bom"
    assert ev["duration_seconds"] <= 300, (
        "tham do phai NGAN — muc dich la tra loi mot cau hoi nhi phan, khong phai do dac"
    )
