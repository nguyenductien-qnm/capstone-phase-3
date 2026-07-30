# Quét tham số MANDATE-23 — số ĐO THẬT

> Sinh bởi `param_sweep_m23.py` (gọi `amazon.titan-embed-text-v2:0` thật, tính cosine trong Python).
> Bản trước của file này là **mô phỏng** — đã thay bằng đo thật ngày 27/07/2026.

## 1. Ngưỡng L2 semantic cache — `SEMANTIC_CACHE_MIN_SIM`

**Luật chọn (viết trước khi chạy):** lấy ngưỡng **thấp nhất** có `false-hit = 0`; hoà thì lấy recall cao nhất. Thấp nhất chứ không phải recall đẹp nhất — MANDATE-23 cấm "trả cũ sai".

Bộ ca: 4 cặp *cùng ý* (phải hit) + 5 cặp *gần giống mà khác nghĩa* (phải miss: phủ định, đổi mốc giá, đổi sản phẩm, đổi thuộc tính).

| Nhóm | Similarity |
|---|---|
| Cặp **cùng ý** — thấp nhất | **0.6587** |
| Cặp **khác nghĩa** — cao nhất | **0.9191** |

| Ngưỡng | Recall | False-hit |
|---|---|---|
| 0.70 – 0.74 | 75% | **20%** |
| 0.75 – 0.85 | 50% | **20%** |
| 0.86 – 0.88 | 25% | **20%** |
| 0.89 – 0.91 | 0% | **20%** |
| 0.92 – 0.99 | **0%** | 0% |

**Kết luận: hai nhóm chồng lấn hoàn toàn.** Có cặp *khác nghĩa* giống nhau hơn cả cặp *cùng ý*, nên **không tồn tại ngưỡng nào** vừa bắt paraphrase vừa không trả sai. Mọi ngưỡng bắt được paraphrase đều kéo theo false-hit 20%.

**Quyết định: TẮT L2 semantic** (`SEMANTIC_CACHE_ENABLED=false`; ngưỡng để 0.92 làm chốt chặn nếu ai bật lại). Nộp với **L1 exact** — memo ghi rõ *"1 bề mặt có cache đo được là sàn đạt"*. Thà điểm sàn còn hơn phục vụ câu trả lời sai.

Điều kiện bật lại L2: có embedding tiếng Việt tách được hai nhóm này, **hoặc** thêm rule guard chặn khi hai câu khác nhau ở token phủ định / mốc giá / tên sản phẩm.

## 2. Các tham số còn lại

| Tham số | Giá trị đang dùng | Căn cứ |
|---|---|---|
| `COPILOT_CACHE_TTL` | 3600s | TTL chỉ là GC backstop — chống-outdate đã do fingerprint lo (mục 3). Chưa quét |
| `MAX_SESSION_MESSAGES` | 20 | giữ baseline; chưa quét — cần đo token vào/lượt trước khi chỉnh |
| `SEMANTIC_CACHE_MIN_SIM` | 0.92 (L2 tắt) | mục 1, đo thật |

> Trung thực: chỉ ngưỡng similarity được quét đo trong vòng này. Hai tham số còn lại vẫn là baseline, chưa có bảng quét — không tuyên bố "đã tối ưu".

## 3. Fingerprint nguồn — vì sao TTL không còn là tuyến phòng thủ chính

Key cache copilot ghim fingerprint của **cả catalog lẫn review**:

```
copilot:answer:{user_id}:{model_ver}:{prompt_ver}:{data_fp}:{mem_fp}:{question_fp}
data_fp = md5(catalog_fp + reviews_global_fp)
```

Đo 27/07 — **trước** khi thêm `reviews_global_fp`: sửa một review rồi hỏi lại vẫn `hit_exact` và trả điểm cũ 3.8 (**trả cũ sai**). **Sau** khi thêm: cùng thao tác cho `miss`. Đây là bằng chứng trực tiếp cho ràng buộc *"nguồn đã đổi mà cache vẫn trả kết quả cũ = fail"*.
