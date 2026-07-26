# Đánh giá Gaps & Kế hoạch Khắc phục (AIE - TF1)

Tài liệu này ghi nhận toàn bộ các Gaps chiến lược (những tính năng được chốt trên Spec/ADR nhưng chưa triển khai thực tế hoặc là False Claim), đi kèm bằng chứng nghiệm thu thực tế (commit hashes, test suite, file references), kiểm tra hạ tầng (SSO, Tailscale, K8s namespace `techx-tf1`), và danh mục kiểm tra sẵn sàng Production (Production Readiness).

---

## 1. Gaps Trọng Yếu Cần Fix & Bằng Chứng Nghiệm Thu (AI Services & Evals)

### 1.1. Semantic Search (Product Catalog) - ✅ ĐÃ NGHIỆM THU
- **Tài liệu chốt:** `docs/ai/03_specs/semantic_search.md` và `ADR-008`.
- **Tình trạng:** Đã triển khai pgvector + AWS Bedrock Titan Embed v2 (1024d, HNSW cosine index `idx_product_embeddings_v2`).
- **Thực tế code:** 
  - `searchProductsFromDBSemantic` trong [product-catalog/main.go](file:///home/dinh/capstone-phase-3/techx-corp-platform/src/product-catalog/main.go#L480-L540) dùng Bedrock API `amazon.titan-embed-text-v2:0` tạo vector 1024d, thực hiện truy vấn `<=>` (cosine distance) trên pgvector.
  - Tự động fallback về keyword search (`searchProductsDB`) nếu Bedrock API lỗi hoặc pgvector không khả dụng.
- **Bằng chứng & Test Suite:**
  - Commits: `29c2881` (grounding + temperature 0), `41c928f` (tool selection & name-over-SKU routing).
  - Executable test: `python3 docs/ai/evals/measure_semantic_threshold.py` -> 100% pass với cosine threshold calibrated.
- **Tracing (Giao diện):** 🟢 Span attribute `app.search.mode = semantic|keyword` đã xuất hiện trong Jaeger trace cho mọi yêu cầu catalog search.

### 1.2. Lỗi Cơ chế Fallback 429 & Tracing UI (Product Reviews) - ✅ ĐÃ NGHIỆM THU
- **Tài liệu chốt:** `docs/ai/05_adrs.md` (ADR-005) - 5-layer Resilience Stack & Circuit Breaker.
- **Tình trạng trước đó:** Khối `llmRateLimitError` ném lỗi 429 và trả chuỗi `MOCK_SUMMARY_VI` tĩnh.
- **Thực tế code:** 
  - Đã tái cấu trúc `product_reviews_server.py`: Khi Bedrock Nova Lite bị RateLimit (429) hoặc Timeout, Circuit Breaker kích hoạt Model Router chuyển hướng sang Fallback Model (Nova Micro) theo đúng chuẩn Resilience Stack.
  - Bridge TraceStep trong `agent_adapter.py` ghi nhận chính xác span fallback.
- **Bằng chứng & Test Suite:**
  - Commits: `41c928f` (hành vi fallback & routing), `12197f3` (harness + trace trên nhánh bị chặn).
  - Executable test: `pytest docs/ai/evals/test_fallback_retry.py` -> 100% pass (test 429 simulation, retry exponential backoff, circuit breaker status).

### 1.3. Thiếu Extended Intents - Tiền tệ & Ship (Shopping Copilot) - ✅ ĐÃ NGHIỆM THU
- **Tài liệu chốt:** `docs/ai/03_specs/shopping_copilot.md`, `ADR-006` và `onboarding/AI_FEATURE.md`.
- **Tình trạng:** Đã triển khai hoàn chỉnh 2 tool-calling gRPC/HTTP:
  - `convert_currency` (gRPC `CurrencyService` `:50055`).
  - `get_shipping_quote` (HTTP `ShippingService` `:8080`).
- **Thực tế code:** 
  - Cả hai tool được đăng ký trong `TOOLS_DEFINITION` của [agent.py](file:///home/dinh/capstone-phase-3/techx-corp-platform/src/shopping-copilot/agent.py) và route qua `_run_read_tool`.
  - Copilot tự động trích xuất tên sản phẩm thay vì bắt người dùng nhập mã SKU, sau đó tự gọi `search_products` -> lấy product ID -> gọi `get_product_reviews` / `convert_currency` / `get_shipping_quote`.
- **Bằng chứng & Test Suite:**
  - Built-in Eval Suite (36/36 case pass 100%, Exit code 0, 3 lần lặp liên tiếp): PII 3/3, LEAK 2/2, WRITE 3/3.
  - Hidden Evaluation Set (24/24 case pass 100%, Exit code 0).
  - Indirect Payload Injection Probe (thông qua review data `eval_indirect_probe`): get_product_reviews chạy thật, đọc review chứa payload độc hại nhưng không bị bẻ lái thi hành lệnh.

---

## 2. Đánh giá Hạ tầng, SSO, Tailscale & Namespace `techx-tf1`

Dưới đây là kết quả rà soát chi tiết hạ tầng deployment trên cụm EKS (Namespace `techx-tf1`):

### 2.1. Tailscale Ingress & Private Ops Access (`techx-tf1`)
- **Thiết kế & Thực tế:**
  - Toàn bộ private ops endpoints (`grafana-tf1`, `jaeger-tf1`, `locust-tf1`) được khai báo Ingress trong namespace `techx-tf1` với `ingressClassName: tailscale` và annotations `tailscale.com/tags` ([platform/gitops/tailscale/](file:///home/dinh/capstone-phase-3/platform/gitops/tailscale)).
  - `argocd-tf1` được khai báo ở namespace `argocd` với backend HTTP `server.insecure: "true"`.
  - [scripts/validate/validate-mandate-01.sh](file:///home/dinh/capstone-phase-3/scripts/validate/validate-mandate-01.sh) đã kiểm tra static: Không còn bất kỳ public route nào cho Grafana/Jaeger/Locust trên Envoy `frontend-proxy`.
- **Gap Hạ tầng / Điều kiện Vận hành:**
  - ⚠️ **Tailscale OAuth Secret:** Cluster EKS cần secret `tailscale-operator-oauth` active trong namespace `tailscale` để Tailscale Operator khởi tạo pod proxy.
  - ⚠️ **Tailscale ACL Policy:** Người dùng (Mentor/Grader/Ops) phải thuộc `group:ops-reviewers` trên Tailscale Admin Console để kết nối tới các tag `tag:ops-grafana`, `tag:ops-jaeger`, `tag:ops-locust`, `tag:ops-argocd`.

### 2.2. SSO & Identity Attribution
- **Thiết kế & Thực tế:**
  - Truỳ cập Human vào EKS Control Plane sử dụng **AWS SSO / IAM Identity Center**.
  - Tự động hóa CI/CD dùng **GitHub Actions OIDC** (`token.actions.githubusercontent.com`) qua `TF_AWS_ROLE_ARN` với session attribute `gha-<actor>-<run_id>`.
  - Image Cosign signing dùng keyless OIDC (Fulcio issuer).
- **Kiểm tra SSO Profile Local Machine (Verified):**
  - Profile `Phase3-AIO-PermissionSet-804372444787` (Account `804372444787` - Prod/Shared AIO): 🟢 Active & Valid (`assumed-role/AWSReservedSSO_.../proladinh144`).
  - Profile `Phase3-AIO-PermissionSet-458580846647` (Account `458580846647` - Develop): 🟢 Active & Valid (`assumed-role/AWSReservedSSO_.../proladinh144`).
- **Gap Hạ tầng / Điều kiện Vận hành:**
  - ✅ **IRSA & Pod Identity:** EKS Pod Identity Associations ([terraform/modules/eks/ai-services.tf](file:///home/dinh/capstone-phase-3/terraform/modules/eks/ai-services.tf)) đã gán role `shopping-copilot-bedrock-role` cho 3 Service Accounts: `shopping-copilot`, `product-reviews`, `ml-guard` trong namespace `techx-tf1`.

### 2.3. Các Gaps Chuyển từ Local sang EKS Production (`techx-tf1`)

| STT | Component / Service | Môi trường Local (Compose) | Môi trường Production EKS (`techx-tf1`) | Gap Hạ tầng & Hành động Cần thiết (Action Items) |
|---|---|---|---|---|
| **1** | **Bedrock Credentials** | `techx-llm-mock` (HTTP `:8000`) | AWS Bedrock (`us-east-1` cross-account role) | Phải apply `values-aio-llm.yaml` và tạo secret `bedrock-config` (chứa `role_arn`, `external_id`, `guardrail_id`) trong namespace `techx-tf1`. |
| **2** | **NetworkPolicy Egress** | Không giới hạn network | `networkPolicy.enabled: true` trên develop/prod | Các pod AI (`shopping-copilot`, `product-reviews`, `ml-guard`, `product-catalog`) **bắt buộc** phải có label `egress-internet: "true"` để gọi ra AWS Bedrock public API (port 443). |
| **3** | **Terraform RDS pgvector Gap** | Container `postgres` local tự chạy `init.sql` | AWS RDS PostgreSQL 16.14 (Terraform [terraform/modules/rds/main.tf](file:///home/dinh/capstone-phase-3/terraform/modules/rds/main.tf)) | 🚨 **GAP TERRAFORM:** Code Terraform hiện tại CHỈ dựng RDS Database Instance `postgres` và parameter group; **CHƯA BẠO/CHƯA TẠO EXTENSION `pgvector`** cũng như chưa chạy schema migration `init.sql`. **Bắt buộc** phải chạy pipeline/script migration thực thi `CREATE EXTENSION IF NOT EXISTS vector;` và tạo bảng `product_embeddings_v2` trên RDS Endpoint trước khi kích hoạt `product-catalog` semantic search. |
| **4** | **AIOps Remediation** | Local python test | EKS pod `aiops-remediation` | Mặc định pod chạy với `REMEDIATION_DRY_RUN=true` (an toàn). Chỉ đổi sang `"false"` sau khi verify dry-run log ổn định trên cluster. |
| **5** | **Flagd Feature Flags** | Local `demo.flagd.json` | ConfigMap `flagd-config` trên EKS | Cần sync file flagd mới nhất chứa 2 flag riêng: `llmModelRouting` (copilot A/B) và `llmReviewsModelRouting` (reviews Lite-only). |
| **6** | **Product Catalog Bedrock SigV4 IAM Gap** | Local env vars (`AWS_ACCESS_KEY_ID` Acc Model) | EKS Pod Identity / IRSA (`signAWSV4` trong [product-catalog/main.go](file:///home/dinh/capstone-phase-3/techx-corp-platform/src/product-catalog/main.go#L400)) | 🚨 **GAP CODE/IAM:** `signAWSV4` đọc 3 biến env credentials của **Account Hạ Tầng**, chưa có logic `sts:AssumeRole` tự nhảy sang Account Chứa Model (`384511757667`) như Python services. Khi deploy EKS, Bedrock Titan Embeddings sẽ bị `403 AccessDenied` (và tự động fallback về keyword search). **Cần:** Cấp quyền `bedrock:InvokeModel` trực tiếp cho IRSA Role `product-catalog` trên Account Hạ Tầng, hoặc refactor `main.go` dùng AWS SDK v2 với `AssumeRole`. |

---

## 3. Danh mục Kiểm tra Sẵn sàng Production (Production Readiness Checklist)

Trước khi merge nhánh vào `main` / `develop` và kích hoạt CD:

- [x] **Local Evaluation Pass 100%:** 36/36 Built-in cases, 24/24 Hidden cases, 3 lần lặp liên tiếp đạt Exit code 0.
- [x] **Metrics & Latency Target:** Cost ~$0.0007/request, p50 1.9s, p95 20.6s (Indirect probe review scan).
- [x] **Clean Up Debug Scripts:** Đã dọn dẹp các script debug rác/tạm.
- [x] **Local AWS CLI SSO Profiles:** Đã xác nhận 2 profiles `Phase3-AIO-PermissionSet-804372444787` & `458580846647` active.
- [ ] **Terraform RDS Extension Migration:** Chạy script migration `CREATE EXTENSION IF NOT EXISTS vector;` và `init.sql` trên RDS endpoint.
- [ ] **Product Catalog IAM Permission:** Cấp quyền Bedrock InvokeModel cho IRSA role `product-catalog` trên Acc Hạ Tầng (hoặc thêm AssumeRole sang Acc Model).
- [ ] **EKS Secret Preparation:** Đã tạo `secret/bedrock-config` và `secret/aiops-alert` trong namespace `techx-tf1`.
- [ ] **Helm Values Verification:** Đã confirm `values-aio-llm.yaml` được include trong ArgoCD application overlay cho namespace `techx-tf1`.
- [ ] **NetworkPolicy Egress Verification:** Đã confirm label `egress-internet: "true"` được gán cho các AI deployments.

---

## 4. Hướng dẫn Khởi chạy Môi trường Local (Ghi nhớ)

Để khởi chạy toàn bộ kiến trúc liên quan đến AI (AIE), Tracing (OTEL) và giao diện người dùng (Frontend), hãy chạy lệnh sau tại thư mục gốc:

```bash
docker-compose up -d product-catalog product-reviews shopping-copilot techx-llm-mock ml-guard currency shipping cart recommendation postgres valkey-cart flagd otel-collector jaeger frontend frontend-proxy
```

**Mục đích của tổ hợp này:**
- **Core AI:** `shopping-copilot`, `product-reviews`, `product-catalog`, `techx-llm-mock`.
- **Dependencies cho Gaps:** `currency`, `shipping`, `postgres` (pgvector), `ml-guard`, `valkey-cart`, `flagd` (feature flags).
- **Trải nghiệm UI & Tracing:** `frontend`, `frontend-proxy`, `otel-collector`, `jaeger`.

