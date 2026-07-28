"""
conftest.py — fixture dung chung cho MOI test trong aiops/detector/.

Vi sao co file nay
------------------
`Alerter.flush()` ghi noi tiep moi alert da ban vao duong dan tra ve boi
`alerter._history_path()`, mac dinh la `aiops/detector/alerter_history.jsonl` —
mot file DUOC COMMIT.

`test_detector.py` da co fixture cach ly, nhung fixture autouse khai bao trong mot
module chi ap cho chinh module do. `test_alerter.py` khong co, nen no ghi thang vao
file that: chay `pytest -q` mot lan la working tree ban them 2 dong.

Khong chi la chuyen ban working tree. `alerter_history.jsonl` la EVIDENCE:
`correlate.py` doc no de dung ma tran dong-xuat-hien, va `incident_replay.py` cham
precision/recall tren no. Rac tu test lan vao se lam lech chinh nhung con so dung de
danh gia he thong.

Dat o conftest.py de moi module test trong thu muc — ke ca module viet sau nay —
deu duoc cach ly ma khong phai nho opt-in.

Ghi chu: `test_detector.py` van giu mot ban sao cung ten o cap module. Hai ban lam y
het nhau (cung set mot bien moi truong) nen vo hai; ban trong module chi che ban o day
cho rieng module do. Xoa ban trung do la viec don dep sau, khong gap.
"""
import pytest


@pytest.fixture(autouse=True)
def _isolate_alert_history(tmp_path, monkeypatch):
    """Day lich su alert cua moi test vao file tam."""
    monkeypatch.setenv("ALERTER_HISTORY_FILE",
                       str(tmp_path / "alerter_history.jsonl"))
