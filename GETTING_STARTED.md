# Getting Started - build & deploy TechX Corp Platform

Mục tiêu: đưa hệ thống từ source lên chạy trên cluster Kubernetes trong account của TF, với image do chính TF build và đẩy lên ECR của mình. Dựng được hệ thống chính là bước tiếp quản đầu tiên.

## 0. Chuẩn bị

- Một cluster Kubernetes trong account của TF (EKS khuyến nghị) + `kubectl` trỏ đúng cluster.
- `docker` (có `buildx` + QEMU cho multi-arch), `helm` v3, `aws` CLI đã đăng nhập account của TF.
- Đủ quyền tạo ECR repo trong account của TF.

Có 2 đường đưa image vào cluster. **Khuyến nghị đường A** (build từ source) vì chính CI/CD + platform là kỹ năng được chấm; đường B chỉ để bootstrap nhanh.

---

## 1A. Build từ source → ECR của TF (khuyến nghị)

```sh
REG=<ACCOUNT>.dkr.ecr.<REGION>.amazonaws.com/techx-corp

# 1. Tạo ECR repo + login
aws ecr create-repository --repository-name techx-corp --region <REGION>
aws ecr get-login-password --region <REGION> | docker login --username AWS \
  --password-stdin <ACCOUNT>.dkr.ecr.<REGION>.amazonaws.com

# 2. Trỏ image registry sang ECR của TF
#    Sửa techx-corp-platform/.env.override:  IMAGE_NAME=$REG   (giữ IMAGE_VERSION=1.0)

# 3. Build + push toàn bộ app image
./scripts/build/build-push-images.sh
```

`build-push-images.sh` build multi-arch (amd64+arm64) toàn bộ app image theo `IMAGE_NAME` trong `.env.override` rồi push. Nó smoke-build 1 service Go trước để bắt lỗi sớm.

> Lưu ý: chỉ **các app image** cần vào ECR của TF. flagd / postgres / collector / grafana / opensearch... pull từ registry public gốc - TF không cần đẩy.

## 1B. Bootstrap nhanh từ image seed (tuỳ chọn)

BTC cấp một image seed public để khởi động. Pull → retag → push sang ECR của TF:

```sh
REG=<ACCOUNT>.dkr.ecr.<REGION>.amazonaws.com/techx-corp
for s in accounting ad cart checkout currency email fraud-detection \
         frontend frontend-proxy image-provider kafka llm load-generator payment \
         product-catalog product-reviews quote recommendation shipping; do
  docker pull  nghiadaulau/techx-corp:1.0-$s
  docker tag   nghiadaulau/techx-corp:1.0-$s $REG:1.0-$s
  docker push  $REG:1.0-$s
done
```

`nghiadaulau` chỉ là seed khởi đầu, không phải registry cố định - TF vận hành trên ECR của mình.

---

## 2. Chuẩn bị chart

```sh
helm repo add open-telemetry https://open-telemetry.github.io/opentelemetry-helm-charts
helm repo add grafana https://grafana.github.io/helm-charts
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add jaegertracing https://jaegertracing.github.io/helm-charts
helm repo add opensearch https://opensearch-project.github.io/helm-charts
helm dependency build ./platform/charts/application
```

## 3. Deploy lên cluster của TF

```sh
NS=techx-<tf>          # namespace của TF, vd techx-tf1

helm upgrade --install techx-corp ./platform/charts/application -n $NS --create-namespace \
  --set default.image.repository=$REG \
  -f platform/gitops/environments/sandbox/values-observability.yaml \
  -f platform/gitops/environments/sandbox/values-flagd-sync.yaml
```

Các values file mẫu trong `platform/gitops/environments/sandbox/` (điểm khởi đầu, tune theo nhu cầu):

| File | Dùng để |
|---|---|
| `values-observability.yaml` | Bật stack observability (collector, metrics, logs, traces, dashboards) |
| `values-app-stamp.yaml` | Chạy app-only (khi observability tách riêng) |
| `values-flagd-sync.yaml` | **Bắt buộc**: cắm flagd của TF vào nguồn cấu hình trung tâm (xem mục 5) |
| `values-aio-llm.yaml` | (AIO) cắm LLM thật thay mock cho `product-reviews` |
| `platform/policies/resource-governance/quota.yaml` | ResourceQuota mẫu cho namespace |

### AIO - cắm LLM thật

```sh
kubectl -n $NS create secret generic llm-api-key --from-literal=key=<REAL_KEY>
helm upgrade ... -f platform/gitops/environments/sandbox/values-aio-llm.yaml   # ghép thêm vào lệnh deploy
```

## 4. Kiểm tra hệ thống đã sống

```sh
kubectl -n $NS get pods                 # tất cả Running/Ready
kubectl -n $NS port-forward svc/frontend-proxy 8080:8080
```

- Mở `http://localhost:8080` → storefront hiện sản phẩm.
- Mở một sản phẩm → phần review có tóm tắt do AI sinh.
- Grafana / Jaeger qua `frontend-proxy` để xem metrics/traces/logs.

## 5. flagd - cấu hình sự cố (đọc kỹ)

Hệ thống dùng `flagd` để bật/tắt các nhánh hành vi. Trong Phase 3, **nguồn flag do BTC giữ tập trung**: flagd của TF được cấu hình **sync read-only** từ một endpoint trung tâm qua `values-flagd-sync.yaml`. BTC sẽ cấp cho TF một `TOKEN` để điền vào file này (thay `<TOKEN>`).

- Đây là cách BTC bơm sự cố vào hệ thống của bạn trong lúc vận hành. Việc của bạn là **làm hệ thống chịu được** (fallback, retry, containment), không phải tắt flagd.
- **Không** gỡ, đổi hướng, hay vô hiệu hóa flagd và các hook đọc flag trong service. Đây là hạ tầng được bảo vệ - vi phạm = disqualify (xem RULES - mục Luật chơi). BTC có kiểm tra định kỳ.

## Sự cố thường gặp khi dựng

- **Image pull lỗi**: kiểm tra `default.image.repository` trỏ đúng ECR của TF và node có quyền pull ECR.
- **`helm dependency build` lỗi**: chạy đủ các `helm repo add` ở mục 2 trước.
- **Pod CrashLoopBackOff**: xem `kubectl -n $NS logs <pod>` - thường do thiếu secret (AIO llm-api-key) hoặc dependency (postgres/valkey/kafka) chưa Ready.
- **Mỗi lần `helm upgrade` để deploy cải tiến**: nhớ ghép lại `-f platform/gitops/environments/sandbox/values-flagd-sync.yaml`, nếu không flagd sẽ rớt về cấu hình local và mất kết nối nguồn trung tâm.
