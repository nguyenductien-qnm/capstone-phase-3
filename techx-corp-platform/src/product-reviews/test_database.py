import os
from unittest.mock import MagicMock, patch
import pytest

os.environ.setdefault("DB_CONNECTION_STRING", "host=test user=test password=test dbname=test")

import psycopg2
from database import fetch_product_reviews_from_db, execute_with_retry

def test_fetch_product_reviews_ordering():
    # Test that the query has ORDER BY id
    with patch('database.psycopg2.connect') as mock_connect:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        
        mock_cursor.fetchall.return_value = [("user1", "good", 5), ("user2", "bad", 1)]
        
        res = fetch_product_reviews_from_db("TEST_ID")
        
        assert len(res) == 2
        mock_cursor.execute.assert_called_once()
        query = mock_cursor.execute.call_args[0][0]
        assert "ORDER BY ID" in query.upper(), "Query must include ORDER BY id to guarantee determinism"


def test_execute_with_retry_backoff():
    # Test that execute_with_retry actually retries on transient errors
    call_count = 0
    
    def failing_work(conn):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise psycopg2.OperationalError("Connection reset by peer")
        return "success"

    with patch('database.psycopg2.connect') as mock_connect:
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        
        # We need to speed up the sleep to not block tests
        with patch('database.time.sleep') as mock_sleep:
            res = execute_with_retry(failing_work)
            
            assert res == "success"
            assert call_count == 3
            assert mock_sleep.call_count == 2


def main_live():
    conn_str = os.environ.get("DB_CONNECTION_STRING", "")
    if not conn_str or conn_str == "host=test user=test password=test dbname=test":
        print("SKIP: main_live() requires a real DB_CONNECTION_STRING")
        return
        
    print("Running main_live()...")
    test_id = "OLJCESPC7Z"
    r1 = fetch_product_reviews_from_db(test_id)
    r2 = fetch_product_reviews_from_db(test_id)
    
    assert r1 == r2, "fetch_product_reviews_from_db returned non-deterministic results across two calls"
    print(f"OK: Live DB fetch returned deterministic order ({len(r1)} reviews)")

if __name__ == "__main__":
    main_live()
