# Báo cáo Tổng kết Hoàn thành Mandate 5: Runtime Hardening & Policy-as-Code

**Dự án**: TechX Corp Microservices Platform - Capstone Phase 3  
**Báo cáo viên**: Châu Thành Trung (CDO-05 / Security & DevOps Lead)  
**Trạng thái**: Hoàn thành & Sẵn sàng bàn giao (Implemented & Ready for Review)  
**Ngày thực hiện**: 15/07/2026  

---

## 1. Tổng quan Yêu cầu của Mandate 5 (Requirements)
Mandate 5 (Runtime Hardening) yêu cầu nhóm Task Force siết chặt an toàn bảo mật ở môi trường chạy (runtime) của các container trên cụm Kubernetes EKS, đồng thời thiết lập cơ chế chặn tự động ở cổng API Server (Policy-as-Code). Cụ thể bao gồm 4 yêu cầu lõi:

1. **Cấm Container chạy quyền Root**: Tất cả container trong cụm phải bắt buộc khai báo `runAsNonRoot: true`, cấm leo thang đặc quyền (`allowPrivilegeEscalation: false`), và loại bỏ các Linux capabilities thừa (`capabilities.drop: ["ALL"]`).
2. **Cấm sử dụng Image Tag trôi nổi (latest)**: Tất cả container và initContainer phải sử dụng thẻ tag phiên bản cố định (ví dụ: `1.0-accounting`) hoặc image digest để kiểm soát chính xác mã nguồn chạy thực tế, tránh rủi ro tấn công chuỗi cung ứng.
3. **Bắt buộc khai báo tài nguyên (Resource Sizing)**: Mọi workload bắt buộc phải khai báo đầy đủ cả 4 trường: `limits.cpu`, `limits.memory`, `requests.cpu`, `requests.memory` nhằm đảm bảo tính ổn định của cụm và scheduler hoạt động tối ưu.
4. **Bảo vệ tự động (Admission Controller)**: Thiết lập cơ chế tự động từ chối (Reject) ngay tại bước `kubectl apply` đối với các manifest cấu hình vi phạm các luật trên. Việc kiểm soát phải đi từ chế độ cảnh báo (Audit) sang chặn (Enforce) một cách có kiểm soát để không gây downtime.

---

## 2. Các công việc đã thực hiện để Giải quyết Yêu cầu (Actions Taken)

Chúng ta đã triển khai toàn bộ các giải pháp kỹ thuật, cấu hình mã nguồn và tài liệu tương ứng để đáp ứng triệt để các yêu cầu trên:

### 2.1. Cấu hình bảo mật Helm values.yaml (Yêu cầu 1, 2 và 3)
Đã thực hiện cập nhật toàn bộ cấu hình an toàn cho các workloads trong file **[values.yaml](file:///c:/Users/THANH%20TRUNG/Desktop/Phase3/capstone-phase-3/platform/charts/application/values.yaml)**:
* **Bảo mật mặc định (Global Default):** Định nghĩa cấu hình `securityContext` và `podSecurityContext` mặc định ở cấp độ toàn cụm dưới key `default:` để mọi microservice tự động thừa hưởng (runAsNonRoot, allowPrivilegeEscalation: false, capabilities.drop: ["ALL"], seccompProfile: RuntimeDefault).
* **Cập nhật các Service ghi đè cục bộ:** Đối với các service tự khai báo User ID chạy riêng (như `frontend`, `frontend-proxy`, `payment`, `quote`, `kafka`, `valkey-cart`), đã bổ sung đầy đủ các tiêu chuẩn drop capabilities và cấm privilege escalation tương tự mặc định.
* **Cấu hình an toàn cho InitContainers:** Toàn bộ 5 initContainers (chạy busybox để chờ Kafka/Valkey) đã được thêm cấu hình `securityContext` để chạy dưới user non-root `1000` và drop capabilities.
* **Image Tag Pinning:** Sửa đổi tag của image `busybox` trong toàn bộ các initContainers sang tag cố định cụ thể (`1.36.1` hoặc `1.38.0`) để loại bỏ hoàn toàn tag trôi nổi `latest`.
* **Phân bổ tài nguyên tối ưu (Resource Sizing):** Định nghĩa đầy đủ 4 trường CPU/Memory Requests & Limits cho toàn bộ 18+ services (bao gồm cả `llm` và `ad` trước đó để trống) với định mức tối giản (ví dụ: requests CPU 10m, RAM 32Mi cho backend) để duy trì ngân sách dưới $300/tuần.
* **Hệ thống file chỉ đọc (ReadOnly Root FS):** Kích hoạt thành công chế độ `readOnlyRootFilesystem: true` riêng cho service **`ad`** (service xử lý logic Go/gRPC không cần ghi ổ đĩa) để minh chứng khả năng siết bảo mật sâu theo từng service mà không làm vỡ các service ghi file tạm.

### 2.2. Tài liệu Quyết định Kiến trúc & Đăng ký Ngoại lệ (Yêu cầu 4)
Đã xây dựng 2 tài liệu quyết định kiến trúc chính thức:
* **[adr-admission-policy.md](file:///c:/Users/THANH%20TRUNG/Desktop/Phase3/capstone-phase-3/docs/adr-admission-policy.md)**: Quyết định lựa chọn **OPA Gatekeeper** làm Admission Policy Engine vì tính trưởng thành, phổ biến và có sẵn thư viện luật mẫu khổng lồ giúp đẩy nhanh tiến độ triển khai.
* **[adr-runtime-hardening.md](file:///c:/Users/THANH%20TRUNG/Desktop/Phase3/capstone-phase-3/docs/adr-runtime-hardening.md)**: Định nghĩa kế hoạch Rollout (Audit/Dryrun trước, Enforce/Deny sau) và đăng ký ngoại lệ có thời hạn cụ thể (đến **31/12/2026**) cho các ứng dụng hệ thống đặc thù (như `otel-collector-agent` cần quyền root thu thập metrics, hay `grafana` sidecars cần ghi file vào EmptyDir).

### 2.3. Tạo bộ Test case phục vụ Mentor Nghiệm thu (Yêu cầu 4)
Đã tạo thư mục **[gatekeeper/tests/](file:///c:/Users/THANH%20TRUNG/Desktop/Phase3/capstone-phase-3/gatekeeper/tests/)** chứa bộ test suite gồm 19 file để kiểm tra toàn diện cả 5 chính sách bảo mật (bao gồm cả trường hợp lỗi - negative và thành công - positive):
* **Cấm chạy Root:** `neg-01-root.yaml`, `neg-09-run-as-root-uid0.yaml` (Negative) & `pos-02-run-as-nonroot-only.yaml` (Positive).
* **Cấm Tag di động:** `neg-02-image-latest.yaml`, `neg-08-no-image-tag.yaml`, `neg-11-initcontainer-latest.yaml` (Negative) & `pos-05-image-digest.yaml` (Positive).
* **Bắt buộc Resource:** `neg-03-missing-resources.yaml`, `neg-10-missing-limits-only.yaml` (Negative).
* **Cấm Privilege Escalation:** `neg-04-priv-esc-true.yaml`, `neg-05-priv-esc-missing.yaml` (Negative) & `pos-04-exempt-image.yaml` (Positive).
* **Giới hạn Capabilities:** `neg-06-no-drop-all.yaml`, `neg-07-add-dangerous-cap.yaml` (Negative) & `pos-03-allowed-cap.yaml` (Positive).
* **Tổng hợp & Hợp lệ:** `neg-12-multi-violation.yaml` (Vi phạm cả 5 luật) & `pos-01-valid.yaml` (Hợp lệ hoàn toàn).
* `namespace-policy-test.yaml`: Khởi tạo namespace chạy thử.

---

## 3. Kết quả Kiểm duyệt & Nghiệm thu (Verification)

### 3.1. Biên dịch Helm & Quét Audit tĩnh
* **Helm Template Check**: Chạy thử lệnh `helm template` thành công 100%, không bị lỗi logic hay xung đột cú pháp YAML nào.
* **Quét Audit Workloads**: Kết quả quét tự động qua script Python cho thấy tất cả các microservice tự phát triển của chúng ta đều đã chuyển sang trạng thái an toàn (**Pass** hoặc **Cần xác minh** do hệ thống file ghi log, không còn container ứng dụng nào bị cảnh báo nguy hiểm **Fail**). Kết quả chi tiết đã được cập nhật vào báo cáo **[docs/security-inventory.md](file:///c:/Users/THANH%20TRUNG/Desktop/Phase3/capstone-phase-3/docs/security-inventory.md)**.

### 3.2. Hướng dẫn Mentor chạy thử nghiệm (Mentor Testing Guide)

Mentor có thể kiểm tra thực tế tính năng chặn tự động (chế độ **Deny**) bằng cách chạy các lệnh sau từ terminal:

```bash
# Bước 1: Khởi tạo namespace test
kubectl apply -f gatekeeper/tests/namespace-policy-test.yaml

# Bước 2: Apply thử các file cấu hình lỗi (Kỳ vọng: OPA Gatekeeper chặn lại ngay lập tức)

# 1. Test cấm chạy root:
kubectl apply -f gatekeeper/tests/neg-01-root.yaml
# Lỗi kỳ vọng: [run-as-non-root] Container neg-root is attempting to run without a required securityContext/runAsNonRoot or securityContext/runAsUser != 0

# 2. Test cấm tag di động (latest):
kubectl apply -f gatekeeper/tests/neg-02-image-latest.yaml
# Lỗi kỳ vọng: [deny-floating-image-tag] container <neg-image-latest> uses a disallowed tag <nginx:latest>...

# 3. Test bắt buộc resource sizing:
kubectl apply -f gatekeeper/tests/neg-03-missing-resources.yaml
# Lỗi kỳ vọng: [require-cpu-memory-limits-requests] container <neg-missing-resources> does not have <{"cpu", "memory"}> limits/requests defined...

# 4. Test cấm privilege escalation:
kubectl apply -f gatekeeper/tests/neg-04-priv-esc-true.yaml
# Lỗi kỳ vọng: Privilege escalation container is not allowed: public.ecr.aws/docker/library/nginx:1.27

# 5. Test giới hạn capabilities (không drop ALL):
kubectl apply -f gatekeeper/tests/neg-06-no-drop-all.yaml
# Lỗi kỳ vọng: containers are not dropping all required capabilities: {container: neg-no-drop-all, capabilities: [ALL]}

# Bước 3: Apply file cấu hình chuẩn (Kỳ vọng: Thành công)
kubectl apply --dry-run=server -f gatekeeper/tests/pos-01-valid.yaml
# Kết quả kỳ vọng: pod/pos-valid created (server dry run)
```
