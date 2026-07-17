# Hợp Đồng Tích Hợp Kỹ Thuật (Integration Contract) — Shopping Copilot Service

* **Đơn vị sở hữu**: AI Team (AIO03) & Platform Team (CDO)
* **Trạng thái**: Draft
* **Ngày cập nhật**: 2026-07-09

Tài liệu này đặc tả cam kết tích hợp kỹ thuật cho dịch vụ **Shopping Copilot** (Python gRPC Server trên cổng `50051`) để phục vụ tính năng hội thoại mua sắm thông minh (AI Agent) trực tiếp trên storefront.

---

## 1. Cổng Dịch Vụ & Định Tuyến (Port & Envoy Routing)

Để tích hợp gRPC service Shopping Copilot vào hệ thống chung của TechX Corp:

1. **Cổng Dịch Vụ**: Pod `shopping-copilot` sẽ lắng nghe các kết nối gRPC trên cổng **`50051`**.
2. **Định tuyến Envoy Proxy**: Nhóm CDO có trách nhiệm cấu hình Envoy (`frontend-proxy`) để giải mã và định tuyến các request gRPC-Web từ client.
   - Thêm cụm dịch vụ (cluster) mới tên là `shopping-copilot` trỏ tới cổng `50051`.
   - Định tuyến các request có prefix `/oteldemo.ShoppingCopilotService/` sang cluster `shopping-copilot`.
   - Bật hỗ trợ gRPC-Web filter trong Envoy để chuyển tiếp chính xác dữ liệu từ trình duyệt của khách hàng.

---

## 2. Thông Số Môi Trường & Kết Nối (Env Variables)

Dịch vụ `shopping-copilot` nhận các biến môi trường cấu hình kết nối sau:

| Tên biến | Kiểu dữ liệu | Giá trị mặc định / Mô tả |
| :--- | :--- | :--- |
| `SHOPPING_COPILOT_PORT` | Integer | `50051` (Cổng chạy gRPC của Agent) |
| `LLM_HOST` | String | `llm` (Host chạy dịch vụ Mock LLM) |
| `LLM_PORT` | Integer | `8000` (Cổng của dịch vụ Mock LLM) |
| `LLM_BASE_URL` | String | `http://llm:8000/v1` (Địa chỉ API OpenAI-compatible của LLM) |
| `LLM_MODEL` | String | `techx-llm` (Tên model mặc định) |
| `OPENAI_API_KEY` | String | `dummy` (API key gọi Mock LLM) |
| `PRODUCT_CATALOG_ADDR` | String | `product-catalog:8080` (Địa chỉ gRPC phục vụ công cụ tra cứu catalog) |
| `CART_ADDR` | String | `cart:8080` (Địa chỉ gRPC phục vụ công cụ quản lý giỏ hàng) |
| `PRODUCT_REVIEWS_ADDR` | String | `product-reviews:3551` (Địa chỉ gRPC phục vụ công cụ lấy review) |
| `FLAGD_HOST` | String | `flagd` (Host của OpenFeature Flagd) |
| `FLAGD_PORT` | Integer | `8013` (Cổng kết nối Flagd) |

---

## 3. Ràng Buộc Tài Nguyên K8s (Kubernetes Resource Limits)

Pod `shopping-copilot` giữ nguyên baseline — **CDO đã xác nhận (17/07/2026)** rằng bật Phase-2 Local ML Guard (`LLM_LOCAL_ML_GUARD=true`) không thay đổi resource của service này ("Local" = self-hosted pod `ml-guard` riêng, không phải in-process; service chỉ gọi HTTP, không load model):

* **CPU Request / Limit**: `200m` / `1000m`
* **Memory Request / Limit**: `256Mi` / `1024Mi`

### 3.1. Pod `ml-guard` (dùng chung cho shopping-copilot + product-reviews)

Toàn bộ model ML (ProtectAI DeBERTa ~738MB, mDeBERTa-xnli NLI, Presidio/SpaCy) load duy nhất trong pod `ml-guard`:

* **Replicas**: 1 · **Port**: 8090 · **Service**: ClusterIP `ml-guard` (namespace `techx-tf1`)
* **CPU Request / Limit**: `500m` / `1000m`
* **Memory Request / Limit**: `1280Mi` / `1536Mi`
* **readinessProbe**: `initialDelaySeconds: 90` — model load mất 25–90s; probe mặc định sẽ kill pod trước khi torch load xong
* **Env chốt cho 2 service tiêu thụ**: `ML_GUARD_URL=http://ml-guard:8090` (không còn là giá trị ví dụ)
* Guardrails **fail-open** khi ml-guard chưa sẵn sàng (PII vẫn mask bằng regex) — thứ tự khởi động không gây lỗi chuỗi.

---

## 4. Đặc Tả Telemetry (Prometheus & Jaeger Contract)

Cam kết tích hợp OpenTelemetry phục vụ việc giám sát hoạt động của Agent:

### 4.1. Trace Context Propagation (Jaeger)
* **W3C Trace Context**: Shopping Copilot cam kết truyền nhận đầy đủ trace context (`traceparent`, `tracestate`) từ client storefront đi qua Envoy, vào dịch vụ Copilot và lan truyền tiếp sang các microservice hạ nguồn (`product-catalog`, `cart`, `product-reviews`) và dịch vụ LLM.
* **Span Attributes**: Các span gọi LLM của Copilot Agent bắt buộc chứa:
  - `gen_ai.system`: `"openai"` (hoặc `"bedrock"` khi chuyển sang LLM thật).
  - `gen_ai.model_id`: Tên model sử dụng.
  - `gen_ai.usage.prompt_tokens`: Số lượng token đầu vào.
  - `gen_ai.usage.completion_tokens`: Số lượng token đầu ra.

### 4.2. Prometheus Custom Metrics
Dịch vụ sẽ export các metric sau phục vụ hệ thống Dashboard giám sát của CDO:

1. **`copilot_chat_requests_total`** (Counter):
   - Đếm tổng số lượt yêu cầu hội thoại gửi tới Shopping Copilot.
   - Nhãn (Labels): `status` (`success`, `error`).
2. **`copilot_tool_calls_total`** (Counter):
   - Thống kê số lần Agent gọi các công cụ (tool calling) hạ nguồn.
   - Nhãn (Labels): `tool_name` (`search_products`, `get_product_reviews`, `add_item_to_cart`, `get_cart`), `status` (`success`, `error`).
3. **`copilot_chat_latency_seconds`** (Histogram):
   - Đo thời gian phản hồi tổng thể của một phiên hội thoại chat (từ lúc gửi request tới khi trả về text cuối cùng cho khách hàng).
   - Buckets đề xuất: `[0.5, 1.0, 2.5, 5.0, 7.5, 10.0]`.

---

## Phụ lục 14/07/2026 — Cập nhật AWS Bedrock & Model Gateway (Đua Top)

Các cập nhật liên quan tới triển khai AWS Bedrock và A/B Testing:

1. **Chuyển dịch sang AWS Bedrock:** `shopping-copilot` sử dụng SDK boto3 để gọi trực tiếp Amazon Bedrock thay vì gọi Mock LLM (`http://llm:8000/v1`). 
   - **Yêu cầu hệ thống (CDO):** Cấp quyền IAM Role for Service Accounts (IRSA) với Policy `bedrock:InvokeModel` cho pod `shopping-copilot`. Thiếu quyền này ứng dụng sẽ không thể hoạt động trên môi trường EKS.
   - **Bedrock Account 2:** Không dùng access key tĩnh. Nếu Bedrock nằm ở account khác, service dùng IRSA mặc định rồi assume role qua `BEDROCK_AWS_ROLE_ARN`; role IRSA cần `sts:AssumeRole`, role đích cần `bedrock:InvokeModel`.
   - **Budget/quota:** Quota/model access tính theo account đang invoke Bedrock. Budget detector chỉ đọc được org/account cost nếu IRSA/role của detector có quyền `ce:*`/`budgets:*` hoặc assume được role đọc cost tương ứng.
2. **Routing qua Model Gateway:** `shopping-copilot` hiện sử dụng component `ModelRouter` để lấy cấu hình model từ OpenFeature/flagd.
   - **Biến flagd mới:** Cờ `llmModelRouting` (kiểu JSON Object) dùng chung với `product-reviews` để xác định tỷ lệ % traffic A/B.
3. **Môi trường & Biến Cấu hình:**
   - Cần đảm bảo có biến `AWS_REGION` (vd: `us-east-1`).
   - Cần biến `AWS_BEDROCK_MODEL` hoặc để Router tự điều phối. Các biến cũ `LLM_BASE_URL` và `OPENAI_API_KEY` chỉ giữ lại làm Fallback nếu sử dụng chế độ Mock.

---

## 5. Phụ lục 14/07/2026 — Action Gate & AI Safety (MANDATE-06)

Để ngăn chặn Copilot tự ý thực hiện các hành động thay đổi dữ liệu (Excessive Agency), chúng tôi đã thiết lập **Action Gate (Xác nhận 2 bước)**. Đội Frontend / CDO cần cập nhật tích hợp để xử lý JSON response từ Agent:

1. **Khi User ra lệnh "Thêm vào giỏ hàng"**:
   - Copilot sẽ KHÔNG gọi trực tiếp `CartService`.
   - Copilot sẽ trả về Frontend một JSON Object yêu cầu xác nhận:
     ```json
     {
       "action": "add_item_to_cart",
       "status": "pending_confirmation",
       "confirmation_token": "token-12345",
       "item_id": "product-uuid",
       "quantity": 1
     }
     ```
2. **Nhiệm vụ của Frontend**:
   - Bắt được JSON này -> Hiển thị nút bấm (VD: "Xác nhận thêm vào giỏ").
   - Khi khách hàng bấm xác nhận, gọi một HTTP request mới kèm `confirmation_token` (hoặc gửi lại vào khung chat) để báo cho Copilot biết đã cấp quyền thực thi.

Vui lòng cấu hình UI xử lý kịp thời để luồng thêm vào giỏ hàng của Agent không bị kẹt.

## 7. Phụ lục 17/07/2026 (chiều) — ML Guard Cascade (ADR-014, thay §6)

§6 dưới đây **hạ cấp thành option** (ADR-014): docs AWS xác nhận Bedrock contextual
grounding chỉ EN/FR/ES (không VN) và prompt-attack VN cần Standard tier → Bedrock
Guardrails default OFF. Thay bằng cascade: regex T0 → **ml-guard pod (NLI)** →
**Nova judge**. Eval 18/18 pass (`docs/ai/evals/eval_mandate06_v5_report.md`).

### 7.1 Resource ask gửi CDO — deploy pod `ml-guard` (AI cung cấp image + values)

Số đo thật 17/07 (bench local, fp32, 2 threads): RSS **1148MB**, grounding p50 **1.8s**.

| Thông số | Giá trị đề nghị | Căn cứ đo |
|---|---|---|
| CPU request / limit | `500m` / `1000m` | 2 torch threads; serialize 1 inference/lượt |
| Memory request / limit | `1280Mi` / `1536Mi` | RSS 1148MB + headroom |
| Replicas | 1 (không HPA — traffic Ask AI 10 view:1 call) | |
| Port | `8090` HTTP (`/healthz`, `/metrics`, `/v1/grounding`) | |
| Probes | readiness `/healthz` (model load ~25–90s → `initialDelaySeconds: 60`) | đo local 25s |
| Image | build từ `techx-corp-platform/src/ml-guard/` — model nướng sẵn, **không egress HF Hub** | |
| Quota | CDO-42 hiện peak 3.45/4.00 cores → thêm 0.5 = 3.95 **sát trần**. Đề nghị nâng `requests.cpu` quota lên **4.5** hoặc xác nhận chấp nhận rủi ro sát trần | docs/cdo09/cdo-42 |

### 7.2 Env bổ sung cho `product-reviews` + `shopping-copilot`

| Env | Default | Ý nghĩa |
|---|---|---|
| `ML_GUARD_URL` | `""` (tắt) | `http://ml-guard:8090` khi pod sẵn sàng; tắt → cascade rơi xuống judge |
| `LLM_JUDGE_MODEL` | `amazon.nova-micro-v1:0` | grounding judge (đo 4/4 VN) |
| `LLM_INJECTION_JUDGE_MODEL` | `amazon.nova-lite-v1:0` | injection judge (đo 7/7 VN; Micro chỉ 4/7) |
| `LLM_INJECTION_JUDGE` | `true` | tắt được để degrade về regex-only |
| `LLM_BEDROCK_GUARDRAIL` | **`false`** (đổi từ §6) | option Standard-tier sau này |

### 7.3 IAM / region (quan trọng)
- Judge chạy **`us-east-1`** (Nova đã mở model access — test 17/07 qua profile `default`,
  acct 384511757667, cùng org). SSO role `Phase3-CDO-PermissionSet` bị `OperationNotAllowed`
  ở us-east-1 → **CDO cần cấp IRSA/role cho 2 pod app gọi `bedrock:InvokeModel` (Nova Lite +
  Micro) ở us-east-1**, hoặc mở model access cùng region đang dùng.
- Pod `ml-guard` KHÔNG cần IAM (model local, không gọi AWS).

### 7.4 TF1-65 — ECR push (phối hợp, không tự đẩy)
AI team **có quyền admin nhưng không push image ECR trực tiếp**. Cần CDO:
1. Tạo ECR repo `ml-guard` + policy như các service hiện có.
2. CI build workflow đã dynamic-detect service mới (`techx-corp-platform/src/ml-guard/`) —
   chỉ cần approve chạy pipeline build+scan (Trivy gate CRITICAL/HIGH giữ nguyên).
3. GitOps: thêm component `ml-guard` vào values env sandbox theo thông số §7.1.

## 6. Phụ lục 17/07/2026 — Bedrock Guardrails (TF1-61, thay guardrail v3) — **superseded bởi §7**

Guardrail nội-code (v3 hand-rolled) được thay bằng **Amazon Bedrock Guardrails** managed
(xem `docs/ai/adr-012-bedrock-guardrails.md`). Áp dụng cho **cả `shopping-copilot` và
`product-reviews`**. Action Gate ở §5 **giữ nguyên** (excessive-agency là app code, không
phải guardrail engine).

**Contract với CDO — chỉ cần cấp env, không đụng application code:**

| Env | Nguồn | Ý nghĩa |
|---|---|---|
| `BEDROCK_GUARDRAIL_ID` | output TF `terraform/ai-guardrails/` (AI-owned) | id guardrail resource |
| `BEDROCK_GUARDRAIL_VERSION` | output TF (numbered, **không dùng DRAFT** ở prod) | version pin |
| `LLM_BEDROCK_GUARDRAIL` | `values-aio-llm.yaml` (default `true`) | flag bật/tắt; tắt → degrade regex pre-filter |

- Tiêm qua `platform/gitops/environments/sandbox/values-aio-llm.yaml` (AI-owned). Guardrail
  resource ở **module TF riêng, state riêng, KHÔNG chạm module CDO**. Nếu account boundary
  chặn `terraform apply` → CDO apply hộ `terraform/ai-guardrails/`, app chỉ cần id+version.
- **IAM:** service role của 2 pod cần `bedrock:ApplyGuardrail` trên ARN guardrail (region
  `us-east-2`, cùng nơi Nova/Titan chạy).
- **Hành vi:** INPUT rail fail-**closed** (chặn khi lỗi); OUTPUT grounding fail-**open** nhưng
  vẫn mask PII. Guardrail lỗi/tắt → không treo trang (degrade an toàn).
- **Lưu ý PII log:** mask chỉ áp lên response API; raw PII vẫn vào CloudWatch model-invocation
  log → nếu bật, KMS-encrypt + siết IAM log group.

