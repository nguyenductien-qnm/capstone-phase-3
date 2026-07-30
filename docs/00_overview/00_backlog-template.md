# Backlog ưu tiên - TF__ / __

> Lý do & công thức xếp hạng: xem `README.md`. Điền xong xóa các dòng `>`.
> Cấu trúc: 1 board chung cho Hạ tầng & CI/CD + 5 board riêng cho 5 trụ (mỗi trụ 1 board).
> Xếp hạng trong từng board từ cao xuống. Rủi ro = khả năng × mức nghiêm trọng. Tác động business dẫn SLO/budget/incident.

## 1. Đánh giá hệ thống hiện tại
> Tóm tắt kiến trúc đang vận hành (1 đoạn) + 3-5 rủi ro lớn nhất nhìn ra, mỗi rủi ro dẫn SLO/incident/SPOF nào.

## Cách chấm Story point (đọc trước khi điền board)

Story point = độ lớn **tương đối** của việc, gộp 3 yếu tố: khối lượng + độ phức tạp + độ bất định (chưa chắc chắn). **Không phải giờ công, không phải tiền** - chi phí $ ghi trong ADR của việc đó khi quyết.

Thang Fibonacci (1, 2, 3, 5, 8, 13):

| Điểm | Cỡ việc | Ví dụ |
|---|---|---|
| 1 | Sửa config nhỏ, rõ ràng, < nửa ngày, không rủi ro | Bật scan-on-push trên ECR |
| 2 | Việc rõ ràng, ~ nửa - 1 ngày, ít phụ thuộc | Thêm AWS Budgets alert |
| 3 | 1-2 ngày, đã hiểu cách làm, cần test | Thêm probe toàn chart |
| 5 | 2-3 ngày, nhiều thành phần hoặc cần test kỹ khỏi vỡ luồng | NetworkPolicy default-deny |
| 8 | ~ 1 tuần, bất định cao, nhiều bước phụ thuộc nhau | Load test → right-size → HPA trọn gói |
| 13 | Quá lớn - **phải tách nhỏ** trước khi đưa vào board | Migrate DB sang managed |

Luật chấm:
- **Chấm bằng đồng thuận nhóm** (planning poker: mỗi người ra số cùng lúc, lệch nhau thì người cao nhất + thấp nhất giải thích, bàn xong ra số lại).
- **So tương đối với việc chuẩn (anchor):** chọn 1 việc cả nhóm đã hiểu rõ làm mốc 3 điểm, mọi việc khác so với nó ("to gấp đôi mốc → 5 hoặc 8").
- **Bất định cao → chấm cao hơn**, không chấm thấp rồi "để xem" - chưa biết cách làm chính là một phần độ lớn.
- **Việc > 8 điểm = tách nhỏ** rồi mới xếp hạng - board không nhận việc 13.

## 2. Board Hạ tầng & CI/CD (nền tảng chung - không thuộc trụ riêng)
> Việc dựng/duy trì nền: Terraform, EKS, ECR, ArgoCD/GitOps, pipeline build-push, quota... Ghi trụ liên quan nếu việc phục vụ trực tiếp 1 trụ.

| # | Việc | Trụ liên quan | Rủi ro (khả năng×nghiêm trọng) | Tác động business | Story point | Vì sao ưu tiên bậc này |
|---|------|---------------|-------------------------------|-------------------|-------------|------------------------|
| 1 | | | | | | |
| 2 | | | | | | |

## 3. Board Security (Bảo mật)

| # | Việc | Rủi ro (khả năng×nghiêm trọng) | Tác động business | Story point | Vì sao ưu tiên bậc này |
|---|------|-------------------------------|-------------------|-------------|------------------------|
| 1 | | | | | |
| 2 | | | | | |

## 4. Board Reliability (Độ tin cậy)

| # | Việc | Rủi ro (khả năng×nghiêm trọng) | Tác động business | Story point | Vì sao ưu tiên bậc này |
|---|------|-------------------------------|-------------------|-------------|------------------------|
| 1 | | | | | |
| 2 | | | | | |

## 5. Board Performance Efficiency (Hiệu năng)

| # | Việc | Rủi ro (khả năng×nghiêm trọng) | Tác động business | Story point | Vì sao ưu tiên bậc này |
|---|------|-------------------------------|-------------------|-------------|------------------------|
| 1 | | | | | |
| 2 | | | | | |

## 6. Board Cost Optimization (Chi phí)

| # | Việc | Rủi ro (khả năng×nghiêm trọng) | Tác động business | Story point | Vì sao ưu tiên bậc này |
|---|------|-------------------------------|-------------------|-------------|------------------------|
| 1 | | | | | |
| 2 | | | | | |

## 7. Board Auditability (Truy vết)

| # | Việc | Rủi ro (khả năng×nghiêm trọng) | Tác động business | Story point | Vì sao ưu tiên bậc này |
|---|------|-------------------------------|-------------------|-------------|------------------------|
| 1 | | | | | |
| 2 | | | | | |

## 8. Cố ý bỏ (lúc này)
> Việc gì KHÔNG làm tuần này + lý do 1 dòng (tác động thấp / chi phí cao / chưa tới lúc). Bỏ đúng được chấm.

## 9. Ký tên
> Người trình + nhóm · ngày.
