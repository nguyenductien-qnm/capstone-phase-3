#!/usr/bin/python

# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

# Python
import os
import simplejson as json
import logging

# Postgres
import psycopg2
from psycopg2.pool import ThreadedConnectionPool

logger = logging.getLogger("main")

def must_map_env(key: str):
    value = os.environ.get(key)
    if value is None:
        raise Exception(f'{key} environment variable must be set')
    return value

# Retrieve Postgres environment variables
db_connection_str = must_map_env('DB_CONNECTION_STRING')

class DynamicThreadedConnectionPool(ThreadedConnectionPool):
    """
    Custom Connection Pool resolving two key challenges:
    1. Thread-safe operations under multi-threaded gRPC.
    2. Dynamic credential loading from kubernetes secrets volume mount
       (/etc/db-secrets/reviews-db-conn) without pod restarts.
    """
    def _connect(self, key=None):
        secret_path = "/etc/db-secrets/reviews-db-conn"
        try:
            if os.path.exists(secret_path):
                with open(secret_path, "r") as f:
                    current_dsn = f.read().strip()
                
                # Update connection arguments used by AbstractConnectionPool.
                # WARNING: Only works if the pool is initialized with a dsn parameter.
                # If individual kwargs (host=, user=, etc.) are passed, psycopg2 Connect
                # prioritizes them over the DSN string.
                if "dsn" in self._kwargs:
                    self._kwargs["dsn"] = current_dsn
                elif self._args:
                    args_list = list(self._args)
                    args_list[0] = current_dsn
                    self._args = tuple(args_list)
                else:
                    self._kwargs["dsn"] = current_dsn
                
                logger.info("Successfully reloaded database DSN into connection pool arguments.")
        except Exception as e:
            logger.warning(f"Failed to read dynamic DSN file. Falling back to cached DSN. Error: {e}")
        
        return super()._connect(key)

# Global pool initialization
db_pool = DynamicThreadedConnectionPool(5, 20, dsn=db_connection_str)

def fetch_product_reviews(product_id):
    try:
        return json.dumps(fetch_product_reviews_from_db(product_id), use_decimal=True)
    except Exception as e:
        return json.dumps({"error": str(e)})

def fetch_product_reviews_from_db(request_product_id):
    # Retry up to 3 times to evict and recover from connection failures
    for attempt in range(3):
        connection = db_pool.getconn()
        try:
            with connection.cursor() as cursor:
                query = "SELECT username, description, score FROM reviews.productreviews WHERE product_id = %s"
                cursor.execute(query, (request_product_id, ))
                records = cursor.fetchall()
                db_pool.putconn(connection)
                return records
        except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
            logger.warning(f"Database connection error detected: {e}. Evicting dead connection and retrying...")
            db_pool.putconn(connection, close=True)
            if attempt == 2:
                raise
        except Exception as e:
            db_pool.putconn(connection)
            raise

def fetch_reviews_fingerprint(request_product_id):
    # Retry up to 3 times to evict and recover from connection failures
    for attempt in range(3):
        connection = db_pool.getconn()
        try:
            with connection.cursor() as cursor:
                query = (
                    "SELECT COUNT(*), COALESCE(MAX(id), 0), "
                    "COALESCE(MD5(STRING_AGG(description || '|' || score::text, ',' ORDER BY id)), '') "
                    "FROM reviews.productreviews WHERE product_id = %s"
                )
                cursor.execute(query, (request_product_id,))
                count, max_id, content_md5 = cursor.fetchone()
                import hashlib
                raw = f"{count}:{max_id}:{content_md5}"
                db_pool.putconn(connection)
                return hashlib.md5(raw.encode()).hexdigest()[:12]
        except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
            logger.warning(f"Database connection error detected: {e}. Evicting dead connection and retrying...")
            db_pool.putconn(connection, close=True)
            if attempt == 2:
                raise
        except Exception as e:
            db_pool.putconn(connection)
            raise

def fetch_avg_product_review_score_from_db(request_product_id):
    # Retry up to 3 times to evict and recover from connection failures
    for attempt in range(3):
        connection = db_pool.getconn()
        try:
            with connection.cursor() as cursor:
                query = "SELECT AVG(score) FROM reviews.productreviews WHERE product_id = %s"
                cursor.execute(query, (request_product_id, ))
                records = cursor.fetchall()
                
                db_pool.putconn(connection)
                if records and records[0][0] is not None:
                    average_score = records[0][0]
                    return f"{average_score:.1f}"
                return "0.0"
        except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
            logger.warning(f"Database connection error detected: {e}. Evicting dead connection and retrying...")
            db_pool.putconn(connection, close=True)
            if attempt == 2:
                raise
        except Exception as e:
            db_pool.putconn(connection)
            raise
