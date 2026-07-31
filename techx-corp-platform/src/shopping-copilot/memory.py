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

import hashlib
import logging
import os
import re
import struct
import time

from semantic_guard import same_question

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
            return hashlib.sha256(raw.encode()).hexdigest()[:12]
    except Exception as e:
        logger.error("Failed to fetch catalog fingerprint: %s", e)
        try:
            conn.rollback()
        except:
            pass
        return "nocache"



SEMANTIC_INDEX = "copilot-semantic-idx"
SEMANTIC_PREFIX = "copilot:semantic:item:"
SEMANTIC_TTL = int(os.environ.get("COPILOT_CACHE_TTL", "3600"))
SEMANTIC_MAX_PER_SCOPE = int(os.environ.get("SEMANTIC_CACHE_MAX_PER_SCOPE", "200"))


def _scope_hash(scope_key: str) -> str:
    return hashlib.sha256(scope_key.encode()).hexdigest()


def _vector_bytes(embedding: list[float]) -> bytes:
    return struct.pack(f"<{len(embedding)}f", *embedding)


def _parse_semantic_results(raw) -> list[tuple[str, str, float]]:
    rows = []
    for i in range(2, len(raw), 2):
        fields = raw[i]
        data = {
            str(fields[j], "utf-8") if isinstance(fields[j], bytes) else fields[j]:
            str(fields[j + 1], "utf-8") if isinstance(fields[j + 1], bytes) else fields[j + 1]
            for j in range(0, len(fields), 2)
        }
        rows.append((data.get("question", ""), data.get("answer", ""),
                     float(data.get("distance", 1.0))))
    return rows


def ensure_semantic_index(client) -> bool:
    """Create the Valkey Search index once; safe to call on every process start."""
    try:
        client.execute_command(
            "FT.CREATE", SEMANTIC_INDEX, "ON", "HASH", "PREFIX", 1, SEMANTIC_PREFIX,
            "SCHEMA", "scope", "TAG", "embedding", "VECTOR", "HNSW", 6,
            "TYPE", "FLOAT32", "DIM", 1024, "DISTANCE_METRIC", "COSINE",
        )
        logger.info("Created Valkey semantic cache index %s", SEMANTIC_INDEX)
        return True
    except Exception as exc:
        if "already exists" in str(exc).lower() or "index exists" in str(exc).lower():
            return True
        logger.error("Valkey Search unavailable; L2 disabled: %s", exc)
        return False


def get_semantic_cache(client, scope_key: str, embedding: list, threshold: float = 0.1,
                       question: str | None = None):
    """Return the first safe Valkey vector hit within the cosine-distance threshold."""
    try:
        raw = client.execute_command(
            "FT.SEARCH", SEMANTIC_INDEX,
            f"@scope:{{{_scope_hash(scope_key)}}}=>[KNN 5 @embedding $query_vec AS distance]",
            "PARAMS", 2, "query_vec", _vector_bytes(embedding),
            "RETURN", 3, "question", "answer", "distance",
            "LIMIT", 0, 5, "DIALECT", 2,
        )
        for cached_q, answer, distance in _parse_semantic_results(raw):
            if distance > threshold:
                continue
            if question and not same_question(question, cached_q):
                logger.info("L2 guard blocked %r != %r (similarity=%.4f)",
                            question[:60], cached_q[:60], 1.0 - distance)
                continue
            return answer, 1.0 - distance
    except Exception as exc:
        logger.error("Failed to fetch Valkey semantic cache: %s", exc)
    return None, 0.0


def insert_semantic_cache(client, scope_key: str, question: str,
                          embedding: list, answer: str):
    """Store one bounded, TTL'd L2 entry in Valkey Search."""
    scope = _scope_hash(scope_key)
    key = f"{SEMANTIC_PREFIX}{scope}:{hashlib.md5(question.encode()).hexdigest()}"
    order_key = f"copilot:semantic:order:{scope}"
    now = time.time()
    try:
        pipe = client.pipeline()
        pipe.hset(key, mapping={
            "scope": scope,
            "question": question,
            "answer": answer,
            "embedding": _vector_bytes(embedding),
        })
        pipe.expire(key, SEMANTIC_TTL)
        pipe.zadd(order_key, {key: now})
        pipe.zremrangebyscore(order_key, 0, now - SEMANTIC_TTL)
        pipe.expire(order_key, SEMANTIC_TTL)
        pipe.execute()
        overflow = client.zcard(order_key) - SEMANTIC_MAX_PER_SCOPE
        if overflow > 0:
            for old_key, _ in client.zpopmin(order_key, overflow):
                client.delete(old_key)
    except Exception as exc:
        logger.error("Failed to insert Valkey semantic cache: %s", exc)

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
    # "ngân sách" (budget) chứa chữ "sách" — không loại trừ thì khách nói ngân sách
    # lại bị ghi thành thích sách (đo 27/07).
    "books": re.compile(r"(?<!ngân )\b(sách|book|comet book)\b", re.IGNORECASE),
}

_BUDGET_RE = re.compile(
    r"(dưới|under|below|less than|<)\s*(\d[\d,.]*)\s*(usd|đồng|vnd|\$)?",
    re.IGNORECASE,
)
_BUDGET_RANGE_RE = re.compile(
    r"(\d[\d,.]*)\s*[-–]\s*(\d[\d,.]*)\s*(usd|đồng|vnd|\$)?",
    re.IGNORECASE,
)

# Dấu hiệu khách đang NÓI VỀ MÌNH chứ không chỉ tra cứu: ngôi thứ nhất + động từ ý
# muốn. Không có dấu hiệu này thì câu hỏi chỉ là một lượt tìm kiếm.
_INTENT_MARKER = re.compile(
    r"(mình|tôi|em|tớ|chúng tôi|nhà tôi|\bi\b|\bmy\b|\bme\b)[^.?!]{0,40}"
    r"(thích|muốn|cần|đang tìm|tìm mua|quan tâm|mua|chơi|dùng|sử dụng|sưu tầm|là|"
    r"gợi ý|recommend|looking for|want|need|prefer|interested in)"
    r"|(gợi ý|tư vấn|recommend)[^.?!]{0,20}(cho mình|cho tôi|for me)",
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

    # CHỦ ĐỀ CÂU HỎI KHÔNG PHẢI SỞ THÍCH. "Ống nhòm giá bao nhiêu?" là một lượt tra
    # cứu, không phải tuyên bố "tôi thích ống nhòm". Ghi bừa gây hai hỏng: memory sai
    # người dùng, và mem_fp đổi sau MỖI lượt nên key L1 đổi theo → câu hỏi lặp không
    # bao giờ hit (đo 27/07: hit-rate 0/12 trên bộ 50% lặp). Vì vậy category và
    # use_case chỉ ghi khi khách nói rõ ý muốn ở ngôi thứ nhất.
    stated = bool(_INTENT_MARKER.search(text))

    # Category
    if stated:
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

    # Use case — cùng lý do với category: chỉ ghi khi khách nói rõ mục đích của MÌNH,
    # không ghi vì câu hỏi tình cờ chứa chữ "thiên văn".
    if stated:
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
    "preferred_category": "Preferred product category",
    "budget_range": "Budget",
    "experience_level": "Experience level",
    "use_case": "Intended use",
}


def format_memory_for_prompt(memory: dict[str, str]) -> str:
    """Format memory as a brief context block for injection into the prompt."""
    if not memory:
        return ""
    parts = []
    for key, value in memory.items():
        label = _LABEL_MAP.get(key, key)
        parts.append(f"{label}: {value}")
    return "Known customer preferences (not product facts): " + ", ".join(parts) + "."
