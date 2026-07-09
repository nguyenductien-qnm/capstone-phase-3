# Alert Runbooks

Tài liệu này hướng dẫn cách phản hồi (respond) khi các Alert kích hoạt trên Grafana/Prometheus.

## 🔴 P0 - CheckoutHighErrorRate (Critical)
**Mô tả:** Tỷ lệ lỗi (Error rate) của service `checkout` vượt quá 1% trong 5 phút. Tác động trực tiếp đến khả năng thanh toán của khách hàng.
**MTTD Target:** < 5 phút

**Hành động (Runbook):**
1. Mở [Jaeger UI](/jaeger/ui/) để tìm các traces bị lỗi (Error = true) từ service `checkout`.
2. Kiểm tra log của `checkout` trên OpenSearch (`kubernetes.namespace: techx-* AND service: checkout AND severity: ERROR`).
3. Kiểm tra xem các dependency của `checkout` (như `payment`, `cart`, `kafka`) có đang phản hồi chậm hoặc bị lỗi không thông qua Grafana APM Dashboard.
4. Báo cáo ngay lên kênh Slack `#incidents-p0`.
5. Nếu do lỗi code mới deploy, thực hiện Rollback qua ArgoCD (GitOps).

---

## 🟡 P1 - BrowseHighLatency (Warning)
**Mô tả:** Độ trễ phân vị thứ 95 (p95 latency) của service `frontend` vượt quá 1 giây trong 5 phút. Tác động đến trải nghiệm lướt web của người dùng.
**MTTD Target:** < 15 phút

**Hành động (Runbook):**
1. Mở [Grafana APM Dashboard](/grafana/) để xem panel RED Metrics của service `frontend`.
2. Truy xuất Jaeger Traces, sắp xếp theo thời gian phản hồi (Duration) dài nhất.
3. Tìm xem Span nào đang chiếm nhiều thời gian nhất (ví dụ: truy vấn DB chậm, hoặc gọi service `recommendation` chậm).
4. Phối hợp với team Development để xem xét tối ưu hóa (ví dụ: thêm caching, sửa câu query).

---

## 🟡 P2 - KafkaConsumerLag (Cost Anomaly / Performance)
**Mô tả:** Kafka Consumer Group Lag vượt quá ngưỡng 1000 message. Điều này có thể gây tốn chi phí lưu trữ hoặc khiến dữ liệu (như tính toán Fraud Detection) bị nghẽn.
**MTTD Target:** < 30 phút

**Hành động (Runbook):**
1. Mở **Cost Estimate Dashboard** trên Grafana để xem mức độ Lag cụ thể của từng Consumer.
2. Kiểm tra xem các worker node có đang chạy với tải CPU/Memory cao không (có thể không xử lý kịp).
3. Scale up số lượng bản sao (Replicas) của service đang tiêu thụ message (như `fraud-detection` hoặc `accounting`) nếu cần thiết.
4. Báo cáo trong buổi Ops Review hàng tuần để có phương án điều chỉnh cấu hình (Scale) hoặc tối ưu chi phí.
