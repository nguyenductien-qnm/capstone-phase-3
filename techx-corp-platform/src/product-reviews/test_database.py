# Self-check: fetch_product_reviews_from_db must return reviews in a stable
# order. Mentor flagged 20/07 that the query had no ORDER BY, so Postgres row
# order was undefined — combined with the MAX_FIELD_CHARS/GROUNDING_MAX_SOURCE_CHARS
# truncation in shopping-copilot/guardrails.py, which reviews survived the cut
# was itself non-reproducible across runs. Run:
#   python3 src/product-reviews/test_database.py
import inspect
import os

os.environ.setdefault("DB_CONNECTION_STRING", "host=test user=test password=test dbname=test")

from database import fetch_product_reviews_from_db


def main():
    source = inspect.getsource(fetch_product_reviews_from_db)
    assert "ORDER BY id" in source, (
        "fetch_product_reviews_from_db must ORDER BY id, or row order is undefined "
        "and non-reproducible (Postgres gives no ordering guarantee without it)"
    )
    print("OK: fetch_product_reviews_from_db query has ORDER BY id")


if __name__ == "__main__":
    main()
