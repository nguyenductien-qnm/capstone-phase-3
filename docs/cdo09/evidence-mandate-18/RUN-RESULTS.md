# MANDATE-18 run results

## Session metadata

- Date: `2026-07-22`.
- AWS profile: `phase3-cdo`; account/caller redacted.
- Region/environment: `us-east-1` / `dev`.
- Cluster/namespace: `ecommerce-dev-eks` / `techx-tf1`.
- Git base/branch: `develop@2376042` / `feat/mandate-18`.
- Jira: PM xử lý riêng, không phải gate của evidence pack này.

## Prompt 1

PASS: Git baseline, SSO identity, EKS scope/read access, five-area code audit và evidence scaffold.

## Prompt 2 — baseline trước thay đổi

| # | Hạng mục được yêu cầu | Kết quả thu thập | Bằng chứng/giới hạn |
|---|---|---|---|
| 1 | EBS/EIP/snapshot/AMI/LB/TG inventory | PASS | 9 EBS in-use; EIP/LB in-use; 0 self snapshot/AMI; 3 TG cần review |
| 2 | EBS type/size/attachment + PVC usage | PASS | 9/9 gp3; OpenSearch 76.77%; Prometheus 25.43% |
| 3 | NAT bytes/connections | PASS | CloudWatch 24h có bytes, connections, timeouts, errors/drops |
| 4 | Cost Explorer non-compute Usage Type | PARTIAL | Query/ranking thật; scope account-wide do tag TF không khả dụng |
| 5 | Telemetry ingestion/spans/series/cardinality | PASS | OTel rates, 221,060 active series, top-10 cardinality có thật |
| 6 | OpenSearch size/retention | PASS | 8,001,615,825 bytes; 0 ISM policies/managed indices — control hiện là GAP |
| 7 | Grafana SLO baseline | PASS | 5m success 100%; 24h budgets 100%; p95 1h/24h dưới 1s; 5m p95 idle/NaN được giữ nguyên |
| 8 | Raw output + redaction | PASS | 9 raw files; account ID/identity/KMS ARN đã redact |
| 9 | Hướng dẫn màn hình/tên ảnh | PASS | `screenshots/README.md` có navigation, filter, window, filename |
| 10 | Safety + unit discipline + top-driver proposal | PASS | Không mutation; không cộng mixed units; driver có qualification |

### Tỷ lệ hoàn thành Prompt 2

- Công thức công khai: `PASS = 1`, `PARTIAL = 0.5`, `GAP/PENDING = 0` trên 10 hạng mục ở bảng trên.
- Kết quả: `9 PASS + 1 PARTIAL = 9.5/10 = 95%` data-collection completion.
- Đây là tỷ lệ hoàn thành Prompt 2, không phải tỷ lệ compliance toàn Mandate 18.

## Top-driver proposal

`EC2 - Other / DataTransfer-Regional-Bytes = 357.6794858022 GB` là hàng lớn nhất trong nhóm cùng unit `GB`. `NatGateway-Bytes = 61.9773010455 GB` và cross-AZ in/out là các sub-driver phù hợp để điều tra. Không so tổng này với `GB-Month`, `Hrs`, `Events` hay `Requests`.

Kết luận vẫn là `PARTIAL`: Cost Explorer chưa có tag filter usable cho `Project=ecommerce`, nên chưa được tuyên bố toàn bộ 357.68 GB thuộc TF/namespace này.

## Safety statement

Không Terraform apply, không sửa AWS/Kubernetes, không xóa resource, không tạo traffic, không tạo evidence after giả. Các port-forward local chỉ dùng để đọc API và đã đóng sau truy vấn.

## Prompt 3 — orphan dependency audit

| # | Audit gate | Kết quả |
|---|---|---|
| 1 | Scope/account/region/EKS/namespace | PASS |
| 2 | Target Group config/tags/attributes/health | PASS |
| 3 | Load Balancer/listener/rule references | PASS |
| 4 | VPC/project ownership signals | PASS |
| 5 | CloudTrail history trong cửa sổ khả dụng | PASS |
| 6 | Tracked repository và remote Terraform state | PASS |
| 7 | CloudFormation resources | PASS |
| 8 | Kubernetes Service/Ingress/TGB/controller | PASS |
| 9 | Backup, blast radius, recreate và inert delete command | PASS |
| 10 | Redaction/safety/no-after-evidence validation | PASS |

Prompt 3 audit completion: `10/10 = 100%`. Đây là completion của audit, không phải cleanup compliance.

Classification:

- `KEEP`: none.
- `DELETE_CANDIDATE`: none.
- `UNKNOWN/HOLD`: `123123321`, `89345789437843`, `testt`.

Cả ba được tạo ngày `2026-07-15` bởi một SSO user khác và không có owner tag. Hai target group đầu thuộc project VPC nhưng ownership vẫn chưa xác nhận. `testt` thuộc default VPC ngoài project. Vì vậy không có deletion và acceptance “không còn orphan sau cleanup” vẫn `PENDING`.

## Prompt 4 — storage

| # | Yêu cầu | Kết quả | Ghi chú |
|---|---|---|---|
| 1 | Xác minh EBS gp3 trong scope | PASS | 9/9 volumes gp3, in-use; attachment instances đều thuộc cluster |
| 2 | Right-size với headroom, không shrink in-place | PASS | PVC và node root usage thật; 12 GiB Prometheus/30 GiB main-root là conditional migration candidates |
| 3 | Snapshot lifecycle/DLM | PASS audit / GAP control | 0 self snapshots và 0 DLM; không tạo snapshot policy gây cost ngoài scope |
| 4 | S3 lifecycle/tiering | PASS audit / PARTIAL control | CloudTrail lifecycle khớp code/runtime; shared state bucket thiếu tags/versioning/lifecycle |
| 5 | Code control và runtime gap | PASS | Matrix ghi trong `logs/05-storage-prompt4-audit.txt` |
| 6 | Thay đổi Terraform nhỏ nhất | PASS | Chỉ xóa stale provider lock entry; không có AWS resource change chưa plan |
| 7 | fmt, validate và plan safety | PARTIAL | fmt/validate PASS; plan BLOCKED trước planning do thiếu 28 protected tfvars |
| 8 | Rollback và AWS/Grafana screenshot checklist | PASS | `storage-rightsize-plan.md` và `storage-console-checklist.md` |

Tỷ lệ Prompt 4:

- Strict PASS: `7/8 = 87.5%`.
- Weighted completion (`PARTIAL = 0.5`): `7.5/8 = 93.75%`.
- Không được làm tròn thành 100% vì chưa có complete plan và chưa thể chứng minh zero unexpected destroy/replace.

Không apply. Không EBS/PVC/S3/DLM resource nào bị thay đổi.

## Prompt 5 — data transfer

| # | Yêu cầu | Kết quả | Ghi chú |
|---|---|---|---|
| 1 | NAT bytes/hours và cross-AZ before | PASS | CloudWatch 24h và Cost Explorer Usage Quantity đã lưu |
| 2 | Xác định AWS service traffic qua NAT | PARTIAL | ECR/S3/API dependency và route được chứng minh; per-service bytes blocked vì VPC Flow Logs chưa có |
| 3 | S3 Gateway Endpoint design định lượng | PASS | Không fixed hourly charge; đúng private egress route scope |
| 4 | Đánh giá ecr.api/ecr.dkr/interface endpoints | PASS | HA fixed estimate ~$43.80/month; break-even ~1251 GB/month, nên không thêm |
| 5 | Reusable Terraform module, route/SG/private DNS scope | PASS | Gateway module; private app/MQ route only; SG/private DNS N/A; NAT giữ nguyên |
| 6 | fmt, validate và module plan test | PASS | fmt/validate PASS; mocked plan 1 passed/0 failed |
| 7 | Full root plan và destroy/replace review | PARTIAL | Blocked trước resource plan do thiếu 28 protected tfvars |
| 8 | Runtime rollout/endpoint available | PENDING | Không apply khi chưa có full safe plan |
| 9 | Image pull/API/SLO và usage after | PENDING | Không tạo after-evidence giả |
| 10 | ADR, rollout và rollback runbook | PASS | ADR định lượng và runbook có evidence names |

Tỷ lệ Prompt 5:

- Strict PASS: `6/10 = 60%`.
- Weighted completion (`PARTIAL = 0.5`): `7/10 = 70%`.
- Prompt 5 chưa `done`: rollout và after verification còn PENDING.

Không xóa NAT, không targeted apply, không AWS/Kubernetes mutation.

## Prompt 6 - telemetry

| # | Requirement | Result | Evidence / limit |
|---|---|---|---|
| 1 | Logs/bytes over time and OpenSearch growth | PASS | Seven daily indices with real docs/bytes; filesystem 77% used |
| 2 | Accepted/exported spans and logs per second | PASS | Real Prometheus 5m rates; exporter fan-out interpretation recorded |
| 3 | Active series and top cardinality labels | PASS | 230879 active series and top-15 label names/families |
| 4 | Current retention | PASS | Prometheus, OpenSearch ISM, and six AWS log groups audited |
| 5 | Inspect topology and choose sampling safely | PASS | 7-agent DaemonSet, Local Service; no unsafe sampling added |
| 6 | Minimal retention/debug/noise implementation | PASS code / PENDING runtime | Sandbox-only exporter overrides plus 3d otel-logs ISM policy |
| 7 | Preserve errors, audit/security, SLO dashboard/alerts | PASS code / PENDING runtime | No sampling; spanmetrics/Jaeger/OpenSearch retained; AWS log groups excluded |
| 8 | Helm lint, render, and manifest validation | PASS | Helm lint 0 failures; full render and kubectl client dry-run pass |
| 9 | Rollback and screenshot/evidence checklist | PASS | ADR and two-stage rollout runbook created |
| 10 | Rollout, equal workload/window, after comparison | PENDING | No apply/Argo sync/workload run; no fake after-evidence |

Prompt 6 completion:

- Strict PASS: `7/10 = 70%`.
- Weighted completion (`PASS code / PENDING runtime = 0.5`):
  `(7 + 0.5 + 0.5) / 10 = 80%`.
- Runtime compliance is not 100% until rollout and equal-window after evidence.

Safety: no Helm upgrade, Argo sync, kubectl mutation, OpenSearch policy write,
index deletion, or workload generation was performed.

## Prompt 7 - final verification

| # | Gate | Result |
|---|---|---|
| 1 | Checkout success >=99% | PASS - 100% |
| 2 | Browse/cart success >=99.5% | PASS - both 100% |
| 3 | Storefront p95 <1s | FAIL - 15000 ms with non-empty buckets |
| 4 | Request volume comparable to baseline | PASS with stated +/-20% assumption - +18.4588% |
| 5 | Pod/deployment healthy | PASS - all desired/ready/available; DS 7/7; STS 1/1 |
| 6 | No ImagePullBackOff or AWS API credential errors | PASS in current events and scanned 15m/30m logs |
| 7 | Metric/dashboard -> Jaeger -> log drill | PARTIAL - 51-span trace and 18 logs correlate; exemplar data absent |
| 8 | Raw evidence and screenshot checklist | PASS |

Prompt 7 completion:

- Strict PASS: `6/8 = 75%`.
- Weighted completion (`PARTIAL = 0.5`): `6.5/8 = 81.25%`.
- Prompt 7 is not complete because storefront p95 fails and the direct metric
  exemplar hop is blocked.

No runtime mutation or synthetic after-evidence was created.

## Prompt 8 - evidence-pack audit

| # | Audit deliverable | Result |
|---|---|---|
| 1 | Inventory required documents/raw evidence | PASS |
| 2 | README and mentor-facing mandate report current | PASS |
| 3 | Every directive requirement mapped to raw log and screenshot | PASS mapping |
| 4 | Implementation plan, ADR and runbooks current | PASS |
| 5 | Every screenshot has caption/number/window/raw source | PARTIAL - manifest complete, but 0 PNG captured |
| 6 | Video/demo script is evidence-driven | PASS |
| 7 | Same-unit/workload before/after delta | PARTIAL - SLO volume delta computed; AWS/telemetry after data absent |
| 8 | Account/secret/redaction scan | PASS - no known account ID, access-key/token/private-key pattern found |
| 9 | Terraform/Helm/plan safety audit | PARTIAL - fmt/validate/module test/Helm pass; full root plan blocked by backend S3 403 |
| 10 | Strict mentor review and complete missing-evidence list | PASS |

Prompt 8 completion:

- Strict PASS: `7/10 = 70%`.
- Weighted completion (`PARTIAL=0.5`): `8.5/10 = 85%`.
- Evidence-pack documentation is audited, but the pack is not submission-ready.

Separate Mandate 18 compliance remains strict `0/5 PASS`, weighted `30%`.
The principal gaps are actual screenshots, owner/destructive approvals,
protected Terraform plan, runtime rollout, equal-window after usage, storefront
p95 remediation, exemplar evidence, and PR/CI/reviewer proof.
