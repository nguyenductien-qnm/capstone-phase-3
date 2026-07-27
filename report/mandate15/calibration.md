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
