#!/usr/bin/env python3
"""Chay bo `promtool test rules` cho rule burn-rate, va canh viec no bi lech khoi rules.yaml.

Vi sao co file nay: quyet dinh dung idiom min() `(A_short < A_long) or (A_long)` thay vi
`and` (nhu PR #318 de xuat) dua tren mot tinh chat cua PromQL — `and` tra ve chuoi RONG khi
chua vuot nguong, min() thi khong. Tinh chat do quyet dinh `expect_series` dat duoc hay
khong, tuc quyet dinh co che `detector-silent-rule` con phan biet duoc "rule mu" voi "he
khoe" hay khong.

Do la mot khang dinh ve hanh vi, nen phai co phep do chu khong phai mot cau trong comment.
`promql_tests/burn_rate_test.yml` do no bang chinh parser cua Prometheus.
"""
import os
import shutil
import subprocess

import pytest
import yaml

_HERE = os.path.dirname(os.path.abspath(__file__))
_RULES = os.path.join(_HERE, "rules.yaml")
_PROMQL_TEST = os.path.join(_HERE, "promql_tests", "burn_rate_test.yml")


def test_promtool_burn_rate_semantics():
    """min() bao so khi he khoe; `and` im lang. Do bang parser that cua Prometheus."""
    promtool = shutil.which("promtool")
    if not promtool:
        pytest.skip("khong co promtool tren may — CI cai o aiops-ci.yaml")

    proc = subprocess.run(
        [promtool, "test", "rules", _PROMQL_TEST],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, (
        "promtool test rules that bai:\n" + (proc.stdout + proc.stderr).strip()
    )


def test_burn_rate_test_khong_lech_khoi_rules_yaml():
    """Bieu thuc trong file test phai la BAN SAO NGUYEN VAN cua query dang ship.

    Khong co rang buoc nay thi sua rules.yaml ma quen sua file test se de lai mot bo test
    van xanh nhung dang do MOT QUERY KHAC — dung lop loi "trong nhu dang kiem tra nhung
    thuc ra khong" ma ca dot MANDATE-15 di tim.
    """
    with open(_RULES, encoding="utf-8") as fh:
        rules = yaml.safe_load(fh)
    with open(_PROMQL_TEST, encoding="utf-8") as fh:
        promql_test = yaml.safe_load(fh)

    shipped = {r["id"]: r.get("query") for r in rules["rules"]}
    assert "error-budget-burn-fast-standard" in shipped, (
        "rule error-budget-burn-fast-standard da bi doi ten/xoa — cap nhat file test kem theo"
    )

    # Ca 1, bieu thuc dau tien = nhanh min() dang ship.
    duoi_test = promql_test["tests"][0]["promql_expr_test"][0]["expr"]
    assert duoi_test.strip() == shipped["error-budget-burn-fast-standard"].strip(), (
        "promql_tests/burn_rate_test.yml da lech khoi rules.yaml — sua mot ben thi phai sua ben kia"
    )


def test_burn_rate_dung_min_idiom_khong_dung_and():
    """Chan viec ai do 'don dep' 4 rule burn-rate sang `and` ma khong doc ly do.

    `and` khong sai ve dieu kien fire — no sai o cho lam rule im lang trong he khoe, nen
    `expect_series: true` mat nghia. Neu that su muon doi thi phai doi ca `expect_series`
    va cap nhat file test nay cung luc, chu khong doi mot minh query.
    """
    with open(_RULES, encoding="utf-8") as fh:
        rules = yaml.safe_load(fh)

    burn_rules = [r for r in rules["rules"] if r["id"].startswith("error-budget-burn-")]
    assert burn_rules, "khong con rule burn-rate nao — neu co y bo thi xoa ca test nay"

    for rule in burn_rules:
        # Chuan hoa khoang trang truoc khi kiem cau truc: YAML `>-` GOP cac dong o muc thut
        # goc nhung GIU nguyen xuong dong o cac dong thut sau hon. Nen `or` (thut goc) nam
        # giua hai dau cach con `<` (thut sau) nam giua hai dau xuong dong — kiem tho tren
        # chuoi goc se cho ket qua khac nhau giua hai toan tu chi vi cach trinh bay.
        query = " ".join(rule["query"].split())
        # Kiem `<` chu KHONG chi kiem `or`. Tu 30/07 tu so co them `or <mau so> * 0` (sua loi
        # mu theo service), nen `" or " in query` da tu dung duoc cho ca query BO HAN phep so
        # sanh min() — tuc phep kiem cu tro thanh luon xanh. Phep so sanh moi la thu dac hieu
        # cho idiom `(A_short < A_long) or (A_long)`.
        assert " < " in query, (
            f"{rule['id']}: mat phep so sanh cua idiom min() `(A_short < A_long) or (A_long)` "
            "— rule chi con nhin MOT cua so. Xem promql_tests/burn_rate_test.yml truoc khi doi."
        )
        assert " or " in query, (
            f"{rule['id']}: mat nhanh du phong `or (A_long)` cua idiom min(). "
            "Xem promql_tests/burn_rate_test.yml truoc khi doi."
        )
        assert " and " not in query, (
            f"{rule['id']}: dung `and` — rule se im lang trong he khoe, lam "
            "`detector-silent-rule` khong phan biet duoc rule mu voi he khoe."
        )
        # Tu so phai co mac dinh 0, khong thi rule mu voi service chua tung loi (do that
        # 30/07: 15 service co traffic, rule chi sinh 5 series).
        assert query.count("* 0") == 3, (
            f"{rule['id']}: tu so thieu mac dinh `or <mau so> * 0`. Phai co du 3 cho "
            "(cua so ngan, cua so dai trong phep so sanh, va cua so dai o nhanh `or`) — "
            f"dang co {query.count('* 0')}. Thieu o cua so NGAN thi sinh bao gia khi loi da tanh."
        )
