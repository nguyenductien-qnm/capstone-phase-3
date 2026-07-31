"""Unit tests cho tang Diagnose (MANDATE-26) — aiops/diagnose.py.

Moi fixture la mot cascade tong hop co GOC THAT BIET TRUOC, nen test tra loi duoc dung cau
mandate hoi: "RCA co chi dung goc khong", chu khong phai "code co chay khong".

Khong can Prometheus/K8s/cum: diagnose.diagnose() la ham thuan, chi nhan list alert + do thi.

Run:
    pytest aiops/test_diagnose.py -v
"""
import json
import os

import diagnose

# Do thi that cua he (rut gon quanh luong browse/checkout). A -> B = "A goi B", nghia la
# B hong thi A hong theo.
GRAPH = {
    "frontend-proxy": ["frontend"],
    "frontend": ["cart", "checkout", "product-catalog", "recommendation"],
    "checkout": ["cart", "currency", "product-catalog"],
    "recommendation": ["product-catalog"],
}

T0 = 1_785_000_000.0


def _alert(svc, offset, rule="service-error-rate-high"):
    return {"ts": T0 + offset, "rule_id": rule, "service": svc, "severity": "critical"}


def _run(alerts, graph=GRAPH, source="static-fallback", ratios=None):
    return diagnose.diagnose(
        alerts, T0 - 10, T0 + 600,
        graph=graph, topology_source=source, topology_note="test", error_ratios=ratios,
    )


# ---------------------------------------------------------------------------
# 1. Cascade don — goc keu truoc VA duoc nhieu service phu thuoc
# ---------------------------------------------------------------------------
def test_cascade_don_chi_dung_goc():
    """`cart` chet -> checkout va frontend do theo. Goc phai la cart."""
    res = _run([
        _alert("cart", 0),
        _alert("checkout", 30),
        _alert("frontend", 55),
    ])
    assert res["root_suspect"] == "cart"
    # San cua mandate: phai co ly le, khong duoc chi tra ve mot cai ten tran.
    assert res["explanation"], "phai co giai thich kem theo"
    assert any("DAU TIEN" in l for l in res["explanation"])
    assert any("phu thuoc vao no" in l for l in res["explanation"])


def test_khong_dung_o_trieu_chung_downstream():
    """Mandate cam dung o trieu chung downstream: frontend do nang nhat van khong phai goc."""
    res = _run(
        [_alert("cart", 0), _alert("checkout", 30), _alert("frontend", 55)],
        ratios={"frontend": 0.95, "checkout": 0.40, "cart": 0.10},
    )
    assert res["root_suspect"] == "cart", "do lon loi khong duoc lan at huong phu thuoc"


def test_hai_anh_em_cung_bac_thi_cai_do_TRUOC_thang():
    """Hai phu thuoc ngang hang cua frontend cung do — do thi khong tach duoc chung.

    Luc do THU TU THOI GIAN moi quyet dinh. Fixture co y dat ten sao cho thu tu ALPHABET
    NGUOC voi thu tu thoi gian: `cart` dung truoc `checkout` theo alphabet nhung keu SAU.
    Neu bo tiebreak theo thoi gian thi sorted() on dinh se tra ve `cart` — dung ket qua
    mong doi nhung vi ly do sai. Dao thu tu nhu the nay moi do duoc dung cai tiebreak.
    """
    res = _run(
        [_alert("checkout", 0), _alert("cart", 50), _alert("frontend", 70)],
        graph={"frontend": ["cart", "checkout"]},   # cart va checkout la anh em, khong noi nhau
    )
    assert res["root_suspect"] == "checkout", "cai do TRUOC thang, khong phai cai dung dau alphabet"
    top2 = [r["service"] for r in res["ranking"][:2]]
    assert top2 == ["checkout", "cart"]


def test_do_lon_loi_khong_duoc_lat_nguoc_ket_luan():
    """Ti le loi cua downstream thuong CAO hon goc — no phai la boi canh, khong phai phieu bau."""
    alerts = [_alert("cart", 0), _alert("checkout", 30), _alert("frontend", 55)]
    khong_ratio = _run(alerts)
    co_ratio = _run(alerts, ratios={"frontend": 0.99, "checkout": 0.95, "cart": 0.01})
    assert khong_ratio["root_suspect"] == co_ratio["root_suspect"] == "cart"
    assert [r["service"] for r in khong_ratio["ranking"]] == \
           [r["service"] for r in co_ratio["ranking"]], "ti le loi khong duoc doi thu tu"


# ---------------------------------------------------------------------------
# 2. Bay tuong quan — thu do lam mandate cho diem cao
# ---------------------------------------------------------------------------
def test_loai_duoc_tin_hieu_trung_hop():
    """`jaeger` OOM cung luc nhung khong lien quan gi ca — va no con keu TRUOC cart.

    Day la ca that: 28/07 pod jaeger OOM deu dan ~39 phut/lan, doc lap voi moi su co dang do.
    Mot RCA chi nhin thoi gian se xep no len dau.
    """
    res = _run([
        _alert("jaeger", 0, rule="oom-detected"),   # keu TRUOC nhat
        _alert("cart", 20),
        _alert("checkout", 45),
        _alert("frontend", 70),
    ])
    assert res["root_suspect"] == "cart"

    # Phai bi LOAI HAN khoi danh sach nghi pham, khong phai chi ha bac.
    assert "jaeger" not in [r["service"] for r in res["ranking"]]
    jaeger = next(c for c in res["concurrent_unrelated"] if c["service"] == "jaeger")
    assert jaeger["rank_by_time"] == 1, "fixture phai dat jaeger keu truoc nhat moi co nghia"
    assert "song song" in jaeger["reason"]
    assert any("LOAI khoi danh sach nghi pham" in l for l in res["explanation"]), \
        "phai NOI RA vi sao loai no, khong duoc lang le bo di"


# ---------------------------------------------------------------------------
# 3. Bay thoi gian — do thi phai thang thu tu thoi gian
# ---------------------------------------------------------------------------
def test_do_thi_thang_thu_tu_thoi_gian_khi_hai_ben_mau_thuan():
    """Trieu chung downstream keu TRUOC goc (lech scrape / cooldown lech pha).

    Thu tu thoi gian mot minh se chi sai. Huong phu thuoc phai keo lai duoc.
    """
    res = _run([
        _alert("frontend", 0),    # downstream, nhung keu truoc
        _alert("checkout", 10),
        _alert("cart", 25),       # goc that, keu muon nhat
    ])
    assert res["root_suspect"] == "cart"
    cart = next(r for r in res["ranking"] if r["service"] == "cart")
    assert cart["rank_by_time"] == 3, "fixture phai dat goc keu MUON nhat moi co nghia"
    assert any("KHONG keu dau tien" in l for l in res["explanation"]), \
        "phai thua nhan la no khong keu dau tien, chu khong giau"


# ---------------------------------------------------------------------------
# 4. Khong co topology — van xep hang, nhung phai KHAI BAO
# ---------------------------------------------------------------------------
def test_khong_co_topology_thi_noi_thang_ra():
    res = _run(
        [_alert("cart", 0), _alert("checkout", 30), _alert("frontend", 55)],
        graph={}, source="none",
    )
    assert res["root_suspect"] == "cart", "khong co do thi thi con moi thu tu thoi gian"
    assert any("KHONG co topology" in l for l in res["explanation"]), \
        "im lang ve viec thieu topology la dung lop loi 'trong nhu dang canh nhung thuc ra khong'"
    # Khong duoc loai ai ca: do thi rong thi "khong noi duoc" phan anh topology thieu,
    # khong phan anh he thong. Loai o day la vu oan.
    assert res["concurrent_unrelated"] == []
    assert len(res["ranking"]) == 3


def test_mot_service_do_don_doc_khong_bi_vu_oan():
    """Chi 1 service noi duoc thi chua thanh cascade — khong duoc loai nhung cai con lai.

    Nguong MIN_LINKED_FOR_CASCADE canh dung cho nay: mot topology thieu canh se lam moi
    service trong 'khong noi duoc', va loai het thi RCA tu bo mat moi ung vien that.
    """
    res = _run(
        [_alert("cart", 0), _alert("email", 30)],
        graph={"checkout": ["cart"]},   # ca cart lan email deu khong noi voi nhau
    )
    assert res["concurrent_unrelated"] == []
    assert len(res["ranking"]) == 2


# ---------------------------------------------------------------------------
# 5. Ca chua tung thay — chuoi 4 tang khong nam trong bo nao
# ---------------------------------------------------------------------------
def test_chuoi_bon_tang_chua_tung_thay():
    """Khong co catalog fault, khong model hoc — nen hinh dang cascade nao cung chay."""
    graph = {"a": ["b"], "b": ["c"], "c": ["d"]}
    res = diagnose.diagnose(
        [_alert("a", 0), _alert("b", 5), _alert("c", 10), _alert("d", 15)],
        T0 - 10, T0 + 600, graph=graph, topology_source="static-fallback", topology_note="t",
    )
    # `d` keu MUON nhat va la day chuoi — nhung ca ba service kia deu phu thuoc bac cau vao no.
    assert res["root_suspect"] == "d"
    top = res["ranking"][0]
    assert top["explains_n"] == 3, "phai bac cau qua ca chuoi, khong chi 1 buoc"


# ---------------------------------------------------------------------------
# Ranh gioi
# ---------------------------------------------------------------------------
def test_do_thi_khong_tach_duoc_thi_phai_KHAI_BAO_la_chi_theo_thoi_gian():
    """cart va email cung do, khong ai phu thuoc ai — do thi khong dong gop gi.

    Van phai tra ve mot goc (san cua mandate la chi dich danh), NHUNG phai noi ro can cu
    yeu hon binh thuong. Bia mot confidence o day la noi doi.
    """
    res = _run([_alert("cart", 0), _alert("email", 30)], graph={"checkout": ["cart", "email"]})
    assert res["root_suspect"] == "cart", "khong tach duoc thi cai do TRUOC thang"
    assert res["basis"] == "temporal-only"
    assert res["confidence"] is None, "khong co dong gop cua do thi thi khong duoc bia so"
    assert any("YEU hon binh thuong" in l for l in res["explanation"])


def test_co_do_thi_thi_can_cu_phai_la_do_thi():
    res = _run([_alert("cart", 0), _alert("checkout", 30), _alert("frontend", 55)])
    assert res["basis"] == "dependency-graph"
    assert res["confidence"] is not None


def test_cua_so_rong_thi_khong_bia_goc():
    res = _run([])
    assert res["root_suspect"] is None
    assert res["explanation"]


def _moi_ten_xuat_hien(res):
    """Moi service duoc nhac toi, o BAT KY danh sach nao.

    Kiem tren ca hai danh sach chu khong rieng `ranking`: mot ban ghi rac se roi vao
    `concurrent_unrelated` (vi no khong co trong do thi), nen chi kiem `ranking` la test
    van xanh du bo loc da hong.
    """
    return ([r["service"] for r in res["ranking"]]
            + [c["service"] for c in res["concurrent_unrelated"]])


def test_bo_qua_alert_tu_to_cao_cua_detector():
    """`detector-silent-rule` la detector noi ve CHINH NO, khong phai quan sat ve he thong."""
    res = _run([
        _alert("cart", 0),
        {"ts": T0 + 1, "rule_id": "detector-silent-rule", "service": "bedrock-cost-high",
         "severity": "info"},
        _alert("checkout", 30),
    ])
    assert "bedrock-cost-high" not in _moi_ten_xuat_hien(res)


def test_bo_qua_service_unknown():
    """`oom-detected` hien bao service='unknown' (TF1-116) — khong duoc thanh mot nghi pham."""
    res = _run([
        _alert("cart", 0),
        {"ts": T0 + 5, "rule_id": "oom-detected", "service": "unknown", "severity": "critical"},
        _alert("checkout", 30),
    ])
    assert "unknown" not in _moi_ten_xuat_hien(res)


def test_alert_ngoai_cua_so_khong_duoc_tinh():
    res = _run([
        _alert("cart", 0),
        _alert("email", -500),      # truoc cua so
        _alert("quote", 5000),      # sau cua so
        _alert("checkout", 30),
    ])
    ten = _moi_ten_xuat_hien(res)
    assert "email" not in ten and "quote" not in ten


def test_t_first_lay_alert_som_nhat_khong_phai_dong_dau_file():
    """File JSONL khong bao dam thu tu; t_first phai la min chu khong phai ban ghi dau tien."""
    res = _run([_alert("cart", 90), _alert("cart", 5), _alert("checkout", 40)])
    cart = next(r for r in res["ranking"] if r["service"] == "cart")
    assert cart["t_first"] == T0 + 5


# ---------------------------------------------------------------------------
# Do thi tinh commit trong repo
# ---------------------------------------------------------------------------
def test_topology_json_doc_duoc_va_khong_co_canh_qua_kafka():
    """checkout -> payment KHONG duoc nam trong `edges`.

    Do that 26/07: giet payment 367s -> ti le loi cua checkout dung nguyen 0.0000 suot
    13/13 mau, vi checkout day don vao Kafka roi tra ve ngay. Dat canh do vao do thi nhan
    qua se lam RCA ket luan sai rang payment giai thich duoc trang thai cua checkout.
    """
    graph = diagnose.load_static_topology()
    assert graph, "aiops/topology.json phai doc duoc"
    assert "payment" not in graph.get("checkout", []), \
        "canh qua Kafka khong lan loi dong bo — thuoc async_edges, khong thuoc edges"

    with open(diagnose.DEFAULT_TOPOLOGY, encoding="utf-8") as f:
        raw = json.load(f)
    assert "payment" in raw["async_edges"]["checkout"], "van phai ghi lai la quan he do co ton tai"


def test_ha_tang_quan_sat_khong_nam_trong_do_thi():
    """jaeger/prometheus/... khong duoc co canh toi service nghiep vu — day chinh la co che
    loai tuong quan o test_loai_duoc_tin_hieu_trung_hop."""
    graph = diagnose.load_static_topology()
    for infra in ("jaeger", "prometheus", "grafana", "opensearch"):
        assert infra not in graph
        for callees in graph.values():
            assert infra not in callees


# ---------------------------------------------------------------------------
# Chieu FAIL — mot test luon xanh con te hon khong co test (bai hoc PR #482)
# ---------------------------------------------------------------------------
def test_dao_canh_thi_ket_luan_phai_doi():
    """Neu do thi bi dao huong, RCA PHAI ra ket qua khac.

    Khong co test nay thi khong biet ket luan "cart la goc" den tu do thi hay chi tinh co
    trung voi thu tu thoi gian.
    """
    alerts = [_alert("frontend", 0), _alert("checkout", 10), _alert("cart", 25)]
    dung = _run(alerts, graph={"frontend": ["checkout"], "checkout": ["cart"]})
    dao = _run(alerts, graph={"cart": ["checkout"], "checkout": ["frontend"]})
    assert dung["root_suspect"] == "cart"
    assert dao["root_suspect"] == "frontend", \
        "dao canh ma ket luan khong doi nghia la do thi khong he duoc dung"


# ---------------------------------------------------------------------------
# Suy do thi tu spanmetrics — ten span TRAN sinh canh gia (su co 31/07)
# ---------------------------------------------------------------------------
def _rows(cap):
    """[(service_name, span_name), ...] -> dang Prometheus tra ve."""
    return [{"metric": {"service_name": s, "span_name": n}} for s, n in cap]


def _gia_lap_prom(monkeypatch, client, server):
    def fake(base_url, promql, timeout=10):
        return _rows(server) if "SERVER" in promql else _rows(client)
    monkeypatch.setattr(diagnose, "_prom_query", fake)


def test_ten_span_tran_khong_duoc_sinh_canh(monkeypatch):
    """Thu nho lai dung su co do tren cum 31/07.

    `POST` la span_name ma CHI `frontend-proxy` xuat hien lam SERVER, nen bo loc mo ho
    (chi bo ten ung voi >1 server) KHONG bat duoc. Ba service phat span CLIENT ten `POST`
    vi chung goi ElastiCache/RDS — nhung dich khong duoc trace. Neu noi canh theo ten do
    thi ca ba deu bi tro ve `frontend-proxy`, va `frontend-proxy` — RIA NGOAI CUNG — thanh
    "thu ma ai cung phu thuoc".
    """
    _gia_lap_prom(
        monkeypatch,
        client=[("cart", "POST"), ("checkout", "POST"), ("shipping", "POST")],
        server=[("frontend-proxy", "POST")],
    )
    graph, stats = diagnose.graph_from_spanmetrics("http://x")
    assert graph == {}, f"ten span tran khong duoc sinh canh nao, nhung ra {graph}"
    assert stats["generic_span_names"] >= 1
    assert stats["edges"] == 0


def test_ten_span_cu_the_van_sinh_canh_binh_thuong(monkeypatch):
    """Bo loc phai bo DUNG ten tran, khong duoc bo lan sang ten that.

    Thieu test nay thi mot bo loc qua tay (vi du bo moi ten bat dau bang GET/POST) se lam
    do thi rong ma khong ai biet — do thi rong thi RCA lang le tut ve xep hang theo thoi
    gian, dung kieu xuong cap am tham ma resolve_topology sinh ra de chan.
    """
    _gia_lap_prom(
        monkeypatch,
        client=[("frontend", "oteldemo.CartService/GetCart"),
                ("frontend", "GET /api/products/index")],
        server=[("cart", "oteldemo.CartService/GetCart"),
                ("product-catalog", "GET /api/products/index")],
    )
    graph, stats = diagnose.graph_from_spanmetrics("http://x")
    assert graph == {"frontend": ["cart", "product-catalog"]}
    assert stats["generic_span_names"] == 0
    assert stats["edges"] == 2


def test_hop_nhat_giu_lai_canh_chi_co_o_file_tinh(monkeypatch):
    """resolve_topology phai HOP NHAT, khong duoc de spanmetrics thay the file tinh.

    Suy luan co recall thap (do 30/07: 13/28 canh sync). Thay the = vut bo phan da kiem tay.
    """
    _gia_lap_prom(
        monkeypatch,
        client=[("frontend", "oteldemo.CartService/GetCart")],
        server=[("cart", "oteldemo.CartService/GetCart")],
    )
    graph, source, note = diagnose.resolve_topology(prom_url="http://x")
    assert source == "spanmetrics+static"
    assert "cart" in graph.get("frontend", []), "canh suy duoc phai co"
    assert "quote" in graph.get("shipping", []), \
        "canh chi co o topology.json phai duoc giu — day la cho thay the lam mat"
    assert "hop nhat" in note and "loi thoi" in note, "nguon phai tu khai, khong xuong cap am tham"


def test_goc_van_tim_duoc_khi_suy_luan_THIEU_canh():
    """Regression cua su co 31/07: giet `quote` ma RCA cham `frontend-proxy` lam goc.

    Do thi suy ra thieu `frontend-proxy -> frontend` (span CLIENT cua frontend-proxy ten
    `router frontend egress`, khong khop SERVER span_name nao) va thieu ca nhanh
    frontend -> shipping -> quote. Chi voi no thi khong ai phu thuoc vao `shipping`.
    """
    do_thi_suy = {
        "checkout": ["currency", "product-catalog"],
        "frontend": ["ad", "checkout", "currency", "product-catalog"],
        "recommendation": ["product-catalog"],
    }
    # Giu dung THU TU quan sat duoc tren cum (shipping keu truoc, frontend-proxy thu hai);
    # khoang cach thu nho lai cho vua cua so cua `_run`.
    alerts = [
        _alert("shipping", 0), _alert("frontend-proxy", 100),
        _alert("frontend", 300), _alert("checkout", 300), _alert("shopping-copilot", 350),
    ]
    chi_suy = _run(alerts, graph=do_thi_suy, source="spanmetrics")
    assert chi_suy["root_suspect"] != "shipping", \
        "neu chi-suy da ra dung roi thi test nay khong chung minh duoc gi ve hop nhat"

    gop = diagnose._hop_nhat_do_thi(do_thi_suy, diagnose.load_static_topology())
    res = _run(alerts, graph=gop, source="spanmetrics+static")
    assert res["root_suspect"] == "shipping", \
        "shipping goi thang `quote` (thu bi giet) — day la cau tra loi dung nhat co the"
    assert res["ranking"][-1]["service"] == "frontend-proxy", \
        "ria ngoai cung phai xep cuoi, khong duoc len lam goc"
