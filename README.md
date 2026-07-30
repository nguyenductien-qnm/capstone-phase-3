# Phase 3 - TechX Corp Service Takeover

Chào mừng đến Phase 3. Đây là vòng cuối: các bạn **tiếp quản một sản phẩm AI đang chạy** của TechX Corp - một storefront thương mại điện tử gồm nhiều microservice trên Kubernetes, có hàng đợi, cơ sở dữ liệu, một tính năng AI tóm tắt review, và đầy đủ observability. Hệ thống này **đang sống và chưa hoàn hảo**: có chỗ chưa tối ưu về chi phí, bảo mật, độ tin cậy, khả năng mở rộng và truy vết.

Nhiệm vụ không phải "làm bài tập". Nhiệm vụ là **vận hành sản phẩm này như một kỹ sư thật**: tự đánh giá, tự ưu tiên, giữ SLA, xử lý sự cố, cải tiến dưới ràng buộc - và bảo vệ được mọi quyết định của mình.

## Đọc gì trước

1. **[RULES.md](RULES.md)** - thể lệ đầy đủ: cấu trúc TF, 5 trụ (Security / Reliability / Performance Efficiency / Cost Optimization / Auditability) + trụ AI, timeline 3 tuần, và **luật chơi** (đọc kỹ mục luật - có điều khoản disqualify).
2. **[onboarding/](onboarding/)** - hiểu hệ thống bạn tiếp quản: [ARCHITECTURE](onboarding/ARCHITECTURE.md), [SLO](onboarding/SLO.md), [BUDGET](onboarding/BUDGET.md), [INCIDENT_HISTORY](onboarding/INCIDENT_HISTORY.md), [AI_FEATURE](onboarding/AI_FEATURE.md) (nhóm AIO), [PITCH_GUIDE](onboarding/PITCH_GUIDE.md).
3. **[GETTING_STARTED.md](GETTING_STARTED.md)** - cách build hệ thống từ source, đẩy image lên ECR của TF, rồi deploy và kiểm tra.

## Repo này có gì

| Đường dẫn | Nội dung |
|---|---|
| `RULES.md` | Thể lệ Phase 3 (bắt buộc đọc) |
| `onboarding/` | Kiến trúc, SLO, ngân sách, lịch sử sự cố, pitch guide - hiểu hệ thống trước khi đụng vào |
| `GETTING_STARTED.md` | Hướng dẫn build → deploy → verify |
| `mandates/` | Directive bắt buộc BTC thả vào trong lúc vận hành (trống lúc đầu) |
| `techx-corp-platform/` | Toàn bộ source code sản phẩm (microservice, AI review + LLM, observability) |
| `aiops/` | Log clustering và detector phục vụ AIOps |
| `terraform/` | Terraform modules và cấu hình theo môi trường |
| `platform/charts/` | Helm chart triển khai application và observability hiện tại |
| `platform/gitops/` | ArgoCD applications và values theo môi trường |
| `platform/policies/` | Chính sách và resource governance cho Kubernetes |
| `scripts/` | Script bootstrap, build, deploy và validate |
| `docs/` | Tài liệu dùng chung và tài liệu theo nhóm AI/CDO |

## Việc đầu tiên: đưa hệ thống lên chạy

Chính việc dựng được hệ thống và đưa nó lên chạy **là bước tiếp quản đầu tiên** - và đã được tính điểm. Bắt đầu từ [GETTING_STARTED.md](GETTING_STARTED.md).

Sau khi hệ thống chạy: đọc kiến trúc, hiểu SLO/ngân sách/lịch sử, dựng backlog ưu tiên, và chuẩn bị cho buổi pitch bảo vệ ưu tiên cuối Tuần 1.

## Vài điều cần nhớ

- **Mỗi TF tự build image → đẩy lên ECR của account mình → deploy trên account của mình.** BTC cấp source + một image seed để khởi động.
- **Sự cố sẽ đến trong lúc vận hành.** Nhiệm vụ là phát hiện và xử lý để khách hàng ít bị ảnh hưởng nhất - **không phải tắt nó đi**. Cơ chế tạo sự cố do BTC kiểm soát; can thiệp/vô hiệu hóa nó = disqualify (xem RULES - mục Luật chơi).
- **Mọi quyết định phải truy được về người** (ADR / decision log ký tên). Đây là thứ được chấm.

Chúc các đội giữ được service khỏe và tỏa sáng.
