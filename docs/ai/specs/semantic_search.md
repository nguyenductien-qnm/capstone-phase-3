# Spec: Semantic Search nâng cao (Hạng mục Đua Top)

> **Trạng thái:** Draft  
> **Trụ:** Performance Efficiency / Cost Optimization  
> **Ngày:** 2026-07-09  
> **Tác giả:** Nhóm AI (AIO03) - TF1  
> **ADR liên quan:** ADR-008  

---

## 1. Bối cảnh & Vấn đề

### 1.1 Thực trạng hiện tại

Hàm `SearchProducts` trong Product Catalog service (`src/product-catalog/main.go:293`) sử dụng **keyword matching** đơn thuần:

```sql
SELECT ... FROM catalog.products p
WHERE LOWER(p.name) LIKE $1 OR LOWER(p.description) LIKE $1
ORDER BY p.id
```

**Hạn chế nghiêm trọng:**
| Truy vấn người dùng | Kết quả keyword search | Kết quả mong đợi |
|---|---|---|
| "tai nghe chống ồn dưới $50" | ❌ Không tìm được (không match "chống ồn") | ✅ Noise-cancelling headphones < $50 |
| "quà sinh nhật cho bạn gái" | ❌ Trả về 0 kết quả | ✅ Các sản phẩm phù hợp làm quà |
| "wireless earbuds for gym" | ❌ Chỉ match nếu có chính xác từ "wireless earbuds" | ✅ Tất cả tai nghe không dây phù hợp tập gym |
| "affordable laptop for students" | ❌ Phải gõ chính xác tên sản phẩm | ✅ Laptops giá rẻ phù hợp sinh viên |

### 1.2 Yêu cầu từ RULES.md

> Line 66: **Mở rộng (đua top):** semantic search nâng cao [...]

### 1.3 Yêu cầu từ AI_FEATURE.md

> Intent #1 (Cốt lõi): Tìm sản phẩm NL — "tai nghe chống ồn dưới $50" → tìm + lọc → query tự nhiên ra đúng sản phẩm, không phải keyword cứng.

---

## 2. Phương án đã đánh giá

### 2.1 Option A: Amazon Titan Embeddings + pgvector (PostgreSQL) ⭐ **CHỌN**

**Kiến trúc:**
```
User Query (NL)
     │
     ▼
┌─────────────────────┐
│  Product Catalog     │
│  Service (Go)        │
│                      │
│  1. Call Bedrock API │──────► Amazon Titan Embeddings
│     embed(query)     │◄────── vector[1024]
│                      │
│  2. pgvector query   │──────► PostgreSQL + pgvector
│     ORDER BY <=>     │◄────── top-K results
│                      │
│  3. (Optional) merge │
│     with keyword     │
│     results (RRF)    │
└─────────────────────┘
```

**Chi tiết kỹ thuật:**
- **Embedding Model:** `amazon.titan-embed-text-v2:0` (1024 dimensions, Amazon first-party → credit-eligible)
  - ⚠️ Xác nhận model khả dụng ở `us-east-1` **trước khi code**: `aws bedrock list-foundation-models --region us-east-1 --query "modelSummaries[?contains(modelId,'embed')].modelId"`
- **Vector Store:** pgvector extension trên PostgreSQL hiện có
- **Index:** HNSW (Hierarchical Navigable Small World) — tối ưu cho approximate nearest neighbor
- **Distance Metric:** Cosine similarity (`<=>`)
- **Pre-compute:** Chạy batch job embed tất cả sản phẩm khi bootstrap, lưu vào cột `embedding VECTOR(1024)`

**Chi phí:**
- Titan Text Embeddings V2: ~$0.00002/1K tokens → ~$0.001 cho toàn bộ catalog (< 200 products)
- Per-search: ~$0.000004 (embed query) → **gần như miễn phí**
- **100% credit-eligible** (Amazon native model)

**Latency:**
| Giai đoạn | p50 | p95 |
|---|---|---|
| Bedrock embed(query) | ~40ms | ~80ms |
| pgvector HNSW search | ~2ms | ~8ms |
| **Tổng** | **~42ms** | **~88ms** |

### 2.2 Option B: Amazon Titan Embeddings + OpenSearch

**Chi phí:** OpenSearch Serverless yêu cầu tối thiểu 2 OCU = ~$350/tháng → **Quá đắt, vượt ngân sách.**

**Kết luận:** ❌ Loại bỏ.

### 2.3 Option C: AWS Bedrock Knowledge Bases (Managed RAG)

**Chi phí:** Tự động tạo OpenSearch Serverless backend → cùng vấn đề chi phí như Option B.

**Kết luận:** ❌ Loại bỏ.

### 2.4 Option D: Hybrid Search (BM25 + Semantic + RRF)

**Kiến trúc:** Chạy song song keyword search (LIKE/FTS hiện tại) và vector search (pgvector), sau đó merge bằng **Reciprocal Rank Fusion (RRF)**:

```
score(d) = Σ 1/(k + rank_i(d))
```
với `k = 60` (hằng số RRF).

**Ưu điểm:** Xử lý tốt cả exact SKU/brand search (keyword wins) lẫn conceptual search (semantic wins).

**Kết luận:** ✅ Nên triển khai nếu còn thời gian, nhưng priority thấp hơn pure semantic.

---

## 3. Case Study

### 3.1 Amazon Product Search
- **Trước:** BM25 keyword matching trên Elasticsearch.
- **Sau:** Dense retrieval models (DSSM/bi-encoder) + vector search. Kết hợp với click-through signals.
- **Kết quả:** Tăng 12-15% Conversion Rate trên các truy vấn NL dài (long-tail queries).
- **Tham khảo:** [Amazon Search Science](https://www.amazon.science/blog/how-amazon-search-reduces-effort-for-customers), KDD 2022.

### 3.2 Shopify Semantic Search (2024)
- **Trước:** Exact keyword matching trên Storefront API.
- **Sau:** AI-powered semantic search sử dụng embeddings.
- **Kết quả:** +8% conversion trên các cửa hàng thử nghiệm, giảm 22% "no results" pages.
- **Tham khảo:** [Shopify Winter Editions 2024](https://www.shopify.com/editions/winter2024#semantic-search)

### 3.3 Instacart Hybrid Search
- **Kiến trúc:** BM25 + dense retrieval + learned sparse retrieval. Sử dụng RRF để merge.
- **Kết quả:** Xử lý tốt cả brand search ("Coca Cola") lẫn concept search ("healthy snack for kids").
- **Tham khảo:** [Instacart Engineering Blog](https://tech.instacart.com/)

### 3.4 Mercari Vector Search
- **Kiến trúc:** Sentence-BERT embeddings + FAISS → Elasticsearch k-NN plugin.
- **Kết quả:** Giảm 30% bounce rate trên trang tìm kiếm, tăng 18% items found per session.
- **Tham khảo:** [Mercari Engineering](https://engineering.mercari.com/)

---

## 4. Kế hoạch triển khai

### Phase 1: Database Schema (Day 1)
```sql
-- Bật pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Thêm cột embedding vào bảng products
ALTER TABLE catalog.products 
ADD COLUMN IF NOT EXISTS embedding VECTOR(1024);

-- Tạo HNSW index cho cosine similarity
CREATE INDEX IF NOT EXISTS idx_products_embedding_hnsw 
ON catalog.products 
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
```

### Phase 2: Batch Embedding Script (Day 1-2)
```python
# scripts/embed_products.py
import boto3, psycopg2, json

bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')

def embed_text(text: str) -> list[float]:
    response = bedrock.invoke_model(
        modelId='amazon.titan-embed-text-v2:0',
        body=json.dumps({
            "inputText": text,
            "dimensions": 1024,
            "normalize": True
        })
    )
    return json.loads(response['body'].read())['embedding']

def embed_all_products():
    conn = psycopg2.connect(os.environ['DATABASE_URL'])
    cur = conn.cursor()
    cur.execute("SELECT id, name, description, categories FROM catalog.products")
    for row in cur.fetchall():
        pid, name, desc, cats = row
        text = f"{name}. {desc}. Categories: {cats}"
        vec = embed_text(text)
        cur.execute(
            "UPDATE catalog.products SET embedding = %s WHERE id = %s",
            (str(vec), pid)
        )
    conn.commit()
```

### Phase 3: Modify Go Search Function (Day 2-3)
```go
// In main.go: searchProductsFromDB
func searchProductsFromDBSemantic(ctx context.Context, query string) ([]*pb.Product, error) {
    // 1. Embed the query via Bedrock
    queryVec := embedQuery(ctx, query) // calls Bedrock Titan Embeddings
    
    // 2. Vector similarity search with pgvector
    rows, err := db.QueryContext(ctx, `
        SELECT p.id, p.name, p.description, p.picture,
               p.price_currency_code, p.price_units, p.price_nanos, p.categories,
               1 - (p.embedding <=> $1::vector) AS similarity
        FROM catalog.products p
        WHERE p.embedding IS NOT NULL
        ORDER BY p.embedding <=> $1::vector
        LIMIT 10
    `, pgvector.NewVector(queryVec))
    // ...
}
```

### Phase 4: Feature Flag Integration (Day 3)
```json
// src/flagd/demo.flagd.json
{
  "semanticSearchEnabled": {
    "state": "ENABLED",
    "variants": { "on": true, "off": false },
    "defaultVariant": "on"
  }
}
```

### Phase 5: Eval & Benchmark (Day 4)
- Golden dataset: 20 truy vấn NL → sản phẩm kỳ vọng
- Metrics: **Recall@10**, **MRR (Mean Reciprocal Rank)**, **Latency p95**
- Before/After comparison

---

## 5. Eval Criteria

| Metric | Target | Cách đo |
|---|---|---|
| Recall@10 | ≥ 80% | Golden dataset 20 queries |
| MRR | ≥ 0.6 | Golden dataset |
| Latency p95 | < 200ms | OpenTelemetry traces |
| Cost/search | < $0.00005 | AWS Cost Explorer |
| Fallback rate | < 5% | Prometheus counter |

---

## 6. Rủi ro & Giảm thiểu

| Rủi ro | Khả năng | Giảm thiểu |
|---|---|---|
| pgvector chưa cài trên PostgreSQL in-cluster | Trung bình | Baseline là postgres chạy như pod (`ARCHITECTURE.md`), **chưa migrate RDS**. Check `SELECT * FROM pg_extension` trước; image `postgres` gốc không có pgvector → cần CDO đổi sang image `pgvector/pgvector` hoặc cài extension. Nếu BTC ban directive migrate sang RDS, kiểm tra lại vì RDS PostgreSQL hỗ trợ pgvector từ 15.2+. |
| Bedrock Embeddings API timeout | Thấp | Cache embeddings cho sản phẩm (one-time); retry cho query embedding |
| Go client cho pgvector chưa mature | Thấp | Sử dụng raw SQL với `::vector` cast |
| Kết quả semantic không chính xác cho brand search | Trung bình | Triển khai Hybrid Search (Phase 2) |
