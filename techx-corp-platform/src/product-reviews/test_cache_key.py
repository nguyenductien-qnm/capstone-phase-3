# Self-check: Ask-AI cache key must include the question. Bug reproduced live
# 17/07 on prod — two different questions about the same product collided on
# the same Valkey key, so every question after the first got back whatever
# answer was cached first, regardless of what was actually asked. Run:
#   python3 src/product-reviews/test_cache_key.py
import os

# database.py reads this at import time (must_map_env) — dummy value, no real connection made.
os.environ.setdefault("DB_CONNECTION_STRING", "host=test user=test password=test dbname=test")

from product_reviews_server import build_ai_assistant_cache_key


def main():
    args = ("9SIQT8TOJO", "nova-lite", "abc123", "fp1")

    key_a = build_ai_assistant_cache_key(*args, "Can you summarize the reviews?")
    key_b = build_ai_assistant_cache_key(*args, "What age(s) is this recommended for?")
    assert key_a != key_b, "different questions must not collide on the same cache key"

    # normalization: same question, different case/whitespace -> same key
    key_c = build_ai_assistant_cache_key(*args, "  What age(s) IS this recommended for?  ")
    assert key_b == key_c, "case/whitespace-only differences should still hit the cache"

    print("cache_key self-check: OK (2 assertions)")


if __name__ == "__main__":
    main()
