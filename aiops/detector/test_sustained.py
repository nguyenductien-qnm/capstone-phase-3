"""MANDATE-28 — su co keo dai khong duoc bien thanh "binh thuong moi".

Moi fixture chay qua CHINH `eval_metric_rule` that, khong mock logic ben trong.

So do dong vai tro dong co cua ca file nay, do tren detector TRUOC khi co freeze: mot su co
40 phut o muc 0.08 (duoi nguong tinh 0.10 nen chi tang 3-sigma bat duoc) chi duoc bao 9 phut
dau, roi IM LANG suot 29 phut con lai — baseline bo tu 0.0093 len 0.0805, tuc detector hoc
chinh cai loi thanh binh thuong. Xem ADR-019.

Run:
    pytest aiops/detector/test_sustained.py -v
"""
import random

from unittest.mock import MagicMock

import detector


RULE = {
    "id": "service-error-rate-high", "type": "metric", "query": "q", "op": "gt",
    "threshold": 0.10, "summary": "s", "summary_dynamic": "sd", "severity": "critical",
    "dynamic_min_fraction": 0.50,
}
KEY = "service-error-rate-high:checkout"

# 0.08 nam DUOI nguong tinh 0.10 -> chi tang 3-sigma bat duoc. Chon co y: neu de tren nguong
# thi tang tinh keu suot va bai test khong he kiem duoc freeze.
SUB_SLO = 0.08
BASELINE = 0.010


def _feed(values, service="checkout", prom=None, rule=None):
    """Bom lan luot tung gia tri, tra ve list bool 'chu ky nay co keu khong'."""
    prom = prom or MagicMock()
    rule = rule or RULE
    out = []
    for v in values:
        prom.query.return_value = [(v, {"service_name": service})]
        out.append(bool(detector.eval_metric_rule(rule, prom)))
    return out


def _noisy(level, n, seed=7, jitter=0.004):
    rnd = random.Random(seed)
    return [level + rnd.uniform(-jitter, jitter) for _ in range(n)]


def _baseline_mean():
    h = detector.metric_history.get(KEY, [])
    return sum(h) / len(h) if h else 0.0


# ---------------------------------------------------------------------------
# Yeu cau 1 — bao lien tuc suot su co dai
# ---------------------------------------------------------------------------
def test_su_co_dai_duoi_nguong_slo_bao_xuyen_suot():
    """Day la ca that su tung FAIL. 80 chu ky = 40 phut @ poll 30s."""
    detector.reset_state()
    fired = _feed(_noisy(BASELINE, 20) + _noisy(SUB_SLO, 80, seed=3))
    trong_su_co = fired[20:]
    assert all(trong_su_co), (
        f"co khoang cam: chi {sum(trong_su_co)}/{len(trong_su_co)} chu ky keu. "
        "Truoc khi co freeze con so nay la 18/80."
    )


def test_baseline_dung_yen_suot_su_co():
    """Bang chung truc tiep cho 'khong hoc cai loi thanh binh thuong'."""
    detector.reset_state()
    _feed(_noisy(BASELINE, 20))
    truoc = _baseline_mean()
    _feed(_noisy(SUB_SLO, 80, seed=3))
    sau = _baseline_mean()
    assert abs(sau - truoc) < 1e-9, f"baseline da troi {truoc:.4f} -> {sau:.4f} trong su co"
    assert sau < 0.02, "baseline phai con o muc binh thuong (~0.01), khong phai muc su co"


# ---------------------------------------------------------------------------
# Yeu cau 1b — het su co thi phai thaw, khong ket freeze
# ---------------------------------------------------------------------------
def test_hoi_phuc_thi_dong_su_co_va_baseline_hoc_lai():
    detector.reset_state()
    _feed(_noisy(BASELINE, 20) + _noisy(SUB_SLO, 30, seed=3))
    assert KEY in detector.incident_state, "su co phai dang mo"

    _feed(_noisy(BASELINE, detector.RECOVERY_CYCLES, seed=5))
    assert KEY not in detector.incident_state, "im lang du RECOVERY_CYCLES thi phai dong su co"

    truoc = _baseline_mean()
    _feed(_noisy(BASELINE, 10, seed=9))
    assert _baseline_mean() != truoc, "dong su co roi thi baseline phai hoc tiep"


def test_mot_nhip_im_lang_khong_dong_su_co_som():
    """RECOVERY_CYCLES > 1 de dao dong khong lam su co dong roi mo lai ngay (flapping)."""
    detector.reset_state()
    _feed(_noisy(BASELINE, 20) + _noisy(SUB_SLO, 20, seed=3))
    _feed([BASELINE])                      # dung MOT chu ky im lang
    assert KEY in detector.incident_state, "mot nhip im lang khong duoc dong su co"
    assert detector.incident_state[KEY]["recovered_streak"] == 1


# ---------------------------------------------------------------------------
# Yeu cau 2 — khong bao gia vi tai hop le doi
# ---------------------------------------------------------------------------
def test_tai_hop_le_dao_dong_khong_mo_su_co():
    detector.reset_state()
    fired = _feed(_noisy(BASELINE, 100, seed=13, jitter=0.003))
    assert not any(fired[5:]), "tai binh thuong dao dong khong duoc keu"
    assert not detector.incident_state


def test_muc_dich_vinh_vien_thi_cuoi_cung_phai_hoc_lai_VA_NOI_RA(monkeypatch):
    """Neu muc moi la binh thuong THAT thi freeze vinh vien se bao mai mai.

    Tran MAX_FREEZE_CYCLES la ranh giua yeu cau 1 va yeu cau 2 — va alert
    `baseline-rebaselined` la thu lam cai ranh do nhin thay duoc.

    Ha tran xuong 30 de bai test chay trong tich tac. KHONG doc
    `detector.MAX_FREEZE_CYCLES` roi cho chay theo no: lam vay thi ai do dat tran thanh vo
    cung se lam bai test TREO thay vi do — da dinh dung cai bay do mot lan.
    Tran that duoc canh rieng o test_tran_freeze_phai_huu_han_va_hop_ly.
    """
    monkeypatch.setattr(detector, "MAX_FREEZE_CYCLES", 30)
    detector.reset_state()
    _feed(_noisy(BASELINE, 20))
    _feed(_noisy(SUB_SLO, 32, seed=3))

    assert detector.pending_rebaselines, "cham tran thi PHAI ghi lai de co alert"
    key, cycles = detector.pending_rebaselines[0]
    assert key == KEY and cycles > 30

    truoc = _baseline_mean()
    _feed(_noisy(SUB_SLO, 10, seed=4))
    assert _baseline_mean() > truoc, "sau khi rebaseline thi baseline phai hoc muc moi"


def test_tran_freeze_phai_huu_han_va_hop_ly():
    """Canh rieng gia tri ship, vi bai test tren da monkeypatch no di.

    Vo cung = freeze vinh vien = pha yeu cau 2 cua mandate (bao gia khi muc binh thuong
    dich). Qua nho = thaw giua su co = pha yeu cau 1. Dai [1h, 6h] @ poll 30s.
    """
    assert 120 <= detector.MAX_FREEZE_CYCLES <= 720, \
        f"MAX_FREEZE_CYCLES={detector.MAX_FREEZE_CYCLES} nam ngoai dai hop ly [1h, 6h]"
    assert 2 <= detector.RECOVERY_CYCLES <= 10, \
        "RECOVERY_CYCLES=1 thi mot nhip dao dong dong su co ngay; qua lon thi cham dong"


def test_hai_hang_so_tune_duoc_luc_chay():
    """Default arg bind luc DINH NGHIA ham, nen doc hang so phai o trong than ham.

    Neu khong thi `detector.MAX_FREEZE_CYCLES = ...` khong co tac dung nao — hai hang so
    trong nhu tune duoc ma thuc ra khong. Da dinh dung loi nay mot lan.
    """
    detector.reset_state()
    for _ in range(5):
        detector._incident_gate("r:s", True, max_freeze_cycles=3)
    assert detector.pending_rebaselines, "tham so truyen vao phai duoc dung that"


def test_chua_cham_tran_thi_khong_rebaseline():
    detector.reset_state()
    _feed(_noisy(BASELINE, 20) + _noisy(SUB_SLO, 30, seed=3))
    assert not detector.pending_rebaselines


# ---------------------------------------------------------------------------
# Yeu cau 3 — su co thu 2 no chong, phai tach rieng
# ---------------------------------------------------------------------------
def test_su_co_chong_duoc_tach_rieng():
    detector.reset_state()
    prom = MagicMock()
    ket_qua = []
    for i in range(70):
        cart = BASELINE if i < 15 else 0.30
        pay = BASELINE if i < 45 else 0.35
        prom.query.return_value = [(cart, {"service_name": "cart"}),
                                   (pay, {"service_name": "payment"})]
        ket_qua.append(sorted(k.split(":")[1] for k, _, _ in detector.eval_metric_rule(RULE, prom)))

    assert ket_qua[44] == ["cart"], "truoc khi su co 2 no, chi cart keu"
    assert ket_qua[46] == ["cart", "payment"], "su co 2 phai duoc bat DU su co 1 chua dut"
    assert all(k in detector.incident_state for k in
               ("service-error-rate-high:cart", "service-error-rate-high:payment"))
    assert detector.metric_history["service-error-rate-high:payment"], \
        "lich su cua payment phai rieng, khong bi cart lam ban"


def test_su_co_dai_o_service_nay_khong_dong_bang_service_khac():
    """Freeze phai theo tung `rule x service`, khong phai theo rule."""
    detector.reset_state()
    prom = MagicMock()
    for i in range(60):
        prom.query.return_value = [(0.30 if i >= 10 else BASELINE, {"service_name": "cart"}),
                                   (BASELINE, {"service_name": "quote"})]
        detector.eval_metric_rule(RULE, prom)

    assert "service-error-rate-high:cart" in detector.incident_state
    assert "service-error-rate-high:quote" not in detector.incident_state
    assert len(detector.metric_history["service-error-rate-high:quote"]) == 30, \
        "quote khoe manh thi lich su cua no phai chay tiep binh thuong"


# ---------------------------------------------------------------------------
# Winsorize con viec khong — neu khong thi phai go, khong giu lai cho dep
# ---------------------------------------------------------------------------
def test_winsorize_van_con_viec_sau_khi_co_freeze():
    """Ca duy nhat winsorize con phuc vu: vuot 3-sigma nhung bi CONG SLO chan.

    Gia tri 0.03 voi threshold 0.10 va dynamic_min_fraction 0.50 -> cong doi >= 0.05 nen
    KHONG keu -> khong mo su co -> khong freeze -> van append. Winsorize la thu ghim no lai.
    Neu mot ngay ca nay bien mat thi winsorize thanh code chet va phai bi go.
    """
    detector.reset_state()
    _feed(_noisy(BASELINE, 20))
    assert KEY not in detector.incident_state

    truoc = detector.metric_history[KEY][-1]
    fired = _feed([0.03])
    assert not fired[0], "0.03 phai bi cong SLO chan (0.50 x 0.10 = 0.05)"
    assert KEY not in detector.incident_state, "khong keu thi khong duoc mo su co"

    vua_them = detector.metric_history[KEY][-1]
    assert vua_them < 0.03, "winsorize phai kep gia tri lai truoc khi append"
    assert vua_them > truoc, "nhung van phai nhich len, khong bi bo qua"


# ---------------------------------------------------------------------------
# Khong pha hanh vi cu
# ---------------------------------------------------------------------------
def test_rule_tat_tang_dong_khong_bi_freeze_dung_toi():
    """`dynamic_enabled: false` khong co baseline nen khong co gi de dong bang."""
    detector.reset_state()
    rule = dict(RULE, id="service-traffic-collapse", op="lt", threshold=0.2,
                dynamic_enabled=False)
    prom = MagicMock()
    for v in (0.05, 0.05, 0.05):
        prom.query.return_value = [(v, {"service_name": "cart"})]
        assert detector.eval_metric_rule(rule, prom), "tang tinh van phai keu"
    assert not detector.incident_state
    assert not detector.metric_history


def test_reset_state_xoa_ca_state_moi():
    detector.reset_state()
    _feed(_noisy(BASELINE, 20) + _noisy(SUB_SLO, 5, seed=3))
    assert detector.incident_state
    detector.reset_state()
    assert not detector.incident_state and not detector.pending_rebaselines
