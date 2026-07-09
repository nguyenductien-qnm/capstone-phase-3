# Templates tài liệu - Phase 3 TechX Corp Takeover

File này giải thích **mọi thứ**: tại sao có từng template, khi nào viết, chấm ở đâu, điền thế nào. Các file template chỉ có tiêu đề + gợi ý ngắn "điền gì" - phần lý do nằm hết ở đây. Đọc file này trước khi mở template.

## 5 template = 5 deliverable bắt buộc

Phase 3 chấm qua vận hành, không qua "docs đẹp". Mỗi template ánh xạ đúng 1 deliverable trong `RULES.md §7`. Không có template thừa.

> 📖 RULES.md §7: "Backlog ưu tiên + bản pitch (Tuần 1). · Decision log / ADR ký tên cho mọi quyết định lớn. · Postmortem / COE ký tên sau mỗi sự cố. · Ops Review hằng tuần. · Service Health Readout cuối kỳ."

| Template | Deliverable | Ai viết | Khi nào |
|---|---|---|---|
| `00_backlog.md` | Backlog ưu tiên + pitch | Cả TF (mỗi nhóm góp việc theo trụ) | Tuần 1, chốt trước pitch cuối T1 |
| `ADR-log.md` | Decision log / ADR ký tên | Người ra quyết định | Mỗi quyết định lớn, xuyên suốt |
| `postmortem.md` | Postmortem / COE ký tên | Người trực on-call | Sau mỗi sự cố |
| `ops-review.md` | Ops Review hằng tuần | Nhóm cầm chính tuần đó | Cuối mỗi tuần |
| `service-health-readout.md` | Service Health Readout | Cả TF | Cuối kỳ (điền dần từ T2) |

## Cách dùng

1. Copy template ra file thật (giữ template gốc sạch). Đặt tên rõ: `ADR-log.md`, `postmortem-INC-01.md`, `ops-review-w2.md`.
2. Điền theo gợi ý dưới mỗi tiêu đề. Xóa dòng gợi ý (dòng `>` in nghiêng) sau khi điền.
3. **Ký tên** - mọi quyết định/sự cố phải truy được về người (RULES §8). Không ký = coi như chưa nộp.
4. Commit theo tuần.

## Chi tiết từng template

### `00_backlog.md` - Backlog ưu tiên
**Deliverable quan trọng nhất Tuần 1.** Pitch cuối T1 chấm *judgment*, không chấm code. Hội đồng đóng vai PM/CFO/SRE-lead vặn thứ tự ưu tiên của bạn.

> 📖 PITCH_GUIDE.md: "Phase 3 đo *judgment* nhiều hơn *code*. Chọn sai ưu tiên = cày nhầm việc suốt hai tuần còn lại."

Công thức xếp hạng (bắt buộc dùng, xem `onboarding/PITCH_GUIDE.md`):
> 📖 PITCH_GUIDE.md: "**Ưu tiên = Rủi ro (khả năng xảy ra × mức nghiêm trọng) × Tác động business (hậu quả với khách / doanh thu / SLA / chi phí / uy tín).**"

Tác động business đo bằng onboarding packet, KHÔNG bằng "có phải feature không":
- `SLO.md` → luồng nào ra tiền (checkout ≥99% = revenue-critical, ưu tiên nhất).
- `BUDGET.md` → việc này tốn/tiết kiệm bao nhiêu trong trần $300/tuần.
- `INCIDENT_HISTORY.md` + `ARCHITECTURE.md` → chỗ nào từng làm khách khổ, chỗ nào là điểm chết đơn lẻ (SPOF).

**"Cố ý bỏ" cũng được chấm** - biết bỏ đúng việc tác động thấp là kỹ năng.
> 📖 PITCH_GUIDE.md: "Bảo vệ thứ tự - vì sao việc A trước việc B, và **cố ý bỏ gì lúc này**. Bỏ đúng cũng là một kỹ năng được chấm."
> 📖 SLO.md: "Checkout là luồng quan trọng nhất (ra tiền) - ưu tiên bảo vệ nó trước."

Điểm soi đầu tiên khi tự đánh giá (từ incident history + trụ của TF1/CDO-05):
- Reliability: `valkey-cart` SPOF (INC-2), deploy gating chưa đồng bộ (INC-3), connection pool dưới tải cao (INC-1).
- Security: secrets management, RBAC least-privilege trong chart, NetworkPolicy giữa service, image scanning, phơi Grafana/Jaeger.
- Auditability: K8s audit log, CloudTrail, change management cho `helm upgrade`.
- Cost: right-size resource, log/metric retention, node/autoscaling, spot.

### `ADR-log.md` - Decision log
**Append-only.** 1 quyết định lớn = 1 ADR. Không xóa ADR cũ; khi hết áp dụng đánh dấu `Thay thế bởi ADR-NNN`.

Viết ADR khi: quyết định có **trade-off thật**, **reversal cost cao**, hoặc **sẽ bị hỏi "sao chọn vậy?"** ở buổi chấm. KHÔNG viết cho chuyện nhỏ không đánh đổi (đặt tên resource...).

Phase 3 bắt buộc mỗi ADR có: **cost Δ (vs trần $300/tuần)**, **ảnh hưởng SLO**, **rollback plan**, **người ký**. Đây là thứ được chấm ở directive/quyết định lớn.
> 📖 mandates/README.md: "Directive được chấm ở **cách bạn làm** (zero-downtime, an toàn dữ liệu, cost, bảo mật, rollback), không phải chỉ "có làm xong hay không"."
> 📖 RULES.md §8: "Fair play: mọi quyết định phải truy được về người (ký tên). Không mượn kết quả của TF khác."

### `postmortem.md` - Postmortem / COE
1 file / sự cố. Viết sau khi sự cố đóng.

**Phân loại sự cố (RULES §8 - quan trọng):**
- **flagd bơm vào** (BTC tạo) → mục tiêu là **làm hệ chịu được** (fallback / retry / containment), KHÔNG tắt cơ chế. Tắt/đổi hướng flagd = **disqualify**.
- **Lỗi cấu hình thật** (thiếu sót trong hệ) → **sửa tận gốc**.

> 📖 RULES.md §8: "Điểm yếu do cấu hình (thiếu sót thật trong hệ thống) thì **sửa tận gốc**; sự cố do ban tổ chức bơm vào thì **làm hệ thống chịu được** (fallback, retry, containment) chứ không "tắt cho hết lỗi"."
> 📖 RULES.md §8: "**Sự cố là để xử lý, không phải để tắt.** ... Nghiêm cấm can thiệp, vô hiệu hóa, hay đổi hướng cơ chế này. Vi phạm = **loại khỏi vòng đánh giá (disqualify)**."

Ghi rõ sự cố thuộc loại nào - chấm dựa trên bạn xử đúng kiểu hay không. Đo **MTTD/MTTR**, ảnh hưởng khách bằng **% SLO tụt**.

### `ops-review.md` - Ops Review hằng tuần
Mốc kiểm tra hằng tuần. Báo trạng thái service bằng số, không kể lể.

Bắt buộc: SLO vs target (nguồn Prometheus/Grafana), error budget còn/cháy, ngân sách đã tiêu vs $300, sự cố + MTTR, backlog burned/added, directive đã xử. Cháy error budget → đóng băng thay đổi rủi ro, ghi rõ.
> 📖 SLO.md: "**Cháy budget** (đã lỗi vượt mức) → đóng băng thay đổi rủi ro, tập trung ổn định lại trước."
> 📖 BUDGET.md: "**Vượt trần = vi phạm ràng buộc**, tính vào trụ Cost khi chấm. Không phải cứ chi nhiều là mạnh - **hiệu quả chi phí trên mỗi đơn vị tải** mới là thứ được nhìn."

### `service-health-readout.md` - Readout cuối kỳ
Bản trình bày cuối trước hội đồng (bị phản biện). Điền dần từ Tuần 2, chốt Tuần 3. Trả lời: đã làm gì, đánh đổi gì, vì sao, service khỏe/yếu ra sao, tiếp theo gì. Dẫn link tới ADR + postmortem làm bằng chứng.
> 📖 RULES.md §5: "Hội đồng **nghe và phản biện (bắt bẻ)** - nhắm vào quyết định và trạng thái service của cả đội, có thể hỏi thẳng một cá nhân để kiểm chứng chiều sâu."

## Quy ước chung

- **Markdown only.** Diagram dùng Mermaid inline; ảnh đặt `assets/`.
- **Ký tên** mọi ADR + postmortem. Truy được về người = tiêu chí chấm.
- **Dẫn link chéo**: readout dẫn ADR/postmortem; postmortem dẫn ADR follow-up; backlog dẫn ADR khi việc được quyết.
- **Số phải tái tạo được**: SLO/cost/MTTR dẫn nguồn (Grafana query, Cost Explorer). Số không tái tạo = coi như chưa chứng minh.
- Đừng vượt trần ngân sách, đừng phá SLO của TF khác (RULES §8).

## Tham chiếu
- `../RULES.md` §7 (deliverables), §8 (luật chơi)
- `../onboarding/PITCH_GUIDE.md` (công thức ưu tiên + hội đồng vặn gì)
- `../onboarding/SLO.md`, `BUDGET.md`, `INCIDENT_HISTORY.md`, `ARCHITECTURE.md`
