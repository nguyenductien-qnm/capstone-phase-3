# ADR-019: Trần thông lượng và cơ chế xuống mềm (Mandate-19)

- **Status:** Accepted
- **Date:** 2026-07-21 (cập nhật 22/07: trần user-facing qua NLB, HPA checkout-path)
- **Owner (ký):** lken1514,nguyenthanhdat2707
- **Deciders:** Task Force CDO
- **Evidence:** `docs/mandate-19/loadtest/README.md` (số đo), `docs/mandate-19/loadtest/EVIDENCE.md`
  (checklist ảnh), `flood-test-tuned-system.md` + `shed-verification-clusterip-vs-podip.md` (YC4 trên hệ đã tuning)

---

## Context

Cụm develop `ecommerce-develop-dev-eks` (account 458), gồm 3 node t3.large primary và 1 node ops,
namespace `techx-develop`, cấu hình prod-like (7 HPA min2/max6 target 70%, PDB maxUnavailable:1,
RDS t4g.micro). Đo trên develop trước để không đụng prod; cấu hình chốt xong mang sang prod nguyên
vẹn vì dùng chung chart và image.

Trước Mandate-19, chưa ai biết trần thông lượng thật của storefront. Mandate đòi bốn thứ: biết
trần, nâng trần bằng hiệu suất chứ không thêm node, tìm và xử nút thắt, và xuống mềm khi vượt trần.
Ràng buộc cốt lõi xuyên suốt là số node app không được đổi giữa các phép đo — mọi cải thiện phải
đến từ việc dùng tốt hơn tài nguyên có sẵn.

---

## Trần đo được (YC1 + YC3)

**Phương pháp:** Locust step-load (5/10/20/40u, rồi 20/40/80/120u) bắn catalog flow vào
`frontend-proxy:80` từ trong cụm, generator ép về node ops để không tranh tài nguyên với app. SLO
chính thức là storefront p95 < 1s (`onboarding/SLO.md`), checkout success ≥99%, browse/cart non-5xx
≥99.5%. Ngưỡng 200ms chỉ là cảnh báo nội bộ, dùng để lộ nút thắt sớm — ở ngưỡng 1s thì mọi bậc đo
đều đạt, khó thấy throttle. Số chốt lấy từ Prometheus (CPU, throttle) và CSV của Locust; run đầu
tiên luôn bị bỏ vì dính warm-up (HPA scale trễ cộng SSR JIT), lấy số từ run thứ hai trở đi.

**Nút thắt của luồng Web UI là `frontend` (Next.js SSR)** — service bão hòa sớm nhất trên đường đi
của storefront.

> ⚠️ **Phạm vi, để không overclaim:** frontend là trần của luồng Web UI đi qua SSR, không phải trần
> của toàn bộ kiến trúc. Luồng khác có nút thắt khác: public API hay mobile gọi thẳng backend qua
> Ingress thì nút thắt có thể nằm ở payment, product-catalog hoặc RDS connection pool; còn checkout
> ở tải cao thì nghẽn ở backend chain (đã đo, xem dưới). Bài này đo storefront web — đúng đối tượng
> của #19 — nên kết luận "frontend là trần" đúng cho phạm vi đó.

Bằng chứng nút thắt (Phase 3, ghim frontend 1 pod, limit 500m): bậc gãy là 80 user, p95 226ms và
503 bắt đầu xuất hiện. Điều đáng chú ý là tại điểm gãy, pod chỉ dùng 83m trên limit 500m (17%) với
throttle 5.2% — CPU còn dư hơn 80%. Nghĩa là thứ bão hòa không phải CPU mà là event loop của
Next.js SSR: đơn process, single-thread, trộn cả I/O lẫn render React trên một luồng, nên request
xếp hàng khi tới nhanh hơn tốc độ xử lý; 503 là lúc hàng đợi đầy. product-catalog throttle 0% suốt
bài, xác nhận backend không phải nút thắt ở luồng này.

**Con số trần:**

- **Per-pod (frontend, catalog flow):** run chứng minh **capacity ≥56.2 rps/pod** với p95<1s nhưng
  chưa chạm trần thật. Team dùng **safe planning capacity = 20 rps/pod** theo ngưỡng cảnh báo 200ms
  để có headroom; đây là số thực nghiệm của team, không phải công thức Kubernetes.
- **User-facing (mixed traffic qua NLB, đo từ EC2 c6i.2xlarge ngoài cụm, 21/07):** **98 rps @
  200u** — checkout p99 970ms vẫn dưới 1s, fail 0%; gãy ở 280u (frontend throttle 9.4%, payment
  8.8%). Node giữ nguyên suốt bài. Đây là con số dùng khi trả lời "hệ chịu được bao nhiêu".

Hai con số không mâu thuẫn: số per-pod là trần của riêng luồng browse đo trong cụm, còn 98 rps là
trần mixed có checkout đi qua NLB — checkout chain gãy sớm hơn browse nên trần mixed thấp hơn là
tất nhiên. Chi tiết đối chiếu và bài học warm-up nằm ở README mục PHASE 6.5.

Trần cũ trước khi tuning (limit 200m): ở 40u frontend throttle 9.3%, p99 341ms, p100 810ms, đã kịch
6 replica HPA max mà vẫn throttle, node giữ 3 primary.

---

## Nâng trần bằng gì (YC2 — Decision)

**Đòn bẩy 1 — nới CPU limit frontend 200m → 500m,** giữ requests 100m để HPA target 70% không đổi:

| Chỉ số @40u | Trần CŨ (200m) | Trần MỚI (500m) | Cải thiện |
|---|---|---|---|
| frontend CPU throttle | 9.3% | **2.1%** | ↓ 4.4× |
| p99 latency | 341ms | **122ms** | ↓ 2.8× |
| p100 (max) latency | 810ms | **260ms** | ↓ 3.1× |
| rps (throughput) | 19.8 | 19.9 | giữ (đã tuyến tính) |
| **Node app** | **3** | **3** | **KHÔNG thêm node ✅** |

**Đòn bẩy 2 — scale-out pod, vì bản chất trần là concurrency.** Nút thắt của frontend không phải
CPU nên nới limit không nâng được rps/pod; nó chỉ hạ tail-latency do throttle. Muốn nâng trần rps
thật sự thì phải thêm pod — mỗi pod là một event loop độc lập. Vì vậy HPA maxReplicas của frontend
nâng từ 6 lên 10 (trần EC2 gãy ở 280u đúng lúc frontend đã kịch max 6). Hai vấn đề, hai đòn bẩy:
giảm p99 thì nới limit, nâng trần thì thêm pod.

**Đòn bẩy 3 — gỡ nút thắt checkout chain.** Checkout gãy sớm hơn browse nhiều (trần ~27 rps so với
~40+ của catalog) vì backend chain bị bóp: email throttle 95.7% ở limit 100m, payment 34.2%,
currency 29.1%, và email/quote/shipping/payment kẹt 1 replica không có HPA. Xử lý bằng hai việc,
đều override riêng develop trong `values-application.yaml`:

- Nới limit theo số đo throttle (email 400m, payment 300m, currency 250m, cart/checkout 350m) và
  right-size requests theo CPU thật sau-shed (email 100m, payment 80m, cart/checkout 60m,
  product-catalog 40m).
- Thêm HPA min2/max4 cho email, quote, shipping, payment. Kết quả: email throttle từ 43% còn 2.1%,
  quote từ 58% còn 8%, shipping về 0.4%. Run chứng minh checkout đạt **capacity ≥76.3 rps** với
  SLO<1s, so với passing point trước tuning ~26.9 rps (measured ratio ≈2.8×). Chưa gọi 76.3 rps là
  trần tuyệt đối vì chưa có bậc kế tiếp làm checkout vi phạm SLO.

Ràng buộc node giữ được ở mọi phép đo (verify `kubectl get nodes` đầu và cuối mỗi bài). Requests
tổng không phình — chỗ tăng (email/payment vốn under-request) bù bằng chỗ giảm (cart/checkout/
catalog vốn over-request).

---

## Load-shedding (YC4 — Decision)

**Cơ chế:** filter `local_ratelimit` per-route trên Envoy `frontend-proxy` (Envoy 1.34) — điểm vào
duy nhất của storefront.

**Thiết kế theo ưu tiên flow:** route `/api/checkout` và `/api/cart` tách lên trên catch-all và
không gắn browse rate-limit — hai route này không bị shed bằng 429, nhưng vẫn có thể lỗi/vi phạm
SLO do downstream overload. Browse `/api/products` chịu
token bucket 80 rps; catch-all `/` (chặn flood homepage) bucket 100 rps. Lưu ý bucket là **per-pod**:
tổng ngưỡng hiệu dụng bằng bucket nhân số pod proxy.

**Hành vi khi vượt trần** (demo Locust flood ~631 rps, 120s):

| Route | reqs | 429 shed | % shed | Kết luận |
|---|---|---|---|---|
| browse `/api/products` | 64448 | 45378 | **70.4%** | shed phần vượt bucket |
| cart (checkout-path) | 10803 | **0** | **0%** | không bị shed 429; theo dõi 5xx/SLO riêng |

Browse bị shed 70% bằng 429 chủ động. `0% 429` của checkout-path chỉ chứng minh route được loại khỏi
browse rate limit, không tự động chứng minh đạt SLO hoặc không có 5xx. Chạy lại trên hệ đã tuning
với cờ flood thật của mentor (`loadGeneratorFloodHomepage`, 22/07):
checkout SLI giữ 100%, node giữ 4, frontend tự scale hấp thụ flood — chi tiết trong
`flood-test-tuned-system.md`. Một bài học phương pháp: vì bucket per-pod, probe qua ClusterIP không
thấy 429 dù shed vẫn chạy đúng; muốn verify phải bắn thẳng pod IP hoặc giữ rps tức thời vượt
bucket × số pod — ghi trong `shed-verification-clusterip-vs-podip.md`.

**Triển khai:** số bucket tune trên develop bằng ConfigMap mount tạm, chốt xong đưa vào
`techx-corp-platform/src/frontend-proxy/envoy.tmpl.yaml` trong repo. File này bake vào image lúc
build (entrypoint chỉ envsubst biến env lúc start), nên merge là CI build image mới, ký Cosign,
bump tag — dev và prod dùng chung một image immutable, diff bằng 0. ConfigMap tạm xóa sau khi image
mới chạy.

---

## Consequences

- **+ Performance Efficiency:** trần được đo và ghi rõ ràng (98 rps user-facing qua NLB; ~56 rps/pod
  frontend theo SLO), tail-latency giảm 3 lần trên cùng số node.
- **+ Cost Optimization:** không thêm node, nhiều request hơn trên mỗi node nghĩa là rẻ hơn trên mỗi
  request. Requests tổng không phình nhờ right-size hai chiều.
- **+ Reliability:** shed loại cart/checkout khỏi 429 của browse; SLO và 5xx của downstream vẫn phải
  giám sát riêng. Email/payment hết cảnh 1 replica đơn điểm.
- **− Browse bị hy sinh khi vượt trần** (trả 429) — chấp nhận có chủ đích, vì browse đứng sau
  checkout về giá trị business.
- **Nút thắt sẽ dịch chuyển:** sau đợt tuning này, trần frontend do concurrency SSR quyết định. Nếu
  vòng sau cần trần cao hơn thì hướng đi là Node cluster workers hoặc cache SSG/ISR để giảm việc
  SSR, không phải tiếp tục nới limit.

---

## Alternatives đã cân nhắc

- **`adaptive_concurrency` thay cho rate-limit tĩnh:** tự dò concurrency tối ưu theo latency, nhưng
  con số khó giải thích trong ADR; rate-limit tĩnh minh bạch hơn cho demo. Để lần lặp sau.
- **Node cluster / PM2 nhiều worker mỗi pod** thay vì scale-out pod: chạy được, nhưng trên t3.large
  với requests 100m thì scale-out pod sạch hơn và để HPA lo được.
- **Bơm thêm node hoặc tăng requests:** loại ngay từ đầu vì trái ràng buộc #19 — nâng bằng hiệu
  suất, không mua thêm.

---

## Ghi nhận trung thực (độ tin cậy — ràng buộc #19)

- **product-reviews CrashLoopBackOff** (protobuf gencode 7.35.0 lệch runtime 5.29.6) làm
  `/api/product-reviews` trả 500. Lỗi build image có sẵn từ trước, không do loadtest, cần fix riêng.
  Reviews không nằm trên đường nghẽn browse/cart/checkout nên không ảnh hưởng kết luận trần.
- **Số 20 rps/pod chỉ đúng cho frontend** (đặc thù concurrency Next.js SSR). Service Go/.NET có mô
  hình khác, muốn biết trần per-pod của chúng phải đo riêng.
- **Số đo in-cluster có giới hạn của nó:** generator chạy trên node t3.large dùng chung với
  observability, không đủ lực ở tải cao và không đi qua NLB. Vì vậy con số công bố ra ngoài luôn
  lấy từ phép đo EC2 ngoài cụm (PHASE 6.5); số in-cluster chỉ dùng so sánh nội bộ before/after.
