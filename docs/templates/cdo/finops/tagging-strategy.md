# Tagging Strategy cho Phase 3 - TechX Corp

## Mục đích

Tài liệu này định nghĩa chiến lược tagging/labeling chuẩn cho task CDO-39 nhằm bảo đảm mọi tài nguyên AWS và Kubernetes mới của TechX Corp có thể truy vết được owner, nhóm phụ trách, service, environment và cost center. Chiến lược này hỗ trợ hai trụ chính của TF1/CDO09: Reliability và Cost Optimization.

## Phạm vi áp dụng

Áp dụng cho các tài nguyên mới phát sinh trong Phase 3 thuộc dự án TechX Corp, bao gồm:

- AWS resources được quản lý bằng Terraform hoặc công cụ IaC tương đương.
- Kubernetes resources được render từ Helm chart `techx-corp-chart`.
- Workload metadata như Deployment, Service, ConfigMap và Pod template.

Task này không tạo AWS resources mới, không deploy lên AWS/EKS và không thay đổi business logic của ứng dụng.

## Required AWS Tags

| Tag | Giá trị bắt buộc | Ý nghĩa |
|---|---|---|
| Project | `techx-corp` | Dự án sở hữu tài nguyên |
| TaskForce | `TF1` | Task Force phụ trách |
| Group | `CDO09` | Nhóm vận hành |
| Environment | `phase3` | Môi trường triển khai |
| Owner | `finops-iac` | Nhóm/chức năng chịu trách nhiệm |
| CostCenter | `techx-phase3` | Cost center để phân bổ chi phí |
| ManagedBy | `terraform/helm` | Công cụ quản lý tài nguyên |
| Pillar | `cost-optimization` | Trụ tối ưu chính |
| Service | `<service-name>` | Service hoặc component sở hữu tài nguyên |

## Required Kubernetes Labels

| Label | Giá trị bắt buộc | Ý nghĩa |
|---|---|---|
| `techx.io/project` | `techx-corp` | Dự án sở hữu resource |
| `techx.io/taskforce` | `tf1` | Task Force phụ trách |
| `techx.io/group` | `cdo09` | Nhóm vận hành |
| `techx.io/environment` | `phase3` | Môi trường triển khai |
| `techx.io/owner` | `finops-iac` | Owner vận hành/IaC |
| `techx.io/cost-center` | `techx-phase3` | Cost center |
| `techx.io/pillar` | `cost-optimization` | Trụ tối ưu chính |
| `techx.io/managed-by` | `helm` | Công cụ render resource |
| `techx.io/service` | `<service-name>` | Service/component sở hữu resource |
| `app.kubernetes.io/part-of` | `techx-corp` | Chuẩn Kubernetes app label |
| `app.kubernetes.io/managed-by` | `Helm` | Chuẩn Kubernetes app label |

## Quy tắc triển khai

- Kubernetes labels chuẩn được cấu hình tại `techx-corp-chart/values.yaml` trong block `global.finops.labels`.
- Helm helper `techx-corp.finopsLabels` render các label dùng chung và tự động thêm `techx.io/service`.
- Với component trong `.Values.components`, `techx.io/service` dùng tên component từ context `.name`.
- Với resource cấp chart không gắn với component cụ thể, `techx.io/service` mặc định là `platform`.
- Deployment, Service, ConfigMap và Pod template phải nhận được bộ label `techx.io/*` khi render từ Helm.

## Quy tắc bắt buộc

- Không sửa `selectorLabels` nếu không cần thiết để tránh lỗi immutable selector khi Helm upgrade.
- Không thay đổi tên release, chart, service hoặc component.
- Không xóa hoặc vô hiệu hóa flagd/OpenFeature hooks.
- Không thay đổi business logic của ứng dụng.
- Không hard-code sai service label; phải ưu tiên tên component đang render.
- Không tạo AWS resources mới và không deploy lên AWS/EKS trong phạm vi task CDO-39.
- Mọi thay đổi tagging/labeling phải có evidence và ghi vào change log.

## Cách kiểm tra bằng helm template

Chạy render local:

```bash
helm template techx-corp ./techx-corp-chart -n techx-tf1 > /tmp/rendered.yaml
```

Kiểm tra các label bắt buộc:

```bash
grep -n "techx.io/project" /tmp/rendered.yaml
grep -n "techx.io/group" /tmp/rendered.yaml
grep -n "techx.io/service" /tmp/rendered.yaml
grep -n "techx.io/cost-center" /tmp/rendered.yaml
```

Trên Windows PowerShell:

```powershell
Select-String -Path $env:TEMP\rendered.yaml -Pattern "techx.io/project","techx.io/group","techx.io/service","techx.io/cost-center"
```

## Cách kiểm tra trên Kubernetes sau khi deploy

Sau khi có môi trường Kubernetes hợp lệ và đã deploy bằng quy trình được phê duyệt, kiểm tra labels:

```bash
kubectl get deploy,svc,cm -n techx-tf1 --show-labels | grep "techx.io/"
kubectl get pods -n techx-tf1 --show-labels | grep "techx.io/"
```

Kiểm tra một resource cụ thể:

```bash
kubectl get deploy frontend -n techx-tf1 -o jsonpath='{.metadata.labels}'
kubectl get deploy frontend -n techx-tf1 -o jsonpath='{.spec.template.metadata.labels}'
```

## Evidence cần chụp cho Jira

- Screenshot hoặc log `helm lint ./techx-corp-chart`.
- Screenshot hoặc log `helm template techx-corp ./techx-corp-chart -n techx-tf1`.
- Kết quả kiểm tra `techx.io/project`, `techx.io/group`, `techx.io/service`, `techx.io/cost-center` trong rendered manifest.
- Diff các file Helm đã sửa: `values.yaml`, `_helpers.tpl`, `_objects.tpl`, `component.yaml`.
- Link hoặc screenshot tài liệu `docs/finops/tagging-strategy.md` và `docs/finops/change-log.md`.

## Owner

- Nguyễn Tấn Huy
- FinOps/IaC Engineer
- TF1 / CDO09
