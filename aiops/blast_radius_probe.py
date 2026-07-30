#!/usr/bin/env python3
"""blast_radius_probe.py — service nao roi vao DAI ma freeze thuc su co y nghia?

VI SAO CAN CAI NAY. Kich ban MANDATE-28 bom su co bang `kubectl scale --replicas=0`,
tuc ti le loi cua nan nhan len ~1.0. Nhung `service-error-rate-high` co TANG TINH:

    detector.py:224 —  static_fired = value > threshold      # so thang voi hang so

Tang tinh KHONG doc `metric_history` nen no khong bao gio troi. Ti le 1.0 >> nguong 0.10
thi no keu moi chu ky, va yeu cau 1 cua mandate ("bao lien tuc, khong khoang cam") se PASS
DU FREEZE CO HOAT DONG HAY KHONG. Mot ca kiem luon xanh — dung lop loi ma PR #513 vua sua o
yeu cau 3, chi khac cho.

Freeze chi co y nghia trong mot DAI HEP:

    duoi:  dynamic_min_fraction * threshold   -> duoi do tang 3-sigma bi cong SLO chan
    tren:  threshold                          -> tren do tang TINH ganh, baseline vo can

Voi cau hinh hien tai la [0.05, 0.10). Bang chung offline co y dung 0.08 chinh vi vay.

Script nay bom mot su co roi DO ti le loi cua MOI service, de tra loi: co service nao roi
vao dai do khong. Neu co thi ta co cho chung minh freeze THAT tren cum. Neu khong thi phai
noi thang trong ticket rang freeze chi chung minh duoc offline — chu dung nop mot lan chay
PASS ma khong biet no pass nho cai gi.

KHONG HARDCODE NGUONG. Ca cong thuc ti le loi lan hai nguong deu doc tu `rules.yaml`, nen
probe khong the lech khoi rule that.

CHI STDLIB (+ pyyaml de doc rules.yaml) — cung rang buoc voi incident_replay.py.

Dung:
    python aiops/blast_radius_probe.py --prom-url http://localhost:9090 --target quote
    python aiops/blast_radius_probe.py --prom-url ... --target quote --dry-run   # chi in lenh

AN TOAN: lenh khoi phuc chay trong `finally`, va in ra man hinh ngay tu dau de neu tien
trinh bi giet thi nguoi van copy duoc.
"""
import argparse
import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request

_HERE = os.path.dirname(os.path.abspath(__file__))
_RULES = os.path.join(_HERE, "detector", "rules.yaml")
_RULE_ID = "service-error-rate-high"


def doc_rule(duong_dan, rule_id):
    """Lay query + hai nguong tu chinh rule dang ship."""
    import yaml
    with open(duong_dan, encoding="utf-8") as fh:
        doc = yaml.safe_load(fh)
    for r in doc["rules"]:
        if r["id"] == rule_id:
            return r
    raise SystemExit(f"khong tim thay rule `{rule_id}` trong {duong_dan}")


def truy_van(prom_url, promql, timeout=30):
    url = prom_url.rstrip("/") + "/api/v1/query?" + urllib.parse.urlencode({"query": promql})
    with urllib.request.urlopen(url, timeout=timeout) as r:
        d = json.load(r)
    if d.get("status") != "success":
        raise RuntimeError(f"Prometheus tra loi: {d.get('error')}")
    out = {}
    for s in d["data"]["result"]:
        ten = s["metric"].get("service_name")
        if ten:
            out[ten] = float(s["value"][1])
    return out


def service_co_baseline(prom_url, rule, cua_so="1h"):
    """Service nao CO chuoi tu so (tuc co baseline), service nao KHONG.

    Vi sao phai hoi cau nay. `service-error-rate-high` chia tu so cho mau so ma KHONG
    co mac dinh 0 — giong het loi da sua o 4 rule burn-rate (PR #509). Service chua tung
    phat ra mot span loi nao thi chuoi TU SO khong ton tai, nen:

        khong co chuoi  ->  vong `for value, labels in series` bo qua no
                        ->  `metric_history` khong bao gio co muc cho no
                        ->  KHONG CO BASELINE

    Hau qua nang hon la chi "khong bao cao so 0". Khi su co bat dau o muc duoi nguong SLO,
    chuoi moi xuat hien va history bat dau tich luy TU CHINH GIA TRI SU CO:

        5 mau dau ~ 0.08  ->  mean ~ 0.08, std ~ 0  ->  mean+3sigma ~ 0.08
        value 0.08 > 0.08 ?  KHONG   ->  tang dong khong keu
        value 0.08 > 0.10 ?  KHONG   ->  tang tinh khong keu
        =>  su co KHONG BAO GIO duoc phat hien

    Va freeze khong cuu duoc, vi khong co baseline lanh nao de dong bang — baseline CHINH LA
    su co. Nen voi nhung service nay, cau hoi "co roi vao dai freeze khong" con chua dung
    van de: chung chua co cai de freeze.
    """
    tu_so = (f'sum by (service_name) (rate(traces_span_metrics_calls_total{{'
             f'status_code="STATUS_CODE_ERROR", span_name!="grpc.health.v1.Health/Check", '
             f'span_kind=~"SPAN_KIND_SERVER|SPAN_KIND_CONSUMER"}}[{cua_so}]))')
    mau_so = (f'sum by (service_name) (rate(traces_span_metrics_calls_total{{'
              f'span_name!="grpc.health.v1.Health/Check", '
              f'span_kind=~"SPAN_KIND_SERVER|SPAN_KIND_CONSUMER"}}[{cua_so}])) > 0')
    co = set(truy_van(prom_url, tu_so))
    co_traffic = set(truy_van(prom_url, mau_so))
    return co_traffic, co


def chay(lenh, dry_run=False):
    print(f"  $ {lenh}", flush=True)
    if dry_run:
        return
    p = subprocess.run(lenh, shell=True, capture_output=True, text=True)
    if p.returncode != 0:
        print(f"    LOI: {(p.stderr or p.stdout).strip()[:200]}", flush=True)
    elif p.stdout.strip():
        print(f"    {p.stdout.strip()[:120]}", flush=True)


def phan_loai(ti_le, nguong, san_duoi):
    """Ti le nay roi vao dai nao — theo dung hai nguong cua rule."""
    if ti_le >= nguong:
        return "TANG TINH ganh — freeze VO CAN"
    if ti_le >= san_duoi:
        return "*** DAI FREEZE ***"
    if ti_le > 0:
        return "duoi cong SLO — khong keu"
    return "khong anh huong"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--prom-url", required=True)
    ap.add_argument("--target", required=True,
                    help="ten deployment bi giet, vd: quote")
    ap.add_argument("--namespace", default="techx-tf1")
    ap.add_argument("--context", default=None, help="kubectl context (bo qua = context hien tai)")
    ap.add_argument("--restore-replicas", type=int, default=2,
                    help="scale ve bao nhieu khi xong (mac dinh 2 = minReplicas cua HPA)")
    ap.add_argument("--baseline-seconds", type=int, default=120)
    ap.add_argument("--duration-seconds", type=int, default=360,
                    help="mac dinh 360: cua so rate() la 5m nen phai bom >= 300s thi ti le "
                         "moi bao hoa; ngan hon la doc duoc so THAP hon thuc te")
    ap.add_argument("--recovery-seconds", type=int, default=120)
    ap.add_argument("--interval-seconds", type=int, default=30)
    ap.add_argument("--rules", default=_RULES)
    ap.add_argument("--out", default=None, help="ghi so do tho ra JSON")
    ap.add_argument("--dry-run", action="store_true", help="chi in lenh, khong bom")
    args = ap.parse_args(argv)

    rule = doc_rule(args.rules, _RULE_ID)
    nguong = float(rule["threshold"])
    ty_le_cong = rule.get("dynamic_min_fraction")
    san_duoi = nguong * float(ty_le_cong) if ty_le_cong is not None else 0.0

    ctx = f"--context {args.context} " if args.context else ""
    lenh_tat = f"kubectl {ctx}-n {args.namespace} scale deploy/{args.target} --replicas=0"
    lenh_bat = (f"kubectl {ctx}-n {args.namespace} scale deploy/{args.target} "
                f"--replicas={args.restore_replicas}")

    print("=" * 78)
    print(f"BLAST RADIUS PROBE — giet `{args.target}` roi do ti le loi cua MOI service")
    print("=" * 78)
    print(f"  rule doc tu   : {args.rules} -> {_RULE_ID}")
    print(f"  nguong tinh   : {nguong}")
    print(f"  cong SLO      : dynamic_min_fraction={ty_le_cong} -> san duoi {san_duoi:.4f}")
    print(f"  DAI FREEZE    : [{san_duoi:.4f}, {nguong:.4f})  <- dai duy nhat freeze co y nghia")
    print(f"  lich          : nen {args.baseline_seconds}s -> bom {args.duration_seconds}s "
          f"-> hoi phuc {args.recovery_seconds}s, lay mau moi {args.interval_seconds}s")
    print()
    print("  LENH CUU HO — chay cai nay neu tien trinh chet giua chung:")
    print(f"    {lenh_bat}")
    print("=" * 78)
    print(flush=True)

    # --- Kiem baseline TRUOC khi bom: service nao co chuoi tu so, service nao khong ---
    try:
        co_traffic, co_baseline = service_co_baseline(args.prom_url, rule)
    except Exception as e:
        print(f"  (khong kiem duoc baseline: {e})\n", flush=True)
        co_traffic, co_baseline = set(), set()

    if co_traffic:
        thieu = sorted(co_traffic - co_baseline)
        print(f"KIEM BASELINE (truoc khi bom) — {len(co_baseline)}/{len(co_traffic)} "
              f"service co traffic CO chuoi tu so")
        if thieu:
            print(f"  {len(thieu)} service KHONG co baseline loi:")
            print("    " + "  ".join(thieu))
            print("  -> voi nhung service nay, mot su co DUOI nguong SLO se khong bao gio")
            print("     duoc phat hien: baseline bat dau tu chinh gia tri su co nen tang dong")
            print("     khong the keu, con tang tinh thi chua toi nguong. Freeze cung vo nghia")
            print("     vi khong co baseline lanh nao de dong bang.")
            print("  -> nguyen nhan: `service-error-rate-high` thieu mac dinh 0 o tu so,")
            print("     dung loi da sua cho 4 rule burn-rate o PR #509.")
        else:
            print("  moi service co traffic deu co baseline — tot")
        print("=" * 78)
        print(flush=True)

    mau = []

    def lay_mau(nhan):
        try:
            ti_le = truy_van(args.prom_url, rule["query"])
        except Exception as e:
            print(f"  [{nhan}] LOI truy van: {e}", flush=True)
            return
        mau.append({"nhan": nhan, "ts": time.time(), "ti_le": ti_le})
        noi_bat = {k: v for k, v in ti_le.items() if v > 0}
        if noi_bat:
            gon = "  ".join(f"{k}={v:.4f}" for k, v in
                            sorted(noi_bat.items(), key=lambda kv: -kv[1])[:6])
        else:
            gon = "(moi service deu 0)"
        print(f"  [{nhan:>16s}] {gon}", flush=True)

    def cho(giay, ten_pha):
        het = time.time() + giay
        i = 0
        while time.time() < het:
            lay_mau(f"{ten_pha}+{i * args.interval_seconds}s")
            i += 1
            con = het - time.time()
            if con > 0:
                time.sleep(min(args.interval_seconds, con))

    print("--- PHA 1: NEN (chua bom) ---", flush=True)
    cho(args.baseline_seconds, "nen")

    nhan_pha2 = f"PHA 2: BOM (giet {args.target})"
    if args.dry_run:
        nhan_pha2 += "  — DRY-RUN: chi IN lenh, KHONG chay. Moi so duoi day se la 0."
    print(f"\n--- {nhan_pha2} ---", flush=True)
    chay(lenh_tat, args.dry_run)
    try:
        cho(args.duration_seconds, "bom")
    finally:
        print(f"\n--- PHA 3: KHOI PHUC ---", flush=True)
        chay(lenh_bat, args.dry_run)

    cho(args.recovery_seconds, "hoi phuc")

    # ---------------- tong ket ----------------
    trong_luc_bom = [m for m in mau if m["nhan"].startswith("bom")]
    # Bo nua dau pha bom: cua so rate() la 5m nen nhung mau dau chua bao hoa, doc chung
    # se ra ti le THAP hon thuc te va lam service bi xep nham dai.
    bao_hoa = trong_luc_bom[len(trong_luc_bom) // 2:] or trong_luc_bom

    dinh = {}
    for m in bao_hoa:
        for svc, v in m["ti_le"].items():
            dinh[svc] = max(dinh.get(svc, 0.0), v)

    print("\n" + "=" * 78)
    if args.dry_run:
        print("TONG KET — DRY-RUN, KHONG BOM. Bang duoi chi la trang thai he luc chay.")
    else:
        print("TONG KET — ti le loi CAO NHAT cua tung service trong nua sau pha bom")
        print(f"  (bo {len(trong_luc_bom) - len(bao_hoa)} mau dau vi cua so rate 5m chua bao hoa)")
    print("=" * 78)
    if not dinh:
        print("  (khong doc duoc mau nao)")
    trong_dai = []
    for svc, v in sorted(dinh.items(), key=lambda kv: -kv[1]):
        loai = phan_loai(v, nguong, san_duoi)
        print(f"  {svc:22s} {v:8.4f}   {loai}")
        if san_duoi <= v < nguong:
            trong_dai.append((svc, v))

    print("\n" + "-" * 78)
    if args.dry_run:
        # KHONG duoc ket luan gi o che do dry-run. Khong bom thi moi service deu 0, va cau
        # "khong service nao roi vao dai freeze" se dung ve chu nghia nhung SAI ve y nghia —
        # no den tu cho chua do, khong phai tu cho do duoc ket qua am tinh.
        #
        # Loi that, gap ngay lan chay dau 30/07: nguoi dung chay --dry-run, doc 20 mau toan 0
        # roi thay mot ket luan trong rat chac chan. Dung lop loi ma ca dot MANDATE-15/26/28
        # di tim — mot phep do luon cho ra cung mot cau tra loi.
        print("DRY-RUN — KHONG co ket luan nao o day.")
        print("  Khong co lenh bom nao duoc chay, nen moi so 0 phia tren chi noi rang he dang")
        print("  khoe, KHONG noi gi ve viec giet `" + args.target + "` thi chuyen gi xay ra.")
        print("  Bo `--dry-run` de do that.")
    elif trong_dai:
        print(f"CO {len(trong_dai)} SERVICE ROI VAO DAI FREEZE [{san_duoi:.4f}, {nguong:.4f}):")
        for svc, v in trong_dai:
            print(f"    {svc}  ({v:.4f})")
        print("  -> dung service nay lam nan nhan cho kich ban sustained thi freeze MOI")
        print("     thuc su duoc kiem. Cap nhat `service` cua su kien tuong ung.")
    else:
        print(f"KHONG service nao roi vao dai [{san_duoi:.4f}, {nguong:.4f}).")
        print("  -> voi diem bom nay, kich ban KHONG chung minh duoc freeze: tang tinh se")
        print("     ganh het va yeu cau 1 pass ma khong noi len dieu gi ve baseline.")
        print("  -> hoac thu diem bom khac, hoac ghi thang vao ticket rang freeze chi")
        print("     chung minh duoc offline (gioi han cua co che bom ma TF duoc phep dung).")
    print("-" * 78)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump({"target": args.target, "nguong": nguong, "san_duoi": san_duoi,
                       "dinh_trong_pha_bom": dinh, "mau": mau}, fh, indent=2)
        print(f"\nSo do tho: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
