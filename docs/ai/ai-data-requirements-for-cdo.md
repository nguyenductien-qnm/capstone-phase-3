# Nhu cầu dữ liệu của tầng AI — tài liệu cho nhóm CDO (đánh giá thay thế OpenSearch)

> Trả lời câu hỏi CDO 11/07: "muốn hiểu nhu cầu dữ liệu bên AI để tính toán thay thế OpenSearch".
> Mọi con số trong doc này là **số đo** trên stack chạy thật (docker compose, image build từ source) hoặc **trích từ code** — có ghi nguồn từng dòng. Chỗ nào chưa đo có đánh dấu ⏳.

## 1. Các service nhóm AI vận hành, và chúng đụng dữ liệu gì

| Service | Chạy ở đâu | Đọc | Ghi | Đụng OpenSearch? |
|---|---|---|---|---|
| `product-reviews` (AI summary path) | Pod in-cluster, gRPC `:3551` | PostgreSQL `reviews.productreviews` (50 dòng), `catalog.products` (10 dòng); Bedrock API; flagd | Valkey cache (≤10 key, mỗi key ~1KB JSON) | **Không** — chỉ *phát* log/trace/metric qua OTel collector như mọi service khác |
| `tools/aiops-detector` | 1 pod nhỏ (poll loop) | Prometheus (3 rule PromQL) + **OpenSearch (5 rule log)** | Webhook Slack/Discord (alert) | **Có — consumer OpenSearch duy nhất của nhóm AI** |
| `aiops/log_clustering` (Drain3) | CronJob batch | Log text thô (hiện đọc qua OpenSearch) | Template/cluster report | **Có** — chỉ cần đọc raw lines theo khoảng thời gian |
| Shopping Copilot (tuần 2+) | Pod mới | `product-catalog`, `product-reviews`, `cart` qua gRPC; Bedrock | — | **Không** |

Kết luận nhanh cho CDO: **toàn bộ phụ thuộc OpenSearch của tầng AI nằm gọn trong 2 tool AIOps, qua đúng 2 kiểu truy vấn** — không có phụ thuộc ẩn.

## 2. Chính xác tầng AI cần gì từ backend log

### 2.1 Query pattern (trích nguyên văn từ `tools/aiops-detector/sources.py`)

Kiểu 1 — đếm phrase trong cửa sổ trượt (5 rule × poll 30s = **10 query/phút**):
```json
POST /otel-logs-*/_search (size=1)
{"query":{"bool":{
  "filter":[{"range":{"observedTimestamp":{"gte":"now-5m"}}}],
  "should":[{"match_phrase":{"body":"<cụm lỗi>"}}, ...],
  "minimum_should_match":1}}}
```
Mỗi query trả về **1 con số + 1 dòng log mẫu**. Hết.

Kiểu 2 — đọc batch raw lines theo khoảng thời gian (Drain3, 1 lần/chu kỳ CronJob).

### 2.2 Những gì tầng AI **KHÔNG** cần (đừng trả tiền cho nó)

- Full-text relevance scoring / inverted index toàn văn — chỉ cần phrase match.
- Aggregation phức tạp, ML plugin, alerting plugin của OpenSearch.
- Dashboard riêng (đã dùng Grafana).
- Realtime/streaming: **không cần** — vì sao: MTTD = ingest lag (2.1s, đo) + gom min_count + offset poll (≤30s); stream chỉ xoá được vế poll (~15–30s) mà không bỏ được logic cửa sổ 5 phút, trong khi MTTD hiện tại (max 35.4s) đã pass target 2 phút với biên 3.4× — đổi 1 consumer service chạy 24/7 (state, reconnect, thêm điểm hỏng, thêm RAM trong trần $300) lấy ~30s không có giá trị theo đề. Poll stateless, 0.08% duty (đo).
- Retention dài: **detection chỉ cần 5 phút dữ liệu** — không phải ý kiến: mọi rule log trong `rules.yaml` query đúng `now-5m`, detector không bao giờ đọc cũ hơn. RCA lookback 24–72h là trần thực tế vì: SLO đo rolling **24h** (SLO.md) → mọi câu hỏi vỡ-SLO chỉ cần 24h; Ops Review tuần dùng metrics tổng hợp Prometheus (giữ riêng), không cần raw log; kịch bản xa nhất là sự cố tối thứ 6 đào lại sáng thứ 2 ≈ 60h → trần 72h. Thứ giữ lâu là kết luận (postmortem/ADR/template), không phải raw log. Tiền: 220MB/ngày × 3d ≈ 660MB vs 30d ≈ 6.6GB — gấp 10 storage cho dữ liệu không ai mở. **Phạm vi: 3 ngày đủ cho nhu cầu AI** — nhu cầu audit/compliance của CDO (nếu có) cộng riêng.
- Vector search (đề xuất semantic search pgvector đã bị review đánh giá là thừa với catalog 10 sản phẩm — `review-week1-verification.md` mục I).

### 2.3 Volume & độ trễ (số đo)

| Đại lượng | Số đo | Nguồn |
|---|---|---|
| Log volume dưới tải locust full | **~180–240k docs/ngày** (241k ngày 08/07, 181k ngày 09/07) | `_cat/indices` trên OS local |
| Dung lượng store | **~1.1KB/doc** (894.9kb / 808 docs) → **~220MB/ngày** ở tải full, chưa tính replica | `_cat/indices?h=store.size` |
| Chi phí 1 query detector | **P50 5ms, P95 12ms** (n=30; corpus nhỏ — sẽ tăng theo index size nhưng vẫn cỡ ms) | đo trực tiếp |
| Ingest lag (log sinh → query được) | **P50 2.1s, max 5.1s** (n=8) | `docs/ai/evals/measure_detection_pipeline.py` |
| MTTD end-to-end (bơm sự cố flagd → alert, poll 30s) | **mean ~19.6s, max ~35.4s** (5 vòng) | như trên |
| Tải query từ detector | 10 query/phút, mỗi query 1 số + 1 doc | `rules.yaml` |

**Ràng buộc duy nhất tầng AI đặt lên backend mới: ingest lag + query phải giữ MTTD ≤ 2 phút** (target suy từ error budget SLO: non-5xx 0.5%/24h ≈ 7.2 phút/ngày). Hiện OpenSearch cho 35s — dư 3.4×, tức backend mới được phép chậm hơn đáng kể mà vẫn đạt đề.

## 3. Tiêu chí so sánh phương án (đề nghị CDO chấm theo bảng này)

1. RAM/CPU chiếm trên node (→ tiền EC2, ràng buộc $300/tuần).
2. Storage/ngày với retention 3d.
3. Có phrase-count-over-window query không (nhu cầu 2.1).
4. Ingest lag (→ MTTD, đo bằng script có sẵn).
5. OTel collector có exporter chính chủ không (đường log hiện là OTLP → collector → backend).
6. Công vận hành (số container, config, nâng cấp).

## 4. Phương án đã research (chưa chốt — quyết định hạ tầng là của CDO)

| Phương án | Fit nhu cầu 2.1? | Footprint (theo tài liệu — ⏳ cần đo tại chỗ) | Ghi chú |
|---|---|---|---|
| **A. Giữ OpenSearch, bóp lại** | ✓ nguyên trạng | Heap là chi phí chính — nhu cầu trên chỉ cần 512MB–1GB heap, 1 node, ISM retention 3d | Zero migration. Nếu "tốn" hiện tại do heap mặc định + retention vô hạn thì bóp trước khi thay |
| **B. Grafana Loki** (single-binary + filesystem/S3) | ✓ — LogQL `count_over_time({ns="techx-corp"} \|= "phrase" [5m])` đúng nghĩa đen query detector cần; query range trả raw lines cho Drain3 | Index label-only → RAM/storage thấp hơn hẳn full-text index | Loki ≥3.0 nhận **OTLP native** — collector chỉ cần `otlphttp` exporter sẵn có (lokiexporter cũ đã deprecated, đừng dùng). Grafana đọc native. Detector đổi adapter trong `sources.py` (~50 dòng, phần query đã tách riêng) |
| **C. VictoriaLogs** | ✓ LogsQL tương đương | Nhẹ nhất theo docs nhà sản xuất | Ecosystem/exporter non trẻ hơn Loki |
| **D. Bỏ backend log, chỉ Prometheus** | ✗ | — | Mất phrase-match + Drain3 → hỏng AIOps core của đề. **Loại.** |

Nguồn so sánh: [Loki vs Elasticsearch 2026](https://lucaberton.com/blog/loki-vs-elasticsearch-2026/), [Kubernetes logging tools 2026](https://metoro.io/blog/kubernetes-logging-tools), [ELK alternatives](https://last9.io/blog/top-elk-alternatives/).

## 5. Đề xuất cách chốt (đo, không cãi bằng niềm tin)

1. CDO cho **con số "tốn" hiện tại** của OpenSearch (RAM request/limit, EBS GB, % node) — baseline.
2. Dựng Loki (1 container) chạy **song song** OS 24h, collector export cả hai.
3. Đo cùng lúc: RAM/CPU/storage hai bên + chạy `docs/ai/evals/measure_detection_pipeline.py` trỏ từng backend → so ingest lag + MTTD táo-với-táo.
4. Chốt bằng bảng tiêu chí mục 3. Tầng AI cam kết: đạt MTTD ≤ 2 phút là OK với bất kỳ backend nào — **không có lock-in từ phía AI.**

---
*Nhóm AIO03 — 2026-07-12. Số đo tái tạo bằng script trong `docs/ai/evals/`.*

---

## 6. Trả lời trực tiếp 4 câu hỏi CDO (12/07 — question.md)

**Q1. AI có dùng OpenSearch query log không? Có bắt buộc OpenSearch không?**
Có dùng — đúng 2 consumer: `tools/aiops-detector` (5 rule log, phrase-count cửa sổ 5m, 10 query/phút, mỗi query trả 1 số + 1 sample) và `aiops/log_clustering` (Drain3, đọc batch raw lines theo khoảng thời gian, CronJob). **KHÔNG bắt buộc OpenSearch.** Nhu cầu thật chỉ là: (a) đếm dòng khớp phrase trong cửa sổ thời gian, (b) đọc raw lines theo range. Loki/VictoriaLogs/OpenSearch bóp nhỏ đều đạt (bảng so sánh mục 4). Lớp query đã tách trong `sources.py` — đổi backend ≈ 50 dòng adapter. Ràng buộc duy nhất: pipeline giữ MTTD ≤ 2 phút (hiện đo được 35.4s max, dư 3.4×).

**Q2. Input của AI lấy cụ thể gì (log/metrics/trace)?**
| Input | Ai dùng | Cụ thể | Bắt buộc? |
|---|---|---|---|
| **Metrics** (Prometheus) | detector (6 rule PromQL) | `http_server_request_duration_seconds_*` theo `service_name`; (draft) `container_memory_working_set_bytes` + `kube_pod_container_resource_limits` — cần **kube-state-metrics + cadvisor** trên EKS | ✅ |
| **Logs** (OpenSearch hiện tại) | detector (5 rule) + Drain3 | index `otel-logs-*`, field `body` + `observedTimestamp`; retention 3d đủ (mục 2.2) | ✅ (backend thay được) |
| **Traces** (Jaeger) | Người vận hành RCA; **không tool AI nào query tự động** trong tuần 1 | 1 trace xuyên 12 service đã verify (mục 7) | ⚠️ giữ cho RCA; AI chưa đọc máy |
| Business data (PostgreSQL) | product-reviews, copilot | `catalog.products` (10), `reviews.productreviews` (50) — read-only | ✅ |
| Flags (flagd) | product-reviews, copilot | `llmReviewsFallbackEnabled`, `llmReviewsCacheEnabled` (+ cờ sự cố BTC) | ✅ |

**Q3. Requirement service để deploy AI (Bedrock, AgentCore...)?**
- **Bedrock runtime** (`bedrock-runtime`, us-east-1): models `amazon.nova-lite-v1:0`, `nova-micro-v1:0` (reviews), `nova-pro-v1:0` (copilot W2). **Cần CDO cấp IAM `bedrock:InvokeModel`** qua IRSA cho serviceAccount `product-reviews` (sau này thêm `shopping-copilot`) hoặc node role — **đang thiếu, là blocker deploy thật duy nhất từ phía hạ tầng.**
- **KHÔNG cần**: AgentCore/Bedrock Agents (copilot tự dựng tool-calling qua Converse API — zero managed-agent cost), Knowledge Bases/OpenSearch Serverless (đã loại — catalog 10 sản phẩm, xem `specs/semantic_search.md` phụ lục), GPU/SageMaker.
- Env/flag mới cho chart: xem bảng trong `contracts/product-reviews-integration.md` phụ lục 12/07 (cần CDO re-sign).
- Copilot W2: pod mới gRPC `:50051`, envoy route + cluster đã có trong `envoy.tmpl.yaml`; chart để `enabled: false` tới khi có image.

**Q4. Chỉnh lại structure code bên AI — ĐÃ LÀM (12/07):**
- Root repo: 6 file copilot PoC + `database.db` rải ở root → gom về **`copilot-poc/`** (kèm README); `__pycache__` bị commit → gỡ khỏi git + `.gitignore` thêm `__pycache__/`, `*.pyc`, `*.db`.
- Docs: bổ sung bộ chuẩn `01_requirements.md`, `02_solution_design.md`, `04_eval_report.md` (khớp khung evidence-pack course); index tổng ở `docs/ai/README.md`.
- Evals: dataset 5→34 case; script đo thật (4 file) thay mô phỏng.

## 7. Trace continuity — ĐÃ VERIFY (12/07, bổ sung cho telemetry-audit)
Jaeger API (compose stack): **1 trace duy nhất `8e7b90520fad0c60` chứa span của 12 service** (load-generator → frontend-proxy → frontend → checkout → payment/email/shipping/cart/currency/product-catalog/quote/flagd); đường GenAI: 1 trace xuyên load-generator → frontend-proxy → frontend → product-reviews. **Trace context không đứt** qua Envoy.
