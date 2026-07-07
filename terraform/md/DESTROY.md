# Hướng dẫn hủy tài nguyên (Destroy Guide)

Quy tắc vàng: **Helm/Kubernetes dọn trước, Terraform destroy sau.**

### Bước 1: Gỡ bỏ các ứng dụng để giải phóng Load Balancer & Ổ đĩa

- **Nếu deploy bằng ArgoCD (Cách A):**
  ```sh
  kubectl delete -f deploy/argocd-app.yaml
  helm uninstall argocd -n argocd
  ```
- **Nếu deploy bằng Helm thủ công (Cách B):**
  ```sh
  helm uninstall techx-corp -n techx-tf1
  ```
  _(Đợi khoảng 1-2 phút cho AWS tự xóa Load Balancer)._

### Bước 2: Hủy hạ tầng cốt lõi

```sh
cd terraform
terraform destroy
```

_(ECR Repository đã bật `force_delete = true` nên sẽ tự xóa sạch ảnh bên trong)._

---
