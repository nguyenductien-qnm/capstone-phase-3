import os
from unittest.mock import MagicMock, patch

import psycopg2

os.environ.setdefault("DB_CONNECTION_STRING", "host=test user=test password=test dbname=test")

from database import execute_with_retry, fetch_product_reviews_from_db


def _pool_with_connection():
    mock_pool = MagicMock()
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_pool.getconn.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    return mock_pool, mock_conn, mock_cursor


def test_fetch_product_reviews_ordering():
    mock_pool, mock_conn, mock_cursor = _pool_with_connection()
    mock_cursor.fetchall.return_value = [("user1", "good", 5), ("user2", "bad", 1)]

    with patch("database.get_connection_pool", return_value=mock_pool):
        result = fetch_product_reviews_from_db("TEST_ID")

    assert len(result) == 2
    query = mock_cursor.execute.call_args.args[0]
    assert "ORDER BY ID" in query.upper()
    mock_pool.putconn.assert_called_once_with(mock_conn, close=False)


def test_execute_with_retry_backoff():
    calls = 0
    mock_pool, mock_conn, _ = _pool_with_connection()

    def failing_work(_conn):
        nonlocal calls
        calls += 1
        if calls < 3:
            raise psycopg2.OperationalError("Connection reset by peer")
        return "success"

    with patch("database.get_connection_pool", return_value=mock_pool), patch("database.time.sleep") as mock_sleep:
        result = execute_with_retry(failing_work)

    assert result == "success"
    assert calls == 3
    assert mock_sleep.call_count == 2
    assert mock_pool.putconn.call_args_list == [
        ((mock_conn,), {"close": True}),
        ((mock_conn,), {"close": True}),
        ((mock_conn,), {"close": False}),
    ]
