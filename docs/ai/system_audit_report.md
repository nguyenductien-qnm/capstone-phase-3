# Báo cáo Audit Hệ thống & Rà soát Gaps (Tuần 2)

Tài liệu ghi nhận kết quả đánh giá toàn diện hạ tầng tự động hóa, kiểm thử hồi quy (regression) và bảo mật của Nhóm AI (TF1), tuân thủ các chỉ dẫn từ skill `automation-audit-ops`, `ai-regression-testing`, và `security-review`.

---

## 1. Inventory & Trạng thái Tự động hóa (Automation Audit)

Dưới đây là bảng phân loại trạng thái các thành phần tự động hóa và tích hợp của dịch vụ AI:

| Hạng mục | Đường dẫn / Môi trường | Trạng thái | Bằng chứng (Proof Path) | Đề xuất (Action) |
|---|---|---|---|---|
| **Valkey Caching** | ElastiCache Valkey Managed | ✅ Authenticated & Verified | [product_reviews_server.py:448](file:///home/dinh/capstone-phase-3/techx-corp-platform/src/product-reviews/product_reviews_server.py#L448) (Valkey cache hit log) | **KEEP** |
| **Model Router** | OpenFeature/flagd `:8013` | ✅ Configured & Verified | [model_router.py:26](file:///home/dinh/capstone-phase-3/techx-corp-platform/src/shopping-copilot/model_router.py#L26) (routed model logs) | **KEEP** |
| **AIOps CI** | `.github/workflows/aiops-ci.yaml` | ✅ Verified (CI pass) | [aiops-ci.yaml](file:///home/dinh/capstone-phase-3/.github/workflows/aiops-ci.yaml) (runs pytest for detector/clustering) | **KEEP** |
| **App CI/CD (CDO)** | `.github/workflows/app-build.yaml` | 🔴 **Broken / Stale (GAP LỚN)** | [app-build.yaml:20-31](file:///home/dinh/capstone-phase-3/.github/workflows/app-build.yaml#L20-L31) (Không khai báo path filter cho 3 services AI) | ⚠️ **FIX-NEXT** |
| **Local Git Hooks** | `.git/hooks/` | ❌ Missing | Thư mục trống | **KEEP** (Không cần thiết ở Phase 3) |

---

## 2. Kiểm thử hồi quy (AI Regression Testing: Sandbox vs Prod)

> [!WARNING]
> **Rủi ro số 1 của AI: AI tự viết code và tự review dẫn đến lọt lỗi cú pháp/logic.**

### Phát hiện & Khắc phục:
* **Sự cố:** Rà soát tệp [recommendation_server.py](file:///home/dinh/capstone-phase-3/techx-corp-platform/src/recommendation/recommendation_server.py#L48) phát hiện 4 docstring nháy kép ba bị escape nhầm thành `\"\"\"` thay vì `"""` ở các dòng 48, 53, 94, 99. Lỗi này do AI tự sửa ở session trước nhưng không chạy kiểm thử local, gây ra lỗi nghiêm trọng `SyntaxError: unexpected character after line continuation character` khiến gRPC server không thể compile.
* **Hành động khắc phục:** Đã dọn dẹp và sửa lại thành `"""` chuẩn. Đã chạy `pytest test_recommendation.py` và pass 100%.

### Đánh giá tính nhất quán (Consistency Audit):
- **Shopping Copilot:** Logic chạy offline (`eval_mandate06.py --mode offline` sử dụng `MockStub`) và logic chạy online (`copilot_server.py` + Bedrock) được đồng bộ hoàn toàn. Không có sự sai lệch trong việc bọc tham số hoặc xử lý session history.

---

## 3. Rà soát An toàn Bảo mật (Security Review)

### Secrets Management:
- **Kết quả:** Đã quét toàn bộ codebase của `product-reviews`, `shopping-copilot` và `recommendation`. Không phát hiện bất kỳ AWS credentials, database passwords hay API keys nào bị hardcoded trần trong mã nguồn. Toàn bộ được trích xuất thông qua biến môi trường (ENV) hoặc cấu hình IAM Role.

### Input/Output Validation Boundaries:
- **Input Guardrail (L1):** Đã verify `sanitize_text` ở cổng gRPC request `request.question` của Copilot để chặn đứng prompt injection độc hại trước khi đưa vào LLM.
- **Tool Output Sanitization:** Dữ liệu thô từ DB (chứa reviews/catalog có nguy cơ nhiễm độc do người dùng spam reviews) được bọc qua `sanitize_json_for_llm` trước khi nhét vào prompt của LLM.

---

## 4. Danh sách GAP cần xử lý tiếp theo (Fix-next)

> [!IMPORTANT]
> **GAP Chí mạng: Thiếu cấu hình build/push ECR cho 3 services AI trong CI/CD pipeline.**
> - **Mô tả:** File `.github/workflows/app-build.yaml` chỉ build & deploy cho các service cũ (`cart`, `checkout`, `frontend-proxy`, `product-catalog`). Khi ta push code mới của `product-reviews`, `shopping-copilot` hay `recommendation`, GitHub Actions CI/CD **không** tự động build Docker Image mới và push lên ECR $\rightarrow$ ArgoCD trên EKS tiếp tục deploy container từ image cũ (hoặc lỗi thiếu image).
> - **Giải pháp đề xuất:** Nhờ CDO (hoặc tự tay nhóm AI) bổ sung path filters và matrix build cho 3 services AI vào `app-build.yaml` và cấu hình biến image tag tương ứng.
