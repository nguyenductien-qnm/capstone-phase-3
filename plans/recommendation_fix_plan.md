# Implementation Plan: Fix Recommendation Service Vector Table Query (Gap STT 7)

## Context
Gap số 7 trong hệ thống AI (AIE - TF1) xác định lỗi trong `recommendation_server.py`. Service này đang truy vấn thông tin embedding từ bảng `catalog.products` với cột `id` và `embedding`. Tuy nhiên, thực tế dữ liệu embedding được sinh ra (bởi `embed_products.py`) lưu tại bảng `catalog.product_embeddings_v2` với 2 cột:
- `product_id` (VARCHAR)
- `embedding` (vector(1024))

Sự bất đồng bộ này khiến SQL exception ném ra lỗi `column "embedding" does not exist`, buộc service phải dùng cơ chế fallback (chọn ngẫu nhiên sản phẩm) và vô tình "giấu" lỗi. 

## Objective
Thay đổi mã nguồn `recommendation_server.py` để query đúng vào bảng `catalog.product_embeddings_v2` và tham chiếu tới cột `product_id`. Đảm bảo hệ thống hoạt động tốt ở môi trường local trước khi tiến hành lên EKS. Không thay đổi cơ sở hạ tầng hoặc push code trong quá trình chuẩn bị plan này.

## Phase 1: Modify SQL Queries trong `recommendation_server.py`

Thay đổi trong hàm `_get_ai_recommendations` (File: `techx-corp-platform/src/recommendation/recommendation_server.py`):

1. **Sửa SQL Query 1: Lấy average embedding cho danh sách input_product_ids**
   - **Cũ:**
     ```sql
     SELECT AVG(embedding) as avg_embedding
     FROM catalog.products
     WHERE id IN ({placeholders}) AND embedding IS NOT NULL
     ```
   - **Mới:**
     ```sql
     SELECT AVG(embedding) as avg_embedding
     FROM catalog.product_embeddings_v2
     WHERE product_id IN ({placeholders}) AND embedding IS NOT NULL
     ```

2. **Sửa SQL Query 2: Tìm top N sản phẩm liên quan nhất (Cosine Distance)**
   - **Cũ:**
     ```sql
     SELECT id
     FROM catalog.products
     WHERE id != ALL(%s) AND embedding IS NOT NULL
     ORDER BY embedding <=> %s::vector
     LIMIT %s
     ```
   - **Mới:**
     ```sql
     SELECT product_id as id
     FROM catalog.product_embeddings_v2
     WHERE product_id != ALL(%s) AND embedding IS NOT NULL
     ORDER BY embedding <=> %s::vector
     LIMIT %s
     ```

## Phase 2: Local Testing
Sau khi thay đổi mã, cần thực hiện restart/rebuild service `recommendation` ở local thông qua Docker Compose và kiểm tra hệ thống (chúng ta sẽ không dùng CLI làm ảnh hưởng hạ tầng EKS theo đúng yêu cầu).
- **Log verification:** Gọi service hoặc thao tác UI để xem span attributes `app.recommendation.type` trên Jaeger. Kỳ vọng giá trị là `ai-embedding` (chứng tỏ AI query thành công, không bị rơi vào exception / `random-fallback`).
- **Data verification:** Kiểm tra output của Recommendation xem có hợp lý thay vì random hay không. 

## Phase 3: Finalizing Artifacts & Gap Status
- Xoá label ⚠️ **OPEN GAP** tại STT 7 trong `docs/ai/gap_analysis.md`.
- Ghi nhận ✅ **ĐÃ NGHIỆM THU** cho Vector Table Query với bằng chứng thay đổi thành công.

---
Vui lòng phê duyệt Kế hoạch này để tôi bắt đầu thực hiện Phase 1!
