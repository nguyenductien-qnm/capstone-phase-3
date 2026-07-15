# Screenshot checklist 01–12

Đặt ảnh do bạn tự chụp vào thư mục này. Bảng dưới đây mô tả chính xác nội dung mentor cần nhìn thấy.

| # | Tên file | Nội dung bắt buộc trong ảnh | Không được nhầm với |
|---|---|---|---|
| 01 | `01-terraform-validate.png` | `terraform validate` trả `Success! The configuration is valid.` | Chỉ chụp `terraform fmt` |
| 02 | `02-terraform-plan.png` | Audit resources đúng scope, tổng kết add/change/destroy; không replace audit bucket ngoài dự kiến | Plan chứa secret/tfvars |
| 03 | `03-eks-audit-enabled.png` | EKS logging `enabled=true`, có `api`, `audit`, `authenticator` | Terraform default chưa apply |
| 04 | `04-cloudwatch-audit-stream.png` | Log group `/aws/eks/<cluster>/cluster`, retention và stream `kube-apiserver-audit-*` có event gần đây | Chỉ chụp log group trống |
| 05 | `05-k8s-forensic-timeline.png` | ConfigMap demo có `create`, `patch`, `delete`; username, timestamp, object, source IP, user agent, response code, audit ID | Event application/flagd |
| 06 | `06-cloudtrail-status.png` | `IsLogging=true`, multi-region/global events/validation, management read/write selector | Chỉ chụp tên trail |
| 07 | `07-cloudtrail-user-identity.png` | CloudTrail assumed-role session `gha-<actor>-<run_id>` và GitHub run tương ứng | Run cũ không có custom session name |
| 08 | `08-s3-log-protection.png` | Versioning `Enabled`, encryption, bốn Public Access Block flag `true`; Object Lock status nếu có | Ghi Object Lock PASS khi đang tắt |
| 09 | `09-cloudtrail-validation.png` | `validate-logs` thành công trên khoảng thời gian nhỏ, không có invalid digest/log | Chỉ chụp validation enabled |
| 10 | `10-pr-jira-review.png` | PR/Jira, owner, plan/diff, tests, rollback, approval và CI checks | PR chưa approval |
| 11 | `11-argocd-git-correlation.png` | Application health/sync revision, `git show` cùng SHA, PR và Jira liên quan | Để `N/A` dù hệ thống dùng ArgoCD |
| 12 | `12-operator-explicit-deny.png` | Operator policy attachment và IAM Simulator trả `explicitDeny` cho stop/delete | `implicitDeny` hoặc gửi lệnh destructive thật |

## Redaction

- Được che phần giữa account ID/ARN nếu mentor không cần account cụ thể.
- Phải giữ role name, GitHub session, Kubernetes username, verb, resource, timestamp và audit ID để chứng minh attribution.
- Không chụp access key, session token, GitHub secret, private key hay nội dung tfvars.

