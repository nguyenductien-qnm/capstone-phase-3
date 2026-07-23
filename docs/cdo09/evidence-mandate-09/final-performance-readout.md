# Mandate 09: Final Performance Readout & Zero-Downtime Verification

## 👥 Metadata
* **Assignee:** Mai Phước Khoa
* **Reviewer:** Hưng Nguyễn Đỗ Khánh
* **Collaborators:** Lê Hưng, Nguyễn Duy Nghĩa
* **Due Date:** 18/07/2026
* **Status:** 🟢 **ALL MANDATE REQUIREMENTS PASSED**

---

## 📊 1. Bảng Tổng Hợp Kết Quả & Trạng Thái (Zero-Downtime Claim Verification)

Tổng số lượng lỗi (Error Count) ghi nhận trên toàn bộ các cửa sổ chạy tải/thực thi thao tác là **0 (Error Rate = 0.00%)**.

| Yêu cầu Mandate / Thao tác | Môi trường | Traffic & Quy mô tải | Kết quả (Error Rate / Latency) | Trạng thái | Bằng chứng chính (Evidence Link) |
| :--- | :--- | :--- | :--- | :---: | :--- |
| **Credential Rotation** <br>(Xoay vòng mật khẩu RDS Proxy + ESO) | Develop / Sandbox | 200 Locust Users | 🟢 0% error rate <br>Latency <20ms <br>Postgres connection pool ~10-15 | **PASS** | [mandate09_zero_downtime_impact_report.md](file:///d:/GitHub/capstone-phase-3/docs/mandate09_zero_downtime_impact_report.md) |
| **DB Failover (TBD1)** <br>(Retry & Connection Pool) | Production (`techx-tf1`) | Continuous Curl loop | 🟢 0% error rate <br>Tải chạy liên tục qua Grafana | **PASS** | [mandate-09-evidence.md #TBD1](file:///d:/GitHub/capstone-phase-3/docs/cdo09/evidence-mandate-09/mandate-09-evidence.md#2-evidence-tbd1-retrypool-chiu-db-blip) <br>Log: [tbd1-drill-log.txt](file:///d:/GitHub/capstone-phase-3/docs/cdo09/evidence-mandate-09/logs/tbd1-drill-log.txt) |
| **Online Schema Migration (TBD2)** <br>(Expand-Contract Pattern) | Production (`techx-tf1`) | Continuous Browse/Cart/Checkout | 🟢 0% error rate <br>Backfill thành công <br>Dual-read hoàn tất | **PASS** | [mandate-09-evidence.md #TBD2](file:///d:/GitHub/capstone-phase-3/docs/cdo09/evidence-mandate-09/mandate-09-evidence.md#3-evidence-tbd2-online-schema-migration-expand-contract) <br>Log: [tbd2-test-log.txt](file:///d:/GitHub/capstone-phase-3/docs/cdo09/evidence-mandate-09/logs/tbd2-test-log.txt) |
| **RDS Major Version Upgrade (TBD3)** <br>(PostgreSQL 16.14 -> 17.10) | Production (`techx-tf1`) | Continuous Curl loop | 🟢 0% error rate <br>Switchover thông suốt <br>Cleanup Blue cũ thành công | **PASS** | [mandate-09-evidence.md #TBD3](file:///d:/GitHub/capstone-phase-3/docs/cdo09/evidence-mandate-09/mandate-09-evidence.md#4-evidence-tbd3-postgresql-major-upgrade-bang-rds-bluegreen) <br>Log: [tbd3-bg-log.txt](file:///d:/GitHub/capstone-phase-3/docs/cdo09/evidence-mandate-09/logs/tbd3-bg-log.txt) |
| **Static Parameter Change (TBD4)** <br>(Multi-AZ Reboot/Failover) | Production (`techx-tf1`) | Continuous Curl loop | 🟢 0% error rate <br>Reboot -force-failover <br>SQL SHOW verify `8kB` | **PASS** | [mandate-09-evidence.md #TBD4](file:///d:/GitHub/capstone-phase-3/docs/cdo09/evidence-mandate-09/mandate-09-evidence.md#5-evidence-tbd4-static-parameter--multi-az-failover) <br>Log: [tbd4-param-log.txt](file:///d:/GitHub/capstone-phase-3/docs/cdo09/evidence-mandate-09/logs/tbd4-param-log.txt) |
| **Security Guardrails Validation** | Develop (`techx-develop`) | Negative Resolution check | 🟢 100% Private Endpoints <br>Blocked public Ops UI (404) <br>TLS/Auth active | **PASS** | [evidence-44.md](file:///d:/GitHub/capstone-phase-3/docs/cdo09/evidence-mandate-09/evidence/evidence-44.md) |
| **Baseline Performance & Tracing** | Develop (`techx-develop`) | 10 Users (~5.14 RPS) | 🟢 0% error rate <br>Jaeger trace (53 spans) <br>Checkout Latency ~43ms | **PASS** | [evidence-46.md](file:///d:/GitHub/capstone-phase-3/docs/cdo09/evidence-mandate-09/evidence/evidence-46.md) <br>[evidence-slo-02.md](file:///d:/GitHub/capstone-phase-3/docs/cdo09/evidence-mandate-09/evidence/evidence-slo-02.md) |

---

## 📈 2. Chi Tiết Các Mốc Thử Nghiệm & Chỉ Số Đo Lường (Performance & Latency Readout)

### 2.1. Credential Rotation (Xoay mật khẩu dưới tải 200 Users)
* **Quy mô tải**: Tăng dần từ 0 lên 200 Locust Virtual Users.
* **Thời gian test**: Chạy ổn định trong suốt quá trình Lambda xoay mật khẩu và pod rollout.
* **Chỉ số đo lường**:
  - **Tỉ lệ lỗi (Error Rate)**: **`0.00%`** (0 errors).
  - **Độ trễ (Latency)**: API phản hồi ổn định `< 20ms`.
  - **Tài nguyên tiêu thụ (CPU/Memory)**: 
    - Database RAM: Giảm từ ~1GB xuống `< 100MB` (nhờ RDS Proxy Multiplexing gom kết nối thành 10-15 connections cố định).
    - Database CPU: Duy trì ổn định từ **20% - 40%**.
  - **Trạng thái HPA & Pods**: HPA tự động scale pod lên 10-12 bản sao để đáp ứng tải. Khi External Secrets Operator (ESO) cập nhật pass mới (sync interval 15s), pod rollout diễn ra an toàn nhờ Rolling Update và `preStop` hook (sleep 5s) giúp giải phóng hết connection cũ trước khi tắt.

### 2.2. DB Primary Failover (TBD1)
* **Quy mô tải**: Tải chạy liên tục (10 Users, ~5.14 RPS).
* **Chỉ số đo lường**:
  - **Tỉ lệ lỗi (Error Rate)**: **`0.00%`** (0 errors).
  - **Độ trễ (Latency)**: P95 latency ở Frontend duy trì ở mức ~92ms, hồi phục ngay sau blip.
  - **Trạng thái HPA & Pods**: Không kích hoạt HPA, chạy ổn định 1 replica trên mỗi service.
  - **Cơ chế**: Client Retry Exponential Backoff tự động retry kết nối, hấp thụ thành công DB blip.

### 2.3. Online Schema Migration (TBD2)
* **Quy mô tải**: Chạy liên tục (10 Users, ~5.14 RPS).
* **Chỉ số đo lường**:
  - **Tỉ lệ lỗi (Error Rate)**: **`0.00%`** (0 errors).
  - **Độ trễ (Latency)**: Latency của các dịch vụ chính (Browse, Cart, Checkout) không bị gián đoạn, giữ mức tốt dưới 100ms.
  - **Trạng thái HPA & Pods**: Toàn bộ pods hoạt động ổn định (1 replica), không bị ảnh hưởng bởi quá trình expand schema và backfill dữ liệu.

### 2.4. RDS Major Version Upgrade (TBD3)
* **Quy mô tải**: Tải chạy liên tục (10 Users, ~5.14 RPS).
* **Chỉ số đo lường**:
  - **Tỉ lệ lỗi (Error Rate)**: **`0.00%`** (0 errors) trong toàn bộ cửa sổ nâng cấp ~40 phút (từ PG 16.14 lên 17.10).
  - **Độ trễ (Latency)**: 100% request HTTP 200 thành công trong suốt thời gian switchover traffic sang cụm Green.
  - **Trạng thái HPA & Pods**: Pods duy trì trạng thái ready tốt, không bị gián đoạn hay crash-loop.

### 2.5. Static Parameter Change (TBD4)
* **Quy mô tải**: Tải chạy liên tục (10 Users, ~5.14 RPS).
* **Chỉ số đo lường**:
  - **Tỉ lệ lỗi (Error Rate)**: **`0.00%`** (0 errors).
  - **Độ trễ (Latency)**: Giữ vững latency bình thường ở Frontend (~92ms) và các dependency services.
  - **Trạng thái HPA & Pods**: Multi-AZ failover diễn ra thông suốt, pods tự động chuyển hướng kết nối và duy trì hoạt động bình thường.
  - **Verify parameter**: SQL `SHOW track_activity_query_size` trả về đúng `8192` (8kB) chứng tỏ tham số đã có hiệu lực.

---

## 📸 3. Liên Kết Ảnh Minh Chứng Runtime (Runtime Evidence Gallery)

Để thuận tiện cho mentor đối chiếu, dưới đây là các ảnh runtime chụp thực tế từ hệ thống:

### 3.1. Thao tác RDS Version Upgrade (TBD3)
* **AWS Console lúc tạo Green DB (chạy song song Blue):**
  ![Blue Green Creating](file:///d:/GitHub/capstone-phase-3/docs/cdo09/evidence-mandate-09/screenshots/taobluegreen.png)
* **AWS Console sau khi switchover & xóa Blue cũ:**
  ![Blue Deleted](file:///d:/GitHub/capstone-phase-3/docs/cdo09/evidence-mandate-09/screenshots/xoabluecu.png)

### 3.2. Biểu Đồ Giám Sát SLO/SLI Trong Lúc Failover
* **SLO Dashboard during TBD1 (Primary Failover):**
  ![TBD1 Grafana during primary failover](file:///d:/GitHub/capstone-phase-3/docs/cdo09/evidence-mandate-09/screenshots/m09-tbd1-01-grafana-during-primary-failover.png)
* **SLO Dashboard during TBD3 (Major PG Upgrade Switchover):**
  ![TBD3 Grafana during switchover](file:///d:/GitHub/capstone-phase-3/docs/cdo09/evidence-mandate-09/screenshots/m09-tbd3-06-grafana-during-switchover.png)
* **SLO Dashboard during TBD4 (Static Parameter Failover):**
  ![TBD4 Grafana during failover](file:///d:/GitHub/capstone-phase-3/docs/cdo09/evidence-mandate-09/screenshots/m09-tbd4-03-grafana-during-failover.png)

---

## ⚠️ 4. Gap Analysis & Rủi ro đã biết (Known Risks & Next Steps)

1. **Khác biệt cấu hình bảo mật giữa Develop và Production (Develop Gaps):**
   * **OPA Gatekeeper constraints**: Không chạy trên Develop EKS để tăng hiệu năng và tính linh hoạt cho developer.
   * **Tailscale VPN**: Develop dựa vào security group + ClusterIP không Ingress (truy cập qua port-forward) thay vì VPN để giảm thiểu tài nguyên.
   * **flagd Configuration**: Chạy offline với ConfigMap local thay vì sync từ remote server.
2. **Quản lý Terraform State đối với TBD4:**
   * Thay đổi static parameter được thao tác trực tiếp qua CLI/API kèm cờ `-RollbackOnly` để reset sau khi test, tránh làm bẩn (drift) Terraform state trên Production.
3. **Trạng thái Proxy Target trong cửa sổ Cleanup (TBD3):**
   * Ngay sau switchover, Target Group của Proxy cũ báo `UNAVAILABLE` do AWS dọn dẹp cụm Blue. Tuy nhiên, kết nối từ App qua Proxy đến DB Green mới vẫn thông suốt 100%, không bị ảnh hưởng.
