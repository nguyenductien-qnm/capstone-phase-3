# Hướng dẫn hiểu project và vai trò Phase 3

Nguồn tổng hợp:

- `team_allocation (1).md`
- `README.md`
- `RULES.md`
- `GETTING_STARTED.md`
- `onboarding/ARCHITECTURE.md`
- `onboarding/SLO.md`
- `onboarding/BUDGET.md`
- `onboarding/INCIDENT_HISTORY.md`
- `onboarding/AI_FEATURE.md`
- `onboarding/PITCH_GUIDE.md`

Tài liệu này giúp bạn hiểu các vai trò trong CDO09 đang đảm nhận gì, hệ thống TechX Corp hoạt động thế nào, và riêng bạn cần nắm gì để hoàn thành Phase 3 với vai trò Observability Engineer / On-Call Captain.

## 1. Phase 3 là gì

Phase 3 không phải bài tập build feature đơn lẻ. Đây là mô phỏng việc một team kỹ sư tiếp quản một sản phẩm đang chạy thật:

- Hệ thống có khách hàng, SLO, ngân sách, incident history và nợ kỹ thuật.
- Team phải tự đánh giá hệ thống, tự chọn backlog, vận hành on-call, xử lý sự cố và bảo vệ quyết định.
- Mọi thay đổi lớn phải có lý do, số liệu, ADR hoặc decision log.
- Không được tắt cơ chế sự cố do BTC cài sẵn, đặc biệt là `flagd` và OpenFeature hooks.

Mục tiêu cá nhân không chỉ là code được, mà là chứng minh bạn biết vận hành, đọc tín hiệu hệ thống, ưu tiên đúng, giao tiếp rõ và chịu trách nhiệm với quyết định.

## 2. Bối cảnh team CDO09

CDO09 thuộc TF1, vận hành chung với AIO03 và CDO05.

CDO09 sở hữu hai trụ core:

- Reliability
- Cost Optimization

Auditability là trụ luân phiên, CDO09 cầm các kỳ lẻ.

Lưu ý quan trọng: home-pillar là để chia ownership dài hạn, nhưng khi on-call thì người trực phải xử lý bất kỳ sự cố nào ập tới, kể cả security, performance, cost hoặc AI.

## 3. Hệ thống TechX Corp cần hiểu

### 3.1 Kiến trúc tổng quan

TechX Corp là storefront thương mại điện tử chạy trên Kubernetes/EKS. Người dùng vào web, duyệt sản phẩm, xem review có tóm tắt AI, thêm giỏ và checkout.

Luồng vào hệ thống:

```text
User -> frontend-proxy/Envoy (:8080) -> frontend -> backend services
```

Các nhóm thành phần chính:

- Web entry: `frontend-proxy`, `frontend`
- Product: `product-catalog`, `recommendation`, `ad`, `image-provider`
- Review + AI: `product-reviews`, `llm`
- Cart/checkout: `cart`, `checkout`, `payment`, `shipping`, `quote`, `currency`, `email`
- Async order flow: `kafka`, `accounting`, `fraud-detection`
- Data stores: `postgresql`, `valkey-cart`, `kafka`
- Observability: OpenTelemetry Collector, Prometheus, Jaeger, OpenSearch, Grafana
- Incident control: `flagd`

### 3.2 Các luồng business quan trọng

Browse:

```text
frontend -> product-catalog + recommendation + ad
```

Product detail + AI review:

```text
frontend -> product-reviews -> postgresql + llm
```

Cart:

```text
frontend -> cart -> valkey-cart
```

Checkout:

```text
frontend -> checkout -> cart/product-catalog/currency/shipping/quote/payment/email -> kafka
```

Post-checkout async:

```text
kafka -> accounting
kafka -> fraud-detection
```

Checkout là luồng revenue-critical. Khi phải chọn ưu tiên, bảo vệ checkout trước.

### 3.3 SLO phải giữ

| Luồng | SLO |
|---|---|
| Browse non-5xx | >= 99.5% |
| Browse p95 latency | < 1s |
| Cart success rate | >= 99.5% |
| Checkout success rate | >= 99.0% |
| AI review summary | Best-effort, nhưng không được hiển thị tóm tắt sai lệch |

Error budget quan trọng nhất:

```text
Checkout SLO >= 99.0% -> error budget = 1%
```

Nếu cháy error budget thì phải đóng băng thay đổi rủi ro, ưu tiên ổn định lại.

### 3.4 Ngân sách

Trần ngân sách là khoảng:

```text
$300 / tuần / TF
```

Chi phí chính gồm:

- EKS nodes / EC2 compute
- Load balancer, NAT, network transfer
- Storage cho DB/log/metric
- Managed services nếu migrate sang RDS, ElastiCache, MSK

Mọi quyết định tốn tiền phải giải thích được ROI. Ví dụ: tăng replica checkout rẻ và bảo vệ revenue thì dễ bảo vệ; bật Multi-AZ RDS đắt hơn nhiều nên cần ADR và cost estimate rõ.

### 3.5 Incident history cần nhớ

INC-1: Checkout chậm/lỗi giờ cao điểm.

- Nguyên nhân: cạn DB connection pool khi tải tăng.
- Bài học: cần load test, timeout, connection pool tuning, alert sớm.

INC-2: Mất giỏ hàng khi node reschedule.

- Nguyên nhân: cart state chạy đơn lẻ, không có replica/độ bền.
- Bài học: cần xử lý SPOF của `valkey-cart`/cart.

INC-3: Lỗi thanh toán khi deploy.

- Nguyên nhân: traffic vào pod chưa sẵn sàng, thiếu readiness gating.
- Bài học: probe, rollout strategy, PDB, rollback runbook phải được làm đồng bộ.

Điểm chung: hệ thống yếu khi có áp lực, deploy, mất node hoặc tải tăng.

## 4. Các vai trò trong CDO09

### 4.1 PM

Mục tiêu: đảm bảo team làm đúng việc, đúng thứ tự, trong ngân sách.

PM chịu trách nhiệm:

- Dẫn kickoff và đọc onboarding packet với cả nhóm.
- Tổng hợp risk register và backlog ưu tiên.
- Chuẩn bị pitch cuối Tuần 1.
- Chủ trì daily standup và bàn giao on-call.
- Viết Weekly Ops Review.
- Theo dõi cost và directive từ BTC.

PM cần input từ bạn:

- Trạng thái telemetry pipeline.
- SLO status.
- Alert/incident summary.
- MTTD/MTTR.
- Cost proxy hoặc cảnh báo liên quan observability.

### 4.2 Tech Lead

Mục tiêu: giữ chuẩn kỹ thuật, deploy đúng, quyết định có ADR và có rollback.

Tech Lead chịu trách nhiệm:

- Setup build/deploy pipeline source -> ECR -> EKS.
- Review Helm changes.
- Viết ADR-001 về kiến trúc ban đầu.
- Sign-off các ADR lớn.
- Là escalation point khi on-call quá 15 phút chưa resolve.
- Đảm bảo luôn dùng `values-flagd-sync.yaml` khi deploy.

Bạn cần phối hợp với Tech Lead khi:

- `kubectl` hoặc cluster access bị lỗi.
- Alert/dashboard đã có trong repo nhưng chưa sync runtime.
- Cần rollback hoặc deploy fix observability.
- Incident vượt khả năng xử lý của primary on-call.

### 4.3 Reliability Engineer #1 - SLO & Failover

Mục tiêu: bảo vệ SLO và giảm SPOF.

Reliability #1 chịu trách nhiệm:

- Dựng SLO dashboard.
- Tính error budget.
- Map single points of failure.
- Ưu tiên fix checkout, cart, product-catalog.
- Thiết kế circuit breaker/fallback cho `product-reviews -> llm`.
- Viết postmortem/COE sau incident.

Bạn cần phối hợp bằng cách:

- Cung cấp số liệu từ Grafana/Prometheus.
- Đảm bảo alert SLO có tín hiệu đúng.
- Giúp trace root cause bằng Jaeger/OpenSearch.

### 4.4 Reliability Engineer #2 - Deploy Safety & Incident Lead

Mục tiêu: deploy không làm chết service và lead incident response.

Reliability #2 chịu trách nhiệm:

- Audit readiness/liveness probes.
- Audit PDB và rollout strategy.
- Thêm probes/PDB/rolling update cho service quan trọng.
- Tạo rollback runbook.
- Cầm primary on-call trong ca trực.

Bạn cần phối hợp bằng cách:

- Cảnh báo khi deploy làm latency/error tăng.
- Hỗ trợ xác định service nào lỗi qua dashboard/log/trace.
- Ghi MTTD/MTTR cho incident.

### 4.5 Reliability Engineer #3 - Load Test & DB Resilience

Mục tiêu: kiểm chứng hệ thống dưới tải và làm cứng DB/Kafka.

Reliability #3 chịu trách nhiệm:

- Đọc lại INC-1 để audit DB connection pool.
- Xem `load-generator` và chạy load test 2x/3x.
- Theo dõi Kafka consumer lag.
- Tuning connection pool, timeout, statement timeout.
- Đánh giá PgBouncer hoặc migration nếu cần.

Bạn cần phối hợp bằng cách:

- Dựng/verify Kafka lag alert.
- Cung cấp p95 latency/error rate khi load test.
- Cung cấp trace/log khi thấy timeout hoặc lag tăng.

### 4.6 Cost/Platform Engineer

Mục tiêu: tối ưu compute và scaling trong trần cost.

Cost/Platform chịu trách nhiệm:

- Setup AWS Budgets alert.
- Bật Cost Anomaly Detection.
- Audit node utilization và pod utilization.
- Right-size nodes.
- Thiết kế Spot cho workload non-critical.
- Dựng HPA, ResourceQuota, LimitRange.

Bạn cần phối hợp bằng cách:

- Cung cấp cost proxy dashboard nếu có metric.
- Báo tín hiệu bất thường như Kafka lag, saturation, scrape volume/log volume.
- Đảm bảo cost optimization không phá SLO.

### 4.7 FinOps/IaC Engineer

Mục tiêu: giữ cost traceable và thay đổi audit được.

FinOps/IaC chịu trách nhiệm:

- Tagging strategy cho AWS resources.
- Cost breakdown dashboard.
- K8s audit log policy.
- Change management log.
- Báo cáo Cost Explorer hằng ngày.
- Đánh giá migration managed services theo cost/reliability trade-off.

Bạn cần phối hợp bằng cách:

- Đảm bảo logs/metrics/traces đủ để audit vận hành.
- Ghi rõ thay đổi alert/dashboard trong change log.
- Cung cấp số liệu phục vụ auditability report.

### 4.8 Observability Engineer - On-Call Captain

Đây là vai trò của bạn.

Mục tiêu: đảm bảo team nhìn thấy vấn đề sớm, có alert đúng, có runbook, có lịch trực và đo được MTTD/MTTR.

Tuần 1:

- Verify telemetry pipeline:
  - Prometheus targets.
  - Jaeger traces.
  - OpenSearch logs.
  - Grafana dashboards.
- Dựng SLO alert rules:
  - `CheckoutHighErrorRate`
  - `BrowseHighLatency`
  - `KafkaConsumerLag`
- Dựng cost estimate panel nếu có metric.
- Tạo runbooks P0/P1/P2.
- Tạo on-call schedule.
- Tạo MTTD/MTTR report template.

Tuần 2-3:

- Quản lý on-call schedule và bàn giao ca mỗi standup.
- Theo dõi MTTD target `< 5 phút` cho P0.
- Sau incident, tune alert để giảm false positive.
- Cung cấp SLO status + cost burn/cost proxy cho PM.
- Dùng Jaeger trace để root cause khi incident.

Điểm cần nhớ:

- Bạn là standby/captain, không cầm primary.
- Primary on-call lead incident.
- TechLead là escalation.
- Bạn phải nói rõ cái gì đã verify, cái gì chưa verify, cái gì đang blocked.

### 4.9 Build Engineer

Mục tiêu: ship các backlog items và hỗ trợ thay đổi Helm/IaC/code.

Build Engineer chịu trách nhiệm:

- Deep dive source code.
- Hỗ trợ build pipeline lần đầu.
- Implement backlog items đã được ưu tiên.
- Cập nhật Helm values cho probes, PDB, HPA, ResourceQuota.
- Implement code fix nếu Reliability/Cost cần.
- Viết ADR cho thay đổi lớn.

Bạn cần phối hợp bằng cách:

- Chỉ ra alert/dashboard/runbook cần thay đổi.
- Yêu cầu build/deploy các thay đổi observability.
- Verify sau khi Build/TechLead sync lên runtime.

## 5. Bạn cần hiểu gì để hoàn thành project

### 5.1 Hiểu Operate và Build chạy song song

Phase 3 luôn có hai luồng:

- Operate: giữ service sống, on-call, incident, SLO, cost, weekly ops review.
- Build: ship cải tiến đã được ưu tiên trong backlog.

Bạn không được chỉ làm tài liệu rồi dừng. Tài liệu, alert, dashboard phải phục vụ vận hành thật.

### 5.2 Hiểu cách ưu tiên backlog

Công thức pitch guide:

```text
Ưu tiên = Rủi ro x Tác động business
```

Với vai trò của bạn, các backlog observability nên ưu tiên như sau:

1. Fix đường đo đạc và verify telemetry pipeline.
2. Đảm bảo checkout P0 alert hoạt động.
3. Đảm bảo Prometheus targets quan trọng đều UP.
4. Đảm bảo Jaeger/OpenSearch dùng được khi incident.
5. Dựng MTTD/MTTR report cho Ops Review.
6. Tune alert sau incident.

### 5.3 Hiểu các công cụ vận hành

Bạn cần biết dùng:

- Grafana: xem dashboard, datasource, Explore.
- Prometheus: query metrics, targets, rules.
- Jaeger: tìm trace theo service, duration, error.
- OpenSearch: query logs theo namespace/service/trace id.
- Kubernetes/kubectl: get pods, services, logs, rollout status, port-forward.
- Helm/ArgoCD: hiểu change trong repo khi nào vào runtime.
- AWS CLI/EKS: update kubeconfig, check identity, xử lý access issue.

### 5.4 Hiểu telemetry pipeline

Pipeline chuẩn:

```text
Service OpenTelemetry SDK
-> OpenTelemetry Collector
-> Prometheus / Jaeger / OpenSearch
-> Grafana
```

Bạn cần biết cách chứng minh từng đoạn đang sống:

- Service có emit telemetry không?
- Collector có nhận không?
- Prometheus/Jaeger/OpenSearch có dữ liệu không?
- Grafana có datasource và dashboard đúng không?
- Alert rules có active không?

### 5.5 Hiểu các ràng buộc không được vi phạm

Không được:

- Tắt hoặc bypass `flagd`.
- Gỡ OpenFeature hooks.
- Sửa hệ thống để tránh sự cố thay vì làm hệ thống chịu lỗi tốt hơn.
- Vượt ngân sách mà không có lý do/ADR.
- Làm thay đổi phá SLO của service khác.
- Nói PASS khi chưa có bằng chứng runtime.

### 5.6 Hiểu cách báo cáo

Mỗi báo cáo nên có:

- Kết quả đo được.
- Nguồn số liệu.
- Trạng thái PASS/PARTIAL/BLOCKED.
- Rủi ro business.
- Đề xuất next action.
- Owner tiếp theo.

Ví dụ đúng:

```text
Prometheus targets: 12 total, 11 UP, 1 DOWN.
Target DOWN là Jaeger metrics :8888, lỗi connection refused.
Đã patch values.yaml để bật endpoint, cần ArgoCD sync.
Trạng thái: PARTIAL, chưa thể mark telemetry pipeline PASS.
```

Ví dụ không nên nói:

```text
Telemetry đã xong.
```

khi vẫn còn target DOWN hoặc runtime chưa sync.

## 6. Những file trong repo bạn nên biết

| File/thư mục | Bạn dùng để làm gì |
|---|---|
| `README.md` | Hiểu nhiệm vụ Phase 3 và thứ tự đọc tài liệu |
| `RULES.md` | Nắm luật chơi, timeline, deliverables, disqualify rules |
| `GETTING_STARTED.md` | Hiểu build/deploy/verify hệ thống |
| `onboarding/ARCHITECTURE.md` | Hiểu service map và request flow |
| `onboarding/SLO.md` | Biết SLO nào phải bảo vệ |
| `onboarding/BUDGET.md` | Biết trần cost và trade-off |
| `onboarding/INCIDENT_HISTORY.md` | Biết rủi ro lịch sử |
| `onboarding/PITCH_GUIDE.md` | Biết cách bảo vệ backlog trước hội đồng |
| `onboarding/AI_FEATURE.md` | Hiểu bề mặt AI và phối hợp với AIO |
| `techx-corp-chart/values.yaml` | Nơi cấu hình Helm, service, observability, alert rules |
| `techx-corp-chart/grafana/provisioning/` | Dashboards, datasources, alerting provisioning |
| `deploy/values-observability.yaml` | Bật observability stack |
| `deploy/values-flagd-sync.yaml` | Cấu hình flagd bắt buộc khi deploy |
| `docs/observability/runbooks.md` | Runbooks P0/P1/P2 |
| `docs/observability/on-call-schedule.md` | Rotation và handover |
| `docs/observability/telemetry-pipeline-verification.md` | Biên bản verify telemetry |
| `docs/observability/current-observability-issues-and-fixes.md` | Vấn đề hiện tại và đề xuất fix |

## 7. Trạng thái hiện tại liên quan vai trò của bạn

Đã làm trong repo:

- SLO alert rules cho `CheckoutHighErrorRate`, `BrowseHighLatency`, `KafkaConsumerLag`.
- Cost dashboard file `cost-dashboard.json`.
- Runbooks P0/P1/P2.
- On-call schedule.
- MTTD/MTTR template.
- Biên bản verify telemetry.
- Tài liệu current issues và đề xuất fix.

Đã verify được qua public endpoint:

- Storefront truy cập được.
- Grafana healthy.
- Datasources có Prometheus, Jaeger, OpenSearch.
- Jaeger có services và traces.
- OpenSearch có logs.
- Prometheus có HTTP/RPC metrics.

Chưa hoàn thành:

- Prometheus chưa đạt tất cả targets UP: hiện 11/12 UP, Jaeger metrics `:8888` DOWN.
- Runtime chưa thấy SLO alert group `SLOs`.
- Runtime chưa thấy Grafana dashboard `Cost Estimate`.
- `kafka_consumer_group_lag` hiện query ra 0 series.

Kết luận: task verify telemetry pipeline hiện là PARTIAL, chưa PASS hoàn toàn.

## 8. Bạn nên làm gì tiếp theo

Thứ tự ưu tiên:

1. Commit/push các thay đổi observability để ArgoCD sync.
2. Sau sync, kiểm tra lại Prometheus targets, kỳ vọng Jaeger `:8888` UP.
3. Kiểm tra runtime có alert group `SLOs`.
4. Kiểm tra runtime có dashboard `Cost Estimate`.
5. Verify lại metric Kafka lag hoặc tìm đúng metric Kafka thực tế.
6. Cập nhật biên bản verification với số liệu mới.
7. Cung cấp status cho PM để đưa vào pitch/Ops Review.

## 9. Cách nói trong pitch hoặc standup

Bạn có thể báo cáo ngắn:

```text
Về Observability, public runtime đã có Grafana, Jaeger traces, OpenSearch logs và Prometheus metrics.
Kubectl local đã được khắc phục sau khi xóa aws_session_token rỗng trong AWS credentials.
Telemetry pipeline đang đạt một phần, nhưng chưa thể mark PASS hoàn toàn vì Prometheus còn 1 target Jaeger :8888 DOWN và runtime chưa thấy SLO/Cost dashboard sync.
SLO alert rules và Cost dashboard đã có trong repo, đang chờ sync lên runtime.
Risk chính hiện tại là alert/dashboard chưa xuất hiện trên runtime và Jaeger metrics target còn DOWN, nên cần sync chart và verify lại Prometheus targets.
```

## 10. Mental model để hoàn thành Phase 3

Khi làm bất kỳ việc gì, hãy tự hỏi:

1. Việc này bảo vệ SLO nào?
2. Nếu không làm, khách hàng hoặc doanh thu bị ảnh hưởng thế nào?
3. Việc này tốn thêm bao nhiêu tiền?
4. Có bằng chứng đo được không?
5. Nếu deploy sai, rollback thế nào?
6. Có ADR/runbook/postmortem chưa?
7. Ai là owner tiếp theo?

Nếu trả lời được các câu này bằng số liệu và link tài liệu, bạn đang làm đúng tinh thần Phase 3.
