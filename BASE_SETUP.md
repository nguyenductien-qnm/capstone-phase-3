# Tài liệu Cấu trúc Dự án (Base Setup Guide)

Dự án Capstone Phase 3 - TechX-Corp Platform. Hệ thống microservices bán hàng kết hợp mô hình GitOps (ArgoCD) và Giám sát đo lường (Observability) trên AWS EKS.

---

## 1. Cấu trúc thư mục dự án

```
capstone-phase-3/
├── techx-corp-platform/            # Source microservices; giữ nguyên build context
│   ├── src/
│   └── pb/                         # Protobuf API definitions
├── aiops/
│   ├── log_clustering/
│   └── detector/
├── terraform/
│   ├── modules/                    # Shared Terraform modules
│   ├── environments/sandbox/       # Root module và state của sandbox
│   └── md/                         # Tài liệu hạ tầng
├── platform/
│   ├── charts/application/         # Helm chart hiện hành
│   ├── gitops/applications/        # ArgoCD applications
│   ├── gitops/environments/        # Values theo môi trường
│   └── policies/                   # K8s policies và resource governance
├── scripts/
│   ├── bootstrap/
│   ├── build/
│   ├── deploy/
│   └── validate/
└── docs/
    ├── shared/
    ├── ai/
    ├── cdo05/
    └── cdo09/
```

---

## 2. Hướng dẫn nhanh cho các vai trò vận hành

- **Dựng hạ tầng:** chạy Terraform từ `terraform/environments/sandbox/`.
- **Deploy ứng dụng:** xem `GETTING_STARTED.md` và chart tại `platform/charts/application/`.
- **Quản trị GitOps:** dùng manifest trong `platform/gitops/`.
- **Build/push image:** dùng script trong `scripts/build/` hoặc `scripts/deploy/`.
