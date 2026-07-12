#!/bin/bash
# Script tự động cài đặt ArgoCD lên EKS Cluster

set -e

echo "=== 1. Tạo namespace argocd ==="
kubectl create namespace argocd || echo "Namespace argocd đã tồn tại"

echo "=== 2. Cài đặt ArgoCD (Bản Stable) ==="
kubectl apply --server-side --force-conflicts -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

echo "=== 3. Chờ các Pods ArgoCD sẵn sàng (khoảng 2-3 phút) ==="
kubectl -n argocd wait --for=condition=Ready pods --all --timeout=300s

echo "=== 4. Lấy mật khẩu đăng nhập Admin ban đầu ==="
echo "--------------------------------------------------------"
echo "Mật khẩu Admin đăng nhập ArgoCD là:"
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d
echo ""
echo "--------------------------------------------------------"

echo "=== 5. Mở cổng truy cập ArgoCD UI (Port-forward) ==="
echo "Hãy chạy lệnh sau ở một cửa sổ Terminal mới để mở UI:"
echo "kubectl -n argocd port-forward svc/argocd-server 8443:443"
echo "Sau đó truy cập: https://localhost:8443 (User: admin)"
