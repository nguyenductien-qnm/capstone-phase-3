# Shed (YC4) Verification — ClusterIP vs Pod IP

**Ngày:** 2026-07-22 · **Cluster:** develop (458) · **Namespace:** techx-develop
**Mục đích:** xác minh dứt điểm load-shedding (Envoy local_ratelimit) còn hoạt động không, sau khi probe qua ClusterIP ban đầu không thấy 429.

---

## TL;DR

**Shed HOẠT ĐỘNG bình thường — KHÔNG lỗi, KHÔNG regression so với demo 07:44 UTC (README).**
Lý do các test đầu "không thấy 429": **bucket rate-limit là PER-POD**, và probe qua ClusterIP phân tải + curl-fork không đạt rps tức thời đủ cạn bucket từng pod. Bắn thẳng 1 pod IP → shed kích ngay.

---

## Cấu hình shed (đã verify trong pod)

- Envoy entrypoint: `envsubst < envoy.tmpl.yaml > envoy.yaml && envoy -c envoy.yaml` (render tmpl→yaml lúc start).
- `envoy.yaml` (render) có **7× local_ratelimit**: `rl_browse` (`/api/products`, bucket 80/s), `rl_home` (`/`, bucket 100/s), filter_enabled/enforced 100%.
- Route checkout-path (`/api/cart`, `/api/checkout`) KHÔNG có ratelimit → ưu tiên tuyệt đối.
- Envoy listen **port 8080** (Service map 80→8080). Envoy admin (9901) **TẮT** → không có metric shed trong Prometheus.
- 2 pod frontend-proxy → **mỗi pod 1 bucket riêng** (tổng cho phép ≈ 2× bucket).

---

## Kết quả đo (2 cách bắn, cùng lúc flood load-generator)

### ❌ Qua ClusterIP `frontend-proxy:80` → KHÔNG thấy 429

| Route | 200 | 429 | 5xx | Ghi chú |
|---|---|---|---|---|
| GET / (2000 req song song) | 2000 | **0** | 0 | không shed |
| /api/products (1500 req) | 1487 | **0** | 13 | không shed |
| /api/cart (400 req) | 400 | 0 | 0 | đúng — không limit |

→ Kể cả 2000 req + flood 200u đồng thời, 429=0.

### ✅ Bắn thẳng 1 pod IP `10.60.x.x:8080` → shed KÍCH rõ

| Route | 200 | **429 (shed)** | % shed |
|---|---|---|---|
| GET / (rl_home=100/s), 800 req song song | 471 | **329** | **41%** |
| /api/products (rl_browse=80/s), 500 req | 233 | **265** | **53%** |

→ Dồn hết tải vào 1 bucket → cạn ngay → 429 đúng cơ chế.

---

## Giải thích nghịch lý (root cause)

1. **Bucket per-pod, không phải per-service.** 2 pod proxy = 2 bucket độc lập (100/s mỗi cái cho rl_home).
2. **ClusterIP (kube-proxy) rải connection đều 2 pod** → mỗi pod nhận ~1/2 tải.
3. **`curl` fork 2000 process KHÔNG đồng thời tuyệt đối** — chúng trải ra trong ~10-15s → **rps tức thời tại mỗi pod < 100** → bucket refill kịp (fill_interval 1s) → không cạn → không shed.
4. **Bắn thẳng 1 pod IP** → toàn bộ dồn 1 bucket, tức thời > 100 rps → cạn → 429.

**→ Muốn shed kích qua ClusterIP/NLB cần rps tức thời > (bucket × số pod) = >200/s liên tục.** Test bằng curl-fork không tạo được; cần công cụ bắn rps ổn định cao (vd `hey -q`, `wrk`, hoặc locust nhiều worker) hoặc bắn thẳng pod IP để verify nhanh.

---

## Kết luận YC4

| Tiêu chí YC4 | Trạng thái |
|---|---|
| Browse bị shed (429) khi vượt bucket | ✅ ĐẠT (pod IP: / 41%, /api/products 53%) |
| Checkout-path KHÔNG bị shed | ✅ ĐẠT (/api/cart 200 hết) |
| Checkout SLI giữ khi flood | ✅ 100% |
| Hệ không sập, node không nở | ✅ node 4 suốt |

**Shed không lỗi.** Điều duy nhất cần lưu ý là **phương pháp test**: bucket per-pod nên phải bắn đủ rps tức thời, hoặc thẳng pod IP.

## Khuyến nghị

1. Nếu cần bằng chứng shed qua đường thật (NLB/ClusterIP): dùng công cụ bắn rps ổn định cao (`hey -z 30s -q 300`, hoặc locust headless nhiều user liên tục) thay vì curl-fork.
2. Cân nhắc **bật Envoy admin** (hoặc scrape stats) để quan sát counter `rl_browse.rate_limited` / `rl_home.rate_limited` — hiện admin tắt nên không có observability cho shed.
3. (Tùy) chuyển bucket sang **global** thay vì per-pod nếu muốn hành vi shed nhất quán không phụ thuộc số replica proxy.

---

## Trạng thái sau test (đã revert)
- cờ flagd flood → **off**, load-generator → **10u**, flagd restart, node **4**.
