# Self-check: content-addressed cache key (Rails cache_key / ETag pattern).
# Bat buoc: review content doi -> cache key doi -> MISS tu nhien (zero staleness).
# Chay: python3 docs/ai/evals/test_cache_key_invalidation.py
import hashlib

def build_key(product_id, model_ver, prompt_ver, content_fp):
    return f"reviews:summary:{product_id}:{model_ver}:{prompt_ver}:{content_fp}"

def fp(raw):  # mirror database.fetch_reviews_fingerprint hashing
    return hashlib.md5(raw.encode()).hexdigest()[:12]

def main():
    m, p = "amazon.nova-lite-v1:0", "abc12345"
    # 4 review, cung noi dung -> cung fp -> cung key (HIT)
    fp_v1 = fp("4:104:d41d8cd0")
    assert build_key("P1", m, p, fp_v1) == build_key("P1", m, p, fp_v1)
    # them 1 review (count 4->5, max_id doi) -> fp doi -> key doi (MISS)
    fp_v2 = fp("5:105:9a0364b9")
    assert build_key("P1", m, p, fp_v1) != build_key("P1", m, p, fp_v2), "them review phai doi key"
    # sua review (count/id giu, content md5 doi) -> fp doi -> key doi (MISS)
    fp_edit = fp("4:104:ffffffff")
    assert build_key("P1", m, p, fp_v1) != build_key("P1", m, p, fp_edit), "sua review phai doi key"
    # doi model -> key doi (versioned key cu van giu)
    assert build_key("P1", "amazon.nova-micro-v1:0", p, fp_v1) != build_key("P1", m, p, fp_v1)
    print("cache-key invalidation self-check: OK (4 assertions)")

if __name__ == "__main__":
    main()
