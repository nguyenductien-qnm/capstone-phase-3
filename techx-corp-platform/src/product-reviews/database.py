#!/usr/bin/python

# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

# Python
import hashlib
import os
import random
import time
import simplejson as json

# Postgres
import psycopg2
from psycopg2 import OperationalError, InterfaceError

# CDO-TBD1: absorb short DB blips (RDS failover / replica restart) without 5xx.
_DB_RETRY_MAX_ATTEMPTS = 5
_DB_RETRY_BASE_SECONDS = 0.1
_DB_RETRY_MAX_SECONDS = 2.0


def must_map_env(key: str):
    value = os.environ.get(key)
    if value is None:
        raise Exception(f'{key} environment variable must be set')
    return value


# Retrieve Postgres environment variables
db_connection_str = must_map_env('DB_CONNECTION_STRING')


def _is_transient_db_error(exc: BaseException) -> bool:
    """Retry only connection/network class failures, not SQL logic errors."""
    if isinstance(exc, (OperationalError, InterfaceError, TimeoutError, ConnectionError, OSError)):
        return True
    msg = str(exc).lower()
    markers = (
        'connection refused',
        'connection reset',
        'broken pipe',
        'server closed the connection',
        'terminating connection',
        'could not connect',
        'timeout',
        'timed out',
        'eof',
        'ssl connection has been closed',
        'the database system is starting up',
        'the database system is in recovery mode',
        'too many connections',
        'remaining connection slots',
        'network is unreachable',
        'name or service not known',
    )
    return any(m in msg for m in markers)


def _backoff_seconds(attempt: int) -> float:
    # attempt is 1-based; exponential with full jitter, capped.
    exp = min(_DB_RETRY_BASE_SECONDS * (2 ** (attempt - 1)), _DB_RETRY_MAX_SECONDS)
    return random.uniform(exp / 2.0, exp)


def connect_with_retry():
    """Open a psycopg2 connection with exponential backoff on transient errors."""
    last_err = None
    for attempt in range(1, _DB_RETRY_MAX_ATTEMPTS + 1):
        try:
            return psycopg2.connect(db_connection_str)
        except Exception as e:
            last_err = e
            if not _is_transient_db_error(e) or attempt == _DB_RETRY_MAX_ATTEMPTS:
                raise
            sleep_s = _backoff_seconds(attempt)
            time.sleep(sleep_s)
    raise last_err


def execute_with_retry(work):
    """
    Run work(connection) with connect + execute retry on transient blips.
    work must be idempotent (SELECT-only paths in this service).
    """
    last_err = None
    for attempt in range(1, _DB_RETRY_MAX_ATTEMPTS + 1):
        connection = None
        try:
            connection = connect_with_retry()
            return work(connection)
        except Exception as e:
            last_err = e
            if not _is_transient_db_error(e) or attempt == _DB_RETRY_MAX_ATTEMPTS:
                raise
            sleep_s = _backoff_seconds(attempt)
            time.sleep(sleep_s)
        finally:
            if connection is not None:
                try:
                    connection.close()
                except Exception:
                    pass
    raise last_err


def fetch_product_reviews(product_id):
    try:
        return json.dumps(fetch_product_reviews_from_db(product_id), use_decimal=True)
    except Exception as e:
        return json.dumps({"error": str(e)})


def fetch_product_reviews_from_db(request_product_id):
    def _work(connection):
        with connection.cursor() as cursor:
            query = "SELECT username, description, score FROM reviews.productreviews WHERE product_id= %s"
            cursor.execute(query, (request_product_id, ))
            return cursor.fetchall()

    return execute_with_retry(_work)


def fetch_reviews_fingerprint(request_product_id):
    """Content fingerprint cua tap review 1 san pham — cho content-addressed cache key.

    Co che chuan the gioi (Rails cache_key / HTTP ETag): key = ham cua STATE object.
    Review doi (them/sua/xoa) -> fingerprint doi -> cache key doi -> MISS tu nhien,
    khong bao gio serve summary cu. Khong dynamic-TTL doan, khong invalidate thu cong.

    1 aggregate query, index san tren product_id, ~5 dong/san pham -> re hon LLM call ~1000x.
    - COUNT + MAX(id): bat them/xoa review (id la IDENTITY PK auto-increment).
    - md5(content): bat SUA review (description/score doi ma count/id khong doi).
    """
    def _work(connection):
        with connection.cursor() as cursor:
            query = (
                "SELECT COUNT(*), COALESCE(MAX(id), 0), "
                "COALESCE(MD5(STRING_AGG(description || '|' || score::text, ',' ORDER BY id)), '') "
                "FROM reviews.productreviews WHERE product_id = %s"
            )
            cursor.execute(query, (request_product_id,))
            count, max_id, content_md5 = cursor.fetchone()
            raw = f"{count}:{max_id}:{content_md5}"
            return hashlib.md5(raw.encode()).hexdigest()[:12]

    return execute_with_retry(_work)


def fetch_avg_product_review_score_from_db(request_product_id):
    def _work(connection):
        with connection.cursor() as cursor:
            query = "SELECT AVG(score) FROM reviews.productreviews WHERE product_id= %s"
            cursor.execute(query, (request_product_id, ))
            records = cursor.fetchall()
            if records:
                average_score = records[0][0]
            else:
                average_score = None
            return f"{average_score:.1f}"

    return execute_with_retry(_work)
