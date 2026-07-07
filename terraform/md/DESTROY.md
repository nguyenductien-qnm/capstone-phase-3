# Hướng dẫn hủy tài nguyên (Destroy Guide)

Quy tắc vàng: **Helm/Kubernetes dọn trước, Terraform destroy sau.**

---

## 1. Quy trình chuẩn (Best Practice)

### Bước 1: Gỡ bỏ các ứng dụng để giải phóng Load Balancer & Ổ đĩa
* **Nếu deploy bằng ArgoCD (Cách A):**
  ```sh
  kubectl delete -f deploy/argocd-app.yaml
  helm uninstall argocd -n argocd
  ```
* **Nếu deploy bằng Helm thủ công (Cách B):**
  ```sh
  helm uninstall techx-corp -n techx-tf1
  ```
*(Đợi khoảng 1-2 phút cho AWS tự xóa Load Balancer).*

### Bước 2: Hủy hạ tầng cốt lõi
```sh
cd terraform
terraform destroy -auto-approve
```
*(ECR Repository đã bật `force_delete = true` nên sẽ tự xóa sạch ảnh bên trong).*

---

## 2. Xử lý sự cố khi bị kẹt (Troubleshooting)

Nếu lỡ chạy `terraform destroy` trước và bị kẹt mạng (VPC, Subnets) không thể xóa:

### TH1: Bị kẹt khóa Lock trên S3
Lấy ID khóa bị kẹt trong thông báo lỗi (VD: `ea049771-...`) và chạy:
```sh
terraform force-unlock -force <LOCK_ID>
```

### TH2: Bị kẹt Subnets do Load Balancer ngầm
1. **Tìm và xóa Load Balancer thừa:**
   ```sh
   # Liệt kê các LB đang chạy
   aws elb describe-load-balancers --region us-east-1 --query "LoadBalancerDescriptions[].LoadBalancerName"
   
   # Xóa LB bị sót
   aws elb delete-load-balancer --load-balancer-name <TÊN_LB> --region us-east-1
   ```
2. **Tìm và xóa Security Group phụ của Load Balancer:**
   Nếu VPC vẫn bị kẹt, tìm và xóa Security Group có tên dạng `k8s-elb-xxx`:
   ```sh
   # Lấy SG ID
   aws ec2 describe-security-groups --filters "Name=group-name,Values=k8s-elb-*" --region us-east-1 --query "SecurityGroups[].GroupId"
   
   # Xóa SG
   aws ec2 delete-security-group --group-id <SG_ID> --region us-east-1
   ```
3. **Chạy lại lệnh hủy hạ tầng:**
   ```sh
   terraform destroy -auto-approve
   ```
