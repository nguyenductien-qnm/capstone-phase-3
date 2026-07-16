# Architectural Decision Record (ADR): Chọn Admission Policy Engine & Kế hoạch Rollout

**Mã tài liệu**: CDO-SEC-ADR-002  
**Trạng thái**: Đề xuất (Proposed)  
**Tác giả**: Châu Thành Trung (CDO-05 / Security Lead)  
**Ngày thực hiện**: 14/07/2026  

---

## 1. Bối cảnh & Yêu cầu (Context)
Để thực hiện **Directive #5 (Runtime Hardening)**, hệ thống cần có cơ chế tự động chặn đứng các cấu hình nguy hiểm (chạy quyền root, không giới hạn tài nguyên, tag image latest trôi nổi) ngay khi lập trình viên thực hiện lệnh `kubectl apply`. 

Chúng ta cần lựa chọn công cụ kiểm soát chính sách đầu vào (Admission Policy Engine) và xây dựng kế hoạch triển khai (Rollout Mode) thỏa mãn các ràng buộc:
* **Tính ổn định & Trưởng thành**: Sử dụng công cụ phổ biến, dễ bảo trì, có thư viện luật mẫu phong phú để hoàn thành trước hạn chót thứ Sáu.
* **Chi phí tối ưu**: Cấu hình tài nguyên (vCPU/RAM) ở mức tối thiểu để tránh vượt trần ngân sách $300/tuần.
* **An toàn vận hành**: Không làm gián đoạn (downtime) các dịch vụ đang chạy ổn định của storefront.

---

## 2. Các Phương án Lựa chọn (Candidates)

### Phương án A: OPA Gatekeeper (Open Policy Agent) - **ĐƯỢC CHỌN**
* **Cơ chế**: Sử dụng một Admission Webhook tiêu chuẩn, quản lý các luật thông qua `ConstraintTemplates` và `Constraints` (CRDs). Chính sách được viết bằng ngôn ngữ Rego.
* **Ưu điểm**:
  * Là công cụ kiểm soát chính sách trưởng thành, phổ biến nhất trong hệ sinh thái Kubernetes hiện nay.
  * Có **Thư viện luật mẫu khổng lồ (Gatekeeper Library)** được xây dựng sẵn cho các trường hợp: cấm chạy root, bắt buộc khai báo resource limit, chặn tag image latest. Nhóm có thể tái sử dụng ngay lập tức mà không cần tự viết luật từ đầu.
  * Hỗ trợ tính năng rà quét độc lập (`Audit`) song song với việc chặn (`Admission Webhook`).

### Phương án B: Kyverno
* **Cơ chế**: Sử dụng Admission Webhook bên thứ ba, viết chính sách bằng YAML.
* **Nhược điểm**: Mặc dù viết bằng YAML dễ học hơn Rego, nhưng Kyverno có ít thư viện mẫu chuẩn hóa hơn so với OPA Gatekeeper trong các môi trường doanh nghiệp lớn.

### Phương án C: Kubernetes ValidatingAdmissionPolicy (VAP)
* **Cơ chế**: Tính năng kiểm soát chính sách native của Kubernetes API Server sử dụng ngôn ngữ CEL (Common Expression Language).
* **Nhược điểm**: VAP là công cụ rất mới (mới chỉ lên GA từ K8s 1.30). Cú pháp CEL còn khá lạ lẫm, tài liệu hướng dẫn và các thư viện luật mẫu của cộng đồng còn hạn chế, dễ gây khó khăn và chậm tiến độ cho đội vận hành khi cần debug gấp.

---

## 3. Quyết định (Decision)
Nhóm quyết định chọn **Phương án A: OPA Gatekeeper** làm Policy Engine chính cho Mandate 5.

### Lý do lựa chọn:
1. **Tính phổ biến & Độ tin cậy**: OPA Gatekeeper là chuẩn công nghiệp được kiểm định thực tế qua rất nhiều dự án lớn, giúp đội vận hành yên tâm hơn khi sử dụng.
2. **Tiết kiệm thời gian triển khai**: Tận dụng được các file mẫu chuẩn hóa từ thư viện mã nguồn mở của OPA, đảm bảo hoàn thành sớm trước deadline thứ Sáu.
3. **Giải pháp tối ưu tài nguyên**: Để tránh phát sinh chi phí, OPA Gatekeeper sẽ được giới hạn tài nguyên ở mức tối thiểu (`resources.limits` nhỏ: CPU 100m, RAM 256Mi) khi deploy lên namespace `gatekeeper-system`.

---

## 4. Kế hoạch Triển khai & Cắt chuyển (Rollout Plan)

Để đảm bảo không làm gián đoạn storefront, quy trình cấu hình sẽ đi qua 2 giai đoạn:

```
[Giai đoạn 1: Dryrun Mode] ──(Sửa các Pod vi phạm)──> [Giai đoạn 2: Deny Mode]
```

### Giai đoạn 1: Dryrun Mode (Giám sát cảnh báo)
* **Cấu hình**: Triển khai các Constraint với thuộc tính `enforcementAction: dryrun`.
* **Mục tiêu**: Gatekeeper sẽ cho phép deploy bình thường nhưng sẽ ghi log cảnh báo vi phạm vào hệ thống log của nó và báo về bảng điều khiển. Nhóm dùng dữ liệu này để rà soát và sửa đổi Helm Chart của 18+ microservices mà không sợ làm sập app đang chạy.
* **Phạm vi áp dụng (Namespace Scope)**: Cấu hình `match.namespaces` chỉ nhắm vào namespace ứng dụng (`techx-tf1`), loại trừ các namespace hệ thống (`kube-system`, `gatekeeper-system`, `argocd`).

### Giai đoạn 2: Active/Deny Mode (Chặn thật sự)
* **Cấu hình**: Cập nhật thuộc tính của Constraint thành `enforcementAction: deny`.
* **Mục tiêu**: Bất kỳ hành vi apply manifest vi phạm nào (như chạy root) sẽ bị Gatekeeper chặn lại ngay lập tức tại cửa ngõ.

---

## 5. Quy trình xử lý Ngoại lệ (Exception Process)
* Đối với các container đặc thù (như `otel-collector-agent` cần quyền đặc biệt để lấy log/metrics hệ thống):
  * **Giải pháp**: Sử dụng cấu hình `excludedUsers` hoặc cấu hình loại trừ cụ thể trong file Constraint (loại trừ theo tên Deployment hoặc theo nhãn `security.techx.corp/exception: "true"`).

---

## 6. Kế hoạch Khôi phục (Rollback Plan)
* Nếu Gatekeeper gặp sự cố chặn nhầm làm tắc nghẽn luồng CI/CD:
  * **Cách thực hiện**: Chuyển nhanh `enforcementAction` của các Constraint về `dryrun` hoặc xóa Constraint đó đi. Quá trình này diễn ra tức thời mà không cần gỡ bỏ OPA Gatekeeper.
  * **Quy trình phê duyệt**: Việc khôi phục (Rollback) chỉ được thực hiện khi có sự đồng ý của Owner (Security Lead / Châu Thành Trung).
