# Truy nguyên báo động giả `llm-rate-limit-429`

**Ngày đo:** 27/07/2026 · **Ticket:** TF1-111 (MANDATE-15) · **Cụm:** `ecommerce-dev-eks`, ns `techx-tf1`

## 1. Nó lộ ra thế nào

Ca `case_healthy_load` của MANDATE-15 hỏi: *"hệ thống BẬN có bị nhầm là HỎNG không?"*
Cách bơm: đẩy locust từ 22 lên 100 user qua REST API `POST /swarm`.

Tải đo được: **24.69 → 94.80 req/s = 3.84×**. Trong lúc đó hệ thống hoàn toàn khoẻ —
p95 `cart` 4.9ms, bộ nhớ 103/512 MiB, không service nào lỗi.

Kết quả:

```
[case-healthy-load-001] expect_fire=False -> FIRED (lead_time=319.7s) MISMATCH
VERDICT (healthy_load): FAIL — false alarm(s): ['case-healthy-load-001']
```

Rule đã bắn: `llm-rate-limit-429`, `severity: critical`, lúc 23:42:21.

## 2. Dòng log đã kích hoạt

```
[frontend-proxy] [2026-07-27T16:42:03.358Z] "GET /api/product-reviews/6E92ZMYYFZ HTTP/1.1" 200 - via_upstream - "-" 0 534 429 429 "10.0.91.23" "python-requests/2.34.2"
```

- **Mã trạng thái HTTP là `200`.** Không có 429 nào cả.
- Hai số `429 429` là trường `%DURATION%` / `%RESPONSE_DURATION%` của Envoy — **429 mili-giây**.
- `python-requests/2.34.2` chính là locust của bài đo.

Chuỗi nhân quả thật: tải 3.84× → độ trễ tăng → một request tình cờ mất **đúng 429ms** →
token `429` xuất hiện trong access log → rule bắn CRITICAL.

Nói cách khác, chính cụm từ này biến *"hệ thống bận"* thành *"hệ thống hỏng"* — đúng cái
lỗi mà MANDATE-15 sinh ra để tìm.

## 3. Nguyên nhân gốc

`match_phrases` của rule chứa cụm `"429"` trần. `message_field` (`body`) là kiểu `text`
**đã analyze**, nên `match_phrase` khớp **token** `429` ở bất kỳ vị trí nào trong dòng
log — không riêng gì ở chỗ mã trạng thái.

## 4. Mức độ — đếm trên toàn bộ index

Index `otel-logs-*`, dữ liệu cũ nhất `2026-07-21T00:00:00Z`, tổng **7,941,641** dòng log.

| Cụm từ trong rule | Số dòng khớp |
|---|---|
| `"Rate limit reached"` | 0 |
| `"rate_limit_exceeded"` | 0 |
| `"429"` | **49** |

Phân loại đủ 49 dòng:

| Nguồn | Số dòng | `429` thực chất là gì |
|---|---|---|
| Access log Envoy (`frontend-proxy`) | 24 | `%DURATION%` — 429 mili-giây, status `200` |
| Kafka consumer (`shipping`) | 25 | `topic=domain.checkout.orders, partition=0, offset=429` |
| **429 thật** | **0** | — |

**Precision của cụm `"429"` = 0.00** trên toàn bộ dữ liệu mà rule này từng thấy.

Đối chiếu thêm, các biến thể đặc hiệu khác cũng 0 khớp trong 7 ngày:
`"Too Many Requests"` · `"HTTP 429"` · `"status_code=429"`.

## 5. Hai cụm đặc hiệu KHÔNG hỏng

`"Rate limit reached"` và `"rate_limit_exceeded"` có 0 khớp, nhưng lý do khác hẳn: cờ flagd
`llmRateLimitError` **chưa bật lần nào** trong 7 ngày đó. Chaos test tuần 1 đã đo chúng bắt
được sự cố thật với **P50 5.1s, max 5.4s (n=5 vòng)** —
xem `docs/ai/review-week1-verification.md:183`.

Chúng là bộ phát hiện đúng. Cụm `"429"` mới là thứ thừa và sai.

## 6. Cách vá và kiểm chứng

Thay `"429"` bằng `'HTTP/1.1" 429'` — neo vào vị trí mã trạng thái trong access log Envoy.
Analyzer tách cụm này thành `[http, 1.1, 429]` **liên tiếp**, nên chỉ khớp khi status thật
sự là 429.

Kiểm chứng bằng `_analyze` trên `otel-logs-2026-07-27` (chỉ đọc, không ghi gì vào cụm):

| Cụm từ | status=429 | status 200 + 429ms | `offset=429` | app log "Rate limit reached" |
|---|---|---|---|---|
| `"429"` (cũ) | ✅ | ❌ khớp oan | ❌ khớp oan | ✅ |
| `'HTTP/1.1" 429'` (mới) | ✅ | không khớp | không khớp | không khớp |
| `"Rate limit reached"` | không khớp | không khớp | không khớp | ✅ |

Hai cụm bù nhau: một cụm bắt 429 ở tầng proxy, một cụm bắt ở tầng ứng dụng.

Thêm test hồi quy `test_no_log_rule_matches_a_bare_number` chặn mọi cụm chỉ gồm chữ số
trong rule log.

## 7. Điều phải nói thẳng về phương pháp

Tôi đổi rule **sau khi** thấy ca FAIL, và sau khi đổi thì FAIL biến mất. Đó đúng là hình
dạng của việc "chỉnh bài test cho khớp kỳ vọng", nên phải nói rõ vì sao trường hợp này khác:

**Lý do biện minh không phụ thuộc vào kết quả ca healthy-load.** Precision 0.00 trên 49 lần
khớp trong 7 ngày, kèm giải thích cơ chế, vẫn đứng vững kể cả nếu ca đó đã PASS.

Và kết quả FAIL gốc **không bị xoá**: nó nằm nguyên trong
`report/mandate15/run-case_healthy_load-eks-restapi.log` và trong báo cáo MANDATE-15, kèm
nguyên nhân. Con số cuối cùng của mandate phải là một lần **chạy lại thật** sau khi rule vá
được deploy, không phải suy luận offline.

## 8. Hạn chế còn lại

`'HTTP/1.1" 429'` phụ thuộc định dạng access log của Envoy. Nếu đội đổi `access_log_format`
thì cụm này chết âm thầm — không có gì báo. Đây là đánh đổi có ý thức: tuyến chính vẫn là
cụm đặc hiệu ở tầng ứng dụng; cụm này chỉ là lưới thứ hai.

Cùng loại rủi ro với 8 rule metric mù đã ghi nhận ở MANDATE-22: một rule không khớp gì
trông y hệt một rule đang yên bình.

## 9. Cách tái tạo

```sh
POD=$(kubectl -n techx-tf1 get pods -l app=aiops-detector -o jsonpath='{.items[0].metadata.name}')

# Dem theo tung cum tu tren toan bo index
kubectl -n techx-tf1 exec -i "$POD" -- python3 - <<'EOF'
import json, urllib.request
def q(b):
    r = urllib.request.Request("http://opensearch:9200/otel-logs-*/_search",
        data=json.dumps(b).encode(), headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(r, timeout=60))
for p in ["Rate limit reached", "rate_limit_exceeded", "429"]:
    d = q({"size": 0, "track_total_hits": True, "query": {"match_phrase": {"body": p}}})
    print(f"{p!r:24s} -> {d['hits']['total']['value']}")
EOF
```
