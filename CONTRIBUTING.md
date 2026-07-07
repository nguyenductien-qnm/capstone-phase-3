# Hướng dẫn Đóng góp Code & Quy trình Git (Contributing Guidelines)

Tài liệu này hướng dẫn quy chuẩn Commit và quy trình gửi Pull Request (PR) trong dự án.

### 1. Quy chuẩn Commit Message

Commit message tuân thủ định dạng Semantic Commits:
`<type>(<scope>): <subject>`

**Các `type` được chấp nhận:**

- `feat`: Thêm tính năng mới.
- `fix`: Sửa lỗi.
- `docs`: Cập nhật tài liệu (ADR, Postmortem, Readme...).
- `refactor`: Tối ưu, cấu trúc lại code (không thay đổi logic).
- `style`: Định dạng code (khoảng trắng, format...) không ảnh hưởng logic.
- `test`: Viết thêm hoặc chỉnh sửa test cases.
- `chore`: Cấu hình, build tool, gitignore, setup môi trường...

**Các `scope` mẫu thường dùng:**

- Tầng App: `app/frontend`, `app/product-reviews`, `app/cart`, `app/checkout`, `app/llm`...
- Tầng Infra: `infra/helm`, `infra/terraform`, `infra/k8s`, `infra/observability`.
- Chung: `docs`, `cicd`, `configs`.

Ví dụ:

- `feat(app/reviews): check prompt injection in user review`
- `fix(infra/helm): adjust resources for cart pod`
- `docs(readme): update getting started instructions`

---

### 2. Quy trình gửi và duyệt Pull Request (PR)

1. **Tuyệt đối không push trực tiếp vào nhánh `main`** (nhánh đã được cấu hình bảo vệ).
2. Tạo nhánh tương ứng từ **`main`**, thực hiện code và kiểm tra chạy thử kỹ ở local.
3. Push nhánh lên remote GitHub.
4. Tạo Pull Request (PR) từ nhánh của bạn vào **`main`**.
5. Điền đầy đủ thông tin vào PR template tự động sinh (Mô tả, link Jira task, kết quả test local).
6. Tag/Thông báo cho Tech Lead và các thành viên khác trong nhóm để review.
7. Yêu cầu ít nhất **1 approval** để có thể merge PR vào **`main`**.
