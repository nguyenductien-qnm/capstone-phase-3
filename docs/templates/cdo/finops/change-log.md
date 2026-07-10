# Change Management Log cho FinOps/IaC

## Mục đích

Tài liệu này ghi nhận các thay đổi liên quan đến tagging, labeling và quản trị chi phí trong phạm vi Phase 3 - TechX Corp. Change log giúp mentor/PM truy vết lý do thay đổi, rủi ro, cách kiểm tra và phương án rollback.

## Quy tắc bắt buộc

- Mọi thay đổi phục vụ task CDO-39 phải có Change ID.
- Mỗi dòng change log phải nêu rõ owner, component bị ảnh hưởng, lý do, rủi ro, validation và rollback plan.
- Không ghi nhận thay đổi đã deploy nếu chưa có evidence kiểm tra.
- Không dùng change log để hợp thức hóa thay đổi ngoài phạm vi task.
- Không ghi nhận thay đổi làm ảnh hưởng selector Kubernetes nếu chưa có phân tích rủi ro riêng.

## Change Log Table

| Date | Change ID | Owner | Component | Change Type | Reason | Risk | Validation | Rollback Plan |
|---|---|---|---|---|---|---|---|---|
| 2026-07-09 | CHG-001 | Nguyễn Tấn Huy | Helm chart labels | Add | Bổ sung tagging strategy cho Kubernetes resources mới. | Thấp; chỉ thêm metadata labels, không sửa selectorLabels. | `helm lint` và `helm template`, kiểm tra `techx.io/*` trong rendered manifest. | Revert thay đổi trong `values.yaml`, `_helpers.tpl`, `_objects.tpl`, `component.yaml`. |
| 2026-07-09 | CHG-002 | Nguyễn Tấn Huy | FinOps docs | Add | Tạo tài liệu tagging strategy và change management log. | Thấp; chỉ bổ sung tài liệu. | Review Markdown và link từ README. | Revert các file trong `docs/finops/`. |

## Ý nghĩa từng cột

| Cột | Ý nghĩa |
|---|---|
| Date | Ngày ghi nhận thay đổi theo định dạng `YYYY-MM-DD` |
| Change ID | Mã thay đổi duy nhất, ví dụ `CHG-003` |
| Owner | Người chịu trách nhiệm chính |
| Component | Thành phần bị ảnh hưởng |
| Change Type | Loại thay đổi: Add, Update, Remove, Fix |
| Reason | Lý do thực hiện thay đổi |
| Risk | Rủi ro kỹ thuật hoặc vận hành |
| Validation | Cách kiểm tra sau thay đổi |
| Rollback Plan | Phương án khôi phục nếu thay đổi gây lỗi |

## Template cho change mới

| Date | Change ID | Owner | Component | Change Type | Reason | Risk | Validation | Rollback Plan |
|---|---|---|---|---|---|---|---|---|
| YYYY-MM-DD | CHG-XXX | Nguyễn Tấn Huy | `<component>` | Add/Update/Fix/Remove | `<reason>` | `<risk>` | `<validation command/evidence>` | `<rollback steps>` |

## Ví dụ change log cho Helm labels

| Date | Change ID | Owner | Component | Change Type | Reason | Risk | Validation | Rollback Plan |
|---|---|---|---|---|---|---|---|---|
| 2026-07-09 | CHG-003 | Nguyễn Tấn Huy | `techx-corp-chart/templates/_helpers.tpl` | Update | Thêm helper render FinOps labels dùng chung. | Thấp; có thể lỗi indent YAML nếu helper render sai. | `helm template techx-corp ./techx-corp-chart -n techx-tf1` và kiểm tra labels. | Revert helper mới và include liên quan. |

## Trách nhiệm của FinOps/IaC Engineer

- Duy trì tagging/labeling strategy nhất quán cho tài nguyên mới.
- Kiểm tra rendered manifest trước khi đề xuất deploy.
- Không thay đổi selectorLabels nếu không có yêu cầu kỹ thuật rõ ràng.
- Cung cấp evidence cho Jira và mentor/PM.
- Cập nhật change log khi có thay đổi liên quan đến IaC, Helm labels hoặc cost allocation.

## Owner

- Nguyễn Tấn Huy
- FinOps/IaC Engineer
- TF1 / CDO09
