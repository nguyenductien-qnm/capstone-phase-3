# Tài liệu Cấu trúc Dự án (Base Setup Guide)

Dự án Capstone Phase 3 - TechX-Corp Platform. Hệ thống microservices bán hàng kết hợp mô hình GitOps (ArgoCD) và Giám sát đo lường (Observability) trên AWS EKS.

---

## 1. Cấu trúc thư mục dự án

```
capstone-phase-3/
├── terraform/                      # Hạ tầng AWS (VPC, EKS v1.36, ECR)
│   ├── modules/                    # Các custom modules (vpc, eks, ecr)
│   └── md/                         # Tài liệu hướng dẫn vận hành hạ tầng
│       ├── DEPLOY.md               # Hướng dẫn deploy từ A-Z
│       ├── DESTROY.md              # Hướng dẫn hủy tài nguyên & gỡ kẹt
│       └── RESOURCES.md            # Danh mục tài nguyên hệ thống
│
├── techx-corp-chart/               # Helm Chart chính định nghĩa 24 dịch vụ
│   ├── templates/                  # Mẫu tài nguyên Kubernetes
│   └── values.yaml                 # Tham số cấu hình mặc định của hệ thống
│
├── deploy/                         # Các script và file manifest bổ trợ
│   ├── install-argocd.sh           # Script tự động cài đặt ArgoCD (Server-Side)
│   ├── argocd-app.yaml             # Manifest khai báo ứng dụng ArgoCD (GitOps)
│   ├── push-seed-images.sh         # Script đẩy 18 images seed + build shipping
│   ├── values-flagd-sync.yaml      # Cấu hình Token đồng bộ cờ tính năng với BTC
│   └── values-aio-llm.yaml         # Cấu hình kết nối OpenAI API thật (AIO)
│
└── techx-corp-platform/            # Mã nguồn các microservices của ứng dụng
    └── src/
        └── shipping/               # Dịch vụ shipping (Rust) đã được sửa Dockerfile
```

---

## 2. Hướng dẫn nhanh cho các vai trò vận hành

Để bắt đầu làm việc hoặc phân chia công việc cho các nhóm chuyên trách (CDO - Platform, CDO - FinOps, AIO):

* **Dựng mới hạ tầng & Deploy ứng dụng:** Xem hướng dẫn chi tiết tại [DEPLOY.md](file:///Users/ductiennguyen/Documents/Project/xbrain/capstone-phase-3/terraform/md/DEPLOY.md).
* **Quản trị & Đồng bộ GitOps:** Sử dụng giao diện điều khiển ArgoCD theo tài khoản admin cấp sẵn tại `DEPLOY.md`.
* **Gỡ bỏ hệ thống tránh phát sinh chi phí AWS:** Xem quy trình dọn dẹp an toàn tại [DESTROY.md](file:///Users/ductiennguyen/Documents/Project/xbrain/capstone-phase-3/terraform/md/DESTROY.md).
* **Tra cứu thông số tài nguyên & Cổng dịch vụ:** Xem bảng tra cứu tại [RESOURCES.md](file:///Users/ductiennguyen/Documents/Project/xbrain/capstone-phase-3/terraform/md/RESOURCES.md).
