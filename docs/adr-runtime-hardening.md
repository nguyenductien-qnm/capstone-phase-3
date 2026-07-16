# Architectural Decision Record (ADR): Runtime Hardening & Đăng ký Ngoại lệ

**Mã tài liệu**: CDO-SEC-ADR-003  
**Trạng thái**: Đề xuất (Proposed)  
**Tác giả**: Châu Thành Trung (CDO-05 / Security & DevOps Lead)  
**Ngày phê duyệt**: 14/07/2026  

---

## 1. Bối cảnh & Yêu cầu Bảo mật (Context)
Nhằm thực hiện **Directive #5 (Runtime Hardening)**, TechX Corp cần siết chặt môi trường runtime của cụm Kubernetes (EKS Cluster) bằng cách chặn các cấu hình không an toàn ngay tại cửa ngõ.

Các rủi ro cần giải quyết:
1. **Container chạy quyền root**: Kẻ tấn công chiếm được container root có thể thoát khỏi sandbox và kiểm soát node máy chủ vật lý.
2. **Sử dụng tag di động (latest)**: Rủi ro tấn công chuỗi cung ứng (supply chain attack) khi Docker image bị đẩy đè mã độc.
3. **Thiếu giới hạn tài nguyên (Limits/Requests)**: Pod bị rò rỉ bộ nhớ hoặc quá tải CPU kéo sập các dịch vụ khác trên cùng một Node.
4. **Hệ thống file ghi được (Writable Root FS)**: Cho phép kẻ tấn công tải và thực thi mã độc hoặc chỉnh sửa file hệ thống của container.

---

## 2. Công cụ Chính sách & Trạng thái Enforce (Policy Engine)
Chúng ta lựa chọn **OPA Gatekeeper** làm Admission Controller để tự động chặn các manifest vi phạm.

### Các luật được thực thi chặn ngay lập tức (Enforced Rules):
* `k8s-disallow-capabilities`: Chặn tất cả các capabilities ngoại trừ các cấu hình đặc biệt được cho phép.
* `k8s-allow-privilege-escalation`: Thiết lập `allowPrivilegeEscalation: false`.
* `k8s-run-as-non-root`: Bắt buộc thiết lập `runAsNonRoot: true`.
* `k8s-require-image-tag`: Cấm sử dụng các image tag di động/trôi nổi (như `latest`, `dev`, `master`). Chỉ cho phép tag cố định (ví dụ: `1.0-accounting`) hoặc image digest.
* `k8s-require-resources`: Bắt buộc tất cả các container ứng dụng phải định nghĩa `limits` và `requests` cho cả CPU và Memory.

---

## 3. Chính sách Giám sát (Audit-Only Rules)
* **Luật áp dụng**: `k8s-read-only-root-filesystem` (Yêu cầu hệ thống file chỉ đọc).
* **Trạng thái**: **Chỉ giám sát (Audit-only / Dryrun)** cho phần lớn các service, ngoại trừ service `ad` đã được chuyển sang **Enforce** thành công.
* **Lý do**: Nhiều microservices của bên thứ ba hoặc các framework phát triển (như NextJS frontend, Envoy proxy) yêu cầu ghi dữ liệu tạm vào các thư mục `/tmp`, `/var/cache` hoặc `.next/cache`. Việc siết chặn ngay lập tức sẽ làm vỡ ứng dụng và gây gián đoạn dịch vụ khách hàng (rớt SLO).
* **Kế hoạch cắt chuyển (Audit -> Enforce)**:
  1. Rà quét nhật ký Audit của Gatekeeper để liệt kê tất cả các thư mục cần ghi file tạm của từng microservice.
  2. Cập nhật Helm Chart để tạo các phân vùng ghi tạm dạng `emptyDir` gắn vào Pod.
  3. Dự kiến chuyển toàn bộ sang chế độ chặn thực tế (Enforce) trước **30/09/2026**.

---

## 4. Danh sách Đăng ký Ngoại lệ (Exception Register)
Để đảm bảo các dịch vụ hệ thống và giám sát hoạt động bình thường, các ngoại lệ sau được đăng ký chính thức (Không vô thời hạn):

| Workload (Kind/Name) | Namespace | Lý do Ngoại lệ | Người phụ trách (Owner) | Ngày hết hạn (Expiry) |
| :--- | :--- | :--- | :---: | :---: |
| `DaemonSet/otel-collector-agent` | `techx-tf1` | Cần đặc quyền root và HostNetwork để thu thập log/metrics trực tiếp từ Host. | DevOps Team | **31/12/2026** |
| `Deployment/grafana` (Sidecars) | `techx-tf1` | Các container `k8s-sidecar` cần ghi file cấu hình dashboard vào EmptyDir chung, không thể bật ReadOnly FS. | Platform Team | **31/12/2026** |
| `StatefulSet/opensearch` | `techx-tf1` | Ứng dụng quản lý log cần ghi trực tiếp vào volume dữ liệu và thực hiện các tối ưu hệ thống lúc khởi tạo. | SRE Team | **31/12/2026** |
| `Deployment/jaeger` | `techx-tf1` | Image của bên thứ ba chưa tương thích hoàn toàn với cấu hình ReadOnly Filesystem nghiêm ngặt. | Platform Team | **31/12/2026** |

---

## 5. Đánh giá từ Các Phòng ban (Security / SRE / CFO Concerns)

### 5.1. Góc nhìn Bảo mật (Security Core)
* **Giải pháp**: Giảm thiểu tối đa bề mặt tấn công. Bằng cách khóa quyền root và drop capabilities, ngay cả khi container bị chiếm quyền điều khiển, kẻ tấn công cũng không thể leo thang đặc quyền lên node máy chủ vật lý.
* **Tác động**: Đạt điểm tuân thủ bảo mật tối đa cho Directive #5.

### 5.2. Góc nhìn Vận hành (SRE / Platform)
* **Rủi ro SLO**: Rủi ro gián đoạn dịch vụ thấp nhờ chiến lược **Rollout 2 giai đoạn (Audit trước, Enforce sau)**. Việc test thử nghiệm qua file render giúp loại bỏ 100% lỗi cú pháp trước khi chạy thực tế.
* **Kịch bản Khôi phục (Rollback)**: Nếu chính sách chặn gây nghẽn deploy do lỗi False Positive, SRE Team có thể tạm thời chuyển nhanh trường `enforcementAction` của Constraint tương ứng về `dryrun` hoặc chạy lệnh xóa Constraint:
  `kubectl delete constraint <constraint-name>`
  Thao tác này khôi phục khả năng deploy tức thì mà không cần cài đặt lại hệ thống.

### 5.3. Góc nhìn Tài chính (CFO / Budget)
* **Chi phí hạ tầng**: **$0 phát sinh**. OPA Gatekeeper được cấu hình tài nguyên tối thiểu (CPU 100m, RAM 256Mi), hoàn toàn nằm gọn trong cụm EKS hiện có, không làm tăng hóa đơn hàng tháng của AWS.
* **Hiệu quả chi phí**: Việc bắt buộc khai báo resource limit giúp Kubernetes Scheduler sắp xếp các Pod gọn gàng hơn, tối ưu hóa mật độ pod trên mỗi Node và tiết kiệm chi phí chạy máy ảo.

---

## 6. Người ký Phê duyệt (Signatories)
* **Châu Thành Trung** (DevOps & Security Lead - Người đề xuất)
* **Duy Nguyễn Khánh** (SRE Lead - Người kiểm duyệt vận hành)
* **Mai Phước Khoa** (Platform Architect - Người kiểm duyệt kiến trúc)
