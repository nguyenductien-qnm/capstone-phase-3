# Mandate 18 — hướng dẫn chụp evidence

Giữ region `N. Virginia (us-east-1)`, hiện rõ bộ lọc và cửa sổ thời gian. Che AWS account ID, user/email và ARN chứa account ID; không che resource name, trạng thái, region, timestamp, metric, unit hoặc giá trị.

## 1. Scope

1. AWS Console → EKS → Clusters → `ecommerce-dev-eks` → Overview.
2. Giữ trong ảnh: cluster name, status `Active`, Kubernetes `1.36`, region.
3. Chụp `01-scope-identity.png`.

## 2. Cost Explorer — top driver trước thay đổi

1. Billing and Cost Management → Cost Explorer → Cost and usage.
2. Date: `2026-07-15` đến `2026-07-22`; Granularity: Monthly; Metric: Usage quantity.
3. Group by: `Service`, sau đó `Usage type`; loại `Amazon Elastic Compute Cloud - Compute`.
4. Chụp riêng bảng/biểu đồ GB, giữ rõ `DataTransfer-Regional-Bytes`, `NatGateway-Bytes`, `USE1-VendedLog-Bytes` và unit `GB`.
5. Không cộng hoặc đặt GB, GB-Month, Hrs trên cùng một tổng.
6. Chụp `02-top-driver-before.png`.

Lưu ý bắt buộc khi trình bày: Cost Explorer hiện không trả tag `Project=ecommerce`; ảnh này là account-wide, chưa phải TF-only.

## 3. Orphan inventory trước thay đổi

1. EC2 → Elastic Block Store → Volumes; filter `State = available`. Chụp `03a-ebs-available-before.png`.
2. EC2 → Elastic IP addresses; giữ cột Association ID/Instance/Network interface. Chụp `03b-eip-before.png`.
3. EC2 → Snapshots → Owned by me. Chụp `03c-snapshots-before.png`.
4. EC2 → AMIs → Owned by me. Chụp `03d-amis-before.png`.
5. EC2 → Load Balancers; giữ State/Type/VPC. Chụp `03e-load-balancers-before.png`.
6. EC2 → Target Groups; mở lần lượt `123123321`, `89345789437843`, `testt`; chụp tab Targets và Load balancer association. Chụp `03f-target-groups-before.png`.

Ba target group trống chỉ là ứng viên cần owner/dependency review; ảnh không được ghi “đã xác nhận orphan”.

## 4. EBS gp3 và PVC usage

1. EC2 → Volumes; thêm cột Volume type, Size, State, Attached resources; filter/tag PVC `prometheus` và `opensearch-opensearch-0`.
2. Chụp `05a-ebs-gp3.png`.
3. Grafana → Explore → Prometheus, chạy ba query:
   - `kubelet_volume_stats_capacity_bytes{namespace="techx-tf1"}`
   - `kubelet_volume_stats_used_bytes{namespace="techx-tf1"}`
   - `kubelet_volume_stats_available_bytes{namespace="techx-tf1"}`
4. Chọn Table, giữ timestamp và PVC label. Chụp `05b-pvc-usage.png`.

## 5. Storage lifecycle

1. S3 → `ecommerce-dev-cloudtrail-logs` → Management → Lifecycle rules; mở `archive-and-retain-audit-logs`. Chụp `06a-cloudtrail-lifecycle.png`.
2. S3 → `terraform-state-phase-3` → Management → Lifecycle rules; thể hiện không có rule. Chụp `06b-terraform-state-lifecycle-gap.png`.
3. EC2 → Lifecycle Manager → EBS snapshot policies; thể hiện danh sách trống. Chụp `06c-dlm-baseline.png`.

## 6. NAT và cross-AZ baseline

1. VPC → NAT gateways → `ecommerce-dev-nat-gw-single` → Monitoring.
2. Custom time: `2026-07-21 07:13:18 UTC` đến `2026-07-22 07:13:18 UTC`.
3. Hiện `BytesInFromSource`, `BytesInFromDestination`, `ActiveConnectionCount`, `ConnectionAttemptCount`, `ConnectionEstablishedCount`, `IdleTimeoutCount`, `ErrorPortAllocation`.
4. Chụp `07a-nat-cloudwatch-before.png`.
5. Cost Explorer cùng cửa sổ ở mục 2; lọc Usage type `NatGateway-Bytes`, `NatGateway-Hours`, `USE1-DataTransfer-xAZ-In-Bytes`, `USE1-DataTransfer-xAZ-Out-Bytes`.
6. Chụp `07b-network-usage-before.png`.

Không cộng bốn NAT byte counters vì các cặp in/out mô tả cùng payload theo hai phía.

## 7. VPC endpoint baseline

1. VPC → Endpoints; filter VPC `vpc-06d4c34ec03f55c6d`.
2. Giữ Service name, Type, State, Private DNS, Subnets.
3. Chụp `08-vpc-endpoints.png`; ghi chú endpoint hiện tại là private endpoint service, không phải S3/ECR AWS service endpoint.

## 8. Telemetry baseline

1. Grafana → Explore → Prometheus, cửa sổ Last 5 minutes, Table mode.
2. Lần lượt chạy các query trong `logs/09-telemetry-before.txt` cho accepted spans/log records/metric points, spanmetrics rate và `prometheus_tsdb_head_series`.
3. Chụp `09a-telemetry-rate-before.png` và `09b-prometheus-series-before.png`.
4. Open Grafana Explore/OpenSearch hoặc OpenSearch Dashboards → Index Management → Indices; giữ index, docs, store size. Chụp `09c-opensearch-size-before.png`.
5. OpenSearch Dashboards → Index Management → State management policies; thể hiện `0 policies`. Chụp `09d-opensearch-retention-gap.png`.
6. CloudWatch → Log groups; giữ Retention và Stored bytes. Chụp `09e-cloudwatch-retention-before.png`.

## 9. SLO baseline

1. Grafana → Dashboards → mở dashboard `SLO Dashboard`.
2. Chọn Last 24 hours; giữ Checkout SLI, Browse SLI, Cart SLI, Storefront p95, request volume và time picker.
3. Chụp `11-slo-baseline.png`.
4. Nếu panel 5m p95 hiện `No data/NaN`, không che; giải thích frontend-proxy có `0 calls/s` trong đúng 5m, trong khi p95 1h = `47.51 ms` và p95 24h = `196.83 ms` ở raw log.

## 10. Ảnh after-change

Chưa chụp các file `04-*`, `10-*`, `11-slo-after.png`, `13-*` trước khi Prompt 3+ có thay đổi thật và chạy lại đúng query/window. Không dùng ảnh baseline làm evidence after.

## 11. Prompt 7 final verification và investigation drill

1. Grafana → SLO Dashboard → chọn đúng cửa sổ 5 phút verification; giữ visible
   checkout/browse/cart success, storefront p95, request volume và UTC time.
   Chụp `11a-slo-final-verification.png`.
2. Grafana Explore → chạy histogram bucket query của frontend-proxy; giữ các
   bucket `1000`, `5000`, `10000`, `15000`, `+Inf`. Chụp
   `11b-storefront-p95-failure.png`. Không đổi 15000 ms thành PASS.
3. EKS → namespace `techx-tf1` → Workloads/Pods; giữ Desired/Ready/Available và
   trạng thái pod. Chụp `11c-runtime-health.png`.
4. EKS → Events; giữ warning history và time. Chụp `11d-warning-events.png`;
   không che các warning rollout cũ.
5. Jaeger → Trace ID `8116e5b4dfe5706856449f1a31e6f299`; mở waterfall và
   checkout PlaceOrder span. Chụp `12a-jaeger-trace.png`.
6. Grafana Explore → OpenSearch → filter cùng trace ID; giữ timestamp, service,
   spanId và body, nhưng che user/order/network data. Chụp
   `12b-opensearch-trace-logs.png`.
7. Grafana Explore → Prometheus exemplar query; chụp empty result với time
   window thành `12c-prometheus-exemplar-blocked.png`.

## 12. Authoritative screenshot manifest for Prompt 8

At the 2026-07-22 audit, **none of these PNG files exists**. The operator must
capture them from AWS/Grafana/Jaeger/Argo/GitHub; expected filenames are not
evidence. Every frame must show the UTC time picker/window and relevant scope.

| File | Caption — what it proves | Number/state to read | Window | Raw evidence |
|---|---|---|---|---|
| `01-scope-identity.png` | Correct read-only AWS/EKS scope; account text redacted | region `us-east-1`, cluster `ecommerce-dev-eks`, namespace `techx-tf1` | capture timestamp visible | `01-scope-identity.txt` |
| `02-top-driver-before.png` | Account-wide non-compute Usage Quantity ranking | Regional transfer `357.6794858022 GB`; NAT `61.9773010455 GB`; warning that scope is account-wide | CE 2026-07-15 to 2026-07-22, end exclusive 07-23 | `02-noncompute-usage-before.json` |
| `03a-ebs-before.png` | No available EBS in audited scope | 9 in-use, 0 available | inventory capture time | `03-orphans-before.json` |
| `03b-eip-before.png` | EIPs are associated | allocation plus association columns; no unassociated scoped EIP | inventory capture time | `03-orphans-before.json` |
| `03c-snapshots-before.png` | Self-owned snapshot inventory | 0 snapshots | inventory capture time | `03-orphans-before.json` |
| `03d-amis-before.png` | Self-owned AMI inventory | 0 AMIs | inventory capture time | `03-orphans-before.json` |
| `03e-load-balancers-before.png` | Active LB inventory | state/type/VPC and associations | inventory capture time | `03-orphans-before.json` |
| `03f-target-groups-before.png` | Three TGs are empty but not proven orphan | names, VPC, zero targets/listener refs; caption UNKNOWN/HOLD | inventory capture time | `03-orphan-dependency-audit.txt` |
| `04-orphans-after.png` | Same-scope post-approved-cleanup inventory | exact approved IDs absent and no confirmed orphan remaining | same filters after cleanup | missing `04-orphans-after.json` |
| `05a-ebs-gp3.png` | Scoped EBS type/size/attachment | 9/9 `gp3`, attached | storage capture time | `05-storage-baseline.json` |
| `05b-pvc-usage.png` | Right-size headroom basis | Prometheus ~25.9%; OpenSearch ~76.8% used | same instant/table timestamp | `05-storage-prompt4-audit.txt` |
| `06a-cloudtrail-lifecycle.png` | Audit bucket lifecycle is finite | Enabled; Glacier IR 90d; expiry 2555d | lifecycle capture time | `06-lifecycle-baseline.json` |
| `06b-terraform-state-lifecycle-gap.png` | Shared state bucket control gap | no lifecycle/versioning status; ownership warning | lifecycle capture time | `05-storage-prompt4-audit.txt` |
| `06c-dlm-baseline.png` | Snapshot lifecycle inventory | 0 DLM policies and 0 current self snapshots | lifecycle capture time | `06-lifecycle-baseline.json` |
| `07a-nat-cloudwatch-before.png` | NAT bytes/connections baseline | source `180538445 B`, destination `4903817398 B` for Prompt 5 window | 2026-07-21T08:22:17Z–2026-07-22T08:22:17Z | `07-data-transfer-prompt5.txt` |
| `07b-network-usage-before.png` | Billing usage baseline without mixed-unit sum | NAT `61.9773010455 GB`, `158 Hrs`; xAZ out/in `1.603371047/1.2116824725 GB` | CE 2026-07-15..22, end exclusive 07-23 | `07-network-before.json` |
| `08a-vpc-endpoints-before.png` | No S3/ECR AWS service endpoint before | `awsServiceEndpointsFoundForS3Ecr=0` | endpoint inventory timestamp | `08-vpc-endpoints.json` |
| `08b-s3-endpoint-after.png` | S3 Gateway Endpoint runtime after rollout | endpoint type Gateway, state available, correct VPC/service | after rollout timestamp | runtime raw file missing |
| `08c-private-route-after.png` | Only intended private egress route gains S3 prefix-list route | route table ID/prefix list/endpoint; NAT default route retained | after rollout timestamp | runtime raw file missing |
| `09a-telemetry-rate-before.png` | OTel ingestion/fan-out baseline | accepted spans `16.5449/s`, logs `0.7655/s`; exporter counter caveat | 5m ending 2026-07-22T08:45–08:54Z | `09-telemetry-prompt6-before.txt` |
| `09b-prometheus-series-before.png` | Active series/cardinality baseline | `230879` series; top label/family values | same capture window | `09-telemetry-prompt6-before.txt` |
| `09c-opensearch-size-before.png` | Daily log growth and storage pressure | `8004309801 B`, filesystem 77%, daily index rows | 2026-07-16..22 | `09-telemetry-prompt6-before.txt` |
| `09d-opensearch-retention-gap.png` | Runtime retention gap | 0 ISM policies, 0 managed log indices | capture timestamp | `09-telemetry-prompt6-before.txt` |
| `09e-cloudwatch-retention-before.png` | Independent AWS log retention | CloudTrail 90d, EKS 7d, audit Lambda 30d, MSK 3d; two unset gaps | capture timestamp | `09-telemetry-prompt6-before.txt` |
| `09f-slo-before.png` | Pre-change SLO/load reference | baseline request rate `4.6500059723/s`; idle p95 shown honestly | exact 5m/24h picker used in raw | `11-slo-baseline.txt` |
| `10a-otel-daemonset-after.png` | OTel rollout stability | 7/7 Ready and rendered runtime pipelines without debug | after rollout timestamp | missing `10-telemetry-after.txt` |
| `10b-opensearch-ism-after.png` | Finite operational log retention is active | policy `otel-logs-retention`, pattern only `otel-logs-*`, age 3d | after owner-approved rollout | missing `10-telemetry-after.txt` |
| `10c-telemetry-comparison-after.png` | Equal-window telemetry delta | accepted/refused/exported rates plus bytes/series before vs after | same workload and duration as 09 | missing `10-telemetry-after.txt` |
| `10d-slo-after.png` | Telemetry change preserved SLO | success thresholds, p95 <1s and comparable request rate | same workload/5m window | missing `10-telemetry-after.txt` |
| `11a-slo-final-verification.png` | Current SLO result, including failure | checkout/browse/cart 100%; p95 15000 ms; volume 5.5083/s | 5m around 2026-07-22T09:07:54Z | `11-slo-final-verification.txt` |
| `11b-storefront-p95-failure.png` | 15s is backed by non-empty histogram buckets | rates at le=1000/5000/10000/15000/+Inf | same 5m window | `11-slo-final-verification.txt` |
| `11c-runtime-health.png` | Current workload health | all deployments available; OpenSearch 1/1; OTel 7/7 | verification timestamp | `11-slo-final-verification.txt` |
| `11d-warning-events.png` | Historical warnings are disclosed | preStop/startup-probe/HPA warning timestamps and current recovery | events at ~43–58m before capture | `11-slo-final-verification.txt` |
| `12a-jaeger-trace.png` | Real request trace remains investigable | trace `8116…f299`, 51 spans, checkout PlaceOrder | trace at 2026-07-22T08:28:58Z | `12-investigation-drill.txt` |
| `12b-opensearch-trace-logs.png` | Same trace reaches service logs | 18 hits; same checkout span; payload identifiers redacted | same trace timestamp | `12-investigation-drill.txt` |
| `12c-prometheus-exemplar-blocked.png` | Direct metric→trace exemplar is missing | `data=[]`, query and time range visible | 1h ending drill capture | `12-investigation-drill.txt` |
| `13-top-driver-after.png` | Same-Usage-Type reduction after finalized window | exact before/after/delta for the selected Usage Type | equal finalized CE duration/scope | missing `13-noncompute-usage-after.json` |
| `14a-terraform-plan.png` | Protected plan safety | exact add/change/destroy/replace counts, zero unexpected destroy/replace | PR commit SHA | `14-pr-readiness-audit.txt`; complete plan absent |
| `14b-pr-ci-review.png` | Delivery governance | PR URL/SHA, required checks green, reviewer approval | PR capture timestamp | missing `14-pr-ci.txt` |

Images must not be captured until the corresponding runtime state exists.
Never reuse a before screenshot as after evidence.
