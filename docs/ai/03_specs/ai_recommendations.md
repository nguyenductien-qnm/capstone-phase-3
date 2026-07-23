# Spec: AI-Powered Product Recommendations (Hạng mục Đua Top)

> **Trạng thái:** Implemented (Code đã được merge và tài liệu hóa)
> **Trụ:** Performance Efficiency / Cost Optimization  
> **Ngày:** 2026-07-09  
> **Tác giả:** Định Nguyễn, Vinh Bui  
> **ADR liên quan:** ADR-009  
> **Cập nhật:** Tính năng đã được deploy thành công dùng `pgvector` và tính trung bình embedding cho `list_recommendations`.

---

## 1. Bối cảnh & Vấn đề

### 1.1 Thực trạng hiện tại

Service `recommendation` (`src/recommendation/recommendation_server.py:107`) trả về **kết quả hoàn toàn ngẫu nhiên**:

```python
# Line 107: recommendation_server.py
indices = random.sample(range(num_products), num_return)
prod_list = [filtered_products[i] for i in indices]
```

**Hệ quả:**
- **CTR (Click-Through Rate) thấp:** Sản phẩm gợi ý không liên quan → khách không click.
- **Cross-sell = 0:** Không có logic gợi ý sản phẩm bổ sung (mua camera → gợi ý thẻ nhớ).
- **Không tận dụng dữ liệu AI:** Review summaries, product descriptions đều có sẵn nhưng không được dùng.

### 1.2 Yêu cầu từ RULES.md

> Line 66: **Mở rộng (đua top):** [...] recommendation bằng tín hiệu AI [...]

### 1.3 Yêu cầu từ AI_FEATURE.md

> Intent #5: **Gợi ý kèm / cross-sell** (recommendation + catalog)

---

## 2. Phương án đã đánh giá

### 2.1 Option A: Embedding-based Item-to-Item Similarity ⭐ **CHỌN**

**Kiến trúc:**
```
User đang xem Product A
         │
         ▼
┌────────────────────────────┐
│  Recommendation Service    │
│  (Python)                  │
│                            │
│  1. Lấy embedding của A    │──── SELECT embedding FROM products WHERE id = A
│     từ DB (đã pre-compute) │◄─── vector[1024]
│                            │
│  2. Tìm K products gần A   │──── pgvector: ORDER BY embedding <=> A_vec LIMIT 5
│     nhất theo cosine sim   │◄─── [B, C, D, E, F]
│                            │
│  3. Loại A khỏi kết quả    │
│     và trả về              │
└────────────────────────────┘
```

**Ưu điểm:**
- **Zero user history needed** → Không bị cold-start problem
- **Sub-50ms latency** → Chỉ 1 SQL query trên pgvector
- **Zero extra cost** → Reuse embeddings đã tính sẵn cho Semantic Search
- **Semantic understanding** → "Noise-cancelling headphones" sẽ gợi ý "wireless earbuds" thay vì random

**Nhược điểm:**
- Chỉ gợi ý sản phẩm **tương tự**, không phải sản phẩm **bổ sung** (complementary)

### 2.2 Option B: LLM Re-ranking (Amazon Nova Lite)

**Kiến trúc:**
1. Dùng embedding similarity tìm top 20 candidates
2. Gọi Nova Lite với prompt: "Given user is viewing [Product A], which 5 of these products would be best to recommend and why?"
3. Trả về 5 sản phẩm được LLM chọn + explanation text

**Chi phí:** ~$0.001/request (Nova Lite)

**Kết luận:** ✅ Hay nhưng đắt hơn và tăng latency. Triển khai ở Phase 2 nếu còn thời gian.

### 2.3 Option C: Amazon Personalize

**Chi phí:** 
- Training: $0.05/giờ compute
- Inference: $0.20/1000 real-time recommendations
- **Yêu cầu:** Tối thiểu 1000 interaction events (clicks, purchases) → **Không có dữ liệu thật.**

**Kết luận:** ❌ Loại bỏ — quá heavy cho capstone, không có clickstream data.

### 2.4 Option D: Collaborative Filtering + Review Sentiment

**Kiến trúc:** Xây ma trận user-product từ reviews → matrix factorization → gợi ý.

**Kết luận:** ❌ Loại bỏ — demo app chỉ có reviews tĩnh, không có user login/profile thật.

### 2.5 Option E: Content-based Filtering (TF-IDF/BM25)

**Kiến trúc:** Tính TF-IDF vectors từ product descriptions → cosine similarity.

**Kết luận:** ❌ Kém hơn embedding-based vì TF-IDF không hiểu ngữ nghĩa (semantic).

---

## 3. Case Study

### 3.1 Amazon "Customers who bought this also bought"
- **Architecture:** Collaborative filtering (item-to-item) + deep learning re-ranking.
- **Scale:** Hàng tỷ interactions/ngày.
- **Takeaway cho capstone:** Item-to-item similarity là pattern cốt lõi. Amazon bắt đầu từ đây trước khi mở rộng sang personalization.
- **Tham khảo:** [Greg Linden, Brent Smith, Jeremy York. "Amazon.com Recommendations: Item-to-Item Collaborative Filtering" IEEE Internet Computing, 2003](https://ieeexplore.ieee.org/document/1167344)

### 3.2 Shopify Product Recommendations
- **Architecture:** Embedding-based similarity cho cửa hàng nhỏ (< 1000 products). Personalize cho enterprise.
- **Kết quả:** +15% average order value (AOV) trên cửa hàng có recommendations.
- **Takeaway:** Embedding similarity là giải pháp tối ưu cho catalog nhỏ.

### 3.3 Zalando "Complete the Look"
- **Architecture:** Multi-modal embeddings (text + image) → gợi ý outfit hoàn chỉnh.
- **Kết quả:** +20% cross-sell revenue.
- **Takeaway:** LLM re-ranking có thể thêm "fashion rules" mà pure embedding không có.

### 3.4 Mercari Similar Items
- **Architecture:** Sentence-BERT embeddings → FAISS ANN search → top-K similar listings.
- **Kết quả:** Giảm 25% thời gian tìm kiếm trung bình, tăng 12% transaction rate.
- **Tham khảo:** [Mercari Engineering](https://engineering.mercari.com/)

---

## 4. Kế hoạch triển khai

### Phase 1: Modify Recommendation Service (Day 1-2)

```python
# recommendation_server.py - MODIFIED
import psycopg2
from pgvector.psycopg2 import register_vector

class RecommendationService(demo_pb2_grpc.RecommendationServiceServicer):
    def ListRecommendations(self, request, context):
        span = trace.get_current_span()
        
        # Kiểm tra feature flag
        if check_feature_flag("aiRecommendationsEnabled"):
            span.set_attribute("app.recommendation.type", "ai-embedding")
            prod_list = self._get_ai_recommendations(request.product_ids)
        else:
            span.set_attribute("app.recommendation.type", "random-fallback")
            prod_list = self._get_random_recommendations(request.product_ids)
        
        response = demo_pb2.ListRecommendationsResponse()
        response.product_ids.extend(prod_list)
        rec_svc_metrics["app_recommendations_counter"].add(
            len(prod_list), 
            {'recommendation.type': 'ai' if check_feature_flag("aiRecommendationsEnabled") else 'random'}
        )
        return response
    
    def _get_ai_recommendations(self, input_product_ids, max_results=5):
        """Find similar products using embedding cosine similarity."""
        with tracer.start_as_current_span("get_ai_recommendations") as span:
            db_connection_str = os.environ.get('DB_CONNECTION_STRING')
            if not db_connection_str:
                return self._get_random_recommendations(input_product_ids)
                
            with psycopg2.connect(db_connection_str) as connection:
                register_vector(connection)
                with connection.cursor() as cur:
                    # Lấy embedding trung bình của các input products
                    placeholders = ','.join(['%s'] * len(input_product_ids))
                    cur.execute(f"""
                        SELECT AVG(embedding) as avg_embedding
                        FROM catalog.products
                        WHERE id IN ({placeholders}) AND embedding IS NOT NULL
                    """, input_product_ids)
                    
                    avg_embedding = cur.fetchone()[0]
                    if avg_embedding is None:
                        return self._get_random_recommendations(input_product_ids)
                    
                    # Cần chuyển sang dạng chuỗi hoặc list để pgvector parse đúng
                    embedding_str = str(list(avg_embedding))
                    
                    # Tìm top-K similar products (loại trừ input products)
                    cur.execute(\"\"\"
                        SELECT id
                        FROM catalog.products
                        WHERE id != ALL(%s) AND embedding IS NOT NULL
                        ORDER BY embedding <=> %s::vector
                        LIMIT %s
                    \"\"\", (input_product_ids, embedding_str, max_results))
                    
                    results = [row[0] for row in cur.fetchall()]
                    span.set_attribute("app.ai_recommendations.count", len(results))
                    
                    if not results:
                        return self._get_random_recommendations(input_product_ids)
                        
                    return results
```

### Phase 2: Feature Flag (Day 2)
```json
// src/flagd/demo.flagd.json
{
  "aiRecommendationsEnabled": {
    "state": "ENABLED",
    "variants": { "on": true, "off": false },
    "defaultVariant": "on"
  }
}
```

### Phase 3: LLM Re-ranking — Optional (Day 3-4, nếu còn thời gian)
Sau khi embedding similarity trả về 20 candidates, gọi Nova Lite để chọn 5 tốt nhất và giải thích:

```python
prompt = f"""
User is viewing: {current_product_name} ({current_product_description})
Here are 20 candidate products: {candidates_json}

Select the 5 best products to recommend. Consider:
1. Complementary items (accessories, related products)
2. Similar but different price tiers
3. Same category but different brands

Return JSON: [{{"id": "...", "reason": "..."}}]
"""
```

---

## 5. Eval Criteria

| Metric | Before (Random) | Target (AI) | Cách đo |
|---|---|---|---|
| Relevance Score | ~20% (random) | ≥ 70% | Manual eval: 5 test products × 5 recommendations |
| Category Match Rate | ~30% | ≥ 60% | Same-category recommendations / total |
| Latency p95 | ~50ms | < 100ms | OpenTelemetry |
| Cost per request | $0 | < $0.0001 | AWS Cost Explorer |

---

## 6. Rủi ro & Giảm thiểu

| Rủi ro | Khả năng | Giảm thiểu |
|---|---|---|
| Embeddings chưa sẵn sàng (batch job chưa chạy) | Trung bình | Fallback về random nếu `embedding IS NULL` |
| pgvector driver cho Python chưa cài | Thấp | `pip install pgvector` trong requirements.txt |
| Recommendation service không connect được PostgreSQL | Trung bình | Hiện tại connect qua Product Catalog gRPC; cần thêm DB connection string |
| Kết quả embedding similarity quá giống nhau | Thấp | Thêm diversity filter (không gợi ý > 2 products cùng subcategory) |
