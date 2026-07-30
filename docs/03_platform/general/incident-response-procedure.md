# Quy trình Incident Response (Phản hồi sự cố) Chuẩn

**Phân loại:** Tài liệu Vận hành (Ops)
**Áp dụng:** Toàn bộ thành viên Task Force (đặc biệt CDO & AIOps)

Tài liệu này định nghĩa luồng xử lý chuẩn khi hệ thống ghi nhận sự cố ở mức độ nghiêm trọng (Alert P0/P1), đảm bảo thời gian MTTR (Mean Time To Recovery) thấp nhất và tuân thủ các nguyên tắc SRE.

---

## 1. Định nghĩa Mức độ Sự cố (Severity)

*   **P0 (Critical):** Hệ thống tê liệt hoàn toàn hoặc luồng chính (Browse, Cart, Checkout) không hoạt động. Ảnh hưởng trên diện rộng, vi phạm nghiêm trọng SLO.
*   **P1 (High):** Một thành phần quan trọng (AZ, Dependency) gặp lỗi gây suy giảm dịch vụ đáng kể nhưng hệ thống vẫn còn một phần hoạt động (degraded), hoặc có nguy cơ lây lan (bảo mật/chiếm quyền pod).

---

## 2. Luồng xử lý sự cố chuẩn P0 / P1

Khi có Alert P0/P1 phát ra từ hệ thống Monitoring (Prometheus/Grafana) hoặc từ hệ thống AIOps Detector:

### Bước 1: Ghi nhận và Phân công (Triage)
*   **Ai nhận Alert?**
    *   **CDO On-call (Người trực hệ thống):** Là người đầu tiên nhận alert (qua Slack/PagerDuty/Email).
    *   CDO On-call lập tức xác nhận (Acknowledge) alert để thông báo cho team rằng sự cố đang được xử lý (tránh nhiều người cùng dẫm chân lên nhau).
    *   CDO On-call đóng vai trò **Incident Lead (Chỉ huy sự cố)** trong suốt quá trình.

### Bước 2: Phân tích & Chẩn đoán (Investigation)
*   **Incident Lead (CDO)** kiểm tra:
    1.  Mức độ ảnh hưởng (Khách hàng có bị lỗi 5xx không? SLO đang tụt bao nhiêu?).
    2.  Khoanh vùng (Blast Radius): Lỗi hạ tầng (AZ sập), lỗi Dependency, hay pod có dấu hiệu bị chiếm quyền (Security).
*   **Ai liên lạc AIO?**
    *   Nếu alert xuất phát từ thuật toán của AIOps (EWMA/Log Clustering) hoặc nếu liên quan đến các dịch vụ AI (GenAI fallback), **Incident Lead (CDO)** sẽ trực tiếp tag/liên lạc đại diện trực ban của team **AIOps (AIO On-call)**.
    *   Team AIOps hỗ trợ xác minh xem đây là True Positive (lỗi thật) hay False Positive (cảnh báo giả do detector), và phối hợp đọc logs/traces nếu cần.

### Bước 3: Cô lập và Khôi phục (Containment & Mitigation)
*   Mục tiêu: Dừng "chảy máu" (khôi phục dịch vụ cho khách hàng trước, tìm nguyên nhân gốc sau).
*   **Hành động:**
    *   *Reliability:* Kích hoạt fallback, Circuit Breaker, hoặc failover sang AZ khác nếu 1 AZ sập.
    *   *Security:* Nếu phát hiện bị xâm nhập, kích hoạt NetworkPolicy để khóa egress, cô lập namespace/pod bị nhiễm để chặn Lateral Movement.
    *   (Quá trình này tuân thủ các kịch bản auto-remediation nếu có, hoặc thực hiện thủ công qua Runbook).

### Bước 4: Khắc phục Triệt để (Resolution)
*   Sau khi cô lập thành công và giữ được SLO, đội ngũ tiến hành fix lỗi tận gốc (Rollback code, vá cấu hình, cập nhật quyền RBAC...).

---

## 3. Hoàn tất và Postmortem (Rút kinh nghiệm)

Sau khi sự cố đã được khắc phục hoàn toàn và hệ thống ổn định:

*   **Ai viết Postmortem?**
    *   **CDO On-call (Incident Lead)** – người trực tiếp xử lý sự cố đó – là người chịu trách nhiệm viết và ký tên vào bản Postmortem.
    *   *Lưu ý:* Nếu nguyên nhân gốc liên quan chặt chẽ đến logic của AIOps (ví dụ: báo động sai gây hậu quả, hoặc AI feature sập), AIOps team có trách nhiệm đóng góp nội dung gốc rễ (Root Cause) vào bản Postmortem.
*   **Quy định về Postmortem:**
    *   Sử dụng template chuẩn: `docs/templates/cdo/postmortem.md`.
    *   Lưu trữ tại thư mục: `report/flagd1/` (đối với lỗi mô phỏng Flagd) hoặc thư mục sự cố tương ứng.
    *   Ghi rõ: MTTR, MTTD, và các Action Items (Việc theo sau) kèm hạn chót và Assignee cụ thể để hệ thống chịu lỗi tốt hơn trong tương lai.

> **Phương châm:** "Không đổ lỗi (Blameless). Chúng ta sửa quy trình và hệ thống, không sửa con người."
