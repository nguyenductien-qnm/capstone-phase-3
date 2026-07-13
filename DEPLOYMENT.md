# 🚀 Hướng dẫn Deploy — TechX-Corp Capstone Phase 3

> **Stack:** AWS EKS · RDS PostgreSQL · MSK Kafka · ElastiCache Valkey · ECR · ArgoCD · Terraform

---

## 📋 Yêu cầu công cụ

| Công cụ | Phiên bản |
|---|---|
| Terraform | >= 1.9 |
| AWS CLI | >= 2.x |
| kubectl | >= 1.28 |
| Docker | >= 24 |
| Helm | >= 3.x |
| Git | bất kỳ |

---

## 1. Chuẩn bị môi trường

### 1.1 Đăng nhập AWS SSO

```bash
aws sso login --profile Phase3-Mentor-PermissionSet-804372444787
export AWS_PROFILE=Phase3-Mentor-PermissionSet-804372444787
```

### 1.2 Clone repository và checkout branch

```bash
git clone https://github.com/nguyenductien-qnm/capstone-phase-3.git
cd capstone-phase-3
git checkout feat/app-migration
```

---

## 2. Provision hạ tầng AWS bằng Terraform

### 2.1 Khởi tạo Terraform

```bash
cd terraform/environments/sandbox
terraform init
```

### 2.2 Kiểm tra plan

```bash
terraform plan
```

### 2.3 Apply theo thứ tự module

> ⚠️ Các module có dependency — nên apply theo thứ tự sau.

```bash
# Bước 1: VPC
terraform apply -target=module.vpc -auto-approve

# Bước 2: EKS + ECR (song song)
terraform apply -target=module.eks -target=module.ecr -auto-approve

# Bước 3: RDS + ElastiCache + MSK (song song, cần VPC + EKS trước)
terraform apply -target=module.rds -target=module.elasticache -target=module.msk -auto-approve

# Bước 4: CloudFront (cần có NLB DNS trước — xem lưu ý bên dưới)
terraform apply -target=module.cloudfront -auto-approve

# Hoặc apply tất cả cùng lúc (Terraform tự resolve dependency)
terraform apply -auto-approve
```

> 💡 **Thời gian ước tính:**
> - VPC: ~2 phút
> - EKS: ~15 phút
> - RDS: ~10 phút
> - MSK: ~20 phút (rolling update nếu update config)
> - ElastiCache: ~5 phút

### 2.4 Lấy thông tin outputs

```bash
terraform output
```

Các giá trị quan trọng:
- `eks_update_kubeconfig_command` — lệnh cấu hình kubectl
- `ecr_repository_urls` — URL ECR để push Docker image
- `msk_bootstrap_brokers_sasl_scram` — broker string MSK
- `valkey_primary_endpoint` — endpoint Valkey
- `db_primary_endpoint` — endpoint RDS PostgreSQL

---

## 3. Build & Push Docker Images lên ECR

```bash
# Đăng nhập ECR
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin \
  804372444787.dkr.ecr.us-east-1.amazonaws.com

# Build và push từng service (ví dụ: product-catalog)
cd techx-corp-platform/src/product-catalog
docker build -t 804372444787.dkr.ecr.us-east-1.amazonaws.com/ecommerce-dev-techx-corp:1.0-product-catalog .
docker push 804372444787.dkr.ecr.us-east-1.amazonaws.com/ecommerce-dev-techx-corp:1.0-product-catalog
```

> 💡 Các image tag hiện tại dùng format: `1.0-<service-name>` (xem `platform/charts/application/values.yaml`).

---

## 4. Cấu hình kubectl

```bash
aws eks update-kubeconfig --region us-east-1 --name ecommerce-dev-eks
kubectl get nodes  # Kiểm tra cluster hoạt động
```

---

## 5. Cài đặt ArgoCD lên EKS

```bash
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# Chờ ArgoCD sẵn sàng
kubectl wait --for=condition=available deployment -l app.kubernetes.io/name=argocd-server -n argocd --timeout=120s
```

---

## 6. Deploy ứng dụng qua ArgoCD (GitOps)

### 6.1 Bootstrap Root App

```bash
kubectl apply -f platform/gitops/bootstrap/root-app.yaml
```

Lệnh này sẽ tạo ArgoCD **App-of-Apps** — tự động sync toàn bộ ứng dụng từ GitHub.

### 6.2 Deploy app của TF (Team Function)

```bash
kubectl apply -f platform/gitops/applications/application.yaml
```

ArgoCD sẽ tự động:
1. Clone repo từ `feat/app-migration`
2. Render Helm chart tại `platform/charts/application`
3. Apply tất cả 25 Kubernetes resources vào namespace `techx-tf1`

### 6.3 Kiểm tra trạng thái

```bash
# Xem app ArgoCD
kubectl get app -n argocd

# Xem Pods
kubectl get pods -n techx-tf1

# Xem logs ArgoCD sync
kubectl logs -n argocd deployment/argocd-application-controller --tail=50
```

---

## 7. Seed Database (RDS PostgreSQL)

> Thực hiện **sau khi** EKS đã có ít nhất 1 node chạy.

```bash
# Chạy pod tạm thời để seed dữ liệu từ init.sql vào RDS
kubectl run pg-client --rm -i --restart=Never \
  --image=postgres:16 \
  --env="PGPASSWORD=<DB_PASSWORD>" -- \
  psql -h ecommerce-dev-postgres.c2x20s086fm5.us-east-1.rds.amazonaws.com \
       -U db_admin -d ecommerce_db \
  < platform/charts/application/postgresql/init.sql
```

> Lấy `DB_PASSWORD` bằng lệnh:
> ```bash
> terraform output -raw db_password
> ```

File `init.sql` tạo:
- Schema `catalog` + bảng `catalog.products` (10 sản phẩm mẫu)
- Schema `reviews` + bảng `reviews.productreviews` (50 review mẫu)
- Schema `accounting` + bảng `accounting.order`, `accounting.shipping`, `accounting.orderitem`

---

## 8. Truy cập ứng dụng

### Cách 1: Port-forward (local)

```bash
kubectl port-forward svc/frontend-proxy 9999:8080 -n techx-tf1
# Truy cập: http://localhost:9999
```

### Cách 2: Cloudflare Quick Tunnel (Internet)

```bash
# Deploy tunnel vào EKS
kubectl apply -f platform/cloudflare-tunnel.yaml

# Lấy URL công khai
kubectl logs deployment/cloudflared-tunnel -n techx-tf1 | grep trycloudflare.com
```

URL sẽ có dạng: `https://xxxx.trycloudflare.com`

> ⚠️ **Lưu ý:** Tài khoản AWS sandbox bị chặn tạo Load Balancer (CLB/ALB/NLB). Dùng Cloudflare Tunnel làm giải pháp thay thế.

---

## 9. Kiểm tra kết nối các services

```bash
# RDS + Valkey: xem log product-reviews
kubectl logs -l app.kubernetes.io/name=product-reviews -n techx-tf1 --tail=20

# MSK: xem log accounting
kubectl logs -l app.kubernetes.io/name=accounting -n techx-tf1 --tail=20

# Toàn bộ Pods
kubectl get pods -n techx-tf1
```

**Kết quả mong đợi:**
| Service | Kết nối |
|---|---|
| `product-catalog` | RDS PostgreSQL (catalog schema) |
| `product-reviews` | RDS PostgreSQL (reviews schema) + Valkey cache |
| `accounting` | MSK Kafka (topic: `orders`) |

---

## 10. Dọn dẹp tài nguyên

```bash
cd terraform/environments/sandbox

# Xóa ArgoCD apps trước (tránh conflict finalizers)
kubectl delete app techx-corp -n argocd
kubectl delete app techx-corp-root -n argocd

# Xóa toàn bộ hạ tầng
terraform destroy -auto-approve
```

> ⏱ Terraform destroy mất khoảng 30–45 phút.

---

## 🔧 Troubleshooting

### Pod `Pending` — không schedule được
```bash
kubectl describe pod <pod-name> -n techx-tf1
# Kiểm tra node có đủ tài nguyên không
kubectl describe nodes
```

### MSK: `Unknown topic or partition`
Topic chưa tồn tại. Với `auto.create.topics.enable=true` đã bật, restart pod accounting:
```bash
kubectl rollout restart deployment/accounting -n techx-tf1
```

### ArgoCD không sync
```bash
kubectl annotate app techx-corp -n argocd argocd.argoproj.io/refresh=normal --overwrite
```

### SSO token hết hạn
```bash
aws sso login --profile Phase3-Mentor-PermissionSet-804372444787
```
