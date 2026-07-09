# Kế hoạch công việc Phase 3 - Observability Engineer

Người phụ trách: Kỹ sư Observability / On-Call Captain

Phạm vi: Observability + quản lý vòng trực on-call

Tài liệu này mô tả những việc bạn cần làm trong Phase 3 theo từng tuần. Phần cuối ghi lại những việc đã được thực hiện trong repository để bạn biết trạng thái hiện tại của hệ thống.

## Tóm tắt vai trò

Kỹ sư Observability chịu trách nhiệm làm cho hệ thống có thể quan sát, đo đạc và vận hành được. Vai trò này không trực tiếp sở hữu mọi bản sửa lỗi production. Trách nhiệm chính là giúp cả đội phát hiện sự cố sớm, chẩn đoán nguyên nhân bằng telemetry, điều phối bàn giao on-call và báo cáo trạng thái SLO/cost rõ ràng.

Các trách nhiệm chính:

- Verify telemetry pipeline: metrics trên Prometheus, traces trên Jaeger, logs trên OpenSearch, dashboards trên Grafana.
- Dựng và duy trì SLO alert rules.
- Duy trì alert runbooks cho các sự cố P0/P1/P2.
- Quản lý on-call schedule và bàn giao ca hằng ngày.
- Theo dõi MTTD/MTTR và cung cấp dữ liệu cho Weekly Ops Review.
- Hỗ trợ người trực chính chẩn đoán sự cố bằng Grafana, Jaeger và OpenSearch.
- Tune alert sau incident để giảm false positive và tăng signal-to-noise.

## Tuần 1 - Bootstrap

Mục tiêu: chứng minh observability stack đang sống và tạo baseline vận hành đầu tiên.

### 1. Verify telemetry pipeline

Kiểm tra Prometheus scraping:

```powershell
kubectl -n techx-tf1 port-forward svc/prometheus 9090:9090
curl http://localhost:9090/api/v1/targets
```

Kết quả kỳ vọng:

- Prometheus truy cập được.
- Các target quan trọng ở trạng thái `UP`.
- Có service metrics, ví dụ:
  - `target_info`
  - `http_server_request_duration_seconds_count`
  - `rpc_server_duration_milliseconds_count`
  - `kafka_consumer_group_lag`

Kiểm tra Jaeger traces:

```powershell
kubectl -n techx-tf1 port-forward svc/frontend-proxy 8080:8080
curl http://localhost:8080/
```

Mở:

```text
http://localhost:8080/jaeger/ui/
```

Kết quả kỳ vọng:

- Có trace mới sau khi tạo request.
- Trace context không bị đứt.
- Có thể inspect luồng liên quan checkout từ `frontend` sang các backend service như `checkout` và `payment`.

Kiểm tra OpenSearch logs:

- Mở Grafana Explore.
- Chọn datasource OpenSearch.
- Query:

```text
kubernetes.namespace: techx-*
```

Kết quả kỳ vọng:

- Có log mới từ các service TechX.
- Có thể filter log theo namespace, service hoặc severity.

Kiểm tra Grafana dashboards:

- APM dashboard có dữ liệu service.
- Cost Estimate dashboard tồn tại.
- SLO hoặc alerting view hiển thị alert group đã cấu hình.

Ghi chú hiện tại:

- Public ELB của Storefront/Grafana/Jaeger truy cập được, nên có thể verify một phần runtime qua URL public.
- `kubectl` local đã truy cập được EKS sau khi xóa dòng `aws_session_token=` rỗng trong `~/.aws/credentials`.
- `kubectl get nodes`, `kubectl get ns` và `kubectl get pods -n techx-tf1` đã chạy thành công.
- Prometheus hiện có 11/12 active targets `UP`; 1 target `DOWN` là Jaeger metrics endpoint `:8888`.
- Không đánh dấu Prometheus scraping là PASS hoàn toàn cho tới khi target Jaeger `:8888` được sửa và `/api/v1/targets` hiển thị tất cả target quan trọng `UP`.

### 2. Dựng SLO alert rules

Tạo hoặc duy trì Prometheus alert rules cho các rủi ro SLO chính:

```yaml
# P0 - Checkout error rate
- alert: CheckoutHighErrorRate
  expr: |
    (
      sum(rate(rpc_server_duration_milliseconds_count{service_namespace="techx-corp",service_name="checkout",rpc_grpc_status_code!="0"}[5m]))
      /
      sum(rate(rpc_server_duration_milliseconds_count{service_namespace="techx-corp",service_name="checkout"}[5m]))
    ) > 0.01
  for: 2m
  labels: { severity: critical }

# P1 - Latency spike
- alert: BrowseHighLatency
  expr: |
    histogram_quantile(
      0.95,
      sum by (le) (
        rate(http_server_request_duration_seconds_bucket{service_namespace="techx-corp",service_name="frontend"}[5m])
      )
    ) > 1
  for: 5m
  labels: { severity: warning }

# P2 - Cost anomaly / async backlog
- alert: KafkaConsumerLag
  expr: kafka_consumer_group_lag > 1000
  for: 10m
  labels: { severity: warning }
```

Kết quả kỳ vọng:

- Alerts được deploy thông qua Helm chart.
- Mỗi alert có runbook tương ứng.
- Prometheus/Grafana hiển thị alert group `SLOs` sau khi deploy.

### 3. Dựng panel cost trên Grafana

Dựng panel ước tính cost theo service nếu có metric phù hợp.

Metric ban đầu:

```promql
kafka_consumer_group_lag
```

Kết quả kỳ vọng:

- Grafana có dashboard `Cost Estimate`.
- Panel hiển thị Kafka lag như một proxy cho async backlog và rủi ro cost/performance.

### 4. Tạo tài liệu on-call ban đầu

Tạo các tài liệu vận hành cho Tuần 1:

- Alert runbooks cho P0/P1/P2.
- On-call schedule.
- Checklist bàn giao ca hằng ngày.
- Mẫu MTTD/MTTR weekly report.

## Tuần 2 - Vận hành và lấy baseline

Mục tiêu: dùng observability setup trong vận hành hằng ngày và thu thập baseline vận hành thật đầu tiên.

### 1. Bàn giao on-call mỗi ngày

Trong mỗi buổi standup, thu thập và bàn giao:

- Alerts đã fire trong 24 giờ qua.
- False positives và alert bị nhiễu.
- Rủi ro SLO đang mở.
- Incident đang xảy ra và người đang sở hữu xử lý.
- Cập nhật MTTD/MTTR.
- Bất kỳ khoảng trống nào về dashboard hoặc telemetry.

### 2. Theo dõi sức khỏe SLO

Theo dõi các tín hiệu SLO hằng ngày:

- Checkout success rate.
- Storefront p95 latency.
- Cart operation success rate.
- Kafka consumer lag.
- Error budget burn.

Kết quả cần có:

- Trạng thái ngắn hằng ngày cho team.
- Input hằng tuần cho PM làm Ops Review.

### 3. Hỗ trợ chẩn đoán incident

Khi có incident:

- Bắt đầu từ Grafana SLO/APM dashboard.
- Dùng Jaeger để inspect traces.
- Dùng OpenSearch để inspect logs.
- Hỗ trợ primary on-call xác định service hoặc dependency có khả năng đang lỗi.

Điểm quan trọng:

- Primary on-call là người lead incident.
- Observability Engineer là standby/captain và hỗ trợ bằng telemetry.
- Escalate lên TechLead nếu incident vượt ngưỡng escalation.

### 4. Bắt đầu đo MTTD/MTTR

Với mỗi incident P0/P1, ghi lại:

- Thời điểm incident bắt đầu.
- Thời điểm alert fire.
- Thời điểm có người acknowledge.
- Thời điểm mitigate.
- Thời điểm resolve.
- MTTD.
- MTTR.

Định nghĩa:

```text
MTTD = thời điểm alert fire - thời điểm incident bắt đầu
MTTR = thời điểm resolve - thời điểm incident bắt đầu
```

Target P0:

```text
MTTD < 5 phút
```

## Tuần 3 - Tune alert và làm cứng vận hành

Mục tiêu: cải thiện chất lượng alert và giảm thời gian chẩn đoán sự cố.

### 1. Tune alert sau incident

Sau mỗi incident hoặc false positive:

- Kiểm tra alert có fire đủ sớm không.
- Kiểm tra alert có fire đúng nguyên nhân không.
- Điều chỉnh threshold, thời lượng `for`, labels hoặc metric filters.
- Bổ sung annotations hoặc runbook links còn thiếu.
- Ghi thay đổi vào Ops Review hoặc postmortem.

Ví dụ:

- Nếu `BrowseHighLatency` fire quá nhiều vì spike ngắn, tăng `for` hoặc thu hẹp filter theo route/service.
- Nếu `CheckoutHighErrorRate` fire quá trễ, giảm window hoặc thêm symptom-level alert.
- Nếu `KafkaConsumerLag` quá rộng, tách threshold theo consumer group.

### 2. Cải thiện runbooks

Mỗi runbook nên trả lời được:

- Alert này nghĩa là gì?
- Ảnh hưởng tới khách hàng hoặc business là gì?
- Dashboard nào cần mở đầu tiên?
- Trace/log query nào cần dùng?
- Ai sở hữu hành động tiếp theo?
- Khi nào phải escalate?

### 3. Cải thiện báo cáo hằng tuần

Cung cấp cho PM:

- Trạng thái SLO.
- Trạng thái error budget.
- Cost burn hoặc cost proxy.
- Số incident theo severity.
- MTTD/MTTR.
- Các thay đổi alert tuning.
- Các khoảng trống observability còn mở.

## Tuần 4 - Tổng kết và bàn giao

Dùng phần này nếu Phase 3 kéo dài 4 tuần. Nếu chương trình kết thúc sau Tuần 3, dùng phần này làm checklist bàn giao cuối.

### 1. Review observability cuối kỳ

Kiểm tra team vẫn trả lời được các câu hỏi:

- Checkout có đang khỏe không?
- Storefront latency có nằm trong SLO không?
- Logs có search được không?
- Traces có đủ đầy để root cause không?
- Alert rules đã deploy và active chưa?
- Alert bị nhiễu đã được ghi nhận hoặc sửa chưa?

### 2. Báo cáo MTTD/MTTR cuối kỳ

Chuẩn bị số liệu cuối:

- Tổng số incident P0/P1/P2.
- MTTD trung bình.
- MTTR trung bình.
- Incident nghiêm trọng nhất.
- Alert hữu ích nhất.
- Alert nhiễu nhất.
- Alert tuning đã hoàn tất.
- Các khoảng trống telemetry còn lại.

### 3. Gói bàn giao

Đảm bảo các file sau được cập nhật:

- `docs/observability/runbooks.md`
- `docs/observability/on-call-schedule.md`
- `docs/observability/telemetry-pipeline-verification.md`
- `docs/templates/ops-review.md`
- `docs/templates/postmortem.md`

## On-call rotation

Rotation 7 ngày gợi ý:

```text
Ngày 1-2:  Reliability Eng #2 (primary)
Ngày 3-4:  Reliability Eng #1 (primary)
Ngày 5:    Cost/Platform Eng (primary)
Ngày 6:    Reliability Eng #3 (primary)
Ngày 7:    Build Engineer (primary)

TechLead = luôn là escalation
Observability Eng = luôn standby, không cầm primary
```

Escalate lên TechLead khi:

- P0 chưa resolve sau hơn 15 phút.
- Checkout/payment bị ảnh hưởng.
- Cần quyết định rollback hoặc hotfix.
- Cần quyết định trade-off giữa SLO, cost, security hoặc scope.

## Deliverables theo tuần

| Tuần | Deliverable | Trạng thái |
|---|---|---|
| Tuần 1 | Verify telemetry pipeline | ĐẠT MỘT PHẦN; `kubectl` local đã OK, nhưng Prometheus còn 1 target DOWN và runtime chưa thấy SLO/Cost dashboard sync |
| Tuần 1 | Prometheus SLO alert rules | ĐÃ LÀM trong repo |
| Tuần 1 | Grafana cost estimate dashboard | ĐÃ LÀM trong repo |
| Tuần 1 | Alert runbooks P0/P1/P2 | ĐÃ LÀM trong repo |
| Tuần 1 | On-call schedule | ĐÃ LÀM trong repo |
| Tuần 1 | Mẫu MTTD/MTTR report | ĐÃ LÀM trong repo |
| Tuần 2 | Daily on-call handover | SẴN SÀNG, cần vận hành thật |
| Tuần 2 | Báo cáo SLO/cost tuần đầu | ĐANG CHỜ runtime data |
| Tuần 3 | Tune alert sau incident | ĐANG CHỜ incident/alert data |
| Tuần 3 | Cải thiện runbooks và input postmortem | SẴN SÀNG |
| Tuần 4 | Final observability review và bàn giao | ĐÃ LÊN KẾ HOẠCH |

## Những việc đã làm trong repository

Các việc sau đã được thực hiện cho vai trò Observability Engineer.

### 1. Đã thêm SLO alert rules

File:

```text
techx-corp-chart/values.yaml
```

Đã thêm Prometheus alert rules:

- `CheckoutHighErrorRate`
- `BrowseHighLatency`
- `KafkaConsumerLag`

Các biểu thức alert đã được chỉnh để khớp với OpenTelemetry metrics mà Grafana APM dashboard hiện có đang dùng.

### 2. Đã thêm cost dashboard

File:

```text
techx-corp-chart/grafana/provisioning/dashboards/cost-dashboard.json
```

Dashboard:

```text
Cost Estimate
```

Panel:

```text
Per-Service Cost Estimate (Proxy via Kafka Lag)
```

Metric:

```promql
kafka_consumer_group_lag
```

### 3. Đã thêm alert runbooks

File:

```text
docs/observability/runbooks.md
```

Runbooks đã có:

- P0 `CheckoutHighErrorRate`
- P1 `BrowseHighLatency`
- P2 `KafkaConsumerLag`

### 4. Đã thêm on-call schedule

File:

```text
docs/observability/on-call-schedule.md
```

Nội dung gồm:

- On-call rotation 7 ngày.
- Vai trò standby của Observability Engineer.
- Vai trò escalation của TechLead.
- Checklist bàn giao ca hằng ngày.
- Mẫu MTTD/MTTR weekly report.

### 5. Đã thêm biên bản verify telemetry

File:

```text
docs/observability/telemetry-pipeline-verification.md
```

Đã ghi lại:

- Các kiểm tra observability ở phía repository đã đạt.
- Các lệnh runtime verification cần chạy.
- Blocker `kubectl` local đã được xử lý; nguyên nhân là `aws_session_token=` rỗng trong `~/.aws/credentials`.
- Kết quả kiểm tra public ELB: Storefront/Grafana/Jaeger truy cập được, Prometheus/OpenSearch query được qua Grafana proxy.
- Vấn đề còn lại: Prometheus có 1 target Jaeger metrics `:8888` đang DOWN; SLO alert group và Cost dashboard chưa thấy trên runtime cho tới khi ArgoCD/Helm sync.
- Checklist cần chạy lại với `kubectl` local; sau đó kiểm tra target Jaeger metrics sau khi chart được sync.

## Trạng thái runtime hiện tại

Chưa thể mark telemetry pipeline PASS hoàn toàn cho tới khi Prometheus không còn target DOWN và các thay đổi SLO/Cost dashboard xuất hiện trên runtime.

Kết quả lệnh quan sát được:

```text
kubectl get nodes: PASS, 3 nodes Ready
kubectl get ns: PASS, có namespace techx-tf1
kubectl get pods -n techx-tf1: PASS, workload pods Running
```

Kiểm tra phía AWS/local cho thấy:

- IAM identity là `arn:aws:iam::265808836805:user/phase3/cdo/hoangplt`.
- EKS cluster `techx-eks-dev` đang ACTIVE.
- Access entry tồn tại cho `hoangplt`.
- `AmazonEKSClusterAdminPolicy` đã được associate ở cluster scope.
- Lỗi cũ do `~/.aws/credentials` có `aws_session_token=` rỗng.
- Sau khi xóa dòng rỗng, EKS token không còn `X-Amz-Security-Token` rỗng và `kubectl` đã vào được cluster.

Hành động cần làm:

- Chạy lại checklist runtime verification của Tuần 1 với `kubectl` local.
- Kiểm tra lại Prometheus target Jaeger `:8888`.
- Commit/push thay đổi observability và đợi ArgoCD/Helm sync để verify SLO rules và Cost dashboard.
- Sau khi ArgoCD/Helm sync bản chart mới, kiểm tra lại Prometheus targets để xác nhận Jaeger metrics endpoint `:8888` đã `UP`.
