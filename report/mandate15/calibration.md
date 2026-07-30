# Hiệu chỉnh độ lớn "sự cố 2" của ca masking

**Ngày đo:** 2026-07-27 · **Cụm:** `ecommerce-dev-eks` / `techx-tf1`
**Script tái tạo:** `report/mandate15/calibrate.py`

## Vì sao phải hiệu chỉnh

Ca masking chỉ có nghĩa khi **sự cố 2 chỉ bắt được bằng tầng 3-sigma**. Trên rule
`service-error-rate-high` (ngưỡng tĩnh `0.10`, cổng SLO `dynamic_min_fraction: 0.50`
→ sàn `0.05`), nghĩa là tỉ lệ lỗi phải rơi vào **(0.05, 0.10)**:

- Vượt `0.10` → tầng **tĩnh** kêu, bài test PASS vì lý do sai → **âm thầm vô nghĩa**
- Dưới `0.05` → cổng SLO chặn, không tầng nào bắt được → FAIL kể cả khi đã có winsorize

Hai kiểu hỏng **không cân nhau**: cái trên im lặng làm hỏng bằng chứng, cái dưới lộ ra
ngay. Nên chọn thiên về phía thấp.

## Điều kiện lúc đo

| | |
|---|---|
| Baseline tỉ lệ lỗi `checkout` | **0.0000 suốt 121/121 mẫu trong 1 giờ** (không phải gần 0 — bằng 0) |
| `checkout` phục vụ | `PlaceOrder` 0.2292 req/s · `Health/Check` 0.6000 req/s |
| `cart` | 2 replica (HPA min=2, max=6) |

## Số đo — gián đoạn `cart` 20 giây

| t (giây) | tỉ lệ lỗi `checkout` | |
|---|---|---|
| −5 | 0.0000 | trước khi bơm |
| 0 | 0.0000 | `cart` → 0 replica |
| 20 | 0.0182 | `cart` → 2 (khôi phục) |
| 44–65 | 0.0182 | |
| 85–127 | 0.0678 | **trong dải** |
| 148–189 | 0.0727 | **trong dải** |
| 210–252 | **0.0909** | **đỉnh, trong dải** |
| 273–314 | 0.0486 → 0.0391 | rơi khỏi dải |
| 335+ | 0.0000 | về baseline |

**Đỉnh 0.0909 tại t=210s. Nằm trong dải (0.05, 0.10) suốt ~167 giây (t=85→252).**
Không mẫu nào vượt ngưỡng tĩnh 0.10.

Độ trễ ~85 giây trước khi lên tới dải là do `rate(...[5m])`: cửa sổ trượt cần thời gian
để phần lỗi chiếm đủ tỉ trọng.

## Chọn: 15 giây

Ngoại suy tuyến tính từ điểm đo: `20s → 0.0909`, nên `15s → ~0.068`.

Vị trí đó cân nhất: **cao hơn cổng 36%**, **thấp hơn ngưỡng tĩnh 32%**. Dùng thẳng 20s
thì đỉnh 0.0909 chỉ cách ngưỡng tĩnh 9% — quá sát, một nhịp traffic đổi là tràn qua và
làm hỏng bằng chứng mà không ai biết.

> Đây là **ngoại suy từ một điểm đo**, không phải số đo trực tiếp. Nếu lần chạy thật cho
> tỉ lệ nằm ngoài dải thì phải ghi đúng như thế và hiệu chỉnh lại — không được sửa ngưỡng
> rule cho khớp kỳ vọng.

## Ghi chú vận hành

Sau khi khôi phục, HPA đẩy `cart` lên **5 replica** để tiêu hoá lượng dồn, rồi tự thu về
`minReplicas=2`. Phải đợi nó ổn định và tỉ lệ lỗi về 0 trước khi chạy ca masking, nếu
không baseline đã bẩn từ đầu.

---

# Vòng 2 — 15s trên `checkout` KHÔNG dùng được, và vì sao

Lần chạy đầu theo hiệu chỉnh ở trên cho verdict **PASS**, nhưng đào ra thì **PASS vì lý do sai**:

| Thời điểm | tỉ lệ lỗi `checkout` | |
|---|---|---|
| 15:37:43 | 0.0678 | trong dải |
| **15:38:13** | **0.1132** | ← alert bắn đúng lúc này |
| 15:39:13 | **0.1458** | đỉnh |

Sự cố 2 **vượt ngưỡng tĩnh 0.10**, nên **tầng tĩnh kêu chứ không phải 3-sigma**. Bài test
không hề kiểm masking. Lấy ảnh đó làm evidence là làm bằng chứng giả.

**Sai ở đâu:** ngoại suy tuyến tính từ **một** điểm đo. `20s → 0.0909` nên tưởng
`15s → 0.068`. Thực tế `15s → 0.1458` — **cao hơn**, tức **không đơn điệu**.

Nguyên nhân: gián đoạn *thật* bị chi phối bởi thời gian pod tắt (grace period) và khởi
động lại, khoảng ±15s, chứ không tỉ lệ với thời lượng khai báo. Ở mức 15–20s thì nhiễu
đó **lớn ngang chính tín hiệu**. **Thời lượng là cần điều khiển sai.**

## Cần điều khiển đúng: tần suất gọi

Đo phổ gọi của `checkout` (CLIENT spans):

| Phụ thuộc | req/s | lần gọi mỗi đơn hàng |
|---|---|---|
| `CurrencyService/Convert` | 0.6696 | ~2.7 |
| `ProductCatalogService/GetProduct` | 0.4216 | ~1.7 |
| `CartService/GetCart` | 0.2480 | ~1.0 |

**Mọi phụ thuộc đồng bộ của `checkout` đều nằm trên MỌI request** → giết cái nào tỉ lệ
cũng vọt lên 1.0. `checkout` **không có nấc trung gian nào**.

`frontend` thì khác: cùng sự cố `cart` chết, nó chỉ đạt **0.2796** vì cart chỉ nằm trên
một phần luồng của nó (`AddItemAndGetCart` + `GetCart` = 1.15 trong tổng 10.93 req/s
SERVER span).

## Ứng viên bị loại: `recommendation`

Giết `recommendation` **360 giây** → tỉ lệ lỗi `frontend` = **0.0000 suốt 19/19 mẫu**.

`frontend` **chịu được** `recommendation` chết — mất widget gợi ý chứ không lỗi. Đó là
kỹ thuật tốt của ứng dụng, nhưng làm nó vô dụng làm điểm bơm.

## Chốt: `frontend` + gián đoạn `cart` 60 giây

Suy từ số đo: `frontend` full-outage = 0.2796; hệ số khuếch đại 1.36 (từ dữ liệu
`checkout`: 20s cho 0.0909 trong khi `20/300 × 1.0 = 0.0667`).

| Mục tiêu | Thời lượng cần | Với nhiễu ±15s → dải tỉ lệ | |
|---|---|---|---|
| 0.060 | 47s | 0.041 – 0.079 | có thể tràn xuống dưới cổng |
| **0.075** | **59s** | **0.056 – 0.094** | **trọn vẹn trong dải** |
| 0.090 | 71s | 0.071 – 0.109 | có thể tràn qua ngưỡng tĩnh |

Chọn **60s**. Vì `frontend` thấp hơn `checkout` 3.6 lần nên cần gián đoạn dài gấp ~4 lần,
và chính điều đó biến nhiễu ±15s từ **thứ chi phối kết quả** thành **sai số nhỏ** — đúng
thứ đã phá vòng 1.
