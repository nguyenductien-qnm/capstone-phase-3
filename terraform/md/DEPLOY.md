# Hướng dẫn triển khai (Deploy Guide)

Quy trình dựng mới hạ tầng AWS và triển khai ứng dụng từ đầu.

---

## Bước 1: Dựng hạ tầng AWS (Terraform)

Khởi tạo và apply cấu hình Terraform để tạo VPC, EKS (v1.36) và ECR.

```sh
cd terraform
terraform init
terraform apply
cd ..
```

---

## Bước 2: Build & Đẩy ảnh lên ECR

Kéo ảnh mẫu `amd64` từ Docker Hub, tự biên dịch dịch vụ `shipping` (Rust) thành bản `amd64`, và đẩy tất cả lên ECR:

```sh
./deploy/push-seed-images.sh
```

---

## Bước 3: Cấu hình kết nối cụm EKS (kubectl)

```sh
aws eks update-kubeconfig --name techx-eks-dev --region us-east-1
```

---

## Bước 4: Triển khai ứng dụng (Chọn 1 trong 2 cách)

### Cách A: Dùng ArgoCD (GitOps - Khuyên dùng)

Tự động đồng bộ và quản lý trạng thái qua Git.

1. **Cài đặt ArgoCD lên cụm EKS:**
   ```sh
   ./deploy/install-argocd.sh
   ```
   _(Đợi script chạy xong và sao chép mật khẩu Admin hiển thị trên màn hình)._
2. **Kích hoạt deploy ứng dụng qua ArgoCD:**
   _(Do repo là public nên không cần cấu hình credentials)_
   ```sh
   kubectl apply -f deploy/argocd-app.yaml
   ```

### Cách B: Deploy thủ công (Dùng Helm CLI)

Chỉ chạy một lần, không tự động đồng bộ khi thay đổi code.

```sh
helm dependency build ./techx-corp-chart
helm upgrade --install techx-corp ./techx-corp-chart -n techx-tf1 --create-namespace -f deploy/values-flagd-sync.yaml
```

---

## Kiểm tra truy cập

- **Kiểm tra 24/24 Pods trạng thái Running:**
  ```sh
  kubectl -n techx-tf1 get pods
  ```
- **Lấy địa chỉ truy cập (Load Balancer):**
  ```sh
  kubectl -n techx-tf1 get svc frontend-proxy
  ```
  _(Truy cập địa chỉ trong cột `EXTERNAL-IP` tại cổng `:8080`)_
  - 🛒 **Storefront:** `http://<EXTERNAL-IP>:8080/`
  - 📊 **Grafana:** `http://<EXTERNAL-IP>:8080/grafana/`
  - 🔍 **Jaeger:** `http://<EXTERNAL-IP>:8080/jaeger/ui/`
