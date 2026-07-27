"""Long-term user memory (MANDATE-23 Phase 5).

Lưu sở thích / ngữ cảnh người dùng bền (Postgres ai.user_memory) thay vì
Valkey — ElastiCache là cache có eviction, dữ liệu người dùng bay mất khi
RAM đầy là fail tiêu chí "thông tin bền".

Pipeline kiểu Mem0 rút gọn:
  extract  → rule cho slot rõ ràng (category, budget, experience, use_case)
  update   → UPSERT (user_id, key), giữ updated_at — mới thắng cũ
  read     → load tất cả key-value cho user_id
"""

from __future__ import annotations

import logging
import os
import re

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# DB connection
# ---------------------------------------------------------------------------
_conn = None


def _get_conn():
    global _conn
    if _conn is not None:
        try:
            _conn.cursor().execute("SELECT 1")
            return _conn
        except Exception:
            _conn = None

    db_str = os.environ.get("DB_CONNECTION_STRING")
    if not db_str:
        logger.warning("DB_CONNECTION_STRING not set — long-term memory disabled")
        return None

    try:
        import psycopg2
        _conn = psycopg2.connect(db_str)
        _conn.autocommit = False
        logger.info("Connected to Postgres for long-term memory")
        return _conn
    except Exception as e:
        logger.error("Failed to connect to Postgres for memory: %s", e)
        return None

def fetch_data_fingerprint() -> str:
    """Fingerprint của TOÀN BỘ nguồn mà câu trả lời copilot có thể dựa vào:
    catalog **và** review.

    Chỉ dùng catalog_fp là chưa đủ — đo 27/07: sửa một review của OLJCESPC7Z rồi hỏi
    lại, copilot vẫn `hit_exact` và trả điểm 3.8 cũ. MANDATE-23 ghi rõ "nguồn đã đổi mà
    cache vẫn trả kết quả cũ = fail", nên key phải ghim cả hai nguồn.
    """
    import hashlib
    return hashlib.md5(
        f"{fetch_catalog_fingerprint()}:{fetch_reviews_global_fingerprint()}".encode()
    ).hexdigest()[:12]


def fetch_reviews_global_fingerprint() -> str:
    """Fingerprint toàn bảng reviews.productreviews (50 dòng — 1 aggregate query rẻ)."""
    conn = _get_conn()
    if conn is None:
        return "nocache"
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*), COALESCE(MAX(id), 0), "
                "COALESCE(MD5(STRING_AGG(description || '|' || score::text, ',' ORDER BY id)), '') "
                "FROM reviews.productreviews"
            )
            count, max_id, content_md5 = cur.fetchone()
            import hashlib
            return hashlib.md5(f"{count}:{max_id}:{content_md5}".encode()).hexdigest()[:12]
    except Exception as e:
        logger.error("Failed to fetch reviews fingerprint: %s", e)
        return "nocache"


def fetch_catalog_fingerprint() -> str:
    """Content fingerprint cua catalog.products — cho content-addressed cache key."""
    conn = _get_conn()
    if conn is None:
        return "nocache"
    try:
        with conn.cursor() as cur:
            query = (
                "SELECT COUNT(*), COALESCE(MAX(id), ''), "
                "COALESCE(MD5(STRING_AGG(description || '|' || price_units::text || '|' || name, ',' ORDER BY id)), '') "
                "FROM catalog.products"
            )
            cur.execute(query)
            count, max_id, content_md5 = cur.fetchone()
            raw = f"{count}:{max_id}:{content_md5}"
            import hashlib
            return hashlib.md5(raw.encode()).hexdigest()[:12]
    except Exception as e:
        logger.error("Failed to fetch catalog fingerprint: %s", e)
        try:
            conn.rollback()
        except:
            pass
        return "nocache"



def get_semantic_cache(scope_key: str, embedding: list, threshold: float = 0.1):
    conn = _get_conn()
    if conn is None:
        return None, 0.0
    try:
        with conn.cursor() as cur:
            vec_str = "[" + ",".join(str(f) for f in embedding) + "]"
            query = """
                SELECT answer, 1 - (question_embedding <=> %s::vector) AS similarity
                FROM ai.semantic_cache
                WHERE scope_key = %s AND (question_embedding <=> %s::vector) < %s
                ORDER BY question_embedding <=> %s::vector
                LIMIT 1
            """
            # Wait, threshold in product-reviews is passed as 1 - similarity.
            # If similarity >= min_sim, then distance < 1 - min_sim.
            # Here threshold is distance threshold. 
            cur.execute(query, (vec_str, scope_key, vec_str, threshold, vec_str))
            row = cur.fetchone()
            if row:
                return row[0], float(row[1])
            return None, 0.0
    except Exception as e:
        logger.error("Failed to fetch semantic cache: %s", e)
        try:
            conn.rollback()
        except:
            pass
        return None, 0.0

def insert_semantic_cache(scope_key: str, question: str, embedding: list, answer: str):
    conn = _get_conn()
    if conn is None:
        return
    try:
        with conn.cursor() as cur:
            vec_str = "[" + ",".join(str(f) for f in embedding) + "]"
            query = """
                INSERT INTO ai.semantic_cache (scope_key, question, question_embedding, answer)
                VALUES (%s, %s, %s::vector, %s)
            """
            cur.execute(query, (scope_key, question, vec_str, answer))
        conn.commit()
    except Exception as e:
        logger.error("Failed to insert semantic cache: %s", e)
        try:
            conn.rollback()
        except:
            pass

# ---------------------------------------------------------------------------
# Extract — rule-based slot extraction
# ---------------------------------------------------------------------------
_CATEGORY_PATTERNS = {
    "telescope": re.compile(
        r"(kính thiên văn|telescope|kính viễn vọng|explorascope|refractor|astrograph)",
        re.IGNORECASE,
    ),
    "binoculars": re.compile(
        r"(ống nhòm|binocular|roof binocular)", re.IGNORECASE
    ),
    "accessories": re.compile(
        r"(phụ kiện|accessori|filter|lens|flashlight|imager|eyepiece)", re.IGNORECASE
    ),
    "books": re.compile(r"(sách|book|comet book)", re.IGNORECASE),
}

_BUDGET_RE = re.compile(
    r"(dưới|under|below|less than|<)\s*(\d[\d,.]*)\s*(usd|đồng|vnd|\$)?",
    re.IGNORECASE,
)
_BUDGET_RANGE_RE = re.compile(
    r"(\d[\d,.]*)\s*[-–]\s*(\d[\d,.]*)\s*(usd|đồng|vnd|\$)?",
    re.IGNORECASE,
)

_EXPERIENCE_PATTERNS = {
    "beginner": re.compile(
        r"(mới bắt đầu|beginner|entry.?level|người mới|newbie|cho trẻ|cho bé|kids|children)",
        re.IGNORECASE,
    ),
    "intermediate": re.compile(
        r"(trung cấp|intermediate|có kinh nghiệm|casual)", re.IGNORECASE
    ),
    "advanced": re.compile(
        r"(chuyên nghiệp|advanced|expert|professional|serious|pro)", re.IGNORECASE
    ),
}

_USE_CASE_PATTERNS = {
    "stargazing": re.compile(
        r"(ngắm sao|stargazing|thiên văn|night sky|deep.?sky|nebula|planet|moon)",
        re.IGNORECASE,
    ),
    "astrophotography": re.compile(
        r"(chụp ảnh|astrophotograph|imaging|astroimag|camera|ccd|dslr)", re.IGNORECASE
    ),
    "birdwatching": re.compile(
        r"(xem chim|birdwatch|bird.?watch|nature observation)", re.IGNORECASE
    ),
    "travel": re.compile(
        r"(du lịch|travel|camping|portable|lightweight|di chuyển|on the go)",
        re.IGNORECASE,
    ),
    "kids": re.compile(
        r"(trẻ em|kids|children|family|gia đình|con|bé)", re.IGNORECASE
    ),
}


def extract_user_preferences(question: str, answer: str) -> dict[str, str]:
    """Rule-based extraction of user preferences — CHỈ từ lời của khách.

    Không đọc `answer`: câu trả lời của bot luôn nhắc tên sản phẩm và trình độ, gộp vào
    sẽ ghi nhầm thành sở thích của khách. Đo 27/07: user chỉ hỏi giá ống nhòm mà memory
    sinh ra `preferred_category=telescope`, `experience_level=beginner`. Hai hệ quả:
    memory sai, và fingerprint memory đổi sau mỗi lượt nên cache L1 không bao giờ trúng.
    Memory phải là điều KHÁCH nói, không phải điều BOT nói.
    """
    text = question
    prefs: dict[str, str] = {}

    # Category
    for cat, pat in _CATEGORY_PATTERNS.items():
        if pat.search(text):
            prefs["preferred_category"] = cat
            break

    # Budget
    m = _BUDGET_RE.search(text)
    if m:
        prefs["budget_range"] = f"under {m.group(2)} {m.group(3) or 'USD'}"
    else:
        m = _BUDGET_RANGE_RE.search(text)
        if m:
            prefs["budget_range"] = f"{m.group(1)}-{m.group(2)} {m.group(3) or 'USD'}"

    # Experience level
    for level, pat in _EXPERIENCE_PATTERNS.items():
        if pat.search(text):
            prefs["experience_level"] = level
            break

    # Use case
    for uc, pat in _USE_CASE_PATTERNS.items():
        if pat.search(text):
            prefs["use_case"] = uc
            break

    return prefs


# ---------------------------------------------------------------------------
# Save — UPSERT into ai.user_memory
# ---------------------------------------------------------------------------

def save_user_memory(user_id: str, preferences: dict[str, str]) -> None:
    """Ghi sở thích vào Postgres. PII phải được redact TRƯỚC khi gọi hàm này."""
    if not preferences:
        return
    conn = _get_conn()
    if conn is None:
        return
    try:
        with conn.cursor() as cur:
            for key, value in preferences.items():
                cur.execute(
                    """
                    INSERT INTO ai.user_memory (user_id, key, value, updated_at)
                    VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (user_id, key)
                    DO UPDATE SET value = EXCLUDED.value, updated_at = CURRENT_TIMESTAMP
                    """,
                    (user_id, key, value),
                )
        conn.commit()
        logger.info("Saved %d memory keys for user=%s", len(preferences), user_id)
    except Exception as e:
        logger.error("Failed to save user memory: %s", e)
        try:
            conn.rollback()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Load — read all key-value for a user
# ---------------------------------------------------------------------------

def load_user_memory(user_id: str) -> dict[str, str]:
    conn = _get_conn()
    if conn is None:
        return {}
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT key, value FROM ai.user_memory WHERE user_id = %s",
                (user_id,),
            )
            return {row[0]: row[1] for row in cur.fetchall()}
    except Exception as e:
        logger.error("Failed to load user memory: %s", e)
        return {}


# ---------------------------------------------------------------------------
# Format — build prompt context block
# ---------------------------------------------------------------------------
_LABEL_MAP = {
    "preferred_category": "Loại sản phẩm quan tâm",
    "budget_range": "Ngân sách",
    "experience_level": "Trình độ",
    "use_case": "Mục đích sử dụng",
}


def format_memory_for_prompt(memory: dict[str, str]) -> str:
    """Format memory as a brief context block for injection into the prompt."""
    if not memory:
        return ""
    parts = []
    for key, value in memory.items():
        label = _LABEL_MAP.get(key, key)
        parts.append(f"{label}: {value}")
    return "Thông tin đã biết về khách hàng này (sở thích, KHÔNG phải dữ liệu sản phẩm): " + ", ".join(parts) + "."
