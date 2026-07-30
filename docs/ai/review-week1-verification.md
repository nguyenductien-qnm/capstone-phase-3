# Review độc lập Tuần 1 — Verify work AIO03 vs baseline & evidence

> Nhánh: `review/week1-baseline-verify` · Ngày: 2026-07-11 · Không commit/push theo yêu cầu.
> Phương pháp: diff `_baseline-phase3` ↔ repo, đọc toàn bộ `onboarding/`, `docs/ai/`, code `product-reviews`, chart/deploy; đối chiếu từng con số với nguồn ngoài (websearch) và với chính nguồn nhóm tự cite.

## TL;DR

Nền tảng docs tốt hơn mặt bằng chung (ADR có phương án loại, có đính chính, pitch tự khai gap). Nhưng: **1 bug CRITICAL làm chết toàn bộ fallback trong cluster thật**, 2 con số chủ chốt **sai so với chính nguồn nhóm cite**, luận điểm CFO trung tâm (credit Claude) **chưa verify và có khả năng outdated**, và phần "đo trước–sau" là **mô phỏng random với tỉ lệ lỗi tự bịa** — đúng loại "số cảm tính" mà grading bar loại thẳng ("số không tái tạo được coi như chưa chứng minh"). Bên AIOps: rules bám SLO chuẩn mực (điểm cộng), nhưng **KPI detector cũng là số synthetic** và **một rule GenAI đã chết một nửa** vì code PR#26 đổi log message.

---

## Nguyên tắc kiểm chứng — mỗi loại claim một phương pháp chuẩn

Không chấp nhận/bác claim theo cảm tính; mỗi finding dưới đây gắn với phương pháp phù hợp với *loại* claim:

| Loại claim | Phương pháp chuẩn | Áp dụng trong review này |
|---|---|---|
| Config/flag hành vi | Đọc config thật + code default path (không tin spec) | A1 (grep flagd JSON + đọc `check_feature_flag`) |
| Cơ chế concurrency | Thí nghiệm deterministic tái tạo được, test cả phương án fix | B1 (script 3 kịch bản, kết quả bên dưới) |
| Latency model/API | Đo trực tiếp P50/P95 trên endpoint thật; benchmark bên thứ ba chỉ là proxy | B3 — **blocked: AWS creds trong shell invalid** (`sts get-caller-identity` fail); script đo để sẵn, cần chạy khi có creds |
| Billing/credit | Test giao dịch thật + Cost Explorer, hoặc văn bản điều khoản credit từ BTC | B4 — **blocked cùng lý do**; không được kết luận thay bằng blog |
| Error-rate/độ bền | Chaos test thật (flagd) + đọc Prometheus trước/sau, có timestamp | B5, G3 — chưa nhóm nào làm; mô phỏng random không thay thế được |
| Premise dữ liệu ("review tĩnh") | Kiểm tra đường ghi: proto rpc + SQL seed + code write path | C2 — **đã verify đúng**: `demo.proto` không có rpc ghi review, server không có INSERT/UPDATE/DELETE, `init.sql` seed sẵn |
| Giá niêm yết/EOL/tham số thư viện | Đối chiếu trang chính chủ (pricing page, endoflife, docs lib) | Mục E — đã làm |
| Judgment/luật cuộc thi (vd B2) | Không tự phán được — hỏi BTC/mentor, ghi nhận là rủi ro cho tới khi có trả lời | B2 |

Bài học tự thân từ review này: **đề xuất fix ban đầu của chính tôi cho B1 (semaphore < pool) cũng sai** — chỉ lộ ra khi chạy thí nghiệm. Mọi khuyến nghị chưa qua phương pháp chuẩn đều phải coi là giả thuyết.

## Bộ tiêu chí đánh giá work nhóm AI — neo vào đề (không phải chuẩn ngành chung)

"Tối ưu" trong review này định nghĩa theo đề: **thoả ràng buộc đề với chi phí + độ phức tạp thấp nhất**. Mỗi tiêu chí trích thẳng từ văn bản đề, kèm thước đo và phương pháp kiểm chứng:

| # | Đề quy định (nguồn) | Thước đo | Phương pháp kiểm chứng | Trạng thái nhóm |
|---|---|---|---|---|
| T1 | "Không bao giờ show tóm tắt sai cho khách" (SLO.md dòng 13, AI_FEATURE) | 0 summary sai/bịa khi LLM lỗi | Chaos flagd + đọc response thật về storefront | ⚠️ A1 làm fallback chết → chỉ còn mock message (đúng T1 nhưng ngoài ý muốn) |
| T2 | "Chạy thật, không mockup — build → deploy" (AI_FEATURE) | Stack deploy được, request đi hết luồng thật | `docker compose up` + smoke test (đã chạy trong review này) | ❌ Image hub 1.0 crash với compose mới (thiếu `LLM_BASE_URL`); image mới chưa push; Bedrock thiếu creds (C4) |
| T3 | "Eval tái tạo được; số không tái tạo được coi như chưa chứng minh" (AI_FEATURE) | Số đo từ hệ thật, script+data committed, chạy lại ra số | Chạy lại eval từ repo sạch | ❌ B5/G3: mô phỏng random, golden set 5 mẫu, không CI |
| T4 | SLO không tụt: p95<1s, non-5xx≥99.5%, checkout≥99% (SLO.md) | Metric Prometheus trước/sau thay đổi AI | Load test + so 2 cửa sổ đo | ⚠️ Chưa đo; B1 cho thấy cơ chế bảo vệ p95 là no-op |
| T5 | AIOps core: "phát hiện → xử lý an toàn → verify, **chạy liên tục**" (RULES.md §4) | Detector sống liên tục; MTTD nhỏ so error budget (non-5xx 0.5%/24h ≈ 7.2 phút/ngày; checkout 1% ≈ 14.4 phút) | Đo MTTD thật bằng chaos flagd — G4 (đo trong review này) | ⚠️ Poll loop đạt "chạy liên tục"; MTTD xem kết quả đo G4 |
| T6 | Budget $300/tuần; "quyết định tốn tiền phải cân lợi ích + ADR" (BUDGET.md) | Cost model có mẫu số kiểm chứng được | Billing test / Cost Explorer | ⚠️ Mẫu số 10:1 có nguồn ✓; claim credit Claude chưa verify (B4) |
| T7 | Cấm "tắt/đổi hướng cơ chế sự cố (flagd)" (AI_FEATURE §3) | Không code path đọc flag sự cố để né sự cố | Đọc code | ⚠️ B2: circuit breaker đọc `llmRateLimitError` — vùng xám, cần hỏi BTC |
| T8 | Cart write phải có cổng xác nhận (CLAUDE.md, AI_FEATURE Phần B) | Không tool ghi giỏ chạy không confirm | E2E copilot + prompt injection test | ✅ **Đã xác nhận 15/07:** Code đã hoàn thiện trên nhánh `feat/TF1-57-59-68` với Action Gating (xem ADR-011). |

Hệ quả cho câu hỏi poll interval (G4): đề chỉ đòi (a) chạy liên tục, (b) phát hiện nhanh so với error budget, (c) không phá budget hạ tầng. Không có chữ nào đòi realtime → poll là đúng đề; số poll chốt bằng phép đo G4, không phải bằng chuẩn ngành.

## A. CRITICAL

### A1. Fallback không bao giờ chạy trong cluster — flag không tồn tại, default False
- `check_feature_flag()` → `client.get_boolean_value(flag_name, False)` (`product_reviews_server.py:601-604`).
- `llmReviewsFallbackEnabled` **không được định nghĩa** trong cả `techx-corp-platform/src/flagd/demo.flagd.json` lẫn `techx-corp-chart/flagd/demo.flagd.json` (grep = 0 match; diff baseline chỉ thêm `llmReviewsCacheEnabled`).
- Hệ quả: flagd trả default `False` → khi Nova Lite lỗi, code **bỏ qua Nova Micro**, raise → trả mock message. Toàn bộ headline PR#26 (fallback routing) chết-khi-deploy.
- Unit test không bắt được vì `test_fallback_retry.py:55` mock `check_feature_flag` trả `True` — test xác nhận logic, không xác nhận cấu hình.
- Spec `fallback_retry.md` §4 ghi "Mặc định: `true`" — sai so với code+config thực tế.
- **Đã xác nhận ở runtime thật** (compose stack, image build từ source): primary Bedrock fail nhưng log `"Fallback routing triggered"` xuất hiện **0 lần** — request rơi thẳng xuống mock message, Nova Micro không bao giờ được gọi.
- **Fix:** thêm flag vào 2 file flagd JSON (defaultVariant `on`), hoặc đổi default trong code thành `True` cho flag này; thêm 1 integration test đọc flagd JSON thật.

## B. HIGH

### B1. Bulkhead = no-op: Semaphore(10) trên thread pool đúng 10 thread
- gRPC server: `ThreadPoolExecutor(max_workers=10)` (`product_reviews_server.py:635`); bulkhead: `threading.Semaphore(10)`.
- Semaphore ≥ pool size → không bao giờ chặn. Luận điểm trung tâm ADR-005 ("bulkhead ngăn LLM treo làm cạn thread pool, bảo vệ `GetProductReviews` → bảo vệ p95 storefront") **không được hiện thực hoá**.
- **Đã kiểm chứng bằng thí nghiệm deterministic** (`docs/ai/evals/bulkhead_experiment.py`: pool 10 thread, 12 request LLM treo 2s, đo latency của 1 request nhanh 10ms tới sau đó):

| Kịch bản | Latency `GetProductReviews` |
|---|---|
| A. `Semaphore(10)` blocking — code hiện tại | **1909.9 ms** (starved) |
| B. `Semaphore(6)` blocking — fix "hiển nhiên" | **1908.9 ms** (vẫn starved!) |
| C. `Semaphore(6)` **non-blocking** → trả mock ngay | **10.2 ms** (protected) |

- Điểm mấu chốt kịch bản B: với sync gRPC, request **chờ semaphore vẫn giữ nguyên thread của pool** — thu nhỏ semaphore không giải phóng gì. Đây cũng là lý do bulkhead kiểu này *không thể* fix bằng chỉnh số.
- **Fix đúng (đã chứng minh):** `sema.acquire(blocking=False)` — không lấy được thì trả mock summary ngay (fail-fast, khớp triết lý Lớp 4 sẵn có); hoặc tách `AskProductAIAssistant` sang executor/port riêng. Kèm load test in-cluster để có số trước–sau thật.
- Phụ: spec ghi `asyncio.Semaphore` — code sync gRPC dùng `threading.Semaphore` (code đúng, spec sai).

### B2. "Circuit breaker" đọc thẳng cờ sự cố của BTC — rủi ro chạm luật disqualify
- Lớp 5 bật `bypass_primary` khi thấy flag `llmRateLimitError` ON — tức **né sự cố bằng cách đọc chính cơ chế bơm sự cố**, không phải phát hiện lỗi từ hành vi hệ thống.
- `AI_FEATURE.md` §3: "Vi phạm = loại: **tắt/đổi hướng cơ chế sự cố (flagd)**". Nhóm không tắt flag, nhưng "đổi hướng" là vùng xám mà grader có thể đánh trượt.
- **Fix:** circuit breaker dựa trên tín hiệu quan sát được (N lỗi liên tiếp / error-rate cửa sổ trượt). Vừa an toàn luật, vừa generalize cho sự cố thật không đi qua flagd.

### B3. TTFT ~0.4s sai so với chính nguồn nhóm cite
- ADR-004 + spec ghi "TTFT Nova Lite ~0.4s theo Artificial Analysis". Artificial Analysis hiện công bố: **TTFT 1.04s, output 175.7 tok/s** (artificialanalysis.ai/models/nova-lite).
- Hệ quả dây chuyền: 1 call (1.5k in / 200 out) ≈ 1.04 + 200/175.7 ≈ **~2.2s điển hình**, mà luồng tóm tắt gọi **2 vòng converse** (tool round + final) → ~4.4s điển hình, không phải "2.5s" như ADR-001/pitch. Timeout 3.0s/call là ~p50–p75, không phải "phủ đuôi phân phối" như lập luận §2.A.
- Worst-case ladder chưa được tính ở đâu: (3×3.0s primary + backoff) + (2×2.0s fallback) ≈ 13.3s/vòng × 2 vòng ≈ **~26s**; fail-fast (Lớp 4) chỉ check `time_remaining` **một lần ở đầu request**, không check trước vòng converse thứ hai.
- **Fix:** đo thật trên Bedrock (P50/P95 end-to-end), cập nhật số; check deadline trước mỗi vòng converse; cân nhắc budget tổng (deadline-aware ladder) thay vì timeout per-call.

### B4. Luận điểm CFO trung tâm (credit Claude) chưa verify, có khả năng outdated
- ADR-004/pitch khẳng định tuyệt đối: "Claude = AWS Marketplace = **không cấn trừ credit**, tiền mặt thật" — đây là trục chính loại Claude và là câu chuyện "$0 cash vs $525 cash".
- Thực tế nhiều lớp: AWS công bố **AWS Activate credits được dùng cho 3P models trên Bedrock từ 04/2024** (aws.amazon.com/blogs/startups/aws-activate-credits-now-accepted-for-third-party-models-on-amazon-bedrock/); ngược lại một số re:Post 2025–2026 vẫn báo Claude bill dưới Marketplace gây trục trặc credit. **Phụ thuộc loại credit BTC cấp** — nhóm chưa hề verify.
- Chọn Nova vẫn có thể đúng, nhưng nếu bị phản biện đúng chỗ này, cả kịch bản CFO sụp. **Fix:** (1) verify bằng 1 call Claude + Cost Explorer/billing xem credit có apply không, hoặc hỏi BTC loại credit; (2) song song, chuyển trọng tâm lập luận sang cái đã verify chắc: **giá** — Nova Lite rẻ hơn Claude Sonnet ~50× ($0.06/$0.24 vs $3/$15 per 1M), đứng vững bất kể credit.
- Phụ: bảng so sánh dùng **Claude 3.5 Sonnet** — model đã **EOL trên Bedrock 03/2026** (endoflife.date/claude); so sánh nên dùng Sonnet 4.x (cùng $3/$15) để khỏi bị bắt lỗi so với model chết.
- **[CẬP NHẬT 12/07] Nhóm đã chốt không dùng Claude — thread verify credit đóng.** Việc còn lại chỉ là sửa *lập luận trình bày* trong pitch/ADR-004: bảo vệ Nova bằng con số đã verify (rẻ ~50× Sonnet) thay vì claim credit chưa kiểm chứng, để không bị grader bẻ.

### B5. "Đo trước–sau" là mô phỏng random với tỉ lệ lỗi tự đặt
- `test_fallback_retry.py::measure_before_after()`: giả định 22% transient failure, 2% outage, 10% fallback failure — **không có nguồn nào**, rồi in ra "tỷ lệ lỗi trước/sau" như kết quả đo.
- Grading bar: "Có eval, tái tạo được... **Số không tái tạo được coi như chưa chứng minh**". Đây là ví dụ điển hình của số cảm tính đóng gói như measurement.
- Golden dataset chỉ **5 mẫu** — quá mỏng để claim gì về fidelity.
- Eval không chạy được out-of-box (thiếu pin deps: `grpc_health` v.v.), và **không có CI workflow nào** (`.github/` chỉ có PR template) dù AI_FEATURE.md bước 4 yêu cầu "đưa eval vào CI".
- **Fix:** thay mô phỏng bằng đo thật (bật `llmRateLimitError`, chạy locust, đọc Prometheus trước/sau); mở rộng golden dataset ≥ 30–50 mẫu; thêm requirements + GitHub Actions chạy pytest.

## C. MEDIUM

### C1. Versioned cache key không thật sự "versioned"
- `model_ver = "nova-lite-v1"`, `prompt_ver = "p3"` là **hằng số hardcode**, không derive từ `LLM_REVIEWS_MAIN_MODEL` hay hash của system prompt. Đổi model qua env → key không đổi → serve tóm tắt của model cũ tới 7 ngày. Cơ chế mà ADR-001 gọi là "bảo vệ chống tóm tắt lỗi thời" không hoạt động cho đúng ca nó được thiết kế.
- Thêm: khi primary fail, kết quả **Nova Micro được cache dưới key nova-lite-v1** tới 7 ngày — chất lượng thấp hơn bị đóng băng dài hạn.
- **Fix:** `model_ver = model_id thực dùng cho response`, `prompt_ver = hash(system_prompt)[:8]`; TTL ngắn cho kết quả từ fallback.

### C2. Dynamic TTL mâu thuẫn với chính premise của ADR-001
- Premise "review tĩnh" **đã được kiểm chứng độc lập, đúng**: `pb/demo.proto` chỉ có `GetProductReviews`/`GetAverageProductReviewScore` (không rpc ghi), `product_reviews_server.py` không có INSERT/UPDATE/DELETE, dữ liệu seed từ `init.sql`.
- Chính vì premise đúng nên nó phản lại thiết kế: dữ liệu tĩnh → N và variance **không bao giờ thay đổi** → TTL động không phản ứng với gì cả; expiry chỉ đốt lại token cho output giống hệt. Con số "tiết kiệm thêm ~40% chi phí token" không có derivation ở bất kỳ đâu.
- Chi phí phụ: mỗi cache-write query lại DB (`fetch_product_reviews_from_db`) chỉ để tính TTL.
- **Đơn giản hơn và đúng hơn:** TTL phẳng 7d + versioned key (đã có). Xoá công thức động.

### C3. Docs–code drift hai chiều (stale ngay trong tuần viết)
| Doc nói | Code thực tế |
|---|---|
| ADR-005 + pitch (10/07): "chưa có bulkhead/circuit breaker/fallback trong code, Tuần 2 làm" | PR#26 đã merge đủ (commit e0135e7) |
| Spec Lớp 1: "SDK adaptive retry" | `retries={'max_attempts': 0}` — SDK retry bị TẮT (đúng để tránh retry kép, nhưng doc sai) |
| Spec flowchart: fallback off → "trả 500 cho client" | Code trả mock message, không 500 |
| Spec §3.2 không liệt kê `LLM_REVIEWS_FALLBACK_TIMEOUT`, `LLM_REVIEWS_FALLBACK_RETRIES`, `LLM_MOCK_ENABLED` | Code đọc cả ba |
- **Fix:** một pass đồng bộ ADR-005 (đổi trạng thái triển khai), spec §1/§3, trước buổi chấm.

### C4. Gap deploy: Bedrock chưa chạy được trên cluster
- `deploy/values-aio-llm.yaml` vẫn OpenAI `gpt-4o-mini`; `values.yaml` có `AWS_REGION`/`AWS_BEDROCK_MODEL` nhưng **không có IRSA annotation / bằng chứng node role có `bedrock:InvokeModel`**; không set `LLM_REVIEWS_*`.
- Tiêu chí chấm "chạy thật, không mockup — build → ECR → deploy" đang hở. Cần: IRSA cho serviceAccount `product-reviews` (hoặc policy node group) + cập nhật values + smoke test in-cluster.
- **Đã kiểm chứng bằng deploy thật (docker compose, trong review này) — hở ở cả 2 tầng:**
  1. **Image đã publish không chạy với compose hiện tại:** `nghiadaulau/techx-corp:1.0-product-reviews` (hub) crash `Exception: LLM_BASE_URL environment variable must be set` — compose đã bỏ biến này khi migrate Bedrock nhưng image mới chưa build/push. Ai `docker compose up` theo README hôm nay là gãy.
  2. **Source tree hiện tại build ra image không boot:** nhóm regen `demo_pb2.py` bằng protoc mới (gencode **7.35.0**) nhưng `requirements.txt` kéo protobuf runtime **5.29.6** → `VersionError: Runtime version cannot be older than the linked gencode version`. Nghĩa là chưa ai build-chạy thử image từ source sau PR proto-regen. Fix tạm trên nhánh review: pin `protobuf==7.35.1` (cần fix chính thức + CI build-smoke).
  3. Phụ: spec §3.1 khẳng định `LLM_BASE_URL`/`OPENAI_API_KEY`/`LLM_MODEL` "bắt buộc giữ, thiếu là CrashLoopBackOff" — code hiện tại đã bỏ các `must_map_env` đó (chỉ còn `LLM_HOST/PORT`) → spec stale thêm một chỗ.

## D. LOW / ghi nhận

- Mock message tiếng Việt trên storefront tiếng Anh (locust hỏi "Can you summarize..."); nên theo locale.
- Backoff full-jitter đúng dạng AWS blog nhưng base 100ms/factor 1.5 cho 429 là rất ngắn so với cửa sổ throttle Bedrock — retry gần như chắc chắn đập lại throttle. Với chỉ 2 retry, tác hại nhỏ; ghi lại lý do chọn số.
- ADR-003 tự khai sửa `ValkeyCartStore.cs` (vùng INC-2, code CDO) **trước khi có co-sign** — đúng là rủi ro quy trình, cần chốt chữ ký hồi tố sớm.
- Các claim chưa có bằng chứng, nên gắn nhãn "assumption": 100k views/ngày, cache hit 90%, "2.5s → <50ms", semantic search "p95 ~88ms (80+8)", "Nova Lite tool-calling tiếng Việt chưa tin cậy", "Nova Pro tool-calling xuất sắc".

## G. AIOps (`tools/aiops-detector`, `aiops/log_clustering`, specs)

### G1. Điểm cộng — đã verify đúng ✅
- **9 rule bám đúng SLO.md nguyên văn**: `latency-p95-high` threshold 1.0, `error-rate-high` 0.005, `checkout-failure-high` 0.01 — khớp `onboarding/SLO.md` (p95 < 1s, non-5xx ≥ 99.5%, checkout ≥ 99%). Config-driven trong `rules.yaml`, không hardcode; cooldown 600s chống alert spam. Đây là mẫu tốt về số-có-nguồn.
- **Claim "read-only, không ghi Kubernetes" đúng**: grep toàn bộ detector/alerter/sources — không có call ghi K8s; `alerter.py` chỉ webhook Slack/Discord + stdout fallback.
- Detector runtime có hybrid **static threshold OR rolling SMA 3σ**
  (`aiops/detector/detector.py::eval_metric_rule`), không phải EWMA.
- Drain3 `sim_th=0.4, depth=4` = default thư viện (đã verify ở E).

#### G1.1. Reconcile sau B1 — SMA hiện hành, EWMA giữ làm phương án so sánh

- Runtime giữ history riêng theo `rule_id × service`, warm-up 5 mẫu, tính trung
  bình cộng + population σ trên tối đa 30 mẫu, rồi fire dynamic khi mẫu hiện tại
  vượt ±3σ và độ lệch tuyệt đối > `0.001`. Mẫu hiện tại chỉ được append sau khi
  so sánh.
- `evaluate_detector.py` cũng dùng SMA 3σ và cửa sổ 30 mẫu, nhưng guard đang là
  `0.01`; vì vậy chỉ khớp phương pháp, chưa khớp hoàn toàn runtime.
- Sau B1, dùng SMA đang có. Kế hoạch EWMA alpha = 0.2 vẫn được giữ trong
  `03_specs/golden_signals_detection.md` để đối chứng khi có đủ dữ liệu thật,
  không được mô tả như code đang chạy.

### G2. HIGH — rule GenAI nửa chết vì coupling chuỗi log với code vừa đổi
- `genai-assistant-failure` match `"unable to process your response"` — **0 match trong code hiện tại**: PR#26 đã đổi message sang tiếng Việt ("Hiện tại hệ thống không thể tạo tóm tắt..."). Rule chỉ còn sống nhờ `"Caught Exception"` (`product_reviews_server.py:440`) — phrase generic, không đặc trưng GenAI-failure.
- Nhóm *có* ý thức về coupling này (giữ nguyên "Rate limit reached" cho rule `llm-rate-limit-429` — có comment trong code) nhưng sót rule này → hai artifact của chính nhóm drift nhau trong cùng tuần.
- **Fix:** log một marker máy-đọc ổn định (vd `AI_SUMMARY_FALLBACK reason=...`) tách khỏi copy hiển thị cho khách, rule match marker đó. Copy đổi thoải mái, detection không chết.

### G3. HIGH — KPI detector là số synthetic, cùng lỗi phương pháp với B5
- `detector_kpi_metrics.json` (precision 0.69 / recall 0.92 / F1 0.79 / TTD 5 steps cho hybrid) sinh từ `evaluate_detector.py::generate_synthetic_metrics()` — **sine wave + ramp + spike tự chế, ground truth tự đặt nhãn**.
- Giá trị thật của nó: unit test so sánh *tương đối* 3 thuật toán (hybrid > 3σ > static trên dữ liệu này) — hợp lệ. Không hợp lệ: trình như KPI hệ thống ("precision 100%", "MTTD < 1 phút") trước grader.
- ADR-007 claim "MTTD 10–15 phút → < 1 phút" chưa đo; với poll 30s + rate window 5m + độ trễ ingest OpenSearch, "< 1 phút" khó đạt thực tế.
- **Phương pháp chuẩn (khả thi ngay, không cần AWS creds mới):** chaos test trên cluster đang chạy — bật `llmRateLimitError` qua flagd lúc T0, ghi timestamp alert bắn ra, MTTD = T_alert − T0; lặp ≥ 5 lần lấy phân phối. Tương tự cho `db-pool-exhaustion`/`oom-detected` nếu BTC có scenario.

### G4. Trả lời câu hỏi CDO — log cần audit realtime hay poll định kỳ?

**Hiện trạng (đọc từ code):** không realtime, không chờ-alert-mới-lấy. `detector.py:173-178` = vòng `while True` poll mỗi **30s** (`rules.yaml: poll_interval_seconds: 30`); mỗi lần poll đếm `match_phrase` trên OpenSearch trong cửa sổ `now-5m`, query `size: 1` (rất rẻ — chỉ đếm + 1 sample để chẩn đoán). Drain3 chạy batch (CronJob theo ADR-007), không stream.

**Realtime có cần không? Không, với hệ này — và đây là lựa chọn đúng:**
- Detection latency tổng = ingest lag (OTel→OpenSearch) + poll ≤30s + thời gian gom đủ `min_count`. Poll 30s chỉ đóng góp trung bình 15s — **không phải bottleneck**; muốn nhanh hơn phải giảm ingest lag, không phải chuyển sang stream.
- So chuẩn ngành: ElastAlert `run_every` mặc định 1 phút, Grafana alert evaluation mặc định 1 phút, Prometheus rule eval 15s–1m. **Poll 30s đã nhanh hơn default ngành.**
- Realtime streaming (consumer Kafka/subscription): **[Cập nhật 14/07]** CDO đã chuyển sang dùng Amazon MSK (Managed Kafka), giải quyết được gánh nặng "phải tự vận hành", nhưng lại làm tăng áp lực lên ngân sách. Vẫn giữ nguyên kết luận: sai trade-off với BUDGET.md ở quy mô nhỏ.
- Pattern đúng cho phần "audit sâu": **on-alert deep-fetch** — khi rule bắn mới kéo log chi tiết quanh timestamp để RCA (alert đã kèm 1 sample sẵn). Không phân tích liên tục toàn bộ log.

**"Số chuẩn" — ĐÃ ĐO THẬT (docker compose stack local, image build từ source hiện tại, chaos qua flagd file-watch; script: `docs/ai/evals/measure_detection_pipeline.py`):**

| Đại lượng | Kết quả đo | Ghi chú |
|---|---|---|
| Ingest lag (request → query được trên OpenSearch) | **P50 2.1s, max 5.1s** (n=8) | otel-collector batch + OS refresh |
| Sự cố (bật `llmRateLimitError`) → phrase rule 429 thấy được trên OS | **P50 5.1s, max 5.4s** (n=5 vòng chaos) | gồm cả thời gian request đầu tiên dính 429 |
| **MTTD với poll 30s (hiện tại)** | **trung bình ~19.6s, max ~35.4s** | = delay đo được + U(0,30) |
| MTTD với poll 60s | trung bình ~34.6s, max ~65.4s | vẫn dưới target |
| MTTD với poll 120s | trung bình ~64.6s, max ~125.4s | chạm biên target 2 phút |

**Vế chi phí của poll (đo bổ sung 12/07):** 1 query detector trên OpenSearch = **P50 5ms / P95 12ms** (n=30). Suy ra duty-cycle OS theo poll interval: 10s → 30 query/phút ≈ 0.25%; 30s → 10 query/phút ≈ 0.08%; 60s → 0.04%. **Chi phí ~0 ở mọi interval khả dĩ** → bài toán chọn poll gần như chỉ còn một chiều MTTD:

| Poll | MTTD max (đo) | Chi phí query | Nhận xét |
|---|---|---|---|
| 10s | 15.4s | ~0.25% duty | Pareto-tốt nếu muốn biên an toàn tối đa |
| **30s (hiện tại)** | **35.4s** | ~0.08% | **Pass đề với biên 3.4×** — giữ được, không còn là "default", đã có số |
| 60s | 65.4s | ~0.04% | Vẫn pass; chỉ đáng nếu OS quá tải (đã thấy 2 query timeout trong FP run) |
| 120s | 125.4s | ~0.02% | Chạm biên target — loại |

Con số 30s ban đầu là default không căn cứ; sau phép đo nó **tình cờ nằm trong vùng hợp lệ [10s, 60s]**. Đề không thưởng MTTD thấp hơn target, nên 30s giữ nguyên là quyết định có số chống lưng; đổi sang 15s chỉ khi nhóm muốn biên an toàn (max ~20s) — cả hai lựa chọn giờ đều evidence-based, hết cãi nhau bằng quen tay.

**Kết luận theo tiêu chí đề** (target suy từ error budget SLO.md: MTTD ≤ 2 phút ≪ budget 7.2 phút/ngày):
- **Poll 30s PASS thừa**: MTTD max 35.4s ≈ 0.5% error budget ngày. ADR-007 claim "MTTD < 1 phút" **giờ có evidence thật** (trước đó là số chưa chứng minh).
- **60s cũng pass** (max 65s) và cắt nửa tải query — nếu CDO muốn giảm tải OpenSearch, nới lên 60s là an toàn, có số chống lưng. 120s thì chạm biên, không khuyến nghị.
- Ingest lag chỉ ~2s (không phải 1–2 phút như lo ngại) → poll interval là thành phần chi phối MTTD → chọn poll trong [30s, 60s] là vùng hợp lệ theo đề; 30s hiện tại giữ nguyên được.
- **Giới hạn phép đo:** stack local compose, không phải EKS (ingest lag trên cluster thật có thể khác — cần chạy lại script này in-cluster, 10 phút); FP rate đo 15 phút thay vì 24h (xem dưới).

**FP-rate — detector THẬT chạy 15 phút dưới tải locust bình thường (flag sự cố OFF), 4 alert:**

| Alert | Số lần | Phân loại | Vấn đề lộ ra |
|---|---|---|---|
| `latency-p95-high` service=**flagd** (val 4.87s) | 2 | **FP cấu hình rule** | Query PromQL group theo `service_name` toàn namespace, không lọc storefront — flagd nội bộ (không thuộc SLO nào) trigger cảnh báo "vi phạm SLO storefront". Fix: filter `service_name` vào nhóm service thuộc SLO. |
| `llm-rate-limit-429` (62 log khớp) | 2 | **TP defect thật, nhưng SAI NHÃN nguyên nhân** | Flag OFF, không hề có 429 — 62 log là Bedrock fail vì **thiếu AWS creds** (gap C4). Alert vẫn nổ vì code in cứng cụm `"Rate limit reached. Bedrock ThrottlingException."` trong except catch-all **cho mọi loại lỗi Bedrock** (comment trong code: "Rule AIOps llm-rate-limit-429 check log phrase"). |
| `db-pool` / `oom` / `dns` | 0 | ✅ sạch | — |
| (meta) 2 lần query OpenSearch timeout 5s | — | detector tự phục hồi ✓ | Chưa có tín hiệu "detector tự ốm" — nếu OS chậm kéo dài thì mù detection mà không ai biết. |

**Finding mới (HIGH) — G6. Log viết để làm hài lòng rule, gây chẩn đoán sai:** code product-reviews log `"Rate limit reached. Bedrock ThrottlingException"` cho MỌI exception Bedrock (kể cả NoCredentials/AccessDenied) nhằm khớp match_phrase của rule AIOps. Hậu quả đo được: on-call nhận alert "429 rate-limit" trong khi sự cố thật là thiếu credentials — **alert đúng lúc, sai bản chất, dẫn RCA lạc đường**. Fix: log đúng error code thật (`err_code` đã có sẵn trong except), rule match theo marker máy-đọc (`AI_SUMMARY_FALLBACK reason=<code>`) — một marker phục vụ cả rule 429 lẫn rule genai-failure (G2).

### G5. MEDIUM — SMA đang chạy; EWMA chưa có comparative backtest
- Runtime hiện tại không có `alpha`: lớp dynamic là rolling SMA 3σ. EWMA alpha
  = 0.2 là kế hoạch gốc hợp lý nhưng chưa có bằng chứng để thay SMA; lý do trong
  spec ("thấp hơn mức mặc định 0.3") cũng chưa có nguồn cho "0.3 là mặc định".
- **Fix khi đủ dữ liệu:** export 24–48h metric thật từ Prometheus, đồng bộ
  `evaluate_detector.py` với runtime, rồi replay cùng dữ liệu qua SMA window=30
  và EWMA alpha 0.1/0.2/0.3. So sánh precision, recall, FP rate, MTTD và độ ổn
  định theo traffic trước khi chọn phương pháp dynamic; lớp static SLO vẫn giữ.

## G7. Tương quan metrics — trả lời thẳng: hiểu CHƯA đủ để làm căn cứ quyết định

Câu hỏi: "đã thực sự hiểu tất cả metrics, tính chất và độ tương quan giữa chúng chưa?"

**Đã có (đo được trong review này):**
- Quan hệ **cộng tính** của pipeline detection: `MTTD = ingest_lag (2.1s) + fill_min_count + U(0, poll)` — đã tách và đo từng thành phần, đủ làm căn cứ chọn poll.
- Một tương quan lộ ra từ FP run: metric `http_server_request_duration` của **flagd** (nội bộ) lọt vào rule p95 storefront → hiểu sai quan hệ metric↔SLO gây alert nhầm (fix: whitelist service thuộc SLO).
- Chuỗi nhân quả log↔alert: lỗi Bedrock (creds) → log phrase 429 → alert sai bản chất (G6) — tương quan alert với *phrase* chứ không với *nguyên nhân*.

**Chưa có (nói thẳng, không vẽ):**
1. **Ma trận tương quan giữa golden signals** (p95 ↔ error-rate ↔ RPS ↔ saturation, theo service, theo lag) — cần cho: đặt alert không trùng lặp (2 rule cùng bắn cho 1 sự cố = double-page), chọn leading indicator (saturation thường dẫn trước latency).
2. **Alert co-occurrence**: rule nào hay bắn cùng rule nào → dedup/correlation (đề AIOps mở rộng "RCA cross-service" cần chính cái này).
3. **SMA window ↔ EWMA alpha ↔ (FP, recall, MTTD) trade-off curve** trên cùng
   metric thật (G5).

**Cách đóng gap (đo được, tuần 2):** export 24h Prometheus (locust load) → Pearson/Spearman giữa các signal per-service ở các lag 0/30/60s; log co-firing từ chính detector log (đã có alerter history). Script ~100 dòng, chạy trên data sẵn có. Trước khi có bảng này, mọi quyết định đặt thêm rule/ngưỡng mới nên coi là tạm.

## G8. Drain3 sim_th/depth — grid-search trên 19.294 dòng log THẬT của hệ (12/07)

Nghi vấn của trưởng nhóm đúng: `sim_th=0.4, depth=4` là default thư viện, chưa từng kiểm trên log của chính hệ. Grid 4×3 (script scratchpad `drain3_grid.py`, tiêu chí đo được: số template ↓, coverage top-20 ↑, singleton% ↓, stability ↓):

| sim_th | templates | top20 coverage | singleton% | stability |
|---|---|---|---|---|
| **0.3** | **795** | **48.3%** | **56.1%** | **0.64** |
| 0.4 (đang dùng) | 1074 | 47.1% | 59.5% | 0.73 |
| 0.5 | 1222 | 46.4% | 60.6% | 0.76 |
| 0.6 | 1645 | 42.1% | 61.5% | 0.76 |

(depth 4→6: thay đổi <2% ở mọi ô — vô cảm, giữ 4.)

**Kết luận:** trên log hệ này, **sim_th 0.3 trội 0.4 ở cả 4 tiêu chí** — 0.4 over-split thêm ~35% template. Trend đơn điệu: sim_th càng cao càng nát cụm (log 18 service đa ngôn ngữ, token đầu đa dạng). Khuyến nghị kèm: singleton ~56% vẫn cao — bật **masking** của Drain3 (số, UUID, IP, duration) trước khi mining sẽ giảm mạnh; đo lại sau khi bật.
Caveat: corpus 19k dòng/25 phút compose + locust; nên chạy lại grid trên 24h log EKS trước khi chốt vào spec — script để sẵn, tiêu chí đã cố định trước (không fit số).

## I. Audit tối ưu PHƯƠNG PHÁP trong từng spec (không chỉ con số)

Tiêu chí "phương pháp tối ưu" theo đề: (1) giải đúng bài đề nêu, (2) **đơn giản nhất** vẫn đạt ràng buộc (không over-engineer), (3) chi phí biên ~0 theo BUDGET.md, (4) mọi số đi kèm đo được/tái tạo được.

**Dữ kiện nền vừa kiểm chứng từ DB thật:** catalog = **10 sản phẩm**, reviews = **50 dòng (5/sản phẩm)** (`catalog.products`, `reviews.productreviews`). Mọi spec phải được đánh giá trên quy mô dữ liệu này, không phải quy mô tưởng tượng.

| Spec | Phương pháp chọn | Verdict | Lý do |
|---|---|---|---|
| `fallback_retry.md` | Routing Lite→Micro→mock, retry+jitter, 5 lớp resilience | ⚠️ **Hướng đúng, thực thi sai 3/5 lớp** | Ladder rẻ-dần khớp best-effort + credit ✓; cross-region không cần theo đề. Nhưng: L3 bulkhead no-op (B1, đã chứng minh), L5 CB đọc flag sự cố (B2, rủi ro luật), L1 "SDK adaptive retry" không tồn tại trong code. |
| `valkey_caching` | Cache-aside + versioned key + dynamic TTL | ⚠️ **Nửa tối ưu** | Cache-aside + versioned key + reuse valkey-cart ($0) ✓ đúng đề. Dynamic TTL **phản tối ưu**: chỉ có 10 cache key, data tĩnh (C2) — công thức TTL là complexity thuần. Thiếu: phân tích maxmemory chung với cart (INC-2 từng OOM) — cache reviews chung instance với cart là quyết định blast-radius chưa được cân nhắc thành văn. |
| `semantic_search.md` | Titan V2 embeddings + pgvector HNSW (+option RRF) | ❌ **Over-engineered với N=10**<br><br>*(GHI CHÚ MỚI: 14/07)*<br>✅ **BÁC BỎ LỜI PHÊ NÀY.** Quyết định mới nhất áp dụng pgvector để đạt chuẩn Cloud-Native Enterprise. Đã chốt thực thi. | HNSW là index *approximate* cho hàng trăm nghìn–triệu vector; với **10 sản phẩm**, brute-force < 1ms, và tối ưu thật theo đề (intent "tìm sản phẩm NL") là **nhét cả catalog (~vài trăm token) vào prompt Copilot** — zero infra, zero embedding cost, đạt "Done" của đề. Số "embed 80ms + HNSW 8ms" chưa đo và vô nghĩa ở N=10. pgvector chỉ đáng khi BTC bơm directive scale catalog — ghi làm "trigger để nâng cấp", đừng build trước (YAGNI). <br><br>**[ADDENDUM 14/07]** Ban Kiến trúc sư đánh giá giải pháp Dynamic Prompting là Anti-pattern. Đã lật kèo và chính thức chốt `pgvector` trên RDS 16.14. |
| RAG reviews (copilot) | Tool `fetch_product_reviews` đưa thẳng vào context | ✅ **Tối ưu** | 5 reviews/sản phẩm → fetch trực tiếp toàn bộ là grounded-QA đúng nghĩa, không cần vector store. Giữ nguyên, đừng "nâng cấp" thành embedding RAG. |
| `golden_signals_detection.md` | Hiện tại: static-threshold OR rolling SMA 3σ; EWMA giữ làm candidate | ⚠️ **Đã reconcile spec↔code; vẫn hạ verdict (xem K1)** — cần comparative backtest trước khi chọn SMA hay EWMA, và rule error-rate còn gap burn-rate theo giáo trình AIOps course | Xem K1. Backtest SMA↔EWMA (G5), MTTD pipeline đã đo (G4). |
| `log_clustering.md` | Drain3, sim_th 0.4 depth 4 | ✅ **Chuẩn canon** | Drain là phương pháp chuẩn log template mining; params = default thư viện; phù hợp quy mô. |
| `anomaly_remediation.md` | Dry-run → blast radius 1 pod/h → verify 120s → CB 3 fails → escalate | ✅ **Tối ưu theo cấu trúc** (đề trích nguyên văn pipeline này ở RULES.md §4 AIOps core) | Các số 120s/3 fails/1 pod/h là assumption hợp lý nhưng cần label + eval khi bật auto-remediation (tuần sau). Tuần 1 detect-only là đúng trình tự. |
| Copilot spec (3 intent + confirmation gate) | Tool-calling agent + gate xác nhận trước ghi cart | ✅ **Đề bắt buộc đúng dạng này** | **[CẬP NHẬT 15/07]** Đã thực thi xong trên codebase (MANDATE-06, xem ADR-011). |

**Tóm tắt trả lời "phương pháp đã tối ưu nhất chưa":** 4/8 tối ưu, 2/8 đúng hướng nhưng thực thi/chi tiết sai, 2 phản-tối ưu rõ (dynamic TTL, semantic search pgvector cho N=10). Điểm hệ thống: các spec có xu hướng **chọn phương pháp theo template ngành** (HNSW, dynamic TTL, adaptive retry) thay vì theo **quy mô dữ liệu thật của hệ (10 sản phẩm, 50 reviews)** — đây chính là dạng "cảm tính có vỏ kỹ thuật" mà đề trừ điểm.

**[ADDENDUM 14/07 - PHỤ LỤC LẬT KÈO KẾT LUẬN CHẤM CHÉO]:**
Tuy nhiên, sau khi tranh luận dựa trên **AWS Well-Architected Framework**, Ban Kiến trúc sư đã kết luận:
Việc nhét Data vào Prompt (Dynamic Prompting) để tiết kiệm cấu hình là một **Anti-pattern** không có khả năng scale. Việc chọn `pgvector` không phải "cảm tính có vỏ kỹ thuật", mà là tầm nhìn xa chuẩn Enterprise-grade. Do đó, điểm trừ về `pgvector` bị HỦY BỎ. Hệ thống sẽ chính thức chạy `pgvector` trên Amazon RDS.

## J. Vòng nghi ngờ 2 (12/07) — soi phần chưa audit + tự soi claim của chính review

### J1. CRITICAL — chuỗi ADR-003 (volatile-lru + bỏ TTL cart) tự vô hiệu và trỏ thẳng vào checkout SLO

Ba mảnh đã verify từ code/config thật, ghép lại thành chuỗi hỏng:

1. **`--maxmemory-policy volatile-lru` được thêm mà KHÔNG set `--maxmemory`** (`techx-corp-chart/values.yaml:947-950`, diff với baseline xác nhận team thêm). Maxmemory mặc định = 0 = không giới hạn → **policy không bao giờ chạy** — volatile-lru hiện là trang trí.
2. **TTL cart bị gỡ** (`ValkeyCartStore.cs:174,199`, comment "prevent cart eviction under volatile-lru") — chẩn đoán sai 2 lớp: (a) TTL expiry và LRU eviction là 2 cơ chế khác nhau; (b) eviction không thể xảy ra vì maxmemory chưa set. Kết quả thực: **gỡ đúng cơ chế chặn rò rỉ bộ nhớ duy nhất đang hoạt động** (baseline TTL 60 phút).
3. **Container limit 20Mi** (values.yaml, baseline giữ nguyên) + cart tích vô hạn (TTL đã gỡ) + load-generator sinh user mới liên tục → RSS vượt 20Mi → **kubelet OOMKill valkey-cart → mất TOÀN BỘ giỏ hàng đang sống** (không persistence) → đánh thẳng **checkout ≥ 99% — luồng được đề dặn bảo vệ số 1**, đúng vết INC-2.
4. Cron GC 30-ngày idle (`valkey-cleanup.py`) không cứu được: 20Mi đầy trước mốc 30 ngày rất xa. Reviews cache chung instance là nhóm key volatile duy nhất — nếu sau này ai set maxmemory, toàn bộ eviction dồn vào cache reviews trước, rồi cart write vẫn lỗi OOM khi hết key volatile.

**Fix đúng (chọn 1, kèm số):** (a) khôi phục TTL cart (60m baseline, hoặc con số khác **có căn cứ đo** từ session length thật); hoặc (b) set `--maxmemory` < cgroup limit + nâng limit lên mức tính từ số cart đồng thời đo được + **tách instance** cache reviews khỏi cart. Trước khi chọn: soak test đo time-to-OOM (`INFO memory` theo giờ). **Việc này phải báo CDO ngay — code và SLO của họ.**

### J2. HIGH — `shopping-copilot: enabled: true` trong values.yaml nhưng không có source, không có image
- `techx-corp-platform/src/` không có thư mục copilot; `nghiadaulau/techx-corp:1.0-shopping-copilot` không tồn tại trên hub (đã probe manifest).
- Helm deploy hiện tại → Deployment ImagePullBackOff vĩnh viễn: xấu T2, sinh noise event/alert. Fix 1 dòng: `enabled: false` tới khi có image; bật lại trong PR chứa code copilot. **[CẬP NHẬT 15/07]** Source code cho `shopping-copilot` hiện đã được hoàn thành (kèm theo Guardrails và Action Gating). Việc build và push image sẽ được giải quyết sau khi nhánh `feat/TF1-57-59-68` merge.

### J3. Tự soi claim của chính review này (không miễn trừ ai)
| Claim của review | Kết quả tự kiểm | Hành động |
|---|---|---|
| "OTel collector có Loki exporter chính chủ" (doc CDO) | **Sai chi tiết**: `lokiexporter` đã deprecated (contrib #33916). Sự thật *tốt hơn*: Loki ≥3.0 nhận **OTLP native** — dùng `otlphttp` exporter sẵn có, không cần component riêng (grafana.com/docs/loki/latest/send-data/otel) | Đã sửa doc CDO |
| "MTTD target ≤ 2 phút" | Là **judgment của review** suy từ error budget, không phải số đề cho. Sensitivity: target 2 phút → poll ≤60s pass; target 1 phút → poll ≤30s pass (max 35.4s); target 30s → poll 10s pass (max 15.4s); target <10s → không đạt bằng chỉnh poll, phải giảm sàn ingest 5.4s (collector batch/refresh) — bài toán khác | Ghi sensitivity thay vì 1 số cứng; nhóm chốt target với mentor |
| MTTD đo bằng rule `min_count=1` | Đúng cho rule 429/OOM; **chưa đo** rule `min_count=3` (db-pool, dns) — thêm thời gian gom đủ 3 dòng, phụ thuộc tần suất log lỗi lúc sự cố (λ cao → thêm vài giây; λ thấp → có thể không bao giờ đủ trong 5m) | Gap ghi nhận; đo khi chaos db-pool trên EKS |
| Drain3 grid | Số tuyệt đối (singleton 56%) bị nhiễu bởi timestamp/id nhúng trong dòng — **kết luận so sánh 0.3 > 0.4 vẫn đứng** vì cùng độ nhiễu ở mọi ô | Bật masking rồi đo lại như đã ghi ở G8 |

## K. Vòng nghi ngờ 3 (12/07) — soi qua lens giáo trình (skill `aiops` + `xbrain-cloud-curriculum`)

Điểm khác vòng trước: đây là đối chiếu với **tài liệu của chính course** — tức là thước mà grader sẽ dùng, không phải "chuẩn ngành chung".

### K1. HIGH — rule error-rate vi phạm non-negotiable của chính giáo trình; review này trước đó cũng chấm sai
- Giáo trình AIOps course (skill `aiops`, mục Non-negotiables): *"**Never alert on raw error rate.** Use multi-window multi-burn-rate against an error budget. Single-window alerting either pages on blips or sleeps through a slow burn."*
- `error-rate-high` và `checkout-failure-high` của nhóm = đúng anti-pattern đó: 1 cửa sổ 5m, ngưỡng raw 0.5%/1%. Hệ quả 2 chiều: (a) page vì blip 5 phút dù budget 24h còn nguyên (FP run đã thấy mặt này ở rule latency); (b) **ngủ quên trước slow burn** — error 0.4% kéo dài cả ngày đốt 80% budget mà không rule nào kêu.
- **Tự đính chính:** mục I trước đó tôi chấm golden signals "✅ Đúng và đủ" — sai theo thước của course. Đã hạ verdict.
- **Fix theo giáo trình + đề (error budget đã có sẵn trong SLO.md):** multi-window multi-burn-rate — page khi burn ≥14.4× ở cả 5m và 1h; ticket khi ≥6× ở 30m và 6h. Prometheus có đủ dữ liệu; thêm 2 rule PromQL, không cần hạ tầng mới.

### K2. MEDIUM — "recall dominates": min_count=3 là rủi ro bỏ sót sự cố
- Giáo trình chấm: *"Missing an incident is a zero on every dimension — recall dominates."*
- Rule `db-pool-exhaustion`, `dns-resolution-error` đòi **min_count=3 trong 5m** — sự cố log thưa (pool nghẽn chớm, DNS chập chờn) có thể mãi 2 dòng/5m → miss hoàn toàn = zero theo thước chấm, tệ hơn nhiều so với vài FP.
- Fix: min_count=1 + cửa sổ dài hơn cho 2 rule này, hoặc chuyển sang burn-rate trên metric tương ứng; FP dư ra xử lý bằng dedup (K3).

### K3. MEDIUM — thiếu hẳn tầng Correlate theo pipeline giáo trình
- Pipeline chuẩn course: Detect → **Correlate (fingerprint dedup → time-window grouping → topology)** → Diagnose → Act. Nhóm hiện chỉ có cooldown per-rule+service — 1 sự cố thật (vd Bedrock chết) bắn đồng thời `llm-rate-limit-429` + `genai-assistant-failure` + `genai-latency-high` = 3 page cho 1 chuyện. G7 đã ghi gap tương quan; giờ có anchor: đây là **stage bắt buộc trong giáo trình**, không phải nice-to-have.
- Fix rẻ: fingerprint (rule_id + service + 5m bucket) → gộp alert cùng bucket thành 1 message. ~30 dòng trong alerter.

### K4. MEDIUM — thiếu leading indicator cho lớp sự cố OOM (nối thẳng J1)
- Giáo trình: saturation là **cause**, phải theo dõi để hành động sớm (không phải làm SLI). Nhóm chỉ có rule log `OOMKilled` — tức phát hiện **sau khi pod đã chết**.
- J1 (valkey-cart 20Mi, cart tích vô hạn) chính là ca sẽ chết kiểu này. Rule Prometheus `container_memory_working_set_bytes / limit > 0.8 trong 10m` bắt được **trước khi kill** — biến J1 từ sự cố thành cảnh báo sớm. Dữ liệu có sẵn.
- Bonus khớp giáo trình RCA: "rank by earliest drift, not loudest signal" — memory drift của valkey-cart sẽ là earliest-drift signal chuẩn cho bài RCA tuần 2.

### K5. Đối chiếu evidence-pack format (xbrain) — cấu trúc docs đang lệch khung chấm
- `CAPSTONE_EVIDENCE_PACK_FORMAT.md` (course): Nhóm AI phải nộp **6 doc chuẩn tên**: `01_requirements.md`, `02_solution_design.md`, `03_ai_engine_spec.md`, `04_eval_report.md`, `05_adrs.md`, `06_contracts/*`; doc chiếm **~40% điểm** checkpoint chính; "doc viết live trong repo, git history = evidence".
- Hiện trạng `docs/ai/`: có ADR-log (≈05 ✓), contracts/ (≈06 ✓), specs rời rạc (≈03 nhưng phân mảnh), **thiếu hẳn 01_requirements, 02_solution_design, 04_eval_report** (eval hiện chỉ có script, chưa có report methodology + kết quả).
- *Caveat trung thực:* format này viết cho capstone W11–12; Phase 3 có RULES.md riêng — **hỏi mentor 1 câu** trước khi làm. Nếu áp dụng: 3 doc thiếu là việc rẻ (số đo đã có sẵn từ review này để đổ vào 04_eval_report).
- Điểm cộng đối chiếu PITCH_GUIDE: pitch.md của nhóm có đúng 3 kịch bản PM/CFO/SRE mà guide mô tả ✓ — chỉ cần thay lập luận CFO (hết credit-claim, sang giá 50×).

### K6. Đối chiếu ngược: những verdict cũ của review ĐỨNG VỮNG qua lens giáo trình
- Remediation spec khớp nguyên văn vòng khép kín của giáo trình (dry-run → blast-radius → act → **verify** → rollback → CB) ✓.
- Drain masking-first: baseline của chính course (`log-clusterer.py` mask `<NUM>/<IP>/<UUID>` trước khi so) — củng cố khuyến nghị G8 ✓.
- Rolling SMA 3σ phù hợp làm baseline hiện tại; EWMA vẫn là bậc nâng cấp hợp lý
  khi data non-stationary nếu comparative backtest chứng minh tốt hơn ✓.
- "Metrics + logs kết hợp" — nhóm làm đúng hướng (3 rule metric + 5 rule log) ✓.

## L. Fix ĐÃ ÁP DỤNG trên nhánh này (12/07) + bằng chứng runtime

Các fix nằm trong working tree nhánh `review/week1-baseline-verify` (chưa commit theo yêu cầu). **Đã verify bằng build + chạy thật trên compose, 4 request thử:**

| Fix | File | Bằng chứng runtime (docker logs) |
|---|---|---|
| A1 — thêm flag `llmReviewsFallbackEnabled` (default on) | 2× `demo.flagd.json` | `"Fallback routing triggered → amazon.nova-micro-v1:0"` ×5 (trước fix: **0**) |
| B2 — circuit breaker theo lỗi quan sát được (3 lỗi liên tiếp → open 30s; bỏ hẳn đọc `llmRateLimitError`) | `product_reviews_server.py` | `"Circuit Breaker OPENED for 30.0s after 3 consecutive primary failures"` + 2 lần bypass |
| B1 — bulkhead non-blocking, sema 6 < pool 10, saturate → mock ngay | `product_reviews_server.py` | Cơ chế chứng minh bằng `evals/bulkhead_experiment.py` (10ms vs 1909ms); không saturate trong test tuần tự (đúng kỳ vọng) |
| G6 — marker `AI_SUMMARY_FALLBACK stage=<..> reason=<..>` thay nhãn 429 giả | `product_reviews_server.py` | `"AI_SUMMARY_FALLBACK stage=bedrock reason=Exception"` ×5, không còn fake ThrottlingException |
| **Mới (phát hiện khi test fix): lỗi ngoài dự kiến thoát ladder** — `NoCredentialsError` (BotoCoreError) không nằm trong except tuple → fallback/CB không chạy với cả lớp lỗi này | `product_reviews_server.py` | Sau khi mở rộng `except (ClientError, BotoCoreError)`: ladder chạy đủ với NoCredentials (chính là 5 dòng fallback ở trên) |
| C1 — `model_ver` đọc từ env model thật, `prompt_ver` = md5(SYSTEM_PROMPT)[:8]; dedupe prompt thành hằng | `product_reviews_server.py` | Compile OK; key tự đổi khi đổi model/prompt |
| C2 — bỏ dynamic TTL → TTL phẳng 7d (+ bỏ query DB thừa mỗi cache-write) | `product_reviews_server.py` | Compile OK |
| G2/G6 — rule `genai-assistant-failure` match marker; K2 — min_count 3→1, window 5→10m cho db-pool/dns | `rules.yaml` | YAML parse OK |
| K1/K4 — 2 rule DRAFT: `error-budget-burn-fast` (multi-window 14.4×), `memory-saturation-high` (>85% limit) | `rules.yaml` | **DRAFT — phải verify PromQL trên Prometheus sống trước khi tin** (ghi rõ trong comment) |
| J2 — `shopping-copilot: enabled: false` | `values.yaml` | Hết ImagePullBackOff khi helm deploy |

**Polish còn nợ:** marker `reason=` ở outer catch đang là `Exception` generic — nên truyền err_code từ wrapper ra (5 phút, tuần 2). **Chưa fix (cần quyết định nhóm/CDO):** J1 (valkey TTL/maxmemory — code CDO), protobuf pin chính thức (đụng PR proto), T3 evals thay mô phỏng, K5 cấu trúc doc.

## E. Con số ĐÃ verify đúng ✅

| Claim | Kết quả |
|---|---|
| Giá Nova Lite $0.06/$0.24, Micro $0.035/$0.14, Pro $0.80/$3.20 /1M | ✅ khớp aws.amazon.com/bedrock/pricing |
| Math $0.000138/request (1500 in + 200 out) & $9.66→$0.97/tuần | ✅ tính lại đúng |
| Mẫu số 10:1 từ locustfile | ✅ `@task(10) browse_product` vs `@task(1) ask_product_ai_assistant` |
| Claude 3 Sonnet/Haiku legacy, bị chặn truy cập | ✅ (retired 11/2024; 3.5 Sonnet EOL Bedrock 03/2026) |
| Titan Embeddings V2 ~$0.02/1M tokens, 1024 dim | ✅ |
| Claude Sonnet $3/$15 /1M | ✅ (áp dụng cả Sonnet 4.x) |
| OpenSearch Serverless min ~$350/tháng | ✅ (~2 OCU dev) |
| Drain3 `sim_th=0.4, depth=4` | ✅ là default của thư viện (hợp lý, nhưng nên ghi "default") |
| Cách tách "credit vs tiền mặt", tự đính chính $30/tuần ở ADR-003 | ✅ điểm cộng về trung thực |

## F. Ưu tiên hành động (thứ tự)

1. **A1** — thêm flag `llmReviewsFallbackEnabled` vào flagd (5 phút, cứu cả feature).
2. **G2** — sửa rule `genai-assistant-failure` sang log-marker ổn định (10 phút, cứu detection GenAI).
3. **B4** — verify credit Claude với BTC/billing; reframe lập luận sang giá nếu không chắc.
4. **B2** — đổi circuit breaker sang error-rate-based (tránh vùng xám disqualify).
5. **B1** — non-blocking semaphore → mock (KHÔNG phải thu nhỏ semaphore — xem thí nghiệm) + load test in-cluster.
6. **B3/B5/G3** — đo thật thay mô phỏng: chaos test flagd đo MTTD + error-rate trước/sau; chạy `evals/measure_bedrock_latency.py` khi có AWS creds; mở rộng golden dataset; CI.
7. **G5** — backtest SMA window=30 và EWMA alpha 0.1/0.2/0.3 trên cùng metric
   Prometheus thật; **G4** — đo ingest lag + FP rate 24h để chốt poll interval
   với CDO.
8. **C1–C4** — sửa versioned key, bỏ dynamic TTL, đồng bộ docs, đóng gap deploy IRSA.

### Script tái tạo đi kèm review này
- `docs/ai/evals/bulkhead_experiment.py` — thí nghiệm B1 (chạy: `python3 bulkhead_experiment.py`, không cần deps).
- `docs/ai/evals/measure_bedrock_latency.py` — đo P50/P95 Nova Lite thật cho B3 (cần AWS creds hợp lệ; creds shell hiện tại invalid).

### Nguồn ngoài đã dùng
- https://aws.amazon.com/bedrock/pricing/
- https://artificialanalysis.ai/models/nova-lite
- https://aws.amazon.com/blogs/startups/aws-activate-credits-now-accepted-for-third-party-models-on-amazon-bedrock/
- https://endoflife.date/claude · https://platform.claude.com/docs/en/about-claude/model-deprecations
- https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/
